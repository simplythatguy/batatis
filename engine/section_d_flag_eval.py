"""Compare practice-of-engineering flag variants on the 60 development cases.

    python -m engine.section_d_flag_eval

`rules_only` fills unstated component facts with "not triggered" and returns professional.py's
yes/no/depends. `rules_plus_unknown` keeps that screen, records a stated span above 12.20 m as
Part 4 design (cited only as Div C 2.4.1.2.(1) from professional.py), and returns unknown instead
of no when a deciding fact was not stated.

The gold labels are model-checked, not human-reviewed. `rules_plus_unknown` was written while
looking at this same development set, so the agreement is in-sample. There is no held-out split.

Gold `depends` matches system `unknown`. Under-flag is gold yes and system no. A case is skipped
when codedb (or the rule lookup standing in for it) cannot resolve a provision the screen asks for.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from .codes import Codes
from .professional import ProfessionalFacts, professional_involvement
from .section_d_issues import PART9_MAX_SPAN_M, PROCESS_RULES, PROFESSIONAL_RULES

CASES = Path(__file__).resolve().parents[1] / 'evals_dev' / 'cases'
VARIANTS = ('rules_only', 'rules_plus_unknown', 'always_unknown')
GOLD_ROWS = ('yes', 'depends', 'no')
SYSTEM_COLS = ('yes', 'unknown', 'no')

_NUM = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
    'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'fifteen': 15, 'eighteen': 18, 'twenty': 20,
    'forty': 40, 'sixty': 60, 'eighty': 80,
}
_NUM_RE = '|'.join(sorted(_NUM, key=len, reverse=True))
_TOKEN = rf'(?:\d+|{_NUM_RE})'
_NO_DEFAULTS = dict(
    part4_design=False, preserved_wood_foundation_part4=False, roof_trusses=False,
    prescriptive_route_confirmed=True, ahj_requires_professional=False, special_safety_concerns=False,
    professional_judgement_required=False, professional_scope_resolved=True,
    fire_suppression=False, fire_alarm=False,
)
_AREA_LIMITS = {
    'assembly': (300, 150, 100), 'care': (300, 150, 100), 'treatment': (300, 150, 100),
    'detention': (300, 150, 100), 'hotel': (400, 200, 130),
    'business': (500, 250, 165), 'mercantile': (500, 250, 165), 'industrial': (500, 250, 165),
}
# Lookup stub ids. Sources are the third field of PROFESSIONAL_RULES and PROCESS_RULES.
RULE_IDS = tuple((division, provision_id) for division, provision_id, _source in (*PROFESSIONAL_RULES, *PROCESS_RULES))
_WILSON_Z = 1.959963984540054  # 95%
_PART4 = re.compile(
    r'\b(?:under part 4|part 4 design|designed under part 4|design under part 4|carrying out part 4|'
    r'part 4 (?:roof|wind|industrial|foundation)|structural(?:ly)? design(?:ed)? (?:is )?under part 4)\b',
    re.I)
_UNRESOLVED = re.compile(
    r'\b(?:steel strap|proprietary tables|proprietary header|structural insulated panels?|shear values|'
    r'into the foam|no engineer(?:s| is)?|part 5)\b', re.I)
_OUT = re.compile(
    r'\b(?:natural gas|gas fitter|gas supply|electrical panel|electrician|air admittance|'
    r'septic|sewage|disposal[- ]field|plumbing contractor)\b', re.I)
_PRODUCT = re.compile(
    r'\b(?:we make|we manufacture|our product|want it approved|sell it for|builders are asking|'
    r'builders want to use|proposed board|wood-plastic composite)\b', re.I)
_DETACHED = re.compile(
    r'\b(?:single[- ]family|single detached|detached house|detached home|bungalow|our new houses|custom home|'
    r'my(?:\s+\w+){0,3}\s+house)\b', re.I)


class RuleLookup:
    """Resolves rule ids without emitting an NBC citation string."""

    def provision(self, provision_id: str, division: str | None = 'B'):
        if division is None:
            raise ValueError(f'division required for {provision_id}')
        key = (division.upper(), provision_id)
        if key not in RULE_IDS:
            return None
        return {'id': provision_id, 'division': division.upper(), 'citation': f'rule:{division.upper()}:{provision_id}',
                'level': 'sentence', 'children': [], 'attributions': [], 'attribution_status': None,
                'intents': [], 'intent_comparison': []}

    def citation(self, provision_id: str, division: str | None = 'B'):
        record = self.provision(provision_id, division)
        return record['citation'] if record else None

    def definition(self, code: str):
        return None


@dataclass
class Signals:
    span_m: float | None = None
    flags: set[str] = field(default_factory=set)


@dataclass
class VariantScore:
    name: str
    scored: int = 0
    skipped: int = 0
    matched: int = 0
    under_flag: int = 0
    unknown: int = 0
    confident_wrong: int = 0
    gold_yes_unknown: list[str] = field(default_factory=list)
    under_flag_facts: list[str] = field(default_factory=list)
    matrix: dict[str, dict[str, int]] = field(default_factory=lambda: {
        gold: {column: 0 for column in SYSTEM_COLS} for gold in GOLD_ROWS})

    @property
    def agreement(self) -> float:
        return self.matched / self.scored if self.scored else 0.0


def wilson_interval(matched: int, scored: int) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion, 95%."""
    if scored <= 0:
        return (0.0, 0.0)
    z2 = _WILSON_Z * _WILSON_Z
    p = matched / scored
    denom = 1 + z2 / scored
    centre = p + z2 / (2 * scored)
    margin = _WILSON_Z * math.sqrt(p * (1 - p) / scored + z2 / (4 * scored * scored))
    return (max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom))


