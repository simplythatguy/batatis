"""Score the frozen engineer-needed screen on an external heldout-v1.1 file.

The v1.1 labels are internal and not judge-facing.

The case file is not in this repo. Appeal decisions have no stated licence, so this
script only reads a path you pass in and does not copy the cases.

Precedent retrieval stays off. These variants call professional.py through
section_d_flag_eval. They do not read research/precedents/index.json.

    python -m engine.section_d_heldout_v11 /path/to/cases_v1.1.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .section_d_flag_eval import VARIANTS, _agreement_cell, _count_cell, load_codes, score

SECTION = 'Held-out v1.1: first run, frozen rules, retrieval off'
INTERPRETATION = (
    'the shipped screen asks rather than says no on most BCV cases, whose no labels come from silence; '
    '0 under-flags (on text-only cases it answers only yes or ask, never no, so 0 under-flags holds by construction); '
    'low agreement here reflects asking, not wrong answers. '
    'Weak labels, internal, not judge-facing.'
)
LABEL = (
    'model-extracted labels; BCV no labels are by silence, not explicit negatives; '
    'province-wide variances, not applications'
)
_LABELS = frozenset({'yes', 'no', 'depends'})


def source_of(row: dict) -> str:
    kind = row.get('source_type') or ''
    if 'STANDATA' in kind or 'bcv' in row.get('id', ''):
        return 'bcv'
    return 'appeal'


def engineering_label(row: dict) -> str | None:
    flag = row.get('gold_engineering_flag')
    if not isinstance(flag, dict):
        return None
    label = flag.get('engineering_required')
    if label not in _LABELS:
        return None
    return label


def labelled_cases(rows: list[dict]) -> tuple[list[dict], int]:
    """Drop null engineering labels. The returned cases match section_d_flag_eval.score."""
    kept = []
    skipped = 0
    for row in rows:
        label = engineering_label(row)
        if label is None:
            skipped += 1
            continue
        kept.append({
            'id': row['id'],
            'description': row.get('description') or '',
            'known_facts': row.get('known_facts') or [],
            'source': source_of(row),
            'gold': {'engineering_required': label},
        })
    return kept, skipped


def _block(title: str, cases: list[dict], codes) -> list[str]:
    totals = score(codes, cases)
    lines = [f'{title} n={len(cases)}']
    for name in VARIANTS:
        row = totals[name]
        facts = ', '.join(row.under_flag_facts) if row.under_flag_facts else 'none'
        lines.append(
            f'{name} agreement {_agreement_cell(row)} '
            f'under_flag {_count_cell(row.under_flag, row.scored)} '
            f'confident_wrong {_count_cell(row.confident_wrong, row.scored)} '
            f'unknown_rate {_count_cell(row.unknown, row.scored)}')
        lines.append(f'under_flag {name}: {facts}')
    return lines


def report(rows: list[dict], codes) -> str:
    cases, skipped = labelled_cases(rows)
    lines = [
        SECTION,
        INTERPRETATION,
        'first run with frozen rules',
        'precedent retrieval: off',
        f'label: {LABEL}',
        f'cases: {len(rows)}',
        f'skipped null: {skipped}',
        f'labelled n: {len(cases)}',
    ]
    for source in ('appeal', 'bcv'):
        lines.extend(_block(f'source {source}', [case for case in cases if case['source'] == source], codes))
    lines.extend(_block('pooled', cases, codes))
    return '\n'.join(lines)


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print('usage: python -m engine.section_d_heldout_v11 CASES.jsonl', file=sys.stderr)
        return 2
    codes, _codedb = load_codes()
    print(report(load_rows(Path(args[0])), codes))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
