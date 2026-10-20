"""Compare practice-of-engineering flag variants on the 60 development cases.

    python -m engine.section_d_flag_eval

`rules_only` fills unstated component facts with "not triggered" and returns professional.py's
yes/no/depends. `rules_plus_unknown` keeps that screen, records a stated span above 12.20 m as
Part 4 design (cited only as Div C 2.4.1.2.(1) from professional.py), and returns unknown with a
question when span, area, storeys, occupancy, or Part 4 design is missing. It does not default
those facts to a boolean. A rule that already resolves to yes still returns yes.

`rules_plus_unknown_cf` is the same frozen screen, run once for every combination of the missing
deciding facts at fixed extremes (the value that most pushes toward yes, and the value that most
pushes toward no). Those extremes come from the rule thresholds and do not change per case. If
every combination returns the same answer, that answer is used. If they disagree, the flag is
unknown and the question names the first missing fact that flips the answer. This variant is
reported beside the shipped screen. The shipped screen stays `rules_plus_unknown`.

The gold labels are model-checked, not human-reviewed. `rules_plus_unknown` was written while
looking at this same development set, so agreement on those 60 cases is in-sample. The eight-case
limit check is reported separately and is no longer blind for missing-fact cases.

Gold `depends` matches system `unknown`. Under-flag is gold yes and system no. A case is skipped
when codedb (or the rule lookup standing in for it) cannot resolve a provision the screen asks for.

(on text-only cases it answers only yes or ask, never no, so 0 under-flags holds by construction)
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path

from .codes import CodeDbMissing, Codes
from .professional import ProfessionalFacts, professional_involvement
from .section_d_issues import PART9_MAX_SPAN_M, PROCESS_RULES, PROFESSIONAL_RULES

CASES = Path(__file__).resolve().parents[1] / 'evals_dev' / 'cases'
HELDOUT = Path(__file__).resolve().parents[1] / 'evals_dev' / 'section_d_heldout'
# Recorded before the missing-fact fix. hold-004 was the miss. Do not recompute this line.
_BLIND_HELDOUT_RULES_PLUS = '7/8 [0.5291, 0.9776]'
_MISSING_QUESTION = {
    'span': 'What is the span in metres?',
    'area': 'What is the building area in square metres, not the sum of every floor?',
    'storeys': 'How many storeys does the building have?',
    'occupancy': 'What is the confirmed occupancy or building type?',
    'part4_design': 'Is any design carried out under Part 4, including beams, connections or foundations?',
}

def _count_phrase(count: int, singular: str) -> str:
    return f'{count} {singular if count == 1 else singular + "s"}'


VARIANTS = ('rules_only', 'rules_plus_unknown', 'rules_plus_unknown_cf', 'always_unknown')
# Not selected. The shipped screen stays rules_plus_unknown even when this variant agrees more.
_NOT_SHIPPED = frozenset({'always_unknown', 'rules_plus_unknown_cf'})
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
# Fixed extremes from engine/professional.py and PART9_MAX_SPAN_M. Not fitted to a gold label.
# Yes: span above 12.20 m, area above every _AREA_LIMITS entry, storeys > 3,
# multi_family with principal_dwelling_units > 4, part4_design true.
# No: span at 12.20 m (the handoff is strict greater-than), area 1 m2, one storey,
# single_family, part4_design false.
_CF_AREA_YES = max(limit for limits in _AREA_LIMITS.values() for limit in limits) + 1
_CF_UNITS_YES = 5  # professional.py sets multi_family general to yes only when units > 4
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
    misses: list[str] = field(default_factory=list)
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


def missing_deciding_facts(facts: ProfessionalFacts, signals: Signals) -> tuple[str, ...]:
    """Span, area, storeys, occupancy, and Part 4 design. None of these is defaulted to a boolean."""
    missing = []
    if signals.span_m is None:
        missing.append('span')
    if facts.building_area_m2 is None:
        missing.append('area')
    if facts.storeys is None:
        missing.append('storeys')
    if facts.occupancy is None:
        missing.append('occupancy')
    if facts.part4_design is None:
        missing.append('part4_design')
    return tuple(missing)


def prepare(facts: ProfessionalFacts, signals: Signals, variant: str) -> ProfessionalFacts:
    data = facts.model_dump()
    # This span handoff came from development case dev-050 (stated 18 m span, gold yes).
    # A stated span above PART9_MAX_SPAN_M is recorded as Part 4 design. The cited
    # provision stays Div C 2.4.1.2.(1) from engine/professional.py.
    if variant == 'rules_plus_unknown' and signals.span_m is not None and signals.span_m > PART9_MAX_SPAN_M:
        data['part4_design'] = True
    candidate = ProfessionalFacts(**data)
    # rules_only fills unstated component facts. rules_plus_unknown does that only when
    # every deciding fact is already present. A missing span, area, storey count,
    # occupancy, or Part 4 design stays unset.
    fill = variant == 'rules_only' or (
        variant == 'rules_plus_unknown'
        and not missing_deciding_facts(candidate, signals)
        and _plain_exemption(data)
        and not signals.flags
        and data.get('part4_design') is not True)
    if fill:
        for key, value in _NO_DEFAULTS.items():
            if data.get(key) is None:
                data[key] = value
    return ProfessionalFacts(**data)


def _with_span_handoff(facts: ProfessionalFacts, signals: Signals) -> ProfessionalFacts:
    if signals.span_m is not None and signals.span_m > PART9_MAX_SPAN_M and facts.part4_design is not True:
        return facts.model_copy(update={'part4_design': True})
    return facts


def _assign_extremes(facts: ProfessionalFacts, signals: Signals, assignment: dict[str, bool]) -> ProfessionalFacts:
    """Set each missing deciding fact to its frozen yes-push or no-push value, then apply the span handoff."""
    data = facts.model_dump()
    span = signals.span_m
    for name, toward_yes in assignment.items():
        if name == 'span':
            span = PART9_MAX_SPAN_M + 0.01 if toward_yes else PART9_MAX_SPAN_M
        elif name == 'area':
            data['building_area_m2'] = _CF_AREA_YES if toward_yes else 1.0
        elif name == 'storeys':
            data['storeys'] = 4 if toward_yes else 1
        elif name == 'occupancy':
            if toward_yes:
                data['occupancy'] = 'multi_family'
                data['principal_dwelling_units'] = _CF_UNITS_YES
            else:
                data['occupancy'] = 'single_family'
                data['principal_dwelling_units'] = None
        elif name == 'part4_design':
            data['part4_design'] = bool(toward_yes)
    if span is not None and span > PART9_MAX_SPAN_M:
        data['part4_design'] = True
    if _plain_exemption(data) and not signals.flags and data.get('part4_design') is not True:
        for key, value in _NO_DEFAULTS.items():
            if data.get(key) is None:
                data[key] = value
    return ProfessionalFacts(**data)


def counterfactual(facts: ProfessionalFacts, signals: Signals, codes) -> tuple[str, str | None]:
    """Return the shared answer when every extreme agrees, otherwise unknown and the first flipping fact."""
    base = _with_span_handoff(facts, signals)
    missing = missing_deciding_facts(base, signals)
    labels: dict[tuple[bool, ...], tuple[str, list[str]]] = {}
    bits_list = list(product((False, True), repeat=len(missing))) or [()]
    for bits in bits_list:
        assignment = {name: bit for name, bit in zip(missing, bits)}
        result = professional_involvement(_assign_extremes(base, signals, assignment), codes)
        labels[bits] = (result.required, result.questions)
    answers = {bits: required for bits, (required, _questions) in labels.items()}
    if len(set(answers.values())) == 1:
        only = next(iter(answers.values()))
        if only == 'depends':
            questions = next(iter(labels.values()))[1]
            question = _MISSING_QUESTION[missing[0]] if missing else (questions[0] if questions else None)
            return 'unknown', question or 'Which deciding building fact is still unconfirmed?'
        return only, None
    baseline = tuple(False for _ in missing)
    for index, name in enumerate(missing):
        trial = list(baseline)
        trial[index] = True
        if answers[tuple(trial)] != answers[baseline]:
            return 'unknown', _MISSING_QUESTION[name]
    return 'unknown', _MISSING_QUESTION[missing[0]]


def evaluate(case: dict, codes, variant: str) -> tuple[str, str | None]:
    if variant == 'always_unknown':
        return 'unknown', None
    facts, signals = observe(case)
    if variant == 'rules_plus_unknown_cf':
        return counterfactual(facts, signals, codes)
    prepared = prepare(facts, signals, variant)
    result = professional_involvement(prepared, codes)
    if variant == 'rules_plus_unknown' and result.required != 'yes':
        missing = missing_deciding_facts(prepared, signals)
        if missing or result.required == 'depends':
            question = _MISSING_QUESTION[missing[0]] if missing else (result.questions[0] if result.questions else None)
            return 'unknown', question or 'Which deciding building fact is still unconfirmed?'
    return result.required, None


def flag_label(case: dict, codes, variant: str) -> str:
    return evaluate(case, codes, variant)[0]


def flag_question(case: dict, codes, variant: str) -> str | None:
    return evaluate(case, codes, variant)[1]


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
    except (CodeDbMissing, FileNotFoundError):
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
            if not _matches(label, gold):
                totals[name].misses.append(f"{case['id']} gold={gold} system={label}")
            if gold == 'yes' and label == 'no':
                totals[name].under_flag += 1
                totals[name].under_flag_facts.append(under_flag_fact(case, name))
            if gold == 'yes' and column == 'unknown':
                totals[name].gold_yes_unknown.append(case['id'])
    return totals


def load_cases() -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted(CASES.glob('dev-*.json'))]


def load_heldout() -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted(HELDOUT.glob('hold-*.json'))]


def winner(totals: dict[str, VariantScore]) -> str:
    # rules_plus_unknown_cf is measured here and is not eligible. The shipped screen stays rules_plus_unknown.
    ranked = sorted((row for row in totals.values() if row.name not in _NOT_SHIPPED),
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


def _variant_lines(row: VariantScore) -> list[str]:
    lines = [
        f'{row.name:<22} {row.scored:>6} {_agreement_cell(row):>22} {row.under_flag:>10} {row.unknown:>7} {row.skipped:>7}',
        f'unknown_rate {row.name}: {_count_cell(row.unknown, row.scored)}',
        f'confident_wrong {row.name}: {_count_cell(row.confident_wrong, row.scored)}',
        f'confusion {row.name}  rows=gold  columns=system yes unknown no',
    ]
    for gold in GOLD_ROWS:
        cells = '  '.join(f'{row.matrix[gold][column]:>3}' for column in SYSTEM_COLS)
        lines.append(f'  {gold:<7} {cells}')
    lines.append(f'gold_yes_as_unknown {row.name}: {_yes_unknown(row)}')
    facts = '; '.join(row.under_flag_facts) if row.under_flag_facts else 'none'
    lines.append(f'under_flag {row.name}: {facts}')
    return lines


def _table_header() -> str:
    return f'{"variant":<22} {"scored":>6} {"agreement":>22} {"under_flag":>10} {"unknown":>7} {"skipped":>7}'


def report(totals: dict[str, VariantScore], codedb: str) -> str:
    scored = max((row.scored for row in totals.values()), default=0)
    skipped = max((row.skipped for row in totals.values()), default=0)
    lines = [
        _table_header(),
        'note: rules_only abstains with depends; that label is counted in the unknown column',
    ]
    for name in VARIANTS:
        lines.extend(_variant_lines(totals[name]))
    lines.append('rules_plus_unknown on this dev table is in-sample and pending out-of-sample confirmation')
    lines.append(f'winner: {winner(totals)}')
    lines.append('under_flag_target: 0')
    lines.append('gold: model-checked')
    lines.append('split: dev (in-sample; pending out-of-sample confirmation)')
    lines.append('out_of_sample: evals_dev/appeals (built on another branch; not scored here)')
    lines.append(f'codedb: {codedb}')
    lines.append(f'scored: {scored}')
    lines.append(f'skipped: {skipped}')
    if codedb == 'missing':
        lines.append('citation_checks: 0')
        lines.append('note: codedb is missing, so citation text was not checked; flag decisions still use professional.py')
    return '\n'.join(lines)


def heldout_report(totals: dict[str, VariantScore]) -> str:
    lines = [
        'held-out: evals_dev/section_d_heldout',
        'held-out gold: model-checked',
        f'held-out rules_plus_unknown: {_BLIND_HELDOUT_RULES_PLUS}',
        'post-fix, no longer blind',
        _table_header(),
    ]
    for name in VARIANTS:
        lines.extend(_variant_lines(totals[name]))
        misses = ', '.join(totals[name].misses) if totals[name].misses else 'none'
        lines.append(f'misses {name}: {misses}')
    return '\n'.join(lines)


def headline(dev: dict[str, VariantScore], heldout: dict[str, VariantScore]) -> str:
    """Name rules_only and whichever variant winner() ships. Counts come from those rows."""
    baseline = dev['rules_only']
    shipped_name = winner(dev)
    shipped = dev[shipped_name]
    post = heldout[shipped_name]
    blind = _BLIND_HELDOUT_RULES_PLUS.split(' ', 1)[0]
    return (
        'Engineer-needed flag (model-checked): '
        f'rules_only {baseline.matched}/{baseline.scored} on the dev set (in-sample), '
        f'{_count_phrase(baseline.under_flag, "under-flag")}; '
        f'shipped {shipped_name}: {shipped.matched}/{shipped.scored} in-sample, '
        f'{_count_phrase(shipped.under_flag, "under-flag")}, '
        f'{_count_phrase(shipped.unknown, "unknown")} sent to the applicant; '
        f'held-out {blind} blind (pre-fix), '
        f'post-fix {post.matched}/{post.scored} (no longer blind).'
    )


def main() -> int:
    codes, codedb = load_codes()
    dev = score(codes)
    heldout = score(codes, load_heldout())
    print(headline(dev, heldout))
    print(report(dev, codedb))
    print(heldout_report(heldout))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
