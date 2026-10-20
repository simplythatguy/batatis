"""The validator must reject planted errors. Run: .venv/bin/python -m pytest evals_dev -q"""
import copy
import json
import pathlib
import sqlite3

import pytest

from evals_dev import validate_cases as vc

CASES = sorted((pathlib.Path(__file__).parent / 'cases').glob('*.json'))


@pytest.fixture(scope='module')
def con():
    if not pathlib.Path(vc.DEFAULT_DB).is_file():
        pytest.skip('code database not built')
    return sqlite3.connect(f'file:{vc.DEFAULT_DB}?mode=ro', uri=True)


@pytest.fixture(scope='module')
def cases():
    return [json.loads(p.read_text()) for p in CASES]


def test_all_cases_pass(con, cases):
    errors, counts = vc.validate(cases, con)
    assert errors == [] and counts['cases'] == 25


def by_id(cases, cid):
    return copy.deepcopy(next(c for c in cases if c['id'] == cid))


def test_rejects_wrong_pair(con, cases):
    c = by_id(cases, 'dev-001')
    c['gold']['section_c'][0]['pairs'] = ['[F03-OS1.2]']
    errors, _ = vc.validate([c], con)
    assert any('pairs' in e for e in errors)


def test_rejects_invented_provision(con, cases):
    c = by_id(cases, 'dev-001')
    c['gold']['must_cite'].append({'division': 'B', 'provision': '9.10.15.5.(99)', 'role': 'benchmark'})
    errors, _ = vc.validate([c], con)
    assert any('not in database' in e for e in errors)


def test_rejects_invented_row_for_no_row_sentence(con, cases):
    c = by_id(cases, 'dev-004')  # 9.10.14.2.(2) has no table row
    c['gold']['section_c'][0]['pairs'] = ['[F03-OP3.1]']
    errors, _ = vc.validate([c], con)
    assert any('pairs' in e for e in errors)


def test_rejects_article_number_in_description(con, cases):
    c = by_id(cases, 'dev-001')
    c['description'] += ' See 9.10.15.5.'
    errors, _ = vc.validate([c], con)
    assert any('article number' in e for e in errors)
