"""Local subject names from sent prose or confirmed applicant facts; no model call.

A small vocabulary names a recognized subject, then falls back to building type.
Unknown subjects keep a generic label. This is deliberately conservative, not a
universal word-count rule or a clipped copy of the applicant's description.
"""
from __future__ import annotations

import re
_TYPE_VALUE = {
    'single_family': 'Single-family',
    'multi_family': 'Multi-family',
    'hotel': 'Hotel',
    'assembly': 'Assembly',
    'care': 'Care',
    'treatment': 'Treatment',
    'detention': 'Detention',
    'business': 'Business',
    'mercantile': 'Mercantile',
    'industrial': 'Industrial',
    'farm': 'Farm',
    'relocatable_industrial_camp': 'Relocatable industrial camp',
    'mixed': 'Mixed use',
}
_TYPE_PROSE = (
    (re.compile(r'\b(?:apartment|apartments|multi[- ]family)\b', re.I), 'Multi-family'),
    (re.compile(r'\bhotel\b', re.I), 'Hotel'),
    (re.compile(r'\b(?:single[- ]family|single detached|detached house|detached home|bungalow|infill house|\bhouse\b)\b', re.I), 'Single-family'),
    # Occupancy phrases only: bare "assembly", "care", "treatment", "detention", "industrial" and "farm"
    # appear in ordinary variance prose ("rated wall assembly", "take care", "stormwater detention").
    (re.compile(r'\b(?:assembly (?:occupancy|building|hall|use)|place of assembly|theatre|auditorium|arena|church)\b', re.I), 'Assembly'),
    (re.compile(r'\b(?:care (?:occupancy|facility|home)|nursing home|assisted living|long[- ]term care)\b', re.I), 'Care'),
    (re.compile(r'\b(?:treatment (?:occupancy|facility|centre|center)|hospital|clinic)\b', re.I), 'Treatment'),
    (re.compile(r'\b(?:detention (?:occupancy|facility|centre|center)|correctional (?:facility|centre|center)|jail)\b', re.I), 'Detention'),
    (re.compile(r'\b(?:mercantile|retail)\b', re.I), 'Mercantile'),
    (re.compile(r'\b(?:industrial (?:occupancy|building|facility|plant|warehouse)|factory|warehouse)\b', re.I), 'Industrial'),
    (re.compile(r'\b(?:farm (?:building|barn)|agricultural building|barn)\b', re.I), 'Farm'),
)
_OCCUPANCY_FIELDS = {'professional.occupancy', 'occupancy', 'building.occupancy', 'building.type'}
_SUBJECT_FIELDS = {'project.description', 'alternative_description'}
# Prefer the earliest recognized subject in the applicant's wording. More specific
# phrases precede their generic forms when they start at the same position.
_SUBJECTS = tuple((re.compile(pattern, re.I), label) for pattern, label in (
    (r'\b(?:exterior|external)\s+sheathing\b', 'Exterior sheathing'),
    (r'\bwall\s+sheathing\b', 'Wall sheathing'),
    (r'\binsulating\s+sheathing\b', 'Insulating sheathing'),
    (r'\bcontinuous\s+sheathing\b', 'Continuous sheathing'),
    (r'\bsheathing\b', 'Sheathing'),
    (r'\b(?:egress|escape)\s+windows?\b', 'Egress window'),
    (r'\b(?:fire[- ]?stopp?ing|fire[- ]?stops?)\b', 'Firestopping'),
    (r'\bfire[- ]rated\s+walls?\b', 'Fire-rated wall'),
    (r'\bfire[- ]rated\s+assembl(?:y|ies)\b', 'Fire-rated assembly'),
    (r'\bfire\s+separations?\b', 'Fire separation'),
    (r'\b(?:exit|egress)\s+stairs?\b', 'Exit stair'),
    (r'\b(?:staircases?|stairs?|stairways?)\b', 'Stairs'),
    (r'\bguard(?:rail)?\s+heights?\b', 'Guard height'),
    (r'\bhandrail\s+heights?\b', 'Handrail height'),
    (r'\bguardrails?\b', 'Guardrail'),
    (r'\bhandrails?\b', 'Handrail'),
    (r'\bsoffits?\b', 'Soffit'),
    (r'\b(?:barrier[- ]free|accessible)\s+entrances?\b', 'Accessible entrance'),
    (r'\b(?:barrier[- ]free|accessible)\s+routes?\b', 'Accessible route'),
    (r'\b(?:barrier[- ]free|accessible)\s+access\b', 'Accessible access'),
    (r'\bramps?\b', 'Ramp'),
    (r'\bsprinklers?\b', 'Sprinklers'),
    (r'\bfire\s+alarms?\b', 'Fire alarm'),
    (r'\bsmoke\s+alarms?\b', 'Smoke alarm'),
    (r'\bexterior\s+insulation\b', 'Exterior insulation'),
    (r'\bwall\s+insulation\b', 'Wall insulation'),
    (r'\bcontinuous\s+insulation\b', 'Continuous insulation'),
    (r'\binsulation\b', 'Insulation'),
    (r'\b(?:mass\s+timber|cross[- ]laminated\s+timber)\b', 'Mass timber'),
    (r'\broof(?:ing)?\s+(?:membranes?|assembl(?:y|ies))\b', 'Roof assembly'),
    (r'\bfoundations?\b', 'Foundation'),
    (r'\bcladding\b', 'Cladding'),
    (r'\bventilation\b', 'Ventilation'),
    (r'\b(?:exit|egress)\b', 'Egress'),
))


