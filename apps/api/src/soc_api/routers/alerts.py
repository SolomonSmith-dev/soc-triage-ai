"""POST /alerts — ingest a raw alert and extract observables."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.db import get_session
from soc_api.deps import current_api_key
from soc_api.models.orm import ApiKey
from soc_api.services import alert_service
from soc_contracts import AlertIngestRequest, AlertIngestResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", response_model=AlertIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_alert(
    body: AlertIngestRequest,
    session: AsyncSession = Depends(get_session),
    _key: ApiKey = Depends(current_api_key),
) -> AlertIngestResponse:
    alert = await alert_service.create_alert(
        session=session,
        raw_text=body.raw_text,
        source=body.source,
        external_id=body.external_id,
    )
    return AlertIngestResponse(alert_id=alert.id, received_at=alert.received_at)
