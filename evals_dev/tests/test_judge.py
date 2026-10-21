"""The judge: separate-process SUT, aggregate-only output, run-once lock, isolation of the judge folder.

Every test builds a synthetic judge folder in tmp_path. The real held-out folder is never read here.
"""
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from evals_dev.judge import cli, lock, sandbox, score
from evals_dev.judge.dataset import DatasetError, judge_dir, load_scenarios, parse_scenario
from evals_dev.judge.sut import SutResult, check_output, run_sut

REPO = Path(__file__).resolve().parents[2]
CANARIES = ['CANARY-ALPHA-7731', 'CANARY-BRAVO-4410', 'CANARY-CHARLIE-9902', 'CANARY-GOLD-WHY-5521']


def scenario(n, split, marker, *, must=(), should=(), forbid=(), action='proceed_conditionally', eng='no',
             confidence='high', canary=None):
    sid = f'ab-{n:03d}'
    cite = lambda prov, div='B': {'document': 'NBC(AE) 2023 p2', 'division': div, 'provision': prov, 'pdf_page': 100,
                                   'why': 'CANARY-GOLD-WHY-5521', 'verification': 'evidence/x.json'}
    return {'schema_version': '1.0', 'id': sid, 'split': split, 'category': 'process-and-admin',
            'applicant_type': 'owner',
            'description': f'{canary or "CANARY-ALPHA-7731"} We want to extend a soffit {marker}',
            'missing_info': [], 'confidence': confidence, 'notes': 'CANARY-BRAVO-4410',
            'gold': {'must_cite': [cite(p) for p in must], 'should_cite': [cite(p) for p in should],
                     'must_not_cite': [{'document': 'NBC(AE) 2023 p2', 'division': 'B', 'provision': p,
                                        'prohibited_use': 'x', 'why': 'y'} for p in forbid]
                     + [{'document': 'other', 'provision': '*', 'prohibited_use': 'x', 'why': 'y'}],
                     'engineering_required': eng, 'intake_action': action, 'out_of_scope': action == 'redirect'}}


