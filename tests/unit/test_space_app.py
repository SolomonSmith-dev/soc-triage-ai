"""The ZeroGPU Space: the demo API with the Gradio page mounted at /. Offline: fake retriever, no model weights.

Skipped when gradio is not installed (the demo's [space] extra); CI installs it in the unit job.
"""
import asyncio
import importlib.util
import logging
import re
import subprocess
import time
from pathlib import Path

import pytest

pytest.importorskip("gradio")
import gradio as gr  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.routing import Mount  # noqa: E402

import soc_demo.space as space_mod  # noqa: E402
from soc_demo.guard import DemoConfig  # noqa: E402
from soc_demo.present import KNOWN_MISS, NOT_RECORDED, md_code, md_literal  # noqa: E402
from soc_demo.replay import CachedClient, Recording  # noqa: E402
from soc_demo.space import (  # noqa: E402
    HEADING, NO_RESPONSE, PAGE_ERROR, PLACEHOLDER, UNREADABLE, create_space_app, observables_md, page_triage, render,
)
from tests.unit.test_demo_replay import (  # noqa: E402
    OFF_TOPIC, RECORDED, REPLY, UNRECORDED, FakeRetriever, harness_case, recorded_key,
)
from triage_engine.triage import SOCTriage  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPACE = ROOT / "deploy" / "hf-space-zerogpu"


def space(tmp_path, **cfg):
    rec = Recording("FAKE-001", REPLY, 900, 150, "2026-10-09T04:36:30Z")
    cases = [harness_case("FAKE-001", RECORDED), harness_case("FAKE-OOC", OFF_TOPIC),
             harness_case("FAKE-UNREC", UNRECORDED)]
    client = CachedClient({recorded_key(RECORDED): rec}, cases)
    config = DemoConfig(state_path=str(tmp_path / "b.json"), **cfg)
    return create_space_app(config, lambda b: (SOCTriage(client=client, retriever=FakeRetriever()), client),
                            warm=False)


def page_fn(app: FastAPI, name: str):
    """The page's handler for one event: the run button (api_name) or the page load ("on_load")."""
    blocks = next(r.app for r in app.routes if isinstance(r, Mount)).get_blocks()
    return next(f for f in blocks.fns.values() if f.api_name == name or getattr(f.fn, "__name__", "") == name)


def test_page_and_api_are_one_app(tmp_path):
    with TestClient(space(tmp_path)) as c:
        page = c.get("/")
        assert page.status_code == 200 and "gradio" in page.text.lower()
        assert c.get("/healthz").json()["mode"] == "cached"
        r = c.post("/triage", json={"alert": RECORDED})
        assert r.status_code == 200 and r.headers["x-demo-replay-case"] == "FAKE-001"
        bad = c.post("/triage", content=b'{"alert": NaN}', headers={"content-type": "application/json"})
        assert bad.status_code == 422 and bad.json()["status"] == "invalid_request"


def test_page_triage_limits_per_visitor_address(tmp_path):
    app = space(tmp_path, per_ip_per_minute=2)

    async def go():
        first = [await page_triage(app, OFF_TOPIC, {"X-Forwarded-For": "198.51.100.1"}) for _ in range(3)]
        other = await page_triage(app, OFF_TOPIC, {"X-Forwarded-For": "198.51.100.2"})
        return first, other

    first, other = asyncio.run(go())
    assert first[0][2] is not None and "No model call was made" in first[0][0]   # refused at retrieval, 200
    assert "Too many requests from your address" in first[2][0] and first[2][2] is None
    assert "Too many requests" not in other[0]


def test_whitespace_only_edit_keeps_the_recording(tmp_path):
    result, _, name, body = asyncio.run(page_triage(space(tmp_path), "  " + RECORDED.strip() + "\n\n", {}))
    assert "replayed from the harness recording of case `FAKE-001`" in result
    assert name.endswith("_replay-FAKE-001.json") and body["alert_raw"] == RECORDED


def test_edited_alert_is_not_recorded_and_shows_retrieval(tmp_path):
    result, evidence, name, _ = asyncio.run(page_triage(space(tmp_path), UNRECORDED, {}))
    assert result.startswith(NOT_RECORDED) and "Retrieval ran live on this alert" in result
    assert name is None and evidence == ""


def test_render_marks_a_documented_guardrail_miss():
    body = {"case_id": "SOC-20261117-0abc", "guardrail_triggered": False, "uncertainty_mode": "actionable",
            "triage": {"severity": "informational", "escalate": False, "confidence": "low", "summary": "s",
                       "recommended_actions": ["a"], "mitre_techniques": [], "reasoning": "r"},
            "evidence": {"chunks_retrieved": [], "avg_retrieval_score": 0.3}, "version": {"model": "m"}}
    samples = [{"id": "OOC-003", "expects_refusal": True, "kind": "replay"}]
    result, _, name = render(200, body, {"x-demo-replay-case": "OOC-003"}, samples)
    assert KNOWN_MISS in result and name == "SOC-20261117-0abc_replay-OOC-003.json"
    result, _, _ = render(200, body, {"x-demo-replay-case": "OOC-003"}, [])
    assert KNOWN_MISS not in result


