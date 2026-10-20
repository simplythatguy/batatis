"""Skip a missing repo code database. The default path lives in engine/codes.py."""
import pytest

from engine.llm_gate import reset_for_tests
from engine.tests._db_skip import CodeDbMissing, skip_missing_default_db


@pytest.fixture(autouse=True)
def _reset_spend_gate():
    """The identify HTTP gate shares one process ledger. Each test starts from empty."""
    reset_for_tests()
    yield
    reset_for_tests()


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
