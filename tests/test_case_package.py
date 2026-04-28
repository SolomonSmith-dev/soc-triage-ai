"""Tests for case package envelope builder."""
import re
from case_package import build_case_package, derive_uncertainty_mode


def _triage_stub(severity="high", confidence="high"):
    return {
        "severity": severity,
        "confidence": confidence,
        "mitre_techniques": ["T1078"],
        "summary": "stub",
        "recommended_actions": ["a"],
        "escalate": True,
        "reasoning": "r",
        "sources": ["insider_threat.md"],
        "retrieval_score": 0.5,
    }


def test_case_id_format():
    pkg = build_case_package("alert", {"ipv4": []}, _triage_stub(), [], False)
    assert re.match(r"^SOC-\d{8}-[a-f0-9]{4}$", pkg["case_id"])


def test_top_level_keys_present():
    pkg = build_case_package("alert", {"ipv4": []}, _triage_stub(), [], False)
    expected_keys = {
        "case_id", "timestamp", "alert_raw", "observables", "triage",
        "evidence", "uncertainty_mode", "guardrail_triggered",
        "analyst_overrides", "version",
    }
    assert expected_keys.issubset(pkg.keys())


def test_version_block_fields():
    pkg = build_case_package("alert", {"ipv4": []}, _triage_stub(), [], False)
    v = pkg["version"]
    for key in ["model", "embeddings", "corpus_chunks",
                "prompt_version", "top_k", "min_similarity"]:
        assert key in v


def test_evidence_block_aggregates_chunks():
    hits = [
        ({"id": "ins_1", "source": "insider_threat.md", "text": "x"}, 0.6),
        ({"id": "ins_2", "source": "insider_threat.md", "text": "y"}, 0.4),
    ]
    pkg = build_case_package("alert", {"ipv4": []}, _triage_stub(), hits, False)
    e = pkg["evidence"]
    assert len(e["chunks_retrieved"]) == 2
    assert e["sources_cited"] == ["insider_threat.md"]
    assert abs(e["avg_retrieval_score"] - 0.5) < 1e-6


def test_evidence_marks_cited_chunks():
    triage = _triage_stub()
    triage["sources"] = ["insider_threat.md"]
    hits = [
        ({"id": "ins_1", "source": "insider_threat.md", "text": "x"}, 0.5),
        ({"id": "phi_1", "source": "phishing.md", "text": "y"}, 0.4),
    ]
    pkg = build_case_package("alert", {}, triage, hits, False)
    chunks = pkg["evidence"]["chunks_retrieved"]
    cited_map = {c["chunk_id"]: c["cited"] for c in chunks}
    assert cited_map["ins_1"] is True
    assert cited_map["phi_1"] is False


def test_uncertainty_actionable_default():
    t = _triage_stub(severity="high", confidence="high")
    assert derive_uncertainty_mode(t, 0.5, False) == "actionable"


def test_uncertainty_out_of_scope():
    t = _triage_stub(severity="informational", confidence="low")
    assert derive_uncertainty_mode(t, 0.0, True) == "out_of_scope"


def test_uncertainty_insufficient_evidence():
    t = _triage_stub(severity="high", confidence="high")
    assert derive_uncertainty_mode(t, 0.10, False) == "insufficient_evidence"


def test_uncertainty_needs_more_context_low_conf():
    t = _triage_stub(severity="medium", confidence="low")
    assert derive_uncertainty_mode(t, 0.50, False) == "needs_more_context"


def test_uncertainty_needs_more_context_medium_conf_low_score():
    t = _triage_stub(severity="medium", confidence="medium")
    assert derive_uncertainty_mode(t, 0.30, False) == "needs_more_context"


def test_uncertainty_priority_out_of_scope_beats_insufficient():
    t = _triage_stub(severity="informational", confidence="low")
    assert derive_uncertainty_mode(t, 0.10, True) == "out_of_scope"
