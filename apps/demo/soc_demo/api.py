"""Demo API: POST /triage returns the CaseEnvelope contract, guarded for public use."""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from soc_contracts import CaseEnvelope
from soc_demo.guard import (
    DailyBudget, DemoConfig, IPRateLimiter, MeteredClient, client_ip, install_redaction, ip_tag,
)

logger = logging.getLogger("soc_demo")

BUDGET_MESSAGE = (
    "Demo budget reached for today. The public demo caps daily model usage to keep it free. "
    "It resets at 00:00 UTC. You can still run it yourself: see the README."
)


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert: str = Field(min_length=1)


def _real_engine(budget: DailyBudget):
    """Build the engine with a metered client. The key comes only from the environment."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None, None
    from anthropic import Anthropic
    from triage_engine.triage import SOCTriage
    metered = MeteredClient(Anthropic(api_key=key), budget)
    return SOCTriage(client=metered), metered


def create_app(config: DemoConfig | None = None, engine_factory=None, clock=time.time, warm: bool = False) -> FastAPI:
    """`engine_factory(budget) -> (engine, metered_client)` is injectable for tests."""
    cfg = config or DemoConfig.from_env()
    install_redaction()
    budget = DailyBudget(cfg.daily_token_cap, cfg.state_path, clock)
    limiter = IPRateLimiter(cfg.per_ip_per_minute, cfg.per_ip_per_day, clock)
    factory = engine_factory or _real_engine
    state: dict = {"engine": None, "metered": None, "loaded": False}

    lock = threading.Lock()

    def ensure_engine():
        with lock:
            if not state["loaded"]:
                state["engine"], state["metered"] = factory(budget)
                state["loaded"] = True

    @asynccontextmanager
    async def lifespan(_app):
        if warm:  # load embeddings in the background so the first visitor does not wait
            threading.Thread(target=ensure_engine, daemon=True).start()
        yield

    app = FastAPI(title="SOC Triage AI (public demo)", version="0.1.0", lifespan=lifespan)

    def log_event(event: str, status: int, **counts) -> None:
        # counts only: never the alert, never the raw address
        logger.info("event=%s status=%s %s", event, status, " ".join(f"{k}={v}" for k, v in counts.items()))

    def refuse(status_code: int, status: str, message: str, headers: dict | None = None, **extra):
        return JSONResponse({"status": status, "message": message, **extra}, status_code=status_code, headers=headers)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "demo_mode": True}

    @app.get("/budget")
    def get_budget():
        return budget.snapshot()

    @app.post("/triage", response_model=CaseEnvelope)
    async def triage(body: TriageRequest, request: Request):
        ip = client_ip(request.headers.get("x-forwarded-for"),
                       request.client.host if request.client else None, cfg.trusted_proxy_hops)
        tag = ip_tag(ip, cfg.ip_salt)
        n = len(body.alert)

        if n > cfg.max_alert_chars:
            log_event("alert_too_long", 413, alert_chars=n, client=tag)
            return refuse(413, "alert_too_long", f"Alert is {n} characters; the demo accepts up to {cfg.max_alert_chars}.")

        if budget.exhausted:
            log_event("budget_reached", 429, alert_chars=n, client=tag)
            return refuse(429, "demo_budget_reached", BUDGET_MESSAGE, resets_at=budget.resets_at())

        allowed, retry = limiter.check(ip)
        if not allowed:
            log_event("rate_limited", 429, alert_chars=n, client=tag, retry_after=retry)
            return refuse(429, "rate_limited", f"Too many requests from your address. Try again in {retry} seconds.",
                          headers={"Retry-After": str(retry)}, retry_after_seconds=retry)

        await asyncio.to_thread(ensure_engine)
        engine, metered = state["engine"], state["metered"]
        if engine is None:
            log_event("not_configured", 503, alert_chars=n, client=tag)
            return refuse(503, "not_configured", "The demo has no model key configured.")

        def run():
            from triage_engine.case_package import build_case_package
            from triage_engine.extractors import extract_observables
            if metered:
                metered.take_request_tokens()
            result, hits, guard = engine.triage_with_context(body.alert)
            tokens = metered.take_request_tokens() if metered else 0
            pkg = build_case_package(alert_raw=body.alert, observables=extract_observables(body.alert),
                                     triage_result=result, retrieval_hits=hits, guardrail_triggered=guard)
            return pkg, guard, tokens

        pkg, guard, tokens = await asyncio.to_thread(run)
        log_event("triaged", 200, alert_chars=n, chunks=len(pkg["evidence"]["chunks_retrieved"]),
                  guardrail=guard, tokens=tokens, client=tag)
        return pkg

    return app


def app_factory() -> FastAPI:  # uvicorn --factory soc_demo.api:app_factory
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return create_app(warm=True)
