"""cli_sut against fake Jev adapters (no network)."""
import subprocess
import sys
from pathlib import Path

from engine import cli_sut
from engine.codes import default_db
from engine.identify import Judge
from engine.tests.test_identify import fake_ask

DB = default_db()
SCRIPT = Path(cli_sut.__file__).resolve()


def test_commits_only_part9_above_threshold_and_builds_section_c(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    out = cli_sut.run('wall close to the property line', DB, Judge(fake_ask('limiting distance'), workers=2))
    assert set(out) >= {'articles', 'section_c', 'engineering_required', 'intake_action', 'questions'}
    arts = out['articles']
    assert len(arts) == cli_sut.TOP_K and all(a['division'] == 'B' for a in arts)
    committed = [a for a in arts if a['committed']]
    assert 0 < len(committed) <= cli_sut.MAX_COMMITS
    assert all(a['part'] == 9 and a['probability'] >= cli_sut.COMMIT_THRESHOLD for a in committed)
    assert any(a['part'] != 9 and a['probability'] >= cli_sut.COMMIT_THRESHOLD and not a['committed'] for a in arts)
    assert out['section_c'] and all(any(r['provision_id'].startswith(a['provision']) for a in committed)
                                    for r in out['section_c'])
    pair = next(p for r in out['section_c'] for p in r['pairs'])
    assert set(pair) == {'function', 'objective', 'condition'}
    assert out['trace']['verifier'].startswith('skipped')
    assert out['engineering_required'] in ('yes', 'no', 'depends')
    assert out['intake_action'] in ('ask', 'proceed_conditionally', 'redirect')


def test_jev_failure_falls_back_to_bm25_without_commits(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    def broken(state, questions, timeout):
        raise ConnectionError('offline')
    out = cli_sut.run('bedroom egress window opening', DB, Judge(broken, attempts=1))
    assert out['trace']['ranker'] == 'bm25 fallback'
    assert out['articles'] and not any(a['committed'] for a in out['articles'])
    assert out['section_c'] == [] and out['intake_action'] == 'ask' and out['questions']


def test_script_runs_from_any_directory(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT)], input='', capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 2 and 'no prose' in r.stderr
