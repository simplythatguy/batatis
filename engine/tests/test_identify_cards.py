"""Article cards on POST /cases/{id}/identify and GET of the stored result."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes, default_db
from engine.identify.cards import present
from engine.store import CaseStore

ROOT = Path(__file__).resolve().parents[2]
_WS = re.compile(r'\s+')


def _description(case_id: str) -> str:
    return json.loads((ROOT / 'evals_dev' / 'cases' / f'{case_id}.json').read_text())['description']


def _client(tmp_path):
    return TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite')))


def _post(client, prose: str):
    case_id = client.post('/cases').json()['id']
    response = client.post(f'/cases/{case_id}/identify', json={'prose': prose})
    return case_id, response


def test_sentence_comes_only_from_one_stored_or_codedb_match():
    article = {
        'provision': '9.10.15.5.', 'division': 'B', 'committed': False, 'title': 'Soffit',
        'quote': 'projecting roof soffits shall not be constructed',
        'reason': 'The proposal is measured against the soffit limit.', 'stage': 'cached',
    }
    stored = {
        'provision_id': '9.10.15.5.(8)',
        'citation': 'stored citation for 9.10.15.5.(8)',
        'explainer': {
            'text': 'Division B 9.10.15.5.(8) is quoted from the code database.',
            'quote': '8) Except as provided, projecting roof soffits shall not be constructed above the face.',
            'source': 'deterministic',
        },
    }
    ambiguous = present({
        'articles': [dict(article)],
        'section_c': [],
        'benchmark': {'section_c': [
            stored,
            {'provision_id': '9.10.15.5.(9)', 'explainer': {'quote': stored['explainer']['quote'], 'text': 'other',
                                                            'source': 'deterministic'}},
        ]},
    }, None, 'cached_demo')
    card = ambiguous['articles'][0]
    assert card['provision_id'] is None and card['benchmark_acceptable_solution'] is None
    assert '9.9.10.1.(2)' not in json.dumps(ambiguous)

    resolved = present({
        'articles': [dict(article)],
        'section_c': [],
        'benchmark': {'section_c': [stored]},
    }, None, 'cached_demo')
    card = resolved['articles'][0]
    assert card['rank'] == 1
    assert card['provision_id'] == '9.10.15.5.(8)'
    assert card['benchmark_acceptable_solution'] == '9.10.15.5.(8)'
    assert card['link'] == '/code/9.10.15.5.?division=B'
    assert card['citation'] == 'stored citation for 9.10.15.5.(8)'
    assert card['title'] == 'Soffit'
    assert card['why'] == article['reason']
    assert card['verifier_status'] == 'unknown'
    assert card['snippet'] and len(card['snippet'].split()) <= 25
    assert card['explainer']['label'] == 'explanation'
    assert card['explainer']['source'] == 'deterministic'
    assert 'This is an explanation of the quoted text.' in card['explainer']['text']
    assert 'compli' not in json.dumps(card).lower()


def test_a_compliance_claim_stays_out_of_the_explainer():
    shaped = present({
        'articles': [{
            'provision': '9.9.10.1.', 'committed': False, 'title': 'Egress',
            'quote': 'unobstructed opening',
            'reason': 'The design complies and is safe.', 'stage': 'verify',
        }],
        'section_c': [],
        'benchmark': {'section_c': [{
            'provision_id': '9.9.10.1.(2)',
            'explainer': {
                'text': 'The design complies and is safe.',
                'quote': 'The window shall provide an unobstructed opening.',
                'source': 'ai_written',
            },
        }]},
        'trace': {'verifier': {'picks': ['9.9.10.1.']}},
    }, None, 'live')
    card = shaped['articles'][0]
    assert card['verifier_status'] == 'candidate'
    assert card['benchmark_acceptable_solution'] == '9.9.10.1.(2)'
    assert card['explainer']['source'] == 'deterministic'
    assert card['explainer']['label'] == 'explanation'
    assert 'compli' not in card['explainer']['text'].lower()
    assert 'safe' not in card['explainer']['text'].lower()


def test_bm25_cards_commit_nothing():
    shaped = present({
        'articles': [{
            'provision': '9.10.15.5.', 'committed': True, 'title': 'Soffit',
            'quote': 'projecting roof soffits', 'reason': 'bm25 overlap', 'stage': 'bm25',
        }],
        'section_c': [{'provision_id': '9.10.15.5.(8)'}],
        'benchmark': {'section_c': []},
    }, None, 'bm25_fallback')
    assert shaped['mode'] == 'bm25_fallback' and shaped['section_c'] == []
    card = shaped['articles'][0]
    assert 'committed' not in card and card['suggested'] is False
    assert card['status'] == 'unknown' and card['verifier_status'] == 'unknown'
    assert card['decision'] is None and card['open_question_id'] is None
    assert card['provision_id'] == '9.10.15.5.(8)'


def test_http_demo_cards_and_stored_get_match(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
    monkeypatch.setattr('engine.routes_case.default_db', lambda: tmp_path / 'missing.sqlite')
    client = _client(tmp_path)
    case_id, response = _post(client, _description('dev-001'))
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'cached_demo'
    card = body['articles'][0]
    assert card['rank'] == 1
    assert card['provision'] == '9.10.15.5.'
    assert card['provision_id'] == '9.10.15.5.(8)'
    assert card['benchmark_acceptable_solution'] == '9.10.15.5.(8)'
    assert card['link'] == '/code/9.10.15.5.?division=B'
    assert card['title']
    assert 1 <= len(card['snippet'].split()) <= 25
    assert card['verifier_status'] == 'unknown'
    assert card['why']
    assert card['explainer']['label'] == 'explanation'
    assert 'compli' not in json.dumps(body).lower()
    assert client.get(f'/cases/{case_id}').json()['provisions'] == []
    stored = client.get(f'/cases/{case_id}/identify')
    assert stored.status_code == 200
    assert stored.json()['articles'] == body['articles']
    assert stored.json()['mode'] == 'cached_demo'
    other = client.post('/cases').json()['id']
    assert client.get(f'/cases/{other}/identify').status_code == 404


def test_live_flag_is_required_before_a_provider_call(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
    called = {'n': 0}

    def boom(*args, **kwargs):
        assert kwargs.get('ranker') == 'bm25'
        called['n'] += 1
        return {'articles': [], 'section_c': [], 'benchmark': {'citation': None, 'quote': None, 'section_c': []},
                'questions': [], 'open_questions': []}

    monkeypatch.setattr('engine.routes_case.identify_run', boom)
    client = _client(tmp_path)
    demo = client.post(f"/cases/{client.post('/cases').json()['id']}/identify",
                       json={'prose': _description('dev-013')})
    assert demo.status_code == 200 and demo.json()['mode'] == 'cached_demo'
    other = client.post(f"/cases/{client.post('/cases').json()['id']}/identify",
                        json={'prose': 'a proposal the demo cache does not store'})
    assert other.status_code == 200 and other.json()['mode'] == 'bm25_fallback'
    assert called['n'] == (1 if default_db().exists() else 0)
    if not default_db().exists():
        assert other.json()['articles'] == [] and other.json()['benchmark']['citation'] is None


def test_snippet_is_a_codedb_sentence_prefix_when_the_database_is_present():
    if not default_db().exists():
        pytest.skip('code database not built at codedb/build/codedb.sqlite')
    codes = Codes()
    client_text = codes.provision('9.10.15.5.(8)', 'B')['text']
    flat = _WS.sub(' ', client_text).strip()
    shaped = present({
        'articles': [{
            'provision': '9.10.15.5.', 'committed': True, 'title': codes.provision('9.10.15.5.', 'B')['title'],
            'quote': 'projecting roof soffits shall not be constructed',
            'reason': 'quoted soffit sentence', 'stage': 'verify',
        }],
        'section_c': [],
        'benchmark': {'section_c': []},
        'trace': {'verifier': {'picks': ['9.10.15.5.']}},
    }, codes, 'live')
    card = shaped['articles'][0]
    assert card['provision_id'] == '9.10.15.5.(8)'
    assert card['status'] == 'suggested' and card['verifier_status'] == 'suggested'
    assert card['decision'] is None and 'committed' not in card
    assert card['citation'] == codes.citation('9.10.15.5.(8)', 'B')
    assert flat.startswith(card['snippet'])
    assert len(card['snippet'].split()) <= 25
    assert card['snippet'] in flat
