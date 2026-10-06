"""Demo mode: refuses when the cap is hit, rate limits per IP, never logs alert bodies."""
import json
import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from soc_demo.api import create_app
from soc_demo.guard import DailyBudget, DemoConfig, IPRateLimiter, MeteredClient, client_ip
from triage_engine.triage import SOCTriage

SECRET_ALERT = "Employee zq-canary-7731 exfiltrated payroll.xlsx to 203.0.113.99 via rclone overnight"
REPLY = ('{"severity":"high","confidence":"high","mitre_techniques":["T1567"],"summary":"s",'
         '"recommended_actions":["a"],"escalate":true,"reasoning":"r"}')


class FakeInner:
    def __init__(self, tokens=(1000, 200)):
        self.messages, self.tokens, self.calls = self, tokens, 0

    def create(self, **kw):
        self.calls += 1
        return SimpleNamespace(content=[SimpleNamespace(text=REPLY)],
                               usage=SimpleNamespace(input_tokens=self.tokens[0], output_tokens=self.tokens[1]))


class FakeRetriever:
    def __init__(self, hits=True):
        self.hits = hits

    def retrieve(self, query, top_k=4, min_score=0.20):
        return [({"id": "c0", "source": "insider_threat.md", "text": "context"}, 0.5)] if self.hits else []


def make(tmp_path, hits=True, tokens=(1000, 200), **cfg):
    inner = FakeInner(tokens)
    config = DemoConfig(state_path=str(tmp_path / "b.json"), **cfg)

    def factory(budget):
        m = MeteredClient(inner, budget)
        return SOCTriage(client=m, retriever=FakeRetriever(hits)), m

    return TestClient(create_app(config, factory)), inner


def test_triage_returns_contract_schema(tmp_path):
    c, _ = make(tmp_path)
    r = c.post("/triage", json={"alert": SECRET_ALERT})
    assert r.status_code == 200
    body = r.json()
    assert body["case_id"].startswith("SOC-") and body["triage"]["severity"] == "high"
    assert body["observables"]["ipv4"] == ["203.0.113.99"]


def test_refuses_with_clear_message_when_daily_cap_is_hit(tmp_path):
    c, inner = make(tmp_path, daily_token_cap=1500, per_ip_per_minute=100)
    assert c.post("/triage", json={"alert": SECRET_ALERT}).status_code == 200   # uses 1200
    assert c.post("/triage", json={"alert": SECRET_ALERT}).status_code == 200   # 2400 >= 1500 afterwards
    r = c.post("/triage", json={"alert": SECRET_ALERT})
    assert r.status_code == 429
    assert r.json()["status"] == "demo_budget_reached" and "budget reached" in r.json()["message"].lower()
    assert inner.calls == 2  # no model call once the cap is hit
    assert c.get("/budget").json()["tokens_remaining"] == 0


def test_budget_survives_restart_and_resets_next_day(tmp_path):
    t = [1_800_000_000.0]
    path = str(tmp_path / "b.json")
    b1 = DailyBudget(1000, path, lambda: t[0])
    b1.add(900)
    assert DailyBudget(1000, path, lambda: t[0]).used == 900
    t[0] += 86400
    assert DailyBudget(1000, path, lambda: t[0]).used == 0


def test_per_ip_rate_limit_is_per_address(tmp_path):
    c, _ = make(tmp_path, per_ip_per_minute=2, per_ip_per_day=100)
    h1, h2 = {"X-Forwarded-For": "198.51.100.1"}, {"X-Forwarded-For": "198.51.100.2"}
    assert c.post("/triage", json={"alert": "a b"}, headers=h1).status_code == 200
    assert c.post("/triage", json={"alert": "a b"}, headers=h1).status_code == 200
    r = c.post("/triage", json={"alert": "a b"}, headers=h1)
    assert r.status_code == 429 and r.json()["status"] == "rate_limited" and "Retry-After" in r.headers
    assert c.post("/triage", json={"alert": "a b"}, headers=h2).status_code == 200


def test_client_ip_uses_trusted_hop_not_spoofed_prefix():
    assert client_ip("6.6.6.6, 198.51.100.7", "10.0.0.1", 1) == "198.51.100.7"
    assert client_ip(None, "10.0.0.1", 1) == "10.0.0.1"


def test_limiter_window_expires():
    t = [0.0]
    lim = IPRateLimiter(1, 10, lambda: t[0])
    assert lim.check("x")[0] and not lim.check("x")[0]
    t[0] = 61
    assert lim.check("x")[0]


def test_oversize_alert_rejected_before_any_work(tmp_path):
    c, inner = make(tmp_path, max_alert_chars=50)
    r = c.post("/triage", json={"alert": "x" * 51})
    assert r.status_code == 413 and inner.calls == 0


def test_no_key_configured_is_a_clear_503(tmp_path):
    cfg = DemoConfig(state_path=str(tmp_path / "b.json"))
    c = TestClient(create_app(cfg, lambda budget: (None, None)))
    r = c.post("/triage", json={"alert": "x y"})
    assert r.status_code == 503 and r.json()["status"] == "not_configured"


@pytest.mark.parametrize("hits", [True, False])
def test_alert_body_never_appears_in_any_log(tmp_path, caplog, hits):
    """Covers the success path and the retrieval-refusal path, where the engine itself logs alert text."""
    c, _ = make(tmp_path, hits=hits)
    with caplog.at_level(logging.DEBUG):
        for logger_name in ("soc_demo", "triage_engine.triage"):
            logging.getLogger(logger_name).setLevel(logging.DEBUG)
        r = c.post("/triage", json={"alert": SECRET_ALERT})
        assert r.status_code == 200
        # also exercise the over-limit and bad-JSON paths
        c.post("/triage", json={"alert": SECRET_ALERT + " " + "x" * 5000})
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert caplog.records, "expected log records"
    for needle in ("zq-canary-7731", "payroll.xlsx", "203.0.113.99", "rclone"):
        assert needle not in text, needle
    assert "alert_chars=" in text  # counts are logged
