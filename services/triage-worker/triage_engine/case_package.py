"""Case envelope builder + uncertainty mode derivation.

Wraps existing triage output, observables, and retrieval metadata into a
complete case package. Pure deterministic logic; no LLM calls.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# TriageResult in packages/contracts, which forbids extra keys. The model sometimes adds keys of its
# own (for example "mitre_attack_mapping"); the envelope carries only these. A unit test pins the two.
TRIAGE_FIELDS = (
    "severity", "confidence", "mitre_techniques", "summary", "recommended_actions", "escalate", "reasoning",
)

VERSION_META = {
    "model": "claude-sonnet-4-5",
    "embeddings": "all-MiniLM-L6-v2",
    "corpus_chunks": 109,
    "prompt_version": "1.0",
    "top_k": 4,
    "min_similarity": 0.20,
}


def _new_case_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"SOC-{today}-{uuid.uuid4().hex[:4]}"


def derive_uncertainty_mode(
    triage_result: Dict,
    avg_retrieval_score: float,
    guardrail_triggered: bool,
) -> str:
    """Classify case into one of four uncertainty modes. First match wins."""
    severity = triage_result.get("severity", "informational")
    confidence = triage_result.get("confidence", "low")

    if severity == "informational" and guardrail_triggered:
        return "out_of_scope"
    if avg_retrieval_score < 0.25 and severity != "informational":
        return "insufficient_evidence"
    if confidence == "low" or (
        confidence == "medium" and avg_retrieval_score < 0.35
    ):
        return "needs_more_context"
    return "actionable"


def build_case_package(
    alert_raw: str,
    observables: Dict,
    triage_result: Dict,
    retrieval_hits: List[Tuple[Dict, float]],
    guardrail_triggered: bool,
) -> Dict:
    """Assemble full case package. Pure function, no side effects."""
    if retrieval_hits:
        avg_score = sum(s for _, s in retrieval_hits) / len(retrieval_hits)
    else:
        avg_score = 0.0

    cited_sources = set(triage_result.get("sources", []))
    chunks = [
        {
            "chunk_id": chunk["id"],
            "source": chunk["source"],
            "score": round(score, 3),
            "text": chunk["text"],
            "cited": chunk["source"] in cited_sources,
        }
        for chunk, score in retrieval_hits
    ]

    sources_cited = sorted(cited_sources)

    uncertainty = derive_uncertainty_mode(
        triage_result, avg_score, guardrail_triggered
    )

    extra = set(triage_result) - set(TRIAGE_FIELDS) - {"sources", "retrieval_score"}
    if extra:
        logger.info("dropped %d model keys outside the TriageResult contract", len(extra))

    return {
        "case_id": _new_case_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "alert_raw": alert_raw,
        "observables": observables,
        "triage": {k: triage_result[k] for k in TRIAGE_FIELDS if k in triage_result},
        "evidence": {
            "chunks_retrieved": chunks,
            "avg_retrieval_score": round(avg_score, 3),
            "sources_cited": sources_cited,
        },
        "uncertainty_mode": uncertainty,
        "guardrail_triggered": guardrail_triggered,
        "analyst_overrides": [],
        "version": dict(VERSION_META),
    }
