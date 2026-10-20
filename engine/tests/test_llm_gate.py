import pytest

from engine.llm_gate import authorize, estimate_usd, record, reset_for_tests
from engine import llm_gate


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv('BATATIS_STORE', raising=False)
    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    reset_for_tests()
    yield
    reset_for_tests()


def test_offline_unless_live_and_key(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-secret')
    decision = authorize(max_input_tokens=100, max_output_tokens=100, client_ip='203.0.113.5')
    assert decision.allowed is False and decision.source == 'offline'
    assert 'sk-test-secret' not in repr(decision)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.delenv('OPENAI_API_KEY')
    assert authorize(max_input_tokens=100, max_output_tokens=100).source == 'offline'


def test_spend_cap_returns_offline_cap_and_record_uses_actual(monkeypatch):
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-secret')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.0000001')
    blocked = authorize(model='gpt-4.1-mini', max_input_tokens=1000, max_output_tokens=1000, client_ip='203.0.113.8')
    assert blocked.source == 'offline-cap' and blocked.allowed is False

    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '5')
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '10')
    reset_for_tests()
    allowed = authorize(model='gpt-4.1-mini', max_input_tokens=1000, max_output_tokens=1000, client_ip='203.0.113.9')
    assert allowed.allowed and allowed.source == 'live'
    record(model='gpt-4.1-mini', input_tokens=10, output_tokens=4, reserved_usd=allowed.reserved_usd)
    assert llm_gate._memory.today() == estimate_usd('gpt-4.1-mini', 10, 4)
    assert 'sk-test-secret' not in repr(allowed)


def test_per_ip_rate_limit(monkeypatch):
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-secret')
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '2')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '5')
    assert authorize(max_input_tokens=1, max_output_tokens=1, client_ip='203.0.113.1').allowed
    assert authorize(max_input_tokens=1, max_output_tokens=1, client_ip='203.0.113.1').allowed
    assert authorize(max_input_tokens=1, max_output_tokens=1, client_ip='203.0.113.1').source == 'rate-limited'
    assert authorize(max_input_tokens=1, max_output_tokens=1, client_ip='203.0.113.2').allowed


def test_postgres_spend_connection_is_created_once(monkeypatch):
    monkeypatch.setenv('BATATIS_STORE', 'postgres')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-secret')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '5')
    created = []

    class Ledger:
        def __init__(self):
            created.append(self)

        def try_reserve_spend(self, usd, cap):
            return True

        def adjust_spend(self, delta):
            return None

        def close(self):
            return None

    monkeypatch.setattr('engine.store_postgres.PostgresSpend', Ledger)
    reset_for_tests()
    assert authorize(max_input_tokens=10, max_output_tokens=10).allowed
    record(model='gpt-4.1-mini', input_tokens=1, output_tokens=1, reserved_usd=0)
    assert authorize(max_input_tokens=10, max_output_tokens=10).allowed
    assert len(created) == 1
