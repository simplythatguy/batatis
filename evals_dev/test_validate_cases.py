"""The validator must reject planted errors. Run: .venv/bin/python -m pytest evals_dev -q"""
import copy
import json
import os
import pathlib
import sqlite3

import pytest

from evals_dev import validate_cases as vc

CASES = sorted((pathlib.Path(__file__).parent / 'cases').glob('*.json'))


@pytest.fixture(scope='module')
def con():
    path = vc.database_path()
    if os.environ.get('BATATIS_CODEDB') and not path.is_file():
        pytest.fail(f'BATATIS_CODEDB is set but the file is missing: {path}')
    if not path.is_file():
        pytest.skip('code database not built at codedb/build/codedb.sqlite')
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


@pytest.fixture(scope='module')
def cases():
    return [json.loads(p.read_text()) for p in CASES]


def test_all_cases_pass(con, cases):
    errors, counts = vc.validate(cases, con)
    expected_ids = [f'dev-{n:03}' for n in range(1, 61)]
    assert errors == [] and counts['cases'] == 60
    assert [c['id'] for c in cases] == expected_ids
    assert [p.stem for p in CASES] == expected_ids


def by_id(cases, cid):
    return copy.deepcopy(next(c for c in cases if c['id'] == cid))


def test_rejects_wrong_pair(con, cases):
    c = by_id(cases, 'dev-001')
    c['gold']['section_c'][0]['pairs'] = ['[F03-OS1.2]']
    errors, _ = vc.validate([c], con)
    assert any('pairs' in e for e in errors)


ADOPTED = {'dev-006', 'dev-010', 'dev-011', 'dev-015'}
CANDIDATES = {'dev-005', 'dev-007', 'dev-009', 'dev-012'}
LABEL = 'model-checked, not human-verified'


def test_ask_identify_gold_is_labelled_and_must_cite_stays_empty(cases):
    by = {case['id']: case for case in cases}
    for cid in ADOPTED:
        gold = by[cid]['gold']
        assert gold['intake_action'] == 'ask' and gold['must_cite'] == []
        assert gold['identify_gold']
        for row in gold['identify_gold']:
            assert row['label'] == LABEL and row['quote'].strip()
    assert [row['provision'] for row in by['dev-015']['gold']['identify_gold']] == [
        '9.9.9.1.(1)', '9.9.10.1.']
    assert by['dev-015']['gold']['identify_gold'][1]['role'] == 'secondary'
    assert by['dev-015']['gold']['identify_gold'][1]['quoted_provision'] == '9.9.10.1.(1)'
    for cid in CANDIDATES:
        gold = by[cid]['gold']
        assert gold['must_cite'] == [] and 'identify_gold' not in gold
        assert gold['identify_gold_candidates']
        for row in gold['identify_gold_candidates']:
            assert row['label'] == LABEL and row['quote'].strip()
    assert 'identify_gold' not in by['dev-020']['gold']
    assert 'identify_gold_candidates' not in by['dev-020']['gold']


def test_rejects_invented_identify_gold(con, cases):
    case = by_id(cases, 'dev-006')
    case['gold']['identify_gold'][0]['provision'] = '9.25.5.2.(99)'
    errors, _counts = vc.validate([case], con)
    assert any('not in database' in error for error in errors)


def test_rejects_invented_provision(con, cases):
    c = by_id(cases, 'dev-001')
    c['gold']['must_cite'].append({'division': 'B', 'provision': '9.10.15.5.(99)', 'role': 'benchmark'})
    errors, _ = vc.validate([c], con)
    assert any('not in database' in e for e in errors)


def test_rejects_invented_row_for_no_row_sentence(con, cases):
    c = by_id(cases, 'dev-004')  # 9.10.15.2.(3) has no table row
    c['gold']['section_c'][0]['pairs'] = ['[F03-OP3.1]']
    errors, _ = vc.validate([c], con)
    assert any('pairs' in e for e in errors)


def test_rejects_article_number_in_description(con, cases):
    c = by_id(cases, 'dev-001')
    c['description'] += ' See 9.10.15.5.'
    errors, _ = vc.validate([c], con)
    assert any('article number' in e for e in errors)
