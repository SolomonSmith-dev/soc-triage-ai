"""Shared fixtures for API integration tests.

Test DB: soc_triage_test (must exist; created once via
  docker exec soc-triage-ai-postgres-1 psql -U soc -d postgres -c "CREATE DATABASE soc_triage_test;")

Tables are created at session start and dropped at session end.
Each test gets a clean DB state via teardown delete.
"""
from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from soc_api.db import Base, get_session
from soc_api.main import app
import soc_api.models.orm  # noqa: F401 — ensures all models register on Base

TEST_DB_URL = "postgresql+asyncpg://soc:soc@localhost:5432/soc_triage_test"


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(test_engine):
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(session: AsyncSession):
    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
