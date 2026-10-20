"""Spend reservations on Postgres. Skips unless DATABASE_URL is postgresql://.

The CI job `engine postgres` runs this against a postgres:16 service. The URL
in that job has no password (`sslmode=disable` on the loopback service).
"""
from __future__ import annotations

import os
import threading
from decimal import Decimal

import pytest

from engine.spend import (
    CAP_NOTICE,
    ROUTE_IDENTIFY_RERANK,
    budget_status,
    database_url,
    estimate_input_tokens,
    openai_chat_json,
    token_cost,
)

_MODEL = 'gpt-4.1-mini'


def _postgres_url() -> str | None:
    url = database_url()
    if url and url.startswith('postgresql://'):
        return url
    return None


def test_postgres_concurrent_reservations_cannot_exceed_the_cap(monkeypatch):
    url = _postgres_url()
    if url is None:
        pytest.skip('postgres service not configured')
    import psycopg

    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.delenv('BATATIS_LLM_PROVIDER', raising=False)
    messages = [{'role': 'user', 'content': 'x'}]
    max_out = 250_000
    reserved_in = estimate_input_tokens(messages)
    estimate = token_cost(_MODEL, reserved_in, max_out)
    monkeypatch.setenv('BATATIS_TOTAL_BUDGET_USD', format(estimate * 2, 'f'))

    with psycopg.connect(url, autocommit=True) as con:
        con.execute('DROP TABLE IF EXISTS spend_ledger')

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
        return {
            'model': payload['model'],
            'usage': {'prompt_tokens': reserved_in, 'completion_tokens': max_out},
            'choices': [{'message': {'content': '{}'}}],
        }

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
    for _ in range(100):
        with lock:
            if len(entered) + len(refused) == 5:
                break
        if threading.Event().wait(0.05):
            break
    with lock:
        assert len(entered) == 2, (len(entered), refused)
        assert refused == [CAP_NOTICE, CAP_NOTICE, CAP_NOTICE]
    status = budget_status()
    assert status.spent_usd == 0
    assert status.remaining_usd == 0
    hold.set()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    with psycopg.connect(url) as con:
        rows = con.execute(
            "SELECT status, actual_usd FROM spend_ledger ORDER BY id"
        ).fetchall()
    assert [row[0] for row in rows] == ['settled', 'settled']
    settled = sum(Decimal(row[1]) for row in rows)
    assert settled <= estimate * 2
