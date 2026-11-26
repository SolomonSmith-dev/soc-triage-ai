# AGENTS.md

Retrieval-grounded triage for security alerts. It extracts observables, retrieves threat intelligence, and returns a structured report (severity, MITRE ATT&CK mapping, recommended actions, escalation decision). When retrieval finds nothing relevant, it refuses and asks for manual review.

## Layout

- `services/triage-worker/`: the triage engine
- `packages/contracts/`: JSON schema and the API contract
- `apps/api/`, `apps/demo/`, `apps/dev-console/`: API, public demo, Streamlit dashboard
- `tests/unit/`, `tests/harness/`: offline unit tests and the 100-case evaluation harness
- `assets/`: sample alerts and images; `docs/`: architecture, decisions, deploy notes
- `model_card.md`: documented capabilities and limits

## Setup and checks

- Install: `pip install -e packages/contracts -e services/triage-worker -e "apps/demo[ui,space]" pytest` (README.md, Quick start)
- Unit tests (offline, no API key): `pytest tests/unit packages/contracts/tests` (.github/workflows/ci.yml, line 39)
- API tests: `pytest apps/api/tests` (ci.yml, line 79)
- Harness validation and replay: `python -m tests.harness.loader --validate`, `python -m tests.harness.test_harness --replay` (README.md, Quick start)
- Live harness run (needs `ANTHROPIC_API_KEY`, spend capped at 5 USD): `python -m tests.harness.test_harness --record`

## Pipeline

Six stages, in order: observable extraction, embedding retrieval, guardrail check, grounded prompting, schema validation, case packaging. Changes to the guardrail or schema stages change the safety behavior, so call them out in the PR. Do not weaken a guardrail to make a test pass.

## Conventions

- `packages/contracts/` is the API contract. Update the schema before any code that produces or consumes it.
- Refusal on weak retrieval is intended behavior, not a bug.
- Use structured logging, not `print()`, in production paths.
- Changes to the prompt or retrieval logic need a fresh harness run and re-recorded cassettes; CI fails on a stale cassette.
- Keep `model_card.md` accurate; `tests/unit/test_model_card.py` fails when it disagrees with the harness JSON.

## Evaluation

Treat the results in `tests/harness/` (`RESULTS.md`, `baseline.json`, `harness_results.json`, `retrieval_results.json`) as the baseline. Compare against them before claiming a regression or an improvement, and report numbers, not impressions.

## Safety

- Never commit secrets. `ANTHROPIC_API_KEY` goes in an untracked `.env` (see `.env.example`).
- Use only the sample alerts in `assets/` or anonymized fixtures. Do not commit real alert data.

## Done means

The unit, API and harness replay checks above pass, and docs and `model_card.md` match any changed behavior.
