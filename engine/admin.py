"""The site admin: whoever signed in with the admin code (BATATIS_ADMIN_CODE)."""
from __future__ import annotations

import secrets

from fastapi import HTTPException, Request


def is_admin(user) -> bool:
    """Signed in with the admin code as it is now, so changing the code in the server settings ends every admin sign-in."""
    from . import ai_access
    if user is None or getattr(user, 'ai_access', None) != ai_access.ADMIN:
        return False
    expected = ai_access.current(ai_access.ADMIN)
    return expected is not None and secrets.compare_digest(expected, getattr(user, 'ai_access_fingerprint', None) or '')


def require_admin(request: Request):
    from .accounts import require_user
    user = require_user(request)
    if not is_admin(user):
        raise HTTPException(403, 'Only the site admin can do this.')
    return user
