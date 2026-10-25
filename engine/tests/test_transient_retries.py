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
    clock = [0.0]
    monkeypatch.setattr('time.monotonic', lambda: clock[0])
    monkeypatch.setattr('time.sleep', lambda s: None)
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.setattr('engine.llm_gate.authorize', lambda **kw: type('D', (), {'allowed': True, 'reserved_usd': 0})())
    attempts = []

    def post(self, url, **kwargs):
        attempts.append(1)
        clock[0] = 230.0
        raise httpx.ConnectError('dropped')
    monkeypatch.setattr(httpx.Client, 'post', post)
    with pytest.raises(TimeoutError):
        review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
    assert len(attempts) == 1


def test_each_review_attempt_reserves_spend_and_an_unknown_outcome_keeps_its_reservation(monkeypatch):
    from decimal import Decimal
    from engine import llm_gate

    llm_gate.reset_for_tests()
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    monkeypatch.setenv('BATATIS_STORE', 'file')
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setattr('time.sleep', lambda _: None)
    attempts = []

    def post(self, url, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ReadTimeout('dispatched but outcome unknown')
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'choices': [{'message': {'content': '{"documents": []}'}}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1}})

    monkeypatch.setattr(httpx.Client, 'post', post)
    max_input = len(('system' + 'user' + '{}').encode()) // 3 + 256
    reservation = llm_gate.estimate_usd('gpt-6-luna', max_input, review.MAX_OUTPUT_TOKENS)
    actual = llm_gate.estimate_usd('gpt-6-luna', 1, 1)
    try:
        review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
        assert len(attempts) == 2
        assert llm_gate._memory.today() == reservation + actual
        assert reservation > Decimal('0')
    finally:
        llm_gate.reset_for_tests()


@pytest.fixture
def review_spend(monkeypatch):
    from engine import llm_gate

    llm_gate.reset_for_tests()
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    monkeypatch.setenv('BATATIS_STORE', 'file')
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setattr('time.sleep', lambda _: None)
    max_input = len(('system' + 'user' + '{}').encode()) // 3 + 256
    reservation = llm_gate.estimate_usd('gpt-6-luna', max_input, review.MAX_OUTPUT_TOKENS)
    yield llm_gate, reservation
    llm_gate.reset_for_tests()


def test_authorization_cannot_dispatch_after_consuming_the_deadline(monkeypatch, review_spend):
    gate, _ = review_spend
    clock, sent = [0.0], []
    authorize = gate.authorize

    def delayed(**kwargs):
        decision = authorize(**kwargs)
        clock[0] = 241.0
        return decision

    monkeypatch.setattr('time.monotonic', lambda: clock[0])
    monkeypatch.setattr(gate, 'authorize', delayed)
    monkeypatch.setattr(httpx.Client, 'post', lambda *args, **kwargs: sent.append(1))
    with pytest.raises(TimeoutError):
        review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
    assert sent == [] and gate._memory.today() == 0


def test_dispatch_uses_the_time_remaining_after_authorization(monkeypatch, review_spend):
    gate, _ = review_spend
    clock, timeouts = [0.0], []
    authorize = gate.authorize

    def delayed(**kwargs):
        decision = authorize(**kwargs)
        clock[0] = 200.0
        return decision

    def post(client, url, **kwargs):
        timeouts.append(client.timeout.read)
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'choices': [{'message': {'content': '{}'}}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1}})

    monkeypatch.setattr('time.monotonic', lambda: clock[0])
    monkeypatch.setattr(gate, 'authorize', delayed)
    monkeypatch.setattr(httpx.Client, 'post', post)
    review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
    assert timeouts == [40.0]


@pytest.mark.parametrize('usage', [None, {}, [], {'prompt_tokens': 1},
    {'prompt_tokens': -1, 'completion_tokens': 1}, {'prompt_tokens': True, 'completion_tokens': 1},
    {'prompt_tokens': '1', 'completion_tokens': 1}, {'prompt_tokens': 1.5, 'completion_tokens': 1}])
def test_success_without_valid_usage_keeps_its_reservation(monkeypatch, review_spend, usage):
    gate, reservation = review_spend

    def post(client, url, **kwargs):
        data = {'choices': [{'message': {'content': '{}'}}]}
        if usage is not None:
            data['usage'] = usage
        return httpx.Response(200, request=httpx.Request('POST', url), json=data)

    monkeypatch.setattr(httpx.Client, 'post', post)
    payload, _ = review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
    assert payload == {} and gate._memory.today() == reservation


@pytest.mark.parametrize('code', [400, 401, 403, 404, 408, 422])
def test_review_4xx_other_than_429_are_not_retried(monkeypatch, review_spend, code):
    gate, reservation = review_spend
    sent = []

    def post(client, url, **kwargs):
        sent.append(1)
        return httpx.Response(code, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx.Client, 'post', post)
    with pytest.raises(httpx.HTTPStatusError):
        review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
    assert sent == [1] and gate._memory.today() == reservation


def test_an_attempt_that_cannot_get_a_connection_releases_only_its_own_reservation(monkeypatch, review_spend):
    gate, _ = review_spend
    sent = []

    def post(client, url, **kwargs):
        sent.append(1)
        if len(sent) == 1:
            raise httpx.PoolTimeout('no connection acquired')
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'choices': [{'message': {'content': '{}'}}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1}})

    monkeypatch.setattr(httpx.Client, 'post', post)
    review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
    assert sent == [1, 1]
    assert gate._memory.today() == gate.estimate_usd('gpt-6-luna', 1, 1)


def test_review_retry_is_blocked_when_its_own_reservation_would_exceed_the_cap(monkeypatch):
    from engine import llm_gate

    llm_gate.reset_for_tests()
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    monkeypatch.setenv('BATATIS_STORE', 'file')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.03')
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setattr('time.sleep', lambda _: None)
    attempts = []

    def post(self, url, **kwargs):
        attempts.append(1)
        raise httpx.ReadTimeout('dispatched but outcome unknown')

    monkeypatch.setattr(httpx.Client, 'post', post)
    try:
        with pytest.raises(review.GateClosed):
            review.openai_transport()('system', 'user', {}, 'gpt-6-luna', 'medium')
        assert len(attempts) == 1
        assert llm_gate._memory.today() > 0
    finally:
        llm_gate.reset_for_tests()
