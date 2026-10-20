"""Spend cap. No network. The OpenAI post is a mock. The ledger is sqlite."""
from __future__ import annotations

import logging
import sqlite3
import threading
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.spend import (
    CAP_NOTICE,
    LEDGER_NOTICE,
    POSTGRES_LOCK_SQL,
    POSTGRES_RESERVE_SQL,
    ROUTE_IDENTIFY_RERANK,
    RequestNotSent,
    RequestSent,
    SpendError,
    UNPRICED_NOTICE,
    _SQLITE_DDL,
    budget_status,
    database_url,
    estimate_input_tokens,
    openai_chat_json,
    sqlite_database_url,
    token_cost,
    total_cap_usd,
)

_MODEL = 'gpt-4.1-mini'


def _url(path: Path) -> str:
    return 'sqlite://' + path.resolve().as_posix()


def _prepare(tmp_path, monkeypatch, *, cap='20', live='1', key='test-openai-key', create=True):
    path = tmp_path / 'spend.sqlite'
    monkeypatch.setenv('DATABASE_URL', _url(path))
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    monkeypatch.delenv('BATATIS_LLM_PROVIDER', raising=False)
    if live is None:
        monkeypatch.delenv('BATATIS_LIVE', raising=False)
    else:
        monkeypatch.setenv('BATATIS_LIVE', live)
    if key is None:
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    else:
        monkeypatch.setenv('OPENAI_API_KEY', key)
    if cap is None:
        monkeypatch.delenv('BATATIS_TOTAL_BUDGET_USD', raising=False)
    else:
        monkeypatch.setenv('BATATIS_TOTAL_BUDGET_USD', cap)
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.000001')
    if create:
        with sqlite3.connect(path) as con:
            con.execute(_SQLITE_DDL)
    return path


def _rows(path: Path):
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            'SELECT id, route, model, est_usd, actual_usd, status FROM spend_ledger ORDER BY id')]


def _messages(text='soffit'):
    return [{'role': 'user', 'content': text}]


def _reply(payload, prompt, completion):
    return {
        'model': payload['model'],
        'usage': {'prompt_tokens': prompt, 'completion_tokens': completion},
        'choices': [{'message': {'content': '{}'}}],
    }


def _install(monkeypatch, seen, *, prompt=None, completion=0, reply=None):
    def post(payload, key):
        assert key == 'test-openai-key'
        assert 'max_completion_tokens' in payload
        assert isinstance(payload['max_completion_tokens'], int)
        seen.append(payload)
        if reply is not None:
            return reply(payload)
        used = estimate_input_tokens(payload['messages']) if prompt is None else prompt
        return _reply(payload, used, completion)

    monkeypatch.setattr('engine.spend._post_chat', post)


def _call(messages=None, *, model=_MODEL, max_completion_tokens=0, route=ROUTE_IDENTIFY_RERANK):
    return openai_chat_json(
        messages if messages is not None else _messages(),
        model=model,
        max_completion_tokens=max_completion_tokens,
        route=route,
    )


