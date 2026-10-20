"""Per-IP limits for /identify and /ccmc/search. This is not a spend cap.

The spend cap is the Postgres total in engine.spend (BATATIS_TOTAL_BUDGET_USD,
default 20). There is no daily cap. BATATIS_DAILY_SPEND_CAP_USD is not read.

Each limit is an in-memory window on this process. It is per instance. It is
not backed by Postgres, so two engine instances do not share a count.
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
            self._evict(now, window_s)
            kept = [stamp for stamp in self.events.get(key, []) if now - stamp < window_s]
            if len(kept) >= limit:
                self.events[key] = kept
                return False
            kept.append(now)
            self.events[key] = kept
            return True

    def _evict(self, now: float, window_s: float) -> None:
        """Drop IPs whose stamps are all outside the window. Caller holds the lock."""
        stale = [
            ip for ip, stamps in self.events.items()
            if not any(now - stamp < window_s for stamp in stamps)
        ]
        for ip in stale:
            del self.events[ip]

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
_search_window = SlidingWindow()


def reset_for_tests() -> None:
    _llm_window.reset()
    _search_window.reset()


def _budget(limit_name: str, limit_default: str, window_name: str, window_default: str) -> tuple[int, float]:
    """Requests per window. A bad value refuses the call (limit 0) instead of failing open."""
    try:
        limit = int((os.environ.get(limit_name) or limit_default).strip())
        window = float((os.environ.get(window_name) or window_default).strip())
    except ValueError:
        return 0, 1.0
    if limit < 0 or window <= 0:
        return 0, 1.0
    return limit, window


def llm_budget() -> tuple[int, float]:
    return _budget('BATATIS_LLM_RATE_LIMIT', '20', 'BATATIS_LLM_RATE_WINDOW_SECONDS', '600')


def search_budget() -> tuple[int, float]:
    return _budget('BATATIS_SEARCH_RATE_LIMIT', '60', 'BATATIS_SEARCH_RATE_WINDOW_SECONDS', '600')


def _retry_after(window: SlidingWindow, budget, client_ip: str) -> int | None:
    limit, seconds = budget()
    key = client_ip or 'unknown'
    if window.allow(key, limit, seconds):
        return None
    return window.retry_after(key, seconds)


def llm_retry_after(client_ip: str) -> int | None:
    """None when this IP may call /identify. Otherwise the Retry-After delay in seconds."""
    return _retry_after(_llm_window, llm_budget, client_ip)


def search_retry_after(client_ip: str) -> int | None:
    """None when this IP may call /ccmc/search. Otherwise the Retry-After delay in seconds."""
    return _retry_after(_search_window, search_budget, client_ip)


def client_ip_from(request) -> str:
    """x-vercel-forwarded-for first, then X-Forwarded-For, else the peer. Not logged."""
    for header in ('x-vercel-forwarded-for', 'x-forwarded-for'):
        raw = request.headers.get(header)
        if not raw:
            continue
        hop = raw.split(',')[0].strip()
        if hop:
            return hop
    client = request.client
    return client.host if client and client.host else 'unknown'
