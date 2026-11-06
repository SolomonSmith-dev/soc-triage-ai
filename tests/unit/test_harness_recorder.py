import json
from types import SimpleNamespace

import pytest

from tests.harness.case_schema import Case
from tests.harness.recorder import (
    Budget, BudgetExceededError, MissingCassetteError, RecordingClient, ReplayClient,
    StaleCassetteError, estimate_cost, prompt_hash,
)
from tests.harness.runner import run_case

REPLY = ('{"severity":"high","confidence":"high","mitre_techniques":["T1566"],"summary":"s",'
         '"recommended_actions":["a"],"escalate":true,"reasoning":"r"}')


class FakeInner:
    def __init__(self):
        self.messages = self
        self.calls = 0

    def create(self, **kw):
        self.calls += 1
        return SimpleNamespace(content=[SimpleNamespace(text=REPLY)],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=200))


class FakeRetriever:
    def __init__(self, hits=True):
        self.hits = hits

    def retrieve(self, query, top_k=4, min_score=0.20):
        return [({"id": "c0", "source": "s.md", "text": "ctx T1566 " + query}, 0.5)] if self.hits else []


def _case(**exp):
    base = {"severity_in": ["high"], "techniques_any": ["T1566"], "escalate": True, "min_retrieval_score": 0.2}
    base.update(exp)
    return Case.model_validate({"id": "X-1", "category": "phishing", "alert": "alert text", "expect": base,
                                "provenance": {"drafted_by": "t"}})


def test_hash_changes_with_prompt():
    a = prompt_hash("m", [{"role": "user", "content": "a"}])
    assert a == prompt_hash("m", [{"role": "user", "content": "a"}])
    assert a != prompt_hash("m", [{"role": "user", "content": "b"}])


def test_record_then_replay_round_trip(tmp_path):
    inner = FakeInner()
    rec = run_case(_case(), FakeRetriever(), "record", tmp_path, real_client=inner)
    assert rec["status"] == "ok" and rec["passed"] and inner.calls == 1
    assert rec["tokens_in"] == 1000
    rep = run_case(_case(), FakeRetriever(), "replay", tmp_path)
    assert rep["status"] == "ok" and rep["passed"] and inner.calls == 1


def test_stale_cassette_detected(tmp_path):
    run_case(_case(), FakeRetriever(), "record", tmp_path, real_client=FakeInner())
    path = tmp_path / "X-1.json"
    data = json.loads(path.read_text())
    data["prompt_sha256"] = "0" * 64
    path.write_text(json.dumps(data))
    r = run_case(_case(), FakeRetriever(), "replay", tmp_path)
    assert r["status"] == "stale" and "stale cassette" in r["error"]


def test_missing_cassette_is_unrecorded_not_failed(tmp_path):
    r = run_case(_case(), FakeRetriever(), "replay", tmp_path)
    assert r["status"] == "unrecorded" and r["passed"] is None


def test_no_hits_means_no_llm_call_and_refusal(tmp_path):
    inner = FakeInner()
    case = _case(severity_in=["informational"], escalate=False, techniques_any=[], guardrail=True, min_retrieval_score=0.0)
    r = run_case(case, FakeRetriever(hits=False), "replay", tmp_path)
    assert r["status"] == "ok" and r["refused"] and r["passed"]
    assert inner.calls == 0


def test_forbidden_string_in_output_fails_case(tmp_path):
    # the fake reply contains the summary "s"; a canary equal to a value in the output must fail the case
    r = run_case(_case(forbid_in_output=["T1566"]), FakeRetriever(), "record", tmp_path, real_client=FakeInner())
    assert r["checks"]["no_forbidden_output"] is False and not r["passed"]


def test_budget_cap(tmp_path):
    b = Budget(max_usd=0.001)
    c = RecordingClient(FakeInner(), "X-2", tmp_path, b)
    c.messages.create(model="m", messages=[{"role": "user", "content": "x"}])
    assert b.spent_usd == pytest.approx(estimate_cost(1000, 200))
    with pytest.raises(BudgetExceededError):
        c.messages.create(model="m", messages=[{"role": "user", "content": "x"}])


def test_preflight_raises_on_bad_key_before_any_case_runs():
    from tests.harness.recorder import preflight

    class Bad:
        messages = SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("invalid x-api-key")))

    with pytest.raises(RuntimeError):
        preflight(Bad(), "m")
    preflight(FakeInner(), "m")  # a working client passes


def test_empty_model_reply_is_recorded_and_replays_as_a_schema_failure(tmp_path):
    class Empty:
        def __init__(self):
            self.messages = self

        def create(self, **kw):
            return SimpleNamespace(content=[], stop_reason="refusal",
                                   usage=SimpleNamespace(input_tokens=500, output_tokens=0))

    rec = run_case(_case(), FakeRetriever(), "record", tmp_path, real_client=Empty())
    assert rec["status"] == "ok" and rec["schema_failure"] and not rec["passed"]
    data = json.loads((tmp_path / "X-1.json").read_text())
    assert data["response_text"] is None and data["stop_reason"] == "refusal"
    rep = run_case(_case(), FakeRetriever(), "replay", tmp_path)
    assert rep["status"] == "ok" and rep["schema_failure"]
