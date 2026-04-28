# SOC Triage AI: MVP Productization Design Spec

**Date:** 2026-04-27
**Status:** Approved (pending final spec review)
**Author:** Solomon Smith + Claude

## Summary

Expand SOC Triage AI from a CodePath final project into a portfolio-grade MVP that looks and behaves like an internal SOC analyst tool. Adds deterministic observable extraction, evidence traceability, enriched case packaging, uncertainty classification, evaluation dashboard, analyst overrides, retrieval debugging, and export capabilities.

**Deployment target:** Portfolio/demo piece. Runs locally. In-memory session state, no persistence beyond file exports.

## Architecture: Module-per-concern

New Python modules alongside `triage.py`, each owning one responsibility. Existing files stay frozen except one surgical addition to `triage.py`.

### File Tree (after implementation)

```
soc-triage-ai/
├── app.py                     # Streamlit UI (3 tabs: Triage / Evaluation / System)
├── triage.py                  # LLM triage pipeline (minimal change: add triage_with_context)
├── extractors.py              # Deterministic regex observable extraction
├── case_package.py            # Case envelope builder + uncertainty derivation
├── evaluation.py              # Harness results loader + live runner + metrics
├── rag/
│   ├── __init__.py
│   ├── corpus.py              # FROZEN
│   └── retriever.py           # FROZEN
├── data/threat_intel/         # FROZEN (11 markdown docs)
├── tests/
│   ├── __init__.py
│   └── test_harness.py        # FROZEN
├── docs/
│   └── superpowers/specs/
│       └── 2026-04-27-mvp-productization-design.md
├── assets/architecture.png
├── model_card.md
├── README.md
├── requirements.txt
├── .env.example
└── .gitignore
```

### Frozen Files (no modifications)

- `rag/corpus.py`
- `rag/retriever.py`
- `data/threat_intel/*`
- `tests/test_harness.py`
- `model_card.md`

---

## Module 1: `extractors.py` -- Observable Extraction

### Purpose

Deterministic regex extraction of security-relevant observables from raw alert text. Runs before the LLM call. Zero API cost.

### Interface

```python
def extract_observables(text: str) -> dict[str, list[str]]:
    """Extract security observables from free-form alert text.
    
    Returns dict with keys: ipv4, email, url, domain, md5, sha1, sha256,
    registry_path, process, filename, hostname, username.
    Empty lists for unmatched types. All values deduplicated.
    """
```

### Extracted Types

| Type | Pattern | Example |
|---|---|---|
| `ipv4` | Standard dotted quad, validated octets 0-255 | `185.220.101.45` |
| `email` | `user@domain.tld` | `ceo@anthrop1c.com` |
| `url` | `http(s)://...` up to whitespace | `https://evil.com/login` |
| `domain` | Bare hostnames with TLD, excluding IPs and domains already captured inside `email` or `url` fields | `anthrop1c.com` |
| `md5` | Exactly 32 hex chars, word-bounded | `d41d8cd98f00b204e9800998ecf8427e` |
| `sha1` | Exactly 40 hex chars, word-bounded | |
| `sha256` | Exactly 64 hex chars, word-bounded | |
| `registry_path` | Starts with `HKLM\`, `HKCU\`, `HKU\`, `HKCR\`, `HKCC\` | `HKLM\Software\Microsoft\...` |
| `process` | Token ending in `.exe`, `.dll`, `.sys` | `rundll32.exe`, `comsvcs.dll` |
| `filename` | Token ending in common doc/archive extensions (`.txt`, `.pdf`, `.docx`, `.xlsx`, `.zip`, `.rar`, `.iso`, `.img`, `.vhd`, `.lnk`, `.html`) | `README.txt` |
| `hostname` | Tokens matching `WKSTN-*`, `srv-*`, `DC-*`, or all-caps-with-dash AD-style patterns | `WKSTN-042`, `srv-bastion-01` |
| `username` | Token following context words: `user`, `account`, `employee`, `login` | `jsmith`, `jdoe` |

### Heuristic Priority

When a token could match multiple types, priority order:
1. `process` (`.exe`/`.dll`/`.sys` always wins)
2. `filename` (other extensions)
3. Fall through to other matchers

### Design Constraints

- Pure regex + string heuristics. No NLP, no external libraries, no API calls.
- Each extractor is a standalone function. `extract_observables` composes them.
- No classes, no state.

---

## Module 2: `case_package.py` -- Case Envelope & Uncertainty Modes

### Purpose

Wraps existing triage output + extracted observables + retrieval metadata into a complete case package. Fully deterministic. No LLM calls.

### Interface

```python
def build_case_package(
    alert_raw: str,
    observables: dict,
    triage_result: dict,
    retrieval_hits: list[tuple[dict, float]],
    guardrail_triggered: bool,
) -> dict:
    """Assemble full case package. Pure function, no side effects."""
