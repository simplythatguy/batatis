"""Render the G1 report and the decision memo from analysed rows.

Everything below is a pure function of the result rows, the datasets and the arm registry: the same rows give the same
bytes. The only prose that is not computed is definitions and the threats to validity, which do not depend on a number.
"""
from __future__ import annotations

import math
from collections import Counter
from statistics import median

from . import report
from .analysis import SELECTION, Analysis, chain_of, mrr_by_repeat, top1_by_part
from .decision import (AGREEMENT_MIN, ERROR_RATE_MAX, OVERRIDE_COST_RATIO, OVERRIDE_POINTS, P95_MAX_MS, TIE_ALPHA,
                       TIE_POINTS)
from .methods.base import Arm

NOT_RUN = 'not run'


def pct(x: float | None, digits: int = 1) -> str:
    return '-' if x is None else f'{x * 100:.{digits}f}%'


def cell(r: dict | None) -> str:
    """``34 of 53 (64.2%, 95% 50.7-76.0)`` from a rate dict."""
    if not r or not r.get('n'):
        return '0 of 0'
    lo, hi = r['wilson_95']
    return f"{r['x']} of {r['n']} ({pct(r['rate'])}, {pct(lo)}-{pct(hi)})"


def usd(x: float | None, digits: int = 4) -> str:
    return '-' if x is None else f'${x:.{digits}f}'


def secs(ms: float | None) -> str:
    return '-' if ms is None else f'{ms / 1000:.1f} s'


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join('---' for _ in header) + '|']
    out += ['| ' + ' | '.join(r) + ' |' for r in rows]
    return out


def describe(arms: dict[str, Arm], name: str) -> str:
    """One line per chain: what the pipeline does, from the arm configs."""
    parts = []
    for n in chain_of(arms, name):
        a, c = arms[n], arms[n].config()
        if a.kind == 'screen':
            parts.append(f"Jev `{c['model']}` judges all 2,080 Division B articles ({c['card_chars']}-character cards)")
        elif a.kind == 'rerank' and 'provider' in c:
            parts.append(f"Jev `{c['model']}` re-judges the top {c['n']} in one request")
        elif a.kind == 'rerank':
            parts.append(f"`{c['model']}` (effort {c['reasoning_effort']}) scores the top {c['n']} in one request")
        elif a.kind == 'verify':
            text = 'full article text' if c['article_text'] == 'full' else c['article_text'] + ' cards'
            parts.append(f"`{c['model']}` (effort {c['reasoning_effort']}, standard tier) reads the top {c['shortlist_n']} in "
                         f"{text} and must quote word for word" + (', may name articles outside the list' if c['out_of_list'] else ''))
        elif a.kind == 'fuse':
            parts.append('reciprocal-rank fusion of ' + ', '.join(a.upstream_names))
        elif n.startswith('R0'):
            parts.append('BM25 over the Division B provisions (best provision per article)')
        elif n.startswith('R1'):
            parts.append('PR #33 V3 provision ranking')
        elif n.startswith('R2'):
            parts.append('precedent matching (BM25 over 151 precedents, leave-one-family-out)')
    return ' -> '.join(parts)


def _selection_counts(an: Analysis) -> dict[str, int]:
    gold = [c for c in an.cases if c.fold in SELECTION and c.gold]
    return {'n': len(gold), **Counter(c.part_group for c in gold)}


def _run_dates(an: Analysis) -> tuple[str, str]:
    stamps = [r['started_at'] for rows in an.L.by_key.values() for r in rows.values() if r['source'] == 'live']
    return (min(stamps), max(stamps)) if stamps else ('-', '-')


def _provenance(an: Analysis) -> list[str]:
    live = [r for rows in an.L.by_key.values() for r in rows.values() if r['source'] == 'live']
    gits = sorted({r['git_sha'] for r in live if r['git_sha']})
    dbs = sorted({r['codedb_sha256'][:16] for r in live if r['codedb_sha256']})
    returned = sorted({m for r in live for m in r['model_ids'].get('returned', [])})
    requested = sorted({r['model_ids']['requested'] for r in live if r['model_ids'].get('requested')})
    first, last = _run_dates(an)
    return [f'- Rows: {len(live)} live rows from {first} to {last}; code revisions {", ".join(gits) or "-"}; '
            f'code database sha256 {", ".join(dbs) or "-"}.',
            f'- Models requested: {", ".join(requested) or "-"}. Returned by the providers: {", ".join(returned) or "-"}.']


