"""Deterministic numeric requirement on one codedb sentence.

A requirement is a number and a unit tied to a phrase such as "not less than".
The sentence is used only when codedb supplied it. A model quote is never parsed.
Several requirements leave the required value empty unless accepted facts match
exactly one of those units.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_WS = re.compile(r'\s+')
_PHRASE = (
    r'not\s+less\s+than|not\s+more\s+than|no\s+\w+\s+less\s+than|'
    r'at\s+least|at\s+most|greater\s+than|less\s+than|more\s+than'
)
_UNIT = r'mm²|mm2|m²|m2|cm|mm|kPa|MPa|kN|%|m'
_REQUIREMENT = re.compile(rf'(?i)(?:{_PHRASE})\s+(\d+(?:\.\d+)?)\s*({_UNIT})')
_FACT_VALUE = re.compile(rf'(?i)^\s*(\d+(?:\.\d+)?)\s*({_UNIT})\s*$')
SNIPPET_WORDS = 25


def _flat(text: str | None) -> str:
    return _WS.sub(' ', text or '').strip()


def _unit_key(unit: str) -> str:
    return unit.replace('²', '2').replace(' ', '').casefold()


def _number(token: str) -> int | float:
    value = Decimal(token)
    if value == value.to_integral():
        return int(value)
    return float(value)


def _phrase(match: re.Match, limit: int = SNIPPET_WORDS) -> str:
    words = match.group(0).split()
    return ' '.join(words[:limit])


def parse_requirements(text: str | None) -> list[dict]:
    """Every numeric requirement in one sentence, in order. Empty when there are none."""
    flat = _flat(text)
    found = []
    for match in _REQUIREMENT.finditer(flat):
        try:
            value = _number(match.group(1))
        except InvalidOperation:
            continue
        unit = match.group(2)
        found.append({
            'value': value,
            'unit': unit,
            'unit_key': _unit_key(unit),
            'snippet': _phrase(match),
        })
    return found


def _accepted_numbers(facts) -> list[dict]:
    """Confirmed facts whose value is one number and one unit. Proposed facts cannot be confirmed."""
    numbers = []
    for fact in facts or []:
        if hasattr(fact, 'status'):
            status, field, value, fact_id = fact.status, fact.field, fact.value, fact.id
        elif isinstance(fact, dict):
            status = fact.get('status')
            field = fact.get('field') or ''
            value = fact.get('value')
            fact_id = fact.get('id')
        else:
            continue
        if status != 'confirmed' or not fact_id:
            continue
        if str(field).startswith(('citation.', 'open_question.')):
            continue
        if not isinstance(value, str):
            continue
        match = _FACT_VALUE.match(value)
        if not match:
            continue
        try:
            number = _number(match.group(1))
        except InvalidOperation:
            continue
        unit = match.group(2)
        numbers.append({
            'id': fact_id,
            'value': number,
            'unit': unit,
            'unit_key': _unit_key(unit),
        })
    return numbers


def _select(requirements: list[dict], accepted: list[dict]) -> dict | None:
    """One requirement. Several stay unresolved unless one unit is the only fact match."""
    if len(requirements) == 1:
        return requirements[0]
    if not requirements:
        return None
    by_unit: dict[str, list[dict]] = {}
    for item in requirements:
        by_unit.setdefault(item['unit_key'], []).append(item)
    chosen = []
    for fact in accepted:
        group = by_unit.get(fact['unit_key']) or []
        if len(group) == 1 and group[0] not in chosen:
            chosen.append(group[0])
    if len(chosen) == 1:
        return chosen[0]
    return None


def benchmark(provision_id: str | None, sentence: str | None, facts) -> dict | None:
    """Comparison object, or null when the sentence text is not from codedb."""
    if not provision_id or not _flat(sentence):
        return None
    requirements = parse_requirements(sentence)
    accepted = _accepted_numbers(facts)
    selected = _select(requirements, accepted)
    required_value = selected['value'] if selected else None
    required_unit = selected['unit'] if selected else None
    snippet = selected['snippet'] if selected else None
    proposed_value = proposed_unit = fact_id = None
    if selected is not None:
        matches = [item for item in accepted if item['unit_key'] == selected['unit_key']]
        if len(matches) == 1:
            proposed_value = matches[0]['value']
            proposed_unit = matches[0]['unit']
            fact_id = matches[0]['id']
    comparison = None
    if required_value is not None and proposed_value is not None and _unit_key(required_unit) == _unit_key(proposed_unit):
        required = Decimal(str(required_value))
        proposed = Decimal(str(proposed_value))
        if proposed == required:
            comparison = 'equal'
        elif proposed < required:
            comparison = 'below'
        else:
            comparison = 'above'
    return {
        'provision_id': provision_id,
        'requirement_snippet': snippet,
        'required_value': required_value,
        'required_unit': required_unit,
        'proposed_value': proposed_value,
        'proposed_unit': proposed_unit,
        'fact_id': fact_id,
        'comparison': comparison,
    }