SCENARIOS = [
    scenario(1, 'dev', 'MARK-S1', must=['9.10.15.5.(8)'], should=['9.10.15.5.(9)'], forbid=['9.10.15.5.(10)'],
             eng='no'),
    scenario(2, 'dev', 'MARK-S2', must=['9.10.9.16.(1)'], eng='depends'),
    scenario(3, 'dev', 'MARK-S3', must=['3.2.2.51.(1)'], eng='yes', canary='CANARY-CHARLIE-9902'),
    scenario(4, 'dev', 'MARK-S4', action='ask', eng='depends'),
    scenario(5, 'dev', 'MARK-S5', action='redirect', eng='no'),
    scenario(6, 'dev', 'MARK-S6', must=['9.8.8.3.(1)'], eng='no'),
    scenario(7, 'test', 'MARK-S7', must=['9.10.15.5.(8)'], eng='no'),
    scenario(8, 'test', 'MARK-S8', must=['3.1.9.1.(1)'], eng='yes'),
    scenario(9, 'test', 'MARK-S9', must=['9.27.5.1.(1)'], eng='no', confidence='low'),
    scenario(10, 'test', 'MARK-S10', action='ask', eng='depends'),
]
ANSWERS = {
    'S1': {'articles': [{'provision': '9.10.15.5.', 'division': 'B', 'committed': True},
                        {'provision': '9.10.15.9.', 'division': 'B', 'committed': False}],
           'engineering_required': 'no', 'intake_action': 'proceed_conditionally', 'questions': ['Where is the wall?']},
    'S2': {'articles': [{'provision': '9.10.8.1.', 'division': 'B', 'committed': True},
                        {'provision': '9.10.9.16.', 'division': 'B', 'committed': False}],
           'engineering_required': 'depends', 'intake_action': 'proceed_conditionally'},
    'S3': {'articles': [{'provision': '9.8.8.3.', 'division': 'B', 'committed': False}],
           'engineering_required': 'no', 'intake_action': 'proceed_conditionally'},
    'S4': {'articles': [], 'engineering_required': 'depends', 'intake_action': 'ask'},
    'S5': {'articles': [{'provision': '9.8.8.3.', 'division': 'B', 'committed': False}],
           'engineering_required': 'no', 'intake_action': 'proceed_conditionally'},
    'S6': {'articles': [{'provision': '9.99.99.99.', 'division': 'B', 'committed': True}],
           'engineering_required': 'no', 'intake_action': 'proceed_conditionally'},
    'S7': {'articles': [{'provision': '9.10.15.5.', 'division': 'B', 'committed': False}],
           'engineering_required': 'no', 'intake_action': 'proceed_conditionally'},
    'S8': {'articles': [{'provision': '3.1.9.1.', 'division': 'B', 'committed': False}],
           'engineering_required': 'yes', 'intake_action': 'proceed_conditionally'},
    'S9': {'articles': [], 'engineering_required': 'no', 'intake_action': 'ask'},
    'S10': {'articles': [], 'engineering_required': 'depends', 'intake_action': 'ask'},
}
SUT_SOURCE = '''
import json, os, sys, time
PEEK = {peek!r}
prose = sys.stdin.read()
try:
    open(PEEK).read(); peek = 'read'
except OSError as e:
    peek = 'blocked'
log = os.environ.get('BATATIS_FAKE_SUT_LOG')
if log:
    with open(log, 'a') as fh:
        fh.write(json.dumps({{'stdin': prose, 'argv': sys.argv, 'cwd': os.getcwd(), 'env': dict(os.environ), 'peek': peek}}) + '\\n')
answers = json.load(open({answers!r}))
if 'MODE-TIMEOUT' in prose: time.sleep(30)
if 'MODE-CRASH' in prose: sys.stderr.write('CANARY-ALPHA-7731 crashed'); sys.exit(3)
if 'MODE-GARBAGE' in prose: print('not json CANARY-ALPHA-7731'); sys.exit(0)
if 'MODE-EMPTY' in prose: sys.exit(0)
if 'MODE-SCHEMA' in prose: print(json.dumps({{'x': 1}})); sys.exit(0)
for key, ans in answers.items():
    if 'MARK-' + key + ' ' in prose + ' ' or prose.rstrip().endswith('MARK-' + key):
        sys.stderr.write('CANARY-ALPHA-7731 on stderr')
        print(json.dumps(ans)); sys.exit(0)
print(json.dumps({{'articles': [], 'intake_action': 'ask'}}))
'''


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / 'batatis-judge'
    scen = root / 'evals' / 'scenarios'
    scen.mkdir(parents=True)
    for s in SCENARIOS:
        (scen / f"{s['id']}.yaml").write_text(json.dumps(s, indent=1))
    (root / 'evals' / 'dataset-manifest.json').write_text(json.dumps(
        {'dataset_version': '9.9.9', 'headline_test_exclusions': ['ab-008']}))
    return root


@pytest.fixture
def sut(tmp_path, folder):
    answers = tmp_path / 'answers.json'
    answers.write_text(json.dumps(ANSWERS))
    peek = folder / 'evals' / 'scenarios' / 'ab-001.yaml'
    script = tmp_path / 'fake_sut.py'
    script.write_text(textwrap.dedent(SUT_SOURCE).format(peek=str(peek), answers=str(answers)))
    return [sys.executable, str(script)]


@pytest.fixture
def codedb(tmp_path, monkeypatch):
    path = tmp_path / 'codedb.sqlite'
    con = sqlite3.connect(path)
    con.execute('create table provisions (id text, doc text, division text, level text)')
    for art in ['9.10.15.5.', '9.10.15.9.', '9.10.8.1.', '9.10.9.16.', '3.2.2.51.', '9.8.8.3.', '3.1.9.1.', '9.27.5.1.']:
        con.execute("insert into provisions values (?, 'NBC-AE', 'B', 'article')", (art,))
    con.commit()
    con.close()
    monkeypatch.setenv('BATATIS_CODEDB', str(path))
    return path


def run_cli(args, folder, capsys, monkeypatch, env=None):
    monkeypatch.setenv('BATATIS_JUDGE_DIR', str(folder))
    monkeypatch.setenv('BATATIS_ENV_FILE', str(folder.parent / 'no-such.env'))      # never load a real .env here
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    code = cli.main(args)
    out = capsys.readouterr()
    return code, out.out, out.err


# ---- dataset ----------------------------------------------------------------------------------------------

