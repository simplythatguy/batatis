"""Live model calls are off unless BATATIS_LIVE=1 and OPENAI_API_KEY is set.

Identify (Jev screen, verifier) and completeness model review call `authorize` before a
provider request and `record` after. The key is never logged or returned.
Over the daily cap the caller takes the offline path with source `offline-cap`.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

# USD per 1M tokens, input then output. Unknown models use the conservative pair so the
# pre-call estimate does not under-count the cap.
PRICES = {
    'gpt-4.1-mini': (Decimal('0.40'), Decimal('1.60')),
    'gpt-4.1': (Decimal('2'), Decimal('8')),
}
CONSERVATIVE = (Decimal('10'), Decimal('30'))
DEFAULT_MODEL = 'gpt-4.1-mini'


class OfflineLLM(Exception):
    def __init__(self, source: str):
        self.source = source
        super().__init__(source)


class SpendStoreRequired(RuntimeError):
    """VERCEL is set and the spend ledger is not Postgres, so the memory ledger must not be used."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    source: str
    reserved_usd: Decimal = Decimal('0')


class SlidingWindow:
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
        """Seconds until the oldest hit in the window expires. At least 1."""
        now = time.monotonic()
        with self._lock:
            kept = [stamp for stamp in self.events.get(key, []) if now - stamp < window_s]
        if not kept:
            return 1
        return max(1, int(window_s - (now - min(kept)) + 0.999))

    def reset(self) -> None:
        with self._lock:
            self.events.clear()


class MemorySpend:
    def __init__(self):
        self.by_day: dict[str, Decimal] = {}
        self._lock = threading.Lock()

    def try_reserve(self, usd: Decimal, cap: Decimal) -> bool:
        day = date.today().isoformat()
        with self._lock:
            current = self.by_day.get(day, Decimal('0'))
            if current + usd > cap:
                return False
            self.by_day[day] = current + usd
            return True

    def adjust(self, delta: Decimal) -> None:
        day = date.today().isoformat()
        with self._lock:
            self.by_day[day] = self.by_day.get(day, Decimal('0')) + delta

    def today(self) -> Decimal:
        return self.by_day.get(date.today().isoformat(), Decimal('0'))

    def reset(self) -> None:
        with self._lock:
            self.by_day.clear()


_memory = MemorySpend()
_llm_window = SlidingWindow()
_search_window = SlidingWindow()
_spend = None
_spend_lock = threading.Lock()


def reset_for_tests() -> None:
    global _spend
    _memory.reset()
    _llm_window.reset()
    _search_window.reset()
    with _spend_lock:
        if _spend is not None:
            _spend.close()
        _spend = None


def live_enabled() -> bool:
    return os.environ.get('BATATIS_LIVE') == '1' and bool((os.environ.get('OPENAI_API_KEY') or '').strip())


def daily_cap() -> Decimal:
    raw = (os.environ.get('BATATIS_DAILY_SPEND_CAP_USD') or '5').strip()
    return Decimal(raw)


def estimate_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    inn, out = PRICES.get(model, CONSERVATIVE)
    usd = (Decimal(input_tokens) * inn + Decimal(output_tokens) * out) / Decimal(1_000_000)
    return usd.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)


def _ledger():
    """Memory cap for a local file store. On Vercel the cap is the Postgres ledger only.

    A set `VERCEL` with any other `BATATIS_STORE` raises SpendStoreRequired. The per-instance
    memory ledger is not a fallback there.
    """
    global _spend
    store = (os.environ.get('BATATIS_STORE') or '').strip().lower()
    if os.environ.get('VERCEL') and store != 'postgres':
        raise SpendStoreRequired(
            'Refusing the spend cap: VERCEL is set and BATATIS_STORE is not postgres. '
            'The per-instance memory ledger is not used on Vercel.')
    if store != 'postgres':
        return _memory
    with _spend_lock:
        if _spend is None:
            from .store_postgres import PostgresSpend
            _spend = PostgresSpend()
        return _spend


def _reserve(ledger, usd: Decimal, cap: Decimal) -> bool:
    if hasattr(ledger, 'try_reserve_spend'):
        return ledger.try_reserve_spend(usd, cap)
    return ledger.try_reserve(usd, cap)


def _adjust(ledger, delta: Decimal) -> None:
    if hasattr(ledger, 'adjust_spend'):
        ledger.adjust_spend(delta)
    else:
        ledger.adjust(delta)


def _rate_limit(name: str, default_limit: str, default_window: str) -> tuple[int, float]:
    limit = int(os.environ.get(name + '_LIMIT') or default_limit)
    window = float(os.environ.get(name + '_WINDOW_SECONDS') or default_window)
    return limit, window


def authorize(*, model: str = DEFAULT_MODEL, max_input_tokens: int, max_output_tokens: int,
              client_ip: str | None = None) -> Decision:
    """Reserve the worst-case cost. Refuse without calling a provider when the gate is shut."""
    if not live_enabled():
        return Decision(False, 'offline')
    limit, window = _rate_limit('BATATIS_LLM_RATE', '20', '600')
    if not _llm_window.allow(client_ip or 'local', limit, window):
        return Decision(False, 'rate-limited')
    estimate = estimate_usd(model, max_input_tokens, max_output_tokens)
    try:
        ledger = _ledger()
    except SpendStoreRequired:
        return Decision(False, 'offline-cap')
    if not _reserve(ledger, estimate, daily_cap()):
        return Decision(False, 'offline-cap')
    return Decision(True, 'live', estimate)


def record(*, model: str, input_tokens: int, output_tokens: int, reserved_usd: Decimal | float = 0) -> None:
    """Replace the reservation with actual token cost. Does not log credentials."""
    try:
        ledger = _ledger()
    except SpendStoreRequired:
        return
    actual = estimate_usd(model, input_tokens, output_tokens)
    _adjust(ledger, actual - Decimal(str(reserved_usd)))


def search_retry_after(client_ip: str) -> int | None:
    """None when this IP may search. Otherwise the Retry-After delay in seconds.

    Default budget is 60 searches per 10 minutes per IP.
    """
    limit, window = _rate_limit('BATATIS_SEARCH_RATE', '60', '600')
    key = client_ip or 'unknown'
    if _search_window.allow(key, limit, window):
        return None
    return _search_window.retry_after(key, window)


def _first_hop(value: str | None) -> str | None:
    if not value:
        return None
    hop = value.split(',')[0].strip()
    return hop or None


def client_ip_from(request) -> str:
    """Vercel's client IP, then the first X-Forwarded-For hop, then the peer address."""
    for header in ('x-vercel-forwarded-for', 'x-forwarded-for'):
        hop = _first_hop(request.headers.get(header))
        if hop:
            return hop
    client = request.client
    return client.host if client and client.host else 'unknown'
