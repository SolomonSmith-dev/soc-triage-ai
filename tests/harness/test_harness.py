"""Reliability harness CLI.

  python -m tests.harness.test_harness --replay              offline, no API key
  python -m tests.harness.test_harness --record              live run, writes cassettes and results
  python -m tests.harness.test_harness --record --update-baseline
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from tests.harness.loader import CaseLoadError, load_cases
from tests.harness.metrics import compute_metrics
from tests.harness.recorder import Budget, _git_sha
from tests.harness.report import (
    BASELINE, RESULTS, baseline_snapshot, diff_text, load_baseline, write_results,
)
from tests.harness.runner import build_retriever, evaluate_case, run_all  # noqa: F401  (evaluate_case re-exported)

logging.basicConfig(level=logging.WARNING)

# Legacy shape consumed by triage_engine.evaluation (dev console "Run live").
try:
    TEST_CASES = [c.to_legacy() for c in load_cases()]
except CaseLoadError:  # surfaced properly by `loader --validate` and the CI gate
    TEST_CASES = []


def _select(cases, args):
    if args.only:
        cases = [c for c in cases if c.id in args.only]
    if args.category:
        cases = [c for c in cases if c.category == args.category or c.group.startswith(args.category)]
    return cases


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SOC Triage reliability harness")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--replay", action="store_true", help="replay cassettes, no API calls")
    mode.add_argument("--record", action="store_true", help="live calls, write cassettes (default)")
    ap.add_argument("--only", nargs="*", help="case ids")
    ap.add_argument("--category", help="category or group prefix, e.g. phishing or adversarial")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-cost-usd", type=float, default=5.0, help="hard cap for a live run")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--yes", action="store_true", help="skip the baseline confirmation prompt")
    args = ap.parse_args(argv)
    replay = args.replay

    try:
        all_cases = load_cases()
    except CaseLoadError as e:
        print("\n".join(e.errors))
        return 2
    cases = _select(all_cases, args)
    filtered = len(cases) != len(all_cases)

    real_client, budget = None, None
    if not replay:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            print("ANTHROPIC_API_KEY not set. Use --replay for an offline run.")
            return 2
        from anthropic import Anthropic
        real_client, budget = Anthropic(api_key=key), Budget(args.max_cost_usd)

    print(f"{len(cases)} cases, mode={'replay' if replay else 'record'}")
    t0 = time.time()
    retriever = build_retriever()
    print(f"retriever ready in {time.time() - t0:.1f}s")
    results = run_all(cases, retriever, "replay" if replay else "record", workers=args.workers,
                      real_client=real_client, budget=budget)
    metrics = compute_metrics(results, cases)

    for r in results:
        tag = {"ok": "PASS" if r.get("passed") else "FAIL"}.get(r["status"], r["status"].upper())
        print(f"  [{tag}] {r['id']} {r.get('error', '')}")
    print(f"\nevaluated {metrics['evaluated']}/{metrics['total_cases']}  unrecorded {metrics['unrecorded']}  "
          f"stale {metrics['stale']}  errors {metrics['errors']}")
    print(f"standard {metrics['pass_rate_standard']}  adversarial {metrics['pass_rate_adversarial']}")
    if budget:
        print(f"live spend estimate: ${budget.spent_usd:.4f} ({budget.tokens_in} in, {budget.tokens_out} out tokens)")

    if not replay and not filtered:
        meta = {"mode": "live", "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "git_sha": _git_sha(), "model": "claude-sonnet-4-5",
                "spend_usd_estimate": round(budget.spent_usd, 4) if budget else None,
                "tokens_in": budget.tokens_in if budget else 0, "tokens_out": budget.tokens_out if budget else 0}
        write_results(RESULTS, meta, results, metrics)
        print(f"wrote {RESULTS}")
        if args.update_baseline:
            new = baseline_snapshot(results, metrics, meta["git_sha"])
            print("\nBASELINE DIFF\n" + diff_text(load_baseline(), new))
            if metrics["evaluated"] != metrics["total_cases"]:
                print("refusing to update baseline: not every case was evaluated")
                return 1
            if args.yes or input("\nOverwrite baseline? [y/N] ").strip().lower() == "y":
                import json
                BASELINE.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")
                print(f"wrote {BASELINE}")
    return 1 if metrics["stale"] or metrics["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
