"""Run cases live, recorded, or replayed through SOCTriage and score them."""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from tests.harness.case_schema import Case
from tests.harness.recorder import (
    CASSETTE_DIR,
    Budget,
    RecordingClient,
    ReplayClient,
    StaleCassetteError,
    MissingCassetteError,
)


def evaluate_case(result: dict, case: dict, guardrail: bool | None = None) -> dict:
    """Check a triage result against one case in legacy dict form.

    `guardrail` is whether the refusal path fired. Two checks are additive and
    only run when the case asks for them: guardrail_match and no_forbidden_output.
    """
    checks: dict[str, bool] = {}
    checks["severity_match"] = result["severity"] in case["expect_severity_in"]

    if "expect_escalate" in case:
        checks["escalate_match"] = result["escalate"] == case["expect_escalate"]

    if "expect_techniques_any" in case:
        result_techs = set(result.get("mitre_techniques", []))
        expected = set(case["expect_techniques_any"])
        match = any(
            any(rt.startswith(et) or et.startswith(rt) for rt in result_techs)
            for et in expected
        )
        checks["techniques_match"] = match if result_techs else False

    checks["retrieval_score_ok"] = result.get("retrieval_score", 0) >= case["min_retrieval_score"]

    if "expect_guardrail" in case:
        checks["guardrail_match"] = bool(guardrail) == case["expect_guardrail"]

    if case.get("forbid_in_output"):
        blob = json.dumps(result, ensure_ascii=False)
        checks["no_forbidden_output"] = not any(s in blob for s in case["forbid_in_output"])

    return {"passed": all(checks.values()), "checks": checks}


def run_case(case: Case, retriever, mode: str, cassette_dir: Path = CASSETTE_DIR,
             real_client=None, budget: Budget | None = None) -> dict[str, Any]:
    """mode: 'replay' or 'record'. Never raises; failures become a status."""
    from triage_engine.triage import SOCTriage

    if mode == "record":
        client = RecordingClient(real_client, case.id, cassette_dir, budget)
    else:
        client = ReplayClient(case.id, cassette_dir)
    base = {"id": case.id, "group": case.group, "category": case.category,
            "alert_excerpt": case.alert[:100]}
    try:
        engine = SOCTriage(client=client, retriever=retriever)
        result, hits, guard = engine.triage_with_context(case.alert)
    except Exception as e:
        return {**base, "passed": False, "status": "error", "error": f"{type(e).__name__}: {e}"}

    err = client.last_error
    if isinstance(err, StaleCassetteError):
        return {**base, "passed": False, "status": "stale", "error": str(err)}
    if isinstance(err, MissingCassetteError):
        return {**base, "passed": None, "status": "unrecorded", "error": str(err)}
    if err is not None:
        return {**base, "passed": False, "status": "error", "error": f"{type(err).__name__}: {err}"}

    refused = guard and not hits           # retrieval guardrail, no LLM call
    schema_failure = guard and bool(hits)  # LLM path produced unusable output
    ev = evaluate_case(result, case.to_legacy(), guardrail=guard)
    tin, tout = client.last_usage
    return {
        **base,
        "severity": result["severity"],
        "confidence": result["confidence"],
        "escalate": result["escalate"],
        "techniques": result.get("mitre_techniques", []),
        "retrieval_score": result.get("retrieval_score"),
        "sources": result.get("sources", []),
        "guardrail": guard,
        "refused": refused,
        "schema_failure": schema_failure,
        "passed": ev["passed"],
        "checks": ev["checks"],
        "status": "ok",
        "latency_seconds": round(client.last_latency, 2) if client.last_latency is not None else None,
        "tokens_in": tin,
        "tokens_out": tout,
    }


def run_all(cases: list[Case], retriever, mode: str, workers: int = 1, **kw) -> list[dict]:
    if workers <= 1 or mode != "record":
        return [run_case(c, retriever, mode, **kw) for c in cases]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda c: run_case(c, retriever, mode, **kw), cases))


def build_retriever():
    from triage_engine.rag.corpus import load_corpus
    from triage_engine.rag.retriever import ThreatIntelRetriever
    from triage_engine.triage import CORPUS_DIR

    r = ThreatIntelRetriever()
    r.index(load_corpus(CORPUS_DIR))
    return r
