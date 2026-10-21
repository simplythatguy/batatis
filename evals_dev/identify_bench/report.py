"""Metrics from stored rows. Every function is pure: rows and datasets in, numbers out.

Success rate (SR) is what the product shows the applicant on a case that has gold articles:

* a Part 9 case succeeds when the first presented article is a gold article (the committed pick, or the first quoted
  choice when nothing is committed);
* any other case, mixed ones included, succeeds when a gold article is among the three quoted choices.

A case's outcome across repeats is the strict majority (more than half of the repeats succeed); the mean of the per-repeat
success rates and its range are reported next to it. A missing or failed row is a miss, never skipped.

A pipeline is the chain of arms ending at an arm. Its cost is the sum of the chain's dollars (fusion branches add); its
latency is the sum of the chain's stage times (fusion branches run in parallel, so the slowest counts), measured only on
rows of the ``interactive`` profile that are not cached.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from statistics import mean

from evals_dev.metrics import evaluate, rate, reciprocal_rank
from evals_dev.metrics.ranking import first_gold_rank

from .datasets import BenchCase
from .rows import RowStore

STAGE_KEYS = ('rank', 'screen', 'rerank', 'verify')
GROUPS = ('part9', 'other', 'mixed')
PLACEHOLDER_THRESHOLD = 0.75         # the unfitted commit threshold in engine/cli_sut.py; used for exploration only
MAX_COMMITS = 3
COMMIT_PART = 9
KS = (1, 3, 5, 10, 15, 20, 40, 50, 60, 100, 200)


def success(case: BenchCase, order: list[str]) -> bool:
    """The product's success definition for one presented ranking."""
    if not case.gold:
        return False
    slots = 1 if case.part_group == 'part9' else 3
    return bool(set(order[:slots]) & set(case.gold))


def majority(flags: list[bool]) -> bool:
    return len(flags) > 0 and sum(flags) * 2 > len(flags)


@dataclass
class Loaded:
    """Rows of one profile for the cases of interest, plus every row by key for following chains."""
    cases: dict[str, BenchCase]
    rows: dict[str, dict[tuple[str, int], dict]]
    by_key: dict[str, dict[str, dict]] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    kinds: dict[str, str] = field(default_factory=dict)
    arts: dict[str, dict] | None = None


def load(store: RowStore, cases: Iterable[BenchCase], hashes: dict[str, str], kinds: dict[str, str] | None = None,
         profile: str = 'throughput', arts: dict[str, dict] | None = None) -> Loaded:
    cases = {c.id: c for c in cases}
    rows, by_key = {}, {}
    for arm, chash in hashes.items():
        latest = store.latest(arm, chash, profile)
        rows[arm] = {k: r for k, r in latest.items() if k[0] in cases}
        by_key[arm] = store.by_key(arm)
    return Loaded(cases=cases, rows=rows, by_key=by_key, hashes=hashes, kinds=kinds or {}, arts=arts)


def repeats_of(L: Loaded, arm: str) -> int:
    reps = {r for (_c, r) in L.rows.get(arm, {})}
    return (max(reps) + 1) if reps else 0


# ---- chains: cost and latency ---------------------------------------------------------------------------------

def chain(L: Loaded, row: dict) -> list[dict]:
    """The row and every upstream row it consumed."""
    out = [row]
    for arm, key in row['upstream'].items():
        up = L.by_key.get(arm, {}).get(key)
        if up is not None:
            out.extend(chain(L, up))
    return out


def stage_ms(row: dict) -> float:
    return sum(v for k, v in row['latency_ms'].items() if k in STAGE_KEYS)


def chain_usd(L: Loaded, row: dict) -> float:
    return sum(r['usd'] for r in chain(L, row))


def chain_tokens(L: Loaded, row: dict) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in chain(L, row):
        for provider, t in r['tokens'].items():
            for k, v in t.items():
                out[provider][k] += v
    return {p: dict(v) for p, v in out.items()}


