"""The keyed benchmark command must refuse a missing key and must load the full case set."""
import io
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout

from evals_dev.completeness_eval import MIN_CASES, load_cases, main, redact


def test_live_command_exits_when_openai_key_is_missing():
    env = os.environ.copy()
    env.pop('OPENAI_API_KEY', None)
    env.pop('ANTHROPIC_API_KEY', None)
    env['BATATIS_LLM_PROVIDER'] = 'openai'
    proc = subprocess.run(
        [sys.executable, '-m', 'evals_dev.completeness_eval', '--live', '--repeats', '3'],
        cwd=os.path.join(os.path.dirname(__file__), '..'),
        env=env, capture_output=True, text=True, check=False)
    combined = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert 'OPENAI_API_KEY is not set' in proc.stderr
    assert 'sk-' not in combined


def test_case_set_covers_planted_dev_and_unc_samples():
    cases = load_cases()
    assert len(cases) >= MIN_CASES
    assert sum(1 for case in cases if case.source == 'planted') >= 20
    assert sum(1 for case in cases if case.source == 'evals_dev') == 60
    assert sum(1 for case in cases if case.source == 'unc') >= 1
    dev = next(case for case in cases if case.id == 'dev-001')
    assert '9.10.15.5' not in dev.document.text
    unc = next(case for case in cases if case.source == 'unc')
    assert unc.gold is None
    assert 'gold' not in unc.document.text.casefold()


def test_redact_strips_a_key_shaped_token():
    assert redact('failed sk-abcdefghijklmnopqrstuvwxyz') == 'failed [redacted]'
    assert 'sk-' not in redact('failed sk-abcdefghijklmnopqrstuvwxyz')


def test_offline_report_prints_the_required_lines():
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(['--repeats', '1'])
    report = stdout.getvalue()
    assert code == 0
    for line in (
        'parameter usd_to_cad=1.4097',
        'parameter usd_to_cad_date=2026-10-19',
        'parameter price_floor_cad=125',
        'parameter pinned_openai_model=gpt-4.1-mini',
        'parameter pinned_anthropic_model=claude-sonnet-5-5',
        'variant A',
        'variant B',
        'variant C',
        'p50_latency_s=',
        'p95_latency_s=',
        'usd_per_case=',
        'cad_per_case=',
        'price_floor=CAD',
        'C$125 price floor',
        'per_class_detection:',
        'clean_control_false_positives=',
        'overall_success=',
        'invented_values=0',
        'invented_value_gate=pass',
        'invented_value_gate_all=pass',
        'status=skipped',
    ):
        assert line in report
    assert 'sk-' not in report