def test_default_folder_is_home_batatis_judge(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    (home / 'batatis-judge' / 'evals' / 'scenarios').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.delenv('BATATIS_JUDGE_DIR', raising=False)
    assert judge_dir().root == (home / 'batatis-judge').resolve()
    monkeypatch.setenv('BATATIS_JUDGE_DIR', str(tmp_path / 'nope'))
    with pytest.raises(DatasetError):
        judge_dir()


def test_scenarios_collapse_gold_to_articles_and_skip_wildcards(folder):
    scs = {s.id: s for s in load_scenarios(judge_dir(folder))}
    assert scs['ab-001'].must_cite_b == ('9.10.15.5.',) and scs['ab-001'].should_cite_b == ('9.10.15.5.',)
    assert scs['ab-001'].forbidden_b == ()          # a sentence-level prohibition inside the required article, and a wildcard
    assert scs['ab-001'].part_group == 'part9' and scs['ab-003'].part_group == 'other'
    assert [s.id for s in load_scenarios(judge_dir(folder), 'test')] == [f'ab-{n:03d}' for n in range(7, 11)]


def test_malformed_scenarios_are_reported_without_their_text():
    bad = scenario(1, 'dev', 'MARK-S1')
    bad['gold']['intake_action'] = 'maybe'
    with pytest.raises(DatasetError) as e:
        parse_scenario(bad)
    assert 'CANARY' not in str(e.value) and 'ab-001' not in str(e.value)


# ---- the candidate sees only the applicant's words ---------------------------------------------------------

def test_candidate_gets_only_the_description_in_a_scrubbed_environment(folder, sut, tmp_path, capsys, monkeypatch,
                                                                       codedb):
    log = tmp_path / 'sut.log'
    code, out, err = run_cli(['run', '--split', 'dev', '--label', 'fake', '--', *sut], folder, capsys, monkeypatch,
                             {'BATATIS_FAKE_SUT_LOG': str(log), 'PYTHONPATH': str(folder)})
    assert code == 0
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(rows) == 6
    descriptions = {s['description'] for s in SCENARIOS if s['split'] == 'dev'}
    assert {r['stdin'] for r in rows} == descriptions
    for r in rows:
        assert 'BATATIS_JUDGE_DIR' not in r['env'] and 'PYTHONPATH' not in r['env']
        assert str(folder) not in json.dumps(r)                      # not in env, argv or cwd
        assert not Path(r['cwd']).resolve().is_relative_to(folder.resolve())
        assert len(r['argv']) == 1                                   # no scenario id on the command line
    if sandbox.sandbox_prefix(folder):
        assert {r['peek'] for r in rows} == {'blocked'}              # the OS denies the read


def test_environment_scrub_keeps_provider_keys_and_drops_judge_paths(tmp_path):
    root = tmp_path / 'j'
    root.mkdir()
    env = sandbox.candidate_env({'PATH': '/bin', 'OPENAI_API_KEY': 'k', 'BATATIS_JUDGE_DIR': str(root),
                                 'BATATIS_X': '1', 'WHERE': f'{root}/evals', 'PYTHONPATH': '/x', 'RANDOM': 'z'},
                                root, {'BATATIS_Y': '2'})
    assert env == {'PATH': '/bin', 'OPENAI_API_KEY': 'k', 'BATATIS_X': '1', 'BATATIS_Y': '2'}
    with pytest.raises(ValueError):
        sandbox.candidate_env({}, root, {'BATATIS_Z': f'{root}/evals'})


@pytest.mark.skipif(sandbox.sandbox_prefix(Path('/tmp')) is None, reason='needs sandbox-exec')
def test_sandbox_denies_reading_and_writing_the_judge_folder(tmp_path):
    root = tmp_path / 'judge'
    (root / 'evals').mkdir(parents=True)
    secret = root / 'evals' / 'secret.txt'
    secret.write_text('CANARY-GOLD-WHY-5521')
    probe = tmp_path / 'probe.py'
    probe.write_text(textwrap.dedent(f'''
        import json, os
        r = {{}}
        for name, fn in (('read', lambda: open({str(secret)!r}).read()),
                         ('list', lambda: os.listdir({str(root)!r})),
                         ('stat', lambda: os.stat({str(secret)!r})),
                         ('write', lambda: open({str(root / "evals" / "new.txt")!r}, "w").write("x"))):
            try:
                fn(); r[name] = 'allowed'
            except OSError:
                r[name] = 'blocked'
        print(json.dumps(r))
    '''))
    out = subprocess.run([*sandbox.sandbox_prefix(root), sys.executable, str(probe)], capture_output=True, text=True)
    assert json.loads(out.stdout) == {'read': 'blocked', 'list': 'blocked', 'stat': 'blocked', 'write': 'blocked'}
    plain = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True)
    assert json.loads(plain.stdout)['read'] == 'allowed'            # the probe itself is sound


