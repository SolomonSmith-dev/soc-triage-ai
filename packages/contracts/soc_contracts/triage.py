"""Triage job contracts."""
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TriageJobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TriageJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert_id: UUID


class TriageJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: UUID | str
    status: TriageJobStatus
    case_id: str | None = None
    submitted_at: datetime