def test_under_cap_call_proceeds_and_is_settled(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    seen = []
    messages = _messages('x' * 30)
    reserved_in = estimate_input_tokens(messages)
    reported_in = max(1, reserved_in // 2)
    _install(monkeypatch, seen, prompt=reported_in, completion=0)
    result = openai_chat_json(
        messages, model=_MODEL, max_completion_tokens=0, route=ROUTE_IDENTIFY_RERANK)
    assert result.offline is False and result.notice is None and result.value['choices']
    assert len(seen) == 1
    assert seen[0]['max_completion_tokens'] == 0
    assert seen[0]['model'] == _MODEL
    rows = _rows(path)
    assert len(rows) == 1
    assert rows[0]['route'] == ROUTE_IDENTIFY_RERANK
    assert rows[0]['model'] == _MODEL
    assert rows[0]['status'] == 'settled'
    assert rows[0]['est_usd'] == format(token_cost(_MODEL, reserved_in, 0), 'f')
    assert rows[0]['actual_usd'] == format(token_cost(_MODEL, reported_in, 0), 'f')
    assert Decimal(rows[0]['actual_usd']) <= Decimal(rows[0]['est_usd'])


def test_reaching_the_cap_refuses_the_next_call_offline(tmp_path, monkeypatch):
    messages = _messages()
    estimate = token_cost(_MODEL, estimate_input_tokens(messages), 0)
    path = _prepare(tmp_path, monkeypatch, cap=format(estimate, 'f'))
    seen = []
    _install(monkeypatch, seen, completion=0)
    first = _call(messages)
    second = _call(messages)
    assert first.offline is False
    assert second.offline is True
    assert second.notice == CAP_NOTICE
    assert len(seen) == 1
    assert [row['status'] for row in _rows(path)] == ['settled']


def test_concurrent_reservations_cannot_exceed_the_cap(tmp_path, monkeypatch):
    messages = _messages('x')
    max_out = 250_000
    reserved_in = estimate_input_tokens(messages)
    estimate = token_cost(_MODEL, reserved_in, max_out)
    path = _prepare(tmp_path, monkeypatch, cap=format(estimate * 2, 'f'))
    hold = threading.Event()
    entered = []
    refused = []
    lock = threading.Lock()

    def post(payload, key):
        assert key == 'test-openai-key'
        assert payload['max_completion_tokens'] == max_out
        with lock:
            entered.append(threading.get_ident())
        assert hold.wait(timeout=10)
        return _reply(payload, reserved_in, max_out)

    monkeypatch.setattr('engine.spend._post_chat', post)

    def worker():
        try:
            result = openai_chat_json(
                messages, model=_MODEL, max_completion_tokens=max_out, route=ROUTE_IDENTIFY_RERANK)
        except Exception as exc:
            with lock:
                refused.append(type(exc).__name__)
            return
        if result.offline:
            with lock:
                refused.append(result.notice)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    deadline = threading.Event()
    for _ in range(100):
        with lock:
            if len(entered) + len(refused) == 5:
                break
        if deadline.wait(0.05):
            break
    with lock:
        assert len(entered) == 2, (entered, refused)
        assert refused == [CAP_NOTICE, CAP_NOTICE, CAP_NOTICE]
        assert [row['status'] for row in _rows(path)] == ['reserved', 'reserved']
    status = budget_status()
    assert status.spent_usd == 0
    assert status.remaining_usd == 0
    hold.set()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    rows = _rows(path)
    assert all(row['status'] == 'settled' for row in rows)
    settled = sum(Decimal(row['actual_usd']) for row in rows)
    assert settled <= Decimal(format(estimate * 2, 'f'))


def test_oversized_prompt_is_refused_before_any_http_call(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch, cap='0.000001')
    seen = []
    _install(monkeypatch, seen)
    result = openai_chat_json(
        _messages('x' * 50_000), model=_MODEL, max_completion_tokens=8_000)
    assert result.offline is True
    assert result.notice == CAP_NOTICE
    assert seen == []
    assert _rows(path) == []


def test_error_releases_the_reservation(tmp_path, monkeypatch):
    messages = _messages()
    estimate = token_cost(_MODEL, estimate_input_tokens(messages), 0)
    path = _prepare(tmp_path, monkeypatch, cap=format(estimate, 'f'))

    def boom(payload, key):
        raise RequestNotSent('openai connect failed')

    monkeypatch.setattr('engine.spend._post_chat', boom)
    with pytest.raises(RequestNotSent, match='connect failed'):
        _call(messages)
    rows = _rows(path)
    assert len(rows) == 1 and rows[0]['status'] == 'released'
    assert budget_status().remaining_usd == float(estimate.quantize(Decimal('0.01')))

    seen = []
    _install(monkeypatch, seen, completion=0)
    result = _call(messages)
    assert result.offline is False and len(seen) == 1
    assert [row['status'] for row in _rows(path)] == ['released', 'settled']


def test_returned_model_must_match_and_be_priced(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)

    def post(payload, key):
        body = _reply(payload, 1, 1)
        body['model'] = 'gpt-4.1'
        return body

    monkeypatch.setattr('engine.spend._post_chat', post)
    with pytest.raises(RequestSent, match='model mismatch'):
        _call()
    rows = _rows(path)
    assert len(rows) == 1 and rows[0]['status'] == 'settled'
    assert rows[0]['actual_usd'] == rows[0]['est_usd']


def test_no_database_in_live_mode_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.delenv('BATATIS_LLM_PROVIDER', raising=False)
    seen = []
    _install(monkeypatch, seen)
    result = _call()
    assert result.offline is True
    assert result.notice == LEDGER_NOTICE
    assert seen == []

    missing = tmp_path / 'missing-parent' / 'spend.sqlite'
    monkeypatch.setenv('DATABASE_URL', _url(missing))
    result = _call()
    assert result.offline is True and result.notice == LEDGER_NOTICE
    assert seen == []
    assert not missing.exists()

    codedb = tmp_path / 'codedb.sqlite'
    codedb.write_text('readonly-bundle')
    monkeypatch.setenv('DATABASE_URL', _url(codedb))
    result = _call()
    assert result.notice == LEDGER_NOTICE
    assert codedb.read_text() == 'readonly-bundle'
    assert seen == []


def test_default_cap_is_20(tmp_path, monkeypatch):
    monkeypatch.delenv('BATATIS_TOTAL_BUDGET_USD', raising=False)
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.000001')
    assert total_cap_usd() == Decimal('20')
    path = _prepare(tmp_path, monkeypatch, cap=None)
    seen = []
    _install(monkeypatch, seen, prompt=35_000, completion=0)
    wide = _messages('x' * 200_000)
    assert estimate_input_tokens(wide) >= 35_000
    result = openai_chat_json(wide, model=_MODEL, max_completion_tokens=0)
    assert result.offline is False and len(seen) == 1
    status = budget_status()
    assert status.cap_usd == 20
    assert status.live is True
    assert status.spent_usd == 0.01
    assert status.remaining_usd == 19.99
    assert path.exists()


def test_live_unset_does_not_write_ledger_or_call_model(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch, live=None, create=False)
    seen = []
    _install(monkeypatch, seen)
    result = _call()
    assert result.offline is True and result.notice is None and result.value is None
    assert seen == []
    assert not path.exists()

    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', '')
    result = _call()
    assert result.offline is True and result.notice is None
    assert seen == []
    assert not path.exists()


def test_unknown_model_is_refused(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    seen = []
    _install(monkeypatch, seen)
    result = openai_chat_json(_messages(), model='gpt-unpriced', max_completion_tokens=10)
    assert result.offline is True
    assert result.notice == UNPRICED_NOTICE
    assert seen == []
    assert _rows(path) == []


def test_api_key_is_not_logged(tmp_path, monkeypatch, caplog):
    _prepare(tmp_path, monkeypatch, key='sk-test-secret-value')

    def boom(payload, key):
        raise SpendError('openai http 500')

    monkeypatch.setattr('engine.spend._post_chat', boom)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SpendError):
            _call()
    assert 'sk-test-secret-value' not in caplog.text
    source = Path(__file__).resolve().parents[1].joinpath('spend.py').read_text()
    assert 'log.' in source
    for line in source.splitlines():
        if 'log.' in line:
            assert 'api_key' not in line
            assert 'OPENAI_API_KEY' not in line


def test_response_format_is_sent(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch)
    seen = []
    _install(monkeypatch, seen, completion=1)
    fmt = {'type': 'json_object'}
    result = openai_chat_json(
        _messages(), model=_MODEL, max_completion_tokens=16, response_format=fmt)
    assert result.offline is False
    assert seen[0]['response_format'] == fmt
    assert seen[0]['max_completion_tokens'] == 16


def test_status_budget_route_hides_the_key_and_stays_200(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.delenv('BATATIS_TOTAL_BUDGET_USD', raising=False)
    monkeypatch.delenv('BATATIS_LLM_PROVIDER', raising=False)
    client = TestClient(create_app())
    response = client.get('/status/budget')
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {'live', 'cap_usd', 'spent_usd', 'remaining_usd'}
    assert body['live'] is True
    assert body['cap_usd'] == 20
    assert body['spent_usd'] is None and body['remaining_usd'] is None
    assert 'test-openai-key' not in response.text

    path = _prepare(tmp_path, monkeypatch)
    seen = []
    _install(monkeypatch, seen, prompt=35_000, completion=0)
    wide = _messages('x' * 200_000)
    assert estimate_input_tokens(wide) >= 35_000
    openai_chat_json(wide, model=_MODEL, max_completion_tokens=0)
    response = client.get('/status/budget')
    assert response.status_code == 200
    body = response.json()
    assert body['spent_usd'] == 0.01
    assert body['remaining_usd'] == 19.99
    assert 'test-openai-key' not in response.text

    blocked = tmp_path / 'not-a-file'
    blocked.mkdir()
    monkeypatch.setenv('DATABASE_URL', _url(blocked))
    response = client.get('/status/budget')
    assert response.status_code == 200
    assert response.json()['spent_usd'] is None


def test_database_url_matches_deploy_convention(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgres://db.example/batatis')
    monkeypatch.setenv('POSTGRES_URL', 'postgres://other.example/ignored')
    assert database_url() == 'postgresql://db.example/batatis?sslmode=require'

    monkeypatch.setenv('DATABASE_URL', 'postgresql://db.example/batatis?sslmode=disable')
    assert database_url() == 'postgresql://db.example/batatis?sslmode=disable'

    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('POSTGRES_URL', 'postgres://db.example/from-postgres')
    assert database_url() == 'postgresql://db.example/from-postgres?sslmode=require'

    monkeypatch.delenv('POSTGRES_URL', raising=False)
    assert database_url() is None


def test_postgres_reservation_locks_before_the_cap_check():
    """The lock is a prior statement. Joining it to the sum is not ordered."""
    import inspect

    from engine.spend import _PostgresLedger

    assert 'pg_advisory_xact_lock' in POSTGRES_LOCK_SQL
    assert 'pg_advisory_xact_lock' not in POSTGRES_RESERVE_SQL
    assert '<=' in POSTGRES_RESERVE_SQL
    assert 'spend_ledger' in POSTGRES_RESERVE_SQL
    src = inspect.getsource(_PostgresLedger.reserve)
    assert src.index('POSTGRES_LOCK_SQL') < src.index('POSTGRES_RESERVE_SQL')


def test_sqlite_url_helper_round_trip(tmp_path):
    path = tmp_path / 'ledger.sqlite'
    assert sqlite_database_url(path).startswith('sqlite:///')
    from engine.spend import _sqlite_path
    assert _sqlite_path(sqlite_database_url(path)) == path.resolve()


def test_sent_request_error_keeps_the_full_reservation(tmp_path, monkeypatch):
    messages = _messages()
    estimate = token_cost(_MODEL, estimate_input_tokens(messages), 8)
    path = _prepare(tmp_path, monkeypatch, cap=format(estimate, 'f'))

    def boom(payload, key):
        raise RequestSent('openai http 500')

    monkeypatch.setattr('engine.spend._post_chat', boom)
    with pytest.raises(RequestSent, match='http 500'):
        openai_chat_json(messages, model=_MODEL, max_completion_tokens=8)
    rows = _rows(path)
    assert rows[0]['status'] == 'settled'
    assert rows[0]['actual_usd'] == rows[0]['est_usd']
    assert Decimal(rows[0]['actual_usd']) == estimate
    seen = []
    _install(monkeypatch, seen, completion=0)
    second = openai_chat_json(messages, model=_MODEL, max_completion_tokens=8)
    assert second.offline is True and second.notice == CAP_NOTICE
    assert seen == []


def test_reported_usage_cannot_settle_above_the_reservation(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch, cap='20')
    messages = _messages('short')

    def post(payload, key):
        return _reply(payload, 50_000_000, 50_000_000)

    monkeypatch.setattr('engine.spend._post_chat', post)
    result = openai_chat_json(messages, model=_MODEL, max_completion_tokens=4)
    assert result.offline is False
    row = _rows(path)[0]
    assert row['status'] == 'settled'
    assert Decimal(row['actual_usd']) == Decimal(row['est_usd'])
    reserved = token_cost(_MODEL, estimate_input_tokens(messages), 4)
    assert Decimal(row['actual_usd']) == reserved


def test_postgres_unreachable_fails_closed(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://batatis@127.0.0.1:1/spend?sslmode=disable')
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.delenv('BATATIS_LLM_PROVIDER', raising=False)
    seen = []
    _install(monkeypatch, seen)
    result = openai_chat_json(_messages(), model=_MODEL, max_completion_tokens=8)
    assert result.offline is True
    assert result.notice == LEDGER_NOTICE
    assert seen == []


def test_character_estimate_is_ceil_of_chars_over_three(monkeypatch):
    """The fallback is documented as conservative: ceil(chars / 3), at least 1."""
    import builtins
    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == 'tiktoken':
            raise ImportError('tiktoken blocked')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', blocked)
    messages = _messages('abcdef')  # json is longer than the six letters
    blob_len = len(__import__('json').dumps(messages, ensure_ascii=False, separators=(',', ':')))
    assert estimate_input_tokens(messages) == max(1, (blob_len + 2) // 3)
