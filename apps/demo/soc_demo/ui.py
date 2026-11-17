"""Streamlit front end for the public demo. Calls the demo API, so limits live in one place."""
import os

import httpx
import streamlit as st

from soc_demo.guard import DemoConfig
from soc_demo.present import (
    CACHED_INTRO, EXACT_TEXT_NOTE, FEATURED, KNOWN_MISS, LIVE_INTRO, NOT_RECORDED, canonical_alert, corpus_md,
    download_name, is_known_miss, md_code, md_literal, option_label,
)
from triage_engine.extractors import extract_observables

API_URL = os.environ.get("DEMO_API_URL", "http://127.0.0.1:8000")
MAX_ALERT_CHARS = DemoConfig.from_env().max_alert_chars  # the API's limit, from the same environment

st.set_page_config(page_title="SOC Triage AI demo", page_icon=":material/shield:", layout="wide")


@st.cache_data(ttl=300, show_spinner=False)
def api_mode() -> str:
    """Raises on failure, so a failed lookup is not cached."""
    return httpx.get(f"{API_URL}/healthz", timeout=5).json().get("mode", "live")


@st.cache_data(ttl=600, show_spinner="Loading recorded alerts...")
def load_samples() -> list[dict]:
    r = httpx.get(f"{API_URL}/samples", timeout=120)  # cached mode verifies the recordings on first load
    r.raise_for_status()
    return r.json()


def _try(fn, default):
    try:
        return fn()
    except Exception:
        return default


MODE = _try(api_mode, "unknown")
CACHED = MODE == "cached"
SAMPLES = _try(load_samples, []) if MODE != "unknown" else []
BY_ID = {s["id"]: s for s in SAMPLES}

st.title("SOC Triage AI")
if CACHED:
    st.caption(CACHED_INTRO)
elif MODE == "live":
    st.caption(LIVE_INTRO)
else:
    st.warning("The demo backend is still starting. Reload the page in a minute.")


def visitor_ip() -> str:
    try:
        xff = st.context.headers.get("X-Forwarded-For", "")
        return [p.strip() for p in xff.split(",") if p.strip()][-1]
    except Exception:
        return ""


def budget_line(slot) -> None:
    """Writes into one sidebar slot, so the refresh after a run replaces the figure instead of adding one."""
    if MODE != "live":
        return
    try:
        b = httpx.get(f"{API_URL}/budget", timeout=3).json()
        slot.metric("Demo tokens left today", f"{b['tokens_remaining']:,}", help=f"Cap {b['daily_token_cap']:,}, resets {b['resets_at']}")
    except Exception:
        slot.caption("Budget unavailable")


with st.sidebar:
    st.subheader("Recorded alerts" if CACHED else "Samples")
    for cid, label in FEATURED.items():
        if cid in BY_ID and st.button(label, use_container_width=True):
            st.session_state["alert"] = BY_ID[cid]["alert"]
    if SAMPLES:
        with st.expander(f"{len(SAMPLES)} recorded harness alerts" if CACHED else f"All {len(SAMPLES)} harness alerts"):
            pick = st.selectbox("Harness case", list(BY_ID), format_func=lambda i: option_label(BY_ID[i]))
            if st.button("Load selected", use_container_width=True):
                st.session_state["alert"] = BY_ID[pick]["alert"]
    else:
        st.caption("Samples unavailable. The backend may still be starting; reload in a minute.")
    if CACHED:
        st.caption("Recorded mode: no model calls, so there is no token budget.")
    BUDGET = st.empty()
    budget_line(BUDGET)

alert = st.text_area("Alert", key="alert", height=140,
                     placeholder="Pick a recorded alert on the left." if CACHED else "Paste an alert, or pick a sample on the left.")
if CACHED:
    st.caption(EXACT_TEXT_NOTE)

if len(alert) > MAX_ALERT_CHARS:  # the API refuses these before extraction; the regexes are slow on some long input
    st.caption(f"Alert is {len(alert):,} characters; the demo accepts up to {MAX_ALERT_CHARS:,}.")
elif alert.strip():
    obs = {k: v for k, v in extract_observables(alert).items() if v}
    if obs:
        st.caption("Observables (regex, runs before any model call): " +
                   "  ".join(f"`{k}`: " + ", ".join(map(md_code, v)) for k, v in obs.items()))

if st.button("Run triage", type="primary", disabled=not alert.strip()):
    with st.spinner("Retrieving context and triaging..."):
        try:
            sent = canonical_alert(alert, SAMPLES) if CACHED else alert
            r = httpx.post(f"{API_URL}/triage", json={"alert": sent}, timeout=90,
                           headers={"X-Forwarded-For": visitor_ip()} if visitor_ip() else {})
        except httpx.HTTPError:
            st.error("The demo backend did not respond. Try again in a minute.")
            st.stop()
    if r.status_code == 200:
        c = r.json()
        t = c["triage"]
        a, b, d, e = st.columns(4)
        a.metric("Severity", t["severity"].upper())
        b.metric("Escalate", "Yes" if t["escalate"] else "No")
        d.metric("Confidence", t["confidence"])
        e.metric("Evidence", c["uncertainty_mode"].replace("_", " "))
        replayed = r.headers.get("x-demo-replay-case")
        if replayed:
            when = r.headers.get("x-demo-recorded-at", "")[:10]
            st.caption(f"Model step replayed from the harness recording of case `{replayed}` "
                       f"({c['version']['model']}{', recorded ' + when if when else ''}). "
                       "Extraction, retrieval and schema validation ran live on this request.")
            if is_known_miss(BY_ID.get(replayed), c):
                st.caption(KNOWN_MISS)
        if c["guardrail_triggered"]:
            st.warning("Guardrail triggered: the system refused to fabricate a triage. Manual analyst review required.")
            if not c["evidence"]["chunks_retrieved"]:
                st.caption("No model call was made: no corpus chunk reached the similarity threshold.")
        # model text goes through st.text, never Markdown: an injected alert cannot get an image or a link into the
        # page, and Streamlit's Markdown would autolink URLs even in escaped text
        st.text(t["summary"])
        st.markdown("**Recommended actions**")
        for i, x in enumerate(t["recommended_actions"], 1):
            st.text(f"{i}. {x}")
        st.markdown("**MITRE ATT&CK:** " + (", ".join(map(md_literal, t["mitre_techniques"])) or "none"))
        st.markdown("**Reasoning:**")
        st.text(t["reasoning"])
        with st.expander(f"Evidence ({len(c['evidence']['chunks_retrieved'])} chunks, avg score {c['evidence']['avg_retrieval_score']})"):
            for ch in c["evidence"]["chunks_retrieved"]:
                st.markdown(f"`{ch['source']}` score {ch['score']}{' (cited)' if ch['cited'] else ''}")
                st.caption(corpus_md(ch["text"][:400]))
        st.download_button("Download case JSON", r.text, file_name=download_name(c, replayed), mime="application/json")
    else:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if body.get("status") == "not_recorded":
            st.info(NOT_RECORDED)
        else:
            st.info(body.get("message") or f"Request failed with status {r.status_code}.")
        chunks = (body.get("retrieval") or {}).get("chunks") or []
        if chunks:
            st.markdown("**Retrieval ran live on this alert:** " +
                        ", ".join(f"`{ch['source']}` {ch['score']}" for ch in chunks))
    budget_line(BUDGET)
