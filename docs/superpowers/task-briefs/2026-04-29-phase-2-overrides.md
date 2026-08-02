# Task Brief — Phase 2: Auth + Override Workflow

**Started:** 2026-04-29
**Branch:** `v2-platform`
**Plan reference:** `docs/superpowers/plans/2026-04-28-v2-platform.md` lines 188-199
**Estimated scope:** 4-5 days (Phase 1.5 auth bundled with Phase 2 overrides)

---

## Goal

Ship the analyst feedback loop end-to-end: a logged-in analyst opens a case, edits a whitelisted field with a rationale, submits, sees the new value reflected on reload, and sees their action in a history panel and audit log. No LLM path changes. No mutation of `cases.envelope`.

## Why bundle auth (Phase 1.5) with overrides (Phase 2)

1. `audit_logs.actor_id` and `analyst_overrides.created_by` are load-bearing columns. Hardcoded UUID poisons the demo data and forces a backfill later.
2. The override demo's narrative — "analyst Sarah escalated this case at 14:32" — collapses without identity.
3. NextAuth credentials provider + API key middleware is hours, not days. Cheap to do correctly the first time.
4. `EditPanel` needs the current user from session to send the request. Stubbing it now means rewriting the same component twice.

## Architectural rules (locked, do not violate)

- `cases.envelope` JSONB is **immutable**. Overrides never mutate it.
- Overrides are **append-only**. New row per edit. Latest-wins on read.
- Override application is **read-side**. `case_service.get_materialized_case()` applies overrides over envelope per request.
- API handlers stay **thin**. Validate → service call → return. No business logic in routers.
- Frozen files stay frozen: `services/triage-worker/triage_engine/`, `tests/test_harness.py` body, `data/threat_intel/*`.

## Deliverables

### Phase 1.5 — Auth (lands first)

1. **Backend (`apps/api/`)**
   - Seed bootstrap admin user from env (`ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`) via lifespan hook or one-shot script.
   - `deps.py:current_user(session_token: Cookie)` resolves to `users` row.
   - `deps.py:current_api_key(authorization: Header)` resolves to `api_keys` row → user.
   - bcrypt for user passwords, argon2id for API keys (per Phase 1.5 spec).
   - Apply `current_user` dependency to mutating routes (`POST /cases/{id}/override`); apply `current_api_key` to `POST /alerts`.

2. **Frontend (`apps/web/`)**
   - NextAuth credentials provider at `app/api/auth/[...nextauth]/route.ts`.
   - `lib/auth.ts` — session config, JWT strategy, callbacks pulling `user_id` into the token.
   - `app/login/page.tsx` — minimal email/password form.
   - Middleware redirects unauthenticated → `/login` for protected routes.
   - `lib/api.ts` forwards session cookie on every request.

### Phase 2 — Overrides (built on top of auth)

3. **Database / migration**
   - Verify `analyst_overrides` and `audit_logs` schemas match plan. Add `created_by UUID FK users(id) NOT NULL` if not present.
   - Field whitelist constant in `override_service.py`: `severity`, `escalate`, `mitre_techniques` (configurable list).

4. **Backend**
   - `services/override_service.py` — `apply_override(case_id, field, new_value, rationale, user)`:
     - Validate field in whitelist.
     - Read current materialized value for `old_value`.
     - Insert `analyst_overrides` row.
     - Insert `audit_logs` row (`action='case.override'`, `payload={field, old, new, rationale}`).
     - Single transaction.
   - `case_service.get_materialized_case(case_id)` — fetch envelope + all overrides for case → fold latest-per-field over envelope copy → return.
   - `routers/cases.py`:
     - `POST /cases/{id}/override` — body: `OverrideRequest` (field, new_value, rationale). Returns updated materialized case.
     - `GET /cases/{id}` — returns materialized view, not raw envelope.
     - `GET /cases/{id}/overrides` — returns override timeline for HistoryPanel.

5. **Contracts** (`packages/contracts/`)
   - `OverrideRequest`, `OverrideEntry`, `MaterializedCase` Pydantic models.
   - Round-trip test: build envelope → apply two overrides → assert materialized output.
   - Regenerate TS types via `pnpm run gen:types`.

6. **Frontend** (`apps/web/src/app/cases/[id]/`)
   - `EditPanel.tsx` (Client Component) — inline edit for whitelisted fields. Rationale textarea required, submit disabled until non-empty. Optimistic update + rollback on error.
   - `HistoryPanel.tsx` (Client Component) — vertical timeline of overrides: actor, timestamp, field, old → new, rationale.
   - `page.tsx` — fetches materialized case server-side; passes initial state to client components.

7. **Tests**
   - `tests/unit/test_override_service.py` — apply override, materialized read, audit log written, whitelist rejection, append-only invariant (envelope unchanged).
   - `tests/unit/test_auth.py` — login flow, session cookie verification, unauthorized 401.
   - Contract round-trip test for `OverrideRequest` / `MaterializedCase`.

## Verification gate (Phase 2 complete when all pass)

- [ ] All existing 37 Python tests still pass.
- [ ] New override-service + auth tests pass.
- [ ] Harness 7/7 unchanged (engine untouched).
- [ ] `tsc --noEmit` clean; `next build` clean.
- [ ] Manual demo: log in → open case → edit severity with rationale → reload → new value visible + history entry → audit log query returns the action.
- [ ] `cases.envelope` JSONB confirmed unchanged after override (SQL diff).

## Out of scope (defer)

- Multi-tenancy beyond `tenant_id` reservation.
- SSO / OIDC.
- RBAC beyond admin / analyst.
- Override revert / undo (just append a new override).
- Caching the materialized view (premature; revisit if perf is a problem).
- Celery (Phase 3).

## Build sequence (commit-by-commit)

1. **Auth schema + seed** — verify users/api_keys tables, seed admin, password hashing utilities.
2. **API auth deps + middleware** — `current_user`, `current_api_key`, applied to existing routes.
3. **NextAuth + login page** — credentials provider, session, login UI.
4. **Override schema verify + service** — `override_service.apply_override` + `case_service.get_materialized_case` + tests.
5. **Override router + contracts** — `POST /cases/{id}/override`, `GET /cases/{id}/overrides`, materialized `GET /cases/{id}`, contract models, round-trip test.
6. **EditPanel + HistoryPanel** — client components on case detail page.
7. **Final verification + brief update** — run all gates, mark complete.

Each commit must pass tests independently. PR #1 stays in draft.

## Progress log

(append after each major step)
