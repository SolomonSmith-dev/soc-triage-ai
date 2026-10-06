# Reliability harness

100 YAML cases, a record/replay LLM seam, retrieval metrics, and a per-case CI gate.

## Commands

```bash
python -m tests.harness.loader --validate                 # schema check, prints review status
python -m tests.harness.retrieval_eval --out /tmp/r.json  # retrieval metrics, local embeddings, no API key
python -m tests.harness.test_harness --replay             # offline replay of committed cassettes
python -m tests.harness.test_harness --record             # live run, writes cassettes + harness_results.json
python -m tests.harness.test_harness --record --update-baseline
python -m tests.harness.report                            # regenerate RESULTS.md from the JSON files
```

A live run needs `ANTHROPIC_API_KEY` in the environment and stops at `--max-cost-usd` (default 5). It prints tokens and an estimated cost.

## Adding a case

1. Copy a file under `cases/` and change `id` (file name must match the id).
2. Set `expect`. Injection cases need `forbid_in_output` with a canary string. Cases the retrieval guardrail must refuse set `guardrail: true`.
3. List `relevant_chunks` (corpus chunk ids such as `mitre_initial_access_2`). Leave it empty only for out-of-corpus alerts. These labels drive the retrieval metrics.
4. Leave `provenance.reviewed_by: null` until a person has read the case. `python -m tests.harness.loader --mark-reviewed NAME` stamps every unreviewed case, so run it only after reviewing them.
5. Record a cassette: `python -m tests.harness.test_harness --record --only YOUR-ID`.

## Change loop

Change a prompt, corpus file or retrieval parameter, then run live, read the baseline diff, run with `--update-baseline`, and commit code, cassettes and `baseline.json` together. Skipping the live run fails CI with `stale cassette`.

## What CI does

- `harness-replay`: validates every case, replays cassettes, fails on a stale or orphan cassette and on any case that passed in `baseline.json` and does not now. Without a baseline the per-case gate is inactive and the job says so.
- `retrieval-eval`: recomputes retrieval metrics and fails if they drift more than 0.01 from `retrieval_results.json`. It prints the full report between `RETRIEVAL_JSON_BEGIN` and `RETRIEVAL_JSON_END` so the numbers can be read from the log.

Aggregate numbers never gate CI. They are reviewed by a person at `--update-baseline` time.
