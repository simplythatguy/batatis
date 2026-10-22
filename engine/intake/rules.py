"""Deterministic first pass: facts the applicant's own words state, each with its exact span.

Base: PR #36 (`fact_extraction.py`), generalised past its demo personas (no product names, no
city literals), with PR #30's number words, feet and square feet folded in through `text.py`.
A rule reads one sentence at a time and records the tight phrase that states the value. Two
different values for one field are a conflict: no fact, and the field is asked instead.
Questions to the tool ("Can we ...?") are never read as facts.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from codedb.ids import canon

from ..redact import STREET
from .text import FT_TO_M, NUMBER, SQFT_TO_M2, is_question, number, rounded, sentence_at, sentences

ROLES = ('owner', 'designer', 'architect-engineer', 'contractor', 'homebuilder', 'manufacturer')
OCCUPANCIES = ('single_family', 'multi_family', 'hotel', 'assembly', 'care', 'treatment', 'detention',
               'business', 'mercantile', 'industrial', 'farm', 'relocatable_industrial_camp', 'mixed')
SPRINKLERED = ('yes', 'no', 'partial')

# Field vocabulary: label and value type. Section A/B names are the SCC export keys
# (engine/export/field_maps); building names are the ones the professional screen reads.
FIELDS: dict[str, tuple[str, str]] = {
    'applicant_role': ('Who is applying', 'enum'),
    'owner_name': ("Owner's name", 'text'),
    'owner_rep_name': ("Owner's representative", 'text'),
    'mailing_address': ('Mailing address', 'text'),
    'municipal_address': ('Municipal address', 'text'),
    'legal_description': ('Legal description', 'text'),
    'lot': ('Lot', 'text'), 'block': ('Block', 'text'), 'plan': ('Plan', 'text'),
    'ats_qtr': ('ATS quarter', 'text'), 'ats_sec': ('ATS section', 'text'), 'ats_twp': ('ATS township', 'text'),
    'ats_rge': ('ATS range', 'text'), 'ats_mer': ('ATS meridian', 'text'),
    'permit_number': ('Permit number', 'text'),
    'request_date': ('Date of request', 'text'),
    'municipality': ('Municipality', 'text'),
    'scope': ('Site or jurisdiction-wide', 'enum'),
    'storeys': ('Storeys', 'int'),
    'building_area_m2': ('Building area (m²)', 'number'),
    'floor_area_m2': ('Floor area per storey (m²)', 'number'),
    'dwelling_units': ('Dwelling units', 'int'),
    'occupancy': ('Occupancy', 'enum'),
    'sprinklered': ('Sprinklered', 'enum'),
    'building_height_m': ('Building height (m)', 'number'),
    'top_floor_height_m': ('Top floor above grade (m)', 'number'),
    'limiting_distance_m': ('Distance to the property line (m)', 'number'),
    'span_m': ('Structural span (m)', 'number'),
    'part4_design': ('Designed under Part 4', 'bool'),
    'alternative_description': ('Proposed alternative', 'text'),
    'claimed_provision': ('Article the applicant named', 'text'),
}
ENUMS = {'applicant_role': ROLES, 'occupancy': OCCUPANCIES, 'sprinklered': SPRINKLERED,
         'scope': ('site', 'jurisdiction')}
PERSONAL = frozenset({'owner_name', 'owner_rep_name', 'mailing_address', 'municipal_address', 'legal_description',
                      'lot', 'block', 'plan', 'ats_qtr', 'ats_sec', 'ats_twp', 'ats_rge', 'ats_mer',
                      'permit_number'})


@dataclass(frozen=True)
class Hit:
    """A value and the span of the words that state it. `raw` is set for a unit conversion:
    (field, value as written, formula); the stored fact is then `computed` from a pointed one."""
    field: str
    value: str | int | float | bool
    start: int
    end: int
    confidence: float = 0.9
    raw: tuple[str, int | float, str] | None = None


@dataclass
class Reading:
    hits: list[Hit] = field(default_factory=list)
    conflicts: dict[str, list[Hit]] = field(default_factory=dict)   # field -> the disagreeing hits
    citations: list[tuple[str, int, int]] = field(default_factory=list)


_HEDGE = re.compile(r"(?i)\b(?:i think|not sure|maybe|probably|roughly|i believe|might be)\b")
_NEGATED_VALUE = re.compile(r'(?i)^(?:n/?a|none|unknown|tbd|tba|to follow|to be confirmed|pending|not (?:yet|known|sure|applied)'
                            r"|don'?t know|do not know|-+|\?+)\b")


def _sub(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


# ---------------------------------------------------------------- building facts

_STOREY = _sub(rf'\b(?P<n>{NUMBER})[\s-]*(?:storeys?|stories|story)\b')
_ONE_STOREY = _sub(r'\b(?:single|one)[\s-]storey\b|\bbungalows?\b')
_STOREY_SKIP = _sub(r'\b(?:not|under|over|up to|more than|less than|fewer than|at most|at least|maximum|max\.?|below)'
                    r'\s+(?:a\s+)?$')
_ADDED = _sub(r'\b(?:add|adding|added|addition of|extra|another)\b[^.]{0,30}\b(?:floors?|storeys?)\b')


def _storeys(sentence: str, at: int) -> list[Hit]:
    hits = []
    if _ADDED.search(sentence):
        # "adding two floors to a one-storey warehouse": the count after the work is not stated.
        found = [m for m in _STOREY.finditer(sentence)] + [m for m in _ONE_STOREY.finditer(sentence)]
        return [Hit('storeys', -1, at + m.start(), at + m.end(), 0.0) for m in found[:1]]
    for match in _STOREY.finditer(sentence):
        if _STOREY_SKIP.search(sentence[:match.start()]) or re.match(r'\s+of\s+travel', sentence[match.end():]):
            continue
        value = number(match.group('n'))
        if isinstance(value, int) and 1 <= value <= 120:
            hits.append(Hit('storeys', value, at + match.start(), at + match.end()))
    for match in _ONE_STOREY.finditer(sentence):
        hits.append(Hit('storeys', 1, at + match.start(), at + match.end()))
    return hits


_M2 = r'(?:m²|m2\b|m\^2|sq\.?\s?m(?:etres?|eters?)?\b|square\s+met(?:re|er)s?\b)'
_FT2 = r'(?:sq\.?\s?ft\.?|square\s+f(?:ee|oo)t\b|ft²|ft2\b|sf\b)'
_AREA = _sub(rf'(?<![\w/(.])(?P<n>\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<u>{_M2}|{_FT2})')
_PER_FLOOR_AFTER = _sub(r'^\s*(?:per|each|a|on each|for each|of each)\s+(?:floor|storey|level)\b|^\s*floors?\b')
_PER_FLOOR_BEFORE = _sub(r'\b(?:each|per|every|typical)\s+(?:floor|storey|level)\b[^,;]{0,25}$|\bfloor\s+area\b[^,;]{0,15}$'
                         r'|\bfloor\s+plate\b[^,;]{0,15}$')
_NOT_BUILDING = _sub(r'\b(?:lot|parcel|site|yard|wall|opening|glazing|window|roof|deck|panel|room)\s+(?:area\s+)?'
                     r'(?:of|is|was|about|approximately|totals?)?\s*(?:about\s+|approximately\s+)?$')
_BUILDING_AREA_CUE = _sub(r'\bbuilding\s+area\b')


def _areas(sentence: str, at: int) -> list[Hit]:
    hits = []
    for match in _AREA.finditer(sentence):
        before, after = sentence[:match.start()], sentence[match.end():]
        if _NOT_BUILDING.search(before[-30:]):
            continue
        per_floor = bool(_PER_FLOOR_AFTER.search(after) or _PER_FLOOR_BEFORE.search(before))
        name = 'floor_area_m2' if per_floor else 'building_area_m2'
        written = number(match.group('n'))
        confidence = 0.9 if per_floor or _BUILDING_AREA_CUE.search(sentence) else 0.7
        if re.search(_FT2, match.group('u'), re.I):
            converted = rounded(written * SQFT_TO_M2)
            raw = (name.replace('_m2', '_ft2'), written, f'{written} sq ft × {SQFT_TO_M2} = {converted} m²')
            hits.append(Hit(name, converted, at + match.start(), at + match.end(), confidence, raw))
        else:
            hits.append(Hit(name, written, at + match.start(), at + match.end(), confidence))
    return hits


_UNITS = _sub(rf'\b(?P<n>{NUMBER})[\s-]+(?:dwelling[\s-]+units?|residential\s+units?|units?|apartments?|dwellings?'
              r'|condo(?:minium)?s?|townhouses?|suites?\s+in\s+total)\b')
_PER_FLOOR_UNITS = _sub(r'^\s*(?:per|on each|on every|each)\s+(?:floor|storey|level)\b')


def _dwelling_units(sentence: str, at: int) -> list[Hit]:
    hits = []
    for match in _UNITS.finditer(sentence):
        if _PER_FLOOR_UNITS.search(sentence[match.end():]):
            continue
        value = number(match.group('n'))
        if value == 1 and not match.group('n').isdigit():
            continue                                 # "one dwelling" is a reference, rarely a count
        if isinstance(value, int) and 1 <= value <= 5000:
            hits.append(Hit('dwelling_units', value, at + match.start(), at + match.end()))
    return hits


_OCCUPANCY = (
    ('single_family', _sub(r'\bsingle[-\s]?family\b|\bsingle[-\s]detached\b|\bdetached\s+(?:house|home|dwelling)s?\b'
                           r'|\bbungalows?\b|\b(?:garden|garage|laneway)\s+suites?\b'
                           r'|(?<![-\w])(?:house|home)s?\b(?!-)')),
    ('multi_family', _sub(r'\bapartments?\b|\bcondo(?:minium)?s?\b|\btownhouses?\b|\brow\s+houses?\b|\bduplex\b'
                          r'|\btriplex\b|\bfourplex\b|\bsemi[-\s]detached\b|\bmulti[-\s]?family\b|\bwalk[-\s]up\b'
                          r'|\bmulti[-\s]unit\s+residential\b'
                          rf'|\b(?:{NUMBER})[\s-]+dwelling[\s-]+units\b')),
    ('business', _sub(r'(?<!bedroom and )(?<!home )(?<!and an )(?<!and a )\boffices?\b(?!\s+room)'
                      r'|\bbusiness\s+occupancy\b')),
    ('mercantile', _sub(r'\bretail\b|\bmercantile\b|\bshopping\s+(?:centre|center|mall)\b|\bstores?\b(?=\s+building)')),
    ('assembly', _sub(r'\barenas?\b|\bcommunity\s+(?:hall|centre|center)\b|\blibrar(?:y|ies)\b|\bchurch(?:es)?\b'
                      r'|\btheat(?:re|er)s?\b|\bassembly\s+(?:occupancy|hall|building)\b|\bschools?\b|\bgymnasium\b'
                      r'|\brecreation\s+(?:centre|center)\b')),
    ('industrial', _sub(r'(?<!-)\bwarehouses?\b(?!-)|(?<!relocatable )\bindustrial\s+(?:building|occupancy|park|facility)\b')),
    ('care', _sub(r'\bnursing\s+homes?\b|\bcare\s+(?:home|facility|occupancy)\b|\bgroup\s+homes?\b'
                  r'|\blong[-\s]term\s+care\b|\bassisted\s+living\b')),
    ('treatment', _sub(r'\bhospitals?\b|\btreatment\s+occupancy\b')),
    ('detention', _sub(r'\bjails?\b|\bprisons?\b|\bdetention\b')),
    ('hotel', _sub(r'\bhotels?\b|\bmotels?\b')),
    ('farm', _sub(r'\bbarns?\b|\bfarm\s+buildings?\b')),
    ('relocatable_industrial_camp', _sub(r'\brelocatable\s+industrial\s+camps?\b')),
    ('mixed', _sub(r'\bmixed[-\s]use\b')),
)
# Words that contain an occupancy word but name something else.
# "Larkspur Example Homes", "Acme Home Builders Ltd.": a capitalized Home(s) inside a company name is not the building.
_COMPANY_HOME = re.compile(r"[A-Z][\w'&.-]*\s+$")
_COMPANY_AFTER = re.compile(r"\s+(?:[A-Z][\w'&.-]*\s+)*(?:Ltd|Inc|Corp|LLC|Limited|Builders|Construction|Group)\b\.?")
_OCCUPANCY_SKIP = _sub(r'\b(?:nursing|care|group|tiny|pool|green|ware|town|row|club|field|open)\s*$')


def _occupancy(sentence: str, at: int) -> list[Hit]:
    hits = []
    for name, pattern in _OCCUPANCY:
        for match in pattern.finditer(sentence):
            if name == 'single_family' and _OCCUPANCY_SKIP.search(sentence[:match.start()]):
                continue
            word = match.group(0)
            if name == 'single_family' and word[:1] == 'H' and word.lower().startswith(('home', 'house')) and (
                    _COMPANY_HOME.search(sentence[:match.start()]) or _COMPANY_AFTER.match(sentence[match.end():])):
                continue                             # a company name, not the building's use
            if re.search(r"(?i)\b(?:not|isn'?t|never)\s+(?:an?\s+|the\s+)?$", sentence[:match.start()]):
                continue
            confidence = 0.6 if name == 'single_family' and match.group(0).lower().startswith(('house', 'home')) else 0.85
            hits.append(Hit('occupancy', name, at + match.start(), at + match.end(), confidence))
    return hits


_SPRINKLER_NO = _sub(r'\b(?:not|non)[\s-]?sprinklered\b|\bunsprinklered\b|\b(?:no|without)\s+sprinklers?\b')
_SPRINKLER_PART = _sub(r'\bpartial(?:ly)?[\s-]+sprinklered\b')
_SPRINKLER_YES = _sub(r'(?<![-\w])(?:fully\s+)?sprinklered\b(?:\s+throughout)?')
_CONDITIONAL = _sub(r'\b(?:if|whether|unless|or not)\b')


def _sprinklered(sentence: str, at: int) -> list[Hit]:
    if _CONDITIONAL.search(sentence) and not _SPRINKLER_NO.search(sentence):
        return []
    hits, taken = [], []
    for value, pattern in (('no', _SPRINKLER_NO), ('partial', _SPRINKLER_PART), ('yes', _SPRINKLER_YES)):
        for match in pattern.finditer(sentence):
            if any(a <= match.start() < b for a, b in taken):
                continue
            if value == 'yes' and re.search(r'(?i)\b(?:not|non|un|partially|partial)[\s-]*$', sentence[:match.start()]):
                continue
            taken.append((match.start(), match.end()))
            hits.append(Hit('sprinklered', value, at + match.start(), at + match.end()))
    return hits


_LEN_UNIT = r'(?P<u>mm|millimet(?:re|er)s?|m|met(?:re|er)s?|ft|feet|foot)\b'
_HALF = r'(?P<half>half\s+a\s+met(?:re|er))'
_DISTANCE = _sub(rf'(?:\b(?P<n>{NUMBER})\s*{_LEN_UNIT}|\b{_HALF}\b)\s+(?:away\s+)?from\s+the\s+(?:[\w-]+\s+){{0,4}}?'
                 r'(?:side\s+|rear\s+|front\s+)?(?:property|lot)\s+line')
_LD = _sub(rf'\blimiting\s+distance\s+(?:of\s+|is\s+|=\s*)?(?:about\s+|only\s+|approximately\s+)?'
           rf'(?P<n>{NUMBER})\s*{_LEN_UNIT}')


def _metres(match: re.Match, name: str, at: int, confidence: float = 0.9) -> Hit | None:
    if match.groupdict().get('half'):
        return Hit(name, 0.5, at + match.start(), at + match.end(), 0.8)
    written = number(match.group('n'))
    if written is None:
        return None
    unit = match.group('u').lower()
    if unit.startswith(('ft', 'feet', 'foot')):
        value = rounded(written * FT_TO_M)
        return Hit(name, value, at + match.start(), at + match.end(), confidence,
                   (name.replace('_m', '_ft'), written, f'{written} ft × {FT_TO_M} = {value} m'))
    if unit.startswith(('mm', 'millim')):
        value = rounded(written / 1000)
        return Hit(name, value, at + match.start(), at + match.end(), confidence,
                   (name.replace('_m', '_mm'), written, f'{written} mm ÷ 1000 = {value} m'))
    return Hit(name, written, at + match.start(), at + match.end(), confidence)


def _distances(sentence: str, at: int) -> list[Hit]:
    hits = [_metres(m, 'limiting_distance_m', at) for m in _LD.finditer(sentence)]
    hits += [_metres(m, 'limiting_distance_m', at, 0.75) for m in _DISTANCE.finditer(sentence)]
    if re.search(r'(?i)\bfrom\s+\d[\d.]*\s*m\s+to\s+\d', sentence):
        return []                                    # a skewed wall: several distances, none is "the" one
    return [hit for hit in hits if hit is not None]


_TOP_FLOOR = _sub(rf'\b(?:floor|storey)\b[^.,;]{{0,30}}?\b(?P<n>\d+(?:\.\d+)?)\s*{_LEN_UNIT}\s+above\s+(?:grade|ground)')
_HEIGHT = _sub(rf'\b(?P<n>\d+(?:\.\d+)?)\s*{_LEN_UNIT}\s+(?:tall|high)\b(?!\s+(?:wall|fence|parapet|guard))'
               rf'|\b(?:an?|the)\s+(?P<n2>\d+(?:\.\d+)?)\s*(?P<u2>m|met(?:re|er)s?)\s+(?:[\w-]+\s+)?(?:tower|building)\b'
               rf'|\bbuilding\s+height\s+(?:of\s+|is\s+)?(?P<n3>\d+(?:\.\d+)?)\s*(?P<u3>m|met(?:re|er)s?)\b')


def _heights(sentence: str, at: int) -> list[Hit]:
    hits = [_metres(m, 'top_floor_height_m', at) for m in _TOP_FLOOR.finditer(sentence)]
    for match in _HEIGHT.finditer(sentence):
        if match.group('n2') or match.group('n3'):
            raw = match.group('n2') or match.group('n3')
            span = match.span('n2') if match.group('n2') else match.span('n3')
            end = match.end('u2') if match.group('n2') else match.end('u3')
            hits.append(Hit('building_height_m', number(raw), at + span[0], at + end))
        else:
            hits.append(_metres(match, 'building_height_m', at))
    return [hit for hit in hits if hit is not None]


_SPAN = _sub(rf'\b(?:clear[-\s])?span(?:s|ning)?\b(?:\s+(?:of|is|about|approximately|roughly))*\s+(?P<n>{NUMBER})[\s-]*{_LEN_UNIT}'
             rf'|\b(?P<n2>{NUMBER})[\s-]*(?P<u2>m|met(?:re|er)s?|ft|feet|foot)\b(?:\s+[\w-]+){{0,3}}?\s+(?:clear[-\s])?span\b')


def _spans(sentence: str, at: int) -> list[Hit]:
    hits = []
    for match in _SPAN.finditer(sentence):
        if match.group('n2'):
            written, unit = number(match.group('n2')), match.group('u2').lower()
            start, end = match.start('n2'), match.end('u2')
        else:
            written, unit = number(match.group('n')), match.group('u').lower()
            start, end = match.start(), match.end()
        if written is None or unit.startswith(('mm', 'millim')):
            continue
        if unit.startswith(('ft', 'feet', 'foot')):
            value = rounded(written * FT_TO_M)
            hits.append(Hit('span_m', value, at + start, at + end, 0.85, ('span_ft', written, f'{written} ft × {FT_TO_M} = {value} m')))
        else:
            hits.append(Hit('span_m', written, at + start, at + end, 0.85))
    return hits


_PART4 = _sub(r'\bPart\s*4\b')
_DESIGN = _sub(r'\b(?:design|designed|designing|structural|engineered|analysis)\b')
_NEGATION = _sub(r"\b(?:without|not|no|never|instead of|rather than|avoid|don't|do not)\b")


def _part4(sentence: str, at: int) -> list[Hit]:
    hits = []
    for match in _PART4.finditer(sentence):
        clause_start = max(sentence.rfind(',', 0, match.start()), sentence.rfind(';', 0, match.start())) + 1
        clause = sentence[clause_start:match.end() + 30]
        if not _DESIGN.search(sentence) or _NEGATION.search(clause):
            continue
        hits.append(Hit('part4_design', True, at + match.start(), at + match.end(), 0.85))
    return hits


# ---------------------------------------------------------------- who is applying

_ROLE_CUES = (
    ('manufacturer', _sub(r"\bwe\s+(?:manufacture|make|produce|fabricate)\b|\bwe(?:'re| are)\s+(?:the\s+)?manufacturers?\b"
                          r'|\bwe\s+(?:want\s+to\s+)?supply\b|\bwe\s+are\s+supplying\b|\bwe\s+build\s+factory\b'
                          r'|\bour\s+product\b|\bour\s+(?:[\w-]+\s+){0,2}(?:board|membrane|panel)\s+is\b')),
    ('contractor', _sub(r"^(?:(?:i am|i'm|we are|we're)\s+)?(?:an?\s+|the\s+)?(?:[\w-]+\s+){0,2}contractors?\b"
                        r"|\b(?:i am|i'm|we are|we're)\s+(?:an?\s+|the\s+)?(?:[\w-]+\s+)?contractors?\b")),
    ('homebuilder', _sub(r"\b(?:i am|i'm|we are|we're)\s+(?:an?\s+|the\s+)?(?:home\s*)?builders?\b|\bhome\s*builders?\s+here\b"
                         r'|\bour\s+next\s+phase\s+of\b')),
    ('architect-engineer', _sub(r"\b(?:i am|i'm)\s+(?:an?\s+|the\s+)?(?:[\w-]+\s+)?(?:architect|engineer)\b"
                                r'|^(?:the\s+)?(?:[\w-]+\s+)?(?:architect|engineer)(?=\s+(?:on|for|of record|carrying)\b)')),
    ('designer', _sub(r"\b(?:i am|i'm)\s+(?:an?\s+|the\s+)?designer\b|^designer(?=\s+(?:on|for)\b)")),
    ('owner', _sub(r"\bmy\s+(?:own\s+)?(?:[\w-]+\s+){0,2}(?:house|home|property|garage|attic|basement|cabin|lot|yard|acreage)\b"
                   r"|\b(?:i am|i'm|we are|we're)\s+the\s+(?:property\s+)?owners?\b|\b(?:i|we)\s+own\s+(?:the|this)\b")),
)


def _roles(sentence: str, at: int) -> list[Hit]:
    hits = []
    for role, pattern in _ROLE_CUES:
        for match in pattern.finditer(sentence):
            hits.append(Hit('applicant_role', role, at + match.start(), at + match.end(), 0.8))
    return hits


_JURISDICTION = _sub(r'\b(?:across|throughout|anywhere\s+in|all\s+of)\s+Alberta\b|\bprovince[-\s]?wide\b'
                     r'|\bjurisdiction[-\s]?wide\b|\bgeneral\s+acceptance\b'
                     r'|\b(?:approved|accepted|acceptance)\s+(?:for\s+use\s+)?(?:in|across)\s+Alberta\b')


def _scope(sentence: str, at: int) -> list[Hit]:
    return [Hit('scope', 'jurisdiction', at + m.start(), at + m.end(), 0.75) for m in _JURISDICTION.finditer(sentence)]


# ---------------------------------------------------------------- Section A and B

_LABELS = (
    ('owner_rep_name', r"owner(?:'s)?\s+rep(?:resentative)?|representative|applicant(?:'s)?\s+name|agent"),
    ('owner_name', r"(?:property\s+|registered\s+)?owner(?:'s)?(?:\s+name)?"),
    ('mailing_address', r'mailing\s+address'),
    ('municipal_address', r'(?:municipal|civic|site|project|street|property)\s+address|address'),
    ('legal_description', r'legal(?:\s+land)?(?:\s+description)?'),
    ('permit_number', r'(?:building\s+)?permit(?:\s+(?:number|no\.?|#))?'),
    ('request_date', r'date\s+of\s+request|request\s+date|date'),
    ('lot', r'lot'), ('block', r'block'), ('plan', r'plan'),
)
_LABEL_LINE = re.compile(
    r'(?im)^[ \t]*(?:[-*•][ \t]+)?(?:\|[ \t]*)?\**(?P<label>' + '|'.join(f'(?:{p})' for _, p in _LABELS) + r')\**'
    r'[ \t]*(?::|\|)[ \t]*(?P<value>[^\n|]*[^\s|*])')
_LOT = re.compile(r'\bLot\s+(?P<v>\d{1,4}[A-Z]?)\b')
_BLOCK = re.compile(r'\bBlock\s+(?P<v>\d{1,4}[A-Z]?)\b')
_PLAN = re.compile(r'\bPlan\s+(?P<v>\d{2,}[A-Z]{0,4}\d*)\b')
_ATS = re.compile(r'\b(?P<qtr>NE|NW|SE|SW)[\s-]+(?P<sec>\d{1,2})[\s-]+(?P<twp>\d{1,3})[\s-]+(?P<rge>\d{1,2})[\s-]+'
                  r'W\s?(?P<mer>[4-6])(?:M)?\b')
_PERMIT = re.compile(r'(?i)\bpermit\s+(?:number|no\.?|#)\s*[:#]?\s*(?P<v>[A-Z0-9][A-Z0-9-]{3,})\b'
                     r'|\b(?P<v2>BP[-\s]?\d[\w-]{2,})\b')
_OWNER_IS = re.compile(r"\b(?:[Tt]he\s+)?(?:property\s+)?owner\s+is\s+(?P<v>[A-Z][\w.'-]*(?:\s+(?:[A-Z][\w.'-]*|&|and)){0,5})")
_ADDRESS_TAIL = re.compile(r'^(?:\s*,\s*[A-Z][\w.\' -]{1,30})?(?:\s*,\s*(?:AB|Alberta))?(?:\s*,?\s*[A-Z]\d[A-Z]\s?\d[A-Z]\d)?')


def _label_lines(text: str) -> list[Hit]:
    hits = []
    for match in _LABEL_LINE.finditer(text):
        label = match.group('label').lower()
        name = next(key for key, pattern in _LABELS if re.fullmatch(pattern, label, re.I))
        value = match.group('value').strip()
        if not value or _NEGATED_VALUE.match(value):
            continue
        start = match.start('value') + (len(match.group('value')) - len(match.group('value').lstrip()))
        end = match.end('value')
        while end > start and text[end - 1] in '.,;':
            end -= 1
        hits.append(Hit(name, text[start:end], start, end, 0.95))
    return hits


def _inline_admin(sentence: str, at: int) -> list[Hit]:
    hits = []
    for name, pattern in (('lot', _LOT), ('block', _BLOCK), ('plan', _PLAN)):
        for match in pattern.finditer(sentence):
            hits.append(Hit(name, match.group('v'), at + match.start('v'), at + match.end('v'), 0.85))
    for match in _ATS.finditer(sentence):
        for part in ('qtr', 'sec', 'twp', 'rge', 'mer'):
            hits.append(Hit('ats_' + part, match.group(part), at + match.start(part), at + match.end(part), 0.9))
    for match in _PERMIT.finditer(sentence):
        group = 'v' if match.group('v') else 'v2'
        if re.search(r'(?i)\b(?:no|not|without)\b[^.]{0,20}$', sentence[:match.start()]):
            continue
        hits.append(Hit('permit_number', match.group(group), at + match.start(group), at + match.end(group), 0.85))
    for match in _OWNER_IS.finditer(sentence):
        hits.append(Hit('owner_name', match.group('v'), at + match.start('v'), at + match.end('v'), 0.8))
    for match in STREET.finditer(sentence):
        tail = _ADDRESS_TAIL.match(sentence[match.end():])
        end = match.end() + (tail.end() if tail else 0)
        if re.search(r'(?i)\bmail(?:ing)?\b[^.]{0,20}$', sentence[:match.start()]):
            hits.append(Hit('mailing_address', sentence[match.start():end], at + match.start(), at + end, 0.8))
        else:
            hits.append(Hit('municipal_address', sentence[match.start():end], at + match.start(), at + end, 0.75))
    return hits


@lru_cache(maxsize=1)
def _places() -> re.Pattern:
    names = [p['name'] for p in json.loads((Path(__file__).with_name('places.json')).read_text())['places']]
    alt = '|'.join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return re.compile(rf'\b(?:in|at|near|for|of|from|to)\s+(?:the\s+)?(?:City\s+of\s+|Town\s+of\s+)?(?P<n>{alt})\b'
                      rf'|\b(?P<n2>{alt}),\s*(?:AB|Alberta)\b')


def _municipality(sentence: str, at: int) -> list[Hit]:
    hits = []
    for match in _places().finditer(sentence):
        group = 'n' if match.group('n') else 'n2'
        hits.append(Hit('municipality', match.group(group), at + match.start(group), at + match.end(group), 0.8))
    return hits


# ---------------------------------------------------------------- the proposal

_DEPARTURE = _sub(r"\binstead\b|\brather\s+than\b|\bin\s+place\s+of\b|\breplac(?:e|es|ed|ing)\b"
                  r"|\b(?:we|i|they|client|owner|developer|team|customer)\s+(?:would\s+like|'d\s+like|want|wants|propose|proposes|plan|intend)\b"
                  r"|\bpropos(?:e|es|ing)\b|\b(?:is|are|be|being)\s+proposed\b|\bomit(?:s|ted|ting)?\b|\bleav(?:e|ing)\s+out\b|\bskip\b"
                  r"|\bnot\s+(?:offering|providing|meet|meeting|provide)\b|\b(?:do|does)\s+not\s+want\b|\bdon'?t\s+want\b"
                  r"|\bwithout\s+(?:the|a|any|adding|designing|checking|demonstrating)\b|\bno\s+(?:separate|installed|rated|wood|other)\b")


_NOT_DEPARTURE = _sub(r'\bwithout\s+(?:a|any|the)\s+variance\b')


def _proposal(text: str, spans: list[tuple[int, int]]) -> list[Hit]:
    """The applicant's statement of what they want to do instead: the first departure sentence and
    the departure sentences that directly follow it. A question is never part of it."""
    chosen: list[tuple[int, int]] = []
    for index, (a, b) in enumerate(spans):
        sentence = text[a:b]
        if is_question(sentence) or sentence.lstrip().startswith(('#', '|')) or not _DEPARTURE.search(sentence) \
                or _NOT_DEPARTURE.search(sentence):
            if chosen:
                break
            continue
        chosen.append((a, b))
        if len(chosen) == 3:
            break
    if not chosen:
        return []
    start, end = chosen[0][0], chosen[-1][1]
    return [Hit('alternative_description', text[start:end], start, end, 0.6)]


# Not the start of a longer number: "21.10.2026" is a date, not 21.10.202 followed by a stray 6.
_PID = re.compile(r'(?<![\d.])\d{1,2}\.\d{1,2}\.\d{1,3}(?:\.\d{1,3})?\.?(?:\s?\(\d{1,2}\))?(?:\([a-z]{1,2}\))?(?!\d)')


def _citations(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(0), m.start(), m.end()) for m in _PID.finditer(text)]


# ---------------------------------------------------------------- read

_SENTENCE_RULES = (_storeys, _areas, _dwelling_units, _occupancy, _sprinklered, _distances, _heights, _spans, _part4,
                   _roles, _scope, _inline_admin, _municipality)
_RESIDENTIAL = {'single_family', 'multi_family'}


def _same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(float(a) - float(b)) < 1e-9
    return a == b


def _resolve(name: str, hits: list[Hit]) -> tuple[Hit | None, list[Hit]]:
    """One value or a conflict. A rule that flags its own field as unclear (value -1) is a conflict."""
    if any(hit.value == -1 for hit in hits):
        return None, hits
    values = []
    for hit in hits:
        if not any(_same(hit.value, seen) for seen in values):
            values.append(hit.value)
    if name == 'occupancy' and len(values) > 1:
        # A house word next to "duplex" or "apartment" is the same building; anything else is unclear.
        if set(values) == _RESIDENTIAL and any(h.value == 'multi_family' and h.confidence > 0.6 for h in hits) \
                and all(h.confidence <= 0.6 for h in hits if h.value == 'single_family'):
            values = ['multi_family']
        elif 'single_family' in values and all(h.confidence <= 0.6 for h in hits if h.value == 'single_family'):
            values = [v for v in values if v != 'single_family']
    if name == 'municipality' and len(values) > 1:
        return None, hits
    if len(values) != 1:
        return None, hits
    keep = [hit for hit in hits if _same(hit.value, values[0])]
    return max(keep, key=lambda hit: (hit.confidence, -hit.start)), []


def read(text: str) -> Reading:
    """Every rule over every statement sentence. Label lines are read over the whole text."""
    reading = Reading(citations=_citations(text))
    spans = sentences(text)
    found: dict[str, list[Hit]] = {}
    for hit in _label_lines(text):
        found.setdefault(hit.field, []).append(hit)
    labelled = set(found)
    for a, b in spans:
        sentence = text[a:b]
        if is_question(sentence):
            continue
        for rule in _SENTENCE_RULES:
            for hit in rule(sentence, a):
                if hit.field in labelled:
                    continue                         # an explicit "Owner: ..." line wins over prose
                found.setdefault(hit.field, []).append(hit)
    for hit in _proposal(text, spans):
        found.setdefault(hit.field, []).append(hit)
    for name, hits in found.items():
        best, conflict = _resolve(name, hits)
        if best is not None:
            if _HEDGE.search(text[(sentence_at(spans, best.start) or (best.start, best.end))[0]:best.end]):
                best = Hit(best.field, best.value, best.start, best.end, min(best.confidence, 0.5), best.raw)
            reading.hits.append(best)
        elif conflict:
            reading.conflicts[name] = conflict
    reading.hits.sort(key=lambda hit: hit.start)
    return reading


def canonical_citation(entered: str) -> str | None:
    try:
        return canon(entered.replace(' ', ''))
    except ValueError:
        return None


def supports(name: str, value, text: str, start: int, end: int) -> bool:
    """True when the rules, re-run over the sentence around `text[start:end]`, read the same value
    for `name` from words overlapping that span. This is the check a model value must pass."""
    spans = sentences(text)
    around = [span for span in spans if span[0] < end and start < span[1]] or [(start, end)]
    a, b = around[0][0], around[-1][1]
    if name == 'alternative_description':
        return isinstance(value, str) and value.strip() != '' and value in text[a:b]
    if name == 'claimed_provision':
        return canonical_citation(text[start:end]) == value
    if name in ENUMS and value not in ENUMS[name]:
        return False
    chunk = text[a:b]
    hits = _label_lines(chunk) + [hit for rule in _SENTENCE_RULES
                                  for s0, s1 in sentences(chunk) for hit in rule(chunk[s0:s1], s0)]
    for hit in hits:
        if hit.field == name and _same(hit.value, value) and a + hit.start < end and start < a + hit.end:
            return True
    return False
