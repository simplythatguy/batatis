"""Run the engine on the Data Prompts cases, judge the output, and print accuracy, guardrails and cost.

    DPE_ENV_FILE=/path/.env DATA_PROMPTS_ROOT=/path/Data\\ Prompts \\
      .venv/bin/python -m evals_dev.data_prompts run --name baseline --split dev
    ... score --name baseline --split dev
    ... show --name baseline --case L04-001

Runs and verdicts live under .dpe-cache/ (git-ignored). Provider responses are cached by request, so a
rerun of unchanged code costs nothing; DPE_HTTP_CACHE=refresh forces fresh calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

from . import checks, corpus, gold, judge, ledger, render, score, sut

RUNS = ledger.CACHE.parent / 'runs'
REPO = corpus.REPO


def _git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def _meta(args) -> dict:
    from engine.identify.config import load_config
    from engine.intake import model as model_pass
    config = load_config()
    dirty = _git('diff', 'HEAD', '--', 'engine')
    return {'name': args.name, 'started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'commit': _git('rev-parse', 'HEAD'),
            'engine_tree': _git('rev-parse', 'HEAD:engine'),
            'engine_diff_sha256': hashlib.sha256(dirty.encode()).hexdigest() if dirty else None,
            'identify_config': config.as_dict(), 'identify_config_hash': config.config_hash,
            'intake_model': model_pass.MODEL, 'intake_effort': model_pass.EFFORT,
            'elephant': os.environ.get('BATATIS_LIVE_ELEPHANT') == '1', 'split': args.split}


def cmd_run(args) -> int:
    # Worker processes, not threads: pdfium (the engine's PDF reader) is not thread-safe and
    # concurrent reads in one process crash it.
    sut.init_worker(not args.offline, args.elephant)
    folder = RUNS / args.name / 'cases'
    folder.mkdir(parents=True, exist_ok=True)
    meta_path = RUNS / args.name / 'meta.json'
    meta = _meta(args)
    if meta_path.exists() and not args.force:
        old = json.loads(meta_path.read_text())
        if (old.get('engine_tree'), old.get('engine_diff_sha256')) != (meta['engine_tree'], meta['engine_diff_sha256']):
            print(f'run {args.name} was made from other engine code; use a new --name or --force', file=sys.stderr)
            return 2
    meta_path.write_text(json.dumps(meta, indent=2))
    cases = corpus.select(args.split)[:args.limit or None]
    todo = [c for c in cases if args.force or not (folder / f'{c.id}.json').exists()]
    print(f'{len(cases)} cases, {len(todo)} to run, workers {args.workers}', flush=True)
    done, errors, usd, started = 0, 0, 0.0, time.monotonic()
    with ProcessPoolExecutor(args.workers, initializer=sut.init_worker,
                             initargs=(not args.offline, args.elephant)) as pool:
        futures = {pool.submit(sut.run_case, c): c for c in todo}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as error:                 # a crashed worker: record it, keep the run going
                case = futures[future]
                result = {'case_id': case.id, 'errors': [f'worker: {type(error).__name__}: {error}'[:300]],
                          'cost': ledger.as_dict(ledger.Ledger())}
            (folder / f'{result["case_id"]}.json').write_text(json.dumps(result))
            done += 1
            errors += bool(result.get('errors'))
            usd += result['cost']['summary']['usd']
            if done % 10 == 0 or done == len(todo):
                print(f'  {done}/{len(todo)} done, {errors} with errors, ${usd:.4f} workflow cost, '
                      f'{time.monotonic() - started:.0f}s', flush=True)
    stray = ledger.UNATTRIBUTED.summary()
    if stray['calls']:
        print(f'unattributed provider calls: {stray["calls"]} (${stray["usd"]})')
    return 0


def _judge_case(case, result, codes, model, effort):
    g = gold.gold(case, codes)
    report = render.report(result)
    book = ledger.Ledger()
    verdicts = judge.grade(case.prompt, report, list(g.items), model=model, effort=effort, book=book)
    rows = [{'id': v.id, 'kind': v.kind, 'passed': v.passed, 'note': v.note, 'evidence': v.evidence} for v in verdicts]
    rows += [{'id': f'A:{a}', 'kind': 'A', 'passed': ok, 'note': '', 'evidence': ''}
             for a, ok in checks.articles(g.articles, result)]
    return {'case_id': case.id, 'tier': case.tier, 'case_type': case.case_type, 'checks': rows,
            'guardrails': checks.guardrails(case, result, codes), 'cost': result['cost']['summary'],
            'judge_usd': book.summary()['usd'], 'facts_unavailable': len(g.facts_unavailable)}


def cmd_score(args) -> int:
    from engine.codes import Codes, default_db
    sut.load_env()
    ledger.install()
    codes = Codes(default_db())
    folder = RUNS / args.name / 'cases'
    cases = [c for c in corpus.select(args.split) if (folder / f'{c.id}.json').exists()]
    missing = len(corpus.select(args.split)) - len(cases)
    out_path = RUNS / args.name / f'score-{args.split}-{args.judge_model}-{args.judge_effort}.jsonl'
    rows, failures = [], 0
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(_judge_case, c, json.loads((folder / f'{c.id}.json').read_text()), codes,
                               args.judge_model, args.judge_effort): c for c in cases}
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as error:
                failures += 1
                print(f'judge failed for {futures[future].id}: {type(error).__name__}: {error}'[:300], file=sys.stderr)
    rows.sort(key=lambda r: r['case_id'])
    out_path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    summary = score.summarize(rows)
    summary.update(run=args.name, split=args.split, judge=f'{args.judge_model}:{args.judge_effort}',
                   cases_missing_output=missing, judge_failures=failures)
    out_path.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2))
    print(score.table(summary))
    print(f'  cases without output {missing}, judge failures {failures}')
    return 0 if not failures else 1


def cmd_show(args) -> int:
    result = json.loads((RUNS / args.name / 'cases' / f'{args.case}.json').read_text())
    print(render.report(result))
    for path in sorted((RUNS / args.name).glob('score-*.jsonl')):
        for row in score.load_rows(path):
            if row['case_id'] == args.case:
                print(f'\n== {path.name}')
                for check in row['checks']:
                    print(f"{'PASS' if check['passed'] else 'FAIL'} {check['id']} {check.get('note', '')} {check.get('evidence', '')[:120]}")
                print('guardrails', row['guardrails'])
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='python -m evals_dev.data_prompts')
    sub = parser.add_subparsers(dest='cmd', required=True)
    run = sub.add_parser('run')
    run.add_argument('--name', required=True)
    run.add_argument('--split', default='dev')
    run.add_argument('--limit', type=int, default=0)
    run.add_argument('--workers', type=int, default=6)
    run.add_argument('--force', action='store_true')
    run.add_argument('--offline', action='store_true', help='no provider calls: rules, forms and keyword fallback only')
    run.add_argument('--elephant', action='store_true', help='allow Elephant requests (50 free per day)')
    run.set_defaults(fn=cmd_run)
    sc = sub.add_parser('score')
    sc.add_argument('--name', required=True)
    sc.add_argument('--split', default='dev')
    sc.add_argument('--judge-model', default='gpt-6.1-sol')
    sc.add_argument('--judge-effort', default='low')
    sc.add_argument('--workers', type=int, default=8)
    sc.set_defaults(fn=cmd_score)
    show = sub.add_parser('show')
    show.add_argument('--name', required=True)
    show.add_argument('--case', required=True)
    show.set_defaults(fn=cmd_show)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
