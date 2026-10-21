"""Pytest hooks for evals_dev.

Tests marked ``paid`` call a live provider (OpenAI or Jev) and cost money. They are skipped unless
``BATATIS_RUN_PAID=1``, so CI, which blanks every provider key, never runs them and never fails for a missing one.
"""
import os

import pytest


def pytest_configure(config):
    config.addinivalue_line('markers', 'paid: calls a live paid provider; skipped unless BATATIS_RUN_PAID=1')


def pytest_collection_modifyitems(config, items):
    if os.environ.get('BATATIS_RUN_PAID') == '1':
        return
    skip = pytest.mark.skip(reason='paid test: set BATATIS_RUN_PAID=1 and the provider key to run it')
    for item in items:
        if 'paid' in item.keywords:
            item.add_marker(skip)
