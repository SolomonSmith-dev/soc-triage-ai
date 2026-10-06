# Roadmap

## Shipped

- Six-stage triage engine (v1, unchanged prompt, retriever, corpus)
- `packages/contracts` as the schema source of truth
- FastAPI service with API-key auth and Postgres persistence
- Streamlit console
- Reliability harness (see `tests/harness/`)

## Later

Deferred by ADR 0001. Files for some of these exist in the tree and are not advertised.

- Next.js analyst console (`apps/web`, partial, no CI)
- Celery async triage with Redis
- OpenTelemetry tracing
- Terraform
- pgvector retrieval and `evidence_links` population
- MITRE ATT&CK and CISA KEV ingestion (`jobs/intel-sync`)
- Analyst override endpoint
