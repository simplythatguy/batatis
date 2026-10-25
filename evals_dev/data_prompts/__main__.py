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

from . import checks, corpus, gold, judge, ledger, manifest, render, score, sut

RUNS = ledger.CACHE.parent / 'runs'
REPO = corpus.REPO


def _git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def _meta(args) -> dict:
    from engine.identify.config import load_config
    from engine.intake import model as model_pass
    from engine.intake import review as review_pass
    config = load_config()
    review_model, review_effort = review_pass.configured()
    transport = os.environ.get('DPE_REVIEW_TRANSPORT') or 'openai'
    review_enabled = not args.offline and os.environ.get('BATATIS_REVIEW', '1') != '0'
    if transport == 'deepseek':
        from . import deepseek_review
        review_model, review_effort = deepseek_review.MODEL, deepseek_review.EFFORT
        review_enabled = True   # sut.run_case explicitly overrides the default review transport
    elif transport == 'opencode':
        from . import opencode_review
        review_model, review_effort = opencode_review.MODEL, 'model-qualified'
        review_enabled = True
    dirty = _git('diff', 'HEAD', '--', 'engine')
    return {'name': args.name, 'started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'commit': _git('rev-parse', 'HEAD'),
            'engine_tree': _git('rev-parse', 'HEAD:engine'),
            'engine_diff_sha256': hashlib.sha256(dirty.encode()).hexdigest() if dirty else None,
            'identify_config': config.as_dict(), 'identify_config_hash': config.config_hash,
            'intake_model': model_pass.MODEL, 'intake_effort': model_pass.EFFORT,
            'offline': args.offline,
            'identify_env': {k: os.environ[k] for k in ['BATATIS_IDENTIFY_CONFIG',
                            *('BATATIS_IDENTIFY_' + f.upper() for f in config.as_dict())] if k in os.environ},
            'review_resolved': {'enabled': review_enabled, 'transport': transport,
                                'model': review_model, 'effort': review_effort, 'service_tier': 'standard'},
            'execution': {k: os.environ.get(k) for k in ('DPE_HTTP_CACHE', 'DPE_SPEND_CAP_USD',
                                                       'DPE_OPENCODE_BIN', 'DPE_OPENCODE_TIMEOUT',
                                                       'BATATIS_REVIEW_DEADLINE_SECONDS')},
            'review': {k: os.environ.get(k) for k in ('BATATIS_REVIEW', 'BATATIS_REVIEW_MODEL', 'BATATIS_REVIEW_EFFORT',
                                                      'DPE_REVIEW_TRANSPORT', 'DPE_OPENCODE_MODEL', 'DPE_DEEPSEEK_MODEL',
                                                      'DPE_DEEPSEEK_EFFORT')},
            'elephant': os.environ.get('BATATIS_LIVE_ELEPHANT') == '1', 'split': args.split}


def _manifest(args, metadata: dict, cases) -> dict:
    return manifest.build(args, metadata, cases)


