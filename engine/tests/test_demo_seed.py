"""Offline demo seed. No code database, no network, no answer keys."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.completeness import check_completeness
from engine.demo_seed import (
    CASE_IDS, OFFICER_AFTER_ID, OFFICER_STORY, STAMP, build_cases, demo_enabled, seed_cases,
)
from engine.models import Case, Fact, Jurisdiction, Source
from engine.process_fields import confirmed_value
from engine.professional import ProfessionalResult
from engine.section_d import supporting_documents
from engine.store import CaseStore

REPO = Path(__file__).resolve().parents[2]
FORBIDDEN = ('/expected/', '/presenter/', '/keys/')


def test_demo_flag_is_off_unless_it_is_exactly_one(monkeypatch):
    monkeypatch.delenv('BATATIS_DEMO', raising=False)
    assert demo_enabled() is False
    for value in ('', '0', 'true', 'yes', 'TRUE'):
        monkeypatch.setenv('BATATIS_DEMO', value)
        assert demo_enabled() is False
    monkeypatch.setenv('BATATIS_DEMO', '1')
    assert demo_enabled() is True


def test_cases_use_fixed_ids_and_only_input_files():
    first = [case.model_dump() for case in build_cases()]
    second = [case.model_dump() for case in build_cases()]
    assert first == second
    assert [case['id'] for case in first] == [*CASE_IDS, OFFICER_AFTER_ID]
    for case in first:
        if case['id'] == OFFICER_AFTER_ID:
            continue
        assert case['created_at'] == case['updated_at'] == STAMP
        assert case['provisions'] == [] and case['section_c'] == [] and case['evidence'] == []
        assert case['facts']
        for fact in case['facts']:
            ref = fact['source']['ref']
            assert '/input/' in ref
            assert ref.startswith('evals/demo-cases/')
            assert all(part not in ref for part in FORBIDDEN)
            assert 'professional_seal' not in fact['field']
            assert fact['kind'] == 'pointed'
            quote = fact['source']['quote']
            if quote is not None:
                text = (REPO / ref).read_text(encoding='utf-8')
                assert quote in text
                assert fact['value'] == Path(ref).name or fact['value'] in quote


def test_seeded_titles_use_the_example_data_prefix():
    for case in build_cases():
        assert case.title is not None and case.title.startswith('EXAMPLE DATA: ')
        assert case.seeded_at == STAMP


def test_no_seeded_fact_uses_an_applicant_source():
    cases = build_cases()
    for case in cases:
        assert all(fact.source.type not in {'user_text', 'user_click'} for fact in case.facts)
    officer = next(case for case in cases if case.id == OFFICER_AFTER_ID)
    ranked = next(fact for fact in officer.facts if fact.field == 'identify.ranked')
    story = next(fact for fact in officer.facts if fact.field == 'package.story')
    assert ranked.source.type == 'demo_seed'
    assert story.source.type == 'demo_seed'
    professional = [fact for fact in officer.facts if fact.value == 'needs professional']
    assert professional and all(fact.source.type == 'demo_seed' and fact.status == 'unconfirmed'
                                for fact in professional)
    nailbase = next(case for case in cases if case.id == CASE_IDS[0])
    assert all(fact.field != 'building.storeys' for fact in nailbase.facts)
    permeance = next(fact for fact in nailbase.facts if fact.field == 'product.permeance')
    assert permeance.status == 'unconfirmed'
    assert permeance.source.type == 'file'


class _GapCodes:
    def provision(self, provision_id, division=None):
        return {'id': provision_id, 'citation': 'fixture citation', 'article_title': 'Fixture'}

    def citation(self, provision_id, division=None):
        return 'fixture citation'


def test_demo_seed_does_not_satisfy_a_gap_or_professional_evidence():
    seeded = Fact(field='owner', value='Dana Hartley', kind='pointed', status='confirmed',
                  source=Source(type='demo_seed', ref='demo-seed', quote='Dana Hartley'))
    stated = Fact(field='owner', value='Dana Hartley', kind='pointed', status='confirmed',
                  source=Source(type='user_text', ref='applicant', quote='Dana Hartley'))
    assert confirmed_value(Case(facts=[seeded]), 'owner') is None
    assert confirmed_value(Case(facts=[stated]), 'owner') == 'Dana Hartley'
    professional = ProfessionalResult(required='no', general_required='no', reasons=[], questions=[])
    jurisdiction = Jurisdiction(id='county-of-example', name='County of Example')
    still_open = check_completeness(Case(facts=[seeded], jurisdiction=jurisdiction), _GapCodes(),
                                    professional=professional)
    assert any(gap.field == 'owner_name' for gap in still_open)
    closed = check_completeness(Case(facts=[stated], jurisdiction=jurisdiction), _GapCodes(),
                                professional=professional)
    assert all(gap.field != 'owner_name' for gap in closed)
    seal = Fact(field='evidence.e1.professional_seal', value='needs professional', kind='pointed',
                status='confirmed', source=Source(type='demo_seed', ref='demo-seed', quote='needs professional'))
    ref = Fact(field='evidence.e1.file_ref', value='demo-seed', kind='pointed', status='confirmed',
               source=Source(type='demo_seed', ref='demo-seed', quote='demo-seed'))
    assert supporting_documents(Case(facts=[ref, seal])) == []


def test_example_drafts_are_not_professional_evidence():
    cases = {case.id: case for case in build_cases()}
    letter = next(fact for fact in cases[CASE_IDS[0]].facts
                  if fact.field == 'input_file.engineer-letter-draft-EXAMPLE.md')
    assert 'DRAFT' in letter.source.quote
    assert 'not signed' in letter.source.quote
    assert letter.value == 'engineer-letter-draft-EXAMPLE.md'
    permeance = next(fact for fact in cases[CASE_IDS[0]].facts if fact.field == 'product.permeance')
    assert permeance.status == 'unconfirmed'
    for case_id, case in cases.items():
        if case_id == OFFICER_AFTER_ID:
            continue
        assert all(fact.field != 'professional_seal' for fact in case.facts)


def test_placeholder_legal_description_stays_unconfirmed():
    home = next(case for case in build_cases() if case.id == CASE_IDS[2])
    legal = next(fact for fact in home.facts if fact.field == 'legalDescription')
    assert legal.status == 'unconfirmed'
    assert 'placeholder' in legal.source.quote
    nailbase = next(case for case in build_cases() if case.id == CASE_IDS[0])
    assert all(fact.field != 'legalDescription' for fact in nailbase.facts)


def test_seed_is_idempotent_and_resets_edits(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    first = seed_cases(store)
    store.add_fact(first[0].id, Fact(field='invented', value='not from a file', kind='pointed',
                                      source=Source(type='user_text', ref='test')))
    second = seed_cases(store)
    assert [case.model_dump() for case in second] == [case.model_dump() for case in first]
    assert all(fact.field != 'invented' for fact in second[0].facts)
    assert store.get(CASE_IDS[0]).provisions == []


def test_route_is_404_until_the_flag_is_set(tmp_path, monkeypatch):
    monkeypatch.delenv('BATATIS_DEMO', raising=False)
    client = TestClient(create_app(CaseStore(tmp_path / 'cases.sqlite'), object()))
    missing = client.post('/demo/seed')
    assert missing.status_code == 404
    assert missing.json() == {'detail': 'not found'}
    monkeypatch.setenv('BATATIS_DEMO', '1')
    seeded = client.post('/demo/seed')
    again = client.post('/demo/seed')
    assert seeded.status_code == 200
    assert again.json() == seeded.json()
    body = seeded.json()
    assert [case['id'] for case in body] == [*CASE_IDS, OFFICER_AFTER_ID]
    assert body[0]['section_c'] == [] and body[0]['provisions'] == []
    blob = json.dumps(body)
    assert 'expected/' not in blob and 'presenter/' not in blob


def test_script_writes_nothing_without_the_flag_and_is_stable_with_it(tmp_path, monkeypatch):
    monkeypatch.delenv('BATATIS_DEMO', raising=False)
    env = os.environ.copy()
    env.pop('BATATIS_DEMO', None)
    db = tmp_path / 'cases.sqlite'
    env['BATATIS_CASES'] = str(db)
    off = subprocess.run([sys.executable, 'scripts/seed_demo.py'], cwd=REPO, env=env,
                         capture_output=True, text=True)
    assert off.returncode == 2
    assert 'BATATIS_DEMO=1' in off.stderr
    assert not db.exists()
    env['BATATIS_DEMO'] = '1'
    on = subprocess.run([sys.executable, 'scripts/seed_demo.py'], cwd=REPO, env=env,
                        capture_output=True, text=True)
    again = subprocess.run([sys.executable, 'scripts/seed_demo.py'], cwd=REPO, env=env,
                           capture_output=True, text=True)
    assert on.returncode == 0 and on.stdout == again.stdout
    payload = json.loads(on.stdout)
    assert [case['id'] for case in payload] == [*CASE_IDS, OFFICER_AFTER_ID]


def test_build_does_not_open_a_socket(monkeypatch):
    import socket

    def refused(*_args, **_kwargs):
        raise AssertionError('demo seed opened a socket')

    monkeypatch.setattr(socket, 'socket', refused)
    monkeypatch.setattr(socket, 'create_connection', refused)
    build_cases()


@pytest.mark.parametrize('case_id', CASE_IDS)
def test_description_quote_is_in_the_project_brief(case_id):
    case = next(case for case in build_cases() if case.id == case_id)
    fact = next(item for item in case.facts if item.field == 'project.description')
    assert fact.source.quote in (REPO / fact.source.ref).read_text(encoding='utf-8')
    assert fact.source.ref.endswith('/input/project-brief.md')
    assert case.section_c == [] and case.provisions == []
