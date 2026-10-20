"""Per-IP limit for /identify. This is not a spend cap.

The spend cap is the Postgres total in engine.spend (BATATIS_TOTAL_BUDGET_USD,
default 20). There is no daily cap. BATATIS_DAILY_SPEND_CAP_USD is not read.
"""
from __future__ import annotations

import os
import threading
import time


class SlidingWindow:
    """Hits kept in this process. The limit is per instance, for one IP."""

    def __init__(self):
        self.events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_s: float) -> bool:
        now = time.monotonic()
        with self._lock:
            kept = [stamp for stamp in self.events.get(key, []) if now - stamp < window_s]
            if len(kept) >= limit:
                self.events[key] = kept
                return False
            kept.append(now)
            self.events[key] = kept
            return True

    def retry_after(self, key: str, window_s: float) -> int:
        now = time.monotonic()
        with self._lock:
            kept = [stamp for stamp in self.events.get(key, []) if now - stamp < window_s]
        if not kept:
            return 1
        return max(1, int(window_s - (now - min(kept)) + 0.999))

    def reset(self) -> None:
        with self._lock:
            self.events.clear()


_llm_window = SlidingWindow()


def reset_for_tests() -> None:
    _llm_window.reset()


def llm_budget() -> tuple[int, float]:
    """Requests per window. A bad value refuses the call (limit 0) instead of failing open."""
    try:
        limit = int((os.environ.get('BATATIS_LLM_RATE_LIMIT') or '20').strip())
        window = float((os.environ.get('BATATIS_LLM_RATE_WINDOW_SECONDS') or '600').strip())
    except ValueError:
        return 0, 1.0
    if limit < 0 or window <= 0:
        return 0, 1.0
    return limit, window


def llm_retry_after(client_ip: str) -> int | None:
    """None when this IP may call /identify. Otherwise the Retry-After delay in seconds."""
    limit, window = llm_budget()
    key = client_ip or 'unknown'
    if _llm_window.allow(key, limit, window):
        return None
    return _llm_window.retry_after(key, window)


def client_ip_from(request) -> str:
    """First forwarded hop, else the peer address. The value is not logged."""
    for header in ('x-vercel-forwarded-for', 'x-forwarded-for'):
        raw = request.headers.get(header)
        if not raw:
            continue
        hop = raw.split(',')[0].strip()
        if hop:
            return hop
    client = request.client
    return client.host if client and client.host else 'unknown'
