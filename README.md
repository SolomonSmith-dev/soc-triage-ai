# SOC Triage AI

**RAG-grounded security alert triage with structured JSON output, MITRE ATT&CK mapping, and reliability evaluation.**

A SOC analyst assistant that ingests raw security alerts, retrieves relevant threat intelligence, and produces structured triage reports including severity classification, MITRE technique mapping, recommended actions, and escalation decisions.

## Base Project

This project is conceptually derived from **The Mood Machine** (CodePath AI110 Module 3), which classified text into sentiment categories using prompt-engineered LLM calls. SOC Triage AI applies the same core pattern, LLM-based categorical classification with structured output, to a higher-stakes domain. The implementation is largely new: retrieval-augmented grounding, MITRE ATT&CK mapping, schema validation, and a reliability harness are additions specific to the security domain.

The lesson carried forward: prompt engineering and structured output are general patterns that transfer across domains, but the system architecture around them determines whether the project is portfolio-worthy.

## Architecture

![System Architecture](assets/architecture.png)

The system processes alerts through six stages:

1. **Observable extraction**: deterministic regex extracts security observables (IPs, hashes, processes, hostnames, usernames, registry paths, etc.) from raw alert text. Runs before the LLM call so analysts get instant visual feedback.
2. **Embedding-based retrieval**: alert text is embedded with sentence-transformers and matched against an indexed threat intelligence corpus using cosine similarity.
3. **Guardrail check**: if no chunks meet the minimum similarity threshold, the system returns a hardcoded refusal that recommends manual review.
4. **Grounded prompting**: top-4 retrieved chunks are injected into a structured prompt that constrains Claude Sonnet 4.5 to use only the provided context.
5. **Schema validation**: LLM output is parsed and validated against a strict JSON schema. Invalid output triggers the guardrail response.
6. **Case packaging**: validated triage, observables, retrieval evidence, and a derived uncertainty mode (`actionable` / `needs_more_context` / `insufficient_evidence` / `out_of_scope`) are wrapped into a single case envelope with a unique `SOC-YYYYMMDD-XXXX` ID, ready for export as JSON or Markdown.

## Setup

```bash
git clone https://github.com/SolomonSmith-dev/soc-triage-ai.git
cd soc-triage-ai
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY
```

## Usage

### Streamlit UI (primary)

```bash
source venv/bin/activate
streamlit run app.py --server.fileWatcherType=none
```

The UI opens at `http://localhost:8501` and presents a three-tab SOC dashboard:

**Triage tab.** Paste an alert or pick a sample from the sidebar. Observable pills appear immediately (color-coded by group: network / host / hash / identity). Click **Run Triage** to produce a full case package: severity / escalation / confidence / uncertainty metric cards, summary, recommended actions, reasoning, MITRE techniques, source attribution, an evidence panel listing the retrieved chunks (with `cited` markers for chunks whose source was used), an analyst override form (severity + escalation with rationale, tracked in session state), and JSON / Markdown download buttons for the full case envelope.

**Evaluation tab.** Loads the static reliability harness results from `tests/harness_results.json` by default — pass rate, severity / escalation accuracy, average retrieval, average latency, plus a per-case results table. A **Run live** button executes the full 7-case harness against the running engine for a fresh result set (costs 7 API calls).

**System tab.** Version metadata (model, embeddings, corpus size, top-k, min similarity), a retrieval debugger (query → top-k chunks with scores, no LLM call), and corpus stats (chunks per source document).

### CLI

```bash
source venv/bin/activate
python triage.py "PowerShell encoded command spawned by outlook.exe"
```

### Reliability harness

```bash
python -m tests.test_harness
```

## Sample Interactions

### Sample 1: Active ransomware

**Input:**

```
Multiple file servers showing thousands of file modifications per minute. Files renamed with .lockbit extension. README.txt ransom notes appearing in every directory. Volume Shadow Copies deleted via vssadmin 30 minutes ago.
```

**Output:**

- Severity: `critical`
- Confidence: `high`
- Escalate: `true`
- MITRE Techniques: `T1486`, `T1490`
- Sources: `ransomware_indicators.md`, `mitre_credential_access_lateral.md`
- Retrieval Score: `0.541`

### Sample 2: Credential dumping (LSASS)

**Input:**

```
EDR detected suspicious access to LSASS process memory by rundll32.exe with comsvcs.dll on workstation WKSTN-042. User account is jsmith. Process tree: cmd.exe -> rundll32.exe.
```

**Output:**

- Severity: `critical`
- Confidence: `high`
- Escalate: `true`
- MITRE Techniques: `T1003`, `T1003.001`
- Sources: `mitre_credential_access_lateral.md`, `mitre_execution_persistence.md`, `log_analysis_windows.md`
- Retrieval Score: `0.488`

### Sample 3: Out-of-scope (guardrail behavior)

