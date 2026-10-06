"""Bridge between the CLI test harness and the Streamlit evaluation tab.

Two modes:
  - load_harness_results: read existing tests/harness_results.json
  - run_harness_live: execute all TEST_CASES against a live triage engine

Metrics derivation is shared between both paths.
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from tests.harness.test_harness import TEST_CASES, evaluate_case


def load_harness_results(
    path: str = "tests/harness/harness_results.json",
) -> Optional[Dict]:
    """Load and parse harness results from disk.

    Returns dict {"results": [...]} or None if file missing/empty/malformed.
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return None
    if not data:
        return None
    return {"results": data}


def run_harness_live(triage_engine) -> Dict:
    """Execute all TEST_CASES against a live triage engine.

    Returns the same shape as load_harness_results: {"results": [...]}.
    Does not write to disk.
    """
    results: List[Dict] = []
    for case in TEST_CASES:
        case_start = time.time()
        try:
            result = triage_engine.triage(case["alert"])
            evaluation = evaluate_case(result, case)
            elapsed = time.time() - case_start
            results.append({
                "id": case["id"],
                "alert_excerpt": case["alert"][:100],
                "severity": result["severity"],
                "confidence": result["confidence"],
                "escalate": result["escalate"],
                "techniques": result.get("mitre_techniques", []),
                "retrieval_score": result.get("retrieval_score"),
                "sources": result.get("sources", []),
                "passed": evaluation["passed"],
                "checks": evaluation["checks"],
                "latency_seconds": round(elapsed, 2),
            })
        except Exception as e:
            results.append({
                "id": case["id"],
                "passed": False,
                "error": f"{type(e).__name__}: {e}",
            })
    return {"results": results}


def compute_eval_metrics(results: List[Dict]) -> Dict:
    """Derive dashboard metrics from raw results."""
    total = len(results)
    if total == 0:
        return {"total": 0, "passed": 0, "pass_rate": 0.0}

    passed = sum(1 for r in results if r.get("passed"))

    def _check_rate(key: str) -> Optional[float]:
        applicable = [r for r in results if "checks" in r and key in r["checks"]]
        if not applicable:
            return None
        hits = sum(1 for r in applicable if r["checks"][key])
        return round(hits / len(applicable), 3)

    scores = [r.get("retrieval_score") for r in results
              if r.get("retrieval_score") is not None]
    latencies = [r.get("latency_seconds") for r in results
                 if r.get("latency_seconds") is not None]

    def _percentile(values: List[float], q: float) -> Optional[float]:
        # Nearest-rank percentile; None when there is nothing to rank.
        if not values:
            return None
        ranked = sorted(values)
        idx = max(0, min(len(ranked) - 1, -(-int(q * 100) * len(ranked) // 100) - 1))
        return round(ranked[idx], 2)

    # Escalation errors split by direction: a missed escalation (should have
    # escalated, did not) is the costly SOC failure; over-escalation is noise.
    esc_checked = [r for r in results
                   if "checks" in r and "escalate_match" in r["checks"]]
    missed = sum(1 for r in esc_checked
                 if not r["checks"]["escalate_match"] and r.get("escalate") is False)
    over = sum(1 for r in esc_checked
               if not r["checks"]["escalate_match"] and r.get("escalate") is True)
    errors = sum(1 for r in results if r.get("error"))

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3),
        "severity_accuracy": _check_rate("severity_match"),
        "escalation_accuracy": _check_rate("escalate_match"),
        "techniques_accuracy": _check_rate("techniques_match"),
        "retrieval_threshold_rate": _check_rate("retrieval_score_ok"),
        "avg_retrieval_score": (
            round(sum(scores) / len(scores), 3) if scores else 0.0
        ),
        "avg_latency": (
            round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        ),
        "latency_p50": _percentile(latencies, 0.50),
        "latency_p95": _percentile(latencies, 0.95),
        "missed_escalation_rate": (
            round(missed / len(esc_checked), 3) if esc_checked else None
        ),
        "over_escalation_rate": (
            round(over / len(esc_checked), 3) if esc_checked else None
        ),
        "error_rate": round(errors / total, 3),
        "per_case": results,
    }
