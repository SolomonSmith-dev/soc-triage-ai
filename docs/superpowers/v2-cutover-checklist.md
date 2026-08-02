# v2 Cutover Checklist

Run this when CodePath grading is complete and you're ready to merge `v2-platform` → `main`.

## Pre-merge verification

- [ ] CodePath grade received and recorded
- [ ] No more changes expected to graded `main` (no Loom URL edits, no README tweaks)
- [ ] `git fetch origin && git log --oneline origin/main` — confirm HEAD is the graded commit
- [ ] PR #1 has been kept in `draft` the entire time (no accidental "Ready for review")

## Sync v2-platform with main one final time

If anything landed on `main` during grading (typo fixes, etc.):

```bash
git checkout v2-platform
git pull origin v2-platform
git merge origin/main
# resolve any conflicts (most likely in README.md)
git push origin v2-platform
```

## Run all gates locally

```bash
cd /Users/solomonsmith/Projects/soc-triage-ai
source venv/bin/activate
python -m pytest tests/unit -v          # expect: 34 passed (more by then)
python -m tests.harness.test_harness     # expect: Passed 7/7
docker compose up -d                     # expect: all services healthy
curl http://localhost:8000/healthz       # expect: 200 OK
# walk through one alert end-to-end via the Next.js UI
```

## Tag the v1.0 -> v2.0 transition

```bash
# v1.0-codepath-final already exists at the graded commit; verify:
git tag -l 'v1.0*'

# Tag the v2 cutover commit (will be created post-merge):
# After merging the PR, on main:
git checkout main
git pull origin main
git tag -a v2.0-platform -m "v2 platform cutover: FastAPI + Next.js + Postgres + Redis. v1 engine vendored as triage-engine library."
git push origin v2.0-platform
```

## Flip the PR

1. Review PR #1 one final time — read the diff, confirm no surprises
2. `gh pr ready 1` (flips draft → ready-for-review)
3. Verify CI passed (the .github/workflows/ci.yml unit-tests job)
4. Merge with **"Create a merge commit"**, NOT squash — each phase commit deserves its own line in main's history for the audit trail. Suggested message:

   ```
   Merge v2 platform: SOC Triage Copilot

   Full-stack migration from Streamlit MVP to FastAPI + Next.js +
   Postgres + Redis platform. v1 triage engine vendored verbatim as
   a library; platform built around it.
   ```

5. After merge, delete the `v2-platform` branch on GitHub (you can keep the local one for reference).

## Post-merge

- [ ] Update README's lead paragraph from "Streamlit-based" → "Full-stack platform"
- [ ] Update resume bullets (those are in the v2 plan under "Resume bullets")
- [ ] Replace the architecture diagram with the new one (Next.js + FastAPI + Postgres)
- [ ] Push a fresh Loom: 5-min walkthrough of the v2 dashboard
- [ ] Check the GitHub repo's "About" section reflects the new tech list

## Rollback plan (if something goes sideways post-merge)

```bash
# Merge commit on main is HEAD. To unwind:
git checkout main
git revert -m 1 HEAD                   # creates a clean revert commit
git push origin main
# v1.0-codepath-final tag still points to the graded commit, untouched.
```

## Why a merge commit (not squash)

Each phase commit is a meaningful checkpoint with its own verification:
- Phase 0: monorepo reorg, harness 7/7
- Phase 1: FastAPI + Next.js + Postgres
- Phase 2: override workflow
- Phase 3: Celery async
- Phase 4: live intel ingestion
- Phase 5: prod plumbing

Squashing destroys this audit trail. Future you (and any portfolio reviewer reading `git log`) benefits from seeing the migration as a sequence of disciplined steps, not one mega-commit.
