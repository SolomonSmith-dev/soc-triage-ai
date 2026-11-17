"""Hugging Face Space on ZeroGPU: the demo API with a Gradio page mounted at /.

Hugging Face hosts Docker Spaces only on paid plans, while a free account can host Gradio Spaces on
ZeroGPU hardware. This module serves the same API as the Docker image (POST /triage, GET /samples,
/healthz, /budget) and mounts a Gradio page at /. The page calls that API in process and forwards
the visitor's X-Forwarded-For, so the page and direct API calls pass the same guards and the same
logging rules. No visitor action uses a GPU: the embedding model runs on the CPU (SOC_EMBED_DEVICE=cpu),
where the cassettes were checked. ZeroGPU still stops a Space that sends no startup report, and `spaces` sends
one only when a @spaces.GPU function exists: zerogpu_handler is that function, a no-op no page event calls, and
send_zerogpu_startup_report covers the `spaces` version that only reports from demo.launch().
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import traceback

import gradio as gr
import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.routing import Mount

from soc_demo.api import _where, create_app
from soc_demo.guard import DemoConfig, IPRateLimiter, client_ip, ip_tag
from soc_demo.present import (
    CACHED_INTRO, EXACT_TEXT_NOTE, FEATURED, KNOWN_MISS, LIVE_INTRO, NOT_RECORDED, canonical_alert, corpus_md,
    download_name, is_known_miss, md_code, md_literal, option_label,
)

try:  # ZeroGPU's package. Absent in local runs and CI's unit job, where nothing needs it.
    import spaces
except ImportError:
    spaces = None

logger = logging.getLogger("soc_demo")

STARTING = "The demo backend is still starting. Reload the page in a minute."
NO_RESPONSE = "The demo backend did not respond. Try again in a minute."
PAGE_ERROR = "Internal error. The demo logs only the error type."
UNREADABLE = "The alert contains characters the demo cannot read. Remove them and try again."
NO_CASE = "Pick a case from the list, then Load selected."
HEADING = {"cached": "**Recorded alerts**", "live": "**Samples**"}
PLACEHOLDER = {"cached": "Pick a recorded alert.", "live": "Paste an alert, or pick a sample."}
PAGE_TIMEOUT = 120  # seconds a Run waits on the API; the in-process transport applies no timeout of its own
LOAD_TIMEOUT = 30
# The page may load images only from the Space itself and Hugging Face's avatar hosts (Gradio's Space badge shows
# the owner's avatar when the page is opened at the hf.space URL), so text it renders cannot make a visitor's browser
# fetch a URL elsewhere.
CSP = ("img-src 'self' data: blob: https://huggingface.co/api/users/ https://huggingface.co/api/organizations/ "
       "https://cdn-avatars.huggingface.co")
# Page events per address. Gradio's queue is shared by every visitor and holds 64 events; a person uses a few a minute.
PAGE_EVENTS_PER_MINUTE, PAGE_EVENTS_PER_DAY = 30, 2000
# Saves the case JSON under the name in its label, which carries the replay provenance the envelope has no field for.
# It runs in the browser only: Gradio's own download button always saves file.json.
SAVE_JSON_JS = """(text) => {
  const label = document.querySelector('#case-json [data-testid="block-label"]')?.textContent || '';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], {type: 'application/json'}));
  a.download = (label.match(/[(]([^()]+[.]json)[)]/) || [])[1] || 'case.json';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}"""


class _GradioTraceback:
    """Stands in for the traceback module inside Gradio's request and queue code, which prints event errors with
    traceback.print_exc(). Exception text can carry what a caller sent, so this logs the type and location only, in
    the demo's log format. Every other attribute is the real module."""

    def __getattr__(self, name):
        return getattr(traceback, name)

    @staticmethod
    def print_exc(*_args, **_kwargs) -> None:
        exc = sys.exc_info()[1]
        logger.error("event=page_event_error error=%s at=%s", type(exc).__name__, _where(exc) if exc else "-")


GRADIO_PRINTERS = ("gradio.queueing", "gradio.routes", "gradio.route_utils")  # checked against gradio 6.32.0


def _quiet_gradio_tracebacks() -> None:
    for name in GRADIO_PRINTERS:
        sys.modules[name].traceback = _GradioTraceback()
    # gradio.routes also print()s the custom_component route's path parameters, text any visitor chooses, before it
    # answers 404. The page uses no custom components, and the module's other prints are off here (monitoring) or
    # carry a file path.
    sys.modules["gradio.routes"].print = lambda *_args, **_kwargs: None