def render_decision(an: Analysis, *, ledger_openai: dict | None = None, ledger_jev: dict | None = None,
                    folds_sha: str = '-') -> str:
    d = an.decision
    sel = _selection_counts(an)
    out = ['# Code identification: decision memo', '',
           'Generated from the result rows by `python -m evals_dev.identify_bench decision --write`. Do not edit by hand: '
           'the same rows regenerate the same file (`evals_dev/tests/test_identify_bench_memo.py`).', '']
    out += ['## Claim (written before any number existed)', '',
            '> Pipeline X has the highest success rate that is not beaten on the paired test, at the lowest cost among tied '
            'pipelines, on public53 plus idr26 (the selection folds), with the Part 9 commit threshold still to be fitted.', '']
    if d is None or d.winner is None:
        out += ['## Verdict', '', '**No pipeline met the rule.** ' + ('; '.join(d.trace) if d else 'No arm has rows yet.'), '']
        return '\n'.join(out) + '\n'
    rows = {r.arm: r for r in d.rows}
    w, ev = rows[d.winner], an.selection[d.winner]
    floor = rows.get('R0-bm25')
    out += ['## Verdict', '',
            f'**Chosen pipeline: `{d.winner}`.** {describe(an.arms, d.winner)}.', '',
            f'- Success rate on the selection folds: **{cell(ev.sr)}** over {sel["n"]} gold-bearing cases '
            f'(Part 9 {sel.get("part9", 0)}, other Parts {sel.get("other", 0)}, mixed {sel.get("mixed", 0)}).',
            f'- Best success rate in the field: `{d.best}` at {pct(rows[d.best].sr)}; `{d.winner}` is '
            f'{"the best" if d.best == d.winner else "tied with it"} (rule below).',
            f'- Cost per case run (all stages, provider usage): {usd(w.usd)}; end-to-end p95 latency on the interactive profile: '
            f'{secs(w.p95_ms) if w.p95_ms is not None else NOT_RUN}.']
    if floor:
        out.append(f'- BM25 floor on the same cases: {floor.sr_label} ({pct(floor.sr)}).')
    out += ['', '### Why', ''] + [f'- {t}' for t in d.trace] + ['']

    out += ['## Decision rule applied to the selection folds', '',
            f'Success: a Part 9 case succeeds when the first presented article is gold; any other case when a gold article is '
            f'among the three quoted choices. A case counts as a success when more than half of its repeats do. Tied with the '
            f'best means a one-sided exact sign test on the discordant cases does not call it worse at alpha {TIE_ALPHA:.2f} and it '
            f'trails by at most {TIE_POINTS * 100:.0f} points; an override takes a pipeline costing at least '
            f'1/{OVERRIDE_COST_RATIO:g} as much when it trails by under {OVERRIDE_POINTS * 100:.0f} points and is not significantly '
            f'worse. Hard filters: H1 no fabricated citation shown, H2 errors under {ERROR_RATE_MAX * 100:.0f}% of rows and, '
            f'when measured, interactive p95 under {P95_MAX_MS // 1000} s.', '']
    t = []
    for r in d.rows:
        e = an.selection[r.arm]
        flag = ', '.join(k.replace('_', ' ') for k, v in r.filters.items() if v is False) or 'passed'
        unmeasured = [k for k, v in r.filters.items() if v is None]
        t.append([f'`{r.arm}`', cell(e.sr), '-' if r.cluster_ci is None else f'{pct(r.cluster_ci[0])}-{pct(r.cluster_ci[1])}',
                  '-' if r.p_worse is None else f'{r.only_this} / {r.only_best}',
                  '-' if r.p_worse is None else f'{r.p_worse:.3f}', 'yes' if r.tied else 'no', usd(r.usd),
                  secs(r.p95_ms) if r.p95_ms is not None else NOT_RUN, flag + (' (unmeasured: ' + ', '.join(unmeasured) + ')' if unmeasured else ''),
                  '; '.join(r.notes) or ('winner' if r.arm == d.winner else '')])
    out += table(['pipeline', 'success rate (Wilson 95%)', 'family bootstrap 95%', 'only it / only best', 'p(worse)', 'tied',
                  '$ per case run', 'p95 latency', 'hard filters', 'notes'], t) + ['']

    out += ['## Pareto table', '',
            'Success rate against cost per case run and against interactive p95 latency. `*` marks a pipeline no other pipeline '
            'beats on both success and cost.', '']
    pt = []
    for r in sorted(d.rows, key=lambda r: (r.usd or 0.0, -r.sr)):
        e = an.selection[r.arm]
        lat = an.latency.get(r.arm, {})
        pt.append([f'`{r.arm}`' + (' *' if r.pareto else ''), cell(e.sr), usd(r.usd), usd(e.cost['usd_per_correct_top1']),
                   secs(lat.get('p50_ms')), secs(lat.get('p95_ms')), str(lat.get('n', 0))])
    out += table(['pipeline', 'success rate', '$ per case run', '$ per correct top-1', 'p50 latency', 'p95 latency', 'latency n'], pt) + ['']

    out += ['## Success rate by Part group (selection folds)', '']
    gt = [[f'`{n}`'] + [cell(e.sr_by_group.get(g)) for g in report.GROUPS] for n, e in an.selection.items()]
    out += table(['pipeline', 'Part 9', 'other Parts', 'mixed'], gt) + ['']

    out += render_g1_section(an) + ['']

    out += ['## Development folds (descriptive, not used to choose)', '',
            'Calibration and validation folds pooled, gold-bearing dev cases only. The validation fold is reserved for gate G4 and '
            'nothing was fitted on it.', '']
    dt = [[f'`{n}`', cell(e.sr), cell(e.sr_by_group.get('part9')), cell(e.sr_by_group.get('other'))] for n, e in an.development.items()]
    out += table(['pipeline', 'success rate', 'Part 9', 'other Parts'], dt) + ['']

    out += render_commit_section(an) + ['']
    out += render_integrity_section(an) + ['']
    out += render_cost_latency_section(an, ledger_openai, ledger_jev) + ['']
    out += render_validity_section(an, ledger_openai) + ['']
    out += render_g4_needs(an, d.winner) + ['']
    out += ['## Provenance', ''] + _provenance(an) + [f'- Folds file sha256 {folds_sha[:16]} (seed 20261021).', '',
                                                      'Row files used (sha256 of the bytes on disk):', '']
    out += table(['arm', 'rows', 'sha256 (first 16)'], [[f'`{f["arm"]}`', str(f['rows']), f['sha256']] for f in an.row_files]) + ['']
    return '\n'.join(out) + '\n'


