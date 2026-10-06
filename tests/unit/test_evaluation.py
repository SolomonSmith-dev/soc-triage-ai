"""Tests for evaluation results loader and metrics derivation."""
import json
from triage_engine.evaluation import (
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


def test_compute_metrics_escalation_direction_and_errors():
    results = [
        {"id": "T1", "passed": False, "escalate": False,
         "checks": {"escalate_match": False}, "latency_seconds": 1.0},
        {"id": "T2", "passed": False, "escalate": True,
         "checks": {"escalate_match": False}, "latency_seconds": 2.0},
        {"id": "T3", "passed": True, "escalate": True,
         "checks": {"escalate_match": True}, "latency_seconds": 3.0},
        {"id": "T4", "passed": False, "error": "TimeoutError: x"},
    ]
    m = compute_eval_metrics(results)
    assert m["missed_escalation_rate"] == 0.333
    assert m["over_escalation_rate"] == 0.333
    assert m["error_rate"] == 0.25


def test_compute_metrics_latency_percentiles():
    results = [{"id": f"T{i}", "passed": True, "latency_seconds": float(i)}
               for i in range(1, 21)]
    m = compute_eval_metrics(results)
    assert m["latency_p50"] == 10.0
    assert m["latency_p95"] == 19.0


def test_compute_metrics_percentiles_none_without_latency():
    m = compute_eval_metrics([{"id": "T1", "passed": True}])
    assert m["latency_p50"] is None
    assert m["missed_escalation_rate"] is None
