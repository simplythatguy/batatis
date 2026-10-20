"""Short case title: building type, place, and one real provision.

The title is not the first sentence of the description, and it does not say the
design complies or is safe. A provision id is copied from the identify result.
"""
from __future__ import annotations

import re

_BANNED = re.compile(r'\b(?:complies|compliant|compliance|safe)\b', re.I)
_ARTICLE = re.compile(r'^\d+(?:\.\d+){3}\.$')
_SENTENCE = re.compile(r'^\d+(?:\.\d+){3}\.\(\d+\)$')
_CITIES = (
    'Edmonton', 'Calgary', 'Red Deer', 'Lethbridge', 'Medicine Hat', 'Grande Prairie',
    'Airdrie', 'Spruce Grove', 'St. Albert', 'Fort McMurray', 'Leduc', 'Okotoks',
    'Cochrane', 'Chestermere', 'Camrose', 'Brooks', 'Wetaskiwin', 'Lloydminster',
    'Canmore', 'Banff', 'Jasper', 'Cold Lake', 'High River', 'Strathmore',
)
_CITY = re.compile(r'\b(' + '|'.join(re.escape(name) for name in _CITIES) + r')\b', re.I)
_CITY_CANON = {name.casefold(): name for name in _CITIES}
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
    'other': 'Other',
}
_TYPE_PROSE = (
    (re.compile(r'\b(?:apartment|apartments|multi[- ]family)\b', re.I), 'Multi-family'),
    (re.compile(r'\bhotel\b', re.I), 'Hotel'),
    (re.compile(r'\b(?:single[- ]family|single detached|detached house|detached home|bungalow|infill house|\bhouse\b)\b', re.I), 'Single-family'),
    (re.compile(r'\bassembly\b', re.I), 'Assembly'),
    (re.compile(r'\bcare\b', re.I), 'Care'),
    (re.compile(r'\btreatment\b', re.I), 'Treatment'),
    (re.compile(r'\bdetention\b', re.I), 'Detention'),
    (re.compile(r'\b(?:mercantile|retail)\b', re.I), 'Mercantile'),
    (re.compile(r'\bindustrial\b', re.I), 'Industrial'),
    (re.compile(r'\bfarm\b', re.I), 'Farm'),
)
_OCCUPANCY_FIELDS = {'professional.occupancy', 'occupancy', 'building.occupancy', 'building.type'}
_PLACE_FIELDS = {'municipalAddress', 'site.city', 'site.address', 'building.address', 'site.location'}


def first_sentence(text: str) -> str:
    trimmed = ' '.join((text or '').split())
    if not trimmed:
        return ''
    return re.split(r'(?<=[.!?])\s+', trimmed, maxsplit=1)[0]


def title_should_replace(title: str | None, prose: str) -> bool:
    """Replace a blank title, or one that is just the description's first sentence."""
    if title is None or not str(title).strip():
        return True
    current = ' '.join(str(title).split())
    first = first_sentence(prose)
    if current == first:
        return True
    if len(first) > 72 and current == f'{first[:69]}…':
        return True
    prose_flat = ' '.join((prose or '').split())
    return bool(prose_flat) and current == prose_flat


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


def _place(prose: str, facts) -> str | None:
    blobs = [prose or '']
    for fact in facts or []:
        name = fact.field if hasattr(fact, 'field') else fact.get('field')
        if name in _PLACE_FIELDS:
            value = fact.value if hasattr(fact, 'value') else fact.get('value')
            blobs.append('' if value is None else str(value))
    for blob in blobs:
        match = _CITY.search(blob)
        if match:
            return _CITY_CANON[match.group(1).casefold()]
    return None


def _real_id(value) -> str | None:
    if isinstance(value, str) and (_SENTENCE.match(value) or _ARTICLE.match(value)):
        return value
    return None


def _topic(title: str | None) -> str | None:
    words = []
    for word in re.sub(r'[^A-Za-z0-9/-]+', ' ', title or '').split():
        if _BANNED.search(word):
            continue
        words.append(word)
    if not words:
        return None
    return ' '.join(words[:4]).lower()


def _provision(result: dict) -> tuple[str | None, str | None]:
    articles = [row for row in (result.get('articles') or []) if isinstance(row, dict)]
    benchmark = result.get('benchmark') if isinstance(result.get('benchmark'), dict) else {}
    chosen = None
    target = benchmark.get('provision') if benchmark.get('identified') else None
    if target:
        for article in articles:
            if article.get('provision') == target or article.get('provision_id') == target:
                chosen = article
                break
        if chosen is None:
            chosen = {'provision': target, 'title': None}
    elif articles:
        chosen = articles[0]
    if not chosen:
        return None, None
    shown = _real_id(chosen.get('provision_id')) or _real_id(chosen.get('provision')) or _real_id(target)
    return shown, _topic(chosen.get('title'))


def _clean(title: str) -> str:
    cleaned = _BANNED.sub('', title)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\s+([,:])', r'\1', cleaned)
    cleaned = re.sub(r'([,:])(?:\s*[:,])+', r'\1', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,:-')
    return cleaned


def short_title(prose: str, facts, result: dict | None) -> str:
    """'Single-family, Edmonton: 9.9.10.1.(2) egress window' when those parts are known."""
    kind = _building_type(prose, facts)
    place = _place(prose, facts)
    provision, topic = _provision(result or {})
    head = ', '.join(part for part in (kind, place) if part)
    tail = ' '.join(part for part in (provision, topic) if part)
    if head and tail:
        title = f'{head}: {tail}'
    else:
        title = head or tail or 'Variance application'
    return _clean(title)
