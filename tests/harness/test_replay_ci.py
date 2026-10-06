"""CI gate. Offline and deterministic: no API key, no LLM call.

Hard failures: invalid case files, stale cassettes, orphan cassettes, and any case
that passed in the committed baseline but fails or is missing now. Aggregate
numbers are never gated here; they are reviewed at --update-baseline time.
Cases with no cassette are reported as unrecorded and skipped until a baseline exists.
"""
import json
import os

import pytest

from tests.harness.loader import CaseLoadError, load_cases
from tests.harness.metrics import compute_metrics
from tests.harness.recorder import CASSETTE_DIR
from tests.harness.report import load_baseline
from tests.harness.runner import build_retriever, run_all


def test_cases_valid():
    try:
        cases = load_cases()
    except CaseLoadError as e:
        pytest.fail("\n".join(e.errors))
    assert len(cases) >= 100


def test_no_orphan_cassettes():
    ids = {c.id for c in load_cases()}
    orphans = [p.name for p in CASSETTE_DIR.glob("*.json") if p.stem not in ids]
    assert not orphans, f"cassettes without a case: {orphans}"


@pytest.fixture(scope="module")
def replay_results():
    try:
        retriever = build_retriever()
    except Exception as e:  # embedding weights unavailable (offline sandbox)
        if os.getenv("HARNESS_REQUIRE_RETRIEVER") == "1":
            raise
        pytest.skip(f"embedding model unavailable: {type(e).__name__}")
    cases = load_cases()
    return cases, run_all(cases, retriever, "replay")


def test_replay_gate(replay_results):
    cases, results = replay_results
    metrics = compute_metrics(results, cases)
    print(json.dumps({k: metrics[k] for k in ("total_cases", "evaluated", "unrecorded", "stale", "errors",
                                               "pass_rate_standard", "pass_rate_adversarial")}, indent=1))
    stale = [r["id"] for r in results if r["status"] == "stale"]
    errors = [r["id"] for r in results if r["status"] == "error"]
    assert not stale, f"stale cassettes: {stale}"
    assert not errors, f"errored cases: {errors}"
    base = load_baseline()
    if base:
        by_id = {r["id"]: r for r in results}
        regress = [i for i, ok in base["per_case"].items() if ok and not (by_id.get(i, {}).get("passed"))]
        assert not regress, f"baseline passes that now fail or are unrecorded: {regress}"
    else:
        print("no baseline.json: per-case regression gate inactive until a live run is recorded")
