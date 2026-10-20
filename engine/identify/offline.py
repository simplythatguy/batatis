"""Offline demo mode for identify.

BATATIS_OFFLINE=1 forces the cache. The same mode is selected when OPENAI_API_KEY
is absent, and when a live provider call fails with an authentication, network,
or timeout error. A cache miss is an empty result, not a guessed citation.
"""
from __future__ import annotations

import os

import httpx


class ProviderOutage(RuntimeError):
    """The live model call did not succeed. Identify should serve the demo cache."""


def _flag_on(name: str) -> bool:
    return os.environ.get(name, '').strip().lower() in {'1', 'true', 'yes', 'on'}


def offline_mode() -> bool:
    if _flag_on('BATATIS_OFFLINE'):
        return True
    return not (os.environ.get('OPENAI_API_KEY') or '').strip()


def http_live() -> bool:
    """POST /cases/{id}/identify calls a provider only when a key is set and BATATIS_LIVE is on.

    The benchmark calls pipeline.run directly and does not read BATATIS_LIVE.
    """
    if offline_mode():
        return False
    return _flag_on('BATATIS_LIVE')


def is_provider_outage(exc: BaseException) -> bool:
    """Auth, network, and timeout failures from the HTTP model client.

    A bare ConnectionError is not included: the injected Jev judge uses that
    class for its own fallback.
    """
    if isinstance(exc, ProviderOutage):
        return True
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, TimeoutError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None and exc.response.status_code in {401, 403}:
        return True
    return type(exc).__name__ in {'APITimeoutError', 'APIConnectionError', 'AuthenticationError', 'PermissionDeniedError'}
