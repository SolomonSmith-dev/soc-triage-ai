"""Contract tests: validate v1 case envelope shape against Pydantic contract."""
from soc_contracts import CaseEnvelope, OverrideRequest


def test_case_envelope_round_trip_from_v1_builder():
    """A case envelope built by triage_engine.case_package validates against CaseEnvelope."""
    from triage_engine.case_package import build_case_package

    triage_result = {
        "severity": "high",
        "confidence": "high",
        "mitre_techniques": ["T1078"],
        "summary": "test summary",
        "recommended_actions": ["a1", "a2"],
        "escalate": True,
        "reasoning": "because",
        "sources": ["insider_threat.md"],
        "retrieval_score": 0.5,
    }
    hits = [
        ({"id": "ins_1", "source": "insider_threat.md", "text": "x"}, 0.6),
        ({"id": "ins_2", "source": "insider_threat.md", "text": "y"}, 0.4),
    ]
    pkg = build_case_package(
        alert_raw="test alert",
        observables={k: [] for k in [
            "ipv4", "email", "url", "domain", "md5", "sha1", "sha256",
            "registry_path", "process", "filename", "hostname", "username",
        ]},
        triage_result=triage_result,
        retrieval_hits=hits,
        guardrail_triggered=False,
    )

    envelope = CaseEnvelope.model_validate(pkg)
    assert envelope.case_id.startswith("SOC-")
    assert envelope.uncertainty_mode.value == "actionable"
    assert len(envelope.evidence.chunks_retrieved) == 2


def test_case_envelope_rejects_extra_fields():
    """Extra fields outside the schema are rejected."""
    import pytest
    from pydantic import ValidationError

    bad = {
        "case_id": "SOC-20260428-aaaa",
        "timestamp": "2026-04-28T00:00:00Z",
        "alert_raw": "x",
        "observables": {k: [] for k in [
            "ipv4", "email", "url", "domain", "md5", "sha1", "sha256",
            "registry_path", "process", "filename", "hostname", "username",
        ]},
        "triage": {
            "severity": "low", "confidence": "low",
            "mitre_techniques": [], "summary": "x",
            "recommended_actions": [], "escalate": False, "reasoning": "x",
        },
        "evidence": {
            "chunks_retrieved": [], "avg_retrieval_score": 0.0, "sources_cited": [],
        },
        "uncertainty_mode": "out_of_scope",
        "guardrail_triggered": True,
        "analyst_overrides": [],
        "version": {
            "model": "x", "embeddings": "x", "corpus_chunks": 1,
            "prompt_version": "x", "top_k": 1, "min_similarity": 0.0,
        },
        "extra_garbage": "should be rejected",
    }
    with pytest.raises(ValidationError):
        CaseEnvelope.model_validate(bad)


def test_override_request_field_whitelist():
    """OverrideRequest.field is constrained to the whitelist."""
    import pytest
    from pydantic import ValidationError

    OverrideRequest(field="severity", new_value="high", rationale="r")
    OverrideRequest(field="escalate", new_value=True, rationale="r")
    OverrideRequest(field="mitre_techniques", new_value=["T1078"], rationale="r")
    OverrideRequest(field="notes", new_value="some text", rationale="r")
    with pytest.raises(ValidationError):
        OverrideRequest(field="not_a_field", new_value="x", rationale="r")