def _expectations(metadata: dict, case) -> dict:
    if 'offline' not in metadata:
        return {}   # Legacy runs did not record enough to infer deliberately disabled providers.
    live = not metadata['offline']
    config = metadata.get('identify_config') or {}
    stages = []
    if config.get('screen') in ('jev', 'elephant', 'decisions', 'shortlist'):
        stages.append('screen')
    if config.get('rerank') not in (None, 'none'):
        stages.append('rerank')
    if config.get('verifier') not in (None, 'none'):
        stages.append('verify')
    return {'intake_model': live,
            'document_review': bool(case.attachments) and bool((metadata.get('review_resolved') or {}).get('enabled')),
            'identify': live, 'identify_stages': stages, 'verify': live and 'verify' in stages,
            'exhaustive': live and config.get('screen') in ('jev', 'elephant', 'decisions')}


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
    meta_path = RUNS / args.name / 'meta.json'
    manifest_path = meta_path.with_name('manifest.json')
    has_artifacts = meta_path.parent.exists() and any(meta_path.parent.iterdir())
    if has_artifacts and (not meta_path.exists() or not manifest_path.exists()):
        print(f'run {args.name} has legacy/unverified provenance; preserve it and use a new --name', file=sys.stderr)
        return 2
    meta = _meta(args)
    cases = corpus.select(args.split)[:args.limit or None]
    frozen = _manifest(args, meta, cases)
    fingerprint = manifest.fingerprint(frozen)
    if has_artifacts:
        old = json.loads(meta_path.read_text())
        previous = json.loads(manifest_path.read_text())
        if manifest.fingerprint(previous) != fingerprint or old.get('manifest_fingerprint') != fingerprint:
            print(f'run {args.name} manifest mismatch; preserve it and use a new --name (--force cannot override)',
                  file=sys.stderr)
            return 2
        meta = old
    else:
        folder.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents an existing experiment from being quietly upgraded.
        with manifest_path.open('x') as handle:
            json.dump(frozen, handle, indent=2)
        meta['manifest_fingerprint'] = fingerprint
        with meta_path.open('x') as handle:
            json.dump(meta, handle, indent=2)
    existing = {}
    for case in cases:
        path = folder / f'{case.id}.json'
        if path.exists():
            try:
                result = json.loads(path.read_text())
            except (ValueError, OSError):
                result = {'errors': ['invalid_output']}
            if (not isinstance(result, dict) or result.get('case_id') != case.id
                    or result.get('manifest_fingerprint') != fingerprint):
                print(f'{case.id}: output has mismatched/unverified provenance; use a new --name', file=sys.stderr)
                return 2
            result['expected_stages'] = _expectations(meta, case)
            existing[case.id] = result
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
            case = futures[future]
            result['manifest_fingerprint'] = fingerprint
            result['provenance'] = 'manifest-verified'
            result['expected_stages'] = _expectations(meta, case)
            result['failure_reasons'] = checks.completion(result)
            ledger.write_artifact(folder / f'{case.id}.json', json.dumps(result))
            existing[case.id] = result
            done += 1
            errors += bool(result['failure_reasons'])
            usd += _case_cost(result)['usd']
            if done % 10 == 0 or done == len(todo):
                print(f'  {done}/{len(todo)} done, {errors} with errors, ${usd:.4f} workflow cost, '
                      f'{time.monotonic() - started:.0f}s', flush=True)
    stray = ledger.UNATTRIBUTED.summary()
    if stray['calls']:
        print(f'unattributed provider calls: {stray["calls"]} (${stray["usd"]})')
    failed = sum(bool(checks.completion(existing.get(c.id) or {})) for c in cases)
    print(f'cases expected {len(cases)}, complete {len(cases) - failed}, failed/incomplete {failed}')
    uncertain_costs = sum(not _case_cost(result)['cost_complete'] for result in existing.values())
    if uncertain_costs:
        print(f'cost incomplete for {uncertain_costs} cases; USD figures are known subtotals; see the attempt ledger')
    return 1 if failed else 0


def _case_cost(result: dict) -> dict:
    cost = dict((result.get('cost') or {}).get('summary') or {})
    spend = result.get('identify_spend') or {}
    identities = {c.get('request_hash') for c in (result.get('cost') or {}).get('calls') or []
                  if c.get('request_hash')}
    legacy_overlap = False
    if 'transport_calls' in spend:
        scoring = sum(c['usd'] for c in spend['transport_calls']
                      if not c.get('http_request_hash') or c['http_request_hash'] not in identities)
    else:
        roles = spend.get('by_provider') or {}
        scoring = sum(v.get('usd', 0.0) for k, v in roles.items()
                      if k in ('scoring', 'jev', 'elephant', 'openai_decisions', 'anthropic'))
        legacy_overlap = bool(roles.get('verification') or roles.get('openai'))
    cost['usd'] = round(cost.get('usd', 0.0) + scoring, 6)
    cost['live_usd'] = round(cost.get('live_usd', 0.0) + scoring, 6)
    cost['scoring_usd'] = round(scoring, 6)
    cost['cost_complete'] = bool((result.get('cost') or {}).get('summary')) and not (
        cost.get('unknown_cost_attempts') or legacy_overlap
        or any(str(e).startswith('worker:') for e in result.get('errors') or []))
    return cost


