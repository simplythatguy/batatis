"""Live model calls require an explicit switch and the provider's credential.

BATATIS_LIVE controls providers by default; BATATIS_LIVE_ELEPHANT can enable only
the free Elephant route while the global switch keeps unrelated providers off.

Completeness model review and the assistant call `authorize` before a provider request and
`record` after. Identify (Jev screen and rerank, OpenAI or Anthropic verifier) calls `reserve`,
then `settle` with the reported tokens, or `release` when the call fails. The key is never
logged or returned. Over the daily cap the caller takes the offline path with source `offline-cap`.

`BATATIS_PROVIDER=fake` lets identify's offline fakes pass this gate as if live, so the spend
path is exercised without keys. It is refused when `VERCEL` is set and has no effect on
`authorize` (the assistant and completeness never treat a fake as live).
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

# USD per 1M tokens, input then output. Unknown models use the conservative pair so the
# pre-call estimate does not under-count the cap.
# Identify's pinned models are listed by their exact ids. Anthropic prices are the first-party
# list prices (claude-api reference, cached 2026-10-06). Jev's input price is the one measured in
# docs/research/2026-10-20-vision/jev-benchmark/README.md ($0.042 per million input tokens); no
# output price is published there, so output is priced the same (Jev answers are a few tokens each).
PRICES = {
    'gpt-4.1-mini': (Decimal('0.40'), Decimal('1.60')),
    'gpt-4.1': (Decimal('2'), Decimal('8')),
    'gpt-4.1-mini-2025-04-14': (Decimal('0.40'), Decimal('1.60')),
    'gpt-4.1-2025-04-14': (Decimal('2'), Decimal('8')),
    'claude-sonnet-5-5': (Decimal('2'), Decimal('10')),
    'claude-opus-5-5': (Decimal('4'), Decimal('20')),
    'jev-1.13.0': (Decimal('0.042'), Decimal('0.042')),
    # The exact free Decisions request route only; no paid aliases inherit this price.
    'baseten/elephant-1:free': (Decimal('0'), Decimal('0')),
    # GPT Luna, identify's verifier. OpenAI's Standard-tier list price (developers.openai.com/api/docs/pricing,
    # read 2026-10-21) is $0.10 in / $0.50 out up to 272K input tokens and $0.20 / $0.75 above. Both the
    # reservation and the settlement use the long-context pair, an over-estimate for every identify call,
    # so the ledger never under-counts. Reasoning tokens are billed as output and arrive in completion_tokens.
    'gpt-6-luna': (Decimal('0.20'), Decimal('0.75')),
    # GPT Sol 6.1, document review at low effort only. Standard-tier list price (same page, read 2026-10-25):
    # $2 / $10 up to 272K input tokens and $4 / $15 above; the long-context pair is used, as for Luna.
    'gpt-6.1-sol': (Decimal('4'), Decimal('15')),
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
    """In-memory hits for this process. A search or model limit is per instance, not global."""

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
_assist_window = SlidingWindow()
_relevance_window = SlidingWindow()
_relevance_daily = SlidingWindow()
_identify_window = SlidingWindow()
_spend = None
_spend_lock = threading.Lock()


def reset_for_tests() -> None:
    global _spend
    _memory.reset()
    _llm_window.reset()
    _search_window.reset()
    _assist_window.reset()
    _relevance_window.reset()
    _relevance_daily.reset()
    _identify_window.reset()
    with _spend_lock:
        if _spend is not None:
            _spend.close()
        _spend = None


def live_enabled(provider: str = 'openai') -> bool:
    from . import ai_access
    if not ai_access.allowed():
        return False
    if provider == 'elephant':
        switch = os.environ.get('BATATIS_LIVE_ELEPHANT') or os.environ.get('BATATIS_LIVE')
        return switch == '1' and bool((os.environ.get('OPENROUTER_API_KEY') or '').strip())
    key = {'openai': 'OPENAI_API_KEY', 'openai_decisions': 'OPENAI_API_KEY',
           'anthropic': 'ANTHROPIC_API_KEY', 'xai': 'XAI_API_KEY'}.get(provider)
    return key is not None and os.environ.get('BATATIS_LIVE') == '1' and bool((os.environ.get(key) or '').strip())


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
              client_ip: str | None = None, provider: str = 'openai') -> Decision:
    """Reserve the worst-case cost. Refuse without calling a provider when the gate is shut."""
    if provider == 'xai' or not live_enabled(provider):
        # Realtime voice is billed in time/text inputs, never token estimates.
        return Decision(False, 'offline')
    return _authorize_cost(estimate_usd(model, max_input_tokens, max_output_tokens), client_ip)


def _authorize_cost(estimate: Decimal, client_ip: str | None) -> Decision:
    """Shared LLM rate window and atomic dollar ledger, including non-token billing."""
    limit, window = _rate_limit('BATATIS_LLM_RATE', '20', '600')
    if not _llm_window.allow(client_ip or 'local', limit, window):
        return Decision(False, 'rate-limited')
    try:
        ledger = _ledger()
    except SpendStoreRequired:
        return Decision(False, 'offline-cap')
    if not _reserve(ledger, estimate, daily_cap()):
        return Decision(False, 'offline-cap')
    return Decision(True, 'live', estimate)


def authorize_voice(*, client_ip: str, max_seconds: int, max_text_inputs: int) -> Decision:
    """Reserve a bounded relay's full allowance; never settle voice as text tokens.

    Official xAI pricing, checked 2026-10-22: $0.08/min + $0.004/text input.
    The relay bounds connection/audio time and ALL non-audio upstream messages.
    Once a connection is attempted this entire reservation is retained, including
    refusal, timeout and cancellation. Reported token counts cannot price minutes.
    """
    if not (1 <= max_seconds <= 60 and 1 <= max_text_inputs <= 20):
        raise ValueError('Voice allowance exceeds the bounded session policy')
    if not live_enabled('xai'):
        return Decision(False, 'offline')
    limit, window = _assist_limits()
    if not _assist_window.allow(client_ip, limit, window):
        return Decision(False, 'rate-limited')
    # Round time UP to whole minutes, even for a short/failed call.
    minutes = (max_seconds + 59) // 60
    estimate = Decimal(minutes) * Decimal('0.08') + Decimal(max_text_inputs) * Decimal('0.004')
    return _authorize_cost(estimate.quantize(Decimal('0.000001')), client_ip)


def authorize_assist(*, model: str, max_input_tokens: int, max_output_tokens: int,
                     client_ip: str, provider: str) -> Decision:
    """The assistant has its own IP budget, plus the shared LLM budget and spend cap."""
    if not live_enabled(provider):
        return Decision(False, 'offline')
    limit, window = _assist_limits()
    if not _assist_window.allow(client_ip, limit, window):
        return Decision(False, 'rate-limited')
    return authorize(model=model, provider=provider, max_input_tokens=max_input_tokens,
                     max_output_tokens=max_output_tokens, client_ip=client_ip)


def _assist_limits() -> tuple[int, float]:
    try:
        limit = int(os.environ.get('BATATIS_ASSIST_RATE_LIMIT') or os.environ.get('BATATIS_ASSIST_RATE') or '12')
        window = float(os.environ.get('BATATIS_ASSIST_RATE_WINDOW_SECONDS') or '600')
    except ValueError:
        limit, window = 12, 600.0  # A malformed setting must not turn /assist into a 500.
    return limit, window


def assist_retry_after(client_ip: str) -> int:
    """Seconds until the assistant or the shared LLM window frees a slot (at least 1)."""
    _, window = _assist_limits()
    llm_limit, llm_window = _rate_limit('BATATIS_LLM_RATE', '20', '600')
    return max(1, _assist_window.retry_after(client_ip, window), _llm_window.retry_after(client_ip, llm_window))


PROVIDERS = ('openai', 'openai_decisions', 'anthropic', 'jev', 'elephant')


def fake_providers() -> bool:
    """True when identify runs on its offline fakes. Never on Vercel."""
    return (os.environ.get('BATATIS_PROVIDER') or '').strip().lower() == 'fake' and not os.environ.get('VERCEL')


def provider_enabled(provider: str) -> bool:
    """Live switch for identify's providers. Jev's credential is the vendored keystore's."""
    if provider not in PROVIDERS:
        return False
    if fake_providers():
        return True
    from . import ai_access
    if not ai_access.allowed():
        return False
    if provider != 'jev':
        return live_enabled(provider)
    if os.environ.get('BATATIS_LIVE') != '1':
        return False                                   # checked first, so tests never touch the keychain
    from .identify.jevkit import keystore
    from .identify.screen import JEV_PROVIDER
    return bool(keystore.resolve(JEV_PROVIDER))


