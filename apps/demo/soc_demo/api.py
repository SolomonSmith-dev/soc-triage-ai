"""Demo API: POST /triage returns the CaseEnvelope contract, guarded for public use.

DEMO_MODE picks how stage 4, the model call, is answered:
  cached (default)  replayed from the harness recordings: no key, no model call, no spend
  live              Claude via ANTHROPIC_API_KEY, metered against a daily token cap
Stages 1 to 3, 5 and 6 run for real in both modes.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from soc_contracts import CaseEnvelope
from soc_demo.guard import (
    DailyBudget, DemoConfig, IPRateLimiter, MeteredClient, client_ip, install_redaction, ip_tag,
)
from soc_demo.replay import CachedClient, check_recordings, load_cases, load_recordings

logger = logging.getLogger("soc_demo")

BUDGET_MESSAGE = (
    "Demo budget reached for today. The public demo caps daily model usage to keep it free. "
    "It resets at 00:00 UTC. You can still run it yourself: see the README."
)
NOT_RECORDED_MESSAGE = (
    "This demo replays model responses recorded by the project's 100-case harness and never calls a model. "
    "Retrieval found context for this alert, so the refusal guardrail did not fire, but no recording matches "
    "this exact text. Send one of the alerts from GET /samples unchanged, or run the project with your own "
    "key: see the README."
)


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert: str = Field(min_length=1)


def _real_engine(budget: DailyBudget):
    """Live mode. The key comes only from the environment."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None, None
    from anthropic import Anthropic
    from triage_engine.triage import SOCTriage
    metered = MeteredClient(Anthropic(api_key=key), budget)
    return SOCTriage(client=metered), metered


def _cached_engine(cfg: DemoConfig):
    """Cached mode. Builds no Anthropic client, so no request can reach a model."""
    recordings = load_recordings(cfg.cassette_dir)
    if not recordings:
        logger.warning("event=no_recordings")
        return None, None
    from triage_engine.triage import SOCTriage
    client = CachedClient(recordings, load_cases(cfg.cases_dir))
    return SOCTriage(client=client), client


