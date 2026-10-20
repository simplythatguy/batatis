"""Spend cap. No network. The OpenAI client is a mock. The ledger is sqlite."""
from __future__ import annotations

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
    UNPRICED_NOTICE,
    _SQLITE_DDL,
    budget_status,
    database_url,
    keyed_openai_call,
    sqlite_database_url,
    total_cap_usd,
)

# 35,000 input tokens on gpt-4.1-mini is exactly $0.014.
_MODEL = 'gpt-4.1-mini'
_IN = 35000
_OUT = 0


def _url(path: Path) -> str:
    return 'sqlite://' + path.resolve().as_posix()


def _prepare(tmp_path, monkeypatch, *, cap='20', live='1', key='test-openai-key', create=True):
    path = tmp_path / 'spend.sqlite'
    monkeypatch.setenv('DATABASE_URL', _url(path))
    monkeypatch.delenv('POSTGRES_URL', raising=False)
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


def _usage(prompt=_IN, completion=_OUT):
    return {'usage': {'prompt_tokens': prompt, 'completion_tokens': completion}, 'choices': [{'message': {}}]}


def _call(path, client, route=ROUTE_IDENTIFY_RERANK):
    return keyed_openai_call(
        route=route, model=_MODEL, max_input_tokens=_IN, max_output_tokens=_OUT, client=client)


def test_under_cap_call_proceeds_and_is_settled(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    seen = []

    def client():
        seen.append('called')
        return _usage()

    # Worst case is 70,000 input tokens ($0.028). The mock reports 35,000 ($0.014).
    result = keyed_openai_call(
        route=ROUTE_IDENTIFY_RERANK, model=_MODEL,
        max_input_tokens=70_000, max_output_tokens=0, client=client)
    assert result.offline is False and result.notice is None and result.value['choices']
    assert seen == ['called']
    rows = _rows(path)
    assert len(rows) == 1
    assert rows[0]['route'] == ROUTE_IDENTIFY_RERANK
    assert rows[0]['model'] == _MODEL
    assert rows[0]['status'] == 'settled'
    assert rows[0]['est_usd'] == '0.028000'
    assert rows[0]['actual_usd'] == '0.014000'
    status = budget_status()
    assert status.spent_usd == 0.01
    assert status.remaining_usd == 19.99


def test_reaching_the_cap_refuses_the_next_call_offline(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch, cap='0.014')
    seen = []

    def client():
        seen.append('called')
        return _usage()

    first = _call(path, client)
    second = _call(path, client)
    assert first.offline is False
    assert second.offline is True
    assert second.notice == CAP_NOTICE
    assert seen == ['called']
    assert [row['status'] for row in _rows(path)] == ['settled']


def test_concurrent_reservations_cannot_exceed_the_cap(tmp_path, monkeypatch):
    # $0.40 each (1,000,000 input tokens on gpt-4.1-mini). Cap $1.00 fits two, not three.
    path = _prepare(tmp_path, monkeypatch, cap='1')
    hold = threading.Event()
    entered = []
    refused = []
    lock = threading.Lock()

    def client():
        with lock:
            entered.append(threading.get_ident())
        assert hold.wait(timeout=10)
        return {'usage': {'prompt_tokens': 0, 'completion_tokens': 0}}

    def worker():
        result = keyed_openai_call(
            route=ROUTE_IDENTIFY_RERANK, model=_MODEL,
            max_input_tokens=1_000_000, max_output_tokens=0, client=client)
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
    assert status.remaining_usd == 0.2
    hold.set()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert all(row['status'] == 'settled' for row in _rows(path))


def test_error_releases_the_reservation(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch, cap='0.014')

    def boom():
        raise RuntimeError('provider failed')

    with pytest.raises(RuntimeError, match='provider failed'):
        _call(path, boom)
    rows = _rows(path)
    assert len(rows) == 1 and rows[0]['status'] == 'released'
    assert budget_status().remaining_usd == 0.01

    seen = []

    def client():
        seen.append('called')
        return _usage()

    result = _call(path, client)
    assert result.offline is False and seen == ['called']
    assert [row['status'] for row in _rows(path)] == ['released', 'settled']


def test_no_database_in_live_mode_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    seen = []
    result = _call(tmp_path, lambda: seen.append('called'))
    assert result.offline is True
    assert result.notice == LEDGER_NOTICE
    assert seen == []

    missing = tmp_path / 'missing-parent' / 'spend.sqlite'
    monkeypatch.setenv('DATABASE_URL', _url(missing))
    result = _call(tmp_path, lambda: seen.append('called'))
    assert result.offline is True and result.notice == LEDGER_NOTICE
    assert seen == []
    assert not missing.exists()

    codedb = tmp_path / 'codedb.sqlite'
    codedb.write_text('readonly-bundle')
    monkeypatch.setenv('DATABASE_URL', _url(codedb))
    result = _call(tmp_path, lambda: seen.append('called'))
    assert result.notice == LEDGER_NOTICE
    assert codedb.read_text() == 'readonly-bundle'
    assert seen == []


def test_default_cap_is_20(tmp_path, monkeypatch):
    monkeypatch.delenv('BATATIS_TOTAL_BUDGET_USD', raising=False)
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.000001')
    assert total_cap_usd() == Decimal('20')
    path = _prepare(tmp_path, monkeypatch, cap=None)
    seen = []
    result = _call(path, lambda: seen.append('called') or _usage())
    assert result.offline is False and seen == ['called']
    status = budget_status()
    assert status.cap_usd == 20
    assert status.live is True


def test_live_unset_does_not_write_ledger_or_call_model(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch, live=None, create=False)
    seen = []
    result = _call(path, lambda: seen.append('called'))
    assert result.offline is True and result.notice is None and result.value is None
    assert seen == []
    assert not path.exists()

    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', '')
    result = _call(path, lambda: seen.append('called'))
    assert result.offline is True and result.notice is None
    assert seen == []
    assert not path.exists()


def test_unknown_model_is_refused(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    seen = []
    result = keyed_openai_call(
        route=ROUTE_IDENTIFY_RERANK, model='gpt-unpriced',
        max_input_tokens=10, max_output_tokens=10,
        client=lambda: seen.append('called'))
    assert result.offline is True
    assert result.notice == UNPRICED_NOTICE
    assert seen == []
    assert _rows(path) == []


def test_status_budget_route_hides_the_key_and_stays_200(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.delenv('BATATIS_TOTAL_BUDGET_USD', raising=False)
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
    _call(path, lambda: _usage())
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
    # The helper is what tests and local doubles should build. Importing it keeps the
    # three-slash form that _sqlite_path accepts.
    from engine.spend import _sqlite_path
    assert _sqlite_path(sqlite_database_url(path)) == path.resolve()
