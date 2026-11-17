"""Demo error paths: bad request bodies, contract-invalid output, unexpected exceptions, a failed engine load.

Each must answer with a fixed message and log counts only. Offline: fake engines and clients, no model weights.
"""
import json
import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import soc_demo.api as api_mod
from soc_demo.api import create_app
from soc_demo.guard import DemoConfig, MeteredClient
from triage_engine.triage import SOCTriage

CANARY = "zq-canary-8854"
HITS = [({"id": "c0", "source": "insider_threat.md", "text": "context"}, 0.5)]


def result(actions):
    return {"severity": "high", "confidence": "high", "mitre_techniques": [], "summary": "s",
            "recommended_actions": actions, "escalate": True, "reasoning": "r",
            "sources": ["insider_threat.md"], "retrieval_score": 0.5}


class StubEngine:
    """Returns a fixed result, as if stages 1 to 5 had run, or raises."""

    def __init__(self, res=None, exc=None):
        self.res, self.exc = res, exc

    def triage_with_context(self, alert):
        if self.exc:
            raise self.exc
        return self.res, HITS, False


class Retriever:
    def retrieve(self, query, top_k=4, min_score=0.20):
        return HITS


class Inner:
    """A model that answers with object actions, which the contract forbids."""

    def __init__(self):
        self.messages = self

    def create(self, **kw):
        reply = json.dumps({**result([{"action": f"block {CANARY}", "priority": 1}]), "mitre_techniques": []})
        return SimpleNamespace(content=[SimpleNamespace(text=reply)],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=50))


def app(tmp_path, factory, clock=None, **cfg):
    config = DemoConfig(mode="live", state_path=str(tmp_path / "b.json"), **cfg)
    kw = {"clock": clock} if clock else {}
    return TestClient(create_app(config, factory, **kw))


def logged(caplog) -> str:
    return "\n".join(r.getMessage() + (r.exc_text or "") for r in caplog.records)


