"""Record and replay wrappers around the one nondeterministic call: messages.create."""
from __future__ import annotations

import hashlib
import json
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

CASSETTE_DIR = Path(__file__).parent / "cassettes"

# Claude Sonnet 4.5 list price, USD per million tokens. Used for estimates only.
PRICE_IN_PER_M = 3.0
PRICE_OUT_PER_M = 15.0


class MissingCassetteError(Exception):
    pass


class StaleCassetteError(Exception):
    pass


class BudgetExceededError(Exception):
    pass


def prompt_hash(model: str, messages: list[dict]) -> str:
    payload = json.dumps({"model": model, "messages": messages}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def estimate_cost(tokens_in: int, tokens_out: int) -> float:
    return tokens_in / 1e6 * PRICE_IN_PER_M + tokens_out / 1e6 * PRICE_OUT_PER_M


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _response(text: str, tokens_in: int, tokens_out: int):
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=tokens_in, output_tokens=tokens_out),
    )


class Budget:
    """Shared across clients in one live run. Enforces the live-spend cap."""

    def __init__(self, max_usd: float):
        self.max_usd = max_usd
        self.spent_usd = 0.0
        self.tokens_in = 0
        self.tokens_out = 0
        self._lock = threading.Lock()

    def check(self) -> None:
        with self._lock:
            if self.spent_usd >= self.max_usd:
                raise BudgetExceededError(f"live budget ${self.max_usd:.2f} reached (${self.spent_usd:.4f} spent)")

    def add(self, tokens_in: int, tokens_out: int) -> None:
        with self._lock:
            self.tokens_in += tokens_in
            self.tokens_out += tokens_out
            self.spent_usd += estimate_cost(tokens_in, tokens_out)


class _Messages:
    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        return self._owner._create(**kwargs)


class RecordingClient:
    """Wraps a real client, writes one cassette per case."""

    def __init__(self, inner, case_id: str, cassette_dir: Path = CASSETTE_DIR, budget: Budget | None = None):
        self.inner = inner
        self.case_id = case_id
        self.cassette_dir = Path(cassette_dir)
        self.budget = budget
        self.last_error: Exception | None = None
        self.last_usage: tuple[int, int] = (0, 0)
        self.last_latency: float | None = None
        self.messages = _Messages(self)

    def _create(self, **kwargs):
        if self.budget:
            self.budget.check()
        t0 = time.time()
        try:
            resp = self.inner.messages.create(**kwargs)
        except Exception as e:
            self.last_error = e
            raise
        latency = time.time() - t0
        text = resp.content[0].text
        tin, tout = resp.usage.input_tokens, resp.usage.output_tokens
        self.last_usage, self.last_latency = (tin, tout), latency
        if self.budget:
            self.budget.add(tin, tout)
        self.cassette_dir.mkdir(parents=True, exist_ok=True)
        (self.cassette_dir / f"{self.case_id}.json").write_text(json.dumps({
            "case_id": self.case_id,
            "prompt_sha256": prompt_hash(kwargs["model"], kwargs["messages"]),
            "model": kwargs["model"],
            "response_text": text,
            "usage": {"input_tokens": tin, "output_tokens": tout},
            "latency_seconds": round(latency, 3),
            "git_sha": _git_sha(),
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }, indent=2) + "\n", encoding="utf-8")
        return resp


class ReplayClient:
    """Returns the recorded response only when the prompt hash matches."""

    def __init__(self, case_id: str, cassette_dir: Path = CASSETTE_DIR):
        self.case_id = case_id
        self.path = Path(cassette_dir) / f"{case_id}.json"
        self.last_error: Exception | None = None
        self.last_usage: tuple[int, int] = (0, 0)
        self.last_latency: float | None = None
        self.messages = _Messages(self)

    def _create(self, **kwargs):
        if not self.path.exists():
            self.last_error = MissingCassetteError(
                f"no cassette for {self.case_id}; run `python -m tests.harness.test_harness --record --only {self.case_id}`"
            )
            raise self.last_error
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data["prompt_sha256"] != prompt_hash(kwargs["model"], kwargs["messages"]):
            self.last_error = StaleCassetteError(
                f"{self.case_id}: stale cassette: prompt or retrieval output changed, re-run live and commit fresh cassettes"
            )
            raise self.last_error
        u = data["usage"]
        self.last_usage = (u["input_tokens"], u["output_tokens"])
        self.last_latency = data.get("latency_seconds")
        return _response(data["response_text"], u["input_tokens"], u["output_tokens"])


def preflight(client, model: str) -> None:
    """One 1-token call before a live run, so a bad key or workspace fails in a second, not after 100 cases."""
    client.messages.create(model=model, max_tokens=1, messages=[{"role": "user", "content": "ping"}])
