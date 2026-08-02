"""Alert ingestion service: persists alert rows + extracts observables."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.models.orm import Alert, Observable
from soc_api.services.bootstrap import DEFAULT_TENANT_ID


async def create_alert(
    session: AsyncSession,
    raw_text: str,
    source: str = "manual",
    external_id: str | None = None,
) -> Alert:
    alert = Alert(
        raw_text=raw_text,
        source=source,
        external_id=external_id,
        tenant_id=DEFAULT_TENANT_ID,
    )
    session.add(alert)
    await session.flush()  # populate alert.id
    await _persist_observables(session, alert)
    await session.commit()
    await session.refresh(alert)
    return alert


async def _persist_observables(session: AsyncSession, alert: Alert) -> None:
    from triage_engine.extractors import extract_observables

    extracted = extract_observables(alert.raw_text)
    for kind, values in extracted.items():
        for value in values:
            session.add(Observable(alert_id=alert.id, kind=kind, value=value))
