import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.ccmc import CCMCRegistry
from engine.codes import Codes
from engine.models import Case, Fact, Source
from engine.routes_case import create_router
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import complete_case, fact


@pytest.fixture
def context(tmp_path):
    store, codes = CaseStore(tmp_path / 'cases.sqlite'), Codes()
    return TestClient(create_app(store, codes)), store, codes


def test_routes_are_mounted_and_rebuild_only_confirmed_rows(context):
    client, store, codes = context
    case = store.put(Case())
    r = client.post(f'/cases/{case.id}/section-d', json={'provisions': ['9.25.5.2.(1)(b)', '9.27.3.2.(1)']})
    assert r.status_code == 200 and r.json()['items']
    assert all(item['status'] == 'not provided' for item in r.json()['items'])
    stored = store.get(case.id)
    assert stored.provisions == ['9.25.5.2.(1)(b)', '9.27.3.2.(1)'] and stored.section_c
    assert stored.evidence == []
    before = stored.model_dump_json()
    r = client.post(f'/cases/{case.id}/section-d', json={'provisions': ['9.99.99.99.(1)']})
    assert r.status_code == 404 and store.get(case.id).model_dump_json() == before
    assert client.post(f'/cases/{case.id}/section-d', json={'risk_assessment': 'AI-written text'}).status_code == 422


def test_professional_process_and_gaps_use_latest_persisted_facts(context):
    client, store, codes = context
    case = store.put(complete_case())
    assert client.get(f'/cases/{case.id}/professional').json()['required'] == 'no'
    assert client.get(f'/cases/{case.id}/gaps').json() == []
    fields = client.get(f'/cases/{case.id}/process-fields').json()
    assert len(fields) == 6 and all(f['answer']['author'] == 'applicant' for f in fields)
    store.add_fact(case.id, fact('process.risk_assessment', 'Proposed generated text', kind='proposed', status='unconfirmed'))
    gaps = client.get(f'/cases/{case.id}/gaps').json()
    assert any(g['id'].startswith('D09:') and g['fix_hint'] and g['citation'] for g in gaps)
    assert next(f for f in client.get(f'/cases/{case.id}/process-fields').json() if f['id'] == 'risk_assessment')['answer'] is None


@pytest.mark.parametrize('path,method', [('section-d', 'post'), ('professional', 'get'), ('process-fields', 'get'), ('gaps', 'get')])
def test_missing_case_404(context, path, method):
    assert getattr(context[0], method)(f'/cases/missing/{path}').status_code == 404


def test_ccmc_route_offline_and_unavailable(tmp_path):
    snapshot = tmp_path / 'registry.json'
    snapshot.write_text(json.dumps({'items': [], 'hasMore': False}))
    store, codes = CaseStore(tmp_path / 'cases.sqlite'), Codes()
    registry = CCMCRegistry(snapshot, '2026-10-18', offline=True)
    app = FastAPI()
    app.include_router(create_router(lambda: store, lambda: codes, registry))
    client = TestClient(app)
    r = client.get('/ccmc/search', params={'q': 'BTRboard'})
    assert r.status_code == 200 and r.json()['source'] == 'snapshot' and not r.json()['results']
    assert client.get('/ccmc/search', params={'q': '---'}).status_code == 422
    assert client.get('/ccmc/search', params={'q': ''}).status_code == 422
    registry.snapshot_path = tmp_path / 'unavailable.json'
    registry._loaded_at = float('-inf')
    assert client.get('/ccmc/search', params={'q': 'BTRboard'}).status_code == 503
