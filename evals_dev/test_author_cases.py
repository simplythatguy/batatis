"""Exercise the Section C refresher through its command-line interface."""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

from evals_dev.validate_cases import DEFAULT_DB

ROOT = pathlib.Path(__file__).resolve().parent


@pytest.fixture
def case_dir(tmp_path):
    if not pathlib.Path(DEFAULT_DB).is_file():
        pytest.skip('code database not built')
    return pathlib.Path(shutil.copytree(ROOT / 'cases', tmp_path / 'cases'))


def run_refresh(case_dir, *flags):
    return subprocess.run(
        [sys.executable, str(ROOT / 'author_cases.py'), '--db', DEFAULT_DB,
         '--cases', str(case_dir), *flags],
        capture_output=True, text=True, check=False, timeout=15,
    )


def snapshot(case_dir):
    return {p.name: p.read_bytes() for p in case_dir.iterdir()}


def test_default_reports_stale_section_c_without_writing(case_dir):
    path = case_dir / 'dev-004.json'
    case = json.loads(path.read_text())
    case['gold']['section_c'][0]['pairs'] = ['[F03-OP3.1]']
    path.write_text(json.dumps(case))
    before = snapshot(case_dir)

    result = run_refresh(case_dir)

    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)['changed_cases'] == ['dev-004']
    assert snapshot(case_dir) == before


def test_write_refreshes_only_section_c_and_preserves_reviewed_labels(case_dir):
    path = case_dir / 'dev-004.json'
    case = json.loads(path.read_text())
    case['description'] += ' Keep this exact applicant wording.'
    case['authoring']['notes'] += ' Preserve this later model-review receipt.'
    path.write_text(json.dumps(case, indent=3))
    expected = {p.name: json.loads(p.read_text()) for p in case_dir.iterdir()}
    for cid in ['dev-001', 'dev-004']:
        path = case_dir / f'{cid}.json'
        case = json.loads(path.read_text())
        case['gold']['section_c'][0]['pairs'] = ['[F03-OS1.2]']
        path.write_text(json.dumps(case))
    before = snapshot(case_dir)

    result = run_refresh(case_dir, '--write')

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['changed_cases'] == ['dev-001', 'dev-004']
    assert {p.name: json.loads(p.read_text()) for p in case_dir.iterdir()} == expected
    after = snapshot(case_dir)
    assert all(after[name] == data for name, data in before.items()
               if name not in {'dev-001.json', 'dev-004.json'})
    assert expected['dev-005.json']['gold']['intake_action'] == 'ask'
    assert expected['dev-011.json']['gold']['engineering_required'] == 'depends'
    assert expected['dev-004.json']['seed_provision'] == '9.10.15.2.(3)'
    assert expected['dev-008.json']['seed_provision'] == '9.23.17.3.(1)'

    assert run_refresh(case_dir, '--check').returncode == 0
    repeated = run_refresh(case_dir, '--write')
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(repeated.stdout)['changed_cases'] == []
    assert snapshot(case_dir) == after


@pytest.mark.parametrize('problem', [
    'missing-case', 'bad-json', 'unknown-benchmark', 'invalid-label', 'mismatched-id', 'unexpected-case',
])
def test_invalid_batch_does_not_partially_refresh_earlier_cases(case_dir, problem):
    earlier = case_dir / 'dev-004.json'
    case = json.loads(earlier.read_text())
    case['gold']['section_c'][0]['pairs'] = ['[F03-OS1.2]']
    earlier.write_text(json.dumps(case))
    last = case_dir / 'dev-060.json'
    case = json.loads(last.read_text())
    if problem == 'missing-case':
        last.unlink()
    elif problem == 'bad-json':
        last.write_text('{invalid')
    elif problem == 'unexpected-case':
        shutil.copyfile(last, case_dir / 'dev-061.json')
    else:
        if problem == 'unknown-benchmark':
            case['gold']['must_cite'] = [
                {'division': 'B', 'provision': '9.10.15.5.(99)', 'role': 'benchmark'},
            ]
        elif problem == 'invalid-label':
            case['gold']['engineering_required'] = 'maybe'
        else:
            case['id'] = 'dev-059'
        last.write_text(json.dumps(case))
    before = snapshot(case_dir)

    result = run_refresh(case_dir, '--write')

    assert result.returncode == 2
    assert json.loads(result.stderr)['ok'] is False
    assert snapshot(case_dir) == before


def test_refresh_uses_listed_benchmarks_not_seed_or_scope_and_keeps_conditions(case_dir):
    path = case_dir / 'dev-001.json'
    case = json.loads(path.read_text())
    case['gold']['must_cite'] = [
        {'division': 'B', 'provision': '9.23.10.1.(1)', 'role': 'benchmark'},
        {'division': 'B', 'provision': '9.10.15.5.(8)', 'role': 'scope'},
    ]
    path.write_text(json.dumps(case))
    result = run_refresh(case_dir, '--write')

    assert result.returncode == 0, result.stderr
    updated = json.loads(path.read_text())
    rows = updated['gold'].pop('section_c')
    case['gold'].pop('section_c')
    assert updated == case
    assert [r['provision'] for r in rows] == ['9.23.10.1.(1)']
    assert {'pair': '[F22-OH4]', 'when': 'Applies to floors and elements that support floors.'} in rows[0]['conditional']
