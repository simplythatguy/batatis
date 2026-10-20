"""Assume the repo code database from PR #12, without editing engine/codes.py."""
import pytest

from engine.tests._db_skip import install_repo_default, skip_missing_default_db

install_repo_default()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    try:
        return (yield)
    except FileNotFoundError as exc:
        skip_missing_default_db(exc)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    try:
        return (yield)
    except FileNotFoundError as exc:
        skip_missing_default_db(exc)