def test_space_files_agree_on_versions_and_load_order():
    card = (SPACE / "README.md").read_text()
    extra = re.search(r'space = \["gradio==([^"]+)"\]', (ROOT / "apps/demo/pyproject.toml").read_text()).group(1)
    assert re.search(r"^sdk: gradio$", card, re.M) and f"sdk_version: {extra}\n" in card
    requirements = (SPACE / "requirements.txt").read_text()
    assert len(re.findall(r"/archive/main\.tar\.gz#subdirectory=", requirements)) == 3
    app = (SPACE / "app.py").read_text()
    # the CPU pin and `import spaces` must both come before anything loads torch
    assert app.index("SOC_EMBED_DEVICE") < app.index("import spaces") < app.index("from soc_demo")


def test_bundle_pins_the_commit_and_replaces_the_data(tmp_path):
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", head, "--",
                              "deploy/hf-space-zerogpu/bundle.py", "tests/harness/cassettes", "tests/harness/cases"],
                             capture_output=True, text=True).stdout.split()
    if "deploy/hf-space-zerogpu/bundle.py" not in tracked:
        pytest.skip("the Space files are not committed yet")
    committed = subprocess.run(["git", "-C", str(ROOT), "show", f"{head}:deploy/hf-space-zerogpu/bundle.py"],
                               capture_output=True).stdout
    if committed != (SPACE / "bundle.py").read_bytes():
        pytest.skip("bundle.py has uncommitted changes, and it refuses to bundle a commit other than its own")
    spec = importlib.util.spec_from_file_location("space_bundle", SPACE / "bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    real_git = mod._git
    mod._git = lambda *a: b"# another version\n" if a[-1].endswith("bundle.py") else real_git(*a)
    with pytest.raises(SystemExit, match="differs from the one at"):
        mod.bundle(head, tmp_path / "refused")
    mod._git = real_git
    stale = tmp_path / "tests/harness/cassettes/stale.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}")
    counts = mod.bundle(head, tmp_path)
    requirements = (tmp_path / "requirements.txt").read_text()
    assert requirements.count(f"/archive/{head}.tar.gz#") == 3 and "main.tar.gz" not in requirements
    assert (tmp_path / "app.py").exists() and (tmp_path / "README.md").exists() and not stale.exists()
    assert counts == {"cassettes": sum(1 for t in tracked if t.startswith("tests/harness/cassettes/") and t.endswith(".json")),
                      "cases": sum(1 for t in tracked if t.startswith("tests/harness/cases/") and t.endswith(".yaml"))}


def test_page_events_take_one_input_at_most(tmp_path):
    # Gradio prints the values a call sent when it sent too few; with one input, a short call sent none
    blocks = next(r.app for r in space(tmp_path).routes if isinstance(r, Mount)).get_blocks()
    assert all(len(f.inputs) <= 1 for f in blocks.fns.values())
    assert not any(isinstance(b, gr.State) for b in blocks.blocks.values())
    assert [len(f.inputs) for f in blocks.fns.values() if f.api_name == "run_triage"] == [1]


def test_long_alert_skips_extraction():
    start = time.monotonic()
    note = observables_md("a." * 50_000, 3000)  # quadratic in the stage 1 regexes: minutes if it ran
    assert time.monotonic() - start < 0.1 and note == "Alert is 100,000 characters; the demo accepts up to 3,000."
    assert "`ipv4`: `198.51.100.44`" in observables_md(RECORDED, 3000)


def test_rendered_text_cannot_become_markdown():
    markdown_it = pytest.importorskip("markdown_it")
    md = markdown_it.MarkdownIt("commonmark")
    beacon = "see ![p](https://attacker.example/t.png) <img src=x> [a](https://attacker.example) **b** `c`"
    for html in (md.render(md_literal(beacon)), md.render(md_code(beacon)),
                 md.render(observables_md("GET https://x.example/`![p](https://attacker.example/t.png)` 200", 3000))):
        assert "<img" not in html and "<a " not in html and "<strong>" not in html, html
    assert md.render(md_literal("a & b < c")).strip() == "<p>a &amp; b &lt; c</p>"
    assert md.render(md_code("x``y`")).strip() == "<p><code>x``y`</code></p>"
    body = {"case_id": "SOC-20261117-0abc", "guardrail_triggered": False, "uncertainty_mode": "actionable",
            "triage": {"severity": "high", "escalate": True, "confidence": "high", "summary": beacon,
                       "recommended_actions": [beacon], "mitre_techniques": [], "reasoning": beacon},
            "evidence": {"chunks_retrieved": [], "avg_retrieval_score": 0.5}, "version": {"model": "m"}}
    html = md.render(render(200, body, {}, [])[0])
    assert "<img" not in html and "attacker.example" in html and "<a " not in html