def _number(token: str) -> int:
    token = token.lower().replace(',', '')
    return _NUM[token] if token in _NUM else int(float(token))


def _case_text(case: dict) -> str:
    return '\n'.join([case.get('description') or '', *(case.get('known_facts') or [])])


def _storeys(text: str) -> int | None:
    found = [1] if re.search(r'\bsingle-storey\b', text, re.I) else []
    found += [_number(match.group(1)) for match in re.finditer(rf'\b({_TOKEN})[-\s]storeys?\b', text, re.I)]
    return max(found) if found else None


def _area(text: str) -> float | None:
    for pattern in (r'building area of\s+(\d[\d,]*(?:\.\d+)?)\s*m', r'(\d[\d,]*(?:\.\d+)?)\s*m\s*(?:2|²)\s+building area'):
        labelled = re.findall(pattern, text, re.I)
        if labelled:
            return float(labelled[-1].replace(',', ''))
    values = []
    for match in re.finditer(r'\b(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*m\s*(?:2|²)\b', text, re.I):
        if re.match(r'\s*per floor', text[match.end():match.end() + 20], re.I):
            continue
        values.append(float(match.group(1).replace(',', '')))
    if len(values) == 1:
        return values[0]
    return None


def _units(text: str, storeys: int | None) -> int | None:
    total = re.search(rf'\b({_TOKEN})\s+in total\b', text, re.I)
    if total:
        return _number(total.group(1))
    per_floor = re.search(rf'\b({_TOKEN})\s+(?:dwelling\s+)?units?\s+per floor\b', text, re.I)
    if per_floor and storeys:
        return _number(per_floor.group(1)) * storeys
    found = []
    for pattern in (
        rf'\b({_TOKEN})-units?\b', rf'\b({_TOKEN})\s+(?:dwelling\s+)?units?\b',
        rf'\b({_TOKEN})\s+apartments?\b', rf'\b({_TOKEN})\s+dwellings?\b',
        rf'\b({_TOKEN})\s+(?:[\w-]+\s+){{0,3}}townhouses?\b', rf'\b({_TOKEN})\s+houses\b',
    ):
        found += [_number(match.group(1)) for match in re.finditer(pattern, text, re.I)]
    if re.search(r'\bduplex\b', text, re.I):
        found.append(2)
    return max(found) if found else None


def _span(text: str) -> float | None:
    found = [float(match.group(1)) for match in re.finditer(
        rf'\b(\d+(?:\.\d+)?)\s*m(?!\s*(?:2|²))(?:\s+\S+){{0,4}}\s+\S*span\b', text, re.I)]
    return max(found) if found else None


def _occupancy(text: str, units: int | None) -> str | None:
    if re.search(r'\b(?:community hall|arena|library)\b', text, re.I):
        return 'assembly'
    if re.search(r'\b(?:warehouse|industrial building|industrial park)\b', text, re.I):
        return 'industrial'
    if re.search(r'\b(?:hotel|motel)\b', text, re.I):
        return 'hotel'
    if _DETACHED.search(text) and not re.search(r'\b(?:apartments?|townhouses?|duplex)\b', text, re.I):
        return 'single_family'
    if re.search(r'\b(?:apartments?|townhouses?|duplex|dwelling units|multi-family)\b', text, re.I) or (
            units is not None and units >= 2):
        return 'multi_family'
    if re.search(r'\boffice\b', text, re.I):
        return 'business'
    if re.search(r'\bdetached garage\b', text, re.I) and re.search(r'\bsuite\b', text, re.I):
        return 'single_family'
    if re.search(r'\b(?:house|houses|home|homes)\b', text, re.I):
        return 'single_family'
    return None


