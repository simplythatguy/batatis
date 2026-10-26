"""AI access codes: hosted AI runs only for accounts holding a current named code."""
import contextvars
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from engine import ai_access, llm_gate
from engine.api import create_app
from engine.identify.screen import Judge
from engine.store import CaseStore

CODES = '{"judges": "judges-code-1234", "team": "team-code-5678", "short": "x"}'


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', CODES)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-synthetic-not-used')
    app = create_app(store=CaseStore(tmp_path / 'accounts.sqlite'))

    @app.get('/probe-ai')
    def probe():
        # What every AI step asks before it spends: the same call, in the request and in a worker thread.
        context = contextvars.copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            in_worker = pool.submit(context.run, llm_gate.live_enabled, 'openai').result()
        return {'request': llm_gate.live_enabled('openai'), 'worker': in_worker}

    return app


def plain(response):
    """A JSON reply without the privacy notice the API adds to every answer."""
    return {key: value for key, value in response.json().items() if key != 'meta'}


def probe(client):
    reply = client.get('/probe-ai').json()
    return {key: reply[key] for key in ('request', 'worker')}


def signup(client, email):
    response = client.post('/auth/signup', json={'email': email, 'password': 'a long test password', 'name': 'Person'})
    assert response.status_code == 201, response.text


def test_named_codes_are_parsed_and_matched_without_revealing_them(monkeypatch):
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', CODES)
    assert ai_access.codes() == {'judges': 'judges-code-1234', 'team': 'team-code-5678'}, 'codes under 8 characters never count'
    assert ai_access.name_for(' team-code-5678 ') == 'team'
    assert ai_access.name_for('x') is None and ai_access.name_for('') is None and ai_access.name_for(None) is None
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', 'not json')
    assert ai_access.codes() == {}


def test_a_local_engine_without_codes_keeps_its_ai_switches(monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('BATATIS_AI_ACCESS_CODES', raising=False)
    assert not ai_access.required() and ai_access.allowed()
    monkeypatch.setenv('VERCEL', '1')
    assert ai_access.required() and not ai_access.allowed(), 'the hosted site never runs AI without a code, even with none set'


def test_ai_stays_off_until_an_account_enters_a_current_code(app):
    with TestClient(app, base_url='http://localhost') as client:
        assert probe(client) == {'request': False, 'worker': False}, 'signed out'
        signup(client, 'applicant@example.test')
        assert plain(client.get('/auth/ai-access')) == {'required': True, 'granted': False}
        assert probe(client) == {'request': False, 'worker': False}

        refused = client.post('/auth/ai-access', json={'code': 'judges-code-0000'})
        assert refused.status_code == 403 and 'judges' not in refused.text
        assert plain(client.post('/auth/ai-access', json={'code': 'judges-code-1234'})) == {'required': True, 'granted': True}
        assert probe(client) == {'request': True, 'worker': True}
        me = client.get('/auth/me').json()['user']
        assert me['ai_access'] == 'judges' and 'judges-code-1234' not in str(me)

        with TestClient(app, base_url='http://localhost') as other:
            signup(other, 'other@example.test')
            assert probe(other) == {'request': False, 'worker': False}, 'one account’s code never reaches another'

        assert plain(client.request('DELETE', '/auth/ai-access', json={})) == {'required': True, 'granted': False}
        assert probe(client) == {'request': False, 'worker': False}


def test_removing_a_code_name_turns_its_accounts_off(app, monkeypatch):
    with TestClient(app, base_url='http://localhost') as client:
        signup(client, 'applicant@example.test')
        client.post('/auth/ai-access', json={'code': 'team-code-5678'})
        assert probe(client)['request'] is True
        monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', '{"judges": "judges-code-1234"}')
        assert probe(client) == {'request': False, 'worker': False}
        assert plain(client.get('/auth/ai-access')) == {'required': True, 'granted': False}


def test_wrong_codes_are_rate_limited(app, monkeypatch):
    monkeypatch.setenv('BATATIS_AUTH_RATE_LIMIT', '3')
    with TestClient(app, base_url='http://localhost') as client:
        signup(client, 'applicant@example.test')
        statuses = [client.post('/auth/ai-access', json={'code': f'guess-{i}-0000'}).status_code for i in range(5)]
        assert statuses[:3] == [403, 403, 403] and statuses[-1] == 429


def test_scoring_batches_in_worker_threads_keep_the_request_access(monkeypatch):
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', CODES)
    seen = []

    def ask(state, questions, timeout):
        seen.append(ai_access.allowed())
        return {'answers': {key: {'noul': 0.5} for key in questions}, 'usage': {}}

    judge = Judge(ask, workers=4, max_state=1500)
    arts = {f'{i}.1.1.1': {'title': f'Synthetic article {i}', 'part': '3', 'section': '3.1', 'subsection': '3.1.1', 'text': 'Synthetic requirement text. ' * 20} for i in range(12)}
    for granted in (True, False):
        seen.clear()
        token = ai_access.GRANTED.set(granted)
        try:
            assert len(judge.batches('A synthetic proposal.', arts, list(arts))) > 1, 'the work fans out to worker threads'
            judge.judge('A synthetic proposal.', arts, list(arts))
        finally:
            ai_access.GRANTED.reset(token)
        assert seen and set(seen) == {granted}
