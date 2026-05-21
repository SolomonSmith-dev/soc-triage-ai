# CLAUDE.md: soc-triage-ai

Operating contract for any Claude session opened inside `~/Projects/soc-triage-ai`. Loaded automatically. Read before responding.

## Identity

`soc-triage-ai` is a RAG-grounded SOC analyst assistant. Ingests raw security alerts, retrieves threat intelligence, returns a structured triage report with severity, MITRE ATT&CK mapping, recommended actions, and an escalation decision.

This is portfolio work targeting **AI/ML engineering and security roles**. Code quality, model card discipline, and evaluation rigor matter more than feature count. Every decision should make the GitHub repo look more credible to a hiring manager who skims for thirty seconds.

Current phase: mid Phase 2 (v2-platform branch). Monorepo migration in progress, `apps/api`, `apps/web`, `apps/dev-console`, `packages/contracts`.

## Required reads

1. `README.md` for architecture and the six-stage pipeline
2. `model_card.md` for capabilities, limits, and known failure modes
3. `tests/harness_results.json` for the current reliability baseline before claiming a regression or improvement
4. `packages/contracts/` for the JSON schema, this is the API contract, not documentation

## The six-stage pipeline

1. Observable extraction (deterministic regex, runs before any LLM call)
2. Embedding-based retrieval (sentence-transformers + cosine similarity)
3. Guardrail check (refuse if no chunks meet threshold)
4. Grounded prompting (top-4 chunks injected, model constrained to provided context)
5. Schema validation (strict JSON, invalid output triggers guardrail)
6. Case packaging (envelope with `SOC-YYYYMMDD-XXXX` ID, JSON or Markdown export)

If a change touches stage 3 or stage 5, you are changing the safety contract. Flag it explicitly. Never weaken a guardrail to make a test pass.

## Hard rules

| Rule | Reason |
|---|---|
| The schema in `packages/contracts/` is the source of truth. Update it before code that produces or consumes it. | Drift between schema and producers breaks downstream evaluation silently. |
| Refusal mode is a feature, not a bug. If retrieval returns nothing above threshold, the system must refuse. | A SOC tool that hallucinates triage is worse than one that says "manual review". |
| Every change to the prompt or retrieval logic requires re-running `tests/harness_results.json`. | Reliability claims in the model card must match the harness, or the model card is fraud. |
| `model_card.md` is not marketing. It documents real limits including failure cases. | The harness must reproduce the limits documented in the card. |
| No raw `print()` in production paths. Use structured logging. | The dev console reads structured logs to render observability. |

## Voice

Security analyst writing for other analysts. Direct, evidence-led, no marketing.

Banned words on top of `~/CLAUDE.md` universals:
- Security marketing: AI-powered, next-gen, intelligent, autonomous, cutting-edge, advanced threat
- ML marketing: state-of-the-art, SOTA (unless citing a benchmark), powerful, sophisticated
- Vague: comprehensive, robust, holistic

No em dashes.

## Toolchain

- Python 3.11+ (check `pyproject.toml`), `pip install -r requirements.txt` or `uv`
- LLM: Claude Sonnet 4.5 via `ANTHROPIC_API_KEY`
- Embeddings: sentence-transformers (local, no network at inference)
- UI: Streamlit for now, migrating to a dedicated `apps/web`
- Tests: `pytest`, reliability harness at `tests/harness.py`

## Secrets

- `ANTHROPIC_API_KEY` in `.env`, never committed
- No real alert data in the repo. Use the sample alerts in `assets/` or anonymized fixtures.
- If a real alert appears in a tracked file, refuse to commit and flag for redaction.

## Evaluation discipline

Before claiming the model "improved":

1. Run the full 7-case harness, store output
2. Diff against the prior `tests/harness_results.json`
3. Report pass rate, severity accuracy, escalation accuracy, retrieval count, latency
4. Update the model card if any documented limit changed

No claim about reliability without numbers.

## When in doubt

1. Re-read `model_card.md` and `README.md`
2. Inspect `packages/contracts/` for the schema
3. `AskUserQuestion` with concrete options
4. If the change weakens a guardrail, stop and ask
