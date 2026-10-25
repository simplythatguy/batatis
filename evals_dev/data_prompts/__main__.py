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
            'identify_env': {k: v for k, v in os.environ.items() if k.startswith('BATATIS_IDENTIFY_')},
            'review': {k: os.environ.get(k) for k in ('BATATIS_REVIEW', 'BATATIS_REVIEW_MODEL', 'BATATIS_REVIEW_EFFORT',
                                                      'DPE_REVIEW_TRANSPORT', 'DPE_OPENCODE_MODEL', 'DPE_DEEPSEEK_MODEL',
                                                      'DPE_DEEPSEEK_EFFORT')},
            'elephant': os.environ.get('BATATIS_LIVE_ELEPHANT') == '1', 'split': args.split}


TRANSIENT = ('ConnectError', 'ReadError', 'ConnectTimeout', 'ReadTimeout', 'RemoteProtocolError', 'WriteError',
             'PoolTimeout', 'HTTPStatusError')


def _transient(path: Path) -> bool:
    """A stored case whose review or run failed on the network, not on the workflow: rerun it."""
    result = json.loads(path.read_text())
    review = ((result.get('case') or {}).get('intake') or {}).get('review') or {}
    if review.get('status') == 'failed' and review.get('reason') in TRANSIENT:
        return True
    identify = (result.get('case') or {}).get('identify') or {}
    jev = (result.get('identify_spend') or {}).get('by_provider', {}).get('scoring')
    if identify.get('mode') == 'bm25_fallback' and jev:          # a model screen was attempted and fell back
        return True
    return any('worker:' in e for e in result.get('errors') or [])


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
    todo = [c for c in cases if args.force or not (folder / f'{c.id}.json').exists()
            or (args.rerun_failed and _transient((folder / f'{c.id}.json')))]
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
            usd += result['cost']['summary']['usd'] + (result.get('identify_spend') or {}).get('usd', 0.0)
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
    review = ((result.get('case') or {}).get('intake') or {}).get('review') or {}
    cost = dict(result['cost']['summary'])
    scoring_usd = (result.get('identify_spend') or {}).get('usd', 0.0) - sum(
        v.get('usd', 0.0) for k, v in ((result.get('identify_spend') or {}).get('by_provider') or {}).items()
        if k == 'openai')
    cost['usd'] = round(cost.get('usd', 0.0) + max(0.0, scoring_usd), 6)
    cost['scoring_usd'] = round(max(0.0, scoring_usd), 6)
    return {'case_id': case.id, 'tier': case.tier, 'case_type': case.case_type, 'checks': rows,
            'review_status': review.get('status') or 'none', 'review_reason': review.get('reason'),
            'guardrails': checks.guardrails(case, result, codes), 'cost': cost,
            'judge_usd': book.summary()['usd'], 'facts_unavailable': len(g.facts_unavailable)}


def cmd_score(args) -> int:
    from engine.codes import Codes, default_db
    sut.load_env()
    ledger.install()
    codes = Codes(default_db())
    folder = RUNS / args.name / 'cases'
    cases = [c for c in corpus.select(args.split) if (folder / f'{c.id}.json').exists()]
    missing = len(corpus.select(args.split)) - len(cases)
    out_path = RUNS / args.name / f'score-{_label(args.split)}-{args.judge_model}-{args.judge_effort}.jsonl'
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


def _label(split: str) -> str:
    """A file-name-safe name for a split: a named split as is, a list of case ids as a short hash."""
    return split if len(split) <= 40 else 'ids-' + hashlib.sha256(split.encode()).hexdigest()[:12]


def _scored(name: str, split: str, judge_model: str, judge_effort: str) -> dict[str, dict]:
    path = RUNS / name / f'score-{_label(split)}-{judge_model}-{judge_effort}.jsonl'
    return {row['case_id']: row for row in score.load_rows(path)}


