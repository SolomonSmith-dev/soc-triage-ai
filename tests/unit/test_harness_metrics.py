import pytest

from tests.harness.case_schema import Case
from tests.harness.metrics import compute_metrics, ordinal_distance, percentile
from tests.harness.runner import evaluate_case


def _c(id, sev, techs=(), esc=None, guard=None, adv=None, forbid=()):
    d = {"id": id, "category": "phishing", "alert": "a",
         "expect": {"severity_in": sev, "techniques_any": list(techs), "escalate": esc, "guardrail": guard,
                    "forbid_in_output": list(forbid)},
         "provenance": {"drafted_by": "t"}}
    if adv:
        d["adversarial"] = {"type": adv}
    return Case.model_validate(d)


def _r(c, sev, techs, esc, conf="high", passed=True, refused=False, sf=False, lat=1.0, checks=None):
    return {"id": c.id, "group": c.group, "category": c.category, "status": "ok", "severity": sev,
            "techniques": techs, "escalate": esc, "confidence": conf, "passed": passed, "refused": refused,
            "schema_failure": sf, "latency_seconds": lat, "tokens_in": 1000, "tokens_out": 100,
            "checks": checks or {"severity_match": True}}


def test_ordinal_distance_to_nearest_accepted():
    assert ordinal_distance("critical", ["high", "medium"]) == 1
    assert ordinal_distance("informational", ["high"]) == 3


def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.5) == 5
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.95) == 10
    assert percentile([], 0.5) is None


def test_metrics_known_inputs():
    a = _c("A", ["high"], ["T1566"], True)
    b = _c("B", ["high"], ["T1003"], True)
    n = _c("N", ["informational"], [], False, guard=True)
    ok = _c("OK", ["low"], [], False, guard=False)
    inj = _c("I", ["high"], ["T1190"], True, adv="injection", forbid=["CANARY"])
    results = [
        _r(a, "high", ["T1566.002", "T1204"], True),
        _r(b, "high", ["T1021", "T1003.001"], False, passed=False, checks={"severity_match": True}),  # top1 miss, any hit
        _r(n, "informational", [], False, refused=True),
        _r(ok, "low", [], False, refused=True, passed=False),  # false refusal
        _r(inj, "low", ["T1190"], True, passed=False, checks={"severity_match": False, "no_forbidden_output": False}),
    ]
    m = compute_metrics(results, [a, b, n, ok, inj])
    assert m["mitre"]["cases"] == 3
    assert m["mitre"]["top1"] == pytest.approx(0.667, abs=1e-3)
    assert m["mitre"]["any_match"] == 1.0
    assert m["refusal"]["precision"] == 0.5 and m["refusal"]["recall"] == 1.0
    assert m["injection"]["resistance"] == 0.0 and m["injection"]["canary_leak_rate"] == 1.0
    assert m["escalation"]["recall"] == pytest.approx(0.667, abs=1e-3)
    assert m["severity"]["accuracy"] == 0.8
    assert m["cost_per_triage_usd"] == pytest.approx(0.0045)


def test_unrecorded_and_stale_excluded_from_rates():
    a = _c("A", ["high"])
    m = compute_metrics([{"id": "A", "status": "unrecorded", "passed": None, "group": "standard", "category": "x"}], [a])
    assert m["evaluated"] == 0 and m["unrecorded"] == 1 and m["pass_rate_standard"]["rate"] is None


def test_evaluate_case_new_checks():
    case = {"expect_severity_in": ["informational"], "min_retrieval_score": 0.0, "expect_guardrail": True,
            "forbid_in_output": ["CANARY-1"]}
    res = {"severity": "informational", "escalate": False, "retrieval_score": 0.0, "summary": "Guardrail"}
    assert evaluate_case(res, case, guardrail=True)["passed"]
    assert not evaluate_case(res, case, guardrail=False)["passed"]
    res["summary"] = "CANARY-1"
    assert not evaluate_case(res, case, guardrail=True)["checks"]["no_forbidden_output"]
