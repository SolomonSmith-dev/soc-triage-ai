"""Section technique IDs in the prompt context, and the analysis the model card cites."""
import json
from pathlib import Path
from types import SimpleNamespace

from triage_engine.rag.corpus import section_technique_ids
from triage_engine.triage import SOCTriage

CH = [
    {"id": "a_1", "source": "a.md", "text": "Intro paragraph with no technique at all, long enough to be a chunk of its own."},
    {"id": "a_2", "source": "a.md", "text": "## T1110 Brute Force - T1110.001 Password Guessing, T1110.003 Password Spraying"},
    {"id": "a_3", "source": "a.md", "text": "Indicators include high failed authentication counts from a single source address."},
    {"id": "a_4", "source": "a.md", "text": "## T1021 Remote Services - T1021.001 RDP lateral movement from non-admin hosts"},
    {"id": "a_5", "source": "a.md", "text": "## Triage Guidance Contain the account first, then review the authentication chain."},
    {"id": "b_1", "source": "b.md", "text": "Ransomware overview paragraph that names no technique and sits before the mapping list."},
    {"id": "b_2", "source": "b.md", "text": "## MITRE Mapping T1486 Data Encrypted for Impact, T1490 Inhibit System Recovery"},
    {"id": "c_1", "source": "c.md", "text": "A document with no technique IDs anywhere in it, only prose about logging practice."},
]


def test_header_sets_ids_and_following_chunks_inherit_until_next_header():
    m = section_technique_ids(CH)
    assert m["a_1"] == []
    assert m["a_2"] == ["T1110", "T1110.001", "T1110.003"]
    assert m["a_3"] == ["T1110", "T1110.001", "T1110.003"]      # inherited
    assert m["a_4"] == ["T1021", "T1021.001"]                   # new header resets, no T1110 leak
    assert m["a_5"] == []                                       # a header with no IDs clears the section


def test_document_mapping_is_the_fallback_and_never_crosses_documents():
    m = section_technique_ids(CH)
    assert m["b_1"] == ["T1486", "T1490"]
    assert m["b_2"] == ["T1486", "T1490"]
    assert m["c_1"] == [] and "T1486" not in m["a_1"]


class Capture:
    def __init__(self):
        self.messages, self.prompt = self, None

    def create(self, **kw):
        self.prompt = kw["messages"][0]["content"]
        return SimpleNamespace(content=[SimpleNamespace(text=json.dumps({
            "severity": "high", "confidence": "high", "mitre_techniques": ["T1110"], "summary": "s",
            "recommended_actions": ["a"], "escalate": True, "reasoning": "r"}))],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1))


class Retriever:
    chunks = CH

    def __init__(self, ids):
        self.ids = ids

    def retrieve(self, query, top_k=4, min_score=0.20):
        by = {c["id"]: c for c in CH}
        return [(by[i], 0.5) for i in self.ids]


def test_prompt_carries_the_section_note_only_where_the_id_is_missing_from_the_chunk():
    cap = Capture()
    SOCTriage(client=cap, retriever=Retriever(["a_3", "a_2"])).triage_with_context("x")
    assert cap.prompt.count("(Techniques named in this section:") == 1
    assert "(Techniques named in this section: T1110, T1110.001, T1110.003)" in cap.prompt   # a_3 only
    assert "T1021" not in cap.prompt                                                         # no leakage


def test_no_note_when_the_retriever_exposes_no_chunks():
    class Bare:
        def retrieve(self, query, top_k=4, min_score=0.20):
            return [(CH[2], 0.5)]

    cap = Capture()
    SOCTriage(client=cap, retriever=Bare()).triage_with_context("x")
    assert "Techniques named in this section" not in cap.prompt


def test_model_card_quotes_the_technique_coverage_snapshot():
    snap = json.loads(Path("tests/harness/analysis/technique_coverage_2026-10-09.json").read_text())
    card = Path("model_card.md").read_text()
    n = snap["cases_expecting_techniques"]
    vb, va = snap["visible_before"], snap["visible_after"]
    w, nw = snap["technique_match_when_visible_before"], snap["technique_match_when_not_visible_before"]
    for needle in (f"{n - vb} of {n}", f"{w[0]} of {w[1]}", f"{nw[0]} of {nw[1]}", f"{va} of {n}",
                   f"{snap['chunks_with_ids_before']} of {snap['chunks_total']}", f"{snap['chunks_with_ids_after']}"):
        assert needle in card, needle
