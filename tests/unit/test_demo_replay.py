"""Demo cached mode: replays harness recordings, refuses out of corpus, never builds a model client.

Offline. The real-retriever check over every committed cassette is tests/harness/test_demo_replay_ci.py.
"""
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import triage_engine.triage as triage_mod
from soc_demo.api import create_app
from soc_demo.guard import DemoConfig
from soc_demo.replay import (
    CachedClient, HarnessCase, NotRecorded, Recording, load_cases, load_recordings, prompt_hash,
)
from tests.harness.recorder import CASSETTE_DIR
from tests.harness.recorder import prompt_hash as harness_prompt_hash
from triage_engine.triage import SOCTriage

CASES_DIR = Path("tests/harness/cases")
REPLY = ('{"severity":"high","confidence":"high","mitre_techniques":["T1110"],"summary":"s",'
         '"recommended_actions":["a"],"escalate":true,"reasoning":"r"}')
RECORDED = "Recorded zq-canary-4410: 900 failed SSH logins from 198.51.100.44 against srv-bastion-02\n"
UNRECORDED = "Unrecorded zq-canary-5521: 40 failed SSH logins from 198.51.100.45 against srv-bastion-03"
OFF_TOPIC = "Off-topic zq-canary-6632: roasted vegetable soup and a fruit cup on Thursday"
CANARIES = ("zq-canary-4410", "zq-canary-5521", "zq-canary-6632", "198.51.100.4", "srv-bastion-0")


class FakeRetriever:
    """Context for anything except off-topic text, which gets no hit, like the 0.20 threshold would."""

    def retrieve(self, query, top_k=4, min_score=0.20):
        if query.startswith("Off-topic"):
            return []
        return [({"id": "log_analysis_linux_3", "source": "log_analysis_linux.md",
                  "text": "SSH brute force: many failures from one source. T1110"}, 0.52)]


class Capture:
    """Records the kwargs the engine would send to the model, then fails like a dead network."""

    def __init__(self):
        self.messages, self.kwargs = self, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        raise RuntimeError("capture only")


def recorded_key(alert: str) -> str:
    cap = Capture()
    SOCTriage(client=cap, retriever=FakeRetriever()).triage_with_context(alert)
    return prompt_hash(cap.kwargs["model"], cap.kwargs["messages"])


def harness_case(case_id: str, alert: str) -> HarnessCase:
    return HarnessCase(case_id=case_id, category="brute_force", group="standard", label=case_id, alert=alert)


def make(tmp_path, reply=REPLY, **cfg):
    rec = Recording(case_id="FAKE-001", response_text=reply, input_tokens=900, output_tokens=150,
                    recorded_at="2026-10-09T04:36:30Z")
    cases = [harness_case("FAKE-001", RECORDED), harness_case("FAKE-OOC", OFF_TOPIC),
             harness_case("FAKE-UNREC", UNRECORDED)]
    client = CachedClient({recorded_key(RECORDED): rec}, cases)
    config = DemoConfig(state_path=str(tmp_path / "b.json"), **cfg)
    return TestClient(create_app(config, lambda budget: (SOCTriage(client=client, retriever=FakeRetriever()), client)))


def test_prompt_hash_is_the_harness_cassette_key():
    for model, content in (("claude-sonnet-4-5", "alert text"), ("m", "unicode: café → ü"),
                           ("claude-sonnet-4-5", "")):
        messages = [{"role": "user", "content": content}]
        assert prompt_hash(model, messages) == harness_prompt_hash(model, messages)


def test_committed_cassettes_and_cases_load():
    recordings, cases = load_recordings(CASSETTE_DIR), load_cases(CASES_DIR)
    assert len(recordings) == len(list(CASSETTE_DIR.glob("*.json"))), "two cassettes share a prompt hash"
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids)) >= 100
    assert {r.case_id for r in recordings.values()} <= set(ids)
    assert any(c.alert.endswith("\n") for c in cases), "alerts must stay verbatim: the hash covers every byte"


def test_cached_client_answers_only_recorded_prompts():
    messages = [{"role": "user", "content": "p"}]
    rec = Recording("C-1", "text", 3, 4, "")
    client = CachedClient({prompt_hash("m", messages): rec}, [])
    client.begin()
    assert client.outcome() == (False, None)
    resp = client.messages.create(model="m", max_tokens=1, messages=messages)
    assert resp.content[0].text == "text" and resp.usage.output_tokens == 4
    assert client.outcome() == (True, rec)
    client.begin()
    with pytest.raises(NotRecorded):
        client.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "other"}])
    assert client.outcome() == (True, None)


def test_recorded_alert_replays_through_the_full_pipeline(tmp_path):
    r = make(tmp_path).post("/triage", json={"alert": RECORDED})
    assert r.status_code == 200
    assert r.headers["x-demo-mode"] == "cached" and r.headers["x-demo-replay-case"] == "FAKE-001"
    assert r.headers["x-demo-recorded-at"] == "2026-10-09T04:36:30Z"
    body = r.json()
    assert body["case_id"].startswith("SOC-") and body["guardrail_triggered"] is False
    assert body["triage"]["severity"] == "high" and body["triage"]["mitre_techniques"] == ["T1110"]
    assert body["observables"]["ipv4"] == ["198.51.100.44"]


def test_replayed_output_still_goes_through_schema_validation(tmp_path):
    r = make(tmp_path, reply="Sure, here is my analysis of the alert.").post("/triage", json={"alert": RECORDED})
    assert r.status_code == 200 and r.headers["x-demo-replay-case"] == "FAKE-001"
    body = r.json()
    assert body["guardrail_triggered"] is True and body["triage"]["escalate"] is True  # stage 5 fail-toward-review


