"""Live mode and the hosted engine call OpenAI only.

Anthropic and Jev/TypeSafe are refused before a request. They are not routed
through the spend cap.
"""
from __future__ import annotations

import os


def non_openai_allowed() -> bool:
    """False when ``BATATIS_LIVE=1`` or the process is the hosted engine."""
    return os.environ.get('BATATIS_LIVE') != '1' and not os.environ.get('VERCEL')


def refuse_non_openai(kind: str) -> None:
    """Raise before a non-OpenAI client is constructed or called."""
    if not non_openai_allowed():
        raise RuntimeError(
            f'The {kind} does not run on the deployed path. Live mode is OpenAI only.'
        )
