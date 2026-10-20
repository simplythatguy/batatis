"""The keyed benchmark command must refuse a missing key and must load the full case set."""
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace

from evals_dev.completeness_eval import MIN_CASES, load_cases, main, redact


def test_bench_script_exits_when_openai_key_is_missing():
    env = os.environ.copy()
    env.pop('OPENAI_API_KEY', None)
    env.pop('ANTHROPIC_API_KEY', None)
    script = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'bench_completeness.sh')
    proc = subprocess.run(['bash', script], cwd=os.path.join(os.path.dirname(__file__), '..'),
                          env=env, capture_output=True, text=True, check=False)
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 2
    assert 'OPENAI_API_KEY is not set' in proc.stderr
    assert 'sk-' not in combined
    text = open(script, encoding='utf-8').read()
    assert '--live' in text and '--repeats 3' in text
    assert 'BATATIS_LLM_PROVIDER=openai' in text
    assert 'engine/requirements.txt' in text
    assert 'codedb/requirements.txt' in text


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


def test_offline_report_prints_the_required_lines(tmp_path, monkeypatch):
    database = tmp_path / 'codedb.sqlite'
    database.write_bytes(b'')
    monkeypatch.setenv('BATATIS_CODEDB', str(database))
    dump_dir = tmp_path / 'dumps'
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(['--repeats', '1', '--dump-dir', str(dump_dir)])
    report = stdout.getvalue()
    assert code == 0, stderr.getvalue()
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
        'parameter gate=B',
        'status=skipped',
        'per_case variant=',
        'per_case_dump variant=B',
    ):
        assert line in report
    assert 'sk-' not in report
    assert '/Users/aamia' not in report
    payload = json.loads((dump_dir / 'variant-B.json').read_text(encoding='utf-8'))
    assert payload['variant'] == 'B'
    assert isinstance(payload['cases'], list)
    markdown = (dump_dir / 'variant-B.md').read_text(encoding='utf-8')
    assert '| case | repeat | invented values | false flags on clean controls | missed planted |' in markdown
    combined = report + markdown + (dump_dir / 'variant-B.json').read_text(encoding='utf-8')
    assert 'sk-' not in combined


def _quote(kind, text):
    return SimpleNamespace(kind=kind, text=text)


def _element(field, verdict='present', problem=None, quotes=(), lookup_skipped=False):
    return SimpleNamespace(field=field, verdict=verdict, problem=problem, quotes=list(quotes),
                           lookup_skipped=lookup_skipped)


def test_resolve_codedb_uses_env_then_repo_and_fails_clearly(tmp_path, monkeypatch):
    from engine import codes

    env_db = tmp_path / 'from-env.sqlite'
    env_db.write_bytes(b'env')
    repo_db = tmp_path / 'from-repo.sqlite'
    repo_db.write_bytes(b'repo')
    other = tmp_path / 'codedb.sqlite'
    other.write_bytes(b'other')
    monkeypatch.setattr(codes, 'repo_codedb_candidates', lambda: (repo_db, other))

    monkeypatch.setenv('BATATIS_CODEDB', str(env_db))
    assert codes.resolve_codedb() == env_db
    assert codes.default_db() == env_db
    assert codes.Codes().db_path == env_db

    monkeypatch.setenv('BATATIS_CODEDB', str(tmp_path / 'missing.sqlite'))
    assert codes.resolve_codedb() == repo_db

    monkeypatch.delenv('BATATIS_CODEDB', raising=False)
    assert codes.resolve_codedb() == repo_db
    assert '/Users/aamia' not in str(codes.default_db())

    monkeypatch.setattr(codes, 'repo_codedb_candidates', lambda: (
        tmp_path / 'nope.sqlite', tmp_path / 'also-nope.sqlite'))
    try:
        codes.resolve_codedb()
    except FileNotFoundError as exc:
        message = str(exc)
    else:
        raise AssertionError('expected FileNotFoundError')
    assert 'code database not found' in message
    assert 'BATATIS_CODEDB' in message
    assert 'codedb/build/codedb.sqlite' in message
    assert '/Users/aamia' not in message
    assert 'sk-' not in message
    assert codes.default_db() == tmp_path / 'nope.sqlite'


