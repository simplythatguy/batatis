"""Delete cases older than 7 days, with their files.

`python -m engine.retention` runs one purge and prints how many cases it deleted.
A second run deletes nothing. Request traffic calls `maybe_purge`, which runs at most
once per interval on this process.
"""
from __future__ import annotations

import threading
import time

PURGE_INTERVAL_SECONDS = 10 * 60

_lock = threading.Lock()
_last_monotonic: float | None = None


def reset_purge_clock() -> None:
    global _last_monotonic
    with _lock:
        _last_monotonic = None


def maybe_purge(store, *, interval: float | None = None) -> int:
    """Purge at most once per interval on this process. A skipped window returns 0."""
    global _last_monotonic
    window = PURGE_INTERVAL_SECONDS if interval is None else interval
    with _lock:
        now_m = time.monotonic()
        if _last_monotonic is not None and now_m - _last_monotonic < window:
            return 0
        _last_monotonic = now_m
    try:
        return int(store.purge_expired())
    except Exception:
        with _lock:
            _last_monotonic = None
        raise


def purge_now(store=None) -> int:
    """One unthrottled purge. Safe to call again: the second call deletes nothing."""
    if store is None:
        from .store import open_store
        store = open_store()
    return int(store.purge_expired())


def main() -> None:
    print(purge_now())


if __name__ == '__main__':
    main()
