"""Corpus version contracts."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CorpusVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    label: str
    embedding_model: str
    chunk_count: int
    is_active: bool
    created_at: datetime
