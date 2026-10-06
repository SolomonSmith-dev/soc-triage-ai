"""GET /retrieval/debug — query the corpus, return top-k chunks. No LLM call."""
from fastapi import APIRouter, Query

from soc_api.services.engine_loader import get_engine
from soc_contracts import RetrievalChunk, RetrievalDebugResponse

router = APIRouter(prefix="/retrieval", tags=["retrieval"])

_DEFAULT_TOP_K = 4
_DEFAULT_MIN_SIM = 0.20


@router.get("/debug", response_model=RetrievalDebugResponse)
async def debug_retrieval(
    query: str = Query(min_length=1),
    top_k: int = Query(default=_DEFAULT_TOP_K, ge=1, le=20),
) -> RetrievalDebugResponse:
    engine = get_engine()
    hits = engine.retriever.retrieve(query, top_k=top_k)
    chunks = [
        RetrievalChunk(
            chunk_id=chunk["id"],
            source=chunk["source"],
            score=score,
            text=chunk["text"],
            above_threshold=score >= _DEFAULT_MIN_SIM,
        )
        for chunk, score in hits
    ]
    return RetrievalDebugResponse(
        query=query,
        top_k=top_k,
        min_similarity=_DEFAULT_MIN_SIM,
        chunks=chunks,
    )
