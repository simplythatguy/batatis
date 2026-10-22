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


def test_uncalibrated_scoring_never_commits_and_keeps_confirmation_questions(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    out = cli_sut.run('wall close to the property line', DB, Judge(fake_ask('limiting distance'), workers=2))
    assert set(out) >= {'articles', 'section_c', 'engineering_required', 'intake_action', 'questions'}
    assert len(out['articles']) == cli_sut.TOP_K
    assert all(a['division'] == 'B' and not a['committed'] for a in out['articles'])
    assert out['section_c'] == [] and out['questions'] and out['intake_action'] == 'ask'
    assert out['trace']['commit_policy']['status'] == 'uncalibrated'
    assert out['trace']['config']['screen_model'] == 'relevance-1'


def test_section_c_for_selected_articles_is_deterministic_lookup():
    from engine.codes import Codes
    rows = cli_sut.section_c(['9.9.10.1.'], Codes(DB))
    assert rows and all(r['division'] == 'B' and r['provision'].startswith('9.9.10.1.') for r in rows)
    pair = next(p for r in rows for p in r['pairs'])
    assert set(pair) == {'function', 'objective', 'condition'}


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