def create_app(config: DemoConfig | None = None, engine_factory=None, clock=time.time, warm: bool = False) -> FastAPI:
    """`engine_factory(budget) -> (engine, client)` is injectable for tests. `client` is the MeteredClient
    (live) or CachedClient (cached) the engine calls, or None."""
    cfg = config or DemoConfig.from_env()
    live = cfg.mode == "live"
    install_redaction()
    budget = DailyBudget(cfg.daily_token_cap, cfg.state_path, clock)
    limiter = IPRateLimiter(cfg.per_ip_per_minute, cfg.per_ip_per_day, clock)
    factory = engine_factory or (_real_engine if live else (lambda _budget: _cached_engine(cfg)))
    state: dict = {"engine": None, "client": None, "loaded": False, "kinds": {}}

    lock = threading.Lock()

    def ensure_engine():
        with lock:
            if state["loaded"]:
                return
            engine, client = factory(budget)
            if engine is not None and isinstance(client, CachedClient):
                # verify on this machine which recordings reproduce, so /samples only offers working ones
                state["kinds"] = check_recordings(engine, client)
                c = Counter(state["kinds"].values())
                logger.info("event=recordings_checked replay=%d refusal=%d unservable=%d",
                            c["replay"], c["refusal"], c["unservable"])
            state["engine"], state["client"], state["loaded"] = engine, client, True

    @asynccontextmanager
    async def lifespan(_app):
        if warm:  # load embeddings in the background so the first visitor does not wait
            threading.Thread(target=ensure_engine, daemon=True).start()
        yield

    app = FastAPI(title="SOC Triage AI (public demo)", version="0.2.0", lifespan=lifespan)

    def log_event(event: str, status: int, **counts) -> None:
        # counts only: never the alert, never the raw address
        logger.info("event=%s status=%s %s", event, status, " ".join(f"{k}={v}" for k, v in counts.items()))

    def refuse(status_code: int, status: str, message: str, headers: dict | None = None, **extra):
        return JSONResponse({"status": status, "message": message, **extra}, status_code=status_code,
                            headers={"X-Demo-Mode": cfg.mode, **(headers or {})})

    @app.get("/healthz")
    def healthz():
        body = {"status": "ok", "demo_mode": True, "mode": cfg.mode}
        if not live:
            c = Counter(state["kinds"].values())
            body["recordings"] = ({k: c[k] for k in ("replay", "refusal", "unservable")}
                                  if state["loaded"] else "loading")
        return body

    @app.get("/budget")
    def get_budget():
        if live:
            return {"mode": "live", **budget.snapshot()}
        # cached mode makes no model calls, so there is nothing to meter
        return {"mode": "cached", "daily_token_cap": None, "tokens_used": 0, "tokens_remaining": None,
                "resets_at": None}

    @app.get("/samples")
    async def samples():
        """Harness alerts to try. In cached mode, only those this machine verified to replay or refuse."""
        if live:
            return [{"id": c.case_id, "category": c.category, "group": c.group, "label": c.label,
                     "kind": "live", "alert": c.alert} for c in load_cases(cfg.cases_dir)]
        await asyncio.to_thread(ensure_engine)
        client, kinds = state["client"], state["kinds"]
        if not isinstance(client, CachedClient):
            return []
        return [{"id": c.case_id, "category": c.category, "group": c.group, "label": c.label,
                 "kind": kinds[c.case_id], "alert": c.alert}
                for c in client.cases if kinds.get(c.case_id) in ("replay", "refusal")]

    @app.post("/triage", response_model=CaseEnvelope)
    async def triage(body: TriageRequest, request: Request, response: Response):
        ip = client_ip(request.headers.get("x-forwarded-for"),
                       request.client.host if request.client else None, cfg.trusted_proxy_hops)
        tag = ip_tag(ip, cfg.ip_salt)
        n = len(body.alert)

        if n > cfg.max_alert_chars:
            log_event("alert_too_long", 413, alert_chars=n, client=tag)
            return refuse(413, "alert_too_long", f"Alert is {n} characters; the demo accepts up to {cfg.max_alert_chars}.")

        if live and budget.exhausted:
            log_event("budget_reached", 429, alert_chars=n, client=tag)
            return refuse(429, "demo_budget_reached", BUDGET_MESSAGE, resets_at=budget.resets_at())

        allowed, retry = limiter.check(ip)
        if not allowed:
            log_event("rate_limited", 429, alert_chars=n, client=tag, retry_after=retry)
            return refuse(429, "rate_limited", f"Too many requests from your address. Try again in {retry} seconds.",
                          headers={"Retry-After": str(retry)}, retry_after_seconds=retry)

        await asyncio.to_thread(ensure_engine)
        engine, client = state["engine"], state["client"]
        if engine is None:
            log_event("not_configured", 503, alert_chars=n, client=tag)
            return refuse(503, "not_configured", "The demo has no model key configured." if live
                          else "The demo has no recorded model responses loaded.")
        cached = isinstance(client, CachedClient)

        def run():
            from triage_engine.case_package import build_case_package
            from triage_engine.extractors import extract_observables
            if cached:
                client.begin()
            elif client:
                client.take_request_tokens()
            result, hits, guard = engine.triage_with_context(body.alert)
            rec, tokens = None, 0
            if cached:
                called, rec = client.outcome()
                if called and rec is None:  # the model step was reached and nothing recorded answers it
                    return None, hits, guard, 0, None
            elif client:
                tokens = client.take_request_tokens()
            pkg = build_case_package(alert_raw=body.alert, observables=extract_observables(body.alert),
                                     triage_result=result, retrieval_hits=hits, guardrail_triggered=guard)
            return pkg, hits, guard, tokens, rec

        pkg, hits, guard, tokens, rec = await asyncio.to_thread(run)
        if pkg is None:
            log_event("not_recorded", 404, alert_chars=n, chunks=len(hits), client=tag)
            return refuse(404, "not_recorded", NOT_RECORDED_MESSAGE, retrieval={
                "avg_score": round(sum(s for _, s in hits) / len(hits), 3) if hits else 0.0,
                "chunks": [{"source": ch["source"], "score": round(s, 3)} for ch, s in hits],
            })
        response.headers["X-Demo-Mode"] = cfg.mode
        if rec is not None:
            response.headers["X-Demo-Replay-Case"] = rec.case_id
            if rec.recorded_at:
                response.headers["X-Demo-Recorded-At"] = rec.recorded_at
        log_event("triaged", 200, alert_chars=n, chunks=len(pkg["evidence"]["chunks_retrieved"]),
                  guardrail=guard, tokens=tokens, replay=rec.case_id if rec else "-", client=tag)
        return pkg

    return app


def app_factory() -> FastAPI:  # uvicorn --factory soc_demo.api:app_factory
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    return create_app(warm=True)
