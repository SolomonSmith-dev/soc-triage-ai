"""API-key auth on /triage/jobs and /cases (kanban t_614c27d9).

No database needed: unauthenticated requests must be rejected before any
session use, and the authenticated path is exercised by overriding the
key dependency and stubbing the services.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from soc_api import deps
from soc_api.db import get_session
from soc_api.main import app
from soc_api.services import case_service, triage_service


async def _fake_session():
    yield object()


@pytest.fixture
async def anon():
    app.dependency_overrides[get_session] = _fake_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def model_call(monkeypatch):
    mock = AsyncMock(side_effect=AssertionError("model call reached without auth"))
    monkeypatch.setattr(triage_service, "triage_alert", mock)
    return mock


async def test_triage_job_without_key_is_401_and_makes_no_model_call(anon, model_call):
    resp = await anon.post("/triage/jobs", json={"alert_id": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 401
    model_call.assert_not_called()


async def test_triage_job_with_bad_key_is_401(anon, model_call):
    resp = await anon.post(
        "/triage/jobs",
        json={"alert_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": "Bearer nope"},
    )
    assert resp.status_code == 401
    model_call.assert_not_called()


async def test_list_cases_without_key_is_401(anon, monkeypatch):
    monkeypatch.setattr(case_service, "list_recent_cases", AsyncMock(return_value=[]))
    assert (await anon.get("/cases")).status_code == 401


async def test_get_case_without_key_is_401(anon, monkeypatch):
    monkeypatch.setattr(case_service, "get_case", AsyncMock(return_value=None))
    assert (await anon.get("/cases/abc")).status_code == 401


async def test_list_cases_with_key_passes_auth(anon, monkeypatch):
    app.dependency_overrides[deps.current_api_key] = lambda: object()
    monkeypatch.setattr(case_service, "list_recent_cases", AsyncMock(return_value=[]))
    resp = await anon.get("/cases")
    assert resp.status_code == 200
    assert resp.json() == []
