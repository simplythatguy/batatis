"""The keyed benchmark refuses to run without OPENAI_API_KEY and does not print a key."""
import importlib
import os
import subprocess
import sys

from engine.identify.benchmark import model_id_fields, price_floor_line
from engine.identify.config import estimate_usd


def test_price_floor_line_uses_the_given_rate():
    line = price_floor_line('c_openai_rerank_verify', 1.25, 1.4097, '2026-10-19')
    assert 'fx_usd_cad=1.4097' in line and 'fx_date=2026-10-19' in line
    assert 'floor_cad=125.00' in line and 'below_floor=yes' in line
    assert 'cad_per_case=1.2500' in line


def test_usage_keeps_the_requested_id_and_the_api_id():
    from engine.identify.llm import _add, _empty_usage
    usage = _empty_usage()
    _add(usage, {'input_tokens': 3, 'output_tokens': 1, 'returned_model': 'gpt-4.1-2025-04-14'}, 'gpt-4.1-2025-04-14')
    slot = usage['by_model']['gpt-4.1-2025-04-14']
    assert slot['input_tokens'] == 3 and slot['returned'] == ['gpt-4.1-2025-04-14']


def test_model_line_records_requested_and_returned_ids():
    pins = {'rerank': 'gpt-4.1-mini-2025-04-14', 'verifier': 'gpt-4.1-2025-04-14'}
    per_case = [{'reps': [{'by_model': {
        'gpt-4.1-mini-2025-04-14': {'returned': ['gpt-4.1-mini-2025-04-14']},
        'gpt-4.1-2025-04-14': {'returned': ['gpt-4.1-2025-04-14']},
    }}]}]
    line = model_id_fields(pins, per_case)
    assert 'rerank_model=gpt-4.1-mini-2025-04-14' in line
    assert 'rerank_returned=gpt-4.1-mini-2025-04-14' in line
    assert 'verifier_model=gpt-4.1-2025-04-14' in line
    assert 'verifier_returned=gpt-4.1-2025-04-14' in line
    assert 'rerank_returned=none' in model_id_fields({'rerank': None, 'verifier': None}, [])


def test_snapshot_defaults_stay_overridable(monkeypatch):
    import engine.identify.config as config
    for name in ('BATATIS_SCREEN_MODEL', 'BATATIS_RERANK_MODEL', 'BATATIS_VERIFY_MODEL'):
        monkeypatch.delenv(name, raising=False)
    fresh = importlib.reload(config)
    assert fresh.SCREEN_MODEL == 'gpt-4.1-mini-2025-04-14'
    assert fresh.RERANK_MODEL == 'gpt-4.1-mini-2025-04-14'
    assert fresh.VERIFY_MODEL_OPENAI == 'gpt-4.1-2025-04-14'
    monkeypatch.setenv('BATATIS_VERIFY_MODEL', 'gpt-4.1-2025-04-14-override')
    monkeypatch.setenv('BATATIS_RERANK_MODEL', 'gpt-4.1-mini')
    overridden = importlib.reload(config)
    assert overridden.VERIFY_MODEL_OPENAI == 'gpt-4.1-2025-04-14-override'
    assert overridden.RERANK_MODEL == 'gpt-4.1-mini'
    for name in ('BATATIS_SCREEN_MODEL', 'BATATIS_RERANK_MODEL', 'BATATIS_VERIFY_MODEL'):
        monkeypatch.delenv(name, raising=False)
    importlib.reload(config)
    assert estimate_usd('gpt-4.1-2025-04-14', 1_000_000, 0) == 2.0
    assert estimate_usd('gpt-4.1-mini-2025-04-14', 1_000_000, 0) == 0.4


def test_missing_key_exits_before_any_run():
    env = os.environ.copy()
    env.pop('OPENAI_API_KEY', None)
    env['BATATIS_LLM_PROVIDER'] = 'openai'
    proc = subprocess.run(
        [sys.executable, '-m', 'engine.identify.benchmark', '--repeats', '3', '--cases', '20',
         '--fx-usd-cad', '1.4097', '--fx-date', '2026-10-19'],
        capture_output=True, text=True, env=env)
    assert proc.returncode == 2
    assert 'OPENAI_API_KEY is not set' in proc.stderr
    blob = proc.stdout + proc.stderr
    assert 'sk-' not in blob
    assert '1.4097' not in blob
