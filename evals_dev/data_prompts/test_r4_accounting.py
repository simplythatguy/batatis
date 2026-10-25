"""Actual Judge -> Decisions -> wrapped HTTP accounting, with local response simulation."""
from __future__ import annotations

import copy
import json
import os
import socket
import threading
from contextlib import contextmanager

import httpx
import pytest

from engine.identify import providers, screen
from evals_dev.data_prompts import ledger, sut
from evals_dev.data_prompts.__main__ import _case_cost


@pytest.fixture
def offline(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('R4 regressions must remain offline')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(httpx.Client, 'send', forbidden)
    monkeypatch.setattr(httpx.Client, 'post', httpx.Client.post)
    monkeypatch.setattr(ledger, '_installed', False)
    monkeypatch.setattr(ledger, 'CACHE', tmp_path / 'http')
    monkeypatch.setattr(ledger, 'ATTEMPTS', tmp_path / 'attempts.jsonl')
    monkeypatch.setattr(ledger, 'UNATTRIBUTED', ledger.Ledger())
    monkeypatch.setattr(screen, 'ThreadPoolExecutor', screen.ThreadPoolExecutor)
    monkeypatch.setattr(screen.time, 'sleep', lambda _: None)
    for name in ('BATATIS_LIVE', 'BATATIS_LIVE_ELEPHANT', 'BATATIS_PROVIDER',
                 'BATATIS_DAILY_SPEND_CAP_USD', 'BATATIS_LLM_RATE_LIMIT',
                 'BATATIS_LLM_RATE_WINDOW_SECONDS', 'BATATIS_STORE', 'BATATIS_JEV_UNCAPPED'):
        monkeypatch.setenv(name, os.environ.get(name, ''))
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-placeholder')
    monkeypatch.delenv('DPE_HTTP_CACHE', raising=False)

    @contextmanager
    def metered(provider, model, *args, log=None, **kwargs):
        def settle(tokens_in, tokens_out):
            if log is not None:
                # Deliberately differs from the HTTP price: this estimate must be deduplicated.
                log.add(provider=provider, model=model, input_tokens=tokens_in,
                        output_tokens=tokens_out, usd=.01)
        yield settle

    monkeypatch.setattr(providers, 'metered', metered)
    return tmp_path


def response(body):
    return {'model': body['model'],
            'answers': [{'type': 'predicate', 'name': q['name'], 'probability': .75}
                        for q in body['questions']],
            'usage': {'input_tokens': 1000, 'output_tokens': 100, 'total_tokens': 1100,
                      'input_tokens_details': {'cached_tokens': 100, 'cache_write_tokens': 0},
                      'output_tokens_details': {'reasoning_tokens': 10}}}


def run_judge():
    log = providers.SpendLog()
    ask = providers.metered_decisions_ask(providers.raw_openai_decisions, log=log)
    judge = screen.Judge(ask, max_state=1, workers=2, attempts=2)
    arts = {name: {'title': name, 'part': '3', 'section': 'Walls', 'subsection': 'Dimensions',
                   'text': 'A short synthetic article card.'} for name in ('article-a', 'article-b')}
    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    try:
        assert len(judge.batches('Offline proposal', arts, list(arts))) == 2
        assert judge.judge('Offline proposal', arts, list(arts)) == {'article-a': .75, 'article-b': .75}
    finally:
        ledger.CURRENT.reset(token)
    result = {'errors': [], 'cost': ledger.as_dict(book),
              'identify_spend': {'transport_calls': sut.accounted_calls(log.calls, book.calls)}}
    return book, result, judge


def events():
    return [json.loads(line) for line in ledger.ATTEMPTS.read_text().splitlines()]


def test_real_judge_pool_attributes_retry_and_does_not_hide_unknown_spend(offline, monkeypatch):
    lock = threading.Lock()
    dispatches = []

    def send(self, request, **kwargs):
        body = json.loads(request.content)
        with lock:
            dispatches.append(body)
            first = len(dispatches) == 1
        if first:
            raise httpx.ReadTimeout('offline transient failure', request=request)
        return httpx.Response(200, request=request, json=response(body))

    monkeypatch.setattr(httpx.Client, 'send', send)
    sut.configure(live=False, elephant=False)
    book, result, judge = run_judge()
    summary = book.summary()
    assert len(dispatches) == 3 and judge.usage.requests == 2 and judge.usage.errors == 1
    assert sum(e['event'] == 'attempt_started' for e in events()) == 3
    assert len(ledger.UNATTRIBUTED.calls) == 0
    assert summary['calls'] == summary['live_calls'] == 3
    assert summary['unknown_cost_attempts'] == summary['live_unknown_cost_attempts'] == 1
    assert summary['input_tokens'] == 2000 and summary['output_tokens'] == 200
    assert all(c['http_request_hash'] for c in result['identify_spend']['transport_calls'])
    cost = _case_cost(result)
    assert cost['scoring_usd'] == 0
    assert cost['usd'] == summary['usd'] > 0
    assert cost['cost_complete'] is False


def test_real_judge_cache_replay_has_zero_fresh_dispatch_or_spend(offline, monkeypatch):
    dispatches = []

    def send(self, request, **kwargs):
        body = json.loads(request.content)
        dispatches.append(body)
        return httpx.Response(200, request=request, json=response(body))

    monkeypatch.setattr(httpx.Client, 'send', send)
    sut.configure(live=False, elephant=False)
    first_book, first_result, _ = run_judge()
    assert len(dispatches) == 2
    assert _case_cost(first_result)['usd'] == first_book.summary()['usd'] > 0

    replay_book, replay_result, _ = run_judge()
    assert len(dispatches) == 2
    assert sum(e['event'] == 'cache_hit' for e in events()) == 2
    assert len(ledger.UNATTRIBUTED.calls) == 0
    summary = replay_book.summary()
    assert summary['calls'] == 2 and summary['live_calls'] == 0
    assert summary['usd'] == first_book.summary()['usd']
    assert summary['live_usd'] == 0 and summary['unknown_cost_attempts'] == 0
    assert all(c.from_cache for c in replay_book.calls)
    cost = _case_cost(replay_result)
    assert cost['usd'] == summary['usd'] and cost['live_usd'] == 0
    assert cost['scoring_usd'] == 0 and cost['cost_complete'] is True


def test_real_judge_replayed_retry_retains_unknown_cost_and_cache_provenance(offline, monkeypatch):
    dispatches = []
    lock = threading.Lock()

    def send(self, request, **kwargs):
        body = json.loads(request.content)
        with lock:
            dispatches.append(body)
            first = len(dispatches) == 1
        if first:
            raise httpx.ReadTimeout('offline transient failure', request=request)
        return httpx.Response(200, request=request, json=response(body))

    monkeypatch.setattr(httpx.Client, 'send', send)
    sut.configure(live=False, elephant=False)
    original, _, _ = run_judge()
    replayed, result, _ = run_judge()
    assert len(dispatches) == 3
    assert len(replayed.calls) == 3 and all(c.from_cache for c in replayed.calls)
    assert replayed.summary()['usd'] == original.summary()['usd'] > 0
    assert replayed.summary()['unknown_cost_attempts'] == 1
    assert replayed.summary()['live_unknown_cost_attempts'] == 0
    cost = _case_cost(result)
    assert cost['live_usd'] == 0 and cost['cost_complete'] is False


def usage_call(monkeypatch, usage, *, endpoint=providers.DECISIONS_URL, body=None):
    body = body or {'model': 'gpt-6-luna', 'input': 'offline request', 'questions': []}

    def send(self, request, **kwargs):
        return httpx.Response(200, request=request, json={'usage': usage})

    monkeypatch.setattr(httpx.Client, 'send', send)
    sut.configure(live=False, elephant=False)
    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    try:
        with httpx.Client() as client:
            client.post(endpoint, json=body)
    finally:
        ledger.CURRENT.reset(token)
    return book


def test_decisions_endpoint_usage_is_priced_with_its_own_token_fields(offline, monkeypatch):
    usage = response({'model': 'gpt-6-luna', 'questions': []})['usage']
    book = usage_call(monkeypatch, usage)
    call, = book.calls
    assert (call.input_tokens, call.cached_input_tokens, call.output_tokens, call.reasoning_tokens) == (1000, 100, 100, 10)
    assert call.usd == ledger.price('gpt-6-luna', 1000, 100, 100)
    assert book.summary()['unknown_cost_attempts'] == 0


@pytest.mark.parametrize('change', [
    {'input_tokens': True}, {'input_tokens': -1}, {'output_tokens': '100'},
    {'total_tokens': 1101}, {'input_tokens_details': {'cached_tokens': 1001, 'cache_write_tokens': 0}},
    {'input_tokens_details': {'cached_tokens': '0', 'cache_write_tokens': 0}},
    {'output_tokens_details': {'reasoning_tokens': 101}},
])
def test_malformed_decisions_usage_stays_unknown(offline, monkeypatch, change):
    usage = response({'model': 'gpt-6-luna', 'questions': []})['usage']
    usage.update(copy.deepcopy(change))
    book = usage_call(monkeypatch, usage)
    assert book.summary()['unknown_cost_attempts'] == 1
    assert _case_cost({'cost': ledger.as_dict(book)})['cost_complete'] is False


def test_chat_usage_cannot_be_borrowed_by_decisions_endpoint(offline, monkeypatch):
    book = usage_call(monkeypatch, {'prompt_tokens': 1000, 'completion_tokens': 100})
    assert book.summary()['unknown_cost_attempts'] == 1


def test_decisions_usage_cannot_be_borrowed_by_chat_endpoint(offline, monkeypatch):
    usage = response({'model': 'gpt-6-luna', 'questions': []})['usage']
    book = usage_call(monkeypatch, usage, endpoint=providers.OPENAI_URL,
                      body={'model': 'gpt-6-luna', 'messages': []})
    assert book.summary()['unknown_cost_attempts'] == 1


@pytest.mark.parametrize('provider', ['openai', 'openai_decisions'])
def test_one_recorded_http_call_covers_one_metered_call_only(offline, provider):
    raw = {'provider': provider, 'model': 'gpt-6-luna', 'input_tokens': 1000,
           'output_tokens': 100, 'usd': .01}
    call = ledger.Call('gpt-6-luna', None, 'unknown', 1000, 100, 100, 10, .000141,
                       False, 0, 'recorded-request')
    rows = sut.accounted_calls([raw, raw], [call])
    assert [row['http_request_hash'] for row in rows] == ['recorded-request', None]


def test_other_transport_is_not_deduplicated_by_matching_token_totals(offline):
    raw = {'provider': 'anthropic', 'model': 'gpt-6-luna', 'input_tokens': 1000,
           'output_tokens': 100, 'usd': .01}
    call = ledger.Call('gpt-6-luna', None, 'unknown', 1000, 100, 100, 10, .000141,
                       False, 0, 'recorded-request')
    assert sut.accounted_calls([raw], [call])[0]['http_request_hash'] is None
