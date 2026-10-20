"""Score the Section D practice screen on the 12 professional-involvement appeals.

The screen reads ``professional_involvement.facts`` only. It does not read the
weak label, the narrative, or the quotes. ``rules_only``, ``rules_plus_unknown``
and ``always_unknown`` are the variants in ``engine/section_d_flag_eval.py``.
Nothing here changes those rules.

    python evals_dev/appeals/score_professional.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.professional import ProfessionalFacts, professional_involvement  # noqa: E402
from engine.section_d_flag_eval import Signals, load_codes, prepare  # noqa: E402
from evals_dev.stats import wilson_interval  # noqa: E402

CASES = Path(__file__).resolve().parent / 'cases'
VARIANTS = ('rules_only', 'rules_plus_unknown', 'always_unknown')
GOLD_ROWS = ('yes', 'depends', 'no')
SYSTEM_COLS = ('yes', 'unknown', 'no')
LINE = 'label_strength: weak; editions pre-2023'


def load_addressed(path: Path = CASES) -> list[dict]:
    """Load only decisions whose professional-involvement issue was marked addressed."""
    cases = []
    for file in sorted(path.glob('scc-*.json')):
        case = json.loads(file.read_text())
        if (case.get('professional_involvement') or {}).get('addressed'):
            cases.append(case)
    return cases


def stored_facts(case: dict) -> ProfessionalFacts:
    """ProfessionalFacts fields recorded on the case. Labels are not read."""
    raw = (case.get('professional_involvement') or {}).get('facts') or {}
    allowed = set(ProfessionalFacts.model_fields)
    return ProfessionalFacts(**{key: value for key, value in raw.items() if key in allowed})


def predict(case: dict, codes, variant: str) -> str:
    """Apply one evaluation variant to stored facts without reading the weak target label."""
    if variant == 'always_unknown':
        return 'unknown'
    result = professional_involvement(prepare(stored_facts(case), Signals(), variant), codes)
    if variant == 'rules_plus_unknown' and result.required == 'depends':
        return 'unknown'
    return result.required


def _column(label: str) -> str:
    """``rules_only`` abstains with ``depends``. That count shares the unknown column."""
    if label == 'depends':
        return 'unknown'
    return label


def _matches(system: str, gold: str) -> bool:
    """Treat unknown and depends as equivalent when comparing screen and weak labels."""
    normalized = {'unknown': 'depends'}
    return normalized.get(system, system) == normalized.get(gold, gold)


def score_cases(cases: list[dict], codes) -> dict[str, dict]:
    """Tally agreement, abstentions and confident errors separately for every screen variant."""
    totals = {}
    for name in VARIANTS:
        matrix = {gold: {column: 0 for column in SYSTEM_COLS} for gold in GOLD_ROWS}
        matched = 0
        unknown = 0
        wrong = []
        for case in cases:
            system = predict(case, codes, name)
            gold = case['professional_involvement']['weak_flag']
            column = _column(system)
            matrix[gold][column] += 1
            matched += int(_matches(system, gold))
            if column == 'unknown':
                unknown += 1
            if column in ('yes', 'no') and not _matches(system, gold):
                wrong.append(case['id'])
        totals[name] = {
            'matched': matched,
            'n': len(cases),
            'unknown': unknown,
            'confident_wrong': wrong,
            'matrix': matrix,
        }
    return totals


def _ratio(count: int, total: int) -> str:
    """Format an agreement ratio with its Wilson 95% interval."""
    low, high = wilson_interval(count, total)
    return f'{count}/{total} [{low:.4f}, {high:.4f}]'


def render(totals: dict[str, dict]) -> str:
    """Render weak-label caveats, confusion matrices and variant outcomes."""
    lines = [LINE, 'screen reads professional_involvement.facts only; the weak label is the target, not an input']
    lines.append('note: rules_only abstains with depends; that label is counted in the unknown column')
    for name in VARIANTS:
        row = totals[name]
        lines.append(f'{name}: {_ratio(row["matched"], row["n"])}')
        lines.append(f'confusion {name}  rows=gold  columns=system yes unknown no')
        for gold in GOLD_ROWS:
            cells = '  '.join(f'{row["matrix"][gold][column]:>3}' for column in SYSTEM_COLS)
            lines.append(f'  {gold:<7} {cells}')
        lines.append(f'unknown {name}: {row["unknown"]}')
        wrong = ', '.join(row['confident_wrong']) if row['confident_wrong'] else 'none'
        lines.append(f'confident_wrong {name}: {wrong}')
    return '\n'.join(lines)


def main() -> int:
    """Require twelve addressed decisions and print their separate professional-screen report."""
    cases = load_addressed()
    if len(cases) != 12:
        print(f'expected 12 professional-involvement appeals, found {len(cases)}', file=sys.stderr)
        return 1
    codes, _codedb = load_codes()
    print(render(score_cases(cases, codes)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
