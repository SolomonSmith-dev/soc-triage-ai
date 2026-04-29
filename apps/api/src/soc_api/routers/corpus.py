"""GET /corpus/versions — list registered corpus versions."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.db import get_session
from soc_api.models.orm import CorpusVersion
from soc_contracts import CorpusVersion as CorpusVersionContract

router = APIRouter(prefix="/corpus", tags=["corpus"])


@router.get("/versions", response_model=list[CorpusVersionContract])
async def list_corpus_versions(
    session: AsyncSession = Depends(get_session),
) -> list[CorpusVersionContract]:
    result = await session.execute(
        select(CorpusVersion).order_by(CorpusVersion.created_at.desc())
    )
    versions = result.scalars().all()
    return [
        CorpusVersionContract(
            id=v.id,
            label=v.label,
            embedding_model=v.embedding_model,
            chunk_count=v.chunk_count,
            is_active=v.is_active,
            created_at=v.created_at,
        )
        for v in versions
    ]
