"""Stage 5 grounding and the fail-safe response. No network, no model weights."""
import json
from types import SimpleNamespace

import pytest

from triage_engine.triage import SOCTriage

CTX = "## T1566 Phishing. T1566.001 Spearphishing Attachment, T1566.002 Spearphishing Link. T1204 User Execution."


class Client:
    def __init__(self, reply=None, exc=None, empty=False):
        self.messages, self.reply, self.exc, self.empty = self, reply, exc, empty

    def create(self, **kw):
        if self.exc:
            raise self.exc
        content = [] if self.empty else [SimpleNamespace(text=self.reply)]
        return SimpleNamespace(content=content, usage=SimpleNamespace(input_tokens=1, output_tokens=1))


class Retriever:
    def __init__(self, hits=True):
        self.hits = hits

    def retrieve(self, query, top_k=4, min_score=0.20):
        return [({"id": "c", "source": "p.md", "text": CTX}, 0.5)] if self.hits else []


def reply(sev="high", techs=("T1566",), conf="high", esc=True):
    return json.dumps({"severity": sev, "confidence": conf, "mitre_techniques": list(techs), "summary": "s",
                       "recommended_actions": ["a"], "escalate": esc, "reasoning": "r"})


def run(client, hits=True):
    return SOCTriage(client=client, retriever=Retriever(hits)).triage_with_context("some alert")


def test_ungrounded_ids_are_dropped_and_grounded_ones_kept():
    r, _, g = run(Client(reply(techs=("T1566.002", "T1136", "T1218.005", "T1204"))))
    assert r["mitre_techniques"] == ["T1566.002", "T1204"] and not g
    assert r["severity"] == "high" and r["escalate"] is True and r["confidence"] == "high"


def test_parent_in_context_grounds_a_subtechnique_but_not_the_reverse_for_other_families():
    r, _, _ = run(Client(reply(techs=("T1204.002", "T1566.003", "T1136.001"))))
    assert r["mitre_techniques"] == ["T1204.002", "T1566.003"]


def test_no_grounded_technique_caps_confidence_but_keeps_severity_and_escalation():
    r, _, _ = run(Client(reply(sev="critical", techs=("T1052", "T1074"), conf="high")))
    assert r["mitre_techniques"] == [] and r["confidence"] == "low"
    assert r["severity"] == "critical" and r["escalate"] is True


def test_empty_list_on_nontrivial_severity_caps_confidence_informational_untouched():
    r, _, _ = run(Client(reply(sev="high", techs=(), conf="high")))
    assert r["confidence"] == "low"
    r, _, _ = run(Client(reply(sev="informational", techs=(), conf="high", esc=False)))
    assert r["confidence"] == "high"


@pytest.mark.parametrize("client", [
    Client(reply="not json at all"),
    Client(empty=True),                      # the empty reply seen in the live run (IndexError)
    Client(exc=RuntimeError("api down")),
    Client(reply=json.dumps({"severity": "high"})),   # schema failure
])
def test_failed_model_call_fails_toward_review_not_silence(client):
    r, hits, guard = run(client)
    assert guard and hits
    assert r["escalate"] is True and r["severity"] == "medium" and r["confidence"] == "low"
    assert "Manual analyst review required" in r["recommended_actions"]


def test_retrieval_refusal_is_unchanged():
    r, hits, guard = run(Client(reply()), hits=False)
    assert guard and not hits
    assert r["severity"] == "informational" and r["escalate"] is False


def test_rescore_meta_only_from_a_live_run():
    from tests.harness.report import rescore_meta
    assert rescore_meta({"mode": "legacy-live-7-case"}, "abc", "now") is None
    m = rescore_meta({"mode": "live", "model": "m", "git_sha": "old"}, "new", "now")
    assert m["git_sha"] == "old" and m["rescored_git_sha"] == "new" and m["mode"] == "live"
