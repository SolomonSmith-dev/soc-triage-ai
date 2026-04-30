"""SOC Triage AI — Streamlit dashboard. Three tabs: Triage / Evaluation / System."""
import json
import os
os.environ["TQDM_DISABLE"] = "1"

from datetime import datetime, timezone

import streamlit as st

from triage_engine.triage import SOCTriage, CORPUS_DIR
from triage_engine.extractors import extract_observables
from triage_engine.case_package import build_case_package, VERSION_META
from triage_engine.evaluation import (
    load_harness_results,
    run_harness_live,
    compute_eval_metrics,
)
from triage_engine.rag.corpus import load_corpus

st.set_page_config(
    page_title="SOC Triage AI",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}

    .title {font-size: 1.5rem; font-weight: 700; color: #e2e8f0;
            letter-spacing: -0.01em; margin-bottom: 0.1rem;}
    .subtitle {font-size: 0.82rem; color: #64748b; margin-bottom: 1.2rem;}

    .sev {padding: 0.25rem 0.65rem; border-radius: 3px; font-weight: 700;
          font-size: 0.78rem; letter-spacing: 0.5px; display: inline-block;
          text-transform: uppercase;}
    .sev-critical    {background:#991b1b; color:#fecaca;}
    .sev-high        {background:#9a3412; color:#fed7aa;}
    .sev-medium      {background:#854d0e; color:#fef08a;}
    .sev-low         {background:#166534; color:#bbf7d0;}
    .sev-informational {background:#334155; color:#cbd5e1;}

    .m-card {background: #0f172a; border: 1px solid #1e293b; border-radius: 6px;
             padding: 0.65rem 0.85rem;}
    .m-card .lbl {font-size: 0.65rem; color: #475569; text-transform: uppercase;
                  letter-spacing: 0.8px; margin-bottom: 0.3rem;}
    .m-card .val {font-size: 1.05rem; font-weight: 600; color: #e2e8f0;}

    .tt {background: #172554; color: #93c5fd; padding: 0.18rem 0.5rem;
         border-radius: 3px; font-family: 'SF Mono','Fira Code',monospace;
         font-size: 0.8rem; font-weight: 500; margin: 0 0.3rem 0.3rem 0;
         display: inline-block;}
    .st {background: #0f172a; border: 1px solid #1e293b; color: #94a3b8;
         padding: 0.15rem 0.4rem; border-radius: 3px; font-family: monospace;
         font-size: 0.75rem; margin: 0 0.25rem 0.25rem 0; display: inline-block;}

    .obs {padding: 0.18rem 0.5rem; border-radius: 3px;
          font-family: 'SF Mono', monospace; font-size: 0.75rem;
          margin: 0 0.25rem 0.25rem 0; display: inline-block; font-weight: 500;}
    .obs-net  {background: #064e3b; color: #6ee7b7;}
    .obs-host {background: #1e3a8a; color: #93c5fd;}
    .obs-hash {background: #581c87; color: #d8b4fe;}
    .obs-id   {background: #78350f; color: #fcd34d;}

    .uncert {padding: 0.22rem 0.55rem; border-radius: 3px; font-weight: 600;
             font-size: 0.72rem; letter-spacing: 0.5px; display: inline-block;
             text-transform: uppercase;}
    .uncert-actionable           {background:#166534; color:#bbf7d0;}
    .uncert-needs_more_context   {background:#854d0e; color:#fef08a;}
    .uncert-insufficient_evidence{background:#9a3412; color:#fed7aa;}
    .uncert-out_of_scope         {background:#334155; color:#cbd5e1;}

    .cited {color: #34d399; font-weight: 700;}
    .uncited {color: #475569;}

    .reasoning {background: #0f172a; border-left: 3px solid #2563eb;
                color: #cbd5e1; padding: 0.85rem 1rem; border-radius: 0 4px 4px 0;
                font-size: 0.88rem; line-height: 1.55;}

    .sec {font-size: 0.68rem; font-weight: 600; color: #475569;
          text-transform: uppercase; letter-spacing: 0.8px;
          margin: 1rem 0 0.4rem 0;}

    .esc-yes {color: #ef4444; font-weight: 700; font-size: 1.05rem;}
    .esc-no  {color: #475569; font-weight: 500; font-size: 1.05rem;}

    .empty {background: #0f172a; border: 1px dashed #1e293b; color: #334155;
            padding: 2.5rem; border-radius: 6px; text-align: center;
            font-size: 0.85rem;}

    .sb-title {font-size: 1rem; font-weight: 700; color: #e2e8f0;}
    .sb-meta {font-size: 0.72rem; color: #475569; line-height: 1.7;}

    .stTextArea textarea {font-family: 'SF Mono','Fira Code',monospace;
                          font-size: 0.88rem;}

    .override {background: #1e293b; color: #fde68a; padding: 0.15rem 0.4rem;
               border-radius: 3px; font-size: 0.7rem; font-weight: 600;
               margin-left: 0.4rem; text-transform: uppercase;
               letter-spacing: 0.5px;}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_triage():
    return SOCTriage()


@st.cache_resource
def cached_corpus():
    return load_corpus(CORPUS_DIR)


SAMPLES = {
    "Active ransomware": (
        "Multiple file servers showing thousands of file modifications per minute. "
        "Files renamed with .lockbit extension. README.txt ransom notes appearing "
        "in every directory. Volume Shadow Copies deleted via vssadmin 30 minutes ago."
    ),
    "LSASS credential dump": (
        "EDR detected suspicious access to LSASS process memory by rundll32.exe "
        "with comsvcs.dll on workstation WKSTN-042. User account is jsmith. "
        "Process tree: cmd.exe -> rundll32.exe."
    ),
    "Phishing + credential entry": (
        "User reported email from ceo@anthrop1c.com (note typo) requesting "
        "urgent wire transfer to new vendor. User clicked link and entered "
        "credentials before reporting. Email contained urgency language."
    ),
    "SSH brute force (Tor exit)": (
        "5000 failed SSH authentication attempts in last 10 minutes against "
        "host srv-bastion-01 from source IP 185.220.101.45 (known Tor exit). "
        "No successful authentications observed yet."
    ),
    "Insider data exfiltration": (
        "Employee jdoe (resignation notice given last week) downloaded 15GB of "
        "customer data from CRM in last 24 hours. Login from new device "
        "fingerprint. Email forwarding rule created to personal Gmail yesterday."
    ),
    "Gibberish (guardrail test)": (
        "asdfqwerzxcv 1234567890 lorem ipsum dolor sit amet"
    ),
}

OBS_GROUPS = {
    "ipv4": "obs-net", "url": "obs-net", "domain": "obs-net", "email": "obs-net",
    "hostname": "obs-host", "process": "obs-host", "filename": "obs-host",
    "registry_path": "obs-host",
    "md5": "obs-hash", "sha1": "obs-hash", "sha256": "obs-hash",
    "username": "obs-id",
}


def sev_badge(s):
    return f'<span class="sev sev-{s}">{s}</span>'


def tech_pills(ts):
    if not ts:
        return '<span style="color:#475569;font-size:0.82rem;">None identified</span>'
    return "".join(f'<span class="tt">{t}</span>' for t in ts)


def src_pills(ss):
    if not ss:
        return '<span style="color:#475569;font-size:0.82rem;">N/A</span>'
    return "".join(f'<span class="st">{s}</span>' for s in ss)


def obs_pills(observables):
    parts = []
    for k in ["ipv4", "url", "domain", "email", "hostname",
              "process", "filename", "registry_path",
              "md5", "sha1", "sha256", "username"]:
        for v in observables.get(k, []):
            cls = OBS_GROUPS.get(k, "obs-host")
            parts.append(f'<span class="obs {cls}" title="{k}">{v}</span>')
    if not parts:
        return '<span style="color:#475569;font-size:0.82rem;">No observables extracted</span>'
    return "".join(parts)


def uncertainty_badge(mode):
    return f'<span class="uncert uncert-{mode}">{mode.replace("_", " ")}</span>'


def case_to_markdown(case):
    """Render case package as analyst-readable markdown."""
    t = case["triage"]
    lines = [
        f"# SOC Triage Case: {case['case_id']}",
        f"_Generated: {case['timestamp']}_",
        "",
        f"**Severity:** {t['severity'].upper()} &nbsp; "
        f"**Confidence:** {t['confidence'].upper()} &nbsp; "
        f"**Escalate:** {'YES' if t['escalate'] else 'NO'} &nbsp; "
        f"**Mode:** {case['uncertainty_mode']}",
        "",
        "## Alert",
        "```",
        case["alert_raw"],
        "```",
        "",
        "## Summary",
        t["summary"],
        "",
        "## MITRE ATT&CK Techniques",
    ]
    if t["mitre_techniques"]:
        lines.extend(f"- {tech}" for tech in t["mitre_techniques"])
    else:
        lines.append("_None identified_")
    lines.extend(["", "## Recommended Actions"])
    lines.extend(f"{i}. {a}" for i, a in enumerate(t["recommended_actions"], 1))
    lines.extend(["", "## Reasoning", t["reasoning"], "", "## Observables"])
    for k, vals in case["observables"].items():
        if vals:
            lines.append(f"- **{k}:** {', '.join(vals)}")
    lines.extend([
        "", "## Evidence",
        f"- Avg retrieval score: {case['evidence']['avg_retrieval_score']}",
        f"- Sources cited: {', '.join(case['evidence']['sources_cited']) or 'None'}",
    ])
    if case["analyst_overrides"]:
        lines.extend(["", "## Analyst Overrides"])
        for o in case["analyst_overrides"]:
            lines.append(
                f"- **{o['field']}**: {o['original']} → {o['override']} ({o['rationale']})"
            )
    return "\n".join(lines)


for key, default in [
    ("alert_input", ""),
    ("current_case", None),
    ("analyst_overrides", []),
    ("eval_data", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


with st.sidebar:
    st.markdown('<div class="sb-title">SOC Triage AI</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown('<div class="sec">Sample alerts</div>', unsafe_allow_html=True)
    for label, text in SAMPLES.items():
        if st.button(label, use_container_width=True, key=f"s_{label}"):
            st.session_state.alert_input = text
            st.session_state.current_case = None
            st.session_state.analyst_overrides = []
            st.rerun()
    st.divider()
    st.markdown(
        '<div class="sb-meta">'
        f"Model &nbsp;{VERSION_META['model']}<br>"
        f"Embeddings &nbsp;{VERSION_META['embeddings']}<br>"
        f"Corpus &nbsp;{VERSION_META['corpus_chunks']} chunks<br>"
        f"Top-k &nbsp;{VERSION_META['top_k']} &nbsp;|&nbsp; "
        f"Min sim &nbsp;{VERSION_META['min_similarity']}"
        "</div>",
        unsafe_allow_html=True,
    )


st.markdown('<div class="title">SOC Triage AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Tier-1 alert triage &middot; MITRE ATT&CK grounded</div>',
    unsafe_allow_html=True,
)

with st.spinner("Indexing corpus..."):
    engine = load_triage()


def render_triage_tab(engine):
    alert_text = st.text_area(
        "Alert input",
        height=120,
        placeholder="Paste a raw alert from your SIEM, EDR, or SOAR platform...",
        label_visibility="collapsed",
        key="alert_input",
    )

    col_btn, _ = st.columns([1, 5])
    with col_btn:
        run = st.button(
            "Run Triage", type="primary", use_container_width=True,
            disabled=not alert_text.strip(),
        )

    if alert_text.strip():
        observables = extract_observables(alert_text)
        st.markdown(
            '<div class="sec">Observables extracted (deterministic)</div>',
            unsafe_allow_html=True,
        )
        st.markdown(obs_pills(observables), unsafe_allow_html=True)
    else:
        observables = {}

    if run and alert_text.strip():
        with st.spinner("Analyzing..."):
            triage_result, hits, guardrail = engine.triage_with_context(alert_text)
        case = build_case_package(
            alert_text, observables, triage_result, hits, guardrail,
        )
        st.session_state.current_case = case
        st.session_state.analyst_overrides = []

    case = st.session_state.current_case
    if case is None:
        st.markdown(
            '<div class="empty">Paste an alert or pick a sample from the sidebar.</div>',
            unsafe_allow_html=True,
        )
        return

    t = case["triage"]
    overrides = st.session_state.analyst_overrides
    override_field = {o["field"]: o for o in overrides}

    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ovr_sev = override_field.get("severity")
        sev_html = sev_badge(ovr_sev["override"]) if ovr_sev else sev_badge(t["severity"])
        suffix = '<span class="override">override</span>' if ovr_sev else ""
        st.markdown(
            f'<div class="m-card"><div class="lbl">Severity</div>{sev_html}{suffix}</div>',
            unsafe_allow_html=True,
        )
    with c2:
        ovr_esc = override_field.get("escalate")
        esc_val = ovr_esc["override"] if ovr_esc else t["escalate"]
        cls = "esc-yes" if esc_val else "esc-no"
        txt = "YES — escalate" if esc_val else "NO"
        suffix = '<span class="override">override</span>' if ovr_esc else ""
        st.markdown(
            f'<div class="m-card"><div class="lbl">Escalate</div>'
            f'<div class="{cls}">{txt}</div>{suffix}</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="m-card"><div class="lbl">Confidence</div>'
            f'<div class="val">{t["confidence"].upper()}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="m-card"><div class="lbl">Uncertainty</div>'
            f'{uncertainty_badge(case["uncertainty_mode"])}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sec">Summary</div>', unsafe_allow_html=True)
    st.info(t["summary"])

    left, right = st.columns([3, 2])
    with left:
        st.markdown('<div class="sec">Recommended actions</div>', unsafe_allow_html=True)
        for i, a in enumerate(t["recommended_actions"], 1):
            st.markdown(f"{i}. {a}")
        st.markdown('<div class="sec">Reasoning</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="reasoning">{t["reasoning"]}</div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="sec">MITRE ATT&CK</div>', unsafe_allow_html=True)
        st.markdown(tech_pills(t["mitre_techniques"]), unsafe_allow_html=True)
        st.markdown('<div class="sec">Sources</div>', unsafe_allow_html=True)
        st.markdown(src_pills(case["evidence"]["sources_cited"]),
                    unsafe_allow_html=True)
        st.markdown(
            f'<div class="sec">Avg retrieval &nbsp; '
            f'<span class="val">{case["evidence"]["avg_retrieval_score"]}</span></div>',
            unsafe_allow_html=True,
        )

    with st.expander("Evidence — retrieved chunks"):
        for c in case["evidence"]["chunks_retrieved"]:
            cited = '<span class="cited">cited</span>' if c["cited"] \
                else '<span class="uncited">not cited</span>'
            st.markdown(
                f"**{c['chunk_id']}** &middot; `{c['source']}` &middot; "
                f"score `{c['score']:.3f}` &middot; {cited}",
                unsafe_allow_html=True,
            )
            st.code(c["text"][:600], language="text")

    with st.expander("Analyst override"):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            new_sev = st.selectbox(
                "Override severity",
                ["(no override)", "critical", "high", "medium", "low", "informational"],
                key="ovr_sev_select",
            )
        with col_b:
            new_esc = st.selectbox(
                "Override escalation",
                ["(no override)", "True", "False"],
                key="ovr_esc_select",
            )
        with col_c:
            rationale = st.text_input("Rationale", key="ovr_rationale")

        if st.button("Apply override"):
            ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if new_sev != "(no override)" and new_sev != t["severity"]:
                st.session_state.analyst_overrides.append({
                    "field": "severity",
                    "original": t["severity"],
                    "override": new_sev,
                    "rationale": rationale or "(no rationale)",
                    "timestamp": ts,
                })
            if new_esc != "(no override)":
                bool_val = new_esc == "True"
                if bool_val != t["escalate"]:
                    st.session_state.analyst_overrides.append({
                        "field": "escalate",
                        "original": t["escalate"],
                        "override": bool_val,
                        "rationale": rationale or "(no rationale)",
                        "timestamp": ts,
                    })
            st.rerun()

    case_with_overrides = dict(case)
    case_with_overrides["analyst_overrides"] = list(st.session_state.analyst_overrides)
    json_blob = json.dumps(case_with_overrides, indent=2)
    md_blob = case_to_markdown(case_with_overrides)
    cdl, cdr = st.columns(2)
    with cdl:
        st.download_button(
            "Download JSON", data=json_blob,
            file_name=f"{case['case_id']}.json", mime="application/json",
            use_container_width=True,
        )
    with cdr:
        st.download_button(
            "Download Markdown", data=md_blob,
            file_name=f"{case['case_id']}.md", mime="text/markdown",
            use_container_width=True,
        )

    with st.expander("Raw case package JSON"):
        st.code(json_blob, language="json")


def render_evaluation_tab(engine):
    if st.session_state.eval_data is None:
        st.session_state.eval_data = load_harness_results()

    col_l, col_r = st.columns([4, 1])
    with col_l:
        st.markdown(
            '<div class="sec">Reliability harness — 7 canonical alerts</div>',
            unsafe_allow_html=True,
        )
    with col_r:
        if st.button("Run live (7 API calls)", use_container_width=True):
            with st.spinner("Running harness against live engine..."):
                st.session_state.eval_data = run_harness_live(engine)

    data = st.session_state.eval_data
    if data is None:
        st.markdown(
            '<div class="empty">No harness results found. '
            'Run <code>python -m tests.test_harness</code> from the CLI '
            'or click "Run live" above.</div>',
            unsafe_allow_html=True,
        )
        return

    metrics = compute_eval_metrics(data["results"])
    cols = st.columns(5)
    cards = [
        ("Pass rate",
         f"{metrics['pass_rate']*100:.0f}% ({metrics['passed']}/{metrics['total']})"),
        ("Severity accuracy",
         f"{metrics['severity_accuracy']*100:.0f}%"
         if metrics['severity_accuracy'] is not None else "n/a"),
        ("Escalation accuracy",
         f"{metrics['escalation_accuracy']*100:.0f}%"
         if metrics['escalation_accuracy'] is not None else "n/a"),
        ("Avg retrieval", f"{metrics['avg_retrieval_score']:.3f}"),
        ("Avg latency", f"{metrics['avg_latency']:.1f}s"),
    ]
    for col, (lbl, val) in zip(cols, cards):
        with col:
            st.markdown(
                f'<div class="m-card"><div class="lbl">{lbl}</div>'
                f'<div class="val">{val}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="sec">Per-case results</div>', unsafe_allow_html=True)
    rows = []
    for r in data["results"]:
        rows.append({
            "Test": r.get("id", "?"),
            "Severity": r.get("severity", "—"),
            "Escalate": r.get("escalate", "—"),
            "Techniques": ", ".join(r.get("techniques", []) or []),
            "Score": r.get("retrieval_score"),
            "Latency": r.get("latency_seconds"),
            "Result": "PASS" if r.get("passed") else "FAIL",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_system_tab(engine):
    st.markdown('<div class="sec">Version metadata</div>', unsafe_allow_html=True)
    rows = [{"Setting": k, "Value": str(v)} for k, v in VERSION_META.items()]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown('<div class="sec">Retrieval debugger</div>', unsafe_allow_html=True)
    q = st.text_input(
        "Query (skips LLM, returns top-k chunks only)",
        key="debug_query",
    )
    if st.button("Debug retrieval", disabled=not q.strip()):
        hits = engine.retriever.retrieve(q, top_k=VERSION_META["top_k"])
        if not hits:
            st.warning("No chunks above min similarity threshold.")
        else:
            for chunk, score in hits:
                passed = score >= VERSION_META["min_similarity"]
                badge = "above threshold" if passed else "below threshold"
                st.markdown(
                    f"**{chunk['id']}** &middot; `{chunk['source']}` &middot; "
                    f"score `{score:.3f}` &middot; {badge}",
                    unsafe_allow_html=True,
                )
                st.code(chunk["text"][:500], language="text")

    st.markdown('<div class="sec">Corpus stats</div>', unsafe_allow_html=True)
    chunks = cached_corpus()
    by_source = {}
    for c in chunks:
        by_source.setdefault(c["source"], 0)
        by_source[c["source"]] += 1
    avg_len = sum(len(c["text"]) for c in chunks) / len(chunks)
    st.markdown(
        f"Total chunks: **{len(chunks)}** &middot; "
        f"Sources: **{len(by_source)}** &middot; "
        f"Avg chunk length: **{avg_len:.0f} chars**"
    )
    st.dataframe(
        [{"Source": s, "Chunks": n} for s, n in sorted(by_source.items())],
        use_container_width=True, hide_index=True,
    )


tab_triage, tab_eval, tab_sys = st.tabs(["Triage", "Evaluation", "System"])

with tab_triage:
    render_triage_tab(engine)
with tab_eval:
    render_evaluation_tab(engine)
with tab_sys:
    render_system_tab(engine)
