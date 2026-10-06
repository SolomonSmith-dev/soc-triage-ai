"""Streamlit front end for the public demo. Calls the demo API, so limits live in one place."""
import os

import httpx
import streamlit as st

from triage_engine.extractors import extract_observables

API_URL = os.environ.get("DEMO_API_URL", "http://127.0.0.1:8000")

SAMPLES = {
    "Active ransomware": (
        "Multiple file servers showing thousands of file modifications per minute. Files renamed with "
        ".lockbit extension. README.txt ransom notes appearing in every directory. Volume Shadow Copies "
        "deleted via vssadmin 30 minutes ago."
    ),
    "LSASS credential dump": (
        "EDR detected suspicious access to LSASS process memory by rundll32.exe with comsvcs.dll on "
        "workstation WKSTN-042. User account is jsmith. Process tree: cmd.exe -> rundll32.exe."
    ),
    "SSH brute force (Tor exit)": (
        "5000 failed SSH authentication attempts in last 10 minutes against host srv-bastion-01 from "
        "source IP 185.220.101.45 (known Tor exit). No successful authentications observed yet."
    ),
    "Out of scope (refusal)": "Cafeteria menu for Thursday: roasted vegetable soup, chicken tikka wrap, fruit cup.",
}

st.set_page_config(page_title="SOC Triage AI demo", page_icon=":material/shield:", layout="wide")
st.title("SOC Triage AI")
st.caption("RAG-grounded alert triage. Public demo: do not paste real alert data. Requests are rate limited "
           "and total model usage is capped per day.")


def visitor_ip() -> str:
    try:
        xff = st.context.headers.get("X-Forwarded-For", "")
        return [p.strip() for p in xff.split(",") if p.strip()][-1]
    except Exception:
        return ""


def budget_line() -> None:
    try:
        b = httpx.get(f"{API_URL}/budget", timeout=3).json()
        st.sidebar.metric("Demo tokens left today", f"{b['tokens_remaining']:,}", help=f"Cap {b['daily_token_cap']:,}, resets {b['resets_at']}")
    except Exception:
        st.sidebar.caption("Budget unavailable")


with st.sidebar:
    st.subheader("Samples")
    for label, text in SAMPLES.items():
        if st.button(label, use_container_width=True):
            st.session_state["alert"] = text
    budget_line()

alert = st.text_area("Alert", key="alert", height=140, placeholder="Paste an alert, or pick a sample on the left.")

if alert.strip():
    obs = {k: v for k, v in extract_observables(alert).items() if v}
    if obs:
        st.caption("Observables (regex, runs before any model call): " +
                   "  ".join(f"`{k}`: {', '.join(v)}" for k, v in obs.items()))

if st.button("Run triage", type="primary", disabled=not alert.strip()):
    with st.spinner("Retrieving context and triaging..."):
        try:
            r = httpx.post(f"{API_URL}/triage", json={"alert": alert}, timeout=90,
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
        if c["guardrail_triggered"]:
            st.warning("Guardrail triggered: the system refused to fabricate a triage. Manual analyst review required.")
        st.write(t["summary"])
        st.markdown("**Recommended actions**\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(t["recommended_actions"], 1)))
        st.markdown("**MITRE ATT&CK:** " + (", ".join(t["mitre_techniques"]) or "none"))
        st.markdown("**Reasoning:** " + t["reasoning"])
        with st.expander(f"Evidence ({len(c['evidence']['chunks_retrieved'])} chunks, avg score {c['evidence']['avg_retrieval_score']})"):
            for ch in c["evidence"]["chunks_retrieved"]:
                st.markdown(f"`{ch['source']}` score {ch['score']}{' (cited)' if ch['cited'] else ''}")
                st.caption(ch["text"][:400])
        st.download_button("Download case JSON", r.text, file_name=f"{c['case_id']}.json", mime="application/json")
    else:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        st.info(body.get("message") or f"Request failed with status {r.status_code}.")
    budget_line()
