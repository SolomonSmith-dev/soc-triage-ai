"""FastAPI application factory for SOC Triage Copilot API."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from soc_api.config import settings
from soc_api.routers import alerts, cases, corpus, eval, health, retrieval, triage
from soc_api.services.engine_loader import get_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly load the engine in non-test environments. In tests, leave it lazy
    # so test runs that don't hit triage endpoints don't pay the 30s load.
    if settings.environment != "test":
        try:
            get_engine()
        except RuntimeError as e:
            # Most common cause: ANTHROPIC_API_KEY missing. Don't crash startup;
            # let endpoint hits surface the error so the API is still pingable.
            logger.warning("Engine not preloaded at startup: %s", e)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="SOC Triage Copilot API",
        version="0.2.0-dev",
        description="Backend API for the SOC Triage Copilot platform.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in (health.router, alerts.router, triage.router, cases.router, eval.router, retrieval.router, corpus.router):
        app.include_router(router)

    return app


app = create_app()
