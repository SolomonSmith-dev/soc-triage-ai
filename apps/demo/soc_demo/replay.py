"""Cached demo mode: answer the model call from the harness recordings, never from the network.

Every request still runs observable extraction, retrieval, the refusal guardrail (stage 3) and
schema validation with technique grounding (stage 5) for real. Only `messages.create` is answered
here, and only when the prompt the engine builds hashes to a prompt the harness recorded
(tests/harness/cassettes). Any other prompt raises NotRecorded. This module builds no Anthropic
client, so cached mode cannot call a model or spend money.
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import yaml


def prompt_hash(model: str, messages: list[dict]) -> str:
    """The cassette key. Must equal tests.harness.recorder.prompt_hash; a unit test pins the two."""
    payload = json.dumps({"model": model, "messages": messages}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class NotRecorded(Exception):
    """The engine built a prompt that no recording answers."""


@dataclass(frozen=True)
class Recording:
    case_id: str
    response_text: str | None  # None reproduces an empty reply the live run saw
    input_tokens: int
    output_tokens: int
    recorded_at: str


@dataclass(frozen=True)
class HarnessCase:
    case_id: str
    category: str
    group: str  # "standard" or "adversarial:<type>", as in the harness results
    label: str
    alert: str  # verbatim, trailing newline included: the recorded prompt hash depends on every byte
    expects_refusal: bool = False  # the harness label says the retrieval guardrail must refuse it


def load_recordings(cassette_dir: str | Path) -> dict[str, Recording]:
    """Cassettes keyed by prompt hash."""
    out: dict[str, Recording] = {}
    for path in sorted(Path(cassette_dir).glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        out[d["prompt_sha256"]] = Recording(
            case_id=d["case_id"],
            response_text=d["response_text"],
            input_tokens=d["usage"]["input_tokens"],
            output_tokens=d["usage"]["output_tokens"],
            recorded_at=d.get("recorded_at", ""),
        )
    return out


def load_cases(cases_dir: str | Path) -> list[HarnessCase]:
    """Every harness case, in the harness loader's file order. Validation lives in tests/harness/loader.py."""
    out: list[HarnessCase] = []
    for path in sorted(Path(cases_dir).rglob("*.yaml")):
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        adv = d.get("adversarial")
        notes = (d.get("notes") or "").strip()
        out.append(HarnessCase(
            case_id=d["id"],
            category=d["category"],
            group="standard" if not adv else f"adversarial:{adv['type']}",
            # "migrated original" records where a case came from, not what it is
            label=notes if notes and notes != "migrated original" else d["category"].replace("_", " "),
            alert=d["alert"],
            expects_refusal=bool((d.get("expect") or {}).get("guardrail")),
        ))
    return out


class CachedClient:
    """Stands in for the Anthropic client in cached mode. It has no network path.

    `begin()` and `outcome()` bracket one request on the calling thread, the same pattern as
    MeteredClient.take_request_tokens: the demo runs each request in a worker thread.
    """

    def __init__(self, recordings: dict[str, Recording], cases: list[HarnessCase]):
        self.recordings = recordings
        self.cases = cases
        self.messages = self
        self._local = threading.local()

    def create(self, **kwargs):
        rec = self.recordings.get(prompt_hash(kwargs["model"], kwargs["messages"]))
        self._local.called, self._local.recording = True, rec
        if rec is None:
            raise NotRecorded("no recorded response for this prompt")
        usage = SimpleNamespace(input_tokens=rec.input_tokens, output_tokens=rec.output_tokens)
        if rec.response_text is None:
            return SimpleNamespace(content=[], usage=usage)
        return SimpleNamespace(content=[SimpleNamespace(text=rec.response_text)], usage=usage)

    def begin(self) -> None:
        self._local.called, self._local.recording = False, None

    def outcome(self) -> tuple[bool, Recording | None]:
        """(model call attempted, recording that answered it) for this thread's last request."""
        return getattr(self._local, "called", False), getattr(self._local, "recording", None)


def check_recordings(engine, client: CachedClient) -> dict[str, str]:
    """Run every harness case through the engine on this machine and sort it by what a visitor gets.

    replay      the engine's prompt matches a recording, so the model step replays it
    refusal     the retrieval guardrail refuses before any model call
    unservable  the engine would call the model and nothing matches: an unrecorded case, or
                embeddings that drifted on this hardware. /samples leaves these out.
    """
    kinds: dict[str, str] = {}
    for case in client.cases:
        client.begin()
        _, hits, guard = engine.triage_with_context(case.alert)
        called, rec = client.outcome()
        if rec is not None:
            kinds[case.case_id] = "replay"
        elif not called and guard and not hits:
            kinds[case.case_id] = "refusal"
        else:
            kinds[case.case_id] = "unservable"
    return kinds
