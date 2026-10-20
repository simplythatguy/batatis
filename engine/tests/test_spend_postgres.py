"""Opt-in Postgres tests. Every test gets a disposable schema, never a shared table.

Only BATATIS_TEST_POSTGRES_URL enables these tests. CI supplies an isolated
postgres:16 service. DATABASE_URL alone never authorizes test DDL or deletion.
Provider requests are faked; no OpenAI key or network to a provider is used.
"""
from __future__ import annotations

import os
import threading
import uuid
from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest

from engine import spend
from engine.tests.test_spend import _messages, _reply

MODEL = 'gpt-4.1-mini'


@pytest.fixture
def postgres_ledger(monkeypatch):
    url = os.environ.get('BATATIS_TEST_POSTGRES_URL')
    if not url:
        pytest.skip('isolated BATATIS_TEST_POSTGRES_URL not provided')
    psycopg = pytest.importorskip('psycopg')
    from psycopg import sql
    schema = 'spend_test_' + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as con:
        con.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query['options'] = '-csearch_path=' + schema
    isolated_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))
    monkeypatch.setenv('DATABASE_URL', isolated_url)
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.setenv('BATATIS_TOTAL_BUDGET_USD', '20')
    monkeypatch.delenv('BATATIS_LLM_PROVIDER', raising=False)
    try:
        yield spend.open_ledger()
    finally:
        with psycopg.connect(url, autocommit=True) as con:
            con.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def _call():
    return spend.openai_chat_json(_messages(), model=MODEL, max_completion_tokens=8)


def test_postgres_concurrent_reservations_cannot_exceed_the_cap(postgres_ledger, monkeypatch):
    """Five real connections, concurrent first-use DDL, and a non-default isolation level."""
    import psycopg
    original = spend._PostgresLedger._connect

    def repeatable_read(self):
        con = original(self)
        con.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        return con

    monkeypatch.setattr(spend._PostgresLedger, '_connect', repeatable_read)
    max_out = 2_500
    messages = _messages()
    reserved_in = spend.estimate_input_tokens(messages, max_completion_tokens=max_out)
    estimate = spend.token_cost(MODEL, reserved_in, max_out)
    monkeypatch.setenv('BATATIS_TOTAL_BUDGET_USD', str(estimate * 2))
    hold = threading.Event()
    ready = threading.Event()
    entered, refused = [], []
    lock = threading.Lock()

    def post(payload, key):
        assert key == 'test-openai-key' and payload['max_completion_tokens'] == max_out
        with lock:
            entered.append(threading.get_ident())
            if len(entered) + len(refused) == 5:
                ready.set()
        assert hold.wait(timeout=15)
        return _reply(payload, reserved_in, max_out)

    monkeypatch.setattr(spend, '_post_chat', post)

    def worker():
        try:
            result = spend.openai_chat_json(messages, model=MODEL, max_completion_tokens=max_out)
            if result.offline:
                with lock:
                    refused.append(result.notice)
                    if len(entered) + len(refused) == 5:
                        ready.set()
        except Exception as exc:
            with lock:
                refused.append(type(exc).__name__)
                ready.set()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    try:
        assert ready.wait(timeout=15), (entered, refused)
        assert len(entered) == 2 and refused == [spend.CAP_NOTICE] * 3, (entered, refused)
        assert postgres_ledger.totals() == (Decimal('0'), estimate * 2)
        assert spend.budget_status().remaining_usd == 0
    finally:
        hold.set()
        for thread in threads:
            thread.join(timeout=15)
            assert not thread.is_alive()
    assert postgres_ledger.totals() == (estimate * 2, Decimal('0'))


@pytest.mark.parametrize('failure', ['timeout', 'settlement'])
def test_postgres_unknown_outcomes_keep_the_budget(postgres_ledger, monkeypatch, failure):
    estimate = spend.token_cost(MODEL, spend.estimate_input_tokens(_messages()), 8)
    monkeypatch.setenv('BATATIS_TOTAL_BUDGET_USD', str(estimate))
    seen = []

    def post(payload, key):
        seen.append(payload)
        if failure == 'timeout':
            raise spend.SpendError('synthetic lost response')
        return _reply(payload, 1, 1)

    monkeypatch.setattr(spend, '_post_chat', post)
    if failure == 'settlement':
        def unavailable(*args):
            raise spend.LedgerUnavailable
        monkeypatch.setattr(spend._PostgresLedger, 'settle', unavailable)
        assert not _call().offline
    else:
        with pytest.raises(spend.SpendError):
            _call()
    assert _call().notice == spend.CAP_NOTICE
    assert len(seen) == 1
    assert postgres_ledger.totals() == (Decimal('0'), estimate)


def test_postgres_lost_reservation_commit_never_sends(postgres_ledger, monkeypatch):
    """The DB committed, but the caller lost the acknowledgement before dispatch."""
    import psycopg
    postgres_ledger._ensure_table()
    monkeypatch.setattr(spend._PostgresLedger, '_ensure_table', lambda self: None)
    estimate = spend.token_cost(MODEL, spend.estimate_input_tokens(_messages()), 8)
    monkeypatch.setenv('BATATIS_TOTAL_BUDGET_USD', str(estimate))
    original = spend._PostgresLedger._connect

    class CommitLost:
        def __init__(self, con):
            self.con = con
        def __getattr__(self, name):
            return getattr(self.con, name)
        def commit(self):
            self.con.commit()
            raise psycopg.OperationalError('synthetic commit acknowledgement lost')

    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload))
    with monkeypatch.context() as patch:
        patch.setattr(spend._PostgresLedger, '_connect', lambda self: CommitLost(original(self)))
        assert _call().notice == spend.LEDGER_NOTICE
    assert not seen
    assert postgres_ledger.totals() == (Decimal('0'), estimate)
    assert _call().notice == spend.CAP_NOTICE


def test_postgres_corrupt_ledger_refuses_before_send(postgres_ledger, monkeypatch):
    postgres_ledger._ensure_table()
    with postgres_ledger._connect() as con:
        con.execute("INSERT INTO spend_ledger (ts,route,model,est_usd,status) VALUES ('now','x',%s,'garbage','reserved')", (MODEL,))
    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload))
    assert _call().notice == spend.LEDGER_NOTICE
    assert not seen


def test_postgres_unreachable_refuses_without_any_provider_attempt(monkeypatch):
    """An injected connection failure needs no database and cannot touch user data."""
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture.invalid/test')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.setenv('BATATIS_TOTAL_BUDGET_USD', '20')
    monkeypatch.delenv('BATATIS_LLM_PROVIDER', raising=False)
    seen = []
    def unavailable(self):
        raise spend.LedgerUnavailable
    monkeypatch.setattr(spend._PostgresLedger, '_connect', unavailable)
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload))
    assert _call().notice == spend.LEDGER_NOTICE
    assert not seen
    assert spend.budget_status().remaining_usd is None
