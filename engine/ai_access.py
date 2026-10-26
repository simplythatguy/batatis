"""Named AI access codes: on the hosted site, AI runs only for accounts that entered a current code.

`BATATIS_AI_ACCESS_CODES` holds named codes, such as {"judges": "...", "team": "..."}. An account
stores the name of the code it entered, never the code, so removing a name from the setting turns
AI off for every account that used it. Codes are required on Vercel, and anywhere the setting has
a code; a local engine without codes keeps every AI switch as it was.
"""
from __future__ import annotations

import contextvars
import json
import os
import secrets

# Set per request by the access guard; worker threads must run in a copy of the request's context.
GRANTED: contextvars.ContextVar[bool] = contextvars.ContextVar('ai_access_granted', default=False)


def codes() -> dict[str, str]:
    try:
        raw = json.loads(os.environ.get('BATATIS_AI_ACCESS_CODES') or '{}')
    except (ValueError, TypeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {name: code for name, code in raw.items() if isinstance(name, str) and name and isinstance(code, str) and len(code) >= 8}


def required() -> bool:
    return bool(os.environ.get('VERCEL')) or bool(codes())


def name_for(code: str | None) -> str | None:
    """The name of the code entered, checking every code in constant time."""
    supplied = (code or '').strip().encode()
    found = None
    for name, expected in codes().items():
        if secrets.compare_digest(expected.encode(), supplied):
            found = name
    return found


def granted(user) -> bool:
    if not required():
        return True
    name = getattr(user, 'ai_access', None) if user is not None else None
    return bool(name) and name in codes()


def allowed() -> bool:
    """May this request reach a paid AI service?"""
    return not required() or GRANTED.get()
