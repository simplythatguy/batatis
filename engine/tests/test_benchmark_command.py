"""The keyed benchmark refuses to run without OPENAI_API_KEY and does not print a key."""
import os
import subprocess
import sys

from engine.identify.benchmark import price_floor_line


def test_price_floor_line_uses_the_given_rate():
    line = price_floor_line('c_openai_rerank_verify', 1.25, 1.4097, '2026-10-19')
    assert 'fx_usd_cad=1.4097' in line and 'fx_date=2026-10-19' in line
    assert 'floor_cad=125.00' in line and 'below_floor=yes' in line
    assert 'cad_per_case=1.2500' in line


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