def test_main_exits_when_no_codedb_exists(tmp_path, monkeypatch, capsys):
    from engine import codes
    import evals_dev.completeness_eval as mod

    monkeypatch.delenv('BATATIS_CODEDB', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(codes, 'repo_codedb_candidates', lambda: (tmp_path / 'missing.sqlite',))
    monkeypatch.setattr(mod, 'load_cases', lambda: [mod.BenchCase('case-1', 'planted', object())])
    code = mod.main(['--repeats', '1', '--dump-dir', str(tmp_path / 'dumps')])
    captured = capsys.readouterr()
    assert code == 2
    assert 'code database not found' in captured.err
    assert 'codedb/build/codedb.sqlite' in captured.err
    assert '/Users/aamia' not in captured.err
    assert 'sk-' not in captured.err + captured.out
    assert not (tmp_path / 'dumps').exists()


def test_case_dump_lists_invented_values_false_flags_and_misses(tmp_path, monkeypatch):
    import evals_dev.completeness_eval as mod

    secret = 'sk-dumpsecretkeyvalue123456'
    monkeypatch.setenv('OPENAI_API_KEY', secret)
    doc = SimpleNamespace(
        form_fields={'Owner': 'Avery Synthetic'},
        data=b'Section B limiting distance: 1.2 m',
        text='Section B limiting distance: 1.2 m',
        ledger=None,
    )
    invented_result = SimpleNamespace(elements=[
        _element('mitigating_measures', 'unclear', 'generic', (
            _quote('pointed', f'invented claim {secret}'),
            _quote('exact', 'Not On The Form'),
        )),
    ])
    control_result = SimpleNamespace(elements=[
        _element('risk_assessment', 'unclear', 'generic'),
        _element('owner_name', 'present'),
    ])
    planted_result = SimpleNamespace(elements=[
        _element('section_b.consistency', 'present'),
        _element('section_c.relevance', 'present'),
    ])
    planted_gold = {
        'control': False,
        'elements': [
            {'field': 'section_b.consistency', 'expected_verdict': 'unclear', 'problem': 'contradiction',
             'defect_class': 'D14', 'requires_codedb': False},
            {'field': 'section_c.relevance', 'expected_verdict': 'unclear', 'problem': 'irrelevant',
             'defect_class': 'D15', 'requires_codedb': False},
            {'field': 'section_c.provision_found', 'expected_verdict': 'missing', 'problem': 'not_found_in_code',
             'defect_class': 'D05', 'requires_codedb': True},
        ],
    }
    rollup = mod.VariantRollup('C', 'gpt-4.1-mini', True, observations=[
        mod.Observation('C', 'case-invented', 'planted', 0, 0, 0, 0.0, 0.0, 2, invented_result, None, doc),
        mod.Observation('C', 'clean-01', 'planted', 0, 0, 0, 0.0, 0.0, 0, control_result,
                        {'control': True, 'elements': []}, doc),
        mod.Observation('C', 'd14-distance', 'planted', 0, 0, 0, 0.0, 0.0, 0, planted_result, planted_gold, doc),
    ])
    rollup.codes_available = False
    paths = mod.write_case_dumps([rollup], tmp_path)
    json_path, markdown_path = paths['C']
    raw = json_path.read_text(encoding='utf-8') + markdown_path.read_text(encoding='utf-8')
    assert secret not in raw
    assert 'sk-' not in raw
    assert '[redacted]' in raw

    payload = json.loads(json_path.read_text(encoding='utf-8'))
    assert payload['variant'] == 'C'
    assert payload['skipped'] is None
    by_id = {row['case_id']: row for row in payload['cases']}
    assert set(by_id) == {'case-invented', 'clean-01', 'd14-distance'}
    assert by_id['case-invented']['invented_values'] == [
        {'field': 'mitigating_measures', 'value': 'invented claim [redacted]'},
        {'field': 'mitigating_measures', 'value': 'Not On The Form'},
    ]
    assert by_id['clean-01']['false_flags'] == [
        {'field': 'risk_assessment', 'problem': 'generic', 'verdict': 'unclear'}]
    assert [item['class'] for item in by_id['d14-distance']['missed_planted']] == ['D14', 'D15']
    assert all(item['class'] != 'D05' for row in payload['cases'] for item in row['missed_planted'])

    markdown = markdown_path.read_text(encoding='utf-8')
    assert '| case | repeat | invented values | false flags on clean controls | missed planted |' in markdown
    assert 'mitigating_measures=invented claim [redacted]' in markdown
    assert 'risk_assessment:generic' in markdown
    assert 'D14 section_b.consistency' in markdown
    assert 'D15 section_c.relevance' in markdown

    summary = '\n'.join(mod.per_case_summary_lines([rollup]))
    assert secret not in summary and 'sk-' not in summary
    assert 'per_case variant=C case=case-invented repeat=0' in summary
    assert 'invented=mitigating_measures=invented claim [redacted]' in summary
    assert 'per_case variant=C case=clean-01 repeat=0' in summary
    assert 'false_flags=risk_assessment:generic' in summary
    assert 'per_case variant=C case=d14-distance repeat=0' in summary
    assert 'missed=D14,D15' in summary


def _stub_rollups(mod, b_invented, c_invented):
    def observation(variant, invented):
        return mod.Observation(variant, 'case-1', 'planted', 0, 0, 0, 0.0, 0.0, invented, result=None)

    return [
        mod.VariantRollup('A', 'none', False, observations=[observation('A', 0)]),
        mod.VariantRollup('B', 'none', False, observations=[observation('B', b_invented)]),
        mod.VariantRollup('C', 'gpt-4.1-mini', True, observations=[observation('C', c_invented)]),
    ]


def _run_stubbed(monkeypatch, tmp_path, argv, b_invented, c_invented):
    import evals_dev.completeness_eval as mod

    monkeypatch.setattr(mod, 'load_cases', lambda: [mod.BenchCase('case-1', 'planted', object())])
    monkeypatch.setattr(mod, 'run_benchmark', lambda *args, **kwargs: _stub_rollups(mod, b_invented, c_invented))
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = mod.main(argv + ['--dump-dir', str(tmp_path)])
    return code, stdout.getvalue(), stderr.getvalue()


def test_default_gate_is_b_and_variant_c_does_not_fail_the_run(tmp_path, monkeypatch):
    code, report, err = _run_stubbed(monkeypatch, tmp_path, ['--repeats', '1'], 0, 5)
    assert code == 0, err
    assert 'parameter gate=B' in report
    assert 'invented_values=5' in report
    assert 'invented_value_gate=fail' in report
    assert 'invented_value_gate_applies=no' in report
    assert 'invented_value_gate_all=pass' in report
    assert 'sk-' not in report


def test_gating_variant_b_still_exits_nonzero(tmp_path, monkeypatch):
    code, report, err = _run_stubbed(monkeypatch, tmp_path, ['--repeats', '1', '--gate', 'B'], 1, 0)
    assert code == 1, err
    assert 'invented_value_gate_all=fail' in report
    assert 'invented_value_gate_applies=yes' in report


def test_gate_can_include_variant_c(tmp_path, monkeypatch):
    code, report, err = _run_stubbed(monkeypatch, tmp_path, ['--repeats', '1', '--gate', 'c'], 0, 5)
    assert code == 1, err
    assert 'parameter gate=C' in report
    assert 'invented_value_gate_all=fail' in report


def test_unknown_gate_exits_without_a_provider_call(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(['--gate', 'Z', '--repeats', '1'])
    assert code == 2
    assert 'gate must list one or more of A, B, C' in stderr.getvalue()
    assert 'sk-' not in stdout.getvalue() + stderr.getvalue()
