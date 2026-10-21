"""The judge command line. It prints aggregate scores and error categories, nothing else.

    python -m evals_dev.judge audit
    python -m evals_dev.judge run --split dev --sut engine
    python -m evals_dev.judge run --split dev --sut bm25-floor
    python -m evals_dev.judge run --split dev --label mine -- /abs/python /abs/sut.py
    python -m evals_dev.judge register --arm winner --label "pipeline c1f2" --config-hash c1f2 -- /abs/python /abs/engine/cli_sut.py
    python -m evals_dev.judge run --split test --arm winner        # once; a second run refuses
    python -m evals_dev.judge status

The folder comes from ``BATATIS_JUDGE_DIR`` (default ``~/batatis-judge``). The system under test runs in a separate
process, in a temporary directory, with a scrubbed environment and, on macOS, a sandbox that denies reads of the
judge folder. Its stdout and stderr are never echoed. Per-scenario detail goes to ``<judge folder>/state`` only.

Exit status: 0 done, 1 internal error (class and location only, never a message), 2 usage, 3 refused by the
run-once lock or registration, 4 isolation required but unavailable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evals_dev import envfile

from . import lock, score
from .dataset import DatasetError, JudgeDir, Scenario, headline_exclusions, judge_dir, load_scenarios
from .sandbox import candidate_env, sandbox_prefix
from .sut import SutResult, run_sut

REPO = Path(__file__).resolve().parents[2]
VERSION = 1
BUILTIN_SUTS = {
    'engine': [sys.executable, str(REPO / 'engine' / 'cli_sut.py')],
    'bm25-floor': [sys.executable, str(REPO / 'evals_dev' / 'judge' / 'suts' / 'bm25_floor.py')],
}


def _code_db() -> Path | None:
    raw = os.environ.get('BATATIS_CODEDB')
    path = Path(raw) if raw else REPO / 'codedb' / 'build' / 'codedb.sqlite'
    return path if path.is_file() else None


def known_articles() -> set[str] | None:
    """Division B article ids in the code database, for the fabricated-citation check; None without a database."""
    db = _code_db()
    if db is None:
        return None
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    try:
        rows = con.execute("select id from provisions where doc='NBC-AE' and division='B' and level='article'")
        return {r[0] for r in rows}
    finally:
        con.close()


def _emit(obj: dict) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def _refuse(message: str, code: int) -> int:
    print(f'judge: {message}', file=sys.stderr)
    return code


def run_scenarios(scenarios: list[Scenario], argv: list[str], env: dict, prefix: list[str] | None, timeout: float,
                  jobs: int, known: set[str] | None) -> list[dict]:
    def one(s: Scenario) -> dict:
        with tempfile.TemporaryDirectory(prefix='judge-sut-') as cwd:
            res = run_sut(argv, s.description, env=env, cwd=cwd, timeout=timeout, prefix=prefix)
        return score.score_scenario(s, res, known)

    if jobs <= 1:
        return [one(s) for s in scenarios]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(one, scenarios))


def summarise(records: list[dict], excluded: set[str]) -> dict:
    headline = [r for r in records if r['confidence'] != 'low' and r['id'] not in excluded]
    out = {'scenarios': {'total': len(records), 'headline': len(headline),
                         'excluded_from_headline': len(records) - len(headline)},
           'headline': score.aggregate(headline)}
    out['diagnostic_all'] = (score.aggregate(records) if len(headline) != len(records)
                             else 'same as headline (no scenario excluded)')
    out.update(errors=score.error_counts(records), latency_s=score.latency(records))
    return out


def cmd_audit(args) -> int:
    jd = judge_dir(args.judge_dir)
    scenarios = load_scenarios(jd)
    projection = 'not checked (candidate_prompt.py absent)'
    prompt_script = jd.evals / 'candidate_prompt.py'
    if prompt_script.is_file():
        bad = 0
        for s in scenarios:
            out = subprocess.run([sys.executable, str(prompt_script), s.id], capture_output=True, text=True, timeout=30)
            bad += out.returncode != 0 or out.stdout.rstrip() != s.description
        projection = f'{bad} mismatches in {len(scenarios)}'
    _emit({'judge_version': VERSION, 'scenarios': len(scenarios),
           'dev': sum(s.split == 'dev' for s in scenarios), 'test': sum(s.split == 'test' for s in scenarios),
           'low_confidence': sum(s.confidence == 'low' for s in scenarios),
           'with_required_division_b_article': sum(bool(s.must_cite_b) for s in scenarios),
           'dataset_version': jd.manifest.get('dataset_version'), 'dataset_manifest_sha256': jd.manifest_sha256,
           'candidate_projection': projection, 'code_database': 'found' if _code_db() else 'missing'})
    return 0


def cmd_register(args) -> int:
    jd = judge_dir(args.judge_dir)
    argv = list(args.cmd)
    if argv and argv[0] == '--':
        argv = argv[1:]
    env = dict(kv.split('=', 1) for kv in args.env)
    try:
        rec = lock.register_arm(jd, args.arm, label=args.label, argv=argv, env=env, config_hash=args.config_hash,
                                note=args.note or '', override_reason=args.override)
    except lock.RunOnceError as e:
        return _refuse(str(e), 3)
    _emit({'registered': rec['name'], 'label': rec['label'], 'config_hash': rec['config_hash'],
           'argv_sha256': rec['argv_sha256'], 'registered_at': rec['registered_at']})
    return 0


def cmd_status(args) -> int:
    _emit(lock.status(judge_dir(args.judge_dir)))
    return 0


def _sut_for_dev(args) -> tuple[list[str], str, str]:
    cmd = list(args.cmd)
    if cmd and cmd[0] == '--':
        cmd = cmd[1:]
    if cmd:
        return cmd, args.label or 'custom', 'unspecified'
    if args.sut in BUILTIN_SUTS:
        return BUILTIN_SUTS[args.sut], args.label or args.sut, 'unspecified'
    raise ValueError('give --sut engine|bm25-floor or a command after --')


def cmd_run(args) -> int:
    jd: JudgeDir = judge_dir(args.judge_dir)
    source_env = dict(os.environ)                       # the SUT's environment is built from a copy, never os.environ
    envfile.load_env_file(args.env_file, names=envfile.KEY_NAMES, environ=source_env)
    envfile.apply_defaults(source_env)
    prefix = sandbox_prefix(jd.root)
    isolation = 'sandbox-exec' if prefix else 'env-only'
    extra_env: dict[str, str] = {}
    registration: dict = {}
    if args.split == 'test':
        if not args.arm:
            return _refuse('the test split runs registered arms only (--arm NAME)', 2)
        if prefix is None and not args.allow_weak_isolation:
            return _refuse('the test split needs OS-level isolation (sandbox-exec); none is available here', 4)
        try:
            registration = lock.load_registration(jd, args.arm)
        except lock.RunOnceError as e:
            return _refuse(str(e), 3)
        argv, label, config_hash = registration['argv'], registration['label'], registration['config_hash']
        extra_env = registration['env']
    else:
        try:
            argv, label, config_hash = _sut_for_dev(args)
        except ValueError as e:
            return _refuse(str(e), 2)
    scenarios = load_scenarios(jd, args.split)           # validate the folder before the run-once lock is taken
    if args.limit and args.split == 'dev':
        scenarios = scenarios[:args.limit]
    run_info: dict = {}
    if args.split == 'test':
        try:
            run_info = lock.acquire_run(jd, args.arm, override_reason=args.override_run_once)
        except lock.RunOnceError as e:
            return _refuse(str(e), 3)
    env = candidate_env(source_env, jd.root, extra_env)
    known = known_articles()
    records = run_scenarios(scenarios, argv, env, prefix, args.timeout, args.jobs, known)
    result = {'judge': {'version': VERSION, 'split': args.split, 'dataset_version': jd.manifest.get('dataset_version'),
                        'dataset_manifest_sha256': jd.manifest_sha256, 'isolation': isolation,
                        'git_sha': lock.git_sha()},
              'sut': {'label': label, 'config_hash': config_hash,
                      'argv_sha256': hashlib.sha256(json.dumps(argv).encode()).hexdigest()},
              **summarise(records, headline_exclusions(jd) if args.split == 'test' else set()),
              'checks': {'fabricated_citation': 'checked against the code database' if known is not None
                         else 'not run: code database missing'}}
    if args.split == 'test':
        result['run_once'] = {k: run_info.get(k) for k in ('arm', 'started_at', 'run_number', 'override')}
        lock.finish_run(jd, args.arm, result, records)
    else:
        runs = jd.state / 'dev-runs'
        runs.mkdir(parents=True, mode=0o700, exist_ok=True)
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        name = f'{stamp}-{label}.jsonl'.replace(' ', '_').replace('/', '_')
        with open(runs / name, 'w', encoding='utf-8') as fh:
            for r in records:
                fh.write(json.dumps(r, sort_keys=True) + '\n')
    _emit(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog='python -m evals_dev.judge', description=__doc__.split('\n')[0])
    ap.add_argument('--judge-dir', help='judge folder (default: $BATATIS_JUDGE_DIR or ~/batatis-judge)')
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('audit', help='check the folder against the schema; prints counts only').set_defaults(fn=cmd_audit)
    sub.add_parser('status', help='registered arms and run-once locks').set_defaults(fn=cmd_status)
    reg = sub.add_parser('register', help='freeze an arm before the test run')
    reg.add_argument('--arm', required=True)
    reg.add_argument('--label', required=True)
    reg.add_argument('--config-hash', required=True)
    reg.add_argument('--env', action='append', default=[], help='NAME=value for the SUT (never a secret)')
    reg.add_argument('--note')
    reg.add_argument('--override', help='written reason to re-register a frozen arm (logged)')
    reg.add_argument('cmd', nargs=argparse.REMAINDER)
    reg.set_defaults(fn=cmd_register)
    run = sub.add_parser('run', help='score a SUT on a split')
    run.add_argument('--split', choices=['dev', 'test'], required=True)
    run.add_argument('--arm', help='registered arm (test split)')
    run.add_argument('--sut', choices=sorted(BUILTIN_SUTS), help='built-in SUT (dev split)')
    run.add_argument('--label')
    run.add_argument('--timeout', type=float, default=180.0)
    run.add_argument('--jobs', type=int, default=1)
    run.add_argument('--limit', type=int, help='first N dev scenarios')
    run.add_argument('--env-file')
    run.add_argument('--override-run-once', help='written reason to run the test split a second time (logged)')
    run.add_argument('--allow-weak-isolation', action='store_true',
                     help='test split without sandbox-exec (environment isolation only)')
    run.add_argument('cmd', nargs=argparse.REMAINDER)
    run.set_defaults(fn=cmd_run)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except DatasetError as e:
        return _refuse(str(e), 2)
    except Exception as e:                  # noqa: BLE001 - a traceback or message could carry scenario text
        tb = e.__traceback__
        while tb is not None and tb.tb_next is not None:
            tb = tb.tb_next
        where = f'{Path(tb.tb_frame.f_code.co_filename).name}:{tb.tb_lineno}' if tb else 'unknown'
        return _refuse(f'internal error {type(e).__name__} at {where}', 1)


if __name__ == '__main__':
    raise SystemExit(main())
