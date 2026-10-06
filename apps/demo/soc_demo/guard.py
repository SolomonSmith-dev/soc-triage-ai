"""Abuse and cost guards for the public demo.

Nothing here logs alert text. Logs carry counts, status codes and a salted
hash of the client address, never the address or the alert body.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("soc_demo")


@dataclass
class DemoConfig:
    daily_token_cap: int = 200_000
    per_ip_per_minute: int = 5
    per_ip_per_day: int = 20
    max_alert_chars: int = 3000
    trusted_proxy_hops: int = 1
    state_path: str = "/tmp/soc-demo-budget.json"
    ip_salt: str = field(default="soc-demo")

    @classmethod
    def from_env(cls) -> "DemoConfig":
        e = os.environ.get
        return cls(
            daily_token_cap=int(e("DEMO_DAILY_TOKEN_CAP", cls.daily_token_cap)),
            per_ip_per_minute=int(e("DEMO_RATE_PER_MINUTE", cls.per_ip_per_minute)),
            per_ip_per_day=int(e("DEMO_RATE_PER_DAY", cls.per_ip_per_day)),
            max_alert_chars=int(e("DEMO_MAX_ALERT_CHARS", cls.max_alert_chars)),
            trusted_proxy_hops=int(e("DEMO_TRUSTED_PROXY_HOPS", cls.trusted_proxy_hops)),
            state_path=e("DEMO_STATE_PATH", cls.state_path),
            ip_salt=e("DEMO_IP_SALT", cls.ip_salt),
        )


def _today(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")


class DailyBudget:
    """Token counter that resets at 00:00 UTC. Persisted so a process restart does not refill it."""

    def __init__(self, cap: int, path: str, clock=time.time):
        self.cap, self.path, self.clock = cap, Path(path), clock
        self._lock = threading.Lock()
        self._day, self._used = _today(clock()), 0
        try:
            data = json.loads(self.path.read_text())
            if data.get("day") == self._day:
                self._used = int(data.get("tokens", 0))
        except Exception:
            pass

    def _roll(self) -> None:
        today = _today(self.clock())
        if today != self._day:
            self._day, self._used = today, 0

    @property
    def used(self) -> int:
        with self._lock:
            self._roll()
            return self._used

    @property
    def exhausted(self) -> bool:
        return self.used >= self.cap

    def resets_at(self) -> str:
        d = datetime.fromtimestamp(self.clock(), timezone.utc).date() + timedelta(days=1)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat()

    def add(self, tokens: int) -> None:
        with self._lock:
            self._roll()
            self._used += max(0, int(tokens))
            try:
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps({"day": self._day, "tokens": self._used}))
                os.replace(tmp, self.path)
            except OSError:
                logger.warning("budget state not persisted")

    def snapshot(self) -> dict:
        used = self.used
        return {"daily_token_cap": self.cap, "tokens_used": used,
                "tokens_remaining": max(0, self.cap - used), "resets_at": self.resets_at()}


class IPRateLimiter:
    """Sliding-window limits per client address, held in memory only."""

    def __init__(self, per_minute: int, per_day: int, clock=time.time, max_clients: int = 10_000):
        self.per_minute, self.per_day, self.clock, self.max_clients = per_minute, per_day, clock, max_clients
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def check(self, ip: str) -> tuple[bool, int]:
        """Record a hit if allowed. Returns (allowed, retry_after_seconds)."""
        now = self.clock()
        with self._lock:
            q = self._hits.setdefault(ip, deque())
            while q and now - q[0] > 86400:
                q.popleft()
            last_min = [t for t in q if now - t <= 60]
            if len(q) >= self.per_day:
                return False, int(86400 - (now - q[0])) + 1
            if len(last_min) >= self.per_minute:
                return False, int(60 - (now - last_min[0])) + 1
            q.append(now)
            if len(self._hits) > self.max_clients:
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > 86400]:
                    del self._hits[k]
            return True, 0


def client_ip(forwarded_for: str | None, peer: str | None, trusted_hops: int) -> str:
    """Take the address added by our own trusted proxy: the Nth entry from the right."""
    if forwarded_for and trusted_hops > 0:
        parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
        if len(parts) >= trusted_hops:
            return parts[-trusted_hops]
    return peer or "unknown"


def ip_tag(ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:10]


class RedactingFilter(logging.Filter):
    """The engine logs fragments of alert text and raw model output. In demo mode withhold the message."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = f"{record.levelname} event from {record.name} (message withheld in demo mode)"
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        return True


def install_redaction() -> None:
    for name in ("triage_engine.triage", "triage_engine.rag.retriever", "triage_engine.rag.corpus"):
        lg = logging.getLogger(name)
        if not any(isinstance(f, RedactingFilter) for f in lg.filters):
            lg.addFilter(RedactingFilter())


class MeteredClient:
    """Wraps the Anthropic client so every call is counted against the daily budget."""

    def __init__(self, inner, budget: DailyBudget):
        self.inner, self.budget = inner, budget
        self._local = threading.local()
        self.messages = self

    def create(self, **kwargs):
        resp = self.inner.messages.create(**kwargs)
        used = resp.usage.input_tokens + resp.usage.output_tokens
        self.budget.add(used)
        self._local.tokens = getattr(self._local, "tokens", 0) + used
        return resp

    def take_request_tokens(self) -> int:
        t = getattr(self._local, "tokens", 0)
        self._local.tokens = 0
        return t
