"""Hosted AI for the desktop app: an access code runs Batatis's pinned steps on the server's keys."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.store import CaseStore

SERVER_KEY = 'sk-server-secret-never-sent-back'
REQUEST = {'task': 'intake', 'system': 'SYSTEM verbatim', 'user': '{"text":"synthetic"}', 'model': 'gpt-6-luna', 'effort': 'medium',
           'schema': {'type': 'object', 'additionalProperties': False, 'required': ['facts'], 'properties': {'facts': {'type': 'array'}}},
           'maxOutputTokens': 1200}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', '{"judges": "judges-code-1234"}')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', SERVER_KEY)
    sent = []

    def post(self, url, **kwargs):
        sent.append({'url': url, **kwargs})
        if url.endswith('/chat/completions'):
            return httpx.Response(200, json={'model': 'gpt-6-luna', 'usage': {'prompt_tokens': 40, 'completion_tokens': 9},
                                             'choices': [{'finish_reason': 'stop', 'message': {'content': '{"facts": []}'}}]})
        return httpx.Response(200, json={'answers': {'q0': {'noul': 0.7}}, 'usage': {'input_tokens': 30, 'output_tokens': 2}})

    monkeypatch.setattr(httpx.Client, 'post', post)
    with TestClient(create_app(store=CaseStore(tmp_path / 'accounts.sqlite')), base_url='http://localhost') as test_client:
        test_client.sent = sent
        yield test_client


def complete(client, code='judges-code-1234', **change):
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


@pytest.mark.parametrize('code', [None, '', 'judges-code-0000'])
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
    headers = {'X-Batatis-Access-Code': 'judges-code-1234'}
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
