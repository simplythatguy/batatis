"""Coded rules (WP-31, AC5.1-AC5.4): data, vectors, cross-language agreement, wording, API.

The TypeScript side of the agreement is web/src/rules/rules.test.ts (CI web job, `npm run test:rules`): it
deep-compares its outputs with evals_dev/rules/outputs.json, which `test_golden_outputs_are_current` keeps
equal to this evaluator. `test_typescript_evaluator_agrees` also runs node here when it is available.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codedb import store as codedb_store
from engine.api import create_app
from engine.codes import Codes
from engine.models import Case, Fact, Source
from engine.rules import evaluate, evaluate_all, fmt, load_index, load_rule, load_rules
from engine.rules import golden
from engine.store import CaseStore
from engine.tests.test_accounts import onboard, signup

ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads((ROOT / 'evals_dev' / 'rules' / 'vectors.json').read_text(encoding='utf-8'))['vectors']
# C5: a rule result never says the design complies, is safe, approved or adequate.
BANNED = re.compile(r'\b(compl(?:y|ies|ied|iant|iance)|safe|safely|approved?|approval|adequate(?:ly)?|adequacy)\b', re.I)
PROVIDERS = re.compile(r'jev|typesafe|openai|anthropic|claude|\bgpt|\bluna\b', re.I)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _summary(result: dict, expect: dict) -> dict:
    got = {'state': result['state'], 'outcome_id': result['outcome_id'], 'provision': result['provision']['id'],
           'missing': [m['field'] for m in result['missing']]}
    if 'assumptions' in expect:
        got['assumptions'] = len(result['assumptions'])
    return got


# ---------------------------------------------------------------- vectors (AC5.1, AC5.4)

@pytest.mark.parametrize('vector', VECTORS, ids=[v['id'] for v in VECTORS])
def test_vector(vector):
    result = evaluate(load_rule(vector['rule']), vector['inputs'])
    assert _summary(result, vector['expect']) == vector['expect']


def test_vector_coverage():
    index = load_index()
    assert len({v['id'] for v in VECTORS}) == len(VECTORS)
    for rule in load_rules():
        mine = [v for v in VECTORS if v['rule'] == rule['id']]
        assert len(mine) >= 10, rule['id']
        assert any('boundary' in v['tags'] for v in mine), rule['id']
        assert any(v['expect']['state'] == 'needs_info' for v in mine), f"{rule['id']}: no missing-input vector"
        hit = {v['expect']['outcome_id'] for v in mine}
        assert {o['id'] for o in rule['outcomes']} <= hit, f"{rule['id']}: outcomes without a vector"
        assert set(rule['inputs']) <= set(index['inputs'])
    # A rule is marked reviewed only when the domain reviewer has signed every one of its vectors (REVIEW.md).
    assert all(isinstance(v['reviewed'], bool) for v in VECTORS)
    for rule in load_rules():
        assert isinstance(rule['reviewed'], bool)
        if rule['reviewed']:
            assert all(v['reviewed'] for v in VECTORS if v['rule'] == rule['id']), rule['id']


def test_missing_inputs_become_questions_not_guesses():
    for result in evaluate_all({}):
        assert result['state'] == 'needs_info'
        assert result['missing'] and all(m['question'].endswith('?') for m in result['missing'])
        assert result['outcome_id'] is None and result['next_step'] is None


def test_departs_names_both_halves_as_an_applicant_action():
    departs = [evaluate(load_rule(v['rule']), v['inputs']) for v in VECTORS if v['expect']['state'] == 'departs']
    assert departs
    for result in departs:
        assert 'alternative solution' in result['next_step'] and 'Division C, Subsection 2.3.1.' in result['next_step']
        assert 'request for variance' in result['next_step'] and 'Safety Codes Act, s.38' in result['next_step']
        assert 'departs from the acceptable solution' in result['message']


def test_fmt():
    assert [fmt(x) for x in (2.1, 2, 0.125, 1.005, 7.066666, 1440, 0.45, -0.5, True)] == \
        ['2.1', '2', '0.13', '1', '7.07', '1440', '0.45', '-0.5', 'yes']


# ---------------------------------------------------------------- agreement (AC5.2)

def test_golden_outputs_are_current():
    assert golden.OUTPUTS.read_text(encoding='utf-8') == golden.text(), 'run python -m engine.rules.golden'


def _node() -> str | None:
    node = shutil.which('node')
    if not node:
        return None
    major, minor = (int(x) for x in subprocess.run([node, '--version'], capture_output=True, text=True)
                    .stdout.strip().lstrip('v').split('.')[:2])
    return node if (major, minor) >= (22, 6) else None


def test_typescript_evaluator_agrees():
    node = _node()
    if node is None:
        pytest.skip('node 22.6+ not available here; the CI web job runs web/src/rules/rules.test.ts')
    web = ROOT / 'web'
    run = subprocess.run([node, '--experimental-strip-types', '--no-warnings', '--import', './scripts/register-ts.mjs',
                          '--test', 'src/rules/rules.test.ts'], cwd=web, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-2000:]


# ---------------------------------------------------------------- data from the code database

def test_every_citation_and_page_comes_from_the_code_database():
    codes = Codes()
    refs = [p for rule in load_rules() for p in rule['provisions']] + load_index()['process_provisions']
    for ref in refs:
        record = codes.provision(ref['id'], ref['division'])
        assert record is not None, ref['id']
        assert record['citation'] == ref['citation'], ref['id']
        assert record['pdf_page'] == ref['pdf_page'], ref['id']
    for rule in load_rules():
        for outcome in rule['outcomes']:
            assert outcome['provision'] in {p['id'] for p in rule['provisions']}, outcome['id']


def test_every_table_is_cited_by_id_and_page():
    codes = Codes()
    with closing(codedb_store.connect(codes.db_path)) as con:
        pages = dict(con.execute("SELECT table_id, pdf_page FROM code_tables WHERE doc='NBC-AE' AND division='B'"))
    for rule in load_rules():
        for table in rule['tables']:
            assert pages.get(table['id']) == table['pdf_page'], table['id']
            assert all(len(row['values']) == len(table['columns']) for row in table['rows'])
            assert [r['max_area'] for r in table['rows']] == [30, 40, 50, 100, None]


def test_tables_as_printed():
    """Transcribed from Tables 9.10.15.4. (PDF p.902) and 9.10.14.4.-A (PDF p.895); null is the printed dash."""
    houses = load_rule('glazed-openings-houses')['tables'][0]
    assert houses['columns'] == [0, 1.2, 1.5, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 25.0]
    assert houses['rows'][0]['values'][:7] == [0, 7, 9, 12, 39, 88, 100]
    assert houses['rows'][4]['values'] == [0, 7, 7, 8, 12, 19, 28, 40, 55, 92, 100, None]
    residential, mercantile = load_rule('unprotected-openings')['tables']
    assert residential['rows'] == houses['rows']
    assert mercantile['rows'][4]['values'] == [0, 4, 4, 4, 6, 10, 14, 20, 27, 46, 70, 100]


# ---------------------------------------------------------------- wording (AC5.3)

def test_no_rule_text_or_output_says_complies_safe_approved_or_adequate():
    texts = list(_strings(load_index())) + [s for rule in load_rules() for s in _strings(rule)]
    texts += [s for v in VECTORS for s in _strings(evaluate(load_rule(v['rule']), v['inputs']))]
    for text in texts:
        assert not BANNED.search(text), text
        assert not PROVIDERS.search(text), text


def test_boundary_prompt_outputs_stay_departure_flags():
    """Inputs chosen to tempt a verdict: everything allowed, exactly at the limits, or wildly over."""
    for given in ({}, {'occupancy': 'single_family', 'limiting_distance_m': 25, 'ebf_area_m2': 10, 'glazed_area_m2': 0},
                  {'occupancy': 'single_family', 'limiting_distance_m': 0, 'ebf_area_m2': 500, 'glazed_area_m2': 500,
                   'soffit_projects': True, 'faces_public_way': False}):
        for result in evaluate_all(given):
            for text in _strings(result):
                assert not BANNED.search(text), text


# ---------------------------------------------------------------- API

def _fact(field, value, status='confirmed', kind='pointed'):
    return Fact(field=field, value=value, kind=kind, status=status, source=Source(type='user_text', ref='test'))


def test_case_route_reads_facts_and_asks_for_the_rest(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case(facts=[
        _fact('occupancy', 'single_family'), _fact('storeys', 2), _fact('building_area_m2', 150),
        _fact('sprinklered', 'no'), _fact('fire_response_over_10_min', False),
        _fact('limiting_distance_m', 1.2, status='unconfirmed'), _fact('ebf_area_m2', 30), _fact('glazed_area_m2', 4),
        _fact('glass_blocks', True, kind='proposed', status='unconfirmed'),   # a model guess is never used
    ]))
    with TestClient(create_app(store=store)) as client:
        body = client.get(f'/cases/{case.id}/rules').json()
        assert client.get('/cases/case_missing/rules').status_code == 404
        rules = client.get('/rules').json()
    assert [r['rule_id'] for r in body['results']] == load_index()['rules']
    glazed = body['results'][0]
    assert glazed['state'] == 'needs_info' and [m['field'] for m in glazed['missing']] == ['glass_blocks']
    assert glazed['unconfirmed_inputs'] == ['limiting_distance_m']
    used = {i['field']: i for i in glazed['inputs']}
    assert used['glazed_area_m2']['fact_id'] and used['glazed_area_m2']['fact_status'] == 'confirmed'
    assert used['glass_blocks']['value'] is None and used['glass_blocks']['fact_id'] is None
    assert body['notice'] and body['edition'] == 'NBC(AE) 2023, 2nd printing'
    assert [r['id'] for r in rules['rules']] == load_index()['rules']


def test_case_route_follows_the_case_access_policy(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
    app = create_app(store=CaseStore(tmp_path / 'cases.sqlite'))
    with TestClient(app, base_url='http://localhost') as owner, TestClient(app, base_url='http://localhost') as other:
        signup(owner)
        onboard(owner)
        case_id = owner.post('/cases', json={}).json()['id']
        assert owner.get(f'/cases/{case_id}/rules').status_code == 200
        assert other.get(f'/cases/{case_id}/rules').status_code == 404
        signup(other, email='other@example.test', name='Other')
        onboard(other)
        assert other.get(f'/cases/{case_id}/rules').status_code == 404
