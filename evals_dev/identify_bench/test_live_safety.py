"""Provider seams are synthetic; stores and ledger live only in pytest's temporary directory."""
from __future__ import annotations

import time
import threading
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from engine.identify import providers
from evals_dev.identify_bench import live
from evals_dev.identify_bench.cache import Store, request_key


@pytest.fixture
def stores(monkeypatch, tmp_path):
    stores = tuple(Store(name, tmp_path) for name in ('elephant', 'openai', 'spend'))
    monkeypatch.setattr(live, '_stores', lambda: stores)
    monkeypatch.setattr(live, 'load_keys', lambda *a: None)
    monkeypatch.setattr(live, '_live_enabled', True, raising=False)
    monkeypatch.setenv('BENCH_OPENAI_CAP_USD', '6')
    return stores


def request(user='proposal', **kwargs):
    return live.openai_json('test', {'type': 'object'}, 'full corpus', user, **kwargs)


def answer(*args, **kwargs):
    return {'ok': True}, {'input_tokens': 1, 'output_tokens': 1, 'returned_model': 'gpt-6-luna'}


def test_quota_reservations_prevent_concurrent_overshoot(monkeypatch, stores):
    calls = []
    monkeypatch.setattr(live, '_price', lambda *a: 0.4)
    monkeypatch.setenv('BENCH_OPENAI_CAP_USD', '0.6')

    def raw(*args, **kwargs):
        calls.append(1)
        time.sleep(0.03)
        return answer()

    monkeypatch.setattr(providers, 'raw_openai_json', raw)

    def one(i):
        try:
            request(str(i))
        except live.BudgetExhausted:
            return 'capped'
        return 'done'

    with ThreadPoolExecutor(4) as pool:
        outcomes = list(pool.map(one, range(4)))
    assert outcomes.count('done') == len(calls) == 1
    assert live.openai_spent() == 0.4


def test_same_request_dispatches_once_with_concurrent_workers(monkeypatch, stores):
    calls = []

    def raw(*args, **kwargs):
        calls.append(1)
        time.sleep(0.02)
        return answer()

    monkeypatch.setattr(providers, 'raw_openai_json', raw)
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: request(), range(4)))
    assert len(calls) == 1 and all(r[0] == {'ok': True} for r in results)
    assert len(stores[2].rows()) == 1


@pytest.mark.parametrize('failure', ['unknown', 'timeout', 'unreadable'])
def test_failures_are_charged_once_and_expose_fixed_error_tags(monkeypatch, stores, failure):
    calls = []
    monkeypatch.setattr(live, '_price', lambda *a: 0.4)
    monkeypatch.setattr(live.time, 'sleep', lambda _: None)

    def raw(*args, **kwargs):
        calls.append(1)
        message = 'sk-secret /private/path Authorization: Bearer secret'
        if failure == 'timeout':
            raise httpx.ReadTimeout(message)
        if failure == 'unreadable':
            raise providers.UnreadableResponse(message, {'input_tokens': 1, 'output_tokens': 1})
        raise RuntimeError(message)

    monkeypatch.setattr(providers, 'raw_openai_json', raw)
    with pytest.raises(RuntimeError) as error:
        request()
    assert len(calls) == 1 and live.openai_spent() == 0.4
    row, = stores[2].rows()
    assert row['response']['failed'] is True
    assert row['response']['error'] in ('timeout', 'invalid_response', 'internal_error')
    assert 'sk-secret' not in str(error.value) + str(row)
    assert '/private/path' not in str(error.value) + str(row)


def test_cache_only_blocks_before_credentials_transport_or_quota(monkeypatch, stores):
    monkeypatch.setattr(live, '_live_enabled', False, raising=False)
    monkeypatch.setattr(live, 'load_keys', lambda *a: pytest.fail('credential read'))
    monkeypatch.setattr(providers, 'raw_openai_json', lambda *a, **k: pytest.fail('network'))
    with pytest.raises(live.BudgetExhausted):
        request()
    budget = live.ElephantBudget(max_calls=1)
    monkeypatch.setattr(budget, 'take', lambda: pytest.fail('quota touched'))
    with pytest.raises(live.BudgetExhausted):
        live.elephant_ask_unbounded({'proposal': 'x'}, {'q': {'type': 'noul'}}, budget=budget)


def test_existing_cache_key_replays_and_full_prompt_changes_identity(monkeypatch, stores):
    req = {'name': 'test', 'schema': {'type': 'object'}, 'system': 'full corpus', 'user': 'proposal',
           'model': 'gpt-6-luna', 'effort': 'medium', 'max_output_tokens': 16000}
    stores[1].put(request_key('openai', req), {'payload': {'saved': True}, 'usage': {'usd': 0.012}})
    monkeypatch.setattr(live, '_live_enabled', False, raising=False)
    monkeypatch.setattr(live, 'load_keys', lambda *a: pytest.fail('credential read'))
    monkeypatch.setattr(providers, 'raw_openai_json', lambda *a, **k: pytest.fail('network'))
    assert request()[0] == {'saved': True}
    with pytest.raises(live.BudgetExhausted):
        live.openai_json('test', {'type': 'object'}, 'changed corpus', 'proposal')
    assert live.openai_spent() == 0 and len(stores[1].rows()) == 1