def test_page_routes_answer_malformed_requests_with_the_fixed_422(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    with TestClient(space(tmp_path), raise_server_exceptions=False) as c:
        for raw in (b'{"data": "zq-canary-7711 \\udc9f", "fn_index": 0, "session_hash": "x"}',
                    b'{"data": {"alert": "zq-canary-7712", "n": NaN}, "fn_index": 0, "session_hash": "x"}'):
            r = c.post("/gradio_api/queue/join", content=raw, headers={"content-type": "application/json"})
            assert r.status_code == 422 and r.json()["status"] == "invalid_request", r.text
            assert "zq-canary" not in r.text
        assert c.post("/gradio_api/upload", files={"files": ("x.bin", b"0" * 5000)}).status_code == 413
        page, api = c.get("/"), c.get("/healthz")
        assert all("img-src 'self'" in r.headers["content-security-policy"] for r in (page, api))
    assert "zq-canary" not in caplog.text and "Traceback" not in caplog.text


def test_page_run_contains_errors_and_waits_a_bounded_time(tmp_path, monkeypatch, caplog):
    run = page_fn(space(tmp_path), "run_triage").fn
    assert asyncio.run(run("zq-canary-7713 \udc9f", None))[0] == UNREADABLE  # the API's fixed 422, no exception

    async def stalled(*_a):
        await asyncio.sleep(5)

    async def broken(*_a):
        raise RuntimeError("zq-canary-7714 alert text in an exception")

    monkeypatch.setattr(space_mod, "PAGE_TIMEOUT", 0.05)
    monkeypatch.setattr(space_mod, "page_triage", stalled)
    assert asyncio.run(run("an alert", None))[0] == NO_RESPONSE
    monkeypatch.setattr(space_mod, "page_triage", broken)
    assert asyncio.run(run("an alert", None))[0] == PAGE_ERROR
    assert "event=page_error error=RuntimeError" in caplog.text and "zq-canary-7714" not in caplog.text


def test_live_mode_page_invites_pasting(tmp_path):
    app = create_space_app(DemoConfig(mode="live", state_path=str(tmp_path / "b.json")), lambda b: (None, None),
                           warm=False)
    out = asyncio.run(page_fn(app, "on_load").fn(None))
    assert out[1] == HEADING["live"] and out[2]["placeholder"] == PLACEHOLDER["live"]
    cached = asyncio.run(page_fn(space(tmp_path), "on_load").fn(None))
    assert cached[1] == HEADING["cached"] and cached[2]["placeholder"] == PLACEHOLDER["cached"]


def test_main_makes_a_failed_startup_fatal(monkeypatch):
    seen = {}
    monkeypatch.setattr(space_mod, "create_space_app", lambda: "app")
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: seen.update(kw, app=app))
    space_mod.main()
    # ZeroGPU's startup report runs in the lifespan; under "auto" a failure there leaves a page whose queue never starts
    assert seen["app"] == "app" and seen["lifespan"] == "on"


def test_gradio_event_errors_are_logged_by_type_only(tmp_path, capfd, caplog):
    import gradio.queueing
    app = space(tmp_path)
    assert all(isinstance(__import__(n, fromlist=["_"]).traceback, space_mod._GradioTraceback)
               for n in space_mod.GRADIO_PRINTERS)
    with TestClient(app) as c:
        event = c.post("/gradio_api/call/run_triage", json={"data": []}).json()["event_id"]  # one input short
        assert "event: error" in c.get(f"/gradio_api/call/run_triage/{event}").text
        extra = c.post("/gradio_api/call/run_triage", json={"data": [UNRECORDED, "zq-canary-7715"]}).json()
        assert "event: complete" in c.get(f"/gradio_api/call/run_triage/{extra['event_id']}").text
    err = capfd.readouterr().err
    assert "Received inputs" not in err and "Traceback" not in err and "zq-canary" not in err
    assert "event=page_event_error error=ValueError" in caplog.text and "zq-canary" not in caplog.text
    assert gradio.queueing.traceback.format_exc  # every other name is the real module's


def test_a_stale_page_stream_ends_cleanly_and_logs_one_line(tmp_path, caplog):
    with TestClient(space(tmp_path)) as c:  # an exception here would reach the test client
        r = c.get("/gradio_api/queue/data?session_hash=stale-tab")
    assert r.status_code == 200
    assert "event=unhandled_error status=aborted route=/gradio_api/queue/data" in caplog.text
    assert "Traceback" not in caplog.text


def test_the_zerogpu_handler_is_a_hidden_no_op(tmp_path):
    # ZeroGPU stops a Space whose Gradio handlers carry no @spaces.GPU; outside ZeroGPU it is the plain function
    blocks = next(r.app for r in space(tmp_path).routes if isinstance(r, Mount)).get_blocks()
    gpu = [f for f in blocks.fns.values() if f.fn is space_mod.zerogpu_handler]
    assert len(gpu) == 1 and not gpu[0].inputs and not gpu[0].outputs and gpu[0].api_visibility == "private"
    button = blocks.blocks[gpu[0].targets[0][0]]
    assert isinstance(button, gr.Button) and button.visible is False
    assert space_mod.zerogpu_handler() is None
