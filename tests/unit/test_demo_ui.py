"""The Streamlit page, run offline with AppTest. httpx is replaced by a fake API, so no server or network is used.

Skipped when streamlit is not installed (it is the demo's [ui] extra); CI installs it in the unit job.
"""
from pathlib import Path

import httpx
import pytest

st = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from triage_engine.case_package import build_case_package  # noqa: E402
from triage_engine.extractors import extract_observables  # noqa: E402

UI = Path(__file__).resolve().parents[2] / "apps" / "demo" / "soc_demo" / "ui.py"
T4 = "40 failed SSH logins from 185.220.101.45 against srv-bastion-07, then one success\n"
OOC4 = "Cafeteria menu for Thursday: soup and a fruit cup\n"
OOC3 = "Employee requested vacation December 12 to 20\n"
SAMPLES = [
    {"id": "T4_brute_force_ssh", "category": "brute_force", "group": "standard", "label": "brute force",
     "expects_refusal": False, "kind": "replay", "alert": T4},
    {"id": "OOC-004", "category": "noise", "group": "adversarial:noise", "expects_refusal": True,
     "label": "out of corpus, retrieval guardrail must refuse", "kind": "refusal", "alert": OOC4},
    {"id": "OOC-003", "category": "noise", "group": "adversarial:noise", "expects_refusal": True,
     "label": "out of corpus, retrieval guardrail must refuse", "kind": "replay", "alert": OOC3},
]
REPLAY = {"X-Demo-Mode": "cached", "X-Demo-Replay-Case": "T4_brute_force_ssh",
          "X-Demo-Recorded-At": "2026-10-09T04:36:30Z"}


def envelope(alert, severity="high", guard=False, chunks=True):
    res = {"severity": severity, "confidence": "high", "mitre_techniques": ["T1110"] if chunks else [],
           "summary": "SSH brute force with a later success.", "recommended_actions": ["Block the source"],
           "escalate": severity != "informational", "reasoning": "r",
           "sources": ["log_analysis_linux.md"] if chunks else [], "retrieval_score": 0.5 if chunks else 0.0}
    hits = [({"id": "log_analysis_linux_3", "source": "log_analysis_linux.md", "text": "ctx"}, 0.5)] if chunks else []
    return build_case_package(alert_raw=alert, observables=extract_observables(alert), triage_result=res,
                              retrieval_hits=hits, guardrail_triggered=guard)


def resp(status, body, headers=None, method="GET"):
    return httpx.Response(status, json=body, headers=headers or {}, request=httpx.Request(method, "http://api/x"))


class FakeAPI:
    def __init__(self, mode="cached", triage=(200, None, REPLAY), down=False):
        self.mode, self.triage, self.down, self.posted, self.budget_calls = mode, triage, down, [], 0

    def get(self, url, timeout=None, **kw):
        if self.down:
            raise httpx.ConnectError("down")
        path = url.rsplit("/", 1)[-1]
        if path == "healthz":
            return resp(200, {"status": "ok", "demo_mode": True, "mode": self.mode})
        if path == "samples":
            return resp(200, [{**s, "kind": "live"} for s in SAMPLES] if self.mode == "live" else SAMPLES)
        if path == "budget":
            self.budget_calls += 1
            return resp(200, {"mode": "live", "daily_token_cap": 200_000, "tokens_used": 1000 * self.budget_calls,
                              "tokens_remaining": 200_000 - 1000 * self.budget_calls,
                              "resets_at": "2026-11-18T00:00:00+00:00"})
        raise AssertionError(url)

    def post(self, url, json=None, timeout=None, headers=None):
        self.posted.append(json)
        status, body, hdrs = self.triage
        return resp(status, body if body is not None else envelope(json["alert"]), hdrs, "POST")


@pytest.fixture
def page(monkeypatch):
    def start(api):
        monkeypatch.setattr(httpx, "get", api.get)
        monkeypatch.setattr(httpx, "post", api.post)
        st.cache_data.clear()
        at = AppTest.from_file(str(UI), default_timeout=30)
        at.run()
        assert not at.exception, at.exception
        return at
    return start


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, at.exception


def texts(at, kind):
    return " | ".join(str(e.value) for e in getattr(at, kind))


def run_triage(at, alert=None):
    if alert is not None:
        at.text_area(key="alert").input(alert).run()
    click(at, "Run triage")