def cmd_compare(args) -> int:
    """Paired comparison on the cases both runs scored: accuracy, per-kind change, flips, bootstrap interval."""
    import random
    a = _scored(args.a, args.split, args.judge_model, args.judge_effort)
    b = _scored(args.b, args.split, args.judge_model, args.judge_effort)
    common = sorted(set(a) & set(b))
    per_case, kinds, flips = [], {}, {'gained': 0, 'lost': 0}
    for cid in common:
        ca = {c['id']: c['passed'] for c in a[cid]['checks']}
        cb = {c['id']: c['passed'] for c in b[cid]['checks']}
        ids = sorted(set(ca) & set(cb))
        per_case.append((sum(ca[i] for i in ids), sum(cb[i] for i in ids), len(ids)))
        for c in a[cid]['checks']:
            if c['id'] in cb:
                k = kinds.setdefault(c['kind'], [0, 0, 0])
                k[0] += ca[c['id']]
                k[1] += cb[c['id']]
                k[2] += 1
                flips['gained'] += (not ca[c['id']]) and cb[c['id']]
                flips['lost'] += ca[c['id']] and (not cb[c['id']])
    n = sum(t for _, _, t in per_case)
    acc_a, acc_b = sum(x for x, _, _ in per_case) / n, sum(y for _, y, _ in per_case) / n
    rng = random.Random(0)
    deltas = []
    for _ in range(2000):
        sample = [per_case[rng.randrange(len(per_case))] for _ in per_case]
        tn = sum(t for _, _, t in sample)
        deltas.append((sum(y for _, y, _ in sample) - sum(x for x, _, _ in sample)) / tn)
    deltas.sort()
    print(f'{len(common)} cases, {n} checks: {args.a} {acc_a:.4f} -> {args.b} {acc_b:.4f}  '
          f'delta {acc_b - acc_a:+.4f} (95% CI {deltas[50]:+.4f} to {deltas[1949]:+.4f})')
    for k, (x, y, t) in sorted(kinds.items()):
        print(f'  {k}: {x}/{t} -> {y}/{t}  ({(y - x) / t:+.4f})')
    print(f'  items gained {flips["gained"]}, lost {flips["lost"]}')
    return 0


def cmd_fails(args) -> int:
    """Failed checks of one scored run with the reference item text, for failure analysis on dev."""
    import random
    from engine.codes import Codes, default_db
    codes = Codes(default_db())
    rows = _scored(args.name, args.split, args.judge_model, args.judge_effort)
    by_id = {c.id: c for c in corpus.load()}
    found = []
    for cid, row in rows.items():
        items = {i.id: i.text for i in gold.gold(by_id[cid], codes).items}
        for check in row['checks']:
            if not check['passed'] and (not args.kind or check['kind'] == args.kind):
                found.append((cid, check['id'], check.get('note', ''), items.get(check['id'], check['id'])))
    random.Random(args.seed).shuffle(found)
    print(f'{len(found)} failed checks')
    for cid, iid, note, text in found[:args.limit]:
        print(f'{cid} {iid} {note} | {text[:220]}')
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
    run.add_argument('--rerun-failed', action='store_true', help='rerun cases that failed on the network')
    run.set_defaults(fn=cmd_run)
    sc = sub.add_parser('score')
    sc.add_argument('--name', required=True)
    sc.add_argument('--split', default='dev')
    sc.add_argument('--judge-model', default='gpt-6.1-sol')
    sc.add_argument('--judge-effort', default='low')
    sc.add_argument('--workers', type=int, default=8)
    sc.set_defaults(fn=cmd_score)
    cmp = sub.add_parser('compare')
    cmp.add_argument('--a', required=True)
    cmp.add_argument('--b', required=True)
    cmp.add_argument('--split', default='dev')
    cmp.add_argument('--judge-model', default='gpt-6.1-sol')
    cmp.add_argument('--judge-effort', default='low')
    cmp.set_defaults(fn=cmd_compare)
    fails = sub.add_parser('fails')
    fails.add_argument('--name', required=True)
    fails.add_argument('--split', default='dev')
    fails.add_argument('--kind', default='')
    fails.add_argument('--limit', type=int, default=40)
    fails.add_argument('--seed', type=int, default=0)
    fails.add_argument('--judge-model', default='gpt-6.1-sol')
    fails.add_argument('--judge-effort', default='low')
    fails.set_defaults(fn=cmd_fails)
    show = sub.add_parser('show')
    show.add_argument('--name', required=True)
    show.add_argument('--case', required=True)
    show.set_defaults(fn=cmd_show)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
