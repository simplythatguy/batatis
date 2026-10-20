"""HTTP identify uses the spend gate. The benchmark calls pipeline.run and does not."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.copyright import clip_marker
from engine.identify.pipeline import run
from engine.llm_gate import authorize, record
from engine.quotes import clip_body
from engine.store import CaseStore

ARTS = {
    '9.10.15.5.': {
        'id': '9.10.15.5.', 'part': 9, 'title': 'Soffit', 'section': '9.10.15.',
        'subsection': '9.10.15.', 'text': 'projecting roof soffits',
    },
}


def _live(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)


def test_authorize_refuses_unless_live_is_exactly_one(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('BATATIS_LIVE', 'true')
    refused = authorize(max_input_tokens=10, max_output_tokens=10)
    assert refused.allowed is False and refused.source == 'offline'
    monkeypatch.setenv('BATATIS_LIVE', '1')
    allowed = authorize(model='gpt-4.1', max_input_tokens=10, max_output_tokens=10)
    assert allowed.allowed is True and allowed.source == 'live' and allowed.reserved_usd > 0


def test_rate_limit_is_per_ip(monkeypatch):
    _live(monkeypatch)
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '1')
    first = authorize(max_input_tokens=10, max_output_tokens=10, client_ip='203.0.113.5')
    second = authorize(max_input_tokens=10, max_output_tokens=10, client_ip='203.0.113.5')
    other = authorize(max_input_tokens=10, max_output_tokens=10, client_ip='203.0.113.9')
    assert first.allowed is True
    assert second.allowed is False and second.source == 'rate-limited'
    assert other.allowed is True


def test_daily_cap_returns_offline_cap(monkeypatch):
    _live(monkeypatch)
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.000001')
    decision = authorize(model='gpt-4.1', max_input_tokens=1_000_000, max_output_tokens=0)
    assert decision.allowed is False and decision.source == 'offline-cap'


def test_record_replaces_the_reservation(monkeypatch):
    _live(monkeypatch)
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.003')
    first = authorize(model='gpt-4.1', max_input_tokens=1000, max_output_tokens=0)
    assert first.allowed is True
    record(model='gpt-4.1', input_tokens=0, output_tokens=0, reserved_usd=first.reserved_usd)
    second = authorize(model='gpt-4.1', max_input_tokens=1000, max_output_tokens=0)
    assert second.allowed is True
    assert second.reserved_usd == Decimal('0.002000')


def test_pipeline_run_does_not_authorize(monkeypatch):
    def boom(**kwargs):
        raise AssertionError('benchmark path must not call the spend gate')

    monkeypatch.setattr('engine.llm_gate.authorize', boom)
    monkeypatch.setattr('engine.llm_gate.record', boom)
    out = run('soffit', arts=ARTS, ranker='bm25')
    assert out['articles']


def test_http_identify_authorizes_before_the_provider_and_records_after(tmp_path, monkeypatch):
    _live(monkeypatch)
    present = tmp_path / 'present.sqlite'
    present.write_bytes(b'')
    monkeypatch.setattr('engine.routes_case.default_db', lambda: present)
    order = []

    def fake_authorize(**kwargs):
        order.append('authorize')
        return type('Decision', (), {'allowed': True, 'source': 'live', 'reserved_usd': Decimal('0.01')})()

    def fake_record(**kwargs):
        order.append(('record', kwargs['reserved_usd'], kwargs['input_tokens']))

    def fake_run(prose, facts=None, on_stage=None, ranker=None, **kwargs):
        order.append(('run', ranker))
        return {
            'articles': [],
            'section_c': [],
            'benchmark': {'section_c': [], 'quote': None, 'identified': False},
            'questions': [],
            'open_questions': [],
            'trace': {'usage': {'input_tokens': 12, 'output_tokens': 3, 'by_model': {
                'gpt-4.1-mini-2025-04-14': {'input_tokens': 8, 'output_tokens': 1},
                'gpt-4.1-2025-04-14': {'input_tokens': 4, 'output_tokens': 2},
            }}},
        }

    monkeypatch.setattr('engine.routes_case.authorize', fake_authorize)
    monkeypatch.setattr('engine.routes_case.record', fake_record)
    monkeypatch.setattr('engine.routes_case.identify_run', fake_run)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite')))
    case_id = client.post('/cases').json()['id']
    response = client.post(f'/cases/{case_id}/identify', json={'prose': 'a wall close to the lot line'})
    assert response.status_code == 200
    assert order[0] == 'authorize'
    assert order[1] == ('run', None)
    assert order[2][0] == 'record' and order[2][1] == Decimal('0.01') and order[2][2] == 8
    assert order[3][0] == 'record' and order[3][1] == 0 and order[3][2] == 4
    assert response.json()['mode'] == 'live'


def test_gate_refusal_skips_the_provider(tmp_path, monkeypatch):
    _live(monkeypatch)
    present = tmp_path / 'present.sqlite'
    present.write_bytes(b'')
    monkeypatch.setattr('engine.routes_case.default_db', lambda: present)
    rankers = []

    def fake_authorize(**kwargs):
        return type('Decision', (), {'allowed': False, 'source': 'rate-limited', 'reserved_usd': Decimal('0')})()

    def fake_run(prose, facts=None, on_stage=None, ranker=None, **kwargs):
        rankers.append(ranker)
        return {
            'articles': [],
            'section_c': [],
            'benchmark': {'section_c': [], 'quote': None, 'identified': False},
            'questions': [],
            'open_questions': [],
        }

    monkeypatch.setattr('engine.routes_case.authorize', fake_authorize)
    monkeypatch.setattr('engine.routes_case.identify_run', fake_run)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite')))
    case_id = client.post('/cases').json()['id']
    response = client.post(f'/cases/{case_id}/identify', json={'prose': 'a proposal the demo cache does not store'})
    assert response.status_code == 200
    assert rankers == ['bm25']
    assert response.json()['source'] == 'rate-limited'
    assert response.json()['mode'] == 'bm25_fallback'


def test_long_provision_text_carries_the_clipped_marker():
    words = ' '.join(f'w{i:02d}' for i in range(40))
    body = clip_body({'text': words, 'pdf_page': 4, 'citation': 'Div B 9.1.1.1.'})
    marker = clip_marker(4)
    assert body['text'].endswith(marker)
    assert len(body['text'].split(marker)[0].split()) == 25
    assert body['clipped'] is True
    assert body['citation'] == 'Div B 9.1.1.1.'
    assert 'url' in body


def test_short_text_is_unchanged_and_applicant_quotes_stay_whole():
    short = clip_body({'text': 'one short sentence'})
    assert short['text'] == 'one short sentence'
    assert short.get('clipped') is not True
    applicant = ' '.join(['porch'] * 40)
    kept = clip_body({'source': {'type': 'user_text', 'ref': 'note', 'quote': applicant}})
    assert kept['source']['quote'] == applicant
    code = clip_body({'source': {'type': 'code', 'ref': '9.1.1.1.', 'quote': ' '.join(f'c{i:02d}' for i in range(30))},
                      'pdf_page': 9})
    assert code['source']['quote'].endswith(clip_marker(9))
    assert len(code['source']['quote'].split(clip_marker(9))[0].split()) == 25
    assert code['source']['clipped'] is True


@pytest.mark.skipif(not __import__('engine.codes', fromlist=['default_db']).default_db().exists(),
                    reason='codedb is not built')
def test_identify_snippet_over_25_words_carries_the_marker():
    from engine.codes import Codes
    from engine.identify.cards import present

    codes = Codes()
    sentence = codes.provision('9.10.15.5.(8)', 'B')
    flat = ' '.join(sentence['text'].split())
    shaped = present({
        'articles': [{
            'provision': '9.10.15.5.', 'title': 'Soffit',
            'quote': 'projecting roof soffits shall not be constructed',
            'reason': 'quoted soffit sentence', 'stage': 'verify',
        }],
        'section_c': [],
        'benchmark': {'section_c': []},
        'trace': {'verifier': {'picks': ['9.10.15.5.']}},
    }, codes, 'live')
    card = shaped['articles'][0]
    prose = card['snippet'].split(' … [clipped, see NBC')[0]
    assert len(flat.split()) > 25
    assert flat.startswith(prose)
    assert len(prose.split()) == 25
    assert card['snippet'].endswith(clip_marker(card['page']))
    assert card['clipped'] is True
    assert card['explainer']['quote'] == card['snippet']
    assert 'quote' not in card
