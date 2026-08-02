"""Health and readiness endpoints."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict:
    # Phase 2+ will add real readiness checks (DB, Redis, model loaded)
    return {"status": "ready"}