def _failure_row(case, result, g, reasons: list[str]) -> dict:
    rows = [{'id': i.id, 'kind': i.kind, 'passed': False, 'scored': False,
             'note': reasons[0], 'evidence': ''} for i in g.items]
    rows += [{'id': f'A:{a}', 'kind': 'A', 'passed': False, 'scored': False,
              'note': reasons[0], 'evidence': ''} for a in g.articles]
    guards = {k: (False, '; '.join(reasons)) for k in ('no_claims', 'citations_resolve',
               'no_alberta_commit_outside_alberta', 'ran')}
    review = (((result.get('case') or {}).get('intake') or {}).get('review') or {})
    return {'case_id': case.id, 'tier': case.tier, 'case_type': case.case_type, 'checks': rows,
            'scored': False, 'failure_reasons': reasons, 'review_status': review.get('status') or 'none',
            'review_reason': review.get('reason'), 'guardrails': guards, 'cost': _case_cost(result),
            'unread_input': [f['text'] for f in review.get('flags') or [] if f.get('kind') == 'not_read'],
            'judge_usd': 0.0, 'judge_live_usd': 0.0, 'validator_version': judge.VERSION,
            'facts_unavailable': len(g.facts_unavailable)}


def _judge_case(case, result, codes, model, effort):
    g = gold.gold(case, codes)
    incomplete = checks.completion(result)
    if incomplete:
        row = _failure_row(case, result, g, incomplete)
        row['guardrails'] = checks.guardrails(case, result, codes)
        return row
    report = render.report(result)
    book = ledger.Ledger()
    try:
        verdicts = judge.grade(case.prompt, report, list(g.items), model=model, effort=effort, book=book)
    except Exception as error:
        row = _failure_row(case, result, g, [f'judge_error:{type(error).__name__}'])
        spent = book.summary()
        row.update(judge_usd=spent['usd'], judge_live_usd=spent['live_usd'],
                   judge_unknown_cost_attempts=spent['unknown_cost_attempts'])
        return row
    invalid = {'unverified', 'missing_verdict', 'duplicate_verdict', 'invalid_verdict', 'invalid_payload',
               'invalid_ids', 'old-validator', 'cache_request_mismatch'}
    rows = [{'id': v.id, 'kind': v.kind, 'passed': v.passed, 'scored': v.note not in invalid,
             'note': v.note, 'evidence': v.evidence} for v in verdicts]
    rows += [{'id': f'A:{a}', 'kind': 'A', 'passed': ok, 'scored': True, 'note': '', 'evidence': ''}
             for a, ok in checks.articles(g.articles, result)]
    review = ((result.get('case') or {}).get('intake') or {}).get('review') or {}
    failures = ['judge_invalid_verdict'] if any(v.note in invalid for v in verdicts) else []
    return {'case_id': case.id, 'tier': case.tier, 'case_type': case.case_type, 'checks': rows,
            'scored': not failures, 'failure_reasons': failures, 'validator_version': judge.VERSION,
            'review_status': review.get('status') or 'none', 'review_reason': review.get('reason'),
            'unread_input': [f['text'] for f in review.get('flags') or [] if f.get('kind') == 'not_read'],
            'guardrails': checks.guardrails(case, result, codes), 'cost': _case_cost(result),
            'judge_usd': book.summary()['usd'], 'judge_live_usd': book.summary()['live_usd'],
            'judge_unknown_cost_attempts': book.summary()['unknown_cost_attempts'],
            'facts_unavailable': len(g.facts_unavailable)}


