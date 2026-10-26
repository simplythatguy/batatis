"""Evaluate narrow Part 9 entry conditions using current facts and exact source text.

No prose keyword chooses a building Part. Missing/unconfirmed/conflicting facts
stay unresolved; candidates invoked by cross-reference are never deleted here.
"""
from __future__ import annotations

import math
import re

from engine.models_scope import PartScopeAssessment, ScopeBasis, ScopeCondition

_ALIASES = {'storeys': {'storeys', 'building.storeys'},
            'building_area_m2': {'building_area_m2', 'building.area_m2'},
            'occupancy': {'occupancy', 'building.occupancy', 'professional.occupancy'}}


def _value(facts, name):
    # The caller supplies active facts, including any unresolved newer reading.
    rows = [f for f in facts if f.field in _ALIASES[name] and f.value not in (None, '')]
    values = {(type(f.value).__name__, str(f.value)) for f in rows}
    if len(values) > 1:
        return rows, 'conflict'
    if not rows or any(f.status != 'confirmed' or f.kind == 'proposed' for f in rows):
        return rows, 'unknown'
    return rows, None


def _number(value):
    if type(value) is bool:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def assess(codes, facts, result=None):
    assessment = PartScopeAssessment()
    # These provision identities were verified against the local second printing.
    # Evaluate the rule only while its expected condition text is present.
    record = codes.provision('1.3.3.3.(1)', 'A')
    if not record or 'NBC(AE) 2023 p2' not in (record.get('citation') or ''):
        return [assessment]
    text = ' '.join((record.get('text') or '').split())
    height = re.search(r'(\d+) storeys or less in building height', text)
    area = re.search(r'building area not exceeding (\d+) m²', text)
    if not height or not area or not all(term in text for term in (
            'Group B, Division 4', 'Group C', 'Group D', 'Group E', 'Group F, Divisions 2 and 3')):
        return [assessment]
    assessment.basis = [ScopeBasis(provision_id=record['id'], citation=record['citation'], quote=record['text'])]
    thresholds = {'storeys': int(height[1]), 'building_area_m2': int(area[1])}
    for name, threshold in thresholds.items():
        rows, status = _value(facts, name)
        value = _number(rows[-1].value) if rows and status is None else None
        if name == 'storeys' and value is not None and (value < 1 or not value.is_integer()):
            value = None
        status = status or ('unknown' if value is None else 'met' if value <= threshold else 'not_met')
        assessment.conditions.append(ScopeCondition(field=name, status=status, values=[f.value for f in rows],
            fact_ids=[f.id for f in rows], explanation=f'The source condition is {name} at most {threshold}; '
                        'only a confirmed numeric value can evaluate it.'))
    rows, status = _value(facts, 'occupancy')
    # Only a supplied classification evaluates this gate; "house" is not one.
    value = str(rows[-1].value).strip().upper() if rows and status is None else ''
    group = re.fullmatch(r'(?:GROUP\s+)?([A-F])(?:\s*[,/-]?\s*(?:DIVISION\s*)?([1-4]))?', value)
    allowed = {('B', '4'), ('C', None), ('D', None), ('E', None), ('F', '2'), ('F', '3')}
    status = status or ('unknown' if not group else 'met' if (group[1], group[2]) in allowed else 'not_met')
    assessment.conditions.append(ScopeCondition(field='occupancy', status=status, values=[f.value for f in rows],
        fact_ids=[f.id for f in rows], explanation='Evaluate the supplied major-occupancy classification '
            'against the groups in the source sentence; an everyday building description is insufficient.'))
    states = {c.status for c in assessment.conditions}
    if 'not_met' in states:
        assessment.status = 'boundary_not_met'
    elif states == {'met'}:
        assessment.status = 'conditions_met_scope_unresolved'
    if result is not None and assessment.status == 'boundary_not_met':
        fields = ', '.join(c.field for c in assessment.conditions if c.status == 'not_met')
        explanation = ('Confirmed input does not meet the ordinary Part 9 entry condition for ' + fields
                       + '; retain any cross-referenced details and review their applicability against '
                       + record['citation'] + '.')
        for item in result.requirements:
            if item.division == 'B' and item.provision_id and item.provision_id.startswith('9.'):
                if explanation not in item.review_reasons:
                    item.review_reasons.append(explanation)
                if item.disposition == 'include':
                    item.applicability, item.needs_review, item.disposition = 'needs_review', True, 'review'
    return [assessment]