def reserve(*, provider: str, model: str, max_input_tokens: int, max_output_tokens: int,
            client_ip: str | None = None, rate: bool = False) -> Decision:
    """Reserve the worst-case cost of one identify provider call. `rate` also takes an LLM window slot.

    Identify takes its per-IP slot once per run (`identify_retry_after`), so stage calls pass rate=False.
    """
    if provider == 'elephant' and model != 'baseten/elephant-1:free':
        return Decision(False, 'model-not-admitted')
    if not provider_enabled(provider):
        return Decision(False, 'offline')
    if rate:
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


def settle(decision: Decision, *, model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Replace a reservation with the reported tokens. Returns the settled cost."""
    actual = estimate_usd(model, input_tokens, output_tokens)
    if decision.allowed:
        record(model=model, input_tokens=input_tokens, output_tokens=output_tokens,
               reserved_usd=decision.reserved_usd)
    return actual


def release(decision: Decision) -> None:
    """Give back a reservation whose call failed before it reported usage."""
    if decision.allowed:
        record(model=DEFAULT_MODEL, input_tokens=0, output_tokens=0, reserved_usd=decision.reserved_usd)


def identify_retry_after(client_ip: str) -> int | None:
    """None when this IP may start an identify run. Default 6 runs per 10 minutes per IP, per instance."""
    limit, window = _rate_limit('BATATIS_IDENTIFY_RATE', '6', '600')
    key = client_ip or 'unknown'
    if _identify_window.allow(key, limit, window):
        return None
    return _identify_window.retry_after(key, window)


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

    Default budget is 60 searches per 10 minutes per IP, on this instance.
    `GET /code/search` and `GET /ccmc/search` share the window.
    """
    limit, window = _rate_limit('BATATIS_SEARCH_RATE', '60', '600')
    key = client_ip or 'unknown'
    if _search_window.allow(key, limit, window):
        return None
    return _search_window.retry_after(key, window)


def relevance_retry_after(client_ip: str) -> int | None:
    """Per-IP scoring starts and a process-wide UTC daily run cap (including failed runs).

    Like the search limiter, these are per process and reset on restart. Jev's run budget
    is separate from the OpenAI token-price ledger; no dollar price is assumed for Jev.
    """
    limit, window = _rate_limit('BATATIS_RELEVANCE_RATE', '2', '600')
    key = client_ip or 'unknown'
    if not _relevance_window.allow(key, limit, window):
        return _relevance_window.retry_after(key, window)
    stamp = datetime.now(timezone.utc)
    daily_limit = int(os.environ.get('BATATIS_RELEVANCE_DAILY_RUNS') or '20')
    if _relevance_daily.allow(stamp.date().isoformat(), daily_limit, 86400):
        return None
    midnight = datetime.combine(stamp.date() + timedelta(days=1), datetime.min.time(), timezone.utc)
    return max(1, int((midnight - stamp).total_seconds() + 0.999))


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