# ---- output: aggregates and categories only ---------------------------------------------------------------

def test_stdout_and_stderr_contain_no_scenario_text(folder, sut, capsys, monkeypatch, codedb):
    code, out, err = run_cli(['run', '--split', 'dev', '--label', 'fake', '--', *sut], folder, capsys, monkeypatch)
    assert code == 0
    for text in (out, err):
        for needle in [*CANARIES, 'ab-0', 'MARK-S', 'soffit', str(folder)]:
            assert needle not in text, needle
    result = json.loads(out)
    assert result['judge']['split'] == 'dev' and result['scenarios']['total'] == 6


def test_aggregate_numbers_follow_the_definitions(folder, sut, capsys, monkeypatch, codedb):
    code, out, _ = run_cli(['run', '--split', 'dev', '--label', 'fake', '--', *sut], folder, capsys, monkeypatch)
    r = json.loads(out)
    h = r['headline']
    # gold-bearing dev scenarios: S1 (hit@1), S2 (hit@5 not @1), S3 (miss), S6 (gold 9.8.8.3 absent: fabricated id only)
    assert h['m2_required_article_in_top5']['label'] == '2 of 4'
    assert h['hit_at_1']['label'] == '1 of 4'
    assert round(h['mrr'], 4) == round((1 + 0.5 + 0 + 0) / 4, 4)
    # commits: S1 right, S2 wrong, S6's commit is a fabricated id and is dropped (not counted as a pick)
    assert h['committed_picks'] == 2
    assert h['committed_precision_required_only']['label'] == '1 of 2'
    assert h['committed_precision_required_or_helpful']['label'] == '1 of 2'
    assert h['commits_on_scenarios_without_required_article'] == 0
    assert h['forbidden_commit_scenarios'] == 0
    assert h['intake_action']['agreement']['label'] == '5 of 6'      # only S5 (gold redirect) is wrong
    assert h['intake_action']['redirect_recall']['label'] == '0 of 1'
    assert h['engineering_required']['under_flag']['label'] == '1 of 1'   # S3 gold yes answered no
    assert r['errors']['fabricated_citation'] == 1


def test_a_helpful_citation_counts_as_a_right_commit_only_in_the_lenient_measure(tmp_path):
    s = parse_scenario(scenario(1, 'dev', 'MARK', must=['9.10.15.5.(8)'], should=['9.10.9.16.(1)']))
    res = SutResult(None, {'articles': [{'provision': '9.10.9.16.', 'committed': True},
                                        {'provision': '9.10.15.5.', 'committed': True}]}, 0.1)
    rec = score.score_scenario(s, res, {'9.10.15.5.', '9.10.9.16.'})
    assert (rec['commits'], rec['commits_strict'], rec['commits_lenient']) == (2, 1, 2)


def test_commit_on_a_prohibited_article_is_an_error_category(tmp_path):
    s = parse_scenario(scenario(1, 'dev', 'MARK', must=['9.10.15.5.(8)'], forbid=['9.10.14.2.(1)']))
    res = SutResult(None, {'articles': [{'provision': '9.10.14.2.', 'committed': True}]}, 0.1)
    rec = score.score_scenario(s, res, None)
    assert rec['forbidden_commit'] and score.error_counts([rec]) == {'forbidden_citation_committed': 1}


def test_approval_claims_are_flagged_unless_negated():
    assert score.claims_approval({'questions': ['This design complies with the code.']})
    assert score.claims_approval({'a': {'b': ['The wall is approved']}})
    assert not score.claims_approval({'questions': ['We cannot say the design complies.']})
    assert not score.claims_approval({'trace': 'complies'})


def test_small_groups_are_suppressed(folder, sut, capsys, monkeypatch, codedb):
    _, out, _ = run_cli(['run', '--split', 'dev', '--label', 'fake', '--', *sut], folder, capsys, monkeypatch)
    groups = json.loads(out)['headline']['by_part_group']
    assert all('suppressed' in g for g in groups.values())          # 6 scenarios: no group reaches 5


