"""Accuracy for a run: judged F/R/B items plus gold articles, with guardrails, errors, work done and cost.

accuracy = passed / applicable over every F, R, B and A check of the selected cases (micro average).
Guardrails are reported beside it and must all pass; they are not counted in accuracy.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


def summarize(rows: list[dict]) -> dict:
    """rows: one per case, as written by `python -m evals_dev.data_prompts score`."""
    by_kind: dict[str, Counter] = defaultdict(Counter)
    by_tier: dict[str, Counter] = defaultdict(Counter)
    guard: dict[str, Counter] = defaultdict(Counter)
    notes = Counter()
    cost = Counter()
    reviews = Counter(row.get('review_status', 'none') for row in rows)
    failures = Counter(reason for row in rows for reason in row.get('failure_reasons') or [])
    scored_cases = sum(row.get('scored', True) and not row.get('failure_reasons') for row in rows)
    scored_checks = sum(check.get('scored', row.get('scored', True)) for row in rows for check in row['checks'])
    for row in rows:
        for check in row['checks']:
            for bucket in (by_kind[check['kind']], by_tier[row['tier']], by_kind['all']):
                bucket['n'] += 1
                bucket['passed'] += check['passed']
            if check.get('note'):
                notes[check['note']] += 1
        for name, (passed, _) in row['guardrails'].items():
            guard[name]['n'] += 1
            guard[name]['passed'] += passed
        summary = row.get('cost') or {}
        cost['usd'] += summary.get('usd', 0.0)
        cost['live_usd'] += summary.get('live_usd', 0.0)
        cost['calls'] += summary.get('calls', 0)
        cost['judge_usd'] += row.get('judge_usd', 0.0)
        cost['judge_live_usd'] += row.get('judge_live_usd', 0.0)
        cost['unknown_cost_attempts'] += summary.get('unknown_cost_attempts', 0)
        cost['judge_unknown_cost_attempts'] += row.get('judge_unknown_cost_attempts', 0)
        cost['cases_with_unverified_cost'] += summary.get('cost_complete') is False
    rate = lambda c: round(c['passed'] / c['n'], 4) if c['n'] else None   # noqa: E731
    cases = len(rows)
    return {
        'cases': cases,
        'cases_expected': cases, 'cases_scored': scored_cases, 'cases_failed': cases - scored_cases,
        'accuracy': rate(by_kind['all']),
        'checks': by_kind['all']['n'],
        'checks_expected': by_kind['all']['n'], 'checks_scored': scored_checks,
        'checks_failed': by_kind['all']['n'] - by_kind['all']['passed'],
        'checks_unscored': by_kind['all']['n'] - scored_checks,
        'by_kind': {k: {'n': v['n'], 'passed': v['passed'], 'rate': rate(v)} for k, v in sorted(by_kind.items())},
        'by_tier': {k: {'n': v['n'], 'passed': v['passed'], 'rate': rate(v)} for k, v in sorted(by_tier.items())},
        'guardrails': {k: {'n': v['n'], 'passed': v['passed'], 'rate': rate(v)} for k, v in sorted(guard.items())},
        'judge_notes': dict(notes),
        'review_status': dict(reviews),
        'failure_reasons': dict(failures),
        'cases_with_unread_input': sum(bool(row.get('unread_input')) for row in rows),
        'provenance': dict(Counter(row.get('provenance', 'legacy/unverified') for row in rows)),
        'validator_versions': dict(Counter(row.get('validator_version', 'old-validator') for row in rows)),
        'cost': {'workflow_usd_total': round(cost['usd'], 4), 'workflow_usd_per_case': round(cost['usd'] / cases, 5)
                 if cases else None, 'live_usd_this_run': round(cost['live_usd'], 4), 'provider_calls': cost['calls'],
                 'judge_usd_total': round(cost['judge_usd'], 4),
                 'judge_live_usd_total': round(cost['judge_live_usd'], 4),
                 'unknown_cost_attempts': cost['unknown_cost_attempts'],
                 'judge_unknown_cost_attempts': cost['judge_unknown_cost_attempts'],
                 'cases_with_unverified_cost': cost['cases_with_unverified_cost'],
                 'cost_complete': not (cost['unknown_cost_attempts'] or cost['judge_unknown_cost_attempts']
                                       or cost['cases_with_unverified_cost'])},
    }


def table(summary: dict) -> str:
    lines = [f"cases {summary['cases']}  checks {summary['checks']}  accuracy {summary['accuracy']}"]
    if 'cases_expected' in summary:
        lines.append(f"  cases expected {summary['cases_expected']}, scored {summary['cases_scored']}, "
                     f"failed/incomplete {summary['cases_failed']}; checks expected {summary['checks_expected']}, "
                     f"scored {summary['checks_scored']}, failed {summary['checks_failed']}, "
                     f"unscored {summary['checks_unscored']}")
    for k, v in summary['by_kind'].items():
        if k != 'all':
            lines.append(f"  {k}: {v['passed']}/{v['n']} = {v['rate']}")
    for k, v in summary['by_tier'].items():
        lines.append(f"  tier {k}: {v['passed']}/{v['n']} = {v['rate']}")
    for k, v in summary['guardrails'].items():
        lines.append(f"  guardrail {k}: {v['passed']}/{v['n']}")
    lines.append(f"  judge notes {summary['judge_notes']}; review status {summary.get('review_status')}")
    c = summary['cost']
    lines.append(f"  workflow cost ${c['workflow_usd_total']} total, ${c['workflow_usd_per_case']}/case; "
                 f"live this run ${c['live_usd_this_run']}; judge ${c['judge_usd_total']} "
                 f"(fresh ${c.get('judge_live_usd_total', 0.0)})")
    if not c.get('cost_complete', True):
        lines.append(f"  cost incomplete: known USD subtotals only; unknown workflow attempts "
                     f"{c['unknown_cost_attempts']}, judge attempts {c['judge_unknown_cost_attempts']}, "
                     f"cases with unverified cost {c['cases_with_unverified_cost']}")
    lines.append(f"  failures {summary.get('failure_reasons', {})}; provenance {summary.get('provenance', {})}; "
                 f"validator {summary.get('validator_versions', {})}")
    lines.append(f"  cases with unread input {summary.get('cases_with_unread_input', 0)}; "
                 "readability is separate from provider execution success")
    return '\n'.join(lines)


def load_rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for row in rows:
        row.setdefault('validator_version', 'old-validator')
        row.setdefault('provenance', 'legacy/unverified')
    return rows
