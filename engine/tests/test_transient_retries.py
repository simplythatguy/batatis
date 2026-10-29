"""A dropped connection or a rate limit is retried; a refused or malformed answer is not."""
from __future__ import annotations

import anthropic
import httpx2 as hx
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


M = 'claude-sonnet-5-5'
_REQUEST = hx.Request('POST', 'https://api.anthropic.com/v1/messages')


def dropped():
    return anthropic.APIConnectionError(request=_REQUEST)


def timed_out():
    return anthropic.APITimeoutError(request=_REQUEST)


def status(code):
    return anthropic.APIStatusError('error', response=hx.Response(code, request=_REQUEST), body=None)


def answers(*outcomes):
    """A stand-in for the Anthropic call: each attempt raises or returns the next outcome."""
    attempts = []

    def call(system, user, schema, **kw):
        attempts.append(kw)
        outcome = outcomes[min(len(attempts), len(outcomes)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, {'input_tokens': 1, 'output_tokens': 1}
    call.attempts = attempts
    return call


def test_the_review_transport_retries_a_dropped_connection(monkeypatch):
    monkeypatch.setattr('time.sleep', lambda s: None)
    monkeypatch.setattr('engine.llm_gate.authorize', lambda **kw: type('D', (), {'allowed': True, 'reserved_usd': 0})())
    monkeypatch.setattr('engine.llm_gate.release', lambda d: None)
    monkeypatch.setattr('engine.llm_gate.record', lambda **kw: None)
    call = answers(dropped(), status(503), {'documents': []})
    monkeypatch.setattr('engine.anthropic_json.call', call)
    payload, usage = review.anthropic_transport()('system', 'user', {}, M, 'low')
    assert payload == {'documents': []} and len(call.attempts) == 3


def test_the_review_never_retries_past_its_deadline(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr('time.monotonic', lambda: clock[0])
    monkeypatch.setattr('time.sleep', lambda s: None)
    monkeypatch.setattr('engine.llm_gate.authorize', lambda **kw: type('D', (), {'allowed': True, 'reserved_usd': 0})())
    monkeypatch.setattr('engine.llm_gate.release', lambda d: None)
    attempts = []

    def call(*args, **kw):
        attempts.append(1)
        clock[0] = 230.0
        raise dropped()
    monkeypatch.setattr('engine.anthropic_json.call', call)
    with pytest.raises(TimeoutError):
        review.anthropic_transport()('system', 'user', {}, M, 'low')
    assert len(attempts) == 1


@pytest.fixture
def review_spend(monkeypatch):
    from engine import llm_gate

    llm_gate.reset_for_tests()
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'synthetic-key')
    monkeypatch.setenv('BATATIS_STORE', 'file')
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setattr('time.sleep', lambda _: None)
    max_input = len(('system' + 'user' + '{}').encode()) // 3 + 256
    reservation = llm_gate.estimate_usd(M, max_input, review.MAX_OUTPUT_TOKENS)
    yield llm_gate, reservation
    llm_gate.reset_for_tests()


def test_each_review_attempt_reserves_spend_and_an_unknown_outcome_keeps_its_reservation(monkeypatch, review_spend):
    gate, reservation = review_spend
    call = answers(timed_out(), {'documents': []})
    monkeypatch.setattr('engine.anthropic_json.call', call)
    review.anthropic_transport()('system', 'user', {}, M, 'low')
    assert len(call.attempts) == 2
    assert gate._memory.today() == reservation + gate.estimate_usd(M, 1, 1) and reservation > 0


def test_authorization_cannot_dispatch_after_consuming_the_deadline(monkeypatch, review_spend):
    gate, _ = review_spend
    clock = [0.0]
    authorize = gate.authorize

    def delayed(**kwargs):
        decision = authorize(**kwargs)
        clock[0] = 241.0
        return decision

    call = answers({})
    monkeypatch.setattr('time.monotonic', lambda: clock[0])
    monkeypatch.setattr(gate, 'authorize', delayed)
    monkeypatch.setattr('engine.anthropic_json.call', call)
    with pytest.raises(TimeoutError):
        review.anthropic_transport()('system', 'user', {}, M, 'low')
    assert call.attempts == [] and gate._memory.today() == 0


def test_dispatch_uses_the_time_remaining_after_authorization(monkeypatch, review_spend):
    gate, _ = review_spend
    clock = [0.0]
    authorize = gate.authorize

    def delayed(**kwargs):
        decision = authorize(**kwargs)
        clock[0] = 200.0
        return decision

    call = answers({})
    monkeypatch.setattr('time.monotonic', lambda: clock[0])
    monkeypatch.setattr(gate, 'authorize', delayed)
    monkeypatch.setattr('engine.anthropic_json.call', call)
    review.anthropic_transport()('system', 'user', {}, M, 'low')
    assert [a['timeout'] for a in call.attempts] == [40.0]


@pytest.mark.parametrize('code', [400, 401, 403, 404, 408, 422])
def test_review_4xx_other_than_429_are_not_retried(monkeypatch, review_spend, code):
    gate, reservation = review_spend
    call = answers(status(code))
    monkeypatch.setattr('engine.anthropic_json.call', call)
    with pytest.raises(anthropic.APIStatusError):
        review.anthropic_transport()('system', 'user', {}, M, 'low')
    assert len(call.attempts) == 1 and gate._memory.today() == reservation


def test_an_attempt_that_cannot_get_a_connection_releases_only_its_own_reservation(monkeypatch, review_spend):
    gate, _ = review_spend
    call = answers(dropped(), {})
    monkeypatch.setattr('engine.anthropic_json.call', call)
    review.anthropic_transport()('system', 'user', {}, M, 'low')
    assert len(call.attempts) == 2
    assert gate._memory.today() == gate.estimate_usd(M, 1, 1)


def test_review_retry_is_blocked_when_its_own_reservation_would_exceed_the_cap(monkeypatch, review_spend):
    gate, reservation = review_spend
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', str(reservation * 3 / 2))
    call = answers(timed_out())
    monkeypatch.setattr('engine.anthropic_json.call', call)
    with pytest.raises(review.GateClosed):
        review.anthropic_transport()('system', 'user', {}, M, 'low')
    assert len(call.attempts) == 1 and gate._memory.today() == reservation