```

### Case Package Schema

```json
{
    "case_id": "SOC-20260427-a3f8",
    "timestamp": "2026-04-27T23:16:58Z",
    "alert_raw": "Employee jdoe...",
    "observables": {
        "ipv4": ["185.220.101.45"],
        "email": [],
        "username": ["jdoe"]
    },
    "triage": {
        "severity": "critical",
        "confidence": "high",
        "mitre_techniques": ["T1078", "T1530"],
        "summary": "...",
        "recommended_actions": ["..."],
        "escalate": true,
        "reasoning": "..."
    },
    "evidence": {
        "chunks_retrieved": [
            {
                "chunk_id": "insider_threat_3",
                "source": "insider_threat.md",
                "score": 0.576,
                "text": "...",
                "cited": true
            }
        ],
        "avg_retrieval_score": 0.404,
        "sources_cited": ["insider_threat.md"]
    },
    "uncertainty_mode": "actionable",
    "guardrail_triggered": false,
    "analyst_overrides": [],
    "version": {
        "model": "claude-sonnet-4-5",
        "embeddings": "all-MiniLM-L6-v2",
        "corpus_chunks": 109,
        "prompt_version": "1.0",
        "top_k": 4,
        "min_similarity": 0.20
    }
}
```

### Uncertainty Mode Derivation

Evaluated in order, first match wins:

| Mode | Condition |
|---|---|
| `out_of_scope` | severity == `informational` AND guardrail triggered |
| `insufficient_evidence` | avg retrieval score < 0.25 AND severity != `informational` |
| `needs_more_context` | confidence == `low` OR (confidence == `medium` AND retrieval score < 0.35) |
| `actionable` | Everything else |

### Case ID Format

`SOC-YYYYMMDD-XXXX` where XXXX is 4 hex chars from `uuid4().hex[:4]`.

---

## Module 3: `evaluation.py` -- Harness Runner & Results Loader

### Purpose

Bridge between the CLI test harness and the Streamlit evaluation dashboard. Two modes: load existing results from JSON, or run live.

### Interface

```python
def load_harness_results(path: str = "tests/harness_results.json") -> dict | None:
    """Load and parse existing harness results. Returns None if file missing."""

def run_harness_live(triage_engine) -> dict:
    """Execute all test cases against a live triage engine. Returns same format."""

def compute_eval_metrics(results: list[dict]) -> dict:
    """Derive dashboard metrics from raw results."""
```

### Metrics Output

```python
{
    "total": 7,
    "passed": 7,
    "pass_rate": 1.0,
    "severity_accuracy": 1.0,
    "escalation_accuracy": 1.0,
    "mitre_overlap": 0.857,
    "refusal_correctness": 1.0,
    "schema_valid": 1.0,
    "avg_latency": 8.1,
    "avg_retrieval_score": 0.433,
    "per_case": [...]
}
```

### Design Constraints

- Imports `TEST_CASES` and `evaluate_case` from `tests.test_harness`. No duplication of test logic.
- `test_harness.py` is never modified.
- Live runner accepts a pre-initialized `triage_engine` to avoid re-indexing the corpus.
- Results format is identical whether loaded from JSON or run live.

---

## Module 4: `triage.py` -- Minimal Modification

### Change

Add `triage_with_context()` method to `SOCTriage`:

```python
def triage_with_context(self, alert: str) -> tuple[dict, list, bool]:
    """Like triage(), but returns (result, retrieval_hits, guardrail_triggered).
    
    Used by case_package.py. The existing triage() stays unchanged for the harness.
    """
