"""Hugging Face Space on ZeroGPU: the demo API with a Gradio page mounted at /.

Hugging Face hosts Docker Spaces only on paid plans, while a free account can host Gradio Spaces on
ZeroGPU hardware. This module serves the same API as the Docker image (POST /triage, GET /samples,
/healthz, /budget) and mounts a Gradio page at /. The page calls that API in process and forwards
the visitor's X-Forwarded-For, so the page and direct API calls pass the same guards and the same
logging rules. Nothing here asks for a GPU: the embedding model runs on the CPU
(SOC_EMBED_DEVICE=cpu), where the cassettes were checked.
"""
from __future__ import annotations

import json
import logging
import os

import gradio as gr
import httpx
from fastapi import FastAPI

from soc_demo.api import create_app
from soc_demo.guard import DemoConfig
from soc_demo.present import (
    CACHED_INTRO, EXACT_TEXT_NOTE, FEATURED, KNOWN_MISS, LIVE_INTRO, NOT_RECORDED, canonical_alert, download_name,
    is_known_miss, option_label,
)
from triage_engine.extractors import extract_observables

STARTING = "The demo backend is still starting. Reload the page in a minute."


def _api(app: FastAPI) -> httpx.AsyncClient:
    # In process: no port, no network. The request still runs the API's middleware, guards and logging.
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://demo", timeout=120)


def _forwarded(request: gr.Request | None) -> dict:
    """The visitor's X-Forwarded-For, unchanged, so the per-address limit keys on the visitor as it does for a
    direct API call. Without it (a local run) every page request shares this process's address."""
    xff = request.headers.get("x-forwarded-for", "") if request is not None else ""
    return {"X-Forwarded-For": xff} if xff else {}


def observables_md(alert: str) -> str:
    obs = {k: v for k, v in extract_observables(alert or "").items() if v}
    if not obs:
        return ""
    return "Observables (regex, runs before any model call): " + "  ".join(
        f"`{k}`: " + ", ".join(f"`{x}`" for x in v) for k, v in obs.items())


def render(status: int, body: dict, headers: dict, samples: list[dict]) -> tuple[str, str, str | None]:
    """(result markdown, evidence markdown, case JSON name or None) for one POST /triage answer."""
    if status != 200:
        msg = NOT_RECORDED if body.get("status") == "not_recorded" else (
            body.get("message") or f"Request failed with status {status}.")
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
    if body["guardrail_triggered"]:
        lines.append("**Guardrail triggered:** the system refused to fabricate a triage. "
                     "Manual analyst review required.\n")
        if not ev["chunks_retrieved"]:
            lines.append("No model call was made: no corpus chunk reached the similarity threshold.\n")
    lines += [t["summary"], "", "**Recommended actions**", ""]
    lines += [f"{i}. {a}" for i, a in enumerate(t["recommended_actions"], 1)]
    lines += ["", "**MITRE ATT&CK:** " + (", ".join(t["mitre_techniques"]) or "none"), "",
              "**Reasoning:** " + t["reasoning"]]
    evidence = [f"{len(ev['chunks_retrieved'])} chunks, average score {ev['avg_retrieval_score']}", ""]
    for ch in ev["chunks_retrieved"]:
        evidence += [f"- `{ch['source']}` score {ch['score']}{' (cited)' if ch['cited'] else ''}",
                     "  > " + ch["text"][:400].replace("\n", " ")]
    return "\n".join(lines), "\n".join(evidence), download_name(body, replayed)


async def page_triage(api_app: FastAPI, alert: str, samples: list[dict], mode: str,
                      forwarded: dict) -> tuple[str, str, str | None, dict]:
    """What the page's Run button does: POST /triage in process, as the visitor. Returns (result markdown,
    evidence markdown, case JSON name or None, response body)."""
    async with _api(api_app) as api:
        if not mode:  # a client that skipped the page load (gradio_client): fetch what the page would hold
            mode = (await api.get("/healthz")).json().get("mode", "live")
            r = await api.get("/samples", headers=forwarded)
            samples = r.json() if r.status_code == 200 else []
        sent = canonical_alert(alert, samples) if mode == "cached" else alert
        r = await api.post("/triage", json={"alert": sent}, headers=forwarded)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        result, evidence, name = render(r.status_code, body, dict(r.headers), samples)
        if mode == "live":
            b = (await api.get("/budget")).json()
            result += f"\n\nDemo tokens left today: {b['tokens_remaining']:,} of {b['daily_token_cap']:,}."
    return result, evidence, name, body