def test_low_confidence_scenarios_leave_the_headline_but_not_the_diagnostic(folder, sut, capsys, monkeypatch, codedb,
                                                                           tmp_path):
    monkeypatch.setenv('BATATIS_JUDGE_DIR', str(folder))
    code, out, _ = run_cli(['register', '--arm', 'a1', '--label', 'fake', '--config-hash', 'h1', '--', *sut],
                           folder, capsys, monkeypatch)
    assert code == 0
    code, out, _ = run_cli(['run', '--split', 'test', '--arm', 'a1', '--allow-weak-isolation'], folder, capsys,
                           monkeypatch)
    r = json.loads(out)
    assert r['scenarios'] == {'total': 4, 'headline': 2, 'excluded_from_headline': 2}   # S9 low confidence + manifest
    assert r['diagnostic_all']['scenarios'] == 4 and r['headline']['scenarios'] == 2


# ---- error categories --------------------------------------------------------------------------------------

@pytest.mark.parametrize('mode,category', [('MODE-CRASH', 'nonzero_exit'), ('MODE-GARBAGE', 'invalid_json'),
                                           ('MODE-EMPTY', 'no_response'), ('MODE-SCHEMA', 'schema_invalid'),
                                           ('MODE-TIMEOUT', 'timeout')])
def test_sut_failures_have_categories_and_never_echo_the_sut(tmp_path, sut, mode, category):
    t0 = 1.0 if mode == 'MODE-TIMEOUT' else 20.0
    res = run_sut(sut, f'{mode} CANARY-ALPHA-7731', env={'PATH': os.environ['PATH']}, cwd=str(tmp_path), timeout=t0)
    assert res.category == category and res.output is None


def test_a_missing_command_is_a_launch_failure(tmp_path):
    res = run_sut(['/no/such/binary'], 'x', env={}, cwd=str(tmp_path), timeout=5)
    assert res.category == 'launch_failed'


def test_failures_stay_in_the_denominators(folder, tmp_path, capsys, monkeypatch, codedb):
    crash = tmp_path / 'crash.py'
    crash.write_text('import sys\nsys.stderr.write("CANARY-ALPHA-7731")\nsys.exit(1)\n')
    _, out, err = run_cli(['run', '--split', 'dev', '--label', 'crash', '--', sys.executable, str(crash)], folder,
                          capsys, monkeypatch)
    r = json.loads(out)
    assert r['errors'] == {'nonzero_exit': 6}
    assert r['headline']['m2_required_article_in_top5']['label'] == '0 of 4'
    assert 'CANARY' not in out + err


def test_output_check_accepts_the_cli_sut_contract():
    assert check_output({'articles': [{'provision': '9.10.15.5.', 'division': 'B', 'committed': False}],
                         'intake_action': 'ask', 'engineering_required': 'depends'}) is None
    assert check_output({'articles': [{'provision': 5}]}) == 'schema_invalid'
    assert check_output({'articles': [], 'intake_action': 'maybe'}) == 'schema_invalid'
    assert check_output([]) == 'schema_invalid'


# ---- the run-once lock -------------------------------------------------------------------------------------

def test_test_split_needs_a_registered_arm(folder, sut, capsys, monkeypatch, codedb):
    code, out, err = run_cli(['run', '--split', 'test', '--arm', 'ghost', '--allow-weak-isolation'], folder, capsys,
                             monkeypatch)
    assert code == 3 and out == '' and 'not registered' in err
    code, out, err = run_cli(['run', '--split', 'test', '--sut', 'engine', '--allow-weak-isolation'], folder, capsys,
                             monkeypatch)
    assert code == 2 and out == ''


