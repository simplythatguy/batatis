"""Synthetic money-gate tests; no provider calls."""
from engine import llm_gate
from decimal import Decimal


def test_voice_requires_its_own_credential_and_unknown_providers_fail_closed(monkeypatch):
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-openai')
    monkeypatch.delenv('XAI_API_KEY', raising=False)
    assert not llm_gate.live_enabled('xai')
    assert not llm_gate.live_enabled('unknown')
    monkeypatch.setenv('XAI_API_KEY', 'synthetic-xai')
    assert llm_gate.live_enabled('xai')


def test_voice_reserves_money_from_the_existing_shared_cap(monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('BATATIS_STORE', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('XAI_API_KEY', 'synthetic-xai')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.16')
    llm_gate.reset_for_tests()
    try:
        first = llm_gate.authorize_voice(client_ip='synthetic', max_seconds=60, max_text_inputs=20)
        assert first.allowed and first.reserved_usd == Decimal('0.160000')
        assert llm_gate.authorize_voice(client_ip='other', max_seconds=60, max_text_inputs=20).source == 'offline-cap'
    finally:
        llm_gate.reset_for_tests()


def test_voice_cannot_use_the_token_authorization_gate(monkeypatch):
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('XAI_API_KEY', 'synthetic-xai')
    assert not llm_gate.authorize(provider='xai', model='grok-voice-3.0',
                                  max_input_tokens=0, max_output_tokens=0).allowed