**Input:**

```
asdfqwerzxcv 1234567890 lorem ipsum dolor sit amet
```

**Output:**

- Severity: `informational`
- Confidence: `high`
- Escalate: `false`
- MITRE Techniques: none
- Reasoning: "Alert contains gibberish content with no recognizable security indicators or actionable intelligence."

## Design Decisions

**sentence-transformers + numpy over a vector database**: With a corpus of 109 chunks, a full vector DB (Milvus, ChromaDB, Pinecone) would add complexity without performance benefit. numpy cosine similarity executes in milliseconds and the entire index fits in memory.

**Strict JSON schema with validation**: SOC tools downstream (SIEM enrichment, ticketing systems) need predictable structured output. The prompt requires exact schema compliance, the parser strips markdown fences, and the validator enforces field types and enum values. Invalid output triggers the guardrail rather than degrading silently.

**Retrieval guardrail over confident fabrication**: The most dangerous failure mode for an AI security tool is confident wrong answers. The system explicitly refuses to triage alerts when retrieval similarity falls below threshold, returning a transparent refusal that recommends manual analyst review.

**MITRE ATT&CK technique citation as required output**: Forces the LLM to ground severity decisions in named adversary techniques rather than vague threat language, making outputs auditable and translatable to existing SOC workflows.

## Testing Summary

The reliability harness runs 7 representative alert scenarios covering phishing, ransomware, credential dumping, brute force, exploitation attempts, insider threat, and gibberish (guardrail test).

Each test case validates four criteria: severity classification falls within expected range, escalation decision matches expectation, at least one expected MITRE technique is identified, and retrieval similarity score exceeds the case minimum.

**Latest harness results:**

- Passed: **7/7 (100%)**
- Avg retrieval similarity: 0.433
- Avg latency per alert: 7.5 seconds

The Evaluation tab in the Streamlit UI surfaces these same metrics live and supports re-running the harness on demand against the active engine.

## Limitations & Known Issues

- **Reliability harness: 7/7 pass rate.** Earlier iterations had a T1 phishing failure traced to corpus chunking separating MITRE technique IDs from retrieved indicator text. Resolved by inlining technique references. See `model_card.md` for full iteration history.
- **Streamlit file watcher noise.** The `sentence-transformers` library triggers `ModuleNotFoundError` warnings for unused image-processing modules during Streamlit's file watcher scan. Workaround: `--server.fileWatcherType=none`. This does not affect functionality.
- **Static corpus.** The current threat intelligence base is 11 markdown documents (109 chunks). For production use, this would be replaced with live MITRE ATT&CK feeds and CVE database integrations.

## Reliability and Evaluation

The system implements six reliability mechanisms:

1. **Retrieval guardrail**: minimum similarity threshold (0.20) prevents triage of out-of-corpus alerts
2. **JSON schema validation**: enforces output structure, falls back to guardrail on malformed responses
3. **Source attribution**: every triage report cites the corpus documents that grounded the decision
4. **Evidence traceability**: the case package records every retrieved chunk with score and a `cited` flag, so reviewers can see which chunks the LLM actually used vs. which were merely above threshold
5. **Uncertainty mode classification**: derived deterministically from confidence + retrieval score (no prompt changes), surfacing low-evidence or low-confidence cases before they reach an analyst
6. **Automated harness**: 7-case test suite validates severity classification, MITRE mapping, and guardrail behavior; results are exposed in the Evaluation tab and re-runnable on demand

## Reflection

See `model_card.md` for full reflection on limitations, biases, misuse risks, and AI collaboration during development.

## Loom Walkthrough

[https://www.loom.com/share/5ae859759c7e4036a5c73b251164e3e9]

## Repository Structure

```
soc-triage-ai/
├── app.py                     # Streamlit 3-tab dashboard (Triage / Evaluation / System)
├── triage.py                  # LLM triage pipeline + triage_with_context()
├── extractors.py              # Deterministic regex observable extraction
├── case_package.py            # Case envelope builder + uncertainty mode derivation
├── evaluation.py              # Harness loader + live runner + metrics
├── rag/
│   ├── __init__.py
│   ├── corpus.py              # Markdown corpus loader
│   └── retriever.py           # Embedding-based retrieval
├── data/threat_intel/         # 11 markdown threat intel documents (109 chunks)
├── tests/
│   ├── __init__.py
│   ├── test_harness.py        # Reliability evaluation harness (7 cases)
│   ├── test_extractors.py     # Observable extraction unit tests (19)
│   ├── test_case_package.py   # Case envelope unit tests (11)
│   └── test_evaluation.py     # Evaluation module unit tests (4)
├── docs/superpowers/          # Design specs and implementation plans
├── assets/
│   └── architecture.png       # System diagram
├── README.md
├── model_card.md
├── requirements.txt
├── .env.example
└── .gitignore
```
