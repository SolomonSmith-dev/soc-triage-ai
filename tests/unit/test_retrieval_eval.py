import json
from pathlib import Path

import pytest

from tests.harness.loader import load_cases
from tests.harness.retrieval_eval import SWEEP, labels_from_cases, metrics_from_raw, sweep_from_raw

LABELS = [
    {"id": "a", "query": "q", "relevant": ["c1", "c2"], "should_refuse": False},
    {"id": "b", "query": "q", "relevant": ["c9"], "should_refuse": False},
    {"id": "n1", "query": "q", "relevant": [], "should_refuse": True},
    {"id": "n2", "query": "q", "relevant": [], "should_refuse": True},
]
RAW = {
    "a": [["c1", 0.60], ["x", 0.5], ["c2", 0.4], ["y", 0.3], ["z", 0.2]],
    "b": [["x", 0.50], ["y", 0.4], ["z", 0.3], ["w", 0.25], ["c9", 0.24]],  # relevant at rank 5, outside top-4
    "n1": [["x", 0.12]],
    "n2": [["x", 0.30]],  # out-of-corpus query that clears 0.20
}


def test_known_values():
    m = metrics_from_raw(RAW, LABELS, 0.20)
    assert m["recall_at_k"] == pytest.approx(0.5)      # a: 2/2, b: 0/1
    assert m["hit_at_k"] == 0.5
    assert m["mrr"] == pytest.approx((1 + 0.2) / 2)    # a: rank 1, b: rank 5
    assert m["refusal_tp"] == 1 and m["refusal_fn"] == 1 and m["refusal_fp"] == 0
    assert m["refusal_precision"] == 1.0 and m["refusal_recall"] == 0.5


def test_sweep_covers_requested_range_and_is_monotone_in_recall():
    s = sweep_from_raw(RAW, LABELS)
    assert [x["threshold"] for x in s] == SWEEP == [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    recalls = [x["refusal_recall"] for x in s]
    assert recalls == sorted(recalls)


def test_committed_results_match_their_own_raw_scores():
    p = Path("tests/harness/retrieval_results.json")
    if not p.exists():
        pytest.skip("retrieval_results.json not committed yet")
    doc = json.loads(p.read_text())
    labels = labels_from_cases(load_cases())
    assert doc["metrics"] == metrics_from_raw(doc["raw"], labels)
    assert doc["sweep"] == sweep_from_raw(doc["raw"], labels)
