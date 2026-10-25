"""One process-wide lock around PDFium, which is not thread-safe, not even for separate documents.

FastAPI runs synchronous routes on worker threads, so two requests that read or draw PDFs could
otherwise call PDFium at once and crash the process. Reader functions use `@pdfium_locked` and the
`engine.pdfium.open_pdf` context manager shares this lock. The decorator holds it until the function
returns, and by then its locals, including any page,
text page or bitmap that it did not close, are released. The lock is reentrant, so a locked function
can call another. A failing call's traceback would keep its frames' PDFium objects alive past the
lock, and their finalizers could then run on another thread; those frames are cleared first.
`engine/tests/test_pdfium_lock.py` checks that every document opened in `engine/` is locked.
"""
from __future__ import annotations

import functools
import threading
import traceback
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec('P')
R = TypeVar('R')

PDFIUM_LOCK = threading.RLock()


def _release(error: BaseException) -> None:
    """Clear the finished frames of an error and of the errors chained to it (running frames stay)."""
    pending: list[BaseException | None] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        traceback.clear_frames(current.__traceback__)
        pending += [current.__cause__, current.__context__]


def pdfium_locked(fn: Callable[P, R]) -> Callable[P, R]:
    """Run `fn` holding the PDFium lock; it must not return or keep any PDFium object."""
    @functools.wraps(fn)
    def locked(*args: P.args, **kwargs: P.kwargs) -> R:
        with PDFIUM_LOCK:
            try:
                return fn(*args, **kwargs)
            except BaseException as error:
                _release(error)
                raise
    return locked