def _zerogpu_noop() -> None:
    return None


# ZeroGPU stops a Space that sends no startup report, and spaces 0.51.3 sends it only once some function carries
# @spaces.GPU. The demo needs no GPU, so this no-op is decorated and wired to nothing: a page event that called it
# would wait up to 60 s for a GPU while ZeroGPU queues, holding a slot of the queue every visitor shares. Outside
# ZeroGPU the decorator returns the function unchanged.
zerogpu_handler = spaces.GPU(duration=1)(_zerogpu_noop) if spaces is not None else _zerogpu_noop


def gpu_functions() -> int:
    """How many functions carry @spaces.GPU: 1 on ZeroGPU (zerogpu_handler), 0 elsewhere."""
    cache = getattr(getattr(getattr(spaces, "zero", None), "decorator", None), "decorated_cache", {})
    return len({id(f) for f in cache.values()})


def send_zerogpu_startup_report(app: FastAPI) -> bool:
    """On ZeroGPU, send the startup report the platform waits for, unless `spaces` will send it itself. Returns
    whether this sent it.

    `spaces` sends the report from demo.launch(). From 0.52 it also sends it for an app built with
    gr.mount_gradio_app, from a middleware it adds there. Hugging Face's ZeroGPU build installs spaces 0.51.3, which
    does neither for this app: it is mounted and run with uvicorn. Without the report ZeroGPU stops the Space with
    "No @spaces.GPU function detected during startup". The report needs a @spaces.GPU function: zerogpu_handler."""
    if spaces is None or not spaces.config.Config.zero_gpu:
        return False
    if any(getattr(m.cls, "__name__", "") == "ZeroGPUMiddleware" and not m.kwargs.get("skip_zerogpu_startup")
           for m in app.user_middleware):
        return False
    spaces.zero.startup()  # a failure raises, and the process exits before serving
    return True


def _api(app: FastAPI) -> httpx.AsyncClient:
    # In process: no port, no network. The request still runs the API's middleware, guards and logging. The
    # transport ignores timeouts, so callers bound their waits with asyncio.wait_for.
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://demo")


def _forwarded(request: gr.Request | None) -> dict:
    """The visitor's X-Forwarded-For, unchanged, so the per-address limit keys on the visitor as it does for a
    direct API call. Without it (a local run) every page request shares this process's address."""
    xff = request.headers.get("x-forwarded-for", "") if request is not None else ""
    return {"X-Forwarded-For": xff} if xff else {}


async def _mode_and_samples(api: httpx.AsyncClient, forwarded: dict) -> tuple[str, list[dict]]:
    mode = (await api.get("/healthz")).json().get("mode", "live")
    r = await api.get("/samples", headers=forwarded)
    return mode, r.json() if r.status_code == 200 else []


def observables_md(observables: dict) -> str:
    """The case's observables, from the API's answer. The page runs no extraction of its own: a per-keystroke
    preview was a cheap, unthrottled event on the queue every visitor shares."""
    found = {k: v for k, v in observables.items() if v}
    if not found:
        return ""
    return "Observables (regex, ran before any model call): " + "  ".join(
        f"`{k}`: " + ", ".join(md_code(x) for x in v) for k, v in found.items()) + "\n"