def normalize_title(value: str) -> str:
    """Keep custom wording and Unicode; collapse whitespace without clipping it."""
    if not isinstance(value, str):
        raise ValueError('title must be a string')
    title = ' '.join(value.split())
    if not 1 <= len(title) <= 500:
        raise ValueError('title must contain between 1 and 500 characters')
    return title


def first_sentence(text: str) -> str:
    trimmed = ' '.join((text or '').split())
    if not trimmed:
        return ''
    return re.split(r'(?<=[.!?])\s+', trimmed, maxsplit=1)[0]


def title_should_replace(title: str | None, prose: str, generated: str | None = None, *, manual: bool = False) -> bool:
    """Replace a blank title, one Batatis generated earlier (`generated`), or the description's first sentence.

    The persisted manual marker wins even if the text equals an old automatic name.
    Old serialized cases keep the original conservative replacement heuristic.
    """
    if manual:
        return False
    if title is None or not str(title).strip():
        return True
    current = ' '.join(str(title).split())
    if generated and current == ' '.join(generated.split()):
        return True
    first = first_sentence(prose)
    if current == first:
        return True
    if len(first) > 72 and current == f'{first[:69]}…':
        return True
    prose_flat = ' '.join((prose or '').split())
    return bool(prose_flat) and current == prose_flat


def _accepted_facts(facts) -> list[dict]:
    latest = {}
    for fact in facts or []:
        row = fact.model_dump() if hasattr(fact, 'model_dump') else fact
        latest[row.get('field')] = row
    return [row for row in latest.values() if row.get('status') == 'confirmed' and row.get('kind') != 'proposed'
            and (row.get('source') or {}).get('type') in {'user_text', 'user_click', 'file', 'drawing'}]


def _building_type(prose: str, facts) -> str | None:
    for fact in facts or []:
        name = fact.field if hasattr(fact, 'field') else fact.get('field')
        if name not in _OCCUPANCY_FIELDS:
            continue
        value = fact.value if hasattr(fact, 'value') else fact.get('value')
        label = _TYPE_VALUE.get(str(value))
        if label:
            return label
    for pattern, label in _TYPE_PROSE:
        if pattern.search(prose or ''):
            return label
    return None


def short_title(prose: str, facts, result: dict | None) -> str:
    """Name the applicant's subject; `result` remains accepted for legacy callers.

    Identification output is deliberately not naming input: an offered code topic
    or unaccepted suggestion is not the applicant's project identity.
    """
    accepted = _accepted_facts(facts)
    blobs = [prose or '', *(row['value'] for row in accepted
                           if row.get('field') in _SUBJECT_FIELDS and isinstance(row.get('value'), str))]
    for blob in blobs:
        matches = [(match.start(), order, label) for order, (pattern, label) in enumerate(_SUBJECTS)
                   if (match := pattern.search(blob))]
        if matches:
            return min(matches)[2]
    kind = _building_type(' '.join(blobs), accepted)
    return kind or 'Variance application'
