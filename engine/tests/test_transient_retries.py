"""A dropped connection or a rate limit is retried; a refused or malformed answer is not."""
from __future__ import annotations

import httpx
import pytest

from engine.identify.screen import Judge, NoRetry
from engine.intake import review


class Coded(NoRetry):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _ask(failures):
    calls = []

    def ask(state, questions, timeout):
        calls.append(1)
        if failures:
            raise failures.pop(0)
        return {'answers': {name: {'noul': 0.5} for name in questions}, 'usage': {}}
    ask.calls = calls
    return ask


ARTS = {'9.10.15.4.': {'id': '9.10.15.4.', 'title': 'Unprotected Openings', 'text': 'Openings.', 'part': 9,
                       'section': 'Fire Protection', 'subsection': 'Spatial Separation'}}


def test_a_transient_scoring_error_is_retried(monkeypatch):
    monkeypatch.setattr('time.sleep', lambda s: None)
    ask = _ask([Coded('rate_limited'), Coded('network')])
    judge = Judge(ask, attempts=3, model='jev-1.13.0', method='jev')
    assert judge.judge('wall near the line', ARTS, ['9.10.15.4.']) == {'9.10.15.4.': 0.5}
    assert len(ask.calls) == 3


@pytest.mark.parametrize('code', ['malformed', 'auth_failed', 'credits_exhausted', None])
def test_a_refused_or_malformed_answer_is_not_retried(monkeypatch, code):
    monkeypatch.setattr('time.sleep', lambda s: None)
    ask = _ask([Coded(code)])
    with pytest.raises(NoRetry):
        Judge(ask, attempts=3, model='jev-1.13.0', method='jev').judge('wall', ARTS, ['9.10.15.4.'])
    assert len(ask.calls) == 1


def test_the_review_transport_retries_a_dropped_connection(monkeypatch):
    monkeypatch.setattr('time.sleep', lambda s: None)
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setattr('engine.llm_gate.authorize', lambda **kw: type('D', (), {'allowed': True, 'reserved_usd': 0})())
    monkeypatch.setattr('engine.llm_gate.record', lambda **kw: None)
    attempts = []

    def post(self, url, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ConnectError('dropped')
        if len(attempts) == 2:
            return httpx.Response(503, request=httpx.Request('POST', url))
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'choices': [{'message': {'content': '{"documents": []}'}}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}})
    monkeypatch.setattr(httpx.Client, 'post', post)
    payload, usage = review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
    assert payload == {'documents': []} and len(attempts) == 3


def test_the_review_never_retries_past_its_deadline(monkeypatch):
    clock = iter([0.0, 0.0, 230.0, 230.0])
    monkeypatch.setattr('time.monotonic', lambda: next(clock))
    monkeypatch.setattr('time.sleep', lambda s: None)
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setattr('engine.llm_gate.authorize', lambda **kw: type('D', (), {'allowed': True, 'reserved_usd': 0})())
    attempts = []

    def post(self, url, **kwargs):
        attempts.append(1)
        raise httpx.ConnectError('dropped')
    monkeypatch.setattr(httpx.Client, 'post', post)
    with pytest.raises(TimeoutError):
        review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
    assert len(attempts) == 1
