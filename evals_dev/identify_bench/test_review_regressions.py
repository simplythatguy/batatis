"""Review regressions: real benchmark paths, fake HTTP peers, temporary ledgers only."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
from datetime import datetime, timezone

import httpx
import pytest

from evals_dev.identify_bench import live
from evals_dev.identify_bench.cache import Store

QUESTIONS = {'q': {'type': 'noul', 'instructions': 'Is it applicable?'}}


@pytest.fixture
def stores(monkeypatch, tmp_path):
    stores = tuple(Store(name, tmp_path) for name in ('elephant', 'openai', 'spend'))
    monkeypatch.setattr(live, '_stores', lambda: stores)
    monkeypatch.setattr(live, 'load_keys', lambda *a: None)
    monkeypatch.setattr(live, '_live_enabled', True)
    monkeypatch.setattr(live, 'MIN_INTERVAL', 0)
    monkeypatch.setenv('BENCH_OPENAI_CAP_USD', '6')
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-test')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'offline-test')
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('network'))
    return stores


def openai_response(monkeypatch, usage_fields, content):
    """Keep raw_openai_json intact so its missing-count defaults reach the benchmark."""
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(200, json={'model': 'gpt-6-luna', **usage_fields,
                                        'choices': [{'message': {'content': content}}]})

    client = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: client(
        transport=httpx.MockTransport(respond), **kwargs))
    return sent


def openai_request():
    return live.openai_json('review', {'type': 'object'}, 'nonempty corpus', 'nonempty proposal')


@pytest.mark.parametrize('content', ['{}', 'not JSON'], ids=['readable', 'unreadable'])
@pytest.mark.parametrize('usage_fields', [
    {}, {'usage': None}, {'usage': {}},
    {'usage': {'prompt_tokens': 100}}, {'usage': {'completion_tokens': 40}},
    {'usage': {'prompt_tokens': 0, 'completion_tokens': 0}},
    {'usage': {'prompt_tokens': 0, 'completion_tokens': 40}},
    {'usage': {'prompt_tokens': 100, 'completion_tokens': 0}},
    {'usage': {'prompt_tokens': -1, 'completion_tokens': 40}},
    {'usage': {'prompt_tokens': 100, 'completion_tokens': True}},
    {'usage': {'prompt_tokens': 100.0, 'completion_tokens': 40}},
    {'usage': {'prompt_tokens': 100, 'completion_tokens': '40'}},
], ids=['absent', 'null', 'empty', 'missing-output', 'missing-input', 'zeros',
        'zero-input', 'zero-output', 'negative', 'boolean', 'float', 'string'])
def test_raw_openai_unknown_usage_retains_reservation(monkeypatch, stores, usage_fields, content):
    sent = openai_response(monkeypatch, usage_fields, content)
    with pytest.raises(live.ProviderFailure) as error:
        openai_request()
    row, = stores[2].rows()
    charge = row['response']
    assert len(sent) == 1
    assert charge['reserved_usd'] > 0
    assert charge['usd'] == charge['reserved_usd'] == live.openai_spent()
    assert charge['unknown_usage'] is True
    assert error.value.usage['unknown_usage'] is True
    assert not {'input_tokens', 'output_tokens'} & charge.keys()
    assert stores[1].rows() == []


@pytest.mark.parametrize('content', ['{}', 'not JSON'], ids=['readable', 'unreadable'])
def test_raw_openai_explicit_usage_settles_reported_tokens(monkeypatch, stores, content):
    sent = openai_response(monkeypatch, {'usage': {'prompt_tokens': 100, 'completion_tokens': 40}}, content)
    if content == '{}':
        payload, usage = openai_request()
        assert payload == {} and usage['usd'] == 0.00005
    else:
        with pytest.raises(live.ProviderFailure):
            openai_request()
    row, = stores[2].rows()
    charge = row['response']
    assert len(sent) == 1
    assert charge['usd'] == live.openai_spent() == 0.00005
    assert charge['usd'] < charge['reserved_usd']
    assert charge['unknown_usage'] is False
    assert (charge['input_tokens'], charge['output_tokens']) == (100, 40)


@pytest.mark.parametrize('quota_is_current', [False, True], ids=['stale-quota', 'accounted-quota'])
def test_elephant_budgets_share_the_daily_reserve(monkeypatch, stores, quota_is_current):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    sent, checked = [], []

    def quota():
        used = len(sent) if quota_is_current else 0
        checked.append(used)
        return {'remaining': 12 - used, 'used': used, 'limit': 12}

    def post(*args):
        sent.append(1)
        return fake_elephant_post(*args)

    monkeypatch.setattr(live, 'elephant_quota', quota)
    monkeypatch.setattr(er, '_post_once', post)
    budgets = [live.ElephantBudget(reserve=4, max_calls=12) for _ in range(2)]
    for budget in budgets:
        budget.remaining = 12
    completed = 0
    for i in range(12):
        try:
            live.elephant_ask_unbounded({'proposal': f'proposal {i}'},
                                       QUESTIONS,
                                       budget=budgets[i % 2])
        except live.BudgetExhausted:
            break
        completed += 1
    # Current remote usage is deliberately counted again; reserve safety takes priority
    # over exhausting the allowance when the aggregate cannot identify local attempts.
    assert 0 < completed == len(sent) <= 8
    assert 12 - completed >= 4
    assert sum(b.sent for b in budgets) == completed
    assert len(checked) == completed + 1  # Refresh before every prospective dispatch.
    rows = stores[2].rows()
    assert len(rows) == completed
    assert min(r['response']['quota_remaining_after'] for r in rows) >= 4
    assert {r['response']['quota_day'] for r in rows} == {datetime.now(timezone.utc).date().isoformat()}


@pytest.mark.parametrize('crossing', ['credential-load', 'reservation-save', 'provider-dispatch'])
def test_midnight_between_admission_and_dispatch_cannot_erase_reserve(monkeypatch, stores, crossing):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    before = datetime(2026, 10, 24, 23, 59, 59, tzinfo=timezone.utc).timestamp()
    after, clock, sent = before + 2, [before], []
    monkeypatch.setattr(live.time, 'time', lambda: clock[0])
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': 12, 'used': 0, 'limit': 12})
    if crossing == 'credential-load':
        monkeypatch.setattr(live, 'load_keys', lambda *args: clock.__setitem__(0, after))
    elif crossing == 'reservation-save':
        original = stores[2].put
        def save(key, response, **meta):
            original(key, response, **meta)
            if response.get('state') == 'reserved':
                clock[0] = after
        monkeypatch.setattr(stores[2], 'put', save)
    def post(*args):
        if crossing == 'provider-dispatch':
            clock[0] = after
        sent.append(clock[0])
        return fake_elephant_post(*args)
    monkeypatch.setattr(er, '_post_once', post)
    budget = live.ElephantBudget(reserve=4, max_calls=12)
    for index in range(12):
        try:
            live.elephant_ask({'proposal': str(index)}, QUESTIONS, budget=budget)
        except live.BudgetExhausted:
            break
    assert all(stamp == after for stamp in sent)
    assert 12 - len(sent) >= 4


@pytest.mark.parametrize('accounted', [False, True], ids=['pending-legacy', 'accounted-reservation'])
@pytest.mark.parametrize('state', ['completed', 'failed', 'reserved'])
def test_elephant_existing_attempt_remains_reserved_after_remote_catch_up(monkeypatch, stores, accounted, state):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    quota = {'quota_day': datetime.now(timezone.utc).date().isoformat(),
             'quota_remaining_after': 5} if accounted else {}
    stores[2].put('existing', {'usd': 0, 'provider': 'elephant', 'started_at': live.time.time(),
                              'state': state, 'unknown_usage': state != 'completed', **quota})
    monkeypatch.setattr(live, 'elephant_quota', lambda: {
        'remaining': 5 if accounted else 6, 'used': int(accounted), 'limit': 6})
    monkeypatch.setattr(er, '_post_once', fake_elephant_post)
    budget = live.ElephantBudget(reserve=4, max_calls=3)
    admitted = int(not accounted)
    if admitted:
        live.elephant_ask_unbounded({'proposal': 'one'}, QUESTIONS, budget=budget)
    with pytest.raises(live.BudgetExhausted):
        live.elephant_ask_unbounded({'proposal': 'two'}, QUESTIONS, budget=budget)
    assert budget.sent == admitted and len(stores[2].rows()) == 1 + admitted


def test_elephant_legacy_attempt_cannot_be_credited_against_unrelated_remote_usage(monkeypatch, stores):
    from engine.identify import elephant_runtime as er
    stores[2].put('legacy', {'usd': 0, 'provider': 'elephant', 'started_at': live.time.time(),
                            'state': 'reserved', 'unknown_usage': True})
    # The remote 100 may all predate this unresolved attempt; it supplies no acknowledgement.
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': 5, 'used': 100, 'limit': 105})
    monkeypatch.setattr(er, '_post_once', lambda *a: pytest.fail('reserve breached'))
    with pytest.raises(live.BudgetExhausted):
        live.elephant_ask_unbounded({'proposal': 'new'}, QUESTIONS,
                                   budget=live.ElephantBudget(reserve=4, max_calls=3))
    assert len(stores[2].rows()) == 1


def test_elephant_legacy_attempt_after_a_quota_reservation_is_retained(monkeypatch, stores):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    entry = {'usd': 0, 'provider': 'elephant', 'started_at': live.time.time(),
             'state': 'reserved', 'unknown_usage': True}
    stores[2].put('reserved', {**entry, 'quota_day': datetime.now(timezone.utc).date().isoformat(),
                              'quota_remaining_after': 6})
    stores[2].put('legacy', entry)
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': 12, 'used': 0, 'limit': 12})
    monkeypatch.setattr(er, '_post_once', fake_elephant_post)
    budget = live.ElephantBudget(reserve=4, max_calls=3)
    live.elephant_ask_unbounded({'proposal': 'one'}, QUESTIONS, budget=budget)
    with pytest.raises(live.BudgetExhausted):
        live.elephant_ask_unbounded({'proposal': 'two'}, QUESTIONS, budget=budget)
    assert budget.sent == 1 and len(stores[2].rows()) == 3


def test_elephant_remote_allowance_drop_is_seen_before_next_dispatch(monkeypatch, stores):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    readings = iter([{'remaining': 12}, {'remaining': 5}])
    monkeypatch.setattr(live, 'elephant_quota', lambda: next(readings))
    monkeypatch.setattr(er, '_post_once', fake_elephant_post)
    budget = live.ElephantBudget(reserve=4, max_calls=12)
    live.elephant_ask_unbounded({'proposal': 'one'}, QUESTIONS, budget=budget)
    with pytest.raises(live.BudgetExhausted):
        live.elephant_ask_unbounded({'proposal': 'two'}, QUESTIONS, budget=budget)
    assert budget.sent == 1 and len(stores[2].rows()) == 1


@pytest.mark.parametrize('progress', ['stale', 'current', 'catch-up', 'unrelated'])
def test_elephant_remote_progress_cannot_acknowledge_local_attempts(monkeypatch, stores, progress):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    sent = []

    def unrelated():
        return 7 if progress == 'unrelated' and sent else 0

    def quota():
        reported_local = len(sent) if progress == 'current' or progress == 'catch-up' and len(sent) >= 2 else 0
        used = reported_local + unrelated()
        return {'remaining': 12 - used, 'used': used, 'limit': 12}

    def post(*args):
        sent.append(1)
        return fake_elephant_post(*args)

    monkeypatch.setattr(live, 'elephant_quota', quota)
    monkeypatch.setattr(er, '_post_once', post)
    budgets = [live.ElephantBudget(reserve=4, max_calls=12) for _ in range(2)]
    for i in range(12):
        try:
            live.elephant_ask_unbounded({'proposal': f'proposal {i}'}, QUESTIONS, budget=budgets[i % 2])
        except live.BudgetExhausted as error:
            assert error.code == 'quota_exhausted'
            break
        actual_remaining = 12 - len(sent) - unrelated()
        assert actual_remaining >= 4, f'actual remaining {actual_remaining} breached reserve 4'
    else:
        pytest.fail('shared reserve never stopped dispatch')
    assert 0 < len(sent) <= 8
    if progress == 'unrelated':
        assert len(sent) == 1  # The remote five still excludes the first local attempt.
    assert sum(b.sent for b in budgets) == len(stores[2].rows()) == len(sent)
    assert 12 - len(sent) - unrelated() >= 4


@pytest.mark.parametrize('bounded', [False, True], ids=['unbounded', 'bounded'])
@pytest.mark.parametrize('reported', [False, True], ids=['unknown-usage', 'known-usage'])
def test_elephant_failure_exposes_its_safe_ledger_usage(monkeypatch, stores, bounded, reported):
    from engine.identify import elephant_runtime as er
    sent = []
    usage = {'input_tokens': 100, 'output_tokens': 40, 'cost': 0} if reported else None
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': 12})

    def post(*args):
        sent.append(1)
        return 200, json.dumps({'model': er.RESPONSE_MODEL, 'usage': usage, 'answers': {},
                                'private': 'sk-secret /private/path'}).encode()

    monkeypatch.setattr(er, '_post_once', post)
    ask = live.elephant_ask if bounded else live.elephant_ask_unbounded
    budget = live.ElephantBudget(reserve=4, max_calls=1)
    with pytest.raises(live.ProviderFailure) as error:
        ask({'proposal': 'failed'}, QUESTIONS, budget=budget)
    row, = stores[2].rows()
    charge = row['response']
    public = error.value.usage
    assert public['usd'] == charge['usd'] == 0
    assert public['unknown_usage'] is charge['unknown_usage'] is (not reported)
    assert type(public['seconds']) in (int, float) and public['seconds'] >= 0
    if reported:
        assert (public['input_tokens'], public['output_tokens']) == (100, 40)
        assert (charge['input_tokens'], charge['output_tokens']) == (100, 40)
    else:
        assert not {'input_tokens', 'output_tokens'} & public.keys()
        assert not {'input_tokens', 'output_tokens'} & charge.keys()
    assert charge['state'] == 'failed' and charge['failed'] is True
    assert len(sent) == budget.sent == 1 and stores[0].rows() == []
    assert 'sk-secret' not in str(error.value) + str(public) + str(row)
    assert '/private/path' not in str(error.value) + str(public) + str(row)


@pytest.mark.parametrize('reason', ['cache-only', 'max-calls', 'quota-exhausted', 'quota-unavailable'])
def test_elephant_pre_dispatch_failure_has_no_usage(monkeypatch, stores, reason):
    from engine.identify import elephant_runtime as er
    monkeypatch.setattr(live, '_live_enabled', reason != 'cache-only')
    monkeypatch.setattr(live, 'load_keys', lambda *a: pytest.fail('credential read'))
    monkeypatch.setattr(er, '_post_once', lambda *a: pytest.fail('network'))

    def quota():
        assert reason not in ('cache-only', 'max-calls'), 'quota refreshed before local gate'
        return {'remaining': None if reason == 'quota-unavailable' else 4}

    monkeypatch.setattr(live, 'elephant_quota', quota)
    budget = live.ElephantBudget(reserve=4, max_calls=0 if reason == 'max-calls' else 12)
    with pytest.raises(live.BudgetExhausted) as error:
        live.elephant_ask({'proposal': 'blocked'}, QUESTIONS, budget=budget)
    assert not hasattr(error.value, 'usage')
    assert budget.sent == 0 and stores[2].rows() == []


@pytest.mark.parametrize('bounded', [False, True], ids=['unbounded', 'bounded'])
def test_elephant_cached_response_needs_no_keys_or_quota(monkeypatch, stores, bounded):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': 12})
    monkeypatch.setattr(er, '_post_once', fake_elephant_post)
    ask = live.elephant_ask if bounded else live.elephant_ask_unbounded
    state = {'proposal': 'cached'}
    result = ask(state, QUESTIONS, budget=live.ElephantBudget(reserve=4, max_calls=1))
    monkeypatch.setattr(live, '_live_enabled', False)
    monkeypatch.setattr(live, 'load_keys', lambda *a: pytest.fail('credential read'))
    monkeypatch.setattr(live, 'elephant_quota', lambda: pytest.fail('quota refreshed'))
    monkeypatch.setattr(er, '_post_once', lambda *a: pytest.fail('network'))
    assert ask(state, QUESTIONS, budget=None) == result
    assert len(stores[2].rows()) == 1


@pytest.mark.parametrize('age', [None, 0, 86_400, 172_800], ids=['undated', 'today', 'yesterday', 'two-days-old'])
@pytest.mark.parametrize('state', ['completed', 'failed', 'reserved'])
def test_elephant_legacy_reservation_requires_a_known_older_utc_day(monkeypatch, stores, age, state):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    stamp = datetime(2026, 10, 24, 0, 0, 1, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(live.time, 'time', lambda: stamp)
    entry = {'usd': 0, 'provider': 'elephant', 'state': state, 'unknown_usage': state != 'completed'}
    if age is not None:
        entry['started_at'] = stamp - age
    stores[2].put('legacy', entry)
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': 5})
    monkeypatch.setattr(er, '_post_once', fake_elephant_post)
    budget = live.ElephantBudget(reserve=4, max_calls=3)
    # Holds survive the following UTC day; only a known older window can be released.
    admitted = int(age == 172_800)
    if admitted:
        live.elephant_ask({'proposal': 'new day'}, QUESTIONS, budget=budget)
    with pytest.raises(live.BudgetExhausted):
        live.elephant_ask({'proposal': 'blocked'}, QUESTIONS, budget=budget)
    assert budget.sent == admitted and len(stores[2].rows()) == 1 + admitted


def test_elephant_reservations_follow_utc_day_and_reset_with_new_allowance(monkeypatch, stores):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    stamp = datetime(2026, 10, 24, 0, 0, 1, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(live.time, 'time', lambda: stamp)
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': 5, 'used': 0, 'limit': 5})
    monkeypatch.setattr(er, '_post_once', fake_elephant_post)
    budget = live.ElephantBudget(reserve=4, max_calls=3)
    live.elephant_ask_unbounded({'proposal': 'today'}, QUESTIONS, budget=budget)
    with pytest.raises(live.BudgetExhausted):
        live.elephant_ask_unbounded({'proposal': 'exhausted'}, QUESTIONS, budget=budget)
    stamp += 86_400
    with pytest.raises(live.BudgetExhausted):
        live.elephant_ask_unbounded({'proposal': 'next-day hold'}, QUESTIONS, budget=budget)
    stamp += 86_400
    live.elephant_ask_unbounded({'proposal': 'tomorrow'}, QUESTIONS, budget=budget)
    assert budget.sent == 2
    assert [r['response']['quota_day'] for r in stores[2].rows()] == ['2026-10-24', '2026-10-26']


@pytest.mark.parametrize('crash', [False, True], ids=['completed', 'crashed'])
@pytest.mark.parametrize('accounted', [False, True], ids=['stale-quota', 'accounted-quota'])
def test_elephant_reserve_is_shared_across_processes_and_survives_crash(tmp_path, crash, accounted):
    source = r'''
import os, socket, sys, time
from pathlib import Path
from engine.identify import elephant_runtime as er
from engine.identify.fakes import fake_elephant_post
from evals_dev.identify_bench import live
from evals_dev.identify_bench.cache import Store
directory, worker = Path(sys.argv[1]), sys.argv[2]
crash, accounted = sys.argv[3] == 'True', sys.argv[4] == 'True'
stores = tuple(Store(name, directory) for name in ('elephant', 'openai', 'spend'))
live._stores = lambda: stores
live.load_keys = lambda *a: None
live.MIN_INTERVAL = 0
os.environ['OPENROUTER_API_KEY'] = 'offline-test'
socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network'))
path = directory / 'dispatched'
def quota():
    used = len(path.read_bytes().split(b'\n')) - 1 if accounted and path.exists() else 0
    return {'remaining': 12 - used, 'used': used, 'limit': 12}
live.elephant_quota = quota
def post(*args):
    active = directory / 'active'
    active.touch(exist_ok=False)
    try:
        with path.open('ab') as f:
            f.write(b'attempt\n')
        time.sleep(0.005)
        if crash:
            raise SystemExit(17)
        return fake_elephant_post(*args)
    finally:
        active.unlink()
er._post_once = post
budget = live.ElephantBudget(reserve=4, max_calls=12)
budget.remaining = 12
with live.live_mode(True):
    for i in range(12):
        try:
            live.elephant_ask({'proposal': f'{worker}-{i}'},
                              {'q': {'type': 'noul', 'instructions': 'Is it applicable?'}}, budget=budget)
        except live.BudgetExhausted:
            break
'''
    processes, outputs = [], []
    for i in range(2):
        process = subprocess.Popen([sys.executable, '-B', '-c', source, str(tmp_path), str(i),
                                    str(crash and i == 0), str(accounted)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        processes.append(process)
        if crash:
            # Recovery starts after the reservation has survived a real process exit.
            outputs.append(process.communicate(timeout=10))
    if not crash:
        outputs = [p.communicate(timeout=10) for p in processes]
    assert all(not stdout and not stderr for stdout, stderr in outputs), outputs
    assert sorted(p.returncode for p in processes) == ([0, 17] if crash else [0, 0])
    dispatched = (tmp_path / 'dispatched').read_bytes().split(b'\n')
    attempts = len(dispatched) - 1
    assert 0 < attempts <= 8 and 12 - attempts >= 4
    assert dispatched == [b'attempt'] * attempts + [b'']
    rows = Store('spend', tmp_path).rows()
    assert len(rows) == attempts
    assert sum(r['response']['state'] == 'reserved' for r in rows) == int(crash)
    assert min(r['response']['quota_remaining_after'] for r in rows) >= 4


def test_cache_roundtrips_unicode_line_separators_and_carriage_returns(tmp_path):
    writer = Store('unicode', tmp_path)
    reader = Store('unicode', tmp_path)
    response = {'text': 'before\u2028between\u2029after\rcarriage\r\nCRLF\nLF'}
    writer.put('first', response)
    assert Store('unicode', tmp_path).get('first') == response
    assert reader.get('first') == response
    writer.put('second', {'text': '\u2029\u2028\r'})
    assert reader.get('second') == {'text': '\u2029\u2028\r'}
    assert len(reader.rows()) == 2


def test_cache_unicode_rows_survive_partial_utf8_tail_and_next_append(tmp_path):
    writer = Store('unicode', tmp_path)
    response = {'text': 'before\u2028between\u2029after\r'}
    writer.put('saved', response)
    with writer.path.open('ab') as f:
        f.write(b'{"key":"interrupted","response":"\xe2\x80')
    reader = Store('unicode', tmp_path)
    assert reader.get('saved') == response
    writer.put('next', {'text': '\r\n\u2028'})
    assert reader.get('next') == {'text': '\r\n\u2028'}
    assert Store('unicode', tmp_path).get('saved') == response
    assert len(reader.rows()) == 2


def test_slow_reservation_save_retains_the_possible_next_day_hold(monkeypatch, tmp_path):
    from engine.identify import elephant_runtime as er
    from engine.identify.fakes import fake_elephant_post
    stores = tuple(Store(name, tmp_path) for name in ('elephant', 'openai', 'spend'))
    monkeypatch.setattr(live, '_stores', lambda: stores)
    monkeypatch.setattr(live, 'MIN_INTERVAL', 0)
    monkeypatch.setattr(live, 'load_keys', lambda *a: None)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'offline-test')
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('network'))
    midnight = datetime(2026, 10, 25, tzinfo=timezone.utc).timestamp()
    initial = midnight - 61
    clock, sent, timeouts = [initial], [], []
    monkeypatch.setattr(live.time, 'time', lambda: clock[0])
    monkeypatch.setattr(live.time, 'monotonic', lambda: 1000 + clock[0] - initial)
    monkeypatch.setattr(live, 'elephant_quota', lambda: {'remaining': 12, 'used': 0, 'limit': 12})
    original = stores[2].put
    saved = [False]
    def save(key, response, **meta):
        original(key, response, **meta)
        if response.get('state') == 'reserved' and not saved[0]:
            saved[0] = True
            clock[0] += 2
    monkeypatch.setattr(stores[2], 'put', save)
    def post(body, headers, timeout):
        timeouts.append(timeout)
        if not sent:
            assert clock[0] == midnight - 59
            clock[0] += 59
        sent.append(clock[0])
        return fake_elephant_post(body, headers, timeout)
    monkeypatch.setattr(er, '_post_once', post)
    budget = live.ElephantBudget(reserve=4, max_calls=12)
    with live.live_mode(True):
        for index in range(12):
            try:
                live.elephant_ask({'proposal': str(index)},
                    {'q': {'type': 'noul', 'instructions': 'Applicable?'}}, budget=budget)
            except live.BudgetExhausted:
                break
    rows = [r['response'] for r in stores[2].rows()]
    assert timeouts[0] == er.MAX_TIMEOUT
    assert set(sent) == {midnight}
    details = {'dispatches': len(sent), 'actual_remaining': 12-len(sent),
        'first_started_at': rows[0]['started_at'],
        'first_hold_days': sorted(live._reservation_days(rows[0])),
        'actual_dispatch_day': live._utc_day(sent[0]),
        'first_timeout': timeouts[0]}
    print(details)
    assert 12-len(sent) >= 4, details
