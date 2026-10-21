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


ASSUMED_OUTPUT_TOKENS = 2600       # the plan's assumption: 0.6k answer + 2k reasoning at medium effort (pilot: 430-1,233)


def cmd_pilot(args) -> int:
    """Three cases through one verifier arm before any larger OpenAI run: does the spend match the estimate?"""
    from . import pricing
    from .methods.verifier import prompt, verifier_system
    arms = standard_arms()
    arm = arms[args.arm]
    cases = select(datasets=['public53'], balanced=3)
    store = RowStore()
    ctx, db_sha = build_context(need_openai=True, need_jev=True, store=store, openai_stop=args.openai_stop)
    before = ctx.openai.ledger.settled()
    run_arms(arms, [args.arm], cases, ctx, repeats=1, git_sha=git_state(), codedb_sha256=db_sha, profile='throughput')
    hashes = arm_hashes(arms)
    rows = store.latest(args.arm, hashes[args.arm])
    print(f'pilot arm {args.arm}: {len(cases)} cases')
    ok = True
    for c in cases:
        row = rows.get((c.id, 0))
        if row is None or row['errors']:
            print(f'  {c.id}: no usable row', row['errors'] if row else '')
            ok = False
            continue
        up = store.by_key(arm.upstream_names[0])[row['upstream'][arm.upstream_names[0]]]
        cand = up['order'][:arm.shortlist_n]
        text = verifier_system(arm.out_of_list) + prompt(c.query, ctx.arts, cand, arm.chars)
        expected = pricing.cost_usd(arm.model, pricing.input_token_estimate(text), ASSUMED_OUTPUT_TOKENS)
        t = row['tokens']['openai']
        ratio = float(row['usd']) / float(expected)
        ok = ok and ratio <= 1.25                  # an estimate that is too high is safe; one that is too low is not
        print(f"  {c.id[-28:]:28s} {c.part_group:6s} in {t['input']:6d} (est {pricing.input_token_estimate(text)}) out {t['output']:5d} "
              f"(reasoning {t['reasoning']}) expected ${float(expected):.5f} actual ${row['usd']:.5f} ratio {ratio:.2f} "
              f"latency {row['latency_ms'].get('verify', 0) / 1000:.1f}s picks {len(row['picks'])} dropped {len(row['dropped'])}")
    spent = ctx.openai.ledger.settled() - before
    print(f'pilot spend ${float(spent):.5f}; ledger total ${float(ctx.openai.ledger.settled()):.5f}; '
          f'spend per case at or below the estimate (at most 1.25x): {"YES" if ok else "NO"}')
    return 0 if ok else 1


def _analysis():
    from .analysis import analyse
    from .live import db_path
    arts = None
    try:
        from engine.identify.corpus import articles
        arts = articles(db_path())
    except Exception:                                    # noqa: BLE001 - the integrity recheck is skipped without a database
        pass
    return analyse(arts=arts)


def _ledger_summaries():
    out = []
    for provider, stop in (('openai', OPENAI_STOP_USD), ('jev', None)):
        path = LEDGER_DIR / f'{provider}.jsonl'
        out.append(Ledger(path, provider, stop).summary() if path.exists() else None)
    return out


def cmd_decision(args) -> int:
    import hashlib
    from . import memo, pin
    from .datasets import FOLDS_FILE
    an = _analysis()
    openai, jev = _ledger_summaries()
    folds_sha = json.loads(FOLDS_FILE.read_text())['sha256']
    decision_text = memo.render_decision(an, ledger_openai=openai, ledger_jev=jev, folds_sha=folds_sha)
    g1_text = memo.render_g1_report(an, ledger_openai=openai, ledger_jev=jev)
    docs = FOLDS_FILE.parents[2] / 'docs' / 'accuracy'
    if args.write:
        docs.mkdir(parents=True, exist_ok=True)
        (docs / 'code-id-decision.md').write_text(decision_text)
        (docs / 'g1-report.md').write_text(g1_text)
        print('wrote', docs / 'code-id-decision.md', 'and', docs / 'g1-report.md')
    else:
        print(decision_text)
    if args.write_pin:
        if an.decision is None or an.decision.winner is None:
            print('no winner to pin', file=sys.stderr)
            return 1
        fields = pin.pin_for(an.arms, an.decision.winner)
        chosen_at = max(r['started_at'] for rows in an.L.by_key.values() for r in rows.values() if r['source'] == 'live')[:10]
        target = FOLDS_FILE.parents[2] / 'engine' / 'identify' / 'pipeline.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(pin.pipeline_json(fields, chosen_at=chosen_at, memo_sha=hashlib.sha256(decision_text.encode()).hexdigest()))
        print('pinned', an.decision.winner, 'config_hash', pin.config_hash(fields), '->', target)
    return 0


def cmd_report(args) -> int:
    from . import memo
    an = _analysis()
    for name, e in an.selection.items():
        print(f"{name:26s} SR {e.sr['label']:>9s} ({e.sr['rate']:.1%})  top1 {e.ranking['hit@1']['mean']:.3f}  MRR {e.ranking['mrr']['mean']:.3f}  "
              f"${e.cost['usd_per_case_run']:.4f}/run  repeats {e.repeats}  missing {e.missing_rows}  errors {e.errors['rows_with_errors']}")
    return 0


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
    dec = sub.add_parser('decision')
    dec.add_argument('--write', action='store_true', help='write docs/accuracy/code-id-decision.md and g1-report.md')
    dec.add_argument('--write-pin', action='store_true', help='write engine/identify/pipeline.json for the winner')
    dec.set_defaults(fn=cmd_decision)
    sub.add_parser('report').set_defaults(fn=cmd_report)
    pilot = sub.add_parser('pilot')
    pilot.add_argument('--arm', default='V15f-R5')
    pilot.add_argument('--openai-stop', default=OPENAI_STOP_USD)
    pilot.set_defaults(fn=cmd_pilot)
    sub.add_parser('ledger').set_defaults(fn=cmd_ledger)
    sub.add_parser('pack').set_defaults(fn=cmd_pack)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    raise SystemExit(main())
