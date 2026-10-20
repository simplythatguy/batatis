"""Skip a missing repo code database without hiding any other missing file.

PR #12 makes ``engine.codes.DEFAULT_DB`` ``<repo>/codedb/build/codedb.sqlite``.
This hook assumes that path. It does not edit ``engine/codes.py``.

Skip only when ``BATATIS_CODEDB`` is unset, that repo file is absent, and the
exception names that same file. A set ``BATATIS_CODEDB`` that is missing fails.
"""
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REPO_DB = REPO / 'codedb' / 'build' / 'codedb.sqlite'
REFERENCE = REPO / 'reference'
SKIP_REASON = 'code database not built at codedb/build/codedb.sqlite'


def install_repo_default() -> None:
    """Point engine lookups at the repo build unless BATATIS_CODEDB is set."""
    if os.environ.get('BATATIS_CODEDB'):
        return
    import engine.codes as codes

    def default_db() -> Path:
        override = os.environ.get('BATATIS_CODEDB')
        return Path(override) if override else REPO_DB

    codes.DEFAULT_DB = REPO_DB
    codes.default_db = default_db


def _opened_path(exc: FileNotFoundError) -> Path | None:
    if exc.filename:
        return Path(exc.filename)
    text = str(exc)
    prefix = 'code database not found: '
    suffix = ' (set BATATIS_CODEDB)'
    if text.startswith(prefix) and text.endswith(suffix):
        return Path(text[len(prefix):-len(suffix)])
    marker = ' not built.'
    if marker in text:
        return Path(text.split(marker, 1)[0])
    # pdfium raises FileNotFoundError(path) with the path as the whole message.
    if text.startswith('/') and 'reference' in Path(text).parts:
        return Path(text)
    return None


def require_repo_db() -> None:
    """Fail when BATATIS_CODEDB is set but missing. Skip when the repo build is absent."""
    configured = os.environ.get('BATATIS_CODEDB')
    if configured and not Path(configured).is_file():
        pytest.fail(f'BATATIS_CODEDB is set but the file is missing: {configured}')
    if not REPO_DB.is_file():
        pytest.skip(SKIP_REASON)


def skip_missing_default_db(exc: BaseException) -> None:
    if not isinstance(exc, FileNotFoundError):
        raise exc
    if os.environ.get('BATATIS_CODEDB'):
        raise exc
    opened = _opened_path(exc)
    if opened is None:
        raise exc
    resolved = opened.resolve()
    if not REPO_DB.is_file() and resolved == REPO_DB.resolve():
        pytest.skip(SKIP_REASON)
    try:
        rel = resolved.relative_to(REFERENCE.resolve())
    except ValueError:
        rel = None
    if rel is not None and not resolved.is_file():
        pytest.skip(f'reference source not present (reference/{rel})')
    raise exc
