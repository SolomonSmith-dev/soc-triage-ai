"""Tests for evaluation results loader and metrics derivation."""
import json
from evaluation import (
    load_harness_results,
    compute_eval_metrics,
)


def _write_results(tmp_path, payload):
    p = tmp_path / "harness_results.json"
    p.write_text(json.dumps(payload))
    return str(p)


def test_load_returns_none_when_missing():
    assert load_harness_results("does/not/exist.json") is None


def test_load_returns_results_when_present(tmp_path):
    payload = [{"id": "T1", "passed": True}]
    path = _write_results(tmp_path, payload)
    out = load_harness_results(path)
    assert out["results"] == payload


def test_compute_metrics_pass_rate():
    results = [
        {"id": "T1", "passed": True, "checks": {}, "severity": "high",
         "retrieval_score": 0.5, "latency_seconds": 8.0},
        {"id": "T2", "passed": False, "checks": {}, "severity": "low",
         "retrieval_score": 0.3, "latency_seconds": 9.0},
    ]
    m = compute_eval_metrics(results)
    assert m["total"] == 2
    assert m["passed"] == 1
    assert m["pass_rate"] == 0.5
    assert m["avg_retrieval_score"] == 0.4
    assert m["avg_latency"] == 8.5


def test_compute_metrics_per_check_accuracy():
    results = [
        {"id": "T1", "passed": True,
         "checks": {"severity_match": True, "escalate_match": True,
                    "techniques_match": True, "retrieval_score_ok": True}},
        {"id": "T2", "passed": False,
         "checks": {"severity_match": False, "escalate_match": True,
                    "techniques_match": True, "retrieval_score_ok": True}},
    ]
    m = compute_eval_metrics(results)
    assert m["severity_accuracy"] == 0.5
    assert m["escalation_accuracy"] == 1.0
