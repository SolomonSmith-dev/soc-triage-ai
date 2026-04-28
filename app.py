"""SOC Triage AI: Streamlit UI for analyst-facing alert triage demo.

Run with: streamlit run app.py
"""
import json
import streamlit as st
from triage import SOCTriage


# Page config
st.set_page_config(
    page_title="SOC Triage AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Custom CSS for a security-tool aesthetic
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #94a3b8;
        font-style: italic;
        margin-top: 0;
    }
    .severity-critical {
        background-color: #7f1d1d; color: white; padding: 0.4rem 1rem;
        border-radius: 0.25rem; font-weight: 700; display: inline-block;
        font-size: 1.1rem; letter-spacing: 1px;
    }
    .severity-high {
        background-color: #c2410c; color: white; padding: 0.4rem 1rem;
        border-radius: 0.25rem; font-weight: 700; display: inline-block;
        font-size: 1.1rem; letter-spacing: 1px;
    }
    .severity-medium {
        background-color: #ca8a04; color: white; padding: 0.4rem 1rem;
        border-radius: 0.25rem; font-weight: 700; display: inline-block;
        font-size: 1.1rem; letter-spacing: 1px;
    }
    .severity-low {
        background-color: #166534; color: white; padding: 0.4rem 1rem;
        border-radius: 0.25rem; font-weight: 700; display: inline-block;
        font-size: 1.1rem; letter-spacing: 1px;
    }
    .severity-informational {
        background-color: #475569; color: white; padding: 0.4rem 1rem;
        border-radius: 0.25rem; font-weight: 700; display: inline-block;
        font-size: 1.1rem; letter-spacing: 1px;
    }
    .metric-label {
        font-size: 0.85rem; color: #94a3b8; text-transform: uppercase;
        letter-spacing: 1px; margin-bottom: 0.25rem;
    }
    .technique-badge {
        background-color: #1e3a8a; color: #dbeafe; padding: 0.25rem 0.6rem;
        border-radius: 0.25rem; font-family: monospace; font-weight: 600;
        margin-right: 0.4rem; display: inline-block; font-size: 0.9rem;
    }
    .source-badge {
        background-color: #1e293b; color: #cbd5e1; padding: 0.2rem 0.5rem;
        border-radius: 0.25rem; font-family: monospace; font-size: 0.85rem;
        margin-right: 0.4rem; display: inline-block;
    }
    .stTextArea textarea {
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)


# Initialize triage system once and cache it
@st.cache_resource
def get_triage_system():
    """Load corpus and embeddings once per session."""
    return SOCTriage()


# Sample alerts for one-click demo
SAMPLE_ALERTS = {
    "Active ransomware (CRITICAL)": (
        "Multiple file servers showing thousands of file modifications per minute. "
        "Files renamed with .lockbit extension. README.txt ransom notes appearing "
        "in every directory. Volume Shadow Copies deleted via vssadmin 30 minutes ago."
    ),
    "LSASS credential dumping (CRITICAL)": (
        "EDR detected suspicious access to LSASS process memory by rundll32.exe "
        "with comsvcs.dll on workstation WKSTN-042. User account is jsmith. "
        "Process tree: cmd.exe -> rundll32.exe."
    ),
    "Phishing with credential entry (HIGH)": (
        "User reported email from ceo@anthrop1c.com (note typo) requesting "
        "urgent wire transfer to new vendor. User clicked link and entered "
        "credentials before reporting. Email contained urgency language."
    ),
    "SSH brute force from Tor (HIGH)": (
        "5000 failed SSH authentication attempts in last 10 minutes against "
        "host srv-bastion-01 from source IP 185.220.101.45 (known Tor exit). "
        "No successful authentications observed yet."
    ),
    "Insider threat (HIGH)": (
        "Employee jdoe (resignation notice given last week) downloaded 15GB of "
        "customer data from CRM in last 24 hours. Login from new device "
        "fingerprint. Email forwarding rule created to personal Gmail yesterday."
    ),
    "Out-of-scope gibberish (GUARDRAIL)": (
        "asdfqwerzxcv 1234567890 lorem ipsum dolor sit amet"
    ),
}


def render_severity_badge(severity: str) -> str:
    return f'<span class="severity-{severity}">{severity.upper()}</span>'


def render_techniques(techniques: list) -> str:
    if not techniques:
        return '<span style="color: #64748b; font-style: italic;">none identified</span>'
    return "".join(f'<span class="technique-badge">{t}</span>' for t in techniques)


def render_sources(sources: list) -> str:
    if not sources:
        return '<span style="color: #64748b; font-style: italic;">none</span>'
    return "".join(f'<span class="source-badge">{s}</span>' for s in sources)


# ============================================================
# SESSION STATE INIT
# ============================================================
# Use a single canonical key for the textarea content.
# Sample alert buttons mutate this BEFORE the textarea is rendered.

