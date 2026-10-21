"""Stage 0: reproduce the recorded Jev and BM25 numbers on public53 without any API call.

``docs/research/2026-10-20-vision/jev-benchmark/results`` holds the rankings and every Jev judgment of the 2026-10-20 run
(jev-latest, which resolved to jev-1.13.0). This module turns them into result rows (``source: recorded``, ``cached: true``,
excluded from latency) and checks that the harness's metric code reproduces the published figures:

    BM25                         top-1 32%  top-5 66%  MRR 0.485
    BM25 top 60 -> Jev rerank    top-1 66%  top-5 81%  MRR 0.728
    Jev screens all              top-1 53%  top-5 77%  MRR 0.643
    screen all -> rerank top 60  top-1 64%  top-5 81%  MRR 0.723
"""
from __future__ import annotations

import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from evals_dev.metrics import evaluate

from .datasets import REPO, BenchCase, load_public53
from .rows import RowDraft, config_hash, make_row

RESULTS = REPO / 'docs' / 'research' / '2026-10-20-vision' / 'jev-benchmark' / 'results'
ARMS = ('R0-bm25-rec', 'R4-jev-screen-rec', 'R5-jev-screen-rerank60-rec', 'R6-bm25-jev-rerank60-rec')
QKEY = {'R4-jev-screen-rec': 'govern_exhaustive', 'R5-jev-screen-rerank60-rec': 'govern_stage2_exh60',
        'R6-bm25-jev-rerank60-rec': 'govern_rerank60'}
LABEL = {'R0-bm25-rec': 'BM25', 'R6-bm25-jev-rerank60-rec': 'BM25 top 60 -> Jev rerank',
         'R4-jev-screen-rec': 'Jev screens all', 'R5-jev-screen-rerank60-rec': 'screen all -> rerank top 60'}
# README table: MRR (3 decimals), top-1 and top-5 hit rates (whole percent), recall@10/50/200 (whole percent).
TARGETS = {
    'R0-bm25-rec': {'mrr': 0.485, 'hit@1': 32, 'hit@5': 66, 'recall@10': 65, 'recall@50': 77, 'recall@200': 83},
    'R6-bm25-jev-rerank60-rec': {'mrr': 0.728, 'hit@1': 66, 'hit@5': 81, 'recall@10': 73, 'recall@50': 77, 'recall@200': 83},
    'R4-jev-screen-rec': {'mrr': 0.643, 'hit@1': 53, 'hit@5': 77, 'recall@10': 70, 'recall@50': 88, 'recall@200': 91},
    'R5-jev-screen-rerank60-rec': {'mrr': 0.723, 'hit@1': 64, 'hit@5': 81, 'recall@10': 72, 'recall@50': 88, 'recall@200': 91},
}


def _load(name: str):
    with gzip.open(RESULTS / name, 'rt', encoding='utf-8') as fh:
        return json.load(fh)


def recorded_orders() -> dict[str, dict[str, list[str]]]:
    jev, stage2 = _load('jev_ranked.json.gz'), _load('jev_stage2.json.gz')
    return {'R0-bm25-rec': _load('bm25_ranked.json.gz'), 'R4-jev-screen-rec': jev['exhaustive'],
            'R5-jev-screen-rerank60-rec': stage2['stage2_exh60'], 'R6-bm25-jev-rerank60-rec': jev['rerank60']}


def recorded_probabilities() -> dict[str, dict[str, dict[str, float]]]:
    """arm -> case -> article -> probability, from the judgments file."""
    wanted = {v: k for k, v in QKEY.items()}
    out: dict = {arm: defaultdict(dict) for arm in QKEY}
    with gzip.open(RESULTS / 'jev_judgments.jsonl.gz', 'rt', encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            arm = wanted.get(r['qkey'])
            if arm:
                out[arm][r['case']][r['art']] = r['p']
    return out


def source_sha256() -> str:
    h = hashlib.sha256()
    for name in ('bm25_ranked.json.gz', 'jev_ranked.json.gz', 'jev_stage2.json.gz', 'jev_judgments.jsonl.gz'):
        h.update((RESULTS / name).read_bytes())
    return h.hexdigest()


def arm_config(arm: str) -> dict:
    return {'recorded': arm, 'source': 'jev-benchmark results 2026-10-20 (jev-latest resolved to jev-1.13.0)',
            'source_sha256': source_sha256()}


def stage0_rows(cases: list[BenchCase] | None = None) -> list[dict]:
    cases = cases or load_public53()
    orders, probs = recorded_orders(), recorded_probabilities()
    rows = []
    for arm in ARMS:
        chash = config_hash(arm_config(arm))
        for case in cases:
            order = orders[arm][case.id]
            p = probs.get(arm, {}).get(case.id, {})
            top = sorted(p, key=lambda a: -p[a])[:60]
            draft = RowDraft(order=list(order), probabilities={a: p[a] for a in top}, cached=True, source='recorded',
                             model_ids={'requested': 'jev-latest', 'resolved': 'jev-1.13.0'} if arm != 'R0-bm25-rec' else {},
                             order_keep=None, notes={'recorded_run': '2026-10-20'})
            rows.append(make_row(draft, arm=arm, chash=chash, case=case, repeat=0, attempt=1, profile='recorded',
                                 git_sha=None, codedb_sha256=None, started_at='2026-10-20T00:00:00Z'))
    return rows


def metrics_from_rows(rows: list[dict], cases: list[BenchCase]) -> dict[str, dict]:
    gold = {c.id: list(c.gold) for c in cases}
    by_arm: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for r in rows:
        by_arm[r['arm']][r['case_id']] = r['order']
    return {arm: evaluate(by_arm[arm], gold) for arm in ARMS}


def check(metrics: dict[str, dict]) -> list[str]:
    """Differences from the published figures, as text. Empty means the harness reproduces them."""
    problems = []
    for arm, target in TARGETS.items():
        got = metrics[arm]
        for key, want in target.items():
            value = got[key]
            shown = round(value, 3) if key == 'mrr' else round(value * 100)
            if shown != want:
                problems.append(f'{LABEL[arm]}: {key} is {shown}, published {want}')
    return problems


def run() -> dict:
    cases = load_public53()
    rows = stage0_rows(cases)
    metrics = metrics_from_rows(rows, cases)
    return {'n_cases': len(cases), 'metrics': metrics, 'differences': check(metrics), 'rows': len(rows)}


def recorded_jev_reference() -> dict:
    """Per-case and per-request timing of the 2026-10-20 recorded run (53 cases, 21 requests each, one case at a time, 8 requests in
    flight). Whole seconds only: the log's elapsed counter has that resolution. Context for today's numbers, never a substitute."""
    import re
    pat = re.compile(r'^(\d+)/(\d+) (\S+) done; requests (\d+) tokens (\d+) errors (\d+) elapsed (\d+)s')
    usage = re.compile(r'latency p50/p95 ms ([\d.]+) ([\d.]+)')
    prev, durations, req = 0, [], None
    for line in (RESULTS / 'run_jev.log').read_text().splitlines():
        m = pat.match(line)
        if m:
            durations.append(int(m.group(7)) - prev)
            prev = int(m.group(7))
        u = usage.search(line)
        if u:
            req = (float(u.group(1)), float(u.group(2)))
    durations.sort()
    n = len(durations)
    return {'cases': n, 'per_case_p50_s': durations[n // 2], 'per_case_max_s': durations[-1], 'per_case_mean_s': sum(durations) / n,
            'request_p50_ms': req[0] if req else None, 'request_p95_ms': req[1] if req else None}
