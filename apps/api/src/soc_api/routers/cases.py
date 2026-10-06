"""GET /cases/{id}, GET /cases — case retrieval endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.db import get_session
from soc_api.services import case_service
from soc_contracts import CaseEnvelope, CaseSummary

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=list[CaseSummary])
async def list_cases(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[CaseSummary]:
    cases = await case_service.list_recent_cases(session, limit=limit)
    return [
        CaseSummary(
            case_id=c.id,
            severity=c.severity,
            escalate=c.escalate,
            uncertainty_mode=c.uncertainty_mode,
            summary=c.envelope.get("triage", {}).get("summary", ""),
            created_at=c.created_at,
            retrieval_score=float(c.retrieval_score) if c.retrieval_score is not None else None,
        )
        for c in cases
    ]


@router.get("/{case_id}", response_model=CaseEnvelope)
async def get_case_detail(
    case_id: str,
    session: AsyncSession = Depends(get_session),
) -> CaseEnvelope:
    case = await case_service.get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"case {case_id} not found")
    return CaseEnvelope.model_validate(case.envelope)