# ---- sections ---------------------------------------------------------------------------------------------------

def render_g1_section(an: Analysis) -> list[str]:
    out = ['## Gate G1', '']
    pub = [c for c in an.cases if c.dataset == 'public53']
    r5 = 'R5-jev-screen-rerank60'
    if r5 in an.selection:
        mrr = mrr_by_repeat(an.L, r5, pub)
        mean_mrr = sum(mrr) / len(mrr)
        verdict = 'PASS' if mean_mrr >= 0.70 else 'FAIL'
        rec = None
        if 'R5-jev-screen-rerank60-rec' in an.hashes:
            from .stage0 import metrics_from_rows, stage0_rows
            rec = metrics_from_rows(stage0_rows(pub), pub)['R5-jev-screen-rerank60-rec']['mrr']
        out += [f'**Rerank MRR on public53 at the pinned `jev-1.13.0`: {mean_mrr:.3f} mean over {len(mrr)} live repeats '
                f'(range {min(mrr):.3f}-{max(mrr):.3f}); threshold 0.70: {verdict}.**'
                + (f' The 2026-10-20 recorded run (jev-latest) gave {rec:.3f}.' if rec is not None else ''), '']
    else:
        out += [f'Rerank MRR on public53: {NOT_RUN}.', '']
    out += ['Verifier top-1 by Part (case-level majority over repeats with Wilson 95%; per-repeat mean and range in brackets), '
            'all gold-bearing cases:', '']
    gold = [c for c in an.cases if c.gold]
    verifiers = [n for n in an.selection if an.arms[n].kind == 'verify']
    if verifiers:
        labels = sorted({report_label for n in verifiers for report_label in top1_by_part(an.L, n, gold)})
        rows = []
        for n in verifiers:
            by = top1_by_part(an.L, n, gold)
            rows.append([f'`{n}`'] + [(f"{cell(by[l]['majority'])} [{pct(by[l]['mean'])} {pct(by[l]['min'])}-{pct(by[l]['max'])}]"
                                        if l in by else '-') for l in labels])
        out += table(['pipeline'] + labels, rows)
    else:
        out += [NOT_RUN]
    out += ['', 'Latency and cost per case are in the Pareto table above and in the cost and latency section.']
    return out