def chain_latency_ms(L: Loaded, row: dict) -> float | None:
    """Sequential stages add; parallel fusion branches count once, by the slowest. None if any row is cached or errored."""
    if row['cached'] or row['source'] != 'live' or row['errors'] or row['profile'] != 'interactive':
        return None
    own = stage_ms(row)
    ups = []
    for arm, key in row['upstream'].items():
        up = L.by_key.get(arm, {}).get(key)
        if up is None:
            return None
        v = chain_latency_ms(L, up)
        if v is None:
            return None
        ups.append(v)
    if not ups:
        return own
    return own + (max(ups) if row['notes'].get('parallel_upstream') else sum(ups))


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] * (1 - (pos - lo)) + s[hi] * (pos - lo)


# ---- one arm / pipeline evaluated on a set of cases ------------------------------------------------------------

@dataclass
class ArmEval:
    arm: str
    n_cases: int
    repeats: int
    missing_rows: int
    outcome: dict[str, bool]                      # case id -> majority success
    by_repeat_sr: list[float]
    sr: dict
    sr_by_group: dict[str, dict]
    ranking: dict[str, dict]
    top1_agreement: float | None
    majority_top1_hit: dict
    errors: dict
    cost: dict
    verifier: dict
    commits: dict


def _per_repeat_orders(L: Loaded, arm: str, cases: list[BenchCase], repeat: int) -> dict[str, list[str]]:
    rows = L.rows.get(arm, {})
    return {c.id: (rows[(c.id, repeat)]['order'] if (c.id, repeat) in rows else []) for c in cases}


def evaluate_arm(L: Loaded, arm: str, cases: Iterable[BenchCase], *, threshold: float = PLACEHOLDER_THRESHOLD) -> ArmEval:
    cases = [c for c in cases if c.gold]
    reps = repeats_of(L, arm)
    rows = L.rows.get(arm, {})
    flags: dict[str, list[bool]] = {c.id: [] for c in cases}
    per_repeat: list[dict[str, bool]] = []
    for r in range(max(reps, 1)):
        orders = _per_repeat_orders(L, arm, cases, r)
        per_repeat.append({c.id: success(c, orders[c.id]) for c in cases})
        for c in cases:
            flags[c.id].append(per_repeat[-1][c.id])
    outcome = {cid: majority(f) for cid, f in flags.items()}
    n = len(cases)
    sr = rate(sum(outcome.values()), n)
    groups = {}
    for g in GROUPS:
        members = [c for c in cases if c.part_group == g]
        if members:
            groups[g] = rate(sum(outcome[c.id] for c in members), len(members))
    gold = {c.id: list(c.gold) for c in cases}
    metrics_by_repeat = [evaluate(_per_repeat_orders(L, arm, cases, r), gold, KS) for r in range(max(reps, 1))]
    ranking = {}
    for key in metrics_by_repeat[0]:
        if key == 'n':
            continue
        vals = [m[key] for m in metrics_by_repeat]
        ranking[key] = {'mean': mean(vals), 'min': min(vals), 'max': max(vals)}
    agree, majority_hits = [], []
    for c in cases:
        tops = [rows[(c.id, r)]['order'][0] for r in range(reps) if (c.id, r) in rows and rows[(c.id, r)]['order']]
        if len(tops) >= 2:
            pairs = [(a, b) for i, a in enumerate(tops) for b in tops[i + 1:]]
            agree.append(sum(a == b for a, b in pairs) / len(pairs))
        if tops:
            winner = Counter(tops).most_common(1)[0][0]
            majority_hits.append(winner in c.gold)
    all_rows = [rows[(c.id, r)] for c in cases for r in range(reps) if (c.id, r) in rows]
    cats = Counter(e['category'] for row in all_rows for e in row['errors'])
    errors = {'rows': len(all_rows), 'rows_with_errors': sum(1 for row in all_rows if row['errors']),
              'rows_degraded': sum(1 for row in all_rows if row['notes'].get('degraded')),
              'categories': dict(sorted(cats.items())),
              'request_count_mismatch': sum(1 for row in all_rows if row['notes'].get('request_count_ok') is False)}
    usd = [chain_usd(L, row) for row in all_rows]
    toks = [chain_tokens(L, row) for row in all_rows]
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t in toks:
        for p, d in t.items():
            for k, v in d.items():
                totals[p][k] += v
    own_usd = [row['usd'] for row in all_rows]
    cost = {'usd_per_case_run': mean(usd) if usd else None, 'own_stage_usd_per_case_run': mean(own_usd) if own_usd else None,
            'usd_total': sum(usd), 'tokens_total': {p: dict(v) for p, v in totals.items()},
            'usd_per_correct_top1': None}
    top1 = ranking.get('hit@1', {}).get('mean')
    if usd and top1:
        cost['usd_per_correct_top1'] = mean(usd) / top1
    return ArmEval(arm=arm, n_cases=n, repeats=reps, missing_rows=n * max(reps, 1) - len(all_rows), outcome=outcome,
                   by_repeat_sr=[sum(p.values()) / n if n else 0.0 for p in per_repeat], sr=sr, sr_by_group=groups,
                   ranking=ranking, top1_agreement=mean(agree) if agree else None,
                   majority_top1_hit=rate(sum(majority_hits), len(majority_hits)),
                   errors=errors, cost=cost, verifier=verifier_integrity(L, all_rows),
                   commits=commit_stats(L, arm, cases, threshold=threshold))


