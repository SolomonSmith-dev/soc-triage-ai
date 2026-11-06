# soc-triage-ai

RAG-grounded SOC analyst assistant: alerts → retrieval → structured triage with MITRE mapping and escalation.

## Task Routing

| Task Type | Go To | Description |
|-----------|-------|-------------|
| Triage worker | `services/triage-worker/` | Six-stage pipeline |
| Contracts | `packages/contracts/` | JSON schema SoT |
| API / consoles | `apps/` | api, dev-console, demo |
| Harness / baseline | `tests/harness/` | 100-case reliability |
| Model card | `model_card.md` | Capabilities and limits |
| ADRs | `docs/decisions/` | Deferred scope |

## Shared Resources

| Resource | Location | Contains |
|----------|----------|----------|
| CLAUDE | `CLAUDE.md` | Portfolio + pipeline contract |
| Deploy | deploy/ · docker-compose.yml | Runtime |
| Graph | `graphify-out/` | God node: extract_observables |
