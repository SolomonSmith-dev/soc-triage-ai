"""Retrieval debugger contracts."""
from pydantic import BaseModel, ConfigDict


class RetrievalChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    source: str
    score: float
    text: str
    above_threshold: bool


class RetrievalDebugResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    top_k: int
    min_similarity: float
    chunks: list[RetrievalChunk]