def test_unrecorded_alert_is_not_answered(tmp_path):
    r = make(tmp_path).post("/triage", json={"alert": UNRECORDED})
    assert r.status_code == 404
    body = r.json()
    assert body["status"] == "not_recorded" and "/samples" in body["message"]
    assert body["retrieval"] == {"avg_score": 0.52, "chunks": [{"source": "log_analysis_linux.md", "score": 0.52}]}
    assert body["observables"]["ipv4"] == ["198.51.100.45"]  # stage 1 ran live and is shown, not just retrieval
    assert "x-demo-replay-case" not in r.headers


def test_editing_a_recorded_alert_breaks_the_match(tmp_path):
    assert make(tmp_path).post("/triage", json={"alert": RECORDED.rstrip("\n")}).status_code == 404


def test_out_of_corpus_alert_is_refused_without_a_model_call(tmp_path):
    r = make(tmp_path).post("/triage", json={"alert": OFF_TOPIC})
    assert r.status_code == 200 and "x-demo-replay-case" not in r.headers
    body = r.json()
    assert body["guardrail_triggered"] is True and body["uncertainty_mode"] == "out_of_scope"
    assert body["evidence"]["chunks_retrieved"] == [] and body["triage"]["severity"] == "informational"


def test_samples_list_only_cases_verified_on_this_machine(tmp_path):
    c = make(tmp_path)
    assert c.get("/healthz").json()["recordings"] == "loading"
    samples = {s["id"]: s for s in c.get("/samples").json()}
    assert {k: s["kind"] for k, s in samples.items()} == {"FAKE-001": "replay", "FAKE-OOC": "refusal"}
    assert samples["FAKE-001"]["alert"] == RECORDED
    health = c.get("/healthz").json()
    assert health["mode"] == "cached" and health["demo_mode"] is True
    assert health["recordings"] == {"replay": 1, "refusal": 1, "unservable": 1}


def test_token_cap_does_not_gate_cached_mode(tmp_path):
    c = make(tmp_path, daily_token_cap=0)
    assert c.post("/triage", json={"alert": RECORDED}).status_code == 200
    assert c.get("/budget").json() == {"mode": "cached", "daily_token_cap": None, "tokens_used": 0,
                                       "tokens_remaining": None, "resets_at": None}


def test_rate_limit_still_applies(tmp_path):
    c = make(tmp_path, per_ip_per_minute=1)
    assert c.post("/triage", json={"alert": OFF_TOPIC}).status_code == 200
    r = c.post("/triage", json={"alert": OFF_TOPIC})
    assert r.status_code == 429 and r.json()["status"] == "rate_limited"


def test_default_cached_app_never_builds_a_model_client(tmp_path, monkeypatch):
    """The shipped path: real cassettes and cases, a key in the environment, and still no client."""
    class NoClient:
        def __init__(self, *a, **k):
            raise AssertionError("cached mode built an Anthropic client")

    class OfflineRetriever(FakeRetriever):
        def index(self, chunks):
            self.chunks = chunks

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setattr(triage_mod, "Anthropic", NoClient)
    monkeypatch.setattr(triage_mod, "ThreatIntelRetriever", OfflineRetriever)
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", NoClient)
    c = TestClient(create_app(DemoConfig(state_path=str(tmp_path / "b.json"), cassette_dir=str(CASSETTE_DIR),
                                         cases_dir=str(CASES_DIR))))
    assert c.post("/triage", json={"alert": UNRECORDED}).status_code == 404
    assert c.post("/triage", json={"alert": OFF_TOPIC}).status_code == 200


def test_missing_recordings_is_a_clear_503(tmp_path):
    cfg = DemoConfig(state_path=str(tmp_path / "b.json"), cassette_dir=str(tmp_path / "none"),
                     cases_dir=str(tmp_path / "none"))
    r = TestClient(create_app(cfg)).post("/triage", json={"alert": "x y"})
    assert r.status_code == 503 and r.json()["status"] == "not_configured"
    assert "recorded" in r.json()["message"]


def test_mode_is_validated(monkeypatch):
    with pytest.raises(ValueError):
        DemoConfig(mode="lve")
    monkeypatch.setenv("DEMO_MODE", " Live ")
    assert DemoConfig.from_env().mode == "live"
    monkeypatch.delenv("DEMO_MODE")
    assert DemoConfig.from_env().mode == "cached"


def test_live_mode_samples_are_the_harness_cases(tmp_path):
    cfg = DemoConfig(mode="live", state_path=str(tmp_path / "b.json"), cases_dir=str(CASES_DIR))
    samples = TestClient(create_app(cfg, lambda budget: (None, None))).get("/samples").json()
    assert len(samples) == len(load_cases(CASES_DIR)) and {s["kind"] for s in samples} == {"live"}


def test_alert_body_never_appears_in_any_log(tmp_path, caplog):
    """Covers startup verification and the replay, not-recorded and refusal paths."""
    c = make(tmp_path)
    with caplog.at_level(logging.DEBUG):
        for name in ("soc_demo", "triage_engine.triage"):
            logging.getLogger(name).setLevel(logging.DEBUG)
        c.get("/samples")
        for alert in (RECORDED, UNRECORDED, OFF_TOPIC):
            c.post("/triage", json={"alert": alert})
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "event=recordings_checked" in text and "event=not_recorded" in text and "replay=FAKE-001" in text
    for needle in CANARIES:
        assert needle not in text, needle
