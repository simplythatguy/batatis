"""Opt-in integration against an owned PostgreSQL cluster; never an ambient application DB."""
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from engine import llm_gate
from engine.account_models import User
from engine.models import Case
from engine.store_postgres import PostgresCaseStore, PostgresSpend
from engine.tests.test_voice_context import case_scope, pdf_bytes, synthetic_codes
from engine.voice_context import prepare_context


@pytest.fixture
def owned_pg(monkeypatch):
    url = os.environ.get('BATATIS_VOICE_TEST_DATABASE_URL', '')
    if not url or 'batatis-voice-pg-' not in url:
        pytest.skip('Set BATATIS_VOICE_TEST_DATABASE_URL to an owned batatis-voice-pg-* test cluster')
    with psycopg.connect(url, autocommit=True) as con:
        assert con.execute('SHOW server_encoding').fetchone()[0] == 'UTF8'
        con.execute('DROP SCHEMA IF EXISTS voice_contract CASCADE')
        con.execute('CREATE SCHEMA voice_contract')
    scoped = make_conninfo(url, options='-c search_path=voice_contract')
    monkeypatch.setenv('DATABASE_URL', scoped)
    monkeypatch.setenv('BATATIS_STORE', 'postgres')
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('XAI_API_KEY', 'synthetic-xai')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-openai')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.16')
    monkeypatch.setenv('BATATIS_ASSIST_RATE_LIMIT', '12')
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '20')
    llm_gate.reset_for_tests()
    yield scoped
    llm_gate.reset_for_tests()
    with psycopg.connect(url, autocommit=True) as con:
        con.execute('DROP SCHEMA voice_contract CASCADE')


def test_voice_reservations_use_the_shared_atomic_postgres_cap(owned_pg):
    def start(index):
        return llm_gate.authorize_voice(client_ip=f'synthetic-{index}', max_seconds=60, max_text_inputs=20)
    with ThreadPoolExecutor(max_workers=6) as pool:
        decisions = list(pool.map(start, range(6)))
    assert sum(item.allowed for item in decisions) == 1
    assert sum(item.reserved_usd for item in decisions) == Decimal('0.160000')
    assert {item.source for item in decisions} == {'live', 'offline-cap'}
    assert llm_gate.authorize_assist(provider='openai', model='gpt-4.1-mini',
        max_input_tokens=100, max_output_tokens=100, client_ip='text-assistant').source == 'offline-cap'


def test_independent_ledger_connections_cannot_double_book_the_same_remaining_cap(owned_pg):
    ledgers = [PostgresSpend(owned_pg), PostgresSpend(owned_pg)]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda ledger: ledger.try_reserve_spend(Decimal('0.16'), Decimal('0.16')), ledgers))
        assert sorted(outcomes) == [False, True]
    finally:
        for ledger in ledgers:
            ledger.close()


def test_real_postgres_case_uploads_keep_authorized_voice_source_identity(owned_pg, tmp_path):
    store = PostgresCaseStore(owned_pg)
    codes = synthetic_codes(tmp_path / 'source.sqlite')
    user = User(email='synthetic@example.test', name='Synthetic Owner', role='applicant')
    case = store.put(Case(owner_id=user.id))
    saved = store.put_file(case.id, 'source.pdf', pdf_bytes('Synthetic PostgreSQL attachment excerpt'))
    prepared = prepare_context(case_scope(case, attachment_ids=[saved['id']]),
                               store=store, code=lambda: codes, user=user)
    assert prepared.data['attachments'][0]['content_state'] == 'text_excerpt'
    assert prepared.data['attachments'][0]['case_id'] == case.id
    assert prepared.data['attachments'][0]['file_id'] == saved['id']
    assert 'Synthetic PostgreSQL attachment excerpt' in prepared.data['attachments'][0]['content'][0]['text']