def render(status: int, body: dict, headers: dict, samples: list[dict]) -> tuple[str, str, str | None]:
    """(result markdown, evidence markdown, case JSON name or None) for one POST /triage answer."""
    if status != 200:
        # invalid_request: the page sends only non-empty text, so the API could not read it (a lone surrogate)
        msg = {"not_recorded": NOT_RECORDED, "invalid_request": UNREADABLE}.get(body.get("status")) or (
            body.get("message") or f"Request failed with status {status}.")
        if obs := observables_md(body.get("observables") or {}):  # not_recorded: stage 1 ran live
            msg += "\n\n" + obs.rstrip("\n")
        chunks = (body.get("retrieval") or {}).get("chunks") or []
        if chunks:
            msg += "\n\n**Retrieval ran live on this alert:** " + ", ".join(
                f"`{ch['source']}` {ch['score']}" for ch in chunks)
        return msg, "", None
    t, ev = body["triage"], body["evidence"]
    replayed = headers.get("x-demo-replay-case")
    lines = ["| Severity | Escalate | Confidence | Evidence |", "|---|---|---|---|",
             f"| **{t['severity'].upper()}** | {'Yes' if t['escalate'] else 'No'} | {t['confidence']} | "
             f"{body['uncertainty_mode'].replace('_', ' ')} |", ""]
    if replayed:
        when = headers.get("x-demo-recorded-at", "")[:10]
        lines.append(f"Model step replayed from the harness recording of case `{replayed}` "
                     f"({body['version']['model']}{', recorded ' + when if when else ''}). "
                     "Extraction, retrieval and schema validation ran live on this request.\n")
        if is_known_miss({s["id"]: s for s in samples}.get(replayed), body):
            lines.append(KNOWN_MISS + "\n")
    if obs := observables_md(body.get("observables") or {}):
        lines.append(obs)
    if body["guardrail_triggered"]:
        lines.append("**Guardrail triggered:** the system refused to fabricate a triage. "
                     "Manual analyst review required.\n")
        if not ev["chunks_retrieved"]:
            lines.append("No model call was made: no corpus chunk reached the similarity threshold.\n")
    # model text is shown as text: in live mode an injected alert could otherwise get Markdown (a remote image)
    # into the page
    lines += [md_literal(t["summary"]), "", "**Recommended actions**", ""]
    lines += [f"{i}. {md_literal(a)}" for i, a in enumerate(t["recommended_actions"], 1)]
    lines += ["", "**MITRE ATT&CK:** " + (", ".join(map(md_literal, t["mitre_techniques"])) or "none"), "",
              "**Reasoning:** " + md_literal(t["reasoning"])]
    evidence = [f"{len(ev['chunks_retrieved'])} chunks, average score {ev['avg_retrieval_score']}", ""]
    for ch in ev["chunks_retrieved"]:
        # each line of the chunk quoted, so its title stays a short heading over its bullets
        evidence += [f"- `{ch['source']}` score {ch['score']}{' (cited)' if ch['cited'] else ''}",
                     *("  > " + line for line in corpus_md(ch["text"][:400]).splitlines())]
    return "\n".join(lines), "\n".join(evidence), download_name(body, replayed)


async def page_triage(api_app: FastAPI, alert: str, forwarded: dict) -> tuple[str, str, str | None, dict]:
    """What the page's Run button does: POST /triage in process, as the visitor. Returns (result markdown,
    evidence markdown, case JSON name or None, response body)."""
    async with _api(api_app) as api:
        mode, samples = await _mode_and_samples(api, forwarded)
        sent = canonical_alert(alert, samples) if mode == "cached" else alert
        # serialized here with non-ASCII escaped: text JSON cannot carry (a lone surrogate) then gets the API's
        # fixed 422 instead of failing in the client
        r = await api.post("/triage", content=json.dumps({"alert": sent}),
                           headers={**forwarded, "content-type": "application/json"})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        result, evidence, name = render(r.status_code, body, dict(r.headers), samples)
        if mode == "live":
            b = (await api.get("/budget")).json()
            result += f"\n\nDemo tokens left today: {b['tokens_remaining']:,} of {b['daily_token_cap']:,}."
    return result, evidence, name, body