# ---- verifier integrity --------------------------------------------------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def verifier_integrity(L: Loaded, rows: list[dict]) -> dict:
    """Picks made, picks dropped, quote-match rate before filtering, and a recheck that no shown pick is fabricated."""
    with_notes = [r for r in rows if 'raw_picks' in r['notes']]
    if not with_notes:
        return {}
    raw = sum(r['notes']['raw_picks'] for r in with_notes)
    kept = sum(r['notes']['kept'] for r in with_notes)
    dropped = sum(r['notes']['dropped'] for r in with_notes)
    reasons = Counter(d['why'] for r in with_notes for d in r['dropped'])
    out = {'rows': len(with_notes), 'raw_picks': raw, 'kept': kept, 'dropped': dropped,
           'dropped_by_reason': dict(sorted(reasons.items())),
           'quote_match_rate_before_filtering': (kept / (kept + dropped)) if kept + dropped else None,
           'empty_picks_rows': sum(1 for r in with_notes if r['notes'].get('empty_picks')),
           'fabricated_citations_shown': None}
    if L.arts is not None:
        from engine.identify.corpus import card
        bad = 0
        for r in with_notes:
            for p in r['picks']:
                art = L.arts.get(p['article'])
                if art is None or not _norm(p['quote']) or _norm(p['quote']) not in _norm(card(art, None)):
                    bad += 1
            bad += sum(1 for a in r['order'][:10] if a not in L.arts)
        out['fabricated_citations_shown'] = bad
    return out


# ---- the commit policy, explored (never fitted here) ------------------------------------------------------------

def committed(row: dict, *, threshold: float, need_pick: bool, max_commits: int = MAX_COMMITS,
              part: int = COMMIT_PART) -> list[str]:
    """Articles the placeholder policy would commit: Part 9, probability at least the threshold, and (when a verifier ran)
    picked by it, at most ``max_commits``. The threshold here is the unfitted placeholder, for exploration only."""
    picked = {p['article'] for p in row['picks']}
    out = []
    for a in row['order'][:10]:
        prob = row['probabilities'].get(a)
        if len(out) >= max_commits:
            break
        if a.split('.')[0] == str(part) and prob is not None and prob >= threshold and (not need_pick or a in picked):
            out.append(a)
    return out


