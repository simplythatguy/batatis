"""Skip a missing repo code database without hiding any other missing file.

``engine.codes.DEFAULT_DB`` is ``<repo>/codedb/build/codedb.sqlite``.

Skip only when ``BATATIS_CODEDB`` is unset, that repo file is absent, and the
exception is the missing-database error. That error is ``FileNotFoundError``
today and ``CodeDbMissing`` after PR #8. A set ``BATATIS_CODEDB`` that is
missing fails.

A missing file under ``reference/`` is skipped only when it is one of the
copyrighted sources kept out of git.
"""
import os
from pathlib import Path

import pytest

try:
    from engine.codes import CodeDbMissing
except ImportError:
    CodeDbMissing = FileNotFoundError

REPO = Path(__file__).resolve().parents[2]
REPO_DB = REPO / 'codedb' / 'build' / 'codedb.sqlite'
REFERENCE = REPO / 'reference'
SKIP_REASON = 'code database not built at codedb/build/codedb.sqlite'
# Exact paths. Any other missing reference file, including a forgotten asset, fails.
GIT_EXCLUDED_REFERENCE = frozenset({
    Path('codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf'),
    Path('text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl'),
})


def _is_code_db_missing(exc: BaseException) -> bool:
    """True only for the PR #8 exception, which carries no filesystem path."""
    return CodeDbMissing is not FileNotFoundError and isinstance(exc, CodeDbMissing)


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
    if configured:
        if not Path(configured).is_file():
            pytest.fail(f'BATATIS_CODEDB is set but the file is missing: {configured}')
        return
    if not REPO_DB.is_file():
        pytest.skip(SKIP_REASON)


def skip_missing_default_db(exc: BaseException) -> None:
    if os.environ.get('BATATIS_CODEDB'):
        raise exc
    if _is_code_db_missing(exc):
        if not REPO_DB.is_file():
            pytest.skip(SKIP_REASON)
        raise exc
    if not isinstance(exc, FileNotFoundError):
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
    if rel in GIT_EXCLUDED_REFERENCE and not resolved.is_file():
        pytest.skip(f'reference source not present (reference/{rel.as_posix()})')
    raise exc