def build_ui(api_app: FastAPI) -> gr.Blocks:
    # Every event takes at most one input and no gr.State. Gradio prints the values a call sent when it sent too
    # few, so with one input a short call prints nothing a visitor typed. Samples and mode come from the API on
    # each event instead, in process.
    async def on_load(request: gr.Request):
        try:
            async with _api(api_app) as api:
                mode, samples = await asyncio.wait_for(_mode_and_samples(api, _forwarded(request)), LOAD_TIMEOUT)
        except Exception as exc:  # a timeout too: the page then says the backend is starting
            logger.warning("event=page_load_failed error=%s at=%s", type(exc).__name__, _where(exc))
            mode, samples = "unknown", []
        intro = CACHED_INTRO if mode == "cached" else LIVE_INTRO if mode == "live" else STARTING
        listed = {s["id"] for s in samples}
        choices = [(option_label(s), s["id"]) for s in samples]
        note = (f"{len(samples)} recorded harness alerts. " + EXACT_TEXT_NOTE if mode == "cached" and samples
                else f"{len(samples)} harness alerts." if samples else STARTING)
        return (intro, HEADING.get(mode, HEADING["cached"]), gr.update(placeholder=PLACEHOLDER.get(mode, "")),
                gr.update(choices=choices, value=None), note, *[gr.update(visible=cid in listed) for cid in FEATURED])

    async def pick(cid, request: gr.Request):
        try:
            async with _api(api_app) as api:
                _, samples = await asyncio.wait_for(_mode_and_samples(api, _forwarded(request)), LOAD_TIMEOUT)
        except Exception as exc:
            logger.warning("event=page_pick_failed error=%s at=%s", type(exc).__name__, _where(exc))
            return gr.update()
        # a raw call can send any JSON value here (the chooser takes custom values, so Gradio never echoes one)
        alert = {s["id"]: s for s in samples}.get(cid if isinstance(cid, str) else "", {}).get("alert")
        if alert is None:  # text typed into the chooser and not picked from it; the notice is fixed text
            gr.Info(NO_CASE)
            return gr.update()
        return alert

    def featured(cid: str):
        async def load(request: gr.Request):
            return await pick(cid, request)
        return load

    async def run(alert: str, request: gr.Request):
        hidden = gr.update(value=None, visible=False)
        if not (alert or "").strip():
            return "Paste an alert or pick one first.", "", hidden
        try:
            result, evidence, name, body = await asyncio.wait_for(
                page_triage(api_app, alert, _forwarded(request)), PAGE_TIMEOUT)
        except TimeoutError:
            logger.warning("event=page_timeout seconds=%d", PAGE_TIMEOUT)
            return NO_RESPONSE, "", hidden
        except Exception as exc:  # by type and location only, as the API's ContainErrors does
            logger.error("event=page_error error=%s at=%s", type(exc).__name__, _where(exc))
            return PAGE_ERROR, "", hidden
        if name is None:
            return result, evidence, hidden
        # shown in the page, never written to the server's disk: the envelope carries the visitor's alert text
        return result, evidence, gr.update(value=json.dumps(body, indent=2), label=f"Case JSON ({name})", visible=True)

    # delete_cache: a backstop. The page takes no files, and the API refuses multipart bodies before Gradio reads them
    with gr.Blocks(title="SOC Triage AI demo", analytics_enabled=False, delete_cache=(600, 600)) as ui:
        gr.Markdown("# SOC Triage AI")
        intro = gr.Markdown()
        with gr.Row():
            with gr.Column(scale=1, min_width=260):
                heading = gr.Markdown(HEADING["cached"])
                buttons = [gr.Button(label, size="sm", visible=False) for label in FEATURED.values()]
                chooser = gr.Dropdown(label="Harness case", choices=[], value=None, interactive=True,
                                      allow_custom_value=True)
                load_selected = gr.Button("Load selected", size="sm")
                note = gr.Markdown()
            with gr.Column(scale=3):
                alert = gr.Textbox(label="Alert", lines=6, placeholder=PLACEHOLDER["cached"])
                run_button = gr.Button("Run triage", variant="primary")
                # latex off: alert and model text are shown as text, and KaTeX would still read $$ in it
                result = gr.Markdown(latex_delimiters=[])
                with gr.Accordion("Evidence", open=False):
                    evidence = gr.Markdown(latex_delimiters=[])
                save_json = gr.Button("Download", size="sm")
                case_json = gr.Code(label="Case JSON", language="json", interactive=False, visible=False,
                                    max_lines=30, buttons=["copy", save_json], elem_id="case-json")

        ui.load(on_load, inputs=None, outputs=[intro, heading, alert, chooser, note, *buttons],
                api_visibility="private")
        for button, cid in zip(buttons, FEATURED):
            button.click(featured(cid), inputs=None, outputs=alert, api_visibility="private")
        load_selected.click(pick, inputs=chooser, outputs=alert, api_visibility="private")
        save_json.click(None, inputs=case_json, outputs=None, js=SAVE_JSON_JS)  # browser only, no server call
        run_button.click(run, inputs=alert, outputs=[result, evidence, case_json], api_name="run_triage")
    ui.queue(default_concurrency_limit=8, max_size=64)
    return ui


