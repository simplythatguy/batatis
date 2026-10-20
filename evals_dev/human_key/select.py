"""Deterministic selection of the 15-case human-key subset.

Persona rule (case field ``applicant_type`` only; other applicant types are out of this subset):

- ``manufacturer`` -> manufacturer
- ``contractor`` -> general contractor
- ``homebuilder`` -> homebuilder

Variance kind is the case ``topic`` field. ``gold.intake_action`` is read only to balance
ask / proceed_conditionally / redirect. It is not written into the key.

Seeded shuffle uses an explicit Fisher-Yates over ``random.Random`` so the draw does not
depend on ``random.shuffle`` changing between Python versions.

    python evals_dev/human_key/select.py
    python evals_dev/human_key/select.py --write
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = ROOT.parent / 'cases'
SEED = 20261020

PERSONA_OF = {
    'manufacturer': 'manufacturer',
    'contractor': 'general contractor',
    'homebuilder': 'homebuilder',
}
PERSONAS = ('manufacturer', 'general contractor', 'homebuilder')
# Rarest action first so a redirect is taken before the common proceed bucket fills the quota.
ACTIONS = ('redirect', 'ask', 'proceed_conditionally')
PER_PERSONA = 5

ANSWER_FIELDS = (
    'section_ab_required_fields', 'expected_top_articles', 'benchmark_acceptable_solution',
    'engineer_needed', 'intake_action', 'verifier_name', 'date_verified', 'source_page_refs', 'notes',
)


def persona_of(case: dict) -> str | None:
    return PERSONA_OF.get(case.get('applicant_type'))


def _shuffled(items: list, rng: random.Random) -> list:
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        j = rng.randrange(i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def select_cases(cases: list[dict], seed: int = SEED, per_persona: int = PER_PERSONA) -> list[dict]:
    """Return 5 cases per persona. Order is persona, then case id."""
    rng = random.Random(seed)
    groups = {(p, a): [] for p in PERSONAS for a in ACTIONS}
    for case in sorted(cases, key=lambda c: c['id']):
        persona = persona_of(case)
        action = (case.get('gold') or {}).get('intake_action')
        if persona is None or action not in ACTIONS:
            continue
        groups[(persona, action)].append(case)
    for key in groups:
        groups[key] = _shuffled(groups[key], rng)

    selected: dict[str, list[dict]] = {p: [] for p in PERSONAS}
    for action in ACTIONS:
        for persona in PERSONAS:
            bucket = groups[(persona, action)]
            if bucket and len(selected[persona]) < per_persona:
                selected[persona].append(bucket.pop(0))

    guard = 0
    while any(len(selected[p]) < per_persona for p in PERSONAS):
        guard += 1
        if guard > per_persona * len(PERSONAS):
            raise RuntimeError('selection could not fill the persona quotas')
        topics = {c['topic'] for rows in selected.values() for c in rows}
        for persona in PERSONAS:
            if len(selected[persona]) >= per_persona:
                continue
            pool = [c for action in ACTIONS for c in groups[(persona, action)]]
            if not pool:
                raise RuntimeError(f'not enough {persona} cases')
            pick = next((c for c in pool if c['topic'] not in topics), pool[0])
            selected[persona].append(pick)
            groups[(persona, pick['gold']['intake_action'])].remove(pick)

    ordered: list[dict] = []
    for persona in PERSONAS:
        ordered.extend(sorted(selected[persona], key=lambda c: c['id']))
    _check_coverage(ordered, per_persona)
    return ordered


def _check_coverage(selected: list[dict], per_persona: int) -> None:
    counts = {p: 0 for p in PERSONAS}
    for case in selected:
        counts[persona_of(case)] += 1
    if any(n != per_persona for n in counts.values()):
        raise RuntimeError(f'persona counts {counts}')
    topics = {c['topic'] for c in selected}
    actions = {c['gold']['intake_action'] for c in selected}
    if len(topics) < 3:
        raise RuntimeError(f'need at least 3 variance kinds, got {sorted(topics)}')
    if actions != set(ACTIONS):
        raise RuntimeError(f'need every intake action, got {sorted(actions)}')


def blank_key(case: dict) -> dict:
    """Answer fields are null. The scenario is the case description and nothing from gold."""
    return {
        'case_id': case['id'],
        'status': 'unverified',
        'persona': persona_of(case),
        'variance_kind': case['topic'],
        'scenario': case['description'],
        'section_ab_required_fields': None,
        'expected_top_articles': None,
        'benchmark_acceptable_solution': None,
        'engineer_needed': None,
        'intake_action': None,
        'verifier_name': None,
        'date_verified': None,
        'source_page_refs': None,
        'notes': None,
    }


def load_cases(path: Path = CASES) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(path.glob('dev-*.json'))]


def _untouched(path: Path) -> bool:
    if not path.exists():
        return True
    data = json.loads(path.read_text())
    if data.get('status') != 'unverified':
        return False
    return all(data.get(field) is None for field in ANSWER_FIELDS)


def write_selection(selected: list[dict], dest: Path = ROOT) -> list[str]:
    """Write blank keys and SELECTION.md. Refuse to overwrite a key that has any answer."""
    skipped = []
    for case in selected:
        path = dest / f"{case['id']}.json"
        if not _untouched(path):
            skipped.append(case['id'])
            continue
        path.write_text(json.dumps(blank_key(case), indent=2, ensure_ascii=False) + '\n')
    (dest / 'SELECTION.md').write_text(_markdown(selected))
    return skipped


def _markdown(selected: list[dict]) -> str:
    actions: dict[str, int] = {a: 0 for a in ACTIONS}
    for case in selected:
        actions[case['gold']['intake_action']] += 1
    lines = [
        '# Human-key subset',
        '',
        'The key files next to this note are **unfilled**. Current evals are **model-checked**.',
        'Nothing here is human verification.',
        '',
        f'Seed `{SEED}`. Reproduce with `python evals_dev/human_key/select.py`.',
        '',
        '## Persona rule',
        '',
        'Persona is inferred from the case field `applicant_type`:',
        '',
        '| `applicant_type` | Persona in this subset |',
        '| --- | --- |',
        '| `manufacturer` | manufacturer |',
        '| `contractor` | general contractor |',
        '| `homebuilder` | homebuilder |',
        '',
        '`architect-engineer` and `owner` are outside this subset.',
        'Variance kind is the case `topic` field.',
        '',
        '## Draw',
        '',
        'Cases are grouped by persona and by `gold.intake_action`, shuffled with Fisher-Yates',
        f'(`random.Random({SEED}).randrange`), then drawn rarest action first (`redirect`, then',
        '`ask`, then `proceed_conditionally`) up to one per action, then filled to 5 per persona',
        'preferring a variance kind not yet chosen. The action label is used only to balance the',
        'draw. It is not copied into the key.',
        '',
        f"Intake-action mix in this draw (counts only): "
        + ', '.join(f'{name} {actions[name]}' for name in ACTIONS) + '.',
        '',
        '## Selected cases',
        '',
        '| Case | Persona | Variance kind |',
        '| --- | --- | --- |',
    ]
    for case in selected:
        lines.append(f"| `{case['id']}` | {persona_of(case)} | `{case['topic']}` |")
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--cases', type=Path, default=CASES)
    ap.add_argument('--seed', type=int, default=SEED)
    ap.add_argument('--write', action='store_true', help='write blank keys and SELECTION.md')
    args = ap.parse_args()
    selected = select_cases(load_cases(args.cases), seed=args.seed)
    for case in selected:
        print(f"{case['id']}\t{persona_of(case)}\t{case['topic']}")
    if args.write:
        skipped = write_selection(selected)
        print(f'wrote {len(selected) - len(skipped)} keys')
        if skipped:
            print('left filled keys untouched: ' + ', '.join(skipped))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
