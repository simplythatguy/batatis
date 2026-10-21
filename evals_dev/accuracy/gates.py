"""Gate G1 (Code ID re-measure), computed from result rows. Pure: rows in, a list of checks out.

G1, from ``docs/research/2026-10-20-vision/2-week-build.md``: rerank MRR at least 0.70 on the 53 public cases at the pinned Jev
version; verifier top-1 by Part with intervals over repeats, with latency and cost per case. Every check is PASS, FAIL or
NOT RUN; a gate with any check not PASS does not pass. The user restricted the OpenAI arm to ``gpt-6-luna`` at medium effort,
so "medium and max" becomes medium only, and the check says so.
"""
from __future__ import annotations

from dataclasses import dataclass

from evals_dev.identify_bench.analysis import Analysis, mrr_by_repeat, top1_by_part

MRR_FLOOR = 0.70
MIN_VERIFIER_REPEATS = 5
MIN_LATENCY_CASES = 20
PUBLIC_RERANK = 'R5-jev-screen-rerank60'


@dataclass
class Check:
    id: str
    status: str            # PASS | FAIL | NOT RUN
    text: str


def evaluate_g1(an: Analysis, verifier: str | None = None) -> list[Check]:
    checks: list[Check] = []
    pub = [c for c in an.cases if c.dataset == 'public53']
    if PUBLIC_RERANK in an.selection:
        mrr = mrr_by_repeat(an.L, PUBLIC_RERANK, pub)
        mean = sum(mrr) / len(mrr)
        status = 'PASS' if mean >= MRR_FLOOR else 'FAIL'
        checks.append(Check('G1.1', status, f'rerank MRR on public53 at jev-1.13.0: mean {mean:.3f} over {len(mrr)} live repeats '
                                            f'(lowest {min(mrr):.3f}); threshold {MRR_FLOOR:.2f}'))
    else:
        checks.append(Check('G1.1', 'NOT RUN', 'no live rows for the Jev screen and rerank'))
    verifiers = [n for n in an.selection if an.arms[n].kind == 'verify']
    chosen = (an.decision.winner or an.decision.provisional) if an.decision else None
    target = verifier or (chosen if chosen in verifiers else (verifiers[0] if verifiers else None))
    gold = [c for c in an.cases if c.gold]
    if target is None:
        checks.append(Check('G1.2', 'NOT RUN', 'no verifier rows'))
    else:
        ev = an.selection[target]
        full = len(pub) * ev.repeats
        rows = sum(1 for c in pub for r in range(ev.repeats) if (c.id, r) in an.L.rows.get(target, {}))
        by = top1_by_part(an.L, target, gold)
        parts = ', '.join(f'{k} {v["rate"]["label"]}' for k, v in by.items())
        ok = ev.repeats >= MIN_VERIFIER_REPEATS and rows == full
        checks.append(Check('G1.2', 'PASS' if ok else 'FAIL',
                            f'verifier {target}: top-1 by Part with intervals ({parts}); {ev.repeats} repeats, {rows} of {full} public53 '
                            f'case-repeat rows, reasoning effort medium only (user decision); need at least {MIN_VERIFIER_REPEATS} repeats '
                            f'on every public53 case'))
        cost = ev.cost['usd_per_case_run']
        checks.append(Check('G1.3', 'PASS' if cost is not None else 'NOT RUN',
                            f'{target}: cost ${cost:.4f} per case run (all stages, provider-reported usage)' if cost is not None
                            else f'{target}: no cost recorded'))
        stage = an.stage_latency.get(target)
        if stage and stage['n'] >= MIN_LATENCY_CASES:
            checks.append(Check('G1.4', 'PASS', f'{target}: verifier stage alone, one request at a time: p50 {stage["p50_ms"] / 1000:.1f} s, '
                                                f'p95 {stage["p95_ms"] / 1000:.1f} s over {stage["n"]} cases'))
        else:
            checks.append(Check('G1.4', 'NOT RUN', f'{target}: needs the verifier stage timed one request at a time on at least '
                                                   f'{MIN_LATENCY_CASES} cases (have {stage["n"] if stage else 0})'))
        lat = an.latency.get(target)
        if lat and lat.get('n', 0) >= MIN_LATENCY_CASES:
            checks.append(Check('G1.5', 'PASS' if lat['p95_ms'] < 20_000 else 'FAIL',
                                f'{target}: end-to-end p50 {lat["p50_ms"] / 1000:.1f} s, p95 {lat["p95_ms"] / 1000:.1f} s over {lat["n"]} cases '
                                f'(interactive profile, whole chain); H2 limit 20 s'))
        else:
            checks.append(Check('G1.5', 'NOT RUN', f'{target}: end-to-end latency needs every stage of the chain timed one case at a time on the '
                                                   f'interactive profile on at least {MIN_LATENCY_CASES} cases'))
        fab = ev.verifier.get('fabricated_citations_shown')
        checks.append(Check('G1.6', 'NOT RUN' if fab is None else ('PASS' if fab == 0 else 'FAIL'),
                            f'{target}: fabricated citations shown: {fab if fab is not None else "not rechecked"} (quote and database check)'))
    return checks


