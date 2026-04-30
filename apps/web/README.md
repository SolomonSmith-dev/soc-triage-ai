# `@soc/web` — analyst console

Next.js 15 + TypeScript + Tailwind dashboard for SOC Triage Copilot. Server Components fetch from the FastAPI service; one Client Component handles alert submission.

## Pages (Phase 1f)

| Route | Type | Purpose |
|---|---|---|
| `/` | Server | Recent cases table |
| `/submit` | Server + Client form | Submit raw alert; runs synchronous triage (~8s); redirects to case detail |
| `/cases/[id]` | Server | Full case envelope: severity / escalate / confidence / uncertainty cards, alert text, observable pills, evidence list with cited markers, MITRE chips, sources, reasoning |
| `/eval` | Server | Latest reliability harness summary + per-case table |

## Local dev

```bash
cp .env.local.example .env.local
pnpm install
pnpm run gen:types     # regenerates src/lib/contracts.ts from packages/contracts/dist/schemas
pnpm run dev           # starts on :3000, expects FastAPI on :8000
```

The `gen:types` step is required after Pydantic contracts in `packages/contracts/` change. JSON Schemas are exported via `python packages/contracts/scripts/export_schemas.py`.

## Type-safety pipeline

```
Pydantic models (Python)
   → packages/contracts/dist/schemas/*.json   (export_schemas.py)
   → apps/web/src/lib/contracts.ts            (json-schema-to-typescript)
   → apps/web/src/lib/api.ts                  (typed fetch client)
   → apps/web/src/app/**/*.tsx                (Server / Client Components)
```

Wire-format drift is impossible: the build fails if a Pydantic model changes and `gen:types` hasn't been re-run.

## Aesthetic

Dark slate SOC dashboard. Color palette and typography mirror `apps/dev-console/app.py` (the v1 Streamlit). Tokens defined in `tailwind.config.ts`:

- `bg-bg / bg-bg-elev / bg-bg-card` — backgrounds
- `text-ink / text-ink-dim / text-ink-mute / text-ink-faint` — typography hierarchy
- `bg-sev-{critical,high,medium,low,informational}` — severity chips
- `bg-obs-{net,host,hash,id}` — observable pill groups

## Phase 1 limitations (lifted in later phases)

- **No auth.** `TODO(P2)` markers in `layout.tsx` and route handlers. NextAuth credentials provider lands in Phase 1.5/2.
- **No override UI.** Phase 2 adds the analyst override drawer + history timeline.
- **Synchronous triage.** Phase 3 swaps the API to Celery; UI polls a job status endpoint.
- **Static corpus.** Phase 4 adds the corpus admin page surfacing scheduled MITRE + KEV ingest freshness.