def test_second_test_run_refuses_without_a_logged_override(folder, sut, capsys, monkeypatch, codedb):
    run_cli(['register', '--arm', 'w', '--label', 'winner', '--config-hash', 'cfg1', '--', *sut], folder, capsys,
            monkeypatch)
    code, out, err = run_cli(['run', '--split', 'test', '--arm', 'w', '--allow-weak-isolation'], folder, capsys,
                             monkeypatch)
    first = json.loads(out)
    assert code == 0 and first['run_once']['run_number'] == 1 and first['run_once']['override'] is False
    code, out, err = run_cli(['run', '--split', 'test', '--arm', 'w', '--allow-weak-isolation'], folder, capsys,
                             monkeypatch)
    assert code == 3 and out == '' and 'already run' in err
    code, out, err = run_cli(['run', '--split', 'test', '--arm', 'w', '--allow-weak-isolation',
                              '--override-run-once', 'too short'], folder, capsys, monkeypatch)
    assert code == 3 and out == '' and 'at least' in err
    reason = 'rerun after the fake network outage on the judge host'
    code, out, err = run_cli(['run', '--split', 'test', '--arm', 'w', '--allow-weak-isolation',
                              '--override-run-once', reason], folder, capsys, monkeypatch)
    again = json.loads(out)
    assert code == 0 and again['run_once']['run_number'] == 2 and again['run_once']['override'] is True
    log = [json.loads(line) for line in (folder / 'state' / 'overrides.log').read_text().splitlines()]
    assert len(log) == 1 and log[0]['action'] == 'rerun' and log[0]['reason'] == reason
    assert log[0]['previous']['run_number'] == 1
    # the lock survives a crash: it is taken before the SUT starts
    st = lock.status(judge_dir(folder))
    assert st['overrides_logged'] == 1 and st['runs']['test-w']['run_number'] == 2


def test_lock_is_taken_before_the_sut_so_a_crash_still_consumes_the_run(folder, tmp_path, capsys, monkeypatch, codedb):
    crash = tmp_path / 'crash.py'
    crash.write_text('import sys\nsys.exit(1)\n')
    run_cli(['register', '--arm', 'c', '--label', 'crashy', '--config-hash', 'x', '--', sys.executable, str(crash)],
            folder, capsys, monkeypatch)
    assert run_cli(['run', '--split', 'test', '--arm', 'c', '--allow-weak-isolation'], folder, capsys, monkeypatch)[0] == 0
    assert run_cli(['run', '--split', 'test', '--arm', 'c', '--allow-weak-isolation'], folder, capsys, monkeypatch)[0] == 3