def observe(case: dict) -> tuple[ProfessionalFacts, Signals]:
    """Facts stated in the applicant text. Gold labels are not read."""
    text = _case_text(case)
    signals = Signals(span_m=_span(text))
    if _OUT.search(text):
        signals.flags.add('out_of_scope')
        return ProfessionalFacts(), signals
    storeys, area = _storeys(text), _area(text)
    if _PRODUCT.search(text) and storeys is None and area is None and not _PART4.search(text):
        signals.flags.add('product_without_building')
        return ProfessionalFacts(), signals
    if re.search(r'not confirmed how many dwellings|dwelling count, use', text, re.I):
        signals.flags.add('occupancy_unconfirmed')
        return ProfessionalFacts(), signals
    if _UNRESOLVED.search(text):
        signals.flags.add('unresolved_design')
    units = _units(text, storeys)
    data = {
        'occupancy': _occupancy(text, units),
        'storeys': storeys,
        'building_area_m2': area,
        'principal_dwelling_units': units if _occupancy(text, units) == 'multi_family' else None,
    }
    if _PART4.search(text):
        data['part4_design'] = True
    return ProfessionalFacts(**{key: value for key, value in data.items() if value is not None}), signals


def _plain_exemption(data: dict) -> bool:
    if data.get('part4_design') is True or data.get('roof_trusses') is True or data.get('ahj_requires_professional') is True:
        return False
    occupancy, units, storeys, area = data.get('occupancy'), data.get('principal_dwelling_units'), data.get('storeys'), data.get('building_area_m2')
    if occupancy == 'single_family' or occupancy == 'relocatable_industrial_camp':
        return True
    if occupancy == 'multi_family' and units is not None and units <= 4:
        return True
    if occupancy == 'farm' and data.get('farm_public_use') is False:
        return True
    if occupancy in _AREA_LIMITS and storeys is not None and storeys <= 3 and area is not None:
        return area <= _AREA_LIMITS[occupancy][storeys - 1]
    return False


def prepare(facts: ProfessionalFacts, signals: Signals, variant: str) -> ProfessionalFacts:
    data = facts.model_dump()
    if variant == 'rules_plus_unknown' and signals.span_m is not None and signals.span_m > PART9_MAX_SPAN_M:
        data['part4_design'] = True
    fill = variant == 'rules_only' or (
        variant == 'rules_plus_unknown' and _plain_exemption(data) and not signals.flags and data.get('part4_design') is not True)
    if fill:
        for key, value in _NO_DEFAULTS.items():
            if data.get(key) is None:
                data[key] = value
    return ProfessionalFacts(**data)


def flag_label(case: dict, codes, variant: str) -> str:
    if variant == 'always_unknown':
        return 'unknown'
    facts, signals = observe(case)
    result = professional_involvement(prepare(facts, signals, variant), codes)
    if variant == 'rules_plus_unknown' and result.required == 'depends':
        return 'unknown'
    return result.required


def _column(label: str) -> str:
    """rules_only abstains with professional.py's ``depends``. That count shares the unknown column."""
    if label == 'depends':
        return 'unknown'
    return label


def under_flag_fact(case: dict, variant: str) -> str:
    facts, signals = observe(case)
    parts = [f'occupancy={facts.occupancy}', f'part4_design={"true" if facts.part4_design is True else "unset"}']
    if signals.span_m is not None:
        parts.append(f'span_m={signals.span_m:g}')
    if variant == 'rules_only' and signals.span_m is not None and signals.span_m > PART9_MAX_SPAN_M:
        parts.append(
            f'rules_only does not apply the {PART9_MAX_SPAN_M:.2f} m span, so part4_design is filled false')
    return f"{case['id']}: " + '; '.join(parts)


def _matches(system: str, gold: str) -> bool:
    normalized = {'unknown': 'depends'}
    return normalized.get(system, system) == normalized.get(gold, gold)


