"""Case read service. Phase 1: fetch by id, list recent. Phase 2: apply overrides."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.models.orm import Case


async def get_case(session: AsyncSession, case_id: str) -> Case | None:
    result = await session.execute(select(Case).where(Case.id == case_id))
    return result.scalar_one_or_none()


async def list_recent_cases(session: AsyncSession, limit: int = 50) -> list[Case]:
    result = await session.execute(
        select(Case).order_by(Case.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
