# SOC Triage Copilot: Professional Project Design

**Date:** 2026-05-21
**Branch:** v2-platform
**Goal:** Ship a portfolio-grade project with a polished GitHub repo and a publicly accessible live demo that demonstrates the full analyst loop.

---

## Target State

A hiring manager opening the repo gets:
- Green CI badge, MIT license badge, architecture diagram, demo link -- all in the README header
- A live demo they can click without signing up (guest submit path) or with demo credentials (full analyst loop)
- A model card that documents real capabilities and real limits

---

## Section 1: Bug Fix Backlog

These four bugs must be fixed before anything else. They will silently break the demo if left in.

### Bug 1: SubmitForm.tsx has no auth header
**Location:** `apps/web/src/app/submit/SubmitForm.tsx` lines 37-40
**Problem:** Calls `POST /alerts` directly from the browser with no `Authorization` header. The API returns 401 since Phase 2 commit 2 enforces API key auth on that route.
**Fix:** Add a Next.js server action (`apps/web/src/app/submit/actions.ts`) that holds the demo ingest API key in `process.env.INGEST_API_KEY` (server-only, never `NEXT_PUBLIC_*`) and proxies the request. `SubmitForm.tsx` calls the server action instead of `api.ts` directly.

### Bug 2: current_user only reads HTTP cookie name
**Location:** `apps/api/src/soc_api/deps.py` line 52
**Problem:** Reads `next-auth.session-token`. HTTPS deployments (Vercel, any TLS-terminated host) use `__Secure-next-auth.session-token`. Cookie-based auth will silently fail in production.
**Fix:** Accept both names. Read `Cookie` header directly and check for either key, or declare both as `Cookie` parameters and use whichever is non-None.

### Bug 3: contracts.ts is generated and gitignored
**Location:** `apps/web/src/lib/contracts.ts` (missing), `packages/contracts/scripts/export_schemas.py`
**Problem:** `apps/web/src/lib/api.ts` imports types from `./contracts` which is generated and gitignored. Fresh checkout or CI Next.js build fails immediately.
**Fix:** Two-step:
1. Add `"predev": "python ../../packages/contracts/scripts/export_schemas.py"` and `"prebuild": "python ../../packages/contracts/scripts/export_schemas.py"` to `apps/web/package.json`.
2. Commit the generated `contracts.ts` as a build artifact (acceptable since it is derived from the committed Pydantic source and changes only when the schema changes).

### Bug 4: tsconfig.json missing baseUrl
**Location:** `apps/web/tsconfig.json` lines 16-18
**Problem:** `paths` is configured but `baseUrl` is absent. TypeScript requires `baseUrl` when using `paths`. The `@/lib/api` alias may fail during `tsc --noEmit` or `next build`.
**Fix:** Add `"baseUrl": "."` to `compilerOptions` alongside the existing `paths`.

---

## Section 2: Phase 2 Remaining Commits (3–7)

### Commit 3: NextAuth credentials provider + login page

**API side:** No changes -- `current_user` in `deps.py` already validates NextAuth JWTs.

**Web side:**
- `apps/web/src/app/api/auth/[...nextauth]/route.ts` -- CredentialsProvider that calls `POST /auth/login` on the FastAPI backend (new endpoint, commit 3 scope). FastAPI verifies the argon2id hash and returns `{ id, email, role }`. NextAuth creates a signed JWT session from this response.
- `apps/web/src/app/login/page.tsx` -- Login form: email + password fields. On success, redirects to `/dashboard`. Shows demo credentials on the page for portfolio visitors.
- Protect `/dashboard` and `/cases/*` routes via NextAuth middleware.

**Scoping note:** No OAuth providers, no magic links, no email verification. Credentials-only for the demo.

### Commit 4: Override service + materialized case read

**Location:** `apps/api/src/soc_api/services/override_service.py` (new file)

`get_materialized_case(case_id, session)`:
- Loads the `Case` row (immutable `envelope` JSONB).
- Loads all `AnalystOverride` rows for that case, ordered by `created_at` ASC.
- Applies overrides in order (latest-wins per field) to produce a merged view dict.
- Returns the merged view alongside the raw envelope and the override list.

The `cases.envelope` column is never mutated. Overrides are append-only.

### Commit 5: Override router + TS contracts

**New endpoint:** `POST /cases/{case_id}/overrides`
- Auth: `current_user` (analyst session required).
- Body: `{ field: str, new_value: Any, rationale: str | None }`.
- Validates `field` is in the allowed set (`severity`, `escalate`, `summary`, `recommended_actions`).
- Writes `AnalystOverride` row and an `AuditLog` row.
- Returns the updated materialized case.

**GET `/cases/{case_id}`** updated to return the materialized view (not the raw envelope).

**TS contracts:** Re-run schema export after adding override models. Commit updated `contracts.ts`.

### Commit 6: EditPanel + HistoryPanel components

Both components live on `/cases/{id}` below the existing triage report display.

**EditPanel** (`apps/web/src/components/EditPanel.tsx`):
- Dropdown for `severity` (critical / high / medium / low / informational).
- Toggle for `escalate`.
- Textarea for `rationale` (required).
- Submit button calls `POST /cases/{id}/overrides` via a server action.
- Optimistic UI: shows pending state, updates on response.

