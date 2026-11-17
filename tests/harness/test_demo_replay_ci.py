"""CI gate for the public demo's cached mode. Offline and deterministic: no API key, no LLM call.

Runs every harness case through the demo API with the real retriever and the committed cassettes.
Every cassette must replay, and every case the recorded run refused at retrieval must still refuse,
or the demo would offer alerts that answer "not recorded". Needs the embedding model, so it runs in
the harness replay job, not with the offline unit tests.
"""
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from soc_demo.api import create_app
from soc_demo.guard import DemoConfig
from soc_demo.replay import CachedClient, load_cases, load_recordings
from tests.harness.loader import CASES_DIR
from tests.harness.recorder import CASSETTE_DIR
from tests.harness.runner import build_retriever

RECORDED_RUN = json.loads((Path(__file__).parent / "harness_results.json").read_text())["results"]


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    try:
        retriever = build_retriever()
    except Exception as e:  # embedding weights unavailable (offline sandbox)
        if os.getenv("HARNESS_REQUIRE_RETRIEVER") == "1":
            raise
        pytest.skip(f"embedding model unavailable: {type(e).__name__}")
    from triage_engine.triage import SOCTriage
    recordings, cases = load_recordings(CASSETTE_DIR), load_cases(CASES_DIR)

    def factory(_budget):
        client = CachedClient(recordings, cases)
        return SOCTriage(client=client, retriever=retriever), client

    cfg = DemoConfig(state_path=str(tmp_path_factory.mktemp("demo") / "budget.json"),
                     per_ip_per_minute=10_000, per_ip_per_day=10_000)
    c = TestClient(create_app(cfg, factory))
    return c, {s["id"]: s for s in c.get("/samples").json()}, recordings


def test_every_cassette_replays_and_recorded_refusals_still_refuse(demo):
    c, samples, recordings = demo
    replay = {i for i, s in samples.items() if s["kind"] == "replay"}
    refusal = {i for i, s in samples.items() if s["kind"] == "refusal"}
    assert replay == {r.case_id for r in recordings.values()}
    assert refusal == {r["id"] for r in RECORDED_RUN if r.get("refused")}
    health = c.get("/healthz").json()["recordings"]
    print(json.dumps(health))
    assert health["replay"] == len(recordings)


def test_each_sample_gets_its_recorded_outcome(demo):
    c, samples, _ = demo
    for case_id, s in samples.items():
        r = c.post("/triage", json={"alert": s["alert"]})
        assert r.status_code == 200, (case_id, r.status_code, r.text[:200])
        body = r.json()
        if s["kind"] == "replay":
            assert r.headers.get("x-demo-replay-case") == case_id, case_id
        else:
            assert "x-demo-replay-case" not in r.headers, case_id
            assert body["guardrail_triggered"] and not body["evidence"]["chunks_retrieved"], case_id


def test_unrecorded_in_corpus_alert_is_not_answered(demo):
    c, _, _ = demo
    r = c.post("/triage", json={"alert": "zq-canary-7310: 40 failed SSH logins from 203.0.113.61 against srv-bastion-07, "
                                          "followed by one success and a new sudoers entry"})
    assert r.status_code == 404 and r.json()["status"] == "not_recorded"
    assert r.json()["retrieval"]["chunks"], "retrieval should still run and report its matches"