def build_ui(api_app: FastAPI) -> gr.Blocks:
    async def on_load(request: gr.Request):
        async with _api(api_app) as api:
            try:
                mode = (await api.get("/healthz")).json().get("mode", "live")
                r = await api.get("/samples", headers=_forwarded(request))
                samples = r.json() if r.status_code == 200 else []
            except Exception:
                mode, samples = "unknown", []
        intro = CACHED_INTRO if mode == "cached" else LIVE_INTRO if mode == "live" else STARTING
        listed = {s["id"] for s in samples}
        choices = [(option_label(s), s["id"]) for s in samples]
        note = (f"{len(samples)} recorded harness alerts. " + EXACT_TEXT_NOTE if mode == "cached" and samples
                else f"{len(samples)} harness alerts." if samples else STARTING)
        return (samples, mode, intro, gr.update(choices=choices, value=None), note,
                *[gr.update(visible=cid in listed) for cid in FEATURED])

    def pick(samples: list[dict], cid: str | None):
        alert = {s["id"]: s for s in samples}.get(cid or "", {}).get("alert")
        return alert if alert is not None else gr.update()

    async def run(alert: str, samples: list[dict], mode: str, request: gr.Request):
        if not (alert or "").strip():
            return "Paste an alert or pick a recorded one first.", "", gr.update(value=None, visible=False)
        result, evidence, name, body = await page_triage(api_app, alert, samples, mode, _forwarded(request))
        if name is None:
            return result, evidence, gr.update(value=None, visible=False)
        # shown in the page, never written to the server's disk: the envelope carries the visitor's alert text
        return result, evidence, gr.update(value=json.dumps(body, indent=2), label=f"Case JSON ({name})", visible=True)

    with gr.Blocks(title="SOC Triage AI demo", analytics_enabled=False) as ui:
        samples_state, mode_state = gr.State([]), gr.State("")
        gr.Markdown("# SOC Triage AI")
        intro = gr.Markdown()
        with gr.Row():
            with gr.Column(scale=1, min_width=260):
                gr.Markdown("**Recorded alerts**")
                buttons = [gr.Button(label, size="sm", visible=False) for label in FEATURED.values()]
                chooser = gr.Dropdown(label="Harness case", choices=[], value=None, interactive=True)
                load_selected = gr.Button("Load selected", size="sm")
                note = gr.Markdown()
            with gr.Column(scale=3):
                alert = gr.Textbox(label="Alert", lines=6, placeholder="Pick a recorded alert.")
                observables = gr.Markdown()
                run_button = gr.Button("Run triage", variant="primary")
                result = gr.Markdown()
                with gr.Accordion("Evidence", open=False):
                    evidence = gr.Markdown()
                case_json = gr.Code(label="Case JSON", language="json", interactive=False, visible=False,
                                    max_lines=30)

        ui.load(on_load, inputs=None, outputs=[samples_state, mode_state, intro, chooser, note, *buttons],
                api_visibility="private")
        for button, cid in zip(buttons, FEATURED):
            button.click(lambda samples, cid=cid: pick(samples, cid), inputs=samples_state, outputs=alert,
                         api_visibility="private")
        load_selected.click(pick, inputs=[samples_state, chooser], outputs=alert, api_visibility="private")
        alert.change(observables_md, inputs=alert, outputs=observables, api_visibility="private")
        run_button.click(run, inputs=[alert, samples_state, mode_state], outputs=[result, evidence, case_json],
                         api_name="run_triage")
    ui.queue(default_concurrency_limit=8, max_size=64)
    return ui


def create_space_app(config: DemoConfig | None = None, engine_factory=None, warm: bool = True) -> FastAPI:
    api_app = create_app(config, engine_factory, warm=warm)
    # show_error=False: an exception's text never reaches the page. run_history=False: nothing about a run is
    # recorded, not even in the visitor's browser. SSR needs a Node server; the page works without.
    return gr.mount_gradio_app(api_app, build_ui(api_app), path="/", show_error=False, ssr_mode=False,
                               run_history=False)


def main() -> None:  # the Space's app.py calls this
    os.environ.setdefault("SOC_EMBED_DEVICE", "cpu")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    import uvicorn
    uvicorn.run(create_space_app(), host=os.environ.get("GRADIO_SERVER_NAME", "0.0.0.0"),
                port=int(os.environ.get("GRADIO_SERVER_PORT", "7860")), access_log=False)
