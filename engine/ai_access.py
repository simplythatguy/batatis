"""Named AI access codes: on the hosted site, AI runs only for accounts that entered a current code.

`BATATIS_AI_ACCESS_CODES` holds named codes, such as {"judges": "...", "team": "..."}; the site admin
can also make, limit and revoke codes in Settings, which keeps them (hashed) in the database. An account
stores the name of the code it entered, never the code, so removing a name from the setting turns
AI off for every account that used it. Codes are required on Vercel, and anywhere the setting has
a code; a local engine without codes keeps every AI switch as it was.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import secrets
import time
from typing import Callable

# Long random codes make guessing hopeless; the same characters work in a header and on the sign-in page.
CODE = re.compile(r'[A-Za-z0-9_-]{20,128}')

# Set per request by the access guard; worker threads must run in a copy of the request's context.
GRANTED: contextvars.ContextVar[bool] = contextvars.ContextVar('ai_access_granted', default=False)


# The name the admin code goes by. Whoever signs in with BATATIS_ADMIN_CODE is the site admin.
ADMIN = 'admin'


def codes() -> dict[str, str]:
    """The codes set in the environment, with the admin code. Codes the admin made in the app live in the database."""
    try:
        raw = json.loads(os.environ.get('BATATIS_AI_ACCESS_CODES') or '{}')
    except (ValueError, TypeError):
        raw = {}
    found = {name: code for name, code in raw.items() if isinstance(name, str) and name and name != ADMIN
             and isinstance(code, str) and CODE.fullmatch(code)} if isinstance(raw, dict) else {}
    admin = (os.environ.get('BATATIS_ADMIN_CODE') or '').strip()
    if CODE.fullmatch(admin):
        found[ADMIN] = admin
    return found


def fingerprint(code: str) -> str:
    """Stored with an account, so changing a code's value, not only removing its name, turns its accounts off."""
    return hashlib.sha256(code.encode()).hexdigest()


# The store the admin's codes live in, bound once when the app is built; unbound (tests, tools), only environment codes exist.
_STORE: Callable[[], object] | None = None
_CACHE: tuple[float, dict[str, dict]] | None = None
_CACHE_SECONDS = 5.0


def bind(store: Callable[[], object] | None) -> None:
    global _STORE
    _STORE = store
    forget()


def forget() -> None:
    """Called after the admin changes a code, so the change shows at once on this server."""
    global _CACHE
    _CACHE = None


def rows() -> dict[str, dict]:
    """The database's codes by name (managed ones and the limit or revocation of environment ones), briefly cached."""
    global _CACHE
    if _STORE is None:
        return {}
    if _CACHE is not None and time.monotonic() - _CACHE[0] < _CACHE_SECONDS:
        return _CACHE[1]
    try:
        found = {row['name']: row for row in _STORE().access_code_rows()}
    except Exception:  # a store without the tables (an older database) simply has no managed codes
        found = {}
    _CACHE = (time.monotonic(), found)
    return found


def _live(name: str) -> bool:
    if name == ADMIN:
        return True
    row = rows().get(name)
    return row is None or not row['revoked']


def current(name: str | None) -> str | None:
    """The fingerprint an account holding this code's name must carry, or None when the code is gone or revoked."""
    if not name or not _live(name):
        return None
    env = codes().get(name)
    if env is not None:
        return fingerprint(env)
    row = rows().get(name)
    return row['code_hash'] if row and row['code_hash'] else None


def required() -> bool:
    return bool(os.environ.get('VERCEL')) or bool(codes()) or any(row['code_hash'] for row in rows().values())


def find(code: str | None) -> tuple[str, str] | None:
    """(name, fingerprint) of the live code entered, checking every environment code in constant time."""
    supplied = (code or '').strip()
    if not supplied:
        return None
    found = None
    for name, expected in codes().items():
        if secrets.compare_digest(expected.encode(), supplied.encode()) and _live(name):
            found = (name, fingerprint(expected))
    if found is not None:
        return found
    digest = fingerprint(supplied)
    for name, row in rows().items():
        if row['code_hash'] and secrets.compare_digest(row['code_hash'].encode(), digest.encode()) and not row['revoked']:
            return name, digest
    return None


def name_for(code: str | None) -> str | None:
    found = find(code)
    return found[0] if found else None


def limit(name: str) -> int | None:
    if name == ADMIN:
        return None
    row = rows().get(name)
    return row['max_users'] if row else None


def granted(user) -> bool:
    if not required():
        return True
    name = getattr(user, 'ai_access', None) if user is not None else None
    expected = current(name)
    return expected is not None and secrets.compare_digest(expected, getattr(user, 'ai_access_fingerprint', None) or '')


def allowed() -> bool:
    """May this request reach a paid AI service?"""
    return not required() or GRANTED.get()
