"""Set-recall metrics for code identification, label metrics, and honest threshold guarantees.

The failure that matters is a governing article the applicant never sees, so the headline metric
is per-case COMPLETE recall: every gold article of the case was surfaced. Article-level (micro)
recall, list sizes and precision against gold+context are reported beside it. Precision is a
lower bound: some sources cite only the varied article, not every related one.

Thresholds come from split conformal prediction at the case level: with n calibration cases and
per-case score m_i = the LOWEST score any of its gold articles received (absent = -inf), the
threshold tau = the k-th smallest m_i, k = floor(alpha * (n + 1)), gives
P(every gold article of a new exchangeable case scores >= tau) >= 1 - alpha.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

LABELS = ('applies', 'check', 'unlikely')


def first_rank(ranked: Sequence[str], article: str) -> int | None:
    try:
        return ranked.index(article) + 1
    except ValueError:
        return None


def recall_at(ranked: Sequence[str], gold: Iterable[str], k: int | None = None) -> float:
    gold = set(gold)
    if not gold:
        return 1.0
    top = set(ranked if k is None else ranked[:k])
    return len(gold & top) / len(gold)


def complete_at(ranked: Sequence[str], gold: Iterable[str], k: int | None = None) -> bool:
    return recall_at(ranked, gold, k) == 1.0


def reciprocal_rank(ranked: Sequence[str], gold: Iterable[str]) -> float:
    ranks = [r for r in (first_rank(ranked, g) for g in gold) if r]
    return 1 / min(ranks) if ranks else 0.0


def rank_needed(ranked: Sequence[str], gold: Iterable[str]) -> int | None:
    """List length needed for complete recall (None if some gold article is absent)."""
    ranks = [first_rank(ranked, g) for g in gold]
    return None if not ranks or any(r is None for r in ranks) else max(ranks)


def ranking_summary(rows: Sequence[tuple[Sequence[str], Iterable[str]]], ks=(1, 3, 5, 10, 20, 30, 40, 60, 100)) -> dict:
    """rows: (ranked ids, gold ids) per case. Complete-recall rate and micro recall at each k."""
    rows = [(list(r), set(g)) for r, g in rows]
    rows = [(r, g) for r, g in rows if g]
    n = len(rows)
    gold_total = sum(len(g) for _, g in rows)
    out = {'cases': n, 'gold_articles': gold_total,
           'mrr': round(sum(reciprocal_rank(r, g) for r, g in rows) / n, 4) if n else None}
    for k in ks:
        out[f'complete@{k}'] = round(sum(complete_at(r, g, k) for r, g in rows) / n, 4) if n else None
        out[f'recall@{k}'] = round(sum(len(g & set(r[:k])) for r, g in rows) / gold_total, 4) if gold_total else None
    out['complete@all'] = round(sum(complete_at(r, g) for r, g in rows) / n, 4) if n else None
    out['recall@all'] = round(sum(len(g & set(r)) for r, g in rows) / gold_total, 4) if gold_total else None
    sizes = [len(r) for r, _ in rows]
    out['mean_list'] = round(sum(sizes) / n, 1) if n else None
    return out


@dataclass
class LabelOutcome:
    gold: int
    applies_hits: int
    surfaced_hits: int          # applies or check
    complete_applies: bool
    complete_surfaced: bool
    applies: int
    check: int
    applies_ok: int             # applies that are gold or context
    failed: bool = False


def label_outcome(labels: Mapping[str, str], gold: Iterable[str], context: Iterable[str] = (), *,
                  failed: bool = False) -> LabelOutcome:
    gold = set(gold)
    ok = gold | set(context)
    labels = {} if failed else labels
    applies = {a for a, l in labels.items() if l == 'applies'}
    check = {a for a, l in labels.items() if l == 'check'}
    return LabelOutcome(gold=len(gold), applies_hits=len(gold & applies), surfaced_hits=len(gold & (applies | check)),
                        complete_applies=gold <= applies, complete_surfaced=gold <= (applies | check),
                        applies=len(applies), check=len(check), applies_ok=len(applies & ok), failed=failed)


def label_summary(outcomes: Sequence[LabelOutcome], *, scope: str = 'gold_preservation_given_pool',
                  attempt_counts: bool = False) -> dict:
    """Label preservation is conditional on the supplied pool unless retrieval is measured too.

    verify_arm injects known gold into diagnostic pools. Its scores are not pipeline recall.
    End-to-end callers must include retrieval misses and failed attempts explicitly. Only callers
    with attempt status should opt into attempt_counts; labels alone cannot establish that status.
    """
    outcomes = [o for o in outcomes if o.gold]
    n = len(outcomes)
    gold = sum(o.gold for o in outcomes)
    applies = sum(o.applies for o in outcomes)
    misses = sum(not o.complete_surfaced for o in outcomes)
    return {
        'cases': n, 'gold_articles': gold, 'metric_scope': scope,
        **({'attempted': n, 'completed': sum(not o.failed for o in outcomes),
            'errors': sum(o.failed for o in outcomes)} if attempt_counts else {}),
        'complete_surfaced': round(sum(o.complete_surfaced for o in outcomes) / n, 4) if n else None,
        'complete_surfaced_upper_miss_95': round(miss_upper_bound(misses, n), 4) if n else None,
        'complete_applies': round(sum(o.complete_applies for o in outcomes) / n, 4) if n else None,
        'recall_surfaced': round(sum(o.surfaced_hits for o in outcomes) / gold, 4) if gold else None,
        'recall_applies': round(sum(o.applies_hits for o in outcomes) / gold, 4) if gold else None,
        'applies_precision_lb': round(sum(o.applies_ok for o in outcomes) / applies, 4) if applies else None,
        'mean_applies': round(applies / n, 2) if n else None,
        'mean_check': round(sum(o.check for o in outcomes) / n, 2) if n else None,
    }


def binom_cdf(x: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(x + 1))


def miss_upper_bound(misses: int, n: int, confidence: float = 0.95) -> float:
    """One-sided Clopper-Pearson upper bound on the true miss rate (0 misses: 1 - (1-c)^(1/n))."""
    if n == 0:
        return 1.0
    if misses >= n:
        return 1.0
    delta = 1 - confidence
    lo, hi = misses / n, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if binom_cdf(misses, n, mid) > delta:
            lo = mid
        else:
            hi = mid
    return hi


def conformal_threshold(case_min_scores: Sequence[float], alpha: float) -> float:
    """Case-level split-conformal threshold: P(all gold of a new case >= tau) >= 1 - alpha.

    case_min_scores: per calibration case, the lowest score of its gold articles (-inf if a gold
    article was never scored/surfaced). Returns -inf when n is too small to certify alpha, which
    means "surface everything" is the only certified rule.
    """
    scores = sorted(case_min_scores)
    n = len(scores)
    k = math.floor(alpha * (n + 1))
    if k < 1:
        return -math.inf
    return scores[k - 1]


def smallest_certifiable_alpha(n: int) -> float:
    """The smallest alpha a case-level conformal threshold can certify with n calibration cases."""
    return 1 / (n + 1)