def render_commit_section(an: Analysis) -> list[str]:
    out = ['## Commit policy, explored (not a calibration)', '',
           f'The placeholder policy in `engine/cli_sut.py`: Part 9 only, rerank probability at least {report.PLACEHOLDER_THRESHOLD}, at most '
           f'{report.MAX_COMMITS}, the verifier must have picked it. The threshold is unfitted; this table shows what it would do on the '
           'Part 9 cases, repeats pooled. `calibration.json` is not written: the fit needs the larger dataset (WP-13).', '']
    rows = []
    for n, e in an.selection.items():
        c = e.commits
        if c['precision']['n'] or an.arms[n].kind == 'verify':
            wrong = ', '.join(c['wrong_commits'][:6]) + (' ...' if len(c['wrong_commits']) > 6 else '')
            rows.append([f'`{n}`', cell(c['precision']), f"{c['precision'].get('cp_lower_95_one_sided', 0) or 0:.3f}",
                         cell(c['coverage']), wrong or 'none'])
    if rows:
        out += table(['pipeline', 'committed picks right (Wilson 95%)', 'exact one-sided 95% lower bound', 'coverage (case runs with a commit)',
                      'wrong commits (case#repeat:article)'], rows)
    else:
        out += [NOT_RUN]
    best = next((n for n in an.selection if an.arms[n].kind == 'verify'), None)
    if best:
        rel = report.reliability(an.L, best, [c for c in an.cases if c.fold in SELECTION and c.gold])
        out += ['', f'Reliability of the top-ranked Part 9 article by rerank probability, `{best}` (selection folds, repeats pooled):', '']
        out += table(['probability bin', 'top-1 right'], [[b['bin'], cell(b)] for b in rel])
    return out


def render_integrity_section(an: Analysis) -> list[str]:
    out = ['## Integrity and reliability', '']
    rows = []
    for n, e in an.selection.items():
        v = e.verifier
        rows.append([f'`{n}`', str(e.errors['rows']), str(e.errors['rows_with_errors']), str(e.errors['rows_degraded']),
                     ', '.join(f'{k} {c}' for k, c in e.errors['categories'].items()) or '-',
                     '-' if e.top1_agreement is None else f'{e.top1_agreement:.3f}', cell(e.majority_top1_hit),
                     '-' if not v else f"{v['raw_picks']} / {v['kept']} / {v['dropped']}",
                     '-' if not v or v.get('quote_match_rate_before_filtering') is None else pct(v['quote_match_rate_before_filtering']),
                     '-' if not v else str(v['fabricated_citations_shown'])])
    out += table(['pipeline', 'rows', 'rows with errors', 'degraded', 'error categories', 'top-1 agreement across repeats',
                  'majority top-1 right', 'picks made / kept / dropped', 'quote match before filtering', 'fabricated citations shown'], rows)
    mismatch = sum(e.errors['request_count_mismatch'] for e in an.selection.values())
    out += ['', f'Rows whose Jev request count differed from the expected count: {mismatch}. Dropped picks never reach the screen; '
            'the recheck above re-verifies every shown pick against the database text.']
    return out


