"""Synchronous triage orchestration.

Phase 1: blocks the request until the LLM call returns. Phase 3 swaps to Celery
without changing the public API contract.
"""
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.models.orm import Alert, Case, EvidenceLink, IntelChunk
from soc_api.services.bootstrap import DEFAULT_TENANT_ID, ensure_default_corpus
from soc_api.services.engine_loader import get_engine

logger = logging.getLogger(__name__)


async def triage_alert(session: AsyncSession, alert_id: UUID) -> Case:
    """Run the v1 engine against an alert, build + persist the case envelope."""
    from triage_engine.case_package import build_case_package
    from triage_engine.extractors import extract_observables

    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise ValueError(f"alert {alert_id} not found")

    corpus_version_id = await ensure_default_corpus(session)
    engine = get_engine()

    triage_result, hits, guardrail = await asyncio.to_thread(
        engine.triage_with_context, alert.raw_text
    )

    observables = extract_observables(alert.raw_text)
    pkg = build_case_package(
        alert_raw=alert.raw_text,
        observables=observables,
        triage_result=triage_result,
        retrieval_hits=hits,
        guardrail_triggered=guardrail,
    )

    case = Case(
        id=pkg["case_id"],
        alert_id=alert.id,
        envelope=pkg,
        uncertainty_mode=pkg["uncertainty_mode"],
        severity=pkg["triage"]["severity"],
        escalate=pkg["triage"]["escalate"],
        guardrail_triggered=guardrail,
        retrieval_score=pkg["evidence"]["avg_retrieval_score"],
        corpus_version_id=corpus_version_id,
        tenant_id=DEFAULT_TENANT_ID,
    )
    session.add(case)
    await session.flush()

    # evidence_links: chunk_id is the v1 string id (e.g., "insider_threat_3"),
    # NOT the intel_chunks.id UUID. In Phase 4, intel_chunks rows exist and we
    # can FK-link properly. For now, skip evidence_links inserts — the
    # envelope JSONB carries the same data, so analyst views are unaffected.
    # TODO(P4): populate evidence_links once intel_chunks are loaded into pgvector.

    await session.commit()
    await session.refresh(case)
    logger.info("triaged alert=%s -> case=%s severity=%s", alert.id, case.id, case.severity)
    return case