def load_codes():
    try:
        codes = Codes()
        if codes.provision('2.4.1.1.(1)', 'C') is None:
            raise FileNotFoundError('division C professional rules are not in codedb')
        return codes, 'present'
    except FileNotFoundError:
        return RuleLookup(), 'missing'


def score(codes, cases: list[dict] | None = None) -> dict[str, VariantScore]:
    rows = cases if cases is not None else load_cases()
    totals = {name: VariantScore(name) for name in VARIANTS}
    for case in rows:
        gold = case['gold']['engineering_required']
        for name in VARIANTS:
            try:
                label = flag_label(case, codes, name)
            except (KeyError, ValueError):
                totals[name].skipped += 1
                continue
            column = _column(label)
            totals[name].scored += 1
            totals[name].matched += int(_matches(label, gold))
            totals[name].matrix[gold][column] += 1
            if column == 'unknown':
                totals[name].unknown += 1
            if column in ('yes', 'no') and not _matches(label, gold):
                totals[name].confident_wrong += 1
            if gold == 'yes' and label == 'no':
                totals[name].under_flag += 1
                totals[name].under_flag_facts.append(under_flag_fact(case, name))
            if gold == 'yes' and column == 'unknown':
                totals[name].gold_yes_unknown.append(case['id'])
    return totals


def load_cases() -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted(CASES.glob('dev-*.json'))]


def winner(totals: dict[str, VariantScore]) -> str:
    ranked = sorted((row for row in totals.values() if row.name != 'always_unknown'),
                    key=lambda row: (row.under_flag > 0, -row.agreement, row.name != 'rules_plus_unknown'))
    if not ranked or ranked[0].scored == 0:
        return 'none'
    return ranked[0].name


def _agreement_cell(row: VariantScore) -> str:
    lower, upper = wilson_interval(row.matched, row.scored)
    upper_text = '1.0' if round(upper, 4) == 1 else f'{upper:.4f}'
    return f'{row.matched}/{row.scored} [{lower:.4f}, {upper_text}]'


def _yes_unknown(row: VariantScore) -> str:
    return 'none' if not row.gold_yes_unknown else ', '.join(row.gold_yes_unknown)


def _count_cell(count: int, scored: int) -> str:
    lower, upper = wilson_interval(count, scored)
    upper_text = '1.0' if round(upper, 4) == 1 else f'{upper:.4f}'
    return f'{count}/{scored} [{lower:.4f}, {upper_text}]'


def report(totals: dict[str, VariantScore], codedb: str) -> str:
    scored = max((row.scored for row in totals.values()), default=0)
    skipped = max((row.skipped for row in totals.values()), default=0)
    lines = [
        f'{"variant":<22} {"scored":>6} {"agreement":>22} {"under_flag":>10} {"unknown":>7} {"skipped":>7}',
        'note: rules_only abstains with depends; that label is counted in the unknown column',
    ]
    for name in VARIANTS:
        row = totals[name]
        lines.append(
            f'{name:<22} {row.scored:>6} {_agreement_cell(row):>22} {row.under_flag:>10} {row.unknown:>7} {row.skipped:>7}')
        lines.append(f'unknown_rate {name}: {_count_cell(row.unknown, row.scored)}')
        lines.append(f'confident_wrong {name}: {_count_cell(row.confident_wrong, row.scored)}')
        lines.append(f'confusion {name}  rows=gold  columns=system yes unknown no')
        for gold in GOLD_ROWS:
            cells = '  '.join(f'{row.matrix[gold][column]:>3}' for column in SYSTEM_COLS)
            lines.append(f'  {gold:<7} {cells}')
        lines.append(f'gold_yes_as_unknown {name}: {_yes_unknown(row)}')
        facts = '; '.join(row.under_flag_facts) if row.under_flag_facts else 'none'
        lines.append(f'under_flag {name}: {facts}')
    lines.append(f'winner: {winner(totals)}')
    lines.append('under_flag_target: 0')
    lines.append('gold: model-checked')
    lines.append('split: dev (in-sample; no held-out)')
    lines.append('out_of_sample: evals_dev/appeals (built on another branch; not scored here)')
    lines.append(f'codedb: {codedb}')
    lines.append(f'scored: {scored}')
    lines.append(f'skipped: {skipped}')
    if codedb == 'missing':
        lines.append('citation_checks: 0')
        lines.append('note: codedb is missing, so citation text was not checked; flag decisions still use professional.py')
    return '\n'.join(lines)


def main() -> int:
    codes, codedb = load_codes()
    print(report(score(codes), codedb))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