def commit_stats(L: Loaded, arm: str, cases: list[BenchCase], *, threshold: float) -> dict:
    need_pick = L.kinds.get(arm) == 'verify'
    rows = L.rows.get(arm, {})
    picks = right = 0
    wrong_cases: list[str] = []
    committing = n_cases = 0
    part9 = [c for c in cases if c.part_group == 'part9']
    for c in part9:
        for r in range(repeats_of(L, arm)):
            row = rows.get((c.id, r))
            if row is None:
                continue
            n_cases += 1
            got = committed(row, threshold=threshold, need_pick=need_pick)
            committing += bool(got)
            for a in got:
                picks += 1
                if a in c.gold:
                    right += 1
                else:
                    wrong_cases.append(f'{c.id}#r{r}:{a}')
    return {'threshold': threshold, 'status': 'placeholder_uncalibrated: exploration only, not a fit',
            'precision': rate(right, picks), 'case_runs': n_cases,
            'coverage': rate(committing, n_cases), 'wrong_commits': wrong_cases}


def reliability(L: Loaded, arm: str, cases: list[BenchCase]) -> list[dict]:
    """Precision of the top-ranked Part 9 article by probability bin (rerank probability, pooled over repeats)."""
    bins = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    rows = L.rows.get(arm, {})
    tally = {b: [0, 0] for b in bins}
    for c in cases:
        if c.part_group != 'part9':
            continue
        for r in range(repeats_of(L, arm)):
            row = rows.get((c.id, r))
            if not row or not row['order']:
                continue
            top = row['order'][0]
            p = row['probabilities'].get(top)
            if p is None:
                continue
            for b in bins:
                if b[0] <= p < b[1]:
                    tally[b][1] += 1
                    tally[b][0] += top in c.gold
    return [{'bin': f'{lo:.1f}-{min(hi, 1.0):.1f}', **rate(x, n)} for (lo, hi), (x, n) in tally.items()]


# ---- latency --------------------------------------------------------------------------------------------------

def latency_summary(L_interactive: Loaded, arm: str, cases: Iterable[BenchCase]) -> dict:
    """p50, p95 and max end-to-end milliseconds of the pipeline ending at ``arm``, on interactive uncached rows.

    Repeat 0 only when the pipeline has several repeats: later repeats of an identical prompt can be served from the
    provider's prompt cache, which no new applicant would get.
    """
    ids = {c.id for c in cases}
    vals, errs = [], 0
    for (cid, rep), row in L_interactive.rows.get(arm, {}).items():
        if cid not in ids:
            continue
        v = chain_latency_ms(L_interactive, row)
        if v is None:
            errs += 1
        else:
            vals.append((rep, v))
    first = [v for rep, v in vals if rep == 0] or [v for _r, v in vals]
    return {'n': len(first), 'unusable_rows': errs, 'p50_ms': percentile(first, 0.5), 'p95_ms': percentile(first, 0.95),
            'max_ms': max(first) if first else None,
            'all_repeats_p50_ms': percentile([v for _r, v in vals], 0.5) if vals else None}


def stage_latency_summary(L_interactive: Loaded, arm: str, cases: Iterable[BenchCase]) -> dict:
    """p50, p95 and max milliseconds of this arm's own stage on interactive, uncached, error-free rows (repeat 0 when several).

    Unlike ``latency_summary`` this needs no upstream interactive rows, so a verifier stage can be timed on its own while the
    screen's credit is unavailable. The end-to-end figure is never inferred from it.
    """
    ids = {c.id for c in cases}
    vals = [(rep, stage_ms(row)) for (cid, rep), row in L_interactive.rows.get(arm, {}).items()
            if cid in ids and row['profile'] == 'interactive' and not row['cached'] and row['source'] == 'live'
            and not row['errors']]
    first = [v for rep, v in vals if rep == 0] or [v for _r, v in vals]
    return {'n': len(first), 'p50_ms': percentile(first, 0.5), 'p95_ms': percentile(first, 0.95),
            'max_ms': max(first) if first else None}