def test_concurrent_attempts_let_exactly_one_through(folder):
    jd = judge_dir(folder)
    won, refused = [], []

    def attempt():
        try:
            lock.acquire_run(jd, 'race')
            won.append(1)
        except lock.RunOnceError:
            refused.append(1)

    threads = [threading.Thread(target=attempt) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(won) == 1 and len(refused) == 11


def test_registration_is_frozen_unless_overridden(folder, sut, capsys, monkeypatch):
    base = ['register', '--arm', 'w', '--label', 'winner', '--config-hash', 'cfg1', '--', *sut]
    assert run_cli(base, folder, capsys, monkeypatch)[0] == 0
    code, out, err = run_cli(base, folder, capsys, monkeypatch)
    assert code == 3 and 'frozen' in err
    code, out, err = run_cli(['register', '--arm', 'w', '--label', 'winner', '--config-hash', 'cfg2',
                              '--override', 'the registered command had a typo in its path', '--', *sut],
                             folder, capsys, monkeypatch)
    assert code == 0
    st = lock.status(judge_dir(folder))
    assert st['arms']['w']['config_hash'] == 'cfg2' and st['overrides_logged'] == 1


def test_arm_names_are_restricted(folder):
    with pytest.raises(lock.RunOnceError):
        lock.register_arm(judge_dir(folder), '../escape', label='x', argv=['x'], env={}, config_hash='h')


def test_test_split_requires_os_isolation_unless_waived(folder, sut, capsys, monkeypatch, codedb):
    run_cli(['register', '--arm', 'w', '--label', 'winner', '--config-hash', 'h', '--', *sut], folder, capsys,
            monkeypatch)
    monkeypatch.setattr(cli, 'sandbox_prefix', lambda root: None)
    code, out, err = run_cli(['run', '--split', 'test', '--arm', 'w'], folder, capsys, monkeypatch)
    assert code == 4 and out == '' and 'isolation' in err
    assert lock.status(judge_dir(folder))['runs'] == {}                   # refusing did not consume the run


def test_a_broken_folder_is_rejected_before_the_lock_is_taken(folder, sut, capsys, monkeypatch):
    run_cli(['register', '--arm', 'w', '--label', 'winner', '--config-hash', 'h', '--', *sut], folder, capsys,
            monkeypatch)
    (folder / 'evals' / 'scenarios' / 'ab-011.yaml').write_text('{not json')
    code, out, err = run_cli(['run', '--split', 'test', '--arm', 'w', '--allow-weak-isolation'], folder, capsys,
                             monkeypatch)
    assert code == 2 and lock.status(judge_dir(folder))['runs'] == {}


def test_private_detail_stays_in_the_judge_folder(folder, sut, capsys, monkeypatch, codedb):
    run_cli(['register', '--arm', 'w', '--label', 'winner', '--config-hash', 'h', '--', *sut], folder, capsys,
            monkeypatch)
    _, out, _ = run_cli(['run', '--split', 'test', '--arm', 'w', '--allow-weak-isolation'], folder, capsys, monkeypatch)
    detail = (folder / 'state' / 'run-test-w.detail-1.jsonl').read_text().splitlines()
    assert len(detail) == 4 and json.loads(detail[0])['id'].startswith('ab-')
    assert 'ab-0' not in out
    assert oct((folder / 'state').stat().st_mode & 0o777) == '0o700'


def test_audit_prints_counts_only(folder, capsys, monkeypatch, codedb):
    code, out, err = run_cli(['audit'], folder, capsys, monkeypatch)
    a = json.loads(out)
    assert code == 0 and a['scenarios'] == 10 and a['dev'] == 6 and a['test'] == 4 and a['low_confidence'] == 1
    assert a['dataset_version'] == '9.9.9' and a['candidate_projection'].startswith('not checked')
    for needle in [*CANARIES, 'ab-0']:
        assert needle not in out + err


def test_audit_checks_the_candidate_projection_when_the_dataset_script_exists(folder, capsys, monkeypatch, codedb):
    (folder / 'evals' / 'candidate_prompt.py').write_text(
        "import json,sys,pathlib\nd=json.loads((pathlib.Path(__file__).parent/'scenarios'/(sys.argv[1]+'.yaml')).read_text())\n"
        "print(d['description'])\n")
    code, out, _ = run_cli(['audit'], folder, capsys, monkeypatch)
    assert json.loads(out)['candidate_projection'] == '0 mismatches in 10'


def test_status_lists_arms_and_runs_without_scenario_data(folder, sut, capsys, monkeypatch):
    run_cli(['register', '--arm', 'w', '--label', 'winner', '--config-hash', 'h', '--', *sut], folder, capsys, monkeypatch)
    code, out, _ = run_cli(['status'], folder, capsys, monkeypatch)
    st = json.loads(out)
    assert st['arms']['w']['label'] == 'winner' and st['runs'] == {} and st['overrides_logged'] == 0


def test_the_bm25_floor_sut_commits_nothing(tmp_path):
    db = REPO / 'codedb' / 'build' / 'codedb.sqlite'
    if not db.is_file() and not os.environ.get('BATATIS_CODEDB'):
        pytest.skip('code database not built at codedb/build/codedb.sqlite')
    out = subprocess.run([sys.executable, str(REPO / 'evals_dev' / 'judge' / 'suts' / 'bm25_floor.py')],
                         input='We want to extend the soffit over a wall 0.3 m from the property line',
                         capture_output=True, text=True, cwd=tmp_path, env={**os.environ})
    obj = json.loads(out.stdout)
    assert check_output(obj) is None and obj['articles'] and not any(a['committed'] for a in obj['articles'])


def test_an_unexpected_error_prints_its_class_and_place_never_its_message(folder, sut, capsys, monkeypatch, codedb):
    def boom(*a, **k):
        raise ValueError('CANARY-ALPHA-7731 leaked through an exception message')
    monkeypatch.setattr(cli, 'run_scenarios', boom)
    code, out, err = run_cli(['run', '--split', 'dev', '--label', 'x', '--', *sut], folder, capsys, monkeypatch)
    assert code == 1 and out == '' and 'ValueError' in err and 'CANARY' not in err


def test_running_the_judge_does_not_change_the_callers_environment(folder, sut, capsys, monkeypatch, codedb, tmp_path):
    env_file = tmp_path / 'keys.env'
    env_file.write_text('OPENAI_API_KEY=sk-test-not-a-real-key-123456\n')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    run_cli(['run', '--split', 'dev', '--label', 'x', '--env-file', str(env_file), '--limit', '1', '--', *sut], folder,
            capsys, monkeypatch)
    assert 'OPENAI_API_KEY' not in os.environ
