# ADR 0001: Ship the v2 core, defer the rest

Status: accepted, 2026-10-05

## Context

`v2-platform` is 21 commits ahead of `main`. The API, contracts, and engine move are working and green in CI. The web UI is partial. Celery, OpenTelemetry, Terraform, pgvector and intel-sync were planned and never started. The project is a portfolio piece; credibility depends on measured claims, not on surface area.

## Decision

Merge the working core: the FastAPI service around the unchanged v1 engine, `packages/contracts`, the Streamlit console, and the harness. Move Next.js, Terraform, OpenTelemetry, Celery, pgvector and intel-sync to "Later" in `docs/ROADMAP.md`. Do not delete their files. Do not claim them in the README.

## Consequences

- The README describes only what runs and what is measured.
- Triage stays synchronous. A public demo (phase 3) is a stateless service with no Postgres.
- `apps/web` stays in the tree, untested, outside CI, and unadvertised.
- The safety contract (stages 3 and 5) is unchanged by this decision.

## Revisit when

A real consumer needs async triage or a non-Streamlit UI.
