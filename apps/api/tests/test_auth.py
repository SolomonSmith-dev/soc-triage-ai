"""Integration tests for API key authentication on POST /alerts."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from soc_api.models.orm import ApiKey
from soc_api.security import generate_api_key

_ALERT_PAYLOAD = {
    "raw_text": "Suspicious login from 10.0.0.1",
    "source": "test-sensor",
    "external_id": None,
}


@pytest.fixture
async def api_key(session: AsyncSession) -> str:
    """Insert an active ApiKey row; return the plaintext key."""
    plaintext, hashed = generate_api_key()
    session.add(ApiKey(key_hash=hashed, label="test-key", scopes=["ingest"]))
    await session.commit()
    return plaintext


async def test_ingest_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/alerts", json=_ALERT_PAYLOAD)
    assert resp.status_code == 401


async def test_ingest_with_valid_key(client: AsyncClient, api_key: str) -> None:
    resp = await client.post(
        "/alerts",
        json=_ALERT_PAYLOAD,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "alert_id" in body
    assert "received_at" in body


async def test_ingest_with_invalid_key(client: AsyncClient) -> None:
    resp = await client.post(
        "/alerts",
        json=_ALERT_PAYLOAD,
        headers={"Authorization": "Bearer not-a-real-key"},
    )
    assert resp.status_code == 401
