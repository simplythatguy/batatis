"""Skip tests that need the code database when that file is not on disk.

NBC(AE) text is rebuilt locally and is not committed. ``evals_dev`` already
skips that same absence. When ``BATATIS_CODEDB`` (or the default path) points
at a built database, these hooks do nothing and the tests run as written.
"""
import pytest


def _missing_code_database(exc):
    if not isinstance(exc, FileNotFoundError):
        return False
    text = str(exc)
    return 'code database not found' in text or ('codedb.sqlite' in text and 'not built' in text)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    try:
        return (yield)
    except FileNotFoundError as exc:
        if _missing_code_database(exc):
            pytest.skip(str(exc))
        raise


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    try:
        return (yield)
    except FileNotFoundError as exc:
        if _missing_code_database(exc):
            pytest.skip(str(exc))
        raise