def cmd_score(args) -> int:
    from engine.codes import Codes, default_db
    sut.load_env()
    ledger.install()
    codes = Codes(default_db())
    folder = RUNS / args.name / 'cases'
    cases = corpus.select(args.split)
    out_path = RUNS / args.name / f'score-{_label(args.split)}-{args.judge_model}-{args.judge_effort}.jsonl'
    meta_path = folder.parent / 'meta.json'
    manifest_path = folder.parent / 'manifest.json'
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    fingerprint = metadata.get('manifest_fingerprint')
    provenance = 'legacy/unverified'
    provenance_error = None
    if manifest_path.exists():
        frozen = json.loads(manifest_path.read_text())
        if manifest.fingerprint(frozen) != fingerprint:
            provenance_error = 'manifest_mismatch'
        elif frozen.get('scoring_sources') != manifest.scoring_sources():
            provenance_error = 'scoring_sources_mismatch'
        else:
            provenance = 'manifest-verified'
    elif fingerprint:
        provenance_error = 'missing_manifest'
    rows, failures, missing = [], 0, 0
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {}
        for case in cases:
            path = folder / f'{case.id}.json'
            result, reason = {}, provenance_error
            if not path.exists():
                missing += 1
                reason = 'missing_output'
            else:
                try:
                    result = json.loads(path.read_text())
                    if not isinstance(result, dict) or result.get('case_id') != case.id:
                        reason = 'invalid_output'
                        result = {}
                except (ValueError, OSError):
                    reason = 'invalid_output'
                if fingerprint and result.get('manifest_fingerprint') != fingerprint:
                    reason = 'output_manifest_mismatch'
            if reason:
                rows.append(_failure_row(case, result, gold.gold(case, codes), [reason]))
                continue
            # Historical output remains legacy even when rejudged with the current validator.
            result = dict(result)
            result['expected_stages'] = _expectations(metadata, case)
            futures[pool.submit(_judge_case, case, result, codes, args.judge_model, args.judge_effort)] = (case, result)
        for future in as_completed(futures):
            case, result = futures[future]
            try:
                row = future.result()
            except Exception as error:
                print(f'judge failed for {case.id}: {type(error).__name__}', file=sys.stderr)
                row = _failure_row(case, result, gold.gold(case, codes), [f'judge_error:{type(error).__name__}'])
            failures += any(r.startswith('judge_error:') for r in row.get('failure_reasons') or [])
            rows.append(row)
    for row in rows:
        reason = next((r for r in row.get('failure_reasons') or [] if r in
                       ('missing_output', 'invalid_output', 'output_manifest_mismatch')), None)
        row['provenance'] = ('unverified:' + (provenance_error or reason)
                             if provenance_error or (fingerprint and reason) else provenance)
        row['manifest_fingerprint'] = fingerprint
    rows.sort(key=lambda r: r['case_id'])
    ledger.write_artifact(out_path, ''.join(json.dumps(r) + '\n' for r in rows))
    summary = score.summarize(rows)
    summary.update(run=args.name, split=args.split, judge=f'{args.judge_model}:{args.judge_effort}',
                   cases_expected=len(cases), cases_missing_output=missing, judge_failures=failures,
                   validator_version=judge.VERSION)
    ledger.write_artifact(out_path.with_suffix('.summary.json'), json.dumps(summary, indent=2))
    print(score.table(summary))
    print(f'  cases without output {missing}, judge failures {failures}')
    guard_failed = any(g['passed'] != g['n'] for g in summary['guardrails'].values())
    return 1 if summary['cases_failed'] or guard_failed else 0


def cmd_show(args) -> int:
    result = json.loads((RUNS / args.name / 'cases' / f'{args.case}.json').read_text())
    print(render.report(result))
    print(f'provenance: {result.get("provenance", "legacy/unverified")}')
    for path in sorted((RUNS / args.name).glob('score-*.jsonl')):
        for row in score.load_rows(path):
            if row['case_id'] == args.case:
                print(f'\n== {path.name}')
                print(f'validator: {row["validator_version"]}; provenance: {row["provenance"]}')
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
    run.add_argument('--force', action='store_true', help='rerun only with the same manifest; preserve old outputs in history')
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
