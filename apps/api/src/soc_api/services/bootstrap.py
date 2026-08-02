"""First-boot bootstrap: ensure default corpus_versions + tenant exist."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.models.orm import CorpusVersion

# Hardcoded for v2 single-tenant. v3 makes this dynamic.
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
BOOTSTRAP_CORPUS_LABEL = "v1-markdown-only"


async def ensure_default_corpus(session: AsyncSession) -> uuid.UUID:
    """Create or return the v1 markdown corpus version row."""
    result = await session.execute(
        select(CorpusVersion).where(CorpusVersion.label == BOOTSTRAP_CORPUS_LABEL)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing.id

    cv = CorpusVersion(
        label=BOOTSTRAP_CORPUS_LABEL,
        embedding_model="all-MiniLM-L6-v2",
        chunk_count=109,
        is_active=True,
        manifest={"sources": ["data/threat_intel/*.md"], "bootstrapped": True},
    )
    session.add(cv)
    await session.commit()
    await session.refresh(cv)
    return cv.id
