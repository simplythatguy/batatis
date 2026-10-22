"""Typed-fact precision and recall of the intake rules on the 60 development cases.

Gold is `gold.json` next to this file: typed values the case's `known_facts` (or, where marked,
its description) state. A prediction is the latest extracted fact per field. A field that is empty
in both is not counted. Run: python -m evals_dev.intake_facts.score
"""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
CASES = HERE.parent / 'cases'


def load() -> tuple[dict, list[dict]]:
    gold = json.loads((HERE / 'gold.json').read_text())
    cases = [json.loads(path.read_text()) for path in sorted(CASES.glob('dev-*.json'))]
    return gold, cases


def predicted(case: dict, fields: list[str], codes=None) -> dict:
    from engine.intake import service
    out = {}
    for fact in service.run(case['description'], [], codes=codes).facts:
        if fact.field in fields:
            out[fact.field] = fact.value
    return out


def _same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 0.02
    return a == b


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def score(codes=None) -> dict:
    gold, cases = load()
    fields = gold['fields']
    counts = {name: {'tp': 0, 'fp': 0, 'fn': 0, 'fn_known': 0, 'known': 0} for name in fields}
    errors = []
    for case in cases:
        labels = gold['cases'].get(case['id'], {})
        pred = predicted(case, fields, codes)
        for name in fields:
            want, got = labels.get(name), pred.get(name)
            if want is not None and want['from'] == 'known_facts':
                counts[name]['known'] += 1
            if want is None and got is None:
                continue
            if want is not None and got is not None and _same(want['value'], got):
                counts[name]['tp'] += 1
                continue
            if got is not None:
                counts[name]['fp'] += 1
            if want is not None:
                counts[name]['fn'] += 1
                counts[name]['fn_known'] += want['from'] == 'known_facts'
            errors.append((case['id'], name, None if want is None else want['value'], got))
    tp = sum(c['tp'] for c in counts.values())
    fp = sum(c['fp'] for c in counts.values())
    fn = sum(c['fn'] for c in counts.values())
    known = sum(c['known'] for c in counts.values())
    known_hit = known - sum(c['fn_known'] for c in counts.values())
    return {'fields': counts, 'tp': tp, 'fp': fp, 'fn': fn, 'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None, 'known': known, 'known_hit': known_hit,
            'precision_ci': wilson(tp, tp + fp), 'recall_ci': wilson(tp, tp + fn),
            'known_recall_ci': wilson(known_hit, known), 'errors': errors}


def render(result: dict) -> str:
    lines = ['| Field | TP | FP | FN |', '| --- | --- | --- | --- |']
    for name, c in result['fields'].items():
        lines.append(f"| {name} | {c['tp']} | {c['fp']} | {c['fn']} |")
    p, r = result['precision'], result['recall']
    lines += ['', f"Precision {result['tp']}/{result['tp'] + result['fp']} = {p:.3f} "
                  f"(95% Wilson {result['precision_ci'][0]:.3f}-{result['precision_ci'][1]:.3f}).",
              f"Recall {result['tp']}/{result['tp'] + result['fn']} = {r:.3f} "
              f"(95% Wilson {result['recall_ci'][0]:.3f}-{result['recall_ci'][1]:.3f}).",
              f"Recall on labels from known_facts only: {result['known_hit']}/{result['known']} "
              f"(95% Wilson {result['known_recall_ci'][0]:.3f}-{result['known_recall_ci'][1]:.3f}).",
              '', 'Misses and wrong values (case, field, gold, predicted):']
    lines += [f'- {cid} {name}: gold {want!r}, got {got!r}' for cid, name, want, got in result['errors']]
    return '\n'.join(lines)


if __name__ == '__main__':
    print(render(score()))