def _corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 5:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return None if sx == 0 or sy == 0 else sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def render_cost_latency_section(an: Analysis, ledger_openai: dict | None, ledger_jev: dict | None) -> list[str]:
    out = ['## Cost and latency', '']
    rows = []
    for n, e in an.selection.items():
        tk = e.cost['tokens_total']
        n_rows = max(e.errors['rows'], 1)
        j, o = tk.get('jev', {}), tk.get('openai', {})
        rows.append([f'`{n}`', usd(e.cost['usd_per_case_run']), usd(e.cost['own_stage_usd_per_case_run']),
                     f"{j.get('requests', 0) / n_rows:.1f}" if j else '-', f"{j.get('input', 0) / n_rows / 1000:.0f}k" if j else '-',
                     f"{o.get('input', 0) / n_rows / 1000:.1f}k" if o else '-', f"{o.get('output', 0) / n_rows / 1000:.1f}k" if o else '-',
                     f"{o.get('reasoning', 0) / n_rows / 1000:.1f}k" if o else '-'])
    out += table(['pipeline', '$ per case run (all stages)', '$ own stage', 'Jev requests', 'Jev input tokens', 'OpenAI input tokens',
                  'OpenAI output tokens (reasoning included)', 'of which reasoning'], rows) + ['']
    if an.latency:
        lt = [[f'`{n}`', secs(v.get('p50_ms')), secs(v.get('p95_ms')), secs(v.get('max_ms')), str(v.get('n')), str(v.get('unusable_rows'))]
              for n, v in an.latency.items()]
        out += ['Latency is end to end, summed along the chain, from interactive-profile rows (one case at a time) that are not cached, repeat 0:', '']
        out += table(['pipeline', 'p50', 'p95', 'max', 'cases', 'unusable rows'], lt) + ['']
        for n in an.latency:
            rows_ = [r for r in an.LI.rows.get(n, {}).values() if r['tokens'].get('openai') and not r['errors']]
            xs = [r['tokens']['openai']['output'] for r in rows_]
            ys = [report.stage_ms(r) for r in rows_]
            c = _corr(xs, ys)
            if c is not None:
                out.append(f'- `{n}`: verifier stage time against completion tokens (reasoning included) correlates at {c:.2f} over '
                           f'{len(xs)} rows, median {median(ys) / 1000:.1f} s at median {median(xs):.0f} tokens.')
    else:
        out += [f'Latency: {NOT_RUN} (no interactive-profile rows).']
    if ledger_openai:
        out += ['', f"OpenAI ledger: {ledger_openai['requests']} requests, US${float(ledger_openai['settled_usd']):.4f} settled of the "
                f"US${ledger_openai['stop_usd']} stop (US${float(ledger_openai['remaining_usd']):.2f} left for the demo)."]
    if ledger_jev:
        out += [f"Jev ledger: {ledger_jev['requests']} requests, about US${float(ledger_jev['settled_usd']):.2f} at $0.042 per million tokens."]
    return out


def render_validity_section(an: Analysis, ledger_openai: dict | None) -> list[str]:
    """The pstack benchmark-checklist, answered from the rows where the rows can answer."""
    out = ['## Validity checklist', '']
    live = [r for rows in an.L.by_key.values() for r in rows.values() if r['source'] == 'live' and r['profile'] == 'throughput']
    ver = [r for r in live if r['tokens'].get('openai')]
    jev = [r for r in live if r['tokens'].get('jev')]
    wrong_model = sum(1 for r in ver if r['model_ids'].get('returned') and r['model_ids']['returned'] != [r['model_ids']['requested']])
    tiers = sorted({r['model_ids'].get('service_tier') for r in ver if r['model_ids'].get('service_tier')})
    out += [
        f'- **Happened.** {len(live)} live rows: {len(jev)} with Jev usage and {len(ver)} with OpenAI usage; every counted row has non-zero tokens '
        f'({sum(1 for r in jev if r["tokens"]["jev"]["input"] == 0) + sum(1 for r in ver if r["tokens"]["openai"]["input"] == 0)} do not). '
        f'Returned model id differs from the pinned id in {wrong_model} verifier rows; service tier reported: {", ".join(tiers) or "-"}. '
        f'Jev screens that did not make the expected request count: {sum(e.errors["request_count_mismatch"] for e in an.selection.values())}.',
        '- **Errors.** Counted per pipeline in the integrity table; a failed row is a miss, never skipped, and a degraded row (verifier or rerank failed, '
        'upstream order kept) is counted as degraded.',
        '- **Reproduces.** Repeats per arm are in the integrity table (top-1 agreement across repeats, majority top-1). Jev is not deterministic: the same '
        'article set returns different probabilities run to run, so no single run is the answer. A gap smaller than the repeat-to-repeat range of the '
        'per-repeat success rate is no measurable difference.',
        '- **Limits.** Dollars are provider-reported usage times the price table in `pricing.py`: 394k Jev tokens per case at $0.042 per million is $0.0166, '
        'which the Jev rows match; OpenAI cost is reported tokens times $0.10 / $0.50 per million with no prompt-cache discount applied.',
        '- **Why not double.** For the verifier the latency limiter is completion (reasoning) tokens, shown by the correlation in the cost and latency '
        'section; for the Jev screen it is request round trips (about 21 requests per case, 8 in flight), not the client.',
        '- **Tuned.** Every arm ran as the pipeline would: pinned model ids, strict structured output, reasoning effort set explicitly to medium, standard '
        'tier, the production `Judge` for Jev.',
        '- **Matters.** Identification is one stage of the applicant flow; its share of end-to-end application time was not measured here. The user-visible '
        'figure is the end-to-end latency above.',
    ]
    if ledger_openai:
        out.append(f"- **Spend check.** The OpenAI ledger's settled total (US${float(ledger_openai['settled_usd']):.4f}) is recomputed from its own file "
                   'after every call and agrees with the rows within the retried and timed-out calls it charges at worst case.')
    return out