def test_cached_page_offers_recorded_alerts_with_honest_labels(page):
    at = page(FakeAPI())
    labels = {b.label for b in at.button}
    assert {"SSH brute force (Tor exit)", "Out of scope (refusal)"} <= labels
    assert "LSASS credential dump" not in labels  # not listed by /samples, so not offered
    assert "3 recorded harness alerts" in [e.label for e in at.expander]
    options = at.selectbox[0].options
    assert "T4_brute_force_ssh: brute force; recorded answer" in options
    assert "OOC-004: out of corpus, retrieval guardrail must refuse; refused at retrieval" in options
    assert any(o.startswith("OOC-003:") and "known miss" in o for o in options)
    assert "no model calls" in texts(at, "caption")


def test_replayed_triage_names_its_recording(page):
    api = FakeAPI()
    at = page(api)
    click(at, "SSH brute force (Tor exit)")
    assert at.text_area(key="alert").value == T4
    run_triage(at)
    assert api.posted == [{"alert": T4}]
    assert [m.value for m in at.metric][:2] == ["HIGH", "Yes"]
    cap = texts(at, "caption")
    assert "replayed from the harness recording of case `T4_brute_force_ssh`" in cap and "2026-10-09" in cap
    assert "Known guardrail miss" not in cap


def test_whitespace_only_edit_still_sends_the_recorded_text(page):
    api = FakeAPI()
    at = page(api)
    run_triage(at, "  " + T4.strip() + "\n\n\n")
    assert api.posted[-1] == {"alert": T4}


def test_real_edit_is_sent_as_typed(page):
    api = FakeAPI(triage=(404, {"status": "not_recorded", "message": "m",
                                "retrieval": {"avg_score": 0.41, "chunks": [{"source": "log_analysis_linux.md",
                                                                             "score": 0.41}]}}, {}))
    at = page(api)
    run_triage(at, T4.replace("40", "41"))
    assert api.posted[-1] == {"alert": T4.replace("40", "41")}
    assert "No recorded model response matches this exact text" in texts(at, "info")
    assert "Retrieval ran live on this alert" in texts(at, "markdown") and "log_analysis_linux.md" in texts(at, "markdown")


def test_retrieval_refusal_says_no_model_call_was_made(page):
    at = page(FakeAPI(triage=(200, envelope(OOC4, "informational", guard=True, chunks=False), {})))
    click(at, "Out of scope (refusal)")
    run_triage(at)
    assert "Guardrail triggered" in texts(at, "warning")
    assert "No model call was made" in texts(at, "caption")


def test_documented_guardrail_miss_is_labelled(page):
    headers = {**REPLAY, "X-Demo-Replay-Case": "OOC-003"}
    at = page(FakeAPI(triage=(200, envelope(OOC3, "informational"), headers)))
    run_triage(at, OOC3)
    assert "Known guardrail miss, documented in model_card.md" in texts(at, "caption")


@pytest.mark.parametrize("status,body", [
    (429, {"status": "rate_limited", "message": "Too many requests from your address. Try again in 40 seconds."}),
    (503, {"status": "engine_unavailable", "message": "The demo backend failed to load."}),
    (500, {"status": "error", "message": "Internal error. The demo logs only the error type."}),
])
def test_refusals_show_the_api_message(page, status, body):
    at = page(FakeAPI(triage=(status, body, {})))
    run_triage(at, T4)
    assert body["message"] in texts(at, "info")


def test_backend_down_shows_starting_notice(page):
    at = page(FakeAPI(down=True))
    assert "still starting" in texts(at, "warning")
    assert "Samples unavailable" in texts(at, "caption")


def test_live_mode_shows_one_budget_figure_after_a_run(page):
    api = FakeAPI(mode="live", triage=(200, None, {"X-Demo-Mode": "live"}))
    at = page(api)
    run_triage(at, T4)
    budget = [m for m in at.metric if m.label == "Demo tokens left today"]
    assert len(budget) == 1 and api.budget_calls >= 2
    assert "replayed" not in texts(at, "caption")
    assert api.posted[-1] == {"alert": T4}



def test_model_text_is_shown_without_markdown(page):
    # Streamlit's Markdown would autolink URLs even in escaped text, and an injected alert could add an image
    text = "Block http://198.51.100.9/x.sh, mail phish@evil.example, see www.example.com ![p](https://a.example/t.png)"
    body = envelope(T4)
    body["triage"].update(summary=text, recommended_actions=[text], reasoning=text)
    at = page(FakeAPI(triage=(200, body, REPLAY)))
    run_triage(at, T4)
    assert [e.value for e in at.text] == [text, "1. " + text, text]
    assert "198.51.100.9" not in texts(at, "markdown") + texts(at, "caption")