```

### Implementation

Extract shared logic into private `_run_triage()` method. Both `triage()` and `triage_with_context()` call it. `triage()` returns just the dict (existing contract). `triage_with_context()` returns the tuple.

### What Stays Frozen

- `TRIAGE_PROMPT`
- `triage()` return signature
- `_parse_json()`, `_validate_schema()`, `_guardrail_response()`
- `format_report()`, `main()`

### Verification

Run full harness after this change, confirm 7/7 before proceeding.

---

## Module 5: `app.py` -- Three-Tab Streamlit UI

### Tab Structure

**Triage | Evaluation | System**

### Triage Tab

1. **Alert input** -- textarea + "Run Triage" button (same interaction model as current)
2. **Observables panel** -- extracted observables rendered as tagged pills grouped by type. Shown immediately after input, before LLM runs. Instant visual feedback.
3. **Triage report** -- severity, escalate, confidence, retrieval score metric cards + new uncertainty mode badge
4. **Evidence traceability panel** -- collapsible section:
   - Table: chunk_id, source doc, similarity score, text preview
   - "Cited" column with checkmark for chunks whose source appears in triage sources
5. **Analyst override section** -- dropdowns for severity/escalation override, text input for rationale. Stored in session state (in-memory). "Override applied" badge on metric cards when active.
6. **Export buttons** -- "Download JSON" and "Download Markdown". Full case package including overrides.
7. **Sample alerts** -- sidebar (same pattern as current)

### Evaluation Tab

1. **Static view (default)** -- loads `tests/harness_results.json`:
   - Summary metrics row: pass rate, severity accuracy, escalation accuracy, MITRE overlap, schema validity, avg latency
   - Per-case table: test ID, severity (actual vs expected), escalate match, techniques, retrieval score, pass/fail badge, latency
2. **"Run Harness" button** -- warning about API cost (7 calls), executes live, replaces display with fresh results
3. No persistence of live results back to the JSON file

### System Tab

1. **Version metadata** -- key-value table: model, embeddings, corpus size, prompt version, top_k, min_similarity
2. **Retrieval debugger** -- text input + "Debug Retrieval" button. Shows top-k chunks with scores, which passed threshold. No LLM call.
3. **Corpus stats** -- total chunks, chunks per source doc, avg chunk length

### Code Organization

Tab rendering logic lives in functions within `app.py`: `render_triage_tab()`, `render_evaluation_tab()`, `render_system_tab()`. Avoids Streamlit multi-file import headaches while keeping logical separation.

### CSS

Extends existing dark SOC dashboard aesthetic. New elements (observable pills, cited badges, uncertainty badges, override indicators) use the same color palette and type conventions.

---

## Data Flow

```
User pastes alert
       |
       v
extractors.extract_observables(alert)     <- deterministic, instant
       |
       v
triage_engine.triage_with_context(alert)  <- retrieval + LLM call
       |
       +-- triage_result (existing dict)
       +-- retrieval_hits (chunk/score tuples)
       +-- guardrail_triggered (bool)
       |
       v
case_package.build_case_package(          <- deterministic assembly
    alert, observables, triage_result,
    retrieval_hits, guardrail_triggered
)
       |
       v
Full case package dict
       |
       +-- Triage tab renders report + evidence + observables
       +-- Session state stores case for override/export
       +-- Export buttons serialize to JSON/markdown
```

**Single API call per triage.** Everything else is regex, dict assembly, or file I/O.

---

## Session State Model

```python
st.session_state.alert_input = ""                  # textarea binding
st.session_state.current_case = None               # latest case package dict
st.session_state.analyst_overrides = []            # list of override dicts:
# {
#     "field": "severity",
#     "original": "high",
#     "override": "critical",
#     "rationale": "Asset is crown jewel DB server",
#     "timestamp": "2026-04-27T23:30:00Z"
# }
```

Overrides are appended to the list, included in exports, shown as badges. They never modify the original triage result. The case package carries both the LLM output and the analyst's corrections side by side.

---

## Priority 2 Features (included in this spec)

### Analyst Override Logging (P2-6)

In-memory per session. Overrides stored in `st.session_state.analyst_overrides`. Included in case package exports. Resets on page reload. No server-side persistence needed for a portfolio demo.

### Retrieval Debugger Tab (P2-7)

Lives in the System tab. Standalone text input + button. Calls `retriever.retrieve()` directly, renders results. No LLM involvement. Useful for debugging why certain alerts retrieve poorly.

### Export to Markdown and JSON (P2-8)

Two `st.download_button` calls in the Triage tab. JSON export is `json.dumps` of the full case package. Markdown export renders the case package as a formatted report with headers, tables, and code blocks.

### Version Metadata Display (P2-9)

Key-value table in the System tab. Values sourced from constants in `triage.py` and `case_package.py`. No dynamic lookup needed.

---

## Dependencies

No new Python packages. All features use stdlib (`re`, `json`, `uuid`, `datetime`) plus existing deps (`streamlit`, `anthropic`, `sentence-transformers`, `numpy`).

---

## Risk Mitigation

1. **Harness regression:** `triage()` return signature is frozen. Harness runs after every change to `triage.py`.
2. **Prompt drift:** `TRIAGE_PROMPT` is frozen. No prompt changes in this spec.
3. **API cost:** Only the existing single LLM call per triage. Evaluation live run costs 7 calls (warned in UI).
4. **Complexity creep:** Each new module is <150 lines, single responsibility, no shared mutable state.