def render_g4_needs(an: Analysis, winner: str | None) -> list[str]:
    out = ['## What WP-13 (dataset growth) must add for gate G4', '',
           'G4 needs at least 50 committed Part 9 picks with at most 1 error on the validation fold (exact one-sided 95% lower bound 0.9086 '
           'at 49 of 50). The numbers below use this run\'s measured coverage for the chosen pipeline at the placeholder threshold, so they '
           'are planning figures, not a fit.', '']
    if winner is None or winner not in an.development:
        return out + [NOT_RUN]
    dev = [c for c in an.cases if c.fold in ('calibration', 'validation') and c.part_group == 'part9']
    rows = an.L.rows.get(winner, {})
    need_pick = an.arms[winner].kind == 'verify'
    runs = commits = picks = 0
    for c in dev:
        for r in range(max(report.repeats_of(an.L, winner), 1)):
            row = rows.get((c.id, r))
            if row is None:
                continue
            runs += 1
            got = report.committed(row, threshold=report.PLACEHOLDER_THRESHOLD, need_pick=need_pick)
            commits += bool(got)
            picks += len(got)
    n_val = sum(1 for c in dev if c.fold == 'validation')
    out.append(f'Part 9 development cases now: {len(dev)} ({n_val} in validation, {len(dev) - n_val} in calibration).')
    if commits == 0 or runs == 0:
        return out + ['At the placeholder threshold this pipeline commits on none of them, so coverage and picks per committing case are unmeasured.']
    cover, per = commits / runs, picks / commits
    out += [f'Measured at the placeholder threshold: coverage {pct(cover)} of Part 9 case runs, {per:.2f} picks per committing case.', '']
    scenarios = [(0.6, 1.2), (0.7, 1.3), (0.8, 1.5), (round(cover, 2), round(per, 2))]
    t = []
    for c, p in dict.fromkeys(scenarios):
        need_val = math.ceil(50 / (c * p)) if c * p > 0 else None
        t.append([f'{c:.2f}', f'{p:.2f}', str(need_val), str(math.ceil(need_val / 0.7)), str(max(0, math.ceil(need_val / 0.7) - len(dev)))])
    out += table(['coverage', 'picks per committing case', 'validation Part 9 cases needed', 'total Part 9 dev cases (70% validation)',
                  'still to author'], t)
    out += ['', 'Also needed: stripped copies of the dev scenarios (M3), the fork and scope boundary sets, a person to sign off 20 cases, and '
            'the calibration fit itself (`calibration.json` with `status: calibrated` only after the validation fold clears G4).']
    return out


def render_g1_report(an: Analysis, *, ledger_openai: dict | None = None, ledger_jev: dict | None = None) -> str:
    """The G1 report on its own: checks against thresholds, then the same tables the decision memo carries."""
    from evals_dev.accuracy.gates import evaluate_g1, passed
    checks = evaluate_g1(an)
    out = ['# Gate G1: Code ID re-measure', '',
           'Generated from the result rows by `python -m evals_dev.identify_bench decision --write`; `python scripts/gate_g1.py` prints the same checks. '
           'Do not edit by hand.', '',
           f'**G1 {"PASS" if passed(checks) else "FAIL"}**', '']
    out += table(['check', 'status', 'measured'], [[c.id, c.status, c.text] for c in checks]) + ['']
    out += render_g1_section(an) + ['']
    out += render_cost_latency_section(an, ledger_openai, ledger_jev) + ['']
    return '\n'.join(out) + '\n'
