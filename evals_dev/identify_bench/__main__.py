"""Command line for the code identification benchmark.

    python -m evals_dev.identify_bench stage0 [--write]          # reproduce the recorded numbers, no API call
    python -m evals_dev.identify_bench arms                      # arms, config hashes, availability
    python -m evals_dev.identify_bench run ARM... [--datasets ...] [--repeats N] [--workers K] [--dry-run]
    python -m evals_dev.identify_bench pilot                     # 3-case Luna pilot: does spend match the estimate?
    python -m evals_dev.identify_bench ledger                    # spend so far, per provider
    python -m evals_dev.identify_bench pack                      # gzip the working result files for commit
    python -m evals_dev.identify_bench report [...]              # tables from the stored rows
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal

from . import stage0
from .arms import arm_hashes, standard_arms, topo_order
from .cases import select
from .ledger import Ledger
from .live import LEDGER_DIR, OPENAI_STOP_USD, build_context
from .rows import RowStore
from .runner import git_state, pending, run_arms


def _cases(args):
    return select(datasets=args.datasets.split(',') if args.datasets else None,
                  folds=args.folds.split(',') if args.folds else None, gold_only=args.gold_only,
                  ids=args.cases.split(',') if args.cases else None, balanced=args.balanced, limit=args.limit)


def cmd_stage0(args) -> int:
    result = stage0.run()
    for arm, m in result['metrics'].items():
        print(f"{stage0.LABEL[arm]:30s} top-1 {m['hit@1']:.0%}  top-5 {m['hit@5']:.0%}  MRR {m['mrr']:.3f}  "
              f"recall@50 {m['recall@50']:.0%}  recall@200 {m['recall@200']:.0%}")
    print('differences from the published figures:', result['differences'] or 'none')
    if args.write:
        store = RowStore()
        rows = stage0.stage0_rows()
        for arm in stage0.ARMS:                              # regenerate from scratch: recorded rows are deterministic
            for old in (store.dir / f'{arm}.jsonl', store.dir / f'{arm}.jsonl.gz'):
                old.unlink(missing_ok=True)
        for r in rows:
            store.append(r)
        for arm in stage0.ARMS:
            print('wrote', store.pack(arm).name)
    return 1 if result['differences'] else 0


def cmd_arms(args) -> int:
    arms = standard_arms()
    hashes = arm_hashes(arms)
    for name in topo_order(arms, list(arms)):
        a = arms[name]
        avail = '' if getattr(a, 'available', True) else '  (unavailable: search_rank module not found)'
        print(f"{name:28s} {a.kind:7s} {hashes[name]}  upstream={','.join(a.upstream_names) or '-'}  "
              f"repeats={a.repeats}{'  paid' if a.live else ''}{avail}")
    return 0


def cmd_run(args) -> int:
    arms = standard_arms(jev_repeats=args.jev_repeats, verifier_repeats=args.verifier_repeats)
    unknown = [a for a in args.arms if a not in arms]
    if unknown:
        print('unknown arm(s):', ', '.join(unknown), file=sys.stderr)
        return 2
    chain = topo_order(arms, args.arms)
    cases = _cases(args)
    store = RowStore()
    if args.dry_run:
        for name in chain:
            print(f'{name}: {pending(arms, name, cases, store, args.repeats)} rows pending over {len(cases)} cases')
        return 0
    ctx, db_sha = build_context(need_openai=any(arms[n].provider == 'openai' for n in chain),
                                need_jev=any(arms[n].provider == 'jev' for n in chain), store=store,
                                openai_stop=args.openai_stop)
    for name in chain:
        a = arms[name]
        if getattr(a, 'available', True) is False:
            print(f'{name} is unavailable here (search_rank module not found); skipping its rows will fail downstream arms')
    shown = {'n': 0}

    def on_row(row):
        shown['n'] += 1
        if shown['n'] % args.progress == 0 or row['errors']:
            flag = ' ERROR ' + row['errors'][0]['category'] if row['errors'] else ''
            print(f"  {row['arm']} {row['case_id']} r{row['repeat']} usd={row['usd']:.5f}{flag}", flush=True)

    summary = run_arms(arms, args.arms, cases, ctx, repeats=args.repeats, retry_errors=args.retry_errors,
                       workers=args.workers, profile=args.profile, codedb_sha256=db_sha, git_sha=git_state(),
                       on_row=on_row)
    print(json.dumps({'ran': summary.ran, 'skipped': summary.skipped, 'errored': summary.errored,
                      'stopped': summary.stopped, 'by_arm': summary.by_arm}, indent=1))
    return 3 if summary.stopped else 0


def cmd_ledger(args) -> int:
    for provider, stop in (('openai', OPENAI_STOP_USD), ('jev', None)):
        path = LEDGER_DIR / f'{provider}.jsonl'
        if path.exists():
            print(json.dumps(Ledger(path, provider, stop).summary(), indent=1))
    return 0


def cmd_pack(args) -> int:
    store = RowStore()
    for arm in store.arms():
        print('packed', store.pack(arm).name)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog='python -m evals_dev.identify_bench', description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='command', required=True)
    s0 = sub.add_parser('stage0')
    s0.add_argument('--write', action='store_true', help='write the recorded rows to results/')
    s0.set_defaults(fn=cmd_stage0)
    sub.add_parser('arms').set_defaults(fn=cmd_arms)
    run = sub.add_parser('run')
    run.add_argument('arms', nargs='+')
    run.add_argument('--datasets')
    run.add_argument('--folds')
    run.add_argument('--gold-only', action='store_true')
    run.add_argument('--cases')
    run.add_argument('--balanced', type=int, help='N gold-bearing cases spread over the Part groups')
    run.add_argument('--limit', type=int)
    run.add_argument('--repeats', type=int)
    run.add_argument('--jev-repeats', type=int, default=3)
    run.add_argument('--verifier-repeats', type=int, default=5)
    run.add_argument('--workers', type=int, default=1)
    run.add_argument('--profile', choices=['throughput', 'interactive'], default='throughput')
    run.add_argument('--retry-errors', action='store_true')
    run.add_argument('--dry-run', action='store_true')
    run.add_argument('--progress', type=int, default=25)
    run.add_argument('--openai-stop', default=OPENAI_STOP_USD)
    run.set_defaults(fn=cmd_run)
    sub.add_parser('ledger').set_defaults(fn=cmd_ledger)
    sub.add_parser('pack').set_defaults(fn=cmd_pack)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    raise SystemExit(main())
