"""Alert ingestion contracts."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AlertIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_text: str = Field(min_length=1)
    source: str = Field(default="manual", min_length=1)
    external_id: str | None = None


class AlertIngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert_id: UUID
    received_at: datetime
