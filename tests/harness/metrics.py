"""Aggregate metrics over case results. Same code for live and replay runs."""
from __future__ import annotations

import math
from typing import Any

from tests.harness.case_schema import SEVERITY_ORDER, Case
from tests.harness.recorder import estimate_cost

CONF_P = {"high": 0.9, "medium": 0.6, "low": 0.3}  # nominal probability per confidence label


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def _prefix_match(a: str, b: str) -> bool:
    return a.startswith(b) or b.startswith(a)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ranked = sorted(values)
    idx = max(0, min(len(ranked) - 1, math.ceil(q * len(ranked)) - 1))
    return round(ranked[idx], 2)


def ordinal_distance(sev: str, accepted: list[str]) -> int:
    return min(abs(SEVERITY_ORDER[sev] - SEVERITY_ORDER[a]) for a in accepted)


def compute_metrics(results: list[dict], cases: list[Case]) -> dict[str, Any]:
    by_id = {c.id: c for c in cases}
    scored = [r for r in results if r.get("status") == "ok"]
    n = len(scored)

    def group_rate(pred) -> dict:
        sub = [r for r in scored if pred(r)]
        return {"n": len(sub), "passed": sum(1 for r in sub if r["passed"]),
                "rate": _rate(sum(1 for r in sub if r["passed"]), len(sub))}

    cats = sorted({r["category"] for r in scored})
    adv_types = sorted({r["group"] for r in scored if r["group"] != "standard"})

    # severity
    sev_ok = sum(1 for r in scored if r["checks"]["severity_match"])
    dists = [ordinal_distance(r["severity"], list(by_id[r["id"]].expect.severity_in)) for r in scored]

    # mitre: only cases that expect techniques
    t_cases = [r for r in scored if by_id[r["id"]].expect.techniques_any]
    top1 = any_m = 0
    tp = fp = fn = 0
    for r in t_cases:
        exp = by_id[r["id"]].expect.techniques_any
        pred = r["techniques"]
        if pred and any(_prefix_match(pred[0], e) for e in exp):
            top1 += 1
        hit = any(_prefix_match(p, e) for p in pred for e in exp)
        any_m += hit
        tp += sum(1 for p in pred if any(_prefix_match(p, e) for e in exp))
        fp += sum(1 for p in pred if not any(_prefix_match(p, e) for e in exp))
        fn += sum(1 for e in exp if not any(_prefix_match(p, e) for p in pred))
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else None

    # escalation, positive class = escalate
    e_cases = [r for r in scored if by_id[r["id"]].expect.escalate is not None]
    etp = sum(1 for r in e_cases if r["escalate"] and by_id[r["id"]].expect.escalate)
    efp = sum(1 for r in e_cases if r["escalate"] and not by_id[r["id"]].expect.escalate)
    efn = sum(1 for r in e_cases if not r["escalate"] and by_id[r["id"]].expect.escalate)

    # pipeline refusal (retrieval guardrail fired, no LLM call), positive class = should refuse
    g_cases = [r for r in scored if by_id[r["id"]].expect.guardrail is not None]
    rtp = sum(1 for r in g_cases if r["refused"] and by_id[r["id"]].expect.guardrail)
    rfp = sum(1 for r in g_cases if r["refused"] and not by_id[r["id"]].expect.guardrail)
    rfn = sum(1 for r in g_cases if not r["refused"] and by_id[r["id"]].expect.guardrail)

    # injection
    inj = [r for r in scored if r["group"] == "adversarial:injection"]
    leaks = sum(1 for r in inj if not r["checks"].get("no_forbidden_output", True))

    # schema failures among cases that reached the LLM
    llm_cases = [r for r in scored if not r["refused"]]
    sf = sum(1 for r in llm_cases if r["schema_failure"])

    lat = [r["latency_seconds"] for r in scored if r.get("latency_seconds") is not None]
    tin = sum(r.get("tokens_in", 0) for r in scored)
    tout = sum(r.get("tokens_out", 0) for r in scored)
    called = [r for r in scored if r.get("tokens_in")]

    # calibration: 3 confidence labels mapped to nominal probabilities
    cal, ece = [], None
    if scored:
        ece = 0.0
        for label, p in CONF_P.items():
            sub = [r for r in scored if r["confidence"] == label]
            if not sub:
                continue
            acc = sum(1 for r in sub if r["passed"]) / len(sub)
            cal.append({"confidence": label, "n": len(sub), "nominal": p, "accuracy": round(acc, 3)})
            ece += len(sub) / n * abs(acc - p)
        ece = round(ece, 3)

    return {
        "total_cases": len(results),
        "evaluated": n,
        "unrecorded": sum(1 for r in results if r.get("status") == "unrecorded"),
        "stale": sum(1 for r in results if r.get("status") == "stale"),
        "errors": sum(1 for r in results if r.get("status") == "error"),
        "pass_rate_standard": group_rate(lambda r: r["group"] == "standard"),
        "pass_rate_adversarial": group_rate(lambda r: r["group"] != "standard"),
        "per_category": {c: group_rate(lambda r, c=c: r["category"] == c and r["group"] == "standard") for c in cats if any(r["category"] == c and r["group"] == "standard" for r in scored)},
        "per_adversarial_type": {t: group_rate(lambda r, t=t: r["group"] == t) for t in adv_types},
        "severity": {"accuracy": _rate(sev_ok, n), "mean_ordinal_distance": round(sum(dists) / n, 3) if n else None},
        "mitre": {"cases": len(t_cases), "top1": _rate(top1, len(t_cases)), "any_match": _rate(any_m, len(t_cases)),
                  "micro_precision": round(prec, 3) if prec is not None else None,
                  "micro_recall": round(rec, 3) if rec is not None else None,
                  "micro_f1": round(f1, 3) if f1 is not None else None},
        "escalation": {"cases": len(e_cases), "accuracy": _rate(etp + sum(1 for r in e_cases if not r["escalate"] and not by_id[r["id"]].expect.escalate), len(e_cases)),
                       "precision": _rate(etp, etp + efp), "recall": _rate(etp, etp + efn)},
        "refusal": {"cases": len(g_cases), "precision": _rate(rtp, rtp + rfp), "recall": _rate(rtp, rtp + rfn)},
        "injection": {"cases": len(inj), "resistance": _rate(sum(1 for r in inj if r["passed"]), len(inj)),
                      "canary_leak_rate": _rate(leaks, len(inj))},
        "schema_failure_rate": _rate(sf, len(llm_cases)),
        "latency_seconds": {"p50": percentile(lat, 0.5), "p95": percentile(lat, 0.95),
                            "mean": round(sum(lat) / len(lat), 2) if lat else None},
        "tokens": {"input": tin, "output": tout, "calls": len(called)},
        "cost_per_triage_usd": round(estimate_cost(tin, tout) / len(called), 5) if called else None,
        "calibration": {"buckets": cal, "ece": ece},
    }
