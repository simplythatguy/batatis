"""Deterministic scoring of one SUT answer against a scenario, and aggregation into the numbers the judge prints.

Definitions follow RUBRIC.md where the SUT contract can supply the evidence:

* required-article recall is scored at article level over the Division B ``must_cite`` entries (a sentence in the
  gold counts as its article); an empty required list is N/A, never 100 percent;
* a SUT failure (timeout, bad JSON, ...) is a trial failure with zero required-item recall and no committed picks;
  it stays in every denominator;
* a committed pick is right if its article is a required citation (strict) or a required or helpful verified citation
  (lenient); a commit on a scenario with no required article is a wrong commit unless it is a helpful citation;
* ``under_flag`` is gold ``yes`` answered ``no``; ``fabricated_citation`` is a Division B article id that is not in the
  code database; ``claims_approval`` is a crude phrase check, a flag for a human, not a finding.

Nothing here prints. ``aggregate`` returns numbers only; groups smaller than ``MIN_CELL`` are suppressed so a
printed block cannot single out one scenario.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from statistics import mean

from evals_dev.metrics import rate as full_rate
from evals_dev.metrics.ranking import article_of

from .dataset import Scenario
from .sut import SutResult

MIN_CELL = 5


def rate(x: int, n: int) -> dict:
    """``x of n`` with the Wilson interval and the exact one-sided lower bound, rounded for printing."""
    r = full_rate(x, n)
    if not n:
        return {'label': r['label']}
    return {'label': r['label'], 'rate': round(r['rate'], 4), 'wilson_95': [round(v, 4) for v in r['wilson_95']],
            'cp_lower_95_one_sided': round(r['cp_lower_95_one_sided'], 4)}


def _round(value):
    return None if value is None else round(value, 4)
_APPROVAL = re.compile(r"\b(?:complies|compliant|in compliance|meets (?:the )?code|(?:is|are|been) approved)\b", re.I)
_NEGATION = re.compile(r"\b(?:not|never|no|cannot|can't|won't|without|nor|neither|unless|until)\b", re.I)


def claims_approval(obj) -> bool:
    """True when a string in the answer (outside ``trace``) says a design complies or is approved, un-negated."""
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for k, v in value.items():
                if k != 'trace':
                    yield from strings(v)
        elif isinstance(value, list):
            for v in value:
                yield from strings(v)

    for text in strings(obj):
        for m in _APPROVAL.finditer(text):
            if not _NEGATION.search(text[max(0, m.start() - 40):m.start()]):
                return True
    return False


def score_scenario(s: Scenario, res: SutResult, known_articles: set[str] | None) -> dict:
    """The private per-scenario record. Never printed; the judge keeps it in its own state folder."""
    ranked: list[str] = []
    committed: list[str] = []
    invalid = 0
    fabricated = 0
    out = res.output or {}
    for a in out.get('articles', []):
        if a.get('division', 'B') != 'B':
            continue
        art = article_of(a['provision'])
        if art is None:
            invalid += 1
            fabricated += 1
            continue
        if known_articles is not None and art not in known_articles:
            fabricated += 1
            continue
        if art not in ranked:
            ranked.append(art)
        if a.get('committed') and art not in committed:
            committed.append(art)
    gold = set(s.must_cite_b)
    helpful = gold | set(s.should_cite_b)
    first = next((i for i, a in enumerate(ranked, start=1) if a in gold), None)
    rec = {
        'id': s.id, 'split': s.split, 'confidence': s.confidence, 'part_group': s.part_group,
        'category': res.category, 'seconds': res.seconds,
        'has_gold': bool(gold), 'hit1': bool(gold & set(ranked[:1])), 'hit3': bool(gold & set(ranked[:3])),
        'hit5': bool(gold & set(ranked[:5])),
        'recall5': (len(gold & set(ranked[:5])) / len(gold)) if gold else None,
        'rr': (1.0 / first) if first else 0.0,
        'commits': len(committed), 'commits_strict': sum(1 for c in committed if c in gold),
        'commits_lenient': sum(1 for c in committed if c in helpful),
        'forbidden_commit': bool(set(committed) & set(s.forbidden_b)),
        'fabricated': fabricated, 'claims_approval': claims_approval(out) if out else False,
        'intake_gold': s.intake_action, 'intake_got': out.get('intake_action'),
        'eng_gold': s.engineering_required, 'eng_got': out.get('engineering_required'),
        'ranked_top5': ranked[:5], 'committed': committed,
    }
    return rec


def _group(records: list[dict]) -> dict:
    gold = [r for r in records if r['has_gold']]
    commits = sum(r['commits'] for r in records)
    return {
        'scenarios': len(records),
        'm2_required_article_in_top5': rate(sum(r['hit5'] for r in gold), len(gold)),
        'hit_at_1': rate(sum(r['hit1'] for r in gold), len(gold)),
        'hit_at_3': rate(sum(r['hit3'] for r in gold), len(gold)),
        'recall_at_5_macro': _round(mean(r['recall5'] for r in gold)) if gold else None,
        'mrr': _round(mean(r['rr'] for r in gold)) if gold else None,
        'committed_picks': commits,
        'committed_precision_required_only': rate(sum(r['commits_strict'] for r in records), commits),
        'committed_precision_required_or_helpful': rate(sum(r['commits_lenient'] for r in records), commits),
    }


def aggregate(records: list[dict]) -> dict:
    """Aggregate numbers for one set of per-scenario records."""
    n = len(records)
    block = _group(records)
    block['commits_on_scenarios_without_required_article'] = sum(
        r['commits'] for r in records if not r['has_gold'])
    block['forbidden_commit_scenarios'] = sum(r['forbidden_commit'] for r in records)
    redirect_gold = [r for r in records if r['intake_gold'] == 'redirect']
    block['intake_action'] = {
        'agreement': rate(sum(r['intake_got'] == r['intake_gold'] for r in records), n),
        'redirect_recall': rate(sum(r['intake_got'] == 'redirect' for r in redirect_gold), len(redirect_gold)),
        'false_redirects': sum(r['intake_got'] == 'redirect' and r['intake_gold'] != 'redirect' for r in records),
    }
    yes_gold = [r for r in records if r['eng_gold'] == 'yes']
    block['engineering_required'] = {
        'agreement': rate(sum(r['eng_got'] == r['eng_gold'] for r in records), n),
        'under_flag': rate(sum(r['eng_got'] == 'no' for r in yes_gold), len(yes_gold)),
        'over_flag': sum(r['eng_got'] == 'yes' and r['eng_gold'] == 'no' for r in records),
    }
    by_group = {}
    for g in ('part9', 'other', 'mixed'):
        members = [r for r in records if r['part_group'] == g]
        if len(members) >= MIN_CELL:
            sub = _group(members)
            by_group[g] = {k: sub[k] for k in ('scenarios', 'm2_required_article_in_top5', 'hit_at_1',
                                               'committed_picks', 'committed_precision_required_only')}
        elif members:
            by_group[g] = {'suppressed': f'fewer than {MIN_CELL} scenarios'}
    block['by_part_group'] = by_group
    return block


def error_counts(records: Iterable[dict]) -> dict[str, int]:
    """SUT failure categories plus content-level flags, over every scenario in the run."""
    c: Counter = Counter()
    for r in records:
        if r['category']:
            c[r['category']] += 1
        if r['fabricated']:
            c['fabricated_citation'] += 1
        if r['claims_approval']:
            c['claims_approval'] += 1
        if r['forbidden_commit']:
            c['forbidden_citation_committed'] += 1
    return dict(sorted(c.items()))


def latency(records: Iterable[dict]) -> dict:
    secs = sorted(r['seconds'] for r in records if r['category'] is None)
    if not secs:
        return {'p50': None, 'p95': None, 'max': None}
    return {'p50': round(secs[len(secs) // 2], 2), 'p95': round(secs[min(len(secs) - 1, int(0.95 * len(secs)))], 2),
            'max': round(secs[-1], 2)}