def test_elephant_max_calls_is_checked_before_any_quota_refresh(monkeypatch, stores):
    budget = live.ElephantBudget(max_calls=0)
    monkeypatch.setattr(live, 'elephant_quota', lambda: pytest.fail('quota endpoint called'))
    with pytest.raises(live.BudgetExhausted):
        budget.take()


def test_missing_elephant_quota_fails_closed(monkeypatch, stores):
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': None})
    with pytest.raises(live.BudgetExhausted):
        live.ElephantBudget(max_calls=1).take()


def test_independent_requests_overlap_but_no_more_than_three_dispatch(monkeypatch, stores):
    lock, release = threading.Lock(), threading.Event()
    active, maximum = 0, 0

    def raw(*args, **kwargs):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(active, maximum)
            if active == 3:
                release.set()
        assert release.wait(2), 'independent calls were serialized'
        time.sleep(0.02)
        with lock:
            active -= 1
        return answer()

    monkeypatch.setattr(providers, 'raw_openai_json', raw)
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda i: request(str(i)), range(6)))
    assert len(results) == 6 and maximum == 3


@pytest.mark.parametrize('crash', [False, True])
def test_cross_process_reservation_survives_crash_and_enforces_shared_cap(tmp_path, crash):
    source = r'''
import socket, sys, time
from pathlib import Path
from engine.identify import providers
from evals_dev.identify_bench import live
from evals_dev.identify_bench.cache import Store
directory, user, crash = Path(sys.argv[1]), sys.argv[2], sys.argv[3] == 'True'
stores = tuple(Store(name, directory) for name in ('elephant', 'openai', 'spend'))
live._stores = lambda: stores
live.load_keys = lambda *a: None
live._price = lambda *a: 0.4
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network'))
def fake(*a, **k):
    with (directory / 'dispatched').open('a') as f:
        f.write('attempt\n')
    time.sleep(0.04)
    if crash:
        raise SystemExit(17)
    return {'ok': True}, {'input_tokens': 1, 'output_tokens': 1, 'returned_model': 'gpt-6-luna'}
providers.raw_openai_json = fake
with live.live_mode(True):
    try:
        live.openai_json('test', {'type': 'object'}, 'corpus', user)
        print('completed')
    except live.BudgetExhausted:
        print('capped')
'''
    env = {**os.environ, 'BENCH_OPENAI_CAP_USD': '0.6'}
    commands = [[sys.executable, '-B', '-c', source, str(tmp_path), str(i), str(crash)] for i in range(2)]
    processes = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                 for cmd in commands]
    outputs = [p.communicate(timeout=10) for p in processes]
    assert all(not stderr for _, stderr in outputs)
    assert sum('capped' in stdout for stdout, _ in outputs) == 1
    assert len((tmp_path / 'dispatched').read_text().splitlines()) == 1
    row, = Store('spend', tmp_path).rows()
    assert row['response']['usd'] == 0.4
    assert row['response']['state'] == ('reserved' if crash else 'completed')
    assert sorted(p.returncode for p in processes) == ([0, 17] if crash else [0, 0])


def test_elephant_failure_consumes_one_attempt_and_retains_unknown_usage(monkeypatch, stores):
    from engine.identify import elephant_runtime as er
    calls = []
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': 100})

    def fail(*a, **k):
        calls.append(1)
        raise OSError('sk-secret /private/path')

    monkeypatch.setattr(er, '_post_once', fail)
    budget = live.ElephantBudget(max_calls=1)
    with pytest.raises(live.ProviderFailure, match='io_error'):
        live.elephant_ask_unbounded({'proposal': 'x'}, {'q': {'type': 'noul'}}, budget=budget)
    with pytest.raises(live.BudgetExhausted):
        live.elephant_ask_unbounded({'proposal': 'x'}, {'q': {'type': 'noul'}}, budget=budget)
    assert len(calls) == budget.sent == 1
    row, = stores[2].rows()
    assert row['response']['failed'] is True and row['response']['unknown_usage'] is True
    assert 'sk-secret' not in str(row) and '/private/path' not in str(row)


def test_live_mode_restores_parent_choice_after_nested_cache_only_scope(monkeypatch, stores):
    monkeypatch.setattr(live, '_live_enabled', False)
    calls = []

    def raw(*a, **k):
        calls.append(1)
        return answer()

    monkeypatch.setattr(providers, 'raw_openai_json', raw)
    with live.live_mode(True):
        request('first')
        with live.live_mode(False):
            assert request('first')[0] == {'ok': True}
            with pytest.raises(live.BudgetExhausted):
                request('uncached')
        request('second')
    with pytest.raises(live.BudgetExhausted):
        request('after parent mode exits')
    assert len(calls) == 2
