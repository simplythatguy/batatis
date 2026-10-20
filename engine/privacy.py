"""Single import site for the privacy notice.

TODO(#24): when backend/deploy is on dev, import the shared notice constant
(web/src/privacy.ts and its engine mirror) and return it from privacy_notice.
Do not add notice copy in this file.
"""
from __future__ import annotations


def privacy_notice(*, live: bool) -> str | None:
    """The shared notice, once #24 is on dev. Nothing is shown until that import exists."""
    del live
    return None