def passed(checks: list[Check]) -> bool:
    return bool(checks) and all(c.status == 'PASS' for c in checks)


# ---- Gate G4: committed Part 9 picks on the validation fold ---------------------------------------------------------

G4_MIN_PICKS = 50
G4_MAX_ERRORS = 1
SWEEP = [round(0.50 + 0.05 * i, 2) for i in range(10)]


def sweep_calibration(an: Analysis, pipeline: str) -> list[dict]:
    """Committed Part 9 picks and errors at each threshold 0.50-0.95 on the calibration fold. Information only: the fit rule
    and the calibration file belong to the threshold-fitting step, which needs the larger dataset (WP-13)."""
    from evals_dev.identify_bench import report
    from evals_dev.metrics import rate
    cases = [c for c in an.cases if c.fold == 'calibration' and c.part_group == 'part9']
    out = []
    for t in SWEEP:
        stats = report.commit_stats(an.L, pipeline, cases, threshold=t)
        out.append({'threshold': t, 'committed': stats['precision']['n'], 'wrong': stats['precision']['n'] - stats['precision']['x'],
                    'cases': len(cases)})
    return out


def evaluate_g4(an: Analysis, pipeline: str | None, calibration: dict | None) -> list[Check]:
    """G4 needs a fitted threshold (``calibration.json``, status calibrated, for this pipeline) and then at least 50 committed picks
    with at most 1 error on the validation fold. Without the file the gate is NOT RUN and says how far the data is."""
    from evals_dev.identify_bench import report
    from evals_dev.metrics import clopper_pearson_lower
    val = [c for c in an.cases if c.fold == 'validation' and c.part_group == 'part9']
    if pipeline is None or pipeline not in an.development:
        return [Check('G4.1', 'NOT RUN', 'no pipeline has development-fold rows')]
    sweep = sweep_calibration(an, pipeline)
    info = (f'{len(val)} Part 9 validation cases and {sweep[0]["cases"]} calibration cases; calibration sweep committed picks '
            f'by threshold: ' + ', '.join(f'{r["threshold"]:.2f}:{r["committed"]}' for r in sweep))
    if not calibration or calibration.get('status') != 'calibrated':
        return [Check('G4.1', 'NOT RUN', 'calibration.json is absent or not calibrated, so no threshold is fixed; ' + info)]
    threshold = float(calibration.get('parts', {}).get('9', {}).get('threshold', 0))
    stats = report.commit_stats(an.L, pipeline, val, threshold=threshold)
    n, wrong = stats['precision']['n'], stats['precision']['n'] - stats['precision']['x']
    lower = clopper_pearson_lower(n - wrong, n) if n else 0.0
    ok = n >= G4_MIN_PICKS and wrong <= G4_MAX_ERRORS
    return [Check('G4.1', 'PASS' if ok else 'FAIL',
                  f'{pipeline} at threshold {threshold:.2f} on the validation fold: {n} committed picks, {wrong} wrong, exact one-sided '
                  f'95% lower bound {lower:.4f}; need at least {G4_MIN_PICKS} picks with at most {G4_MAX_ERRORS} error')]