**HistoryPanel** (`apps/web/src/components/HistoryPanel.tsx`):
- Timeline list of overrides on this case.
- Each entry shows: analyst email, field changed, old value → new value, rationale, timestamp.
- Empty state: "No overrides yet."
- Read-only. No delete/undo.

### Commit 7: Final verification

Checklist before merging:
- [ ] Harness 7/7 still passing (`pytest tests/harness -v`).
- [ ] All 12 API unit tests passing.
- [ ] `seed_admin` creates a user and the login flow works end-to-end.
- [ ] Submit alert → triage → override → history panel shows the entry.
- [ ] Alembic migrations run clean on a fresh DB.
- [ ] `model_card.md` updated with current harness numbers and override loop documented.

---

## Section 3: Deployment Architecture

```
Browser
  └── Vercel  (apps/web, Next.js 15)
        └── Railway  (apps/api, FastAPI + triage-engine)
              └── Railway Postgres  (pgvector enabled)
```

**Vercel (Next.js):**
- Connected to the GitHub repo. Auto-deploys on merge to `main`.
- Environment vars: `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `NEXT_PUBLIC_API_URL`, `INGEST_API_KEY` (server-only).
- No Redis needed for Phase 2.

**Railway (FastAPI):**
- Dockerfile in `apps/api/`. Railway detects and builds it.
- Environment vars: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `NEXTAUTH_SECRET`, `ENVIRONMENT=production`.
- Alembic migrations run as a Railway deploy command before the server starts.

**Railway Postgres:**
- Managed instance with `pgvector` extension enabled via `CREATE EXTENSION IF NOT EXISTS vector` in the first Alembic migration. Confirm this exists; add it if not.

**Redis:** Wired in `docker-compose.yml` for local dev but not deployed. Phase 2 does not use it.

**Demo seeding (one-time Railway deploy hook):**
1. `python -m soc_api.cli.seed_admin` creates `demo@soctriage.ai` with password `Demo1234!`.
2. Seed script loads 3 pre-built alerts from `assets/` through the triage pipeline and stores the resulting cases.
3. Creates the demo ingest API key; the plaintext is stored in Railway env as `INGEST_API_KEY`.

---

## Section 4: Demo Flow

### Path 1 -- Guest submit (no login)

```
Landing page (/)
  → Paste raw alert text into the "Try it" form
  → Next.js server action: POST /alerts with INGEST_API_KEY (server-side)
  → Redirect to /cases/{id}
  → Triage report: severity, confidence, MITRE techniques, evidence chunks, recommended actions
```

No account needed. The demo API key never touches the browser.

### Path 2 -- Full analyst loop

```
/login  (demo credentials shown on page: demo@soctriage.ai / Demo1234!)
  → /dashboard: list of 3 pre-seeded cases
  → /cases/{id}: full triage report + EditPanel + HistoryPanel
  → Submit severity override + rationale
  → HistoryPanel: override appears in audit trail
```

Pre-seeded cases cover three alert categories: ransomware (critical/escalate), credential stuffing (high), lateral movement (medium). All sourced from existing `assets/` sample alerts.

---

## Section 5: Repository Polish

### README rewrite structure

```markdown
# SOC Triage Copilot  [CI badge] [License badge]

One-line description.

[Architecture diagram -- embedded Mermaid or PNG]

## Try the demo
[Live link]  |  Login: demo@soctriage.ai / Demo1234!

## Six-stage pipeline
1. Observable extraction (deterministic regex, pre-LLM)
2. Embedding-based retrieval (sentence-transformers, local)
3. Guardrail check (refuse if no chunks meet threshold)
4. Grounded prompting (top-4 chunks, model constrained to provided context)
5. Schema validation (strict JSON, invalid output triggers guardrail)
6. Case packaging (SOC-YYYYMMDD-XXXX ID, override-aware materialized view)

## What's here
[Repo structure map]

## Local dev
[3-command quickstart]

## Model card
[Link to model_card.md]
```

### Architecture diagram
Update `docs/architecture.mermaid` to reflect the v2 stack. Embed as a Mermaid block in the README (GitHub renders it natively).

### model_card.md
Update after Commit 7 verification:
- Harness numbers (pass rate, severity accuracy, escalation accuracy, latency).
- Add "Human override loop" to capabilities section.
- Add HTTPS cookie limitation note (mitigated by the dual-cookie fix in Bug 2).

### CI badges
Add to README header:
```markdown
![CI](https://github.com/SolomonSmith-dev/soc-triage-ai/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
```

### .env.example
Audit for vars added in Phase 2: `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `INGEST_API_KEY`. All must be present with placeholder values and a comment explaining each.

---

## Implementation Order

1. Bug fixes (4 items) -- unblock demo, unblock CI for web build
2. Commit 3: login page + NextAuth
3. Commit 4: override service
4. Commit 5: override router + contracts
5. Commit 6: EditPanel + HistoryPanel
6. Commit 7: final verification + model card update
7. Deploy: Railway (API + Postgres) then Vercel (web)
8. Seed demo data
9. README rewrite

---

## Out of Scope

- OAuth providers, magic links, email verification
- Redis / async job queue
- Storybook, Swagger-UI customization
- Multi-tenancy (tenant_id column exists but is not used in the demo)
- Rate limiting (add in a hardening pass post-portfolio)
