"""Decisions wire contract and metering, with synthetic evidence and no network."""
import json
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import httpx
import pytest

from engine import llm_gate
from engine.identify import providers
from engine.identify.screen import Judge


@pytest.fixture(autouse=True)
def clean_gate(monkeypatch):
    llm_gate.reset_for_tests()
    for name in ('VERCEL', 'BATATIS_STORE', 'BATATIS_PROVIDER'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-not-a-key')
    yield
    llm_gate.reset_for_tests()


def reply(*, questions=('q0', 'q1')):
    return {'model': 'gpt-6-luna',
            'answers': [{'type': 'predicate', 'name': q, 'probability': p}
                        for q, p in zip(questions, (0.0, 0.875))],
            'usage': {'input_tokens': 123, 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                      'output_tokens': 0, 'output_tokens_details': {'reasoning_tokens': 0}, 'total_tokens': 123}}


def test_metered_decisions_uses_dedicated_endpoint_and_preserves_named_probabilities(monkeypatch):
    sent = []

    def handle(request):
        assert llm_gate._memory.today() > 0, 'reserve before network'
        assert str(request.url) == 'https://api.openai.com/v1/decisions'
        assert request.method == 'POST'
        assert request.headers['authorization'] == 'Bearer synthetic-not-a-key'
        assert request.headers['content-type'] == 'application/json'
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=reply())

    client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: client(transport=httpx.MockTransport(handle), **kw))
    state = {'proposal': 'SYNTHETIC: a blue square.', 'articles': {'A0': 'Blue.', 'A1': 'Square.'}}
    questions = {'q0': {'type': 'noul', 'instructions': 'Is A0 about red?'},
                 'q1': {'type': 'noul', 'instructions': 'Is A1 about shape?'}}
    log = providers.SpendLog()
    ask = providers.metered_decisions_ask(providers.raw_openai_decisions, log=log)
    result = ask(state, questions, 5)
    assert sent == [{'model': 'gpt-6-luna', 'input': json.dumps(state), 'questions': [
        {'type': 'predicate', 'name': 'q0', 'instructions': 'Is A0 about red?'},
        {'type': 'predicate', 'name': 'q1', 'instructions': 'Is A1 about shape?'}]}]
    assert result['answers'] == {'q0': {'noul': 0.0}, 'q1': {'noul': 0.875}}
    assert result['usage'] == reply()['usage']
    assert result['model'] == 'gpt-6-luna'
    assert len(log.calls) == 1 and log.calls[0]['input_tokens'] == 123
    assert log.calls[0]['provider'] == 'openai_decisions'
    assert llm_gate._memory.today() == llm_gate.estimate_usd('gpt-6-luna', 123, 0) > Decimal('0')


def ask_two(raw):
    return providers.metered_decisions_ask(raw)('SYNTHETIC: shape', {
        'q0': {'type': 'noul', 'instructions': 'Is it round?'},
        'q1': {'type': 'noul', 'instructions': 'Is it blue?'}}, 5)


@pytest.mark.parametrize('damage', [
    lambda d: d['answers'].pop(),
    lambda d: d['answers'].append(deepcopy(d['answers'][0])),
    lambda d: d['answers'][1].update(name='q0'),
    lambda d: d['answers'][1].update(name='extra'),
    lambda d: d['answers'][0].pop('name'),
    lambda d: d['answers'].reverse(),
    lambda d: d['answers'][0].update(type='refusal'),
    lambda d: d['answers'][0].update(type='choice'),
    lambda d: d.update(model='wrong-model'),
    lambda d: d.update(answers={}),
    lambda d: d['answers'].__setitem__(0, None),
] + [lambda d, p=p: d['answers'][0].update(probability=p)
     for p in (True, False, None, '0.5', -0.01, 1.01, float('nan'), float('inf'), -float('inf'))])
def test_malformed_or_refused_answers_fail_without_retry_but_settle_reported_usage(damage):
    data = reply()
    damage(data)
    with pytest.raises(providers.DecisionsProtocolError):
        ask_two(lambda *_: data)
    assert llm_gate._memory.today() == llm_gate.estimate_usd('gpt-6-luna', 123, 0)


@pytest.mark.parametrize('field,value', [('input_tokens', None), ('output_tokens', True),
                                        ('input_tokens', -1), ('input_tokens', 1.5)])
