"""Assemble the evaluated results the memo and the gate print: one pass over the rows, no side effects.

``analyse`` loads the throughput rows (accuracy) and the interactive rows (latency) for the standard arms, evaluates every
arm that has rows on the selection folds and on the development folds, and returns plain dicts and dataclasses.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from evals_dev.metrics import evaluate, rate

from . import decision, report
from .arms import arm_hashes, standard_arms, topo_order
from .datasets import BenchCase, load_all
from .methods.base import Arm
from .report import ArmEval, Loaded
from .rows import RowStore

SELECTION = ('selection',)
DEVELOPMENT = ('calibration', 'validation')
PIPELINES = ('R0-bm25', 'R1-searchrank-v3', 'R2-precedent-lofo', 'R4-jev-screen', 'R5-jev-screen-rerank60',
             'R6-bm25-jev-rerank60', 'F1-rrf-R5-R1-R2', 'A9-bm25-luna-rerank60', 'V15f-R5', 'V40f-R5', 'V15c-R5',
             'V15f-R6', 'V15f-F1', 'V15f-R5-ool')


@dataclass
class Analysis:
    arms: dict[str, Arm]
    hashes: dict[str, str]
    cases: list[BenchCase]
    store: RowStore
    L: Loaded
    LI: Loaded
    selection: dict[str, ArmEval] = field(default_factory=dict)
    development: dict[str, ArmEval] = field(default_factory=dict)
    public: dict[str, ArmEval] = field(default_factory=dict)
    latency: dict[str, dict] = field(default_factory=dict)
    stage_latency: dict[str, dict] = field(default_factory=dict)
    ask_commits: dict[str, dict] = field(default_factory=dict)
    decision: decision.Decision | None = None
    row_files: list[dict] = field(default_factory=list)


def row_file_digests(store: RowStore) -> list[dict]:
    out = []
    for arm in store.arms():
        paths = sorted(store.dir.glob(f'{arm}.jsonl*'))
        h = hashlib.sha256()
        n = 0
        for p in paths:
            h.update(p.read_bytes())
        n = len(store.arm_rows(arm))
        out.append({'arm': arm, 'rows': n, 'sha256': h.hexdigest()[:16]})
    return out


def has_rows(L: Loaded, arm: str) -> bool:
    return bool(L.rows.get(arm))


def analyse(store: RowStore | None = None, *, arms: dict[str, Arm] | None = None, cases: list[BenchCase] | None = None,
            arts: dict[str, dict] | None = None, pipelines: tuple[str, ...] = PIPELINES) -> Analysis:
    store = store or RowStore()
    arms = arms or standard_arms()
    hashes = arm_hashes(arms)
    cases = cases if cases is not None else load_all()
    kinds = {n: a.kind for n, a in arms.items()}
    L = report.load(store, cases, hashes, kinds, 'throughput', arts)
    LI = report.load(store, cases, hashes, kinds, 'interactive', arts)
    an = Analysis(arms=arms, hashes=hashes, cases=cases, store=store, L=L, LI=LI, row_files=row_file_digests(store))
    sel = [c for c in cases if c.fold in SELECTION and c.gold]
    dev = [c for c in cases if c.fold in DEVELOPMENT and c.gold]
    pub = [c for c in cases if c.dataset == 'public53']
    for name in pipelines:
        if name not in arms or not has_rows(L, name):
            continue
        an.selection[name] = report.evaluate_arm(L, name, sel)
        if any(cid in {c.id for c in dev} for (cid, _r) in L.rows[name]):        # only arms that were run on the development folds
            an.development[name] = report.evaluate_arm(L, name, dev)
            an.ask_commits[name] = report.ask_commit_stats(L, name, [c for c in cases if c.fold in DEVELOPMENT])
        an.public[name] = report.evaluate_arm(L, name, pub)
        if has_rows(LI, name):
            an.stage_latency[name] = report.stage_latency_summary(LI, name, sel + dev)
            full = report.latency_summary(LI, name, sel + dev)
            if full['n']:
                an.latency[name] = full
    for name in an.selection:
        stages = [an.stage_latency[n]['p95_ms'] for n in chain_of(arms, name)
                  if n in an.stage_latency and an.stage_latency[n]['p95_ms'] is not None]
        if stages:                                         # a single stage already over the limit settles H2 without the rest
            an.latency.setdefault(name, {'n': 0, 'p50_ms': None, 'p95_ms': None, 'max_ms': None})
            an.latency[name]['lower_bound_p95_ms'] = max(stages)
    if an.selection:
        an.decision = decision.decide(an.selection, an.latency, sel,
                                      stages={n: len(chain_of(arms, n)) for n in an.selection})
    return an


def chain_of(arms: dict[str, Arm], name: str) -> list[str]:
    return topo_order(arms, [name])


def part_label(case: BenchCase) -> str:
    return f'Part {case.parts[0]}' if len(case.parts) == 1 else 'mixed'


def top1_by_part(L: Loaded, arm: str, cases: list[BenchCase]) -> dict[str, dict]:
    """Top-1 hit by single Part (and mixed): mean share of repeats with the top pick right, Wilson, and the per-repeat range."""
    reps = report.repeats_of(L, arm)
    rows = L.rows.get(arm, {})
    have = {cid for (cid, _r) in rows}                     # only cases this arm was run on; a case never run is not a miss here
    groups: dict[str, list[BenchCase]] = defaultdict(list)
    for c in cases:
        if c.gold and c.id in have:
            groups[part_label(c)].append(c)
    out = {}
    for label, members in sorted(groups.items()):
        flags = {c.id: [bool(rows.get((c.id, r)) and rows[(c.id, r)]['order'] and rows[(c.id, r)]['order'][0] in c.gold)
                        for r in range(max(reps, 1))] for c in members}
        total = sum(sum(f) / len(f) for f in flags.values())
        per_repeat = [sum(f[r] for f in flags.values()) / len(members) for r in range(max(reps, 1))]
        out[label] = {'cases': len(members), 'rate': report.fractional_rate(total, len(members)),
                      'mean': sum(per_repeat) / len(per_repeat), 'min': min(per_repeat), 'max': max(per_repeat)}
    return out


def mrr_by_repeat(L: Loaded, arm: str, cases: list[BenchCase]) -> list[float]:
    gold = {c.id: list(c.gold) for c in cases if c.gold}
    rows = L.rows.get(arm, {})
    out = []
    for r in range(max(report.repeats_of(L, arm), 1)):
        orders = {c.id: rows[(c.id, r)]['order'] if (c.id, r) in rows else [] for c in cases if c.gold}
        out.append(evaluate(orders, gold, (1,))['mrr'])
    return out


def ledger_reconciliation(L: Loaded, provider_arms: list[str], provider: str, ledger_summary: dict | None) -> dict:
    """Sum of the rows' own-stage dollars against the ledger's settled total for the same provider."""
    rows_usd = 0.0
    n = 0
    for arm in provider_arms:
        for row in L.by_key.get(arm, {}).values():
            if row['profile'] in ('throughput', 'interactive'):
                rows_usd += sum(1 for _ in [0]) and row['usd']
                n += 1
    return {'rows': n, 'rows_usd': rows_usd,
            'ledger_settled_usd': float(ledger_summary['settled_usd']) if ledger_summary else None}
