"""SOC Triage AI — Streamlit interface."""
import json
import streamlit as st
from triage import SOCTriage

st.set_page_config(
    page_title="SOC Triage AI",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS — dark SOC dashboard aesthetic, no decorative nonsense
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}

    /* typography */
    .title {
        font-size: 1.5rem; font-weight: 700; color: #e2e8f0;
        letter-spacing: -0.01em; margin-bottom: 0.1rem;
    }
    .subtitle {
        font-size: 0.82rem; color: #64748b; margin-bottom: 1.2rem;
    }

    /* severity chips */
    .sev {
        padding: 0.25rem 0.65rem; border-radius: 3px; font-weight: 700;
        font-size: 0.78rem; letter-spacing: 0.5px; display: inline-block;
        text-transform: uppercase;
    }
    .sev-critical    {background:#991b1b; color:#fecaca;}
    .sev-high        {background:#9a3412; color:#fed7aa;}
    .sev-medium      {background:#854d0e; color:#fef08a;}
    .sev-low         {background:#166534; color:#bbf7d0;}
    .sev-informational {background:#334155; color:#cbd5e1;}

    /* metric cards */
    .m-card {
        background: #0f172a; border: 1px solid #1e293b; border-radius: 6px;
        padding: 0.65rem 0.85rem;
    }
    .m-card .lbl {
        font-size: 0.65rem; color: #475569; text-transform: uppercase;
        letter-spacing: 0.8px; margin-bottom: 0.3rem;
    }
    .m-card .val {
        font-size: 1.05rem; font-weight: 600; color: #e2e8f0;
    }

    /* technique pills */
    .tt {
        background: #172554; color: #93c5fd; padding: 0.18rem 0.5rem;
        border-radius: 3px; font-family: 'SF Mono','Fira Code',monospace;
        font-size: 0.8rem; font-weight: 500; margin: 0 0.3rem 0.3rem 0;
        display: inline-block;
    }
    /* source pills */
    .st {
        background: #0f172a; border: 1px solid #1e293b; color: #94a3b8;
        padding: 0.15rem 0.4rem; border-radius: 3px; font-family: monospace;
        font-size: 0.75rem; margin: 0 0.25rem 0.25rem 0; display: inline-block;
    }

    /* reasoning panel */
    .reasoning {
        background: #0f172a; border-left: 3px solid #2563eb; color: #cbd5e1;
        padding: 0.85rem 1rem; border-radius: 0 4px 4px 0; font-size: 0.88rem;
        line-height: 1.55;
    }

    /* section label */
    .sec {
        font-size: 0.68rem; font-weight: 600; color: #475569;
        text-transform: uppercase; letter-spacing: 0.8px;
        margin: 1rem 0 0.4rem 0;
    }

    /* escalation */
    .esc-yes {color: #ef4444; font-weight: 700; font-size: 1.05rem;}
    .esc-no  {color: #475569; font-weight: 500; font-size: 1.05rem;}

    /* empty state */
    .empty {
        background: #0f172a; border: 1px dashed #1e293b; color: #334155;
        padding: 2.5rem; border-radius: 6px; text-align: center;
        font-size: 0.85rem;
    }

    /* sidebar */
    .sb-title {font-size: 1rem; font-weight: 700; color: #e2e8f0;}
    .sb-meta {font-size: 0.72rem; color: #475569; line-height: 1.7;}

    /* textarea */
    .stTextArea textarea {
        font-family: 'SF Mono','Fira Code','Cascadia Code',monospace;
        font-size: 0.88rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_triage():
    return SOCTriage()


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


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "alert_input" not in st.session_state:
    st.session_state.alert_input = ""

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sb-title">SOC Triage AI</div>', unsafe_allow_html=True)
    st.divider()

    st.markdown('<div class="sec">Sample alerts</div>', unsafe_allow_html=True)
    for label, text in SAMPLES.items():
        if st.button(label, use_container_width=True, key=f"s_{label}"):
            st.session_state.alert_input = text
            st.rerun()

    st.divider()
    st.markdown(
        '<div class="sb-meta">'
        "Model &nbsp;Claude Sonnet 4.5<br>"
        "Embeddings &nbsp;all-MiniLM-L6-v2<br>"
        "Corpus &nbsp;11 docs / 109 chunks<br>"
        "Min similarity &nbsp;0.20"
        "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.markdown('<div class="title">SOC Triage AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Tier-1 alert triage &middot; MITRE ATT&CK grounded</div>',
    unsafe_allow_html=True,
)

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

with st.spinner("Indexing corpus..."):
    engine = load_triage()

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
if run and alert_text.strip():
    with st.spinner("Analyzing..."):
        r = engine.triage(alert_text)

    st.divider()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f'<div class="m-card"><div class="lbl">Severity</div>'
            f'{sev_badge(r["severity"])}</div>',
            unsafe_allow_html=True,
        )
    with c2:
        esc = r["escalate"]
        cls = "esc-yes" if esc else "esc-no"
        txt = "YES — escalate" if esc else "NO"
        st.markdown(
            f'<div class="m-card"><div class="lbl">Escalate</div>'
            f'<div class="{cls}">{txt}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="m-card"><div class="lbl">Confidence</div>'
            f'<div class="val">{r["confidence"].upper()}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        score = r.get("retrieval_score", 0)
        st.markdown(
            f'<div class="m-card"><div class="lbl">Retrieval</div>'
            f'<div class="val">{score:.3f}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sec">Summary</div>', unsafe_allow_html=True)
    st.info(r["summary"])

    left, right = st.columns([3, 2])

    with left:
        st.markdown('<div class="sec">Recommended actions</div>', unsafe_allow_html=True)
        for i, a in enumerate(r["recommended_actions"], 1):
            st.markdown(f"{i}. {a}")

        st.markdown('<div class="sec">Reasoning</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="reasoning">{r["reasoning"]}</div>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown('<div class="sec">MITRE ATT&CK</div>', unsafe_allow_html=True)
        st.markdown(tech_pills(r["mitre_techniques"]), unsafe_allow_html=True)

        st.markdown('<div class="sec">Sources</div>', unsafe_allow_html=True)
        st.markdown(src_pills(r.get("sources", [])), unsafe_allow_html=True)

    with st.expander("Raw JSON"):
        st.code(json.dumps(r, indent=2), language="json")

elif not run:
    st.markdown(
        '<div class="empty">Paste an alert or pick a sample from the sidebar.</div>',
        unsafe_allow_html=True,
    )
