"""The site admin: the account whose email is listed in BATATIS_ADMIN_EMAILS (default: the project owner's)."""
from __future__ import annotations

import os

from fastapi import HTTPException, Request

DEFAULT_ADMIN_EMAILS = 'aabdelwaly7@gmail.com'


def admin_emails() -> frozenset[str]:
    raw = os.environ.get('BATATIS_ADMIN_EMAILS') or DEFAULT_ADMIN_EMAILS
    return frozenset(part.strip().casefold() for part in raw.split(',') if part.strip())


def is_admin(user) -> bool:
    email = getattr(user, 'email', None)
    return bool(email) and email.strip().casefold() in admin_emails()


def require_admin(request: Request):
    from .accounts import require_user
    user = require_user(request)
    if not is_admin(user):
        raise HTTPException(403, 'Only the site admin can do this')
    return user