def test_missing_or_invalid_usage_fails_without_fabricating_tokens(field, value):
    data = reply()
    data['usage'][field] = value
    with pytest.raises(providers.DecisionsProtocolError):
        ask_two(lambda *_: data)
    assert llm_gate._memory.today() == 0


def test_inconsistent_total_usage_cannot_produce_scores():
    data = reply()
    data['usage']['total_tokens'] = 999
    with pytest.raises(providers.DecisionsProtocolError):
        ask_two(lambda *_: data)
    assert llm_gate._memory.today() == llm_gate.estimate_usd('gpt-6-luna', 123, 0)


@pytest.mark.parametrize('kind', ['timeout', 'http', 'invalid_json'])
def test_failure_before_usage_releases_reservation(monkeypatch, kind):
    def handle(request):
        assert llm_gate._memory.today() > 0
        if kind == 'timeout':
            raise httpx.ReadTimeout('synthetic timeout', request=request)
        return httpx.Response(503 if kind == 'http' else 200, content=b'not JSON')
    client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: client(transport=httpx.MockTransport(handle), **kw))
    with pytest.raises((httpx.HTTPError, ValueError)):
        ask_two(providers.raw_openai_decisions)
    assert llm_gate._memory.today() == 0


def test_closed_budget_makes_no_call(monkeypatch):
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0')
    with pytest.raises(providers.GateClosed):
        ask_two(lambda *_: pytest.fail('network beyond budget'))
    assert llm_gate._memory.today() == 0


def test_concurrent_calls_settle_without_losing_or_leaking_reservations():
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: ask_two(lambda *_: reply()), range(16)))
    assert len(results) == 16
    assert llm_gate._memory.today() == 16 * llm_gate.estimate_usd('gpt-6-luna', 123, 0)


@pytest.mark.parametrize('n', [0, 401])
def test_question_limit_is_enforced_before_reserving_or_network(n):
    ask = providers.metered_decisions_ask(lambda *_: pytest.fail('invalid request sent'))
    with pytest.raises(providers.DecisionsProtocolError):
        ask('SYNTHETIC', {f'q{i}': {'type': 'noul', 'instructions': 'True?'} for i in range(n)}, 5)
    assert llm_gate._memory.today() == 0


def test_judge_batches_tiny_cards_below_400_question_limit():
    counts = []
    def raw(body, timeout):
        counts.append(len(body['questions']))
        return {**reply(), 'answers': [{'type': 'predicate', 'name': q['name'], 'probability': 0.5}
                                       for q in body['questions']]}
    arts = {str(i): {'title': 'SYNTHETIC', 'part': 9, 'section': '', 'subsection': '', 'text': 'x'}
            for i in range(801)}
    judge = Judge(providers.metered_decisions_ask(raw), chars=1, max_state=1_000_000, workers=3, attempts=1)
    assert len(judge.judge('SYNTHETIC', arts, list(arts))) == 801
    assert sorted(counts) == [1, 400, 400]


@pytest.mark.parametrize('refuse', [True, False])
def test_judge_does_not_retry_refusals_but_retries_transient_failures(monkeypatch, refuse):
    from engine.identify import screen
    monkeypatch.setattr(screen.time, 'sleep', lambda _: None)
    calls = []
    def raw(body, timeout):
        calls.append(body)
        if refuse:
            return {**reply(), 'answers': [{'type': 'refusal', 'name': 'q0'}]}
        if len(calls) == 1:
            raise httpx.ReadTimeout('synthetic timeout')
        return reply(questions=('q0',))
    arts = {'synthetic': {'title': 'SYNTHETIC', 'part': 9, 'section': '', 'subsection': '', 'text': 'x'}}
    judge = Judge(providers.metered_decisions_ask(raw), attempts=4)
    if refuse:
        with pytest.raises(providers.DecisionsProtocolError):
            judge.judge('SYNTHETIC', arts, ['synthetic'])
        assert len(calls) == 1
    else:
        assert judge.judge('SYNTHETIC', arts, ['synthetic']) == {'synthetic': 0.0}
        assert len(calls) == 2 and judge.usage.errors == 1
    assert llm_gate._memory.today() == llm_gate.estimate_usd('gpt-6-luna', 123, 0)