class PageEventLimit:
    """Per-address limit on the page's event calls (every POST under /gradio_api/). Gradio's queue is shared by all
    visitors and holds 64 events, so without it one client could fill the queue and every other visitor's page would
    fail. Each Run also passes the demo API's own limits. Plain ASGI."""

    def __init__(self, app, limiter: IPRateLimiter, trusted_hops: int, salt: str):
        self.app, self.limiter, self.trusted_hops, self.salt = app, limiter, trusted_hops, salt

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or not scope["path"].startswith("/gradio_api/"):
            await self.app(scope, receive, send)
            return
        peer = scope.get("client")
        ip = client_ip(Headers(scope=scope).get("x-forwarded-for"), peer[0] if peer else None, self.trusted_hops)
        allowed, retry = self.limiter.check(ip)
        if not allowed:
            logger.info("event=page_rate_limited status=429 client=%s retry_after=%d", ip_tag(ip, self.salt), retry)
            # Gradio's page shows a refused event's "detail"; without it the toast says only "An error occurred". A
            # refused page load is not retried, so the text says to reload.
            msg = f"Too many page requests from your address. Reload the page in {retry} seconds."
            await JSONResponse({"status": "rate_limited", "detail": msg, "message": msg}, status_code=429,
                               headers={"Retry-After": str(retry)})(scope, receive, send)
            return
        await self.app(scope, receive, send)


class PageHeaders:
    """Adds the Content-Security-Policy to every response, and closes Gradio's /gradio_api/file=<URL> route, which
    fetches any public URL for anyone. The page shows no files. Plain ASGI, so streaming responses pass through."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"].lower().startswith(("/gradio_api/file=http:", "/gradio_api/file=https:")):
            await JSONResponse({"detail": "Not Found"}, status_code=404,
                               headers={"content-security-policy": CSP})(scope, receive, send)
            return

        async def with_csp(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []),
                                                  (b"content-security-policy", CSP.encode())]}
            await send(message)

        await self.app(scope, receive, with_csp)


async def _invalid_page_request(_request: Request, _exc: RequestValidationError):
    # Gradio's routes would answer with FastAPI's default, which echoes the input and, when the input cannot be
    # encoded, fails into a 500 that logs it. The API's routes already answer this way.
    logger.info("event=invalid_request status=422 route=page")
    return JSONResponse({"status": "invalid_request", "message": "Invalid request."}, status_code=422)


def create_space_app(config: DemoConfig | None = None, engine_factory=None, warm: bool = True) -> FastAPI:
    cfg = config or DemoConfig.from_env()
    api_app = create_app(cfg, engine_factory, warm=warm)
    # show_error=False: an exception's text never reaches the page. run_history=False: nothing about a run is
    # recorded, not even in the visitor's browser. SSR needs a Node server; the page works without.
    # max_file_size: no component takes files. Monitoring and the MCP server stay off.
    app = gr.mount_gradio_app(api_app, build_ui(api_app), path="/", show_error=False,
                              ssr_mode=False, run_history=False, max_file_size="1kb", enable_monitoring=False,
                              mcp_server=False)
    page = next(r.app for r in app.routes if isinstance(r, Mount) and isinstance(r.app, FastAPI))
    page.add_exception_handler(RequestValidationError, _invalid_page_request)
    _quiet_gradio_tracebacks()
    # 1 on ZeroGPU, where spaces records zerogpu_handler; its startup report needs one
    logger.info("event=page_built gpu_functions=%d", gpu_functions())
    app.add_middleware(PageEventLimit, limiter=IPRateLimiter(PAGE_EVENTS_PER_MINUTE, PAGE_EVENTS_PER_DAY),
                       trusted_hops=cfg.trusted_proxy_hops, salt=cfg.ip_salt)
    app.add_middleware(PageHeaders)  # outermost: every answer gets the CSP, a refusal from the limits included
    return app


def main() -> None:  # the Space's app.py calls this
    os.environ.setdefault("SOC_EMBED_DEVICE", "cpu")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # httpx logs each request URL at INFO, and callers choose some of them (a FileData URL in an event's data, the
    # X-IP-Token spaces forwards to the device API)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    import uvicorn
    app = create_space_app()
    if send_zerogpu_startup_report(app):
        logger.info("event=zerogpu_startup_report sent_by=app")
    # lifespan="on": a failed startup (from spaces 0.52 the ZeroGPU startup report runs in it) stops the process.
    # The default, "auto", would log it at INFO and serve a page whose queue never started.
    # ws="none": the page uses SSE, and uvicorn would log every WebSocket handshake's path and query at INFO
    uvicorn.run(app, host=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
                port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")), access_log=False, lifespan="on", ws="none")
