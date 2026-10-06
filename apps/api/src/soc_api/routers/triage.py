"""POST /triage/jobs — synchronously run the v1 engine and persist a case."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.db import get_session
from soc_api.services import triage_service
from soc_contracts import TriageJobRequest, TriageJobResponse, TriageJobStatus

router = APIRouter(prefix="/triage", tags=["triage"])


# TODO(P2): add API key auth dep
# TODO(P3): swap synchronous run for Celery dispatch; this endpoint becomes a
# real job-queue + GET /triage/jobs/{job_id} for polling.
@router.post("/jobs", response_model=TriageJobResponse, status_code=status.HTTP_200_OK)
async def submit_triage_job(
    body: TriageJobRequest,
    session: AsyncSession = Depends(get_session),
) -> TriageJobResponse:
    submitted_at = datetime.now(timezone.utc)
    try:
        case = await triage_service.triage_alert(session, body.alert_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return TriageJobResponse(
        job_id=str(uuid.uuid4()),
        status=TriageJobStatus.completed,
        case_id=case.id,
        submitted_at=submitted_at,
    )