if "alert_input" not in st.session_state:
    st.session_state.alert_input = ""


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("### 🛡️ SOC Triage AI")
    st.markdown(
        "RAG-grounded alert triage with structured output and reliability evaluation."
    )

    st.divider()

    st.markdown("### Sample Alerts")
    st.markdown(
        "<small>Click to load a representative SOC alert into the input field.</small>",
        unsafe_allow_html=True,
    )

    # CRITICAL: writing to st.session_state.alert_input here is allowed
    # because we haven't rendered the textarea widget yet. After the textarea
    # renders, Streamlit owns the key and we can't modify it.
    for label, alert_text in SAMPLE_ALERTS.items():
        if st.button(label, use_container_width=True, key=f"btn_{label}"):
            st.session_state.alert_input = alert_text
            st.rerun()

    st.divider()

    st.markdown("### System")
    st.markdown(
        "<small>"
        "<b>Model:</b> Claude Sonnet 4.5<br>"
        "<b>Embeddings:</b> all-MiniLM-L6-v2<br>"
        "<b>Corpus:</b> 11 docs · 109 chunks<br>"
        "<b>Threshold:</b> retrieval similarity ≥ 0.20"
        "</small>",
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        "<small>"
        "Built as the AI110 Final Project for CodePath. "
        "Extends the Mood Machine sentiment classifier "
        "into a security domain with RAG, MITRE mapping, and reliability harness."
        "</small>",
        unsafe_allow_html=True,
    )


# ============================================================
# MAIN
# ============================================================

st.markdown('<p class="main-header">🛡️ SOC Triage AI</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Tier 1 alert triage assistant · grounded in MITRE ATT&CK threat intelligence</p>',
    unsafe_allow_html=True,
)

st.divider()

# Input - bound to session state via key
alert_text = st.text_area(
    "Security Alert",
    height=140,
    placeholder=(
        "Paste an alert from your SIEM, EDR, or SOAR platform.\n\n"
        "Example: 'EDR detected suspicious access to LSASS process memory by rundll32.exe...'"
    ),
    help="The system will retrieve relevant threat intelligence and produce a structured triage report.",
    key="alert_input",
)

col_btn, col_status = st.columns([1, 4])

with col_btn:
    triage_clicked = st.button(
        "🔍 Triage Alert",
        type="primary",
        use_container_width=True,
        disabled=not alert_text.strip(),
    )

with col_status:
    if not alert_text.strip():
        st.markdown(
            "<small style='color: #94a3b8;'>Enter an alert above or select a sample from the sidebar.</small>",
            unsafe_allow_html=True,
        )

# Pre-load system on first render so demo feels snappy
with st.spinner("Initializing system (one-time corpus indexing)..."):
    triage = get_triage_system()


# ============================================================
# TRIAGE EXECUTION + DISPLAY
# ============================================================

if triage_clicked and alert_text.strip():
    with st.spinner("Retrieving threat intelligence and analyzing alert..."):
        result = triage.triage(alert_text)

    st.divider()
    st.markdown("### 📋 Triage Report")

    # Top metrics row
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.markdown('<div class="metric-label">Severity</div>', unsafe_allow_html=True)
        st.markdown(render_severity_badge(result["severity"]), unsafe_allow_html=True)

    with m2:
        st.markdown('<div class="metric-label">Confidence</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="font-size: 1.3rem; font-weight: 600;">{result["confidence"].upper()}</div>',
            unsafe_allow_html=True,
        )

    with m3:
        st.markdown('<div class="metric-label">Escalate</div>', unsafe_allow_html=True)
        escalate_color = "#dc2626" if result["escalate"] else "#475569"
        escalate_text = "YES" if result["escalate"] else "NO"
        st.markdown(
            f'<div style="font-size: 1.3rem; font-weight: 700; color: {escalate_color};">{escalate_text}</div>',
            unsafe_allow_html=True,
        )

    with m4:
        st.markdown('<div class="metric-label">Retrieval Score</div>', unsafe_allow_html=True)
        score = result.get("retrieval_score", 0)
        st.markdown(
            f'<div style="font-size: 1.3rem; font-weight: 600;">{score:.3f}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # Summary
    st.markdown("**Summary**")
    st.info(result["summary"])

    # Two-column body
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("**Recommended Actions**")
        for i, action in enumerate(result["recommended_actions"], 1):
            st.markdown(f"{i}. {action}")

        st.markdown("")
        st.markdown("**Reasoning**")
        st.markdown(
            f'<div style="background-color: #1e293b; color: #cbd5e1; padding: 1rem; '
            f'border-left: 3px solid #3b82f6; border-radius: 0.25rem; font-size: 0.95rem;">'
            f'{result["reasoning"]}</div>',
            unsafe_allow_html=True,
        )

    with col_right:
        st.markdown("**MITRE ATT&CK Techniques**")
        st.markdown(render_techniques(result["mitre_techniques"]), unsafe_allow_html=True)

        st.markdown("")
        st.markdown("**Threat Intel Sources**")
        st.markdown(render_sources(result.get("sources", [])), unsafe_allow_html=True)

    # Raw JSON (collapsible)
    with st.expander("🔧 Raw JSON Output (for SIEM/SOAR integration)"):
        st.code(json.dumps(result, indent=2), language="json")

elif not triage_clicked:
    st.markdown("")
    st.markdown(
        '<div style="background-color: #1e293b; color: #94a3b8; padding: 2rem; '
        'border-radius: 0.5rem; text-align: center; font-style: italic;">'
        'Submit an alert to see the triage report.<br>'
        'The system will retrieve relevant threat intelligence, ground its analysis in '
        'MITRE ATT&CK, and produce a structured report ready for analyst review.'
        '</div>',
        unsafe_allow_html=True,
    )
