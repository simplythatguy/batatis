"""Hosted AI for the desktop app: an access code runs Batatis's pinned steps on the server's keys."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from engine import llm_gate
from engine.api import create_app
from engine.store import CaseStore

SERVER_KEY = 'sk-server-secret-never-sent-back'
REQUEST = {'task': 'intake', 'system': 'SYSTEM verbatim', 'user': '{"text":"synthetic"}', 'model': 'gpt-6-luna', 'effort': 'medium',
           'schema': {'type': 'object', 'additionalProperties': False, 'required': ['facts'], 'properties': {'facts': {'type': 'array'}}},
           'maxOutputTokens': 1200}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', '{"judges": "judges-code-aaaaaaaaaaaaaaaa"}')
    llm_gate.reset_for_tests()
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', SERVER_KEY)
    sent = []
    reply = {'value': None}

    def post(self, url, **kwargs):
        sent.append({'url': url, **kwargs})
        if reply['value'] is not None:
            if isinstance(reply['value'], Exception):
                raise reply['value']
            return reply['value']
        if url.endswith('/chat/completions'):
            return httpx.Response(200, json={'model': 'gpt-6-luna', 'usage': {'prompt_tokens': 40, 'completion_tokens': 9},
                                             'choices': [{'finish_reason': 'stop', 'message': {'content': '{"facts": []}'}}]})
        return httpx.Response(200, json={'answers': {'q0': {'noul': 0.7}}, 'usage': {'input_tokens': 30, 'output_tokens': 2}})

    monkeypatch.setattr(httpx.Client, 'post', post)
    with TestClient(create_app(store=CaseStore(tmp_path / 'accounts.sqlite')), base_url='http://localhost') as test_client:
        test_client.sent = sent
        test_client.reply = reply
        yield test_client


def complete(client, code='judges-code-aaaaaaaaaaaaaaaa', **change):
    return client.post('/hosted-ai/complete', json={**REQUEST, **change}, headers={'X-Batatis-Access-Code': code} if code else {})


def test_a_valid_code_runs_the_pinned_step_on_the_server_key_and_never_returns_it(client):
    reply = complete(client)
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert {key: body[key] for key in ('json', 'model', 'effort', 'usage')} == {
        'json': {'facts': []}, 'model': 'gpt-6-luna', 'effort': 'medium', 'usage': {'inputTokens': 40, 'outputTokens': 9}}
    assert SERVER_KEY not in reply.text
    [call] = client.sent
    assert call['headers']['Authorization'] == 'Bearer ' + SERVER_KEY
    assert call['json']['model'] == 'gpt-6-luna' and call['json']['reasoning_effort'] == 'medium'
    assert call['json']['messages'] == [{'role': 'system', 'content': 'SYSTEM verbatim'}, {'role': 'user', 'content': '{"text":"synthetic"}'}]
    assert call['json']['response_format']['json_schema']['strict'] is True


@pytest.mark.parametrize('code', [None, '', 'judges-code-zzzzzzzzzzzzzzzz'])
def test_no_or_wrong_code_never_reaches_a_provider(client, code):
    assert complete(client, code=code).status_code == 403
    assert client.sent == []


@pytest.mark.parametrize('change', [{'model': 'gpt-6.1-sol'}, {'effort': 'high'}, {'task': 'anything'}, {'maxOutputTokens': 0}])
def test_only_the_pinned_desktop_profile_is_answered(client, change):
    assert complete(client, **change).status_code == 422
    assert client.sent == []


def test_the_site_spend_cap_still_applies(client, monkeypatch):
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0')
    assert complete(client).status_code == 503
    assert client.sent == []


def test_screening_forwards_only_the_pinned_profile(client, monkeypatch):
    monkeypatch.setenv('JEV_API_KEY', 'jev-server-secret')
    headers = {'X-Batatis-Access-Code': 'judges-code-aaaaaaaaaaaaaaaa'}
    wrong = json.dumps({'model': 'other', 'questions': {'q0': 'x'}, 'state': {}})
    assert client.post('/hosted-ai/screen', json={'body': wrong}, headers=headers).status_code == 422
    good = json.dumps({'model': 'jev-1.13.0', 'questions': {'q0': 'Does A0 govern?'}, 'state': {'proposal': 'synthetic'}})
    assert client.post('/hosted-ai/screen', json={'body': good}).status_code == 403
    reply = client.post('/hosted-ai/screen', json={'body': good}, headers=headers)
    assert reply.status_code == 200, reply.text
    assert json.loads(reply.json()['body'])['answers']['q0']['noul'] == 0.7
    assert 'jev-server-secret' not in reply.text
    [call] = client.sent
    assert call['content'] == good and call['headers']['Authorization'] == 'Bearer jev-server-secret'


def test_wrong_codes_from_one_address_stop_all_checks_there(client):
    for _ in range(10):
        assert complete(client, code='judges-code-zzzzzzzzzzzzzzzz').status_code == 403
    blocked = complete(client)
    assert blocked.status_code == 429, 'even the right code waits once the address has guessed too often'
    assert client.sent == []


def test_document_review_gets_its_full_output_budget(client):
    assert complete(client, task='document-review', maxOutputTokens=32000).status_code == 200
    assert client.sent[0]['json']['max_completion_tokens'] == 32000


def test_the_ledger_keeps_the_reservation_without_usage_and_frees_it_when_nothing_was_sent(client):
    assert complete(client).status_code == 200
    reported = llm_gate._memory.today()
    assert 0 < reported < 0.01, 'reported usage replaces the reservation'
    client.reply['value'] = httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{"facts": []}'}}]})
    assert complete(client).status_code == 200
    without_usage = llm_gate._memory.today() - reported
    assert without_usage > reported, 'no reported usage keeps the worst-case reservation'
    before = llm_gate._memory.today()
    client.reply['value'] = httpx.ConnectError('offline')
    assert complete(client).status_code == 503
    assert llm_gate._memory.today() == before, 'a request that never reached the service costs nothing'


def test_an_unreadable_answer_is_a_clean_error(client):
    client.reply['value'] = httpx.Response(200, content=b'not json')
    reply = complete(client)
    assert reply.status_code == 502 and SERVER_KEY not in reply.text
