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

from tests.test_harness import TEST_CASES, evaluate_case


def load_harness_results(
    path: str = "tests/harness_results.json",
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
        "per_case": results,
    }
