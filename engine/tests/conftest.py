"""Skip a missing repo code database. The default path lives in engine/codes.py."""
import pytest

from engine.tests._db_skip import CodeDbMissing, skip_missing_default_db


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    try:
        return (yield)
    except (FileNotFoundError, CodeDbMissing) as exc:
        skip_missing_default_db(exc)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    try:
        return (yield)
    except (FileNotFoundError, CodeDbMissing) as exc:
        skip_missing_default_db(exc)