@pytest.mark.parametrize("body", [
    b'{"alert": "' + CANARY.encode() + b' \\udc9f"}',   # a lone surrogate: valid JSON, not encodable as UTF-8
    b'{"alert": NaN}',
    b'{"alert": "' + CANARY.encode() + b'", "extra": 1}',
    b'{"alert": "' + CANARY.encode(),                    # truncated JSON
    b'{"alert": ""}',
])
def test_invalid_body_gets_a_fixed_422_that_echoes_nothing(tmp_path, caplog, body):
    c = app(tmp_path, lambda b: (StubEngine(result(["a"])), None))
    with caplog.at_level(logging.DEBUG):
        r = c.post("/triage", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 422 and r.json()["status"] == "invalid_request"
    assert r.headers["x-demo-mode"] == "live"
    assert CANARY not in r.text and CANARY not in logged(caplog)
    assert "event=invalid_request status=422" in logged(caplog)


def test_model_output_with_object_actions_fails_toward_review(tmp_path, caplog):
    """Stage 5 rejects it, so the visitor gets a valid envelope instead of a 500."""
    def factory(budget):
        m = MeteredClient(Inner(), budget)
        return SOCTriage(client=m, retriever=Retriever()), m

    c = app(tmp_path, factory)
    with caplog.at_level(logging.DEBUG):
        r = c.post("/triage", json={"alert": "40 failed logins on jump-host-02"})
    assert r.status_code == 200
    t = r.json()["triage"]
    assert r.json()["guardrail_triggered"] is True and t["escalate"] is True and t["severity"] == "medium"
    assert all(isinstance(a, str) for a in t["recommended_actions"])
    assert c.get("/budget").json()["tokens_used"] == 1050
    assert CANARY not in logged(caplog)


def test_contract_invalid_case_is_never_returned_or_logged(tmp_path, caplog):
    """Defense behind stage 5: an envelope that fails the contract gets a fixed 500, and no success line."""
    c = app(tmp_path, lambda b: (StubEngine(result([{"do": CANARY}])), None))
    with caplog.at_level(logging.DEBUG):
        r = c.post("/triage", json={"alert": "40 failed logins on jump-host-02"})
    assert r.status_code == 500 and r.json()["status"] == "invalid_envelope"
    text = logged(caplog)
    assert "event=invalid_envelope status=500" in text and "event=triaged" not in text
    assert CANARY not in r.text and CANARY not in text


def test_unexpected_exception_logs_type_and_place_only(tmp_path, caplog):
    c = app(tmp_path, lambda b: (StubEngine(exc=RuntimeError(f"model echoed {CANARY}")), None))
    with caplog.at_level(logging.DEBUG):
        r = c.post("/triage", json={"alert": "40 failed logins on jump-host-02"})
    assert r.status_code == 500 and r.json() == {"status": "error",
                                                 "message": "Internal error. The demo logs only the error type."}
    text = logged(caplog)
    assert "event=unhandled_error status=500 route=/triage error=RuntimeError at=" in text
    assert CANARY not in text and "jump-host-02" not in text


def test_failed_engine_load_backs_off_and_reports_it(tmp_path, caplog):
    t = [1_800_000_000.0]
    calls = []

    def factory(budget):
        calls.append(t[0])
        if len(calls) == 1:
            raise ValueError(f"corrupt cassette near {CANARY}")
        return StubEngine(result(["a"])), None

    c = app(tmp_path, factory, clock=lambda: t[0], per_ip_per_minute=100)
    with caplog.at_level(logging.DEBUG):
        for _ in range(3):
            r = c.post("/triage", json={"alert": "40 failed logins on jump-host-02"})
            assert r.status_code == 503 and r.json()["status"] == "engine_unavailable"
        h = c.get("/healthz")
        assert h.status_code == 503 and h.json()["status"] == "error"
        assert len(calls) == 1, "a failed load must not be retried on every request"
        t[0] += api_mod.LOAD_RETRY_SECONDS + 1
        assert c.post("/triage", json={"alert": "40 failed logins on jump-host-02"}).status_code == 200
    assert len(calls) == 2 and c.get("/healthz").json()["status"] == "ok"
    text = logged(caplog)
    assert "event=engine_load_failed error=ValueError at=" in text and CANARY not in text


def test_failed_cached_load_reports_failed_recordings(tmp_path):
    def factory(budget):
        raise OSError("disk")

    c = TestClient(create_app(DemoConfig(state_path=str(tmp_path / "b.json")), factory))
    assert c.get("/samples").status_code == 503
    h = c.get("/healthz")
    assert h.status_code == 503 and h.json()["recordings"] == "failed"


def test_live_samples_are_parsed_once(tmp_path, monkeypatch):
    real, calls = api_mod.load_cases, []
    monkeypatch.setattr(api_mod, "load_cases", lambda d: calls.append(d) or real(d))
    c = app(tmp_path, lambda b: (None, None), cases_dir="tests/harness/cases")
    first, second = c.get("/samples").json(), c.get("/samples").json()
    assert first == second and len(first) >= 100 and len(calls) == 1


def test_ip_salt_is_random_unless_configured(monkeypatch):
    monkeypatch.delenv("DEMO_IP_SALT", raising=False)
    a, b = DemoConfig.from_env().ip_salt, DemoConfig.from_env().ip_salt
    assert a != b and len(a) == 32 and DemoConfig().ip_salt != DemoConfig().ip_salt
    monkeypatch.setenv("DEMO_IP_SALT", "fixed-salt")
    assert DemoConfig.from_env().ip_salt == "fixed-salt"


def test_oversized_bodies_are_refused_before_parsing(tmp_path, caplog):
    c = app(tmp_path, lambda b: (StubEngine(result(["a"])), None))
    big = b'{"alert": "' + CANARY.encode() + b"a" * api_mod.MAX_BODY_BYTES + b'"}'
    with caplog.at_level(logging.DEBUG):
        r = c.post("/triage", content=big, headers={"content-type": "application/json"})
        assert r.status_code == 413 and r.json()["status"] == "body_too_large"
        # sent without a length (chunked), the body is cut off at the limit instead of read to the end
        chunked = c.post("/triage", content=iter([big[:200_000], big[200_000:]]),
                         headers={"content-type": "application/json"})
        assert chunked.status_code == 400
        assert c.post("/triage", json={"alert": "short alert"}).status_code == 200
    assert CANARY not in logged(caplog)
