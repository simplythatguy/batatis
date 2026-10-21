"""The decision rule from ``benchmark-plan.md`` section 1, applied to stored results.

The unit is a pipeline (the chain ending at an arm). Success rate (SR) is defined in ``report.py``. The rule, written
before any number existed:

1. Compute SR with a 95% interval for every feasible pipeline on the selection folds (public53 and idr26).
2. ``SR_best`` is the highest SR. A pipeline is *tied* with it when its paired difference from the best is not significantly
   negative (exact one-sided sign test on the discordant cases, alpha 0.10) and it trails by at most 3 points. A case is discordant
   when the two pipelines' shares of successful repeats differ; the sign of the difference is what the test counts.
3. Among tied pipelines pick the lowest expected cost per case (API dollars, then p95 latency). Refinement, added on 2026-10-21 after
   the interim rows showed that one stage (the exhaustive screen) is almost the whole cost of every pipeline that has it: costs within
   5 percent (or $0.0002) of the cheapest count as equal, and among those the pipeline with fewer stages wins, then the higher
   success rate, then the lower p95 latency. Without it a difference of $0.0003 in tokens per case would decide the choice. The
   strict lowest-cost pick is reported next to it.
4. Override: if the best pipeline costs more than 3 times a cheaper pipeline that is not significantly worse and trails
   by under 5 points, take the cheaper one.
5. Robustness: the winner needs run-to-run top-1 agreement of at least 0.9 across repeats (or to be deterministic) and
   must not trail the BM25 floor on any Part group; otherwise the next cheapest tied pipeline is tried.
6. Publish the Pareto table.

Hard filters disqualify a pipeline for production but it is still reported: H1 no fabricated citation reaches the screen;
H2 provider errors under 2 percent of rows and, when measured, interactive p95 under 20 seconds; H3 feasibility (key,
metering, redaction); H4 a pinned model version. H3 and H4 are properties of the design, stated in the memo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from evals_dev.metrics import bootstrap_ci, paired_counts_graded, sign_test

from .datasets import BenchCase
from .report import ArmEval

TIE_POINTS = 0.03
TIE_ALPHA = 0.10
OVERRIDE_POINTS = 0.05
OVERRIDE_COST_RATIO = 3.0
COST_BAND = 0.05                  # costs within 5 percent (or COST_BAND_ABS dollars) of the cheapest tied pipeline count as equal
COST_BAND_ABS = 0.0002
ERROR_RATE_MAX = 0.02
P95_MAX_MS = 20_000
AGREEMENT_MIN = 0.9


@dataclass
class Row:
    arm: str
    sr: float
    sr_label: str
    wilson: list[float]
    cluster_ci: list[float] | None
    usd: float | None
    p95_ms: float | None
    only_this: int = 0
    only_best: int = 0
    p_worse: float | None = None
    tied: bool = False
    complete: bool = True
    filters: dict = field(default_factory=dict)
    robust: dict = field(default_factory=dict)
    pareto: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class Decision:
    rows: list[Row]
    best: str | None
    winner: str | None
    trace: list[str]
    provisional: str | None = None     # the cheapest tied pipeline when none passes robustness; flagged, never silent


def hard_filters(e: ArmEval, latency: dict | None) -> dict:
    """True passes, False fails, None means not measured. A None never disqualifies; the memo names it."""
    err = e.errors
    rate = (err['rows_with_errors'] / err['rows']) if err['rows'] else None
    h1 = e.verifier.get('fabricated_citations_shown') if e.verifier else 0
    p95 = (latency or {}).get('p95_ms')
    floor = (latency or {}).get('lower_bound_p95_ms')
    if p95 is not None:
        h2_latency = p95 < P95_MAX_MS
    elif floor is not None and floor >= P95_MAX_MS:        # one stage alone is over the limit, whatever the others take
        h2_latency = False
    else:
        h2_latency = None
    return {
        'H1_no_fabricated_citation': None if h1 is None else h1 == 0,
        'H2_errors_under_2_percent': None if rate is None else rate < ERROR_RATE_MAX,
        'H2_p95_under_20s': h2_latency,
    }


def disqualified(filters: dict) -> bool:
    return any(v is False for v in filters.values())


def pareto_front(points: dict[str, tuple[float, float]]) -> set[str]:
    """Names not dominated in (higher SR, lower cost)."""
    front = set()
    for a, (sr_a, c_a) in points.items():
        dominated = any((sr_b >= sr_a and c_b <= c_a) and (sr_b > sr_a or c_b < c_a)
                        for b, (sr_b, c_b) in points.items() if b != a)
        if not dominated:
            front.add(a)
    return front


def decide(evals: dict[str, ArmEval], latency: dict[str, dict], cases: list[BenchCase], *, floor: str = 'R0-bm25',
           expected_cases: int | None = None, stages: dict[str, int] | None = None) -> Decision:
    gold = [c for c in cases if c.gold]
    n_expected = expected_cases or len(gold)
    trace: list[str] = []
    rows: dict[str, Row] = {}
    families = [c.family for c in gold]
    for name, e in evals.items():
        vals = [float(e.outcome.get(c.id, 0.0)) for c in gold]
        ci = bootstrap_ci(vals, clusters=families, resamples=2000)
        r = Row(arm=name, sr=e.sr['rate'] or 0.0, sr_label=e.sr['label'], wilson=e.sr['wilson_95'] or [0, 0],
                cluster_ci=[ci['low'], ci['high']] if ci['low'] is not None else None,
                usd=e.cost['usd_per_case_run'], p95_ms=(latency.get(name) or {}).get('p95_ms'),
                complete=(e.n_cases == n_expected and e.missing_rows == 0),
                filters=hard_filters(e, latency.get(name)))
        if not r.complete:
            r.notes.append(f'incomplete: {e.n_cases} cases, {e.missing_rows} missing rows')
        if disqualified(r.filters):
            r.notes.append('fails a hard filter: ' + ', '.join(k for k, v in r.filters.items() if v is False))
        rows[name] = r
    feasible = [n for n, r in rows.items() if r.complete and not disqualified(r.filters)]
    if not feasible:
        return Decision(list(rows.values()), None, None, ['no feasible pipeline has complete data'])
    best = max(feasible, key=lambda n: (rows[n].sr, -(rows[n].usd or 0.0)))
    trace.append(f'SR_best = {rows[best].sr:.3f} ({rows[best].sr_label}) by {best}')
    best_outcome = evals[best].outcome
    for n in feasible:
        r = rows[n]
        c = paired_counts_graded(evals[n].outcome, best_outcome)
        r.only_this, r.only_best = c['only_a'], c['only_b']
        r.p_worse = 1.0 if n == best else sign_test(c['only_a'], c['only_b'], 'less')
        r.tied = (r.p_worse >= TIE_ALPHA) and (rows[best].sr - r.sr <= TIE_POINTS + 1e-12)
    tied = [n for n in feasible if rows[n].tied]
    trace.append('tied with the best (not significantly worse at alpha 0.10 and within 3 points): ' + ', '.join(tied))

    def cost_key(n: str):
        return (rows[n].usd if rows[n].usd is not None else float('inf'),
                rows[n].p95_ms if rows[n].p95_ms is not None else float('inf'), n)

    stages = stages or {}
    by_cost = sorted(tied, key=cost_key)
    strict = by_cost[0]
    c0 = rows[strict].usd or 0.0
    limit = max(c0 * (1 + COST_BAND), c0 + COST_BAND_ABS)
    band = [n for n in by_cost if (rows[n].usd or 0.0) <= limit]
    band.sort(key=lambda n: (stages.get(n, 1), -rows[n].sr, rows[n].p95_ms if rows[n].p95_ms is not None else float('inf'), n))
    ranked = band + [n for n in by_cost if n not in band]
    pick = ranked[0]
    trace.append(f'cheapest tied pipeline, strictly: {strict} (${c0:.4f} per case run)')
    if len(band) > 1:
        trace.append('costs within 5 percent of it count as equal (' + ', '.join(f'{n} ${rows[n].usd:.4f}, {stages.get(n, 1)} stages' for n in band)
                     + f'); fewest stages, then highest success rate: {pick}')
    else:
        trace.append(f'taking {pick}')
    # rule 4: a much cheaper pipeline within 5 points that is not significantly worse
    near = [n for n in feasible if n != best and rows[best].sr - rows[n].sr < OVERRIDE_POINTS and rows[n].p_worse >= TIE_ALPHA]
    if near:
        cheapest_near = min(near, key=cost_key)
        if (rows[best].usd or 0) > OVERRIDE_COST_RATIO * (rows[cheapest_near].usd or 0) and cost_key(cheapest_near) < cost_key(pick):
            trace.append(f'override: {best} costs more than {OVERRIDE_COST_RATIO:g}x {cheapest_near} and beats it by under '
                         f'{OVERRIDE_POINTS * 100:g} points; taking {cheapest_near}')
            pick = cheapest_near
            ranked = [pick] + [n for n in ranked if n != pick]
    # rule 5: robustness; try the picks in cost order
    floor_eval = evals.get(floor)
    winner = None
    for n in ranked:
        e = evals[n]
        agree_ok = (e.top1_agreement is None) or e.top1_agreement >= AGREEMENT_MIN
        group_ok, behind = True, []
        if floor_eval is not None:
            for g, rt in e.sr_by_group.items():
                fl = floor_eval.sr_by_group.get(g)
                if fl and (rt['rate'] or 0) < (fl['rate'] or 0):
                    group_ok = False
                    behind.append(g)
        rows[n].robust = {'top1_agreement': e.top1_agreement, 'agreement_ok': agree_ok, 'not_behind_floor_by_group': group_ok,
                          'behind_floor_on': behind, 'vote_of_3_agreement': e.vote_agreement, 'success_agreement': e.success_agreement}
        if agree_ok and group_ok:
            winner = n
            trace.append(f'robustness passed for {n}')
            break
        trace.append(f'robustness failed for {n}: agreement_ok={agree_ok}, behind the BM25 floor on {behind or "none"}')
    provisional = None
    if winner is None:
        provisional = ranked[0]
        trace.append(f'no tied pipeline passed robustness; {provisional} is carried as provisional, not as a winner: the condition it fails is named '
                     'above and the choice needs a person')
    pts = {n: (rows[n].sr, rows[n].usd or 0.0) for n in rows if rows[n].usd is not None and rows[n].complete}
    for n in pareto_front(pts):
        rows[n].pareto = True
    return Decision(sorted(rows.values(), key=lambda r: (-r.sr, r.usd or 0)), best, winner, trace, provisional)
