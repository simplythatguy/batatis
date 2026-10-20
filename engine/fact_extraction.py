"""Offline extraction of intake facts from a pasted description.

Rules run with no network. A model pass runs only when BATATIS_LIVE=1 and OPENAI_API_KEY
is set, and it may fill a field the rules left blank. It cannot override a rules hit.
Extracted values stay unconfirmed. Exemption claims and evidence listings are not decided here.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from html import unescape
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from codedb.ids import canon

from .completeness import Gap, check_completeness
from .models import Case, Fact, Source
from .professional import Occupancy

ApplicantRole = Literal['owner', 'designer', 'contractor', 'manufacturer', 'other']
Scope = Literal['site', 'jurisdiction_wide']
Sprinklered = Literal['yes', 'no', 'partial', 'unknown']
Installation = Literal['installed', 'planned', 'unknown']
Confidence = Literal['high', 'medium', 'low']
CellStatus = Literal['extracted', 'confirmed', 'corrected', 'missing']
Method = Literal['rules', 'model', 'user']
AuthorType = Literal['professional', 'vendor', 'lab', 'applicant', 'unknown']

WINNER = 'classifier'
REVIEW_STATUS = 'listed_not_reviewed'
REVIEW_LABEL = 'evidence_listed (not reviewed)'
EJ_MISSING = ('signature', 'tested system', 'job name and location', 'issuer qualifications')
EXEMPTION_QUESTION = 'What evidence supports this exemption claim?'
EXEMPTION_GAP = 'applicant claim not supported by a citation'
EJ_ROUTE = 'Ask for an EJ from a qualified issuer. The officer decides.'
OCCUPANCY_QUESTION = 'What is the major occupancy of each part?'
AREA_QUESTION = 'Is this the building area, or a gross or total floor area?'
SCOPE_QUESTION = 'Does this application cover this site only, or jurisdiction-wide use?'

_PLANTED = re.compile(
    r"(?i)isn'?t a real engineering judgment|not an engineering judgment|\bnot an EJ\b")
_DEPARTURE = re.compile(
    r"(?i)\b(?:replaces|instead of|i want|we want|approval to|nailed directly|no furring|no poly|we propose|propose to)\b")
_FACTISH = re.compile(r'(?i)\b(?:storey|storeys|m2|m²|unsprinklered|sprinklered|address)\b')
_PID = re.compile(r'\b\d+(?:\.\d+){3}(?:\.\(\d+\))?(?:\([a-z]\))?(?:\([ivx]+\))?')
_CITIES = ('Red Deer', 'Calgary', 'Edmonton')
_WORDS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7,
          'eight': 8, 'nine': 9, 'ten': 10}
_SQFT = 0.09290304
_CONF = {'high': 0.86, 'medium': 0.6, 'low': 0.35}

SCALAR_FIELDS = (
    'applicant_role', 'owner_name', 'municipal_address', 'legal_description', 'permit_number',
    'municipality', 'jurisdiction_scope', 'occupancy', 'storeys', 'building_area_m2',
    'dwelling_units', 'sprinklered', 'product_or_assembly', 'installation_status',
    'proposed_alternative', 'required_acceptable_solution', 'project_name',
)
_MIRROR_ALIAS = {'jurisdiction_scope': 'scope', 'proposed_alternative': 'alternative_description'}


class FactCell(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: str | int | float | None = None
    status: CellStatus = 'missing'
    confidence: Confidence | None = None
    source_quote: str | None = None
    source_span: list[int] | None = None
    method: Method | None = None
    question: str | None = None


class ClaimedProvision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str | None = None
    entered: str
    resolved: bool = False
    division: str | None = None


class ClaimedExemption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
    provision_ids: list[str] = []
    status: Literal['applicant_asserted'] = 'applicant_asserted'
    by: str | None = None
    question: str = EXEMPTION_QUESTION
    officer_gap: str | None = EXEMPTION_GAP
    source_quote: str | None = None
    source_span: list[int] | None = None


class ApplicantClaim(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
    status: Literal['applicant_asserted'] = 'applicant_asserted'
    source_quote: str
    source_span: list[int] | None = None


class EvidenceExtract(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str
    signed: bool | None = None
    author_type: AuthorType = 'unknown'
    stated_role: str | None = None
    review_status: Literal['listed_not_reviewed'] = REVIEW_STATUS
    review_label: Literal['evidence_listed (not reviewed)'] = REVIEW_LABEL
    missing_items: list[str] = []
    question: str | None = None
    professional_confirmed: Literal[False] = False
    source_quote: str
    source_span: list[int] | None = None


class IntakeFacts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    applicant_role: FactCell = Field(default_factory=FactCell)
    owner_name: FactCell = Field(default_factory=FactCell)
    municipal_address: FactCell = Field(default_factory=FactCell)
    legal_description: FactCell = Field(default_factory=FactCell)
    permit_number: FactCell = Field(default_factory=FactCell)
    municipality: FactCell = Field(default_factory=FactCell)
    jurisdiction_scope: FactCell = Field(default_factory=FactCell)
    occupancy: FactCell = Field(default_factory=FactCell)
    storeys: FactCell = Field(default_factory=FactCell)
    building_area_m2: FactCell = Field(default_factory=FactCell)
    dwelling_units: FactCell = Field(default_factory=FactCell)
    sprinklered: FactCell = Field(default_factory=FactCell)
    product_or_assembly: FactCell = Field(default_factory=FactCell)
    installation_status: FactCell = Field(default_factory=FactCell)
    proposed_alternative: FactCell = Field(default_factory=FactCell)
    required_acceptable_solution: FactCell = Field(default_factory=FactCell)
    project_name: FactCell = Field(default_factory=FactCell)
    claimed_provisions: list[ClaimedProvision] = []
    claimed_exemptions: list[ClaimedExemption] = []
    claims: list[ApplicantClaim] = []
    evidence_items: list[EvidenceExtract] = []


def blank_facts() -> IntakeFacts:
    return IntakeFacts()


def html_to_text(html: str) -> str:
    """Drop tags. Headings keep a markdown marker so they are not read as a proposal."""
    text = re.sub(r'(?i)<br\s*/?>', '\n', html)
    text = re.sub(r'(?i)<h[1-6][^>]*>', '\n# ', text)
    text = re.sub(r'(?i)</h[1-6]>', '\n', text)
    text = re.sub(r'(?i)</(?:p|div|tr|li|h[1-6])>', '\n', text)
    text = re.sub(r'(?i)<li[^>]*>', '\n- ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = text.replace('\xa0', ' ')
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def extract(text: str, codes=None, *, approach: str | None = None) -> IntakeFacts:
    """Shipped extractor. `approach` is `classifier` (default) or `regex` for the comparison."""
    mode = approach or WINNER
    facts = _extract(text, normalise=mode == 'classifier', departure=mode, codes=codes)
    if mode == WINNER:
        facts = _model_fill(text, facts)
    return facts


def _extract(text: str, *, normalise: bool, departure: str, codes) -> IntakeFacts:
    units = _units(text)
    facts = IntakeFacts(
        applicant_role=_role(text),
        owner_name=_owner(text),
        municipal_address=_address(text),
        legal_description=_legal(text),
        permit_number=_permit(text),
        municipality=_municipality(text),
        project_name=_project_name(text),
        storeys=_storeys(text, units, normalise),
        building_area_m2=_area(text, units, normalise),
        dwelling_units=_dwelling(text, units),
        sprinklered=_sprinklered(text, units),
        occupancy=_occupancy(text, units),
        product_or_assembly=_product(text, units),
        installation_status=_installation(text, units),
        required_acceptable_solution=_required(text),
        proposed_alternative=_proposed(text, units, departure),
        claimed_provisions=_provisions(text, codes),
        claimed_exemptions=_exemptions(text, units),
        claims=_claims(text, units),
        evidence_items=_evidence(text, units),
    )
    facts.jurisdiction_scope = _scope(text, facts.municipal_address.value)
    return facts


def _units(text: str) -> list[tuple[int, int]]:
    units: list[tuple[int, int]] = []
    n = len(text)
    i = 0
    start = 0
    in_quote = False

    def emit(a: int, b: int) -> None:
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if a < b:
            units.append((a, b))

    while i < n:
        ch = text[i]
        if ch == '"':
            in_quote = not in_quote
            i += 1
            continue
        if in_quote:
            i += 1
            continue
        if ch == '\n':
            emit(start, i)
            i += 1
            start = i
            continue
        if ch in '.?!':
            nxt = text[i + 1] if i + 1 < n else ''
            if nxt == '' or nxt.isspace():
                tail = text[max(0, i - 5):i + 1]
                if re.search(r'(?i)(?:o\.c|Inc|Ltd|e\.g|i\.e|U\.S)\.$', tail):
                    i += 1
                    continue
                emit(start, i + 1)
                i += 1
                start = i
                continue
        i += 1
    emit(start, n)
    return units


def _slice(text: str, span: tuple[int, int]) -> str:
    return text[span[0]:span[1]]


def _unit_at(text: str, units: list[tuple[int, int]], index: int) -> str:
    for a, b in units:
        if a <= index < b:
            return text[a:b]
    line_end = text.find('\n', index)
    if line_end < 0:
        line_end = len(text)
    line_start = text.rfind('\n', 0, index) + 1
    return text[line_start:line_end].strip()


def _located(text: str, quote: str | None) -> tuple[str | None, list[int] | None]:
    if not quote or _PLANTED.search(quote):
        return None, None
    at = text.find(quote)
    if at < 0:
        return None, None
    return quote, [at, at + len(quote)]


def _hit(text: str, value, quote: str | None, confidence: Confidence, question: str | None = None) -> FactCell:
    if isinstance(value, str) and _PLANTED.search(value):
        return FactCell()
    src, span = _located(text, quote)
    return FactCell(value=value, status='extracted', confidence=confidence, source_quote=src,
                    source_span=span, method='rules', question=question)


def _abstain(question: str) -> FactCell:
    return FactCell(method='rules', question=question)


def _polish(value: str) -> str:
    value = re.sub(r'\*+', '', value)
    value = re.sub(r'\s*\((?:fictional[^)]*)\)', '', value, flags=re.I)
    value = re.sub(r'\s+', ' ', value).strip(' ,;')
    if not re.search(r'(?i)\b(?:Inc|Ltd|Corp)\.$', value):
        value = value.rstrip('.')
    return value


def _negated(value: str) -> bool:
    return bool(re.search(r"(?i)\b(?:don'?t have|do not have|not applied|not yet|will ask|unknown|n/?a)\b", value))


def _table(text: str) -> dict[str, str]:
    rows = {}
    for match in re.finditer(r'^\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|', text, re.M):
        rows[_polish(match.group(1)).casefold()] = _polish(match.group(2))
    return rows


def _role(text: str) -> FactCell:
    made = re.search(r'(?i)\bwe manufacture\b', text)
    if made:
        return _hit(text, 'manufacturer', made.group(0), 'high')
    prepared = re.search(r'(?i)Prepared by:\s*([^(\n]+?)\s*\(([^)]+)\)', text)
    if prepared and re.search(r'(?i)\bowner\b', prepared.group(2)):
        return _hit(text, 'owner', prepared.group(0), 'high')
    if prepared and re.search(r'(?i)\bdesigner\b', prepared.group(2)):
        return _hit(text, 'designer', prepared.group(0), 'high')
    origin = re.search(r'(?i)^.*\b(?:builders|contractor|general contractor)\b.*$', text, re.M)
    if origin and re.search(r'(?i)^(?:\*\*)?From:', origin.group(0).strip()):
        quote = origin.group(0).strip()
        return _hit(text, 'contractor', quote, 'medium')
    return FactCell()


def _owner(text: str) -> FactCell:
    table = _table(text)
    if table.get('owner') and not _negated(table['owner']) and table['owner'] in text:
        return _hit(text, table['owner'], table['owner'], 'high')
    named = re.search(r'(?i)\bthe owner is\s+([A-Z][^.\n]{1,80})', text)
    if named:
        name = named.group(1).strip()
        return _hit(text, name, name, 'high')
    prepared = re.search(r'(?i)Prepared by:\s*([^(\n]+?)\s*\(([^)]+)\)', text)
    if prepared and re.search(r'(?i)\bowner\b', prepared.group(2)):
        name = prepared.group(1).strip()
        if name in text:
            return _hit(text, name, name, 'high')
    return FactCell()


_ADDRESS = re.compile(
    r'\b(\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9 .\'-]{0,48}?\s(?:Avenue|Way|Road|Street|Drive|Crescent|Boulevard)'
    r'\s+(?:NW|NE|SW|SE)(?:\s*,\s*(?:Calgary|Edmonton|Red Deer),\s*AB)?)', re.I)


def _address(text: str) -> FactCell:
    table = _table(text)
    if table.get('address') and table['address'] in text:
        return _hit(text, table['address'], table['address'], 'high')
    match = _ADDRESS.search(text)
    if match:
        return _hit(text, match.group(1), match.group(1), 'high')
    return FactCell()


def _legal(text: str) -> FactCell:
    table = _table(text)
    if table.get('legal') and not _negated(table['legal']) and table['legal'] in text:
        return _hit(text, table['legal'], table['legal'], 'high')
    match = re.search(r'(?i)legal(?:\s+description)?\s*[:|]\s*([^.\n]+)', text)
    if not match:
        return FactCell()
    value = _polish(match.group(1))
    if _negated(value) or value not in text:
        return FactCell()
    return _hit(text, value, value, 'high')


def _permit(text: str) -> FactCell:
    for match in re.finditer(r'\b(BP-[\w-]+)\b', text):
        window = text[max(0, match.start() - 80):match.end() + 40]
        if re.search(r'(?i)\bnot applied\b|\bno permit\b', window):
            continue
        return _hit(text, match.group(1), match.group(1), 'high')
    return FactCell()


def _municipality(text: str) -> FactCell:
    found = []
    for city in _CITIES:
        if re.search(r'\b' + city + r'\b', text, re.I):
            found.append(city)
    if len(found) == 1 and found[0] in text:
        return _hit(text, found[0], found[0], 'high')
    if len(found) > 1:
        return _abstain('Which municipality will receive this application?')
    return FactCell()


def _project_name(text: str) -> FactCell:
    name = _table(text).get('name')
    if name and name in text:
        return _hit(text, name, name, 'high')
    return FactCell()


def _storeys(text: str, units, normalise: bool) -> FactCell:
    hits: list[tuple[int, int]] = []
    number = re.compile(r'(?i)(?P<pre>not\s+(?:a\s+)?|under\s+)?(?P<num>\d+)\s*-?\s*storeys?\b')
    word = re.compile(r'(?i)(?P<pre>not\s+(?:a\s+)?|under\s+)?(?P<word>one|two|three|four|five|six|seven|eight|nine|ten)[\s-]+storeys?\b')
    patterns = [number] + ([word] if normalise else [])
    for pattern in patterns:
        for match in pattern.finditer(text):
            if match.group('pre'):
                continue
            sentence = _unit_at(text, units, match.start())
            if re.search(r'(?i)\bnot sure\b|\bi think\b', sentence):
                continue
            value = int(match.group('num')) if match.groupdict().get('num') else _WORDS[match.group('word').lower()]
            hits.append((value, match.start()))
    unique = {value for value, _ in hits}
    if len(unique) != 1:
        return _abstain('How many storeys is the building?') if len(unique) > 1 else FactCell()
    value, index = next((value, index) for value, index in hits)
    quote = _unit_at(text, units, index)
    return _hit(text, value, quote if quote in text else str(value), 'high')


def _area(text: str, units, normalise: bool) -> FactCell:
    pattern = re.compile(
        r'(?i)(?P<hedge>about|approximately|approx\.?|~|roughly)?\s*'
        r'(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>m\s*(?:²|2)|sq\.?\s*m(?:etres)?|sq\.?\s*ft|square feet)')
    found = []
    for match in pattern.finditer(text):
        unit = match.group('unit').lower()
        sqft = 'ft' in unit or 'feet' in unit
        if sqft and not normalise:
            continue
        number = float(match.group('num').replace(',', ''))
        value = round(number * _SQFT, 2) if sqft else (int(number) if number.is_integer() else number)
        sentence = _unit_at(text, units, match.start())
        soft = bool(match.group('hedge') or sqft or re.search(r'(?i)\b(?:gross|total floor|main floor)\b', sentence))
        question = AREA_QUESTION if re.search(r'(?i)\b(?:gross|total floor|main floor)\b', sentence) else None
        found.append((value, sentence, 'medium' if soft else 'high', question))
    if not found:
        return FactCell()
    value, sentence, confidence, question = found[0]
    quote = sentence if sentence in text else _match_quote(text, value)
    return _hit(text, value, quote, confidence, question)


def _match_quote(text: str, value) -> str:
    token = str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
    return token if token in text else ''


def _dwelling(text: str, units) -> FactCell:
    match = re.search(r'(?i)\b(\d+)\s+dwelling units\b', text)
    if not match:
        return FactCell()
    return _hit(text, int(match.group(1)), _unit_at(text, units, match.start()), 'high')


def _sprinkler_value(sentence: str) -> str | None:
    if re.search(r'(?i)\b(?:not\s+sprinklered|non-?\s*sprinklered|unsprinklered|no sprinklers)\b', sentence):
        return 'no'
    if re.search(r'(?i)\bpartial(?:ly)?\s+sprinklered\b', sentence):
        return 'partial'
    if re.search(r'(?i)(?<![-\w])sprinklered\b', sentence):
        return 'yes'
    return None


def _sprinklered(text: str, units) -> FactCell:
    hits = []
    for span in units:
        sentence = _slice(text, span)
        value = _sprinkler_value(sentence)
        if value:
            hits.append((value, sentence))
    if not hits:
        for match in re.finditer(r'(?i)(?<![-\w])(?:un|non-?)?sprinklered\b|\bno sprinklers\b', text):
            sentence = _unit_at(text, units, match.start())
            value = _sprinkler_value(sentence)
            if value:
                hits.append((value, sentence))
                break
    unique = {value for value, _ in hits}
    if not unique:
        # "exempt" is a claim about a penetration, not a yes/no on the building.
        return FactCell(method='rules') if re.search(r'(?i)\bexempt\b', text) else FactCell()
    if len(unique) != 1:
        return _abstain('Is the building sprinklered?')
    value, sentence = hits[0]
    return _hit(text, value, sentence, 'high')


def _occupancy(text: str, units) -> FactCell:
    if re.search(r'(?i)\bretail\b', text) and re.search(r'(?i)\bdwelling units\b', text):
        return _abstain(OCCUPANCY_QUESTION)
    checks = (
        (r'(?i)\bsingle[-\s]family\b', 'single_family', 'high'),
        (r'(?i)\bgarden suite\b', 'single_family', 'medium'),
        (r'(?i)\bcare\s+(?:building|occupancy)\b', 'care', 'high'),
        (r'(?i)(?<![\w-])(?:warehouse|factory)(?![\w-])', 'industrial', 'high'),
    )
    for pattern, value, confidence in checks:
        match = re.search(pattern, text)
        if match:
            return _hit(text, value, _unit_at(text, units, match.start()), confidence)
    return FactCell()


_PRODUCTS = (
    re.compile(r'NailBase\s+CI-\d+'),
    re.compile(r'Example\s+FireSeal\s+\d+'),
    re.compile(r'FireSeal\s+\d+'),
    re.compile(r'cast-in-place\s+hempcrete', re.I),
    re.compile(r'HempWall\s+Pro'),
)


def _product(text: str, units) -> FactCell:
    best = None
    for pattern in _PRODUCTS:
        for match in pattern.finditer(text):
            sentence = _unit_at(text, units, match.start())
            score = (2 if _DEPARTURE.search(sentence) else 1, len(match.group(0)))
            if best is None or score > best[0]:
                best = (score, match.group(0), sentence)
    if not best:
        return FactCell()
    return _hit(text, best[1], best[1], 'high')


def _installation(text: str, units) -> FactCell:
    installed = re.search(r'(?i)\b(?:sealed the|already installed|was installed|have been installed)\b', text)
    planned = re.search(r'(?i)\b(?:to build|propose to|we propose|i want|we want)\b', text)
    if installed:
        return _hit(text, 'installed', _unit_at(text, units, installed.start()), 'high')
    if planned:
        return _hit(text, 'planned', _unit_at(text, units, planned.start()), 'high')
    return FactCell()


def _required(text: str) -> FactCell:
    match = re.search(r'(?i)\binstead of\s+(.+?)(?=\s+in this\b|,\s*I want\b|,\s*we\b|[.])', text)
    if match:
        value = match.group(1).strip()
        if value in text:
            return _hit(text, value, value, 'high')
    said = re.search(r'(?i)\bthe code (?:requires|says)\s+(.+?)(?:\.|$)', text)
    if said and said.group(1).strip() in text:
        value = said.group(1).strip()
        return _hit(text, value, value, 'medium')
    return FactCell()


def _skip_unit(text: str, span: tuple[int, int], departure: str) -> bool:
    sentence = _slice(text, span).strip()
    if not sentence or _PLANTED.search(sentence):
        return True
    if sentence.startswith('#') or sentence.startswith('|'):
        return True
    if sentence.endswith('?'):
        return True
    if departure == 'regex':
        return False
    if re.search(r'(?i)\bexempt\b', sentence) or re.search(r'(?i)\ba variance so\b', sentence):
        return True
    return _DEPARTURE.search(sentence) is None


def _trim_colon(text: str, span: tuple[int, int]) -> tuple[int, int]:
    sentence = _slice(text, span)
    if ':' not in sentence:
        return span
    rel = sentence.find(':')
    left, right = sentence[:rel].rstrip(), sentence[rel + 1:]
    if _DEPARTURE.search(left) and _FACTISH.search(right):
        return span[0], span[0] + len(left)
    return span


def _proposed(text: str, units, departure: str) -> FactCell:
    kept = []
    for span in units:
        if _skip_unit(text, span, departure):
            continue
        if departure == 'classifier':
            span = _trim_colon(text, span)
        kept.append(span)
    if not kept:
        return FactCell()
    contiguous = all(not text[b:c].strip() for (_, b), (c, _) in zip(kept, kept[1:]))
    if contiguous:
        value = text[kept[0][0]:kept[-1][1]].strip()
        return _hit(text, value, value, 'medium')
    value = ' '.join(_slice(text, span) for span in kept)
    quote = _slice(text, kept[0])
    cell = _hit(text, value if value in text else quote, quote, 'medium')
    if value in text:
        cell.value = value
    return cell


def _resolve(entered: str, codes) -> ClaimedProvision | None:
    try:
        cid = canon(entered)
    except ValueError:
        return None
    if codes is None:
        return ClaimedProvision(id=cid, entered=entered, resolved=False, division=None)
    for division in ('B', 'A', 'C'):
        try:
            rec = codes.provision(cid, division)
        except Exception:
            rec = None
        if rec:
            return ClaimedProvision(id=rec.get('id', cid), entered=entered, resolved=True,
                                    division=rec.get('division', division))
    return ClaimedProvision(id=cid, entered=entered, resolved=False, division=None)


def _provisions(text: str, codes) -> list[ClaimedProvision]:
    found = []
    seen = set()
    for match in _PID.finditer(text):
        entered = match.group(0)
        window = text[max(0, match.start() - 24):match.start()]
        if re.search(r'(?i)not under\s*$', window):
            continue
        item = _resolve(entered, codes)
        if item is None or item.id in seen:
            continue
        seen.add(item.id)
        found.append(item)
    return found


def _exemptions(text: str, units) -> list[ClaimedExemption]:
    items = []
    for index, span in enumerate(units):
        sentence = _slice(text, span)
        if not re.search(r'(?i)\bexempt\b', sentence) or _PLANTED.search(sentence):
            continue
        start, end = span
        if index:
            prev = _slice(text, units[index - 1])
            gap = text[units[index - 1][1]:span[0]]
            if re.search(r'(?i)sprinkler', prev) and not gap.strip():
                start = units[index - 1][0]
        quote = text[start:end].strip()
        if quote not in text:
            quote = sentence
        ids = []
        for pid in _PID.findall(quote):
            try:
                ids.append(canon(pid))
            except ValueError:
                continue
        speaker = None
        said = re.search(
            r'\b([A-Z][A-Za-z]*(?:\s+[A-Za-z]+){0,3})\s+says\b(?:(?!\bsays\b).){0,80}\bexempt', quote)
        if said:
            speaker = said.group(1)
            if re.fullmatch(r'(?i)the sub', speaker) and re.search(r'(?i)\bfirestop sub\b', text):
                speaker = 'firestop sub'
        src, span_out = _located(text, quote)
        items.append(ClaimedExemption(
            text=quote, provision_ids=ids, by=speaker,
            question=EXEMPTION_QUESTION,
            officer_gap=None if ids else EXEMPTION_GAP,
            source_quote=src, source_span=span_out))
    return items


def _claims(text: str, units) -> list[ApplicantClaim]:
    items = []
    for span in units:
        sentence = _slice(text, span).strip()
        if not sentence or sentence.endswith('?') or _PLANTED.search(sentence):
            continue
        if re.search(r'(?i)\bexempt\b', sentence):
            continue
        if re.search(r'(?i)\ba variance so\b', sentence) or re.search(r'(?i)engineering judgment', sentence):
            src, located = _located(text, sentence)
            if src:
                items.append(ApplicantClaim(text=sentence, source_quote=src, source_span=located))
    return items


_EVIDENCE = (
    ('product_data_sheet', re.compile(r'(?i)\bproduct data sheet\b'), 'applicant'),
    ('lab_test', re.compile(r'(?i)\b(?:permeance test|test summary|lab(?:oratory)?\s+(?:\w+\s+){0,3}tests?)\b'), 'lab'),
    ('engineer_letter', re.compile(r'(?i)\bengineer letter\b'), 'professional'),
    ('email', re.compile(r'(?i)\bdraft\s+EJ\s+email\b|\bengineering judgment\b|\bemailed an unsigned note\b'), 'vendor'),
    ('brochure', re.compile(r'(?i)\bbrochure\b'), 'vendor'),
    ('photos', re.compile(r'(?i)\bphotos\b'), 'applicant'),
)


def _is_ej(sentence: str) -> bool:
    if _PLANTED.search(sentence):
        return False
    return bool(re.search(r'\bEJ\b', sentence) or re.search(r'(?i)engineering judgment', sentence))


def _missing_items(quote: str, ej: bool, signed: bool | None) -> list[str]:
    if ej:
        items = []
        if not re.search(r'(?i)\b(?:signed by|signature of|bears a signature)\b', quote):
            items.append('signature')
        if not re.search(r'(?i)\b(?:tested system|CAN/ULC|listing\s+[A-Z0-9-]*\d)\b', quote):
            items.append('tested system')
        if not re.search(r'(?i)\b(?:job name|project\s*:|located at)\b', quote):
            items.append('job name and location')
        if not re.search(r'(?i)\b(?:P\.?\s*Eng|registered professional|qualifications|licensed)\b', quote):
            items.append('issuer qualifications')
        return items
    if signed is False:
        return ['signature']
    return []


def _clause(sentence: str, sentence_start: int, match_start: int) -> str:
    """Comma-separated piece that holds the cue, so one sentence can list several documents."""
    rel = match_start - sentence_start
    bounds = [0]
    bounds.extend(match.end() for match in re.finditer(r',', sentence))
    bounds.append(len(sentence))
    for start, end in zip(bounds, bounds[1:]):
        if start <= rel < end or (rel == len(sentence) and end == len(sentence)):
            return sentence[start:end].strip(' ,')
    return sentence.strip()


def _evidence(text: str, units) -> list[EvidenceExtract]:
    found: dict[str, EvidenceExtract] = {}
    for kind, pattern, author in _EVIDENCE:
        for match in pattern.finditer(text):
            window = text[max(0, match.start() - 48):match.start()]
            if re.search(r'(?i)\b(?:no|not|without|never)\b', window):
                continue
            sentence = _unit_at(text, units, match.start()).strip()
            if not sentence or _PLANTED.search(sentence):
                continue
            sentence_at = text.find(sentence, max(0, match.start() - len(sentence) - 2))
            if sentence_at < 0:
                sentence_at = match.start()
            clause = _clause(sentence, sentence_at, match.start())
            if not clause or _PLANTED.search(clause):
                continue
            ej = kind == 'email' and _is_ej(clause)
            if re.search(r'(?i)\b(?:unsigned|draft)\b', clause):
                signed: bool | None = False
            elif re.search(r'(?i)\b(?:signed by|signature of|bears a signature)\b', clause):
                signed = True
            elif ej:
                signed = False
            else:
                signed = None
            author_type = author
            stated = None
            if kind == 'email':
                if re.search(r'(?i)\bsales rep\b', text):
                    stated = 'sales rep'
                elif re.search(r'(?i)\bsealant rep\b', text):
                    stated = 'sealant rep'
                elif not re.search(r'(?i)\bvendor\b', text):
                    author_type = 'unknown'
            src, span = _located(text, clause)
            if not src:
                continue
            item = EvidenceExtract(
                kind=kind, signed=signed, author_type=author_type, stated_role=stated,
                missing_items=_missing_items(clause, ej, signed),
                question=EJ_ROUTE if ej else None,
                source_quote=src, source_span=span)
            current = found.get(kind)
            if current is None or len(item.missing_items) > len(current.missing_items):
                found[kind] = item
    return list(found.values())


def _scope(text: str, address) -> FactCell:
    wide = re.search(r'(?i)\b(?:across Alberta|province-wide|jurisdiction-wide|anywhere in Alberta)\b', text)
    site = bool(address) or re.search(r'(?i)\bSite:|\bthis site\b|\bpilot house\b', text)
    if wide and site:
        return _abstain(SCOPE_QUESTION)
    if wide:
        return _hit(text, 'jurisdiction_wide', wide.group(0), 'high')
    if site:
        quote = 'Site:' if 'Site:' in text else (address if isinstance(address, str) else None)
        return _hit(text, 'site', quote if isinstance(quote, str) else None, 'high')
    return FactCell()


def _model_suggest(text: str, fields: list[str]) -> dict:
    """Optional filler. Returns {} unless a live key is configured. Never logs the key."""
    if os.environ.get('BATATIS_LIVE') != '1' or not fields:
        return {}
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        return {}
    body = {
        'model': os.environ.get('BATATIS_EXTRACT_MODEL', 'gpt-4o-mini'),
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': (
                'Extract only the requested fields from the user text. '
                'Each hit is {"value": ..., "quote": "..."} and quote must be copied exactly from the text. '
                'Omit a field you cannot support. Do not decide exemptions or whether evidence is adequate. '
                'Return {"fields": {...}}.')},
            {'role': 'user', 'content': json.dumps({'fields': fields, 'text': text[:8000]})},
        ],
    }
    request = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
        method='POST')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
        content = payload['choices'][0]['message']['content']
        return json.loads(content).get('fields') or {}
    except Exception:
        return {}


def _supports(field: str, value, quote: str, text: str) -> bool:
    if not quote or quote not in text:
        return False
    if field == 'sprinklered' and value == 'yes':
        return bool(re.search(r'(?i)(?<![-\w])sprinklered\b', quote)) and not bool(
            re.search(r'(?i)\b(?:not\s+sprinklered|unsprinklered|non-?\s*sprinklered)\b', quote))
    if field == 'sprinklered' and value == 'no':
        if re.search(r'(?i)\bexempt\b', quote) and not re.search(r'(?i)not sprinklered|unsprinklered', quote):
            return False
        return bool(re.search(r'(?i)\b(?:not\s+sprinklered|unsprinklered|non-?\s*sprinklered|no sprinklers)\b', quote))
    if field == 'storeys':
        return str(value) in quote
    if field == 'building_area_m2':
        return re.search(r'\d', quote) is not None and str(value).split('.')[0] in quote.replace(',', '')
    return str(value) in quote


def _coerce(field: str, value):
    if field in ('storeys', 'dwelling_units'):
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number >= 1 else None
    if field == 'building_area_m2':
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None
    enums = {
        'applicant_role': {'owner', 'designer', 'contractor', 'manufacturer', 'other'},
        'jurisdiction_scope': {'site', 'jurisdiction_wide'},
        'occupancy': set(get_args(Occupancy)),
        'sprinklered': {'yes', 'no', 'partial', 'unknown'},
        'installation_status': {'installed', 'planned', 'unknown'},
    }
    if field in enums:
        return value if value in enums[field] else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _model_fill(text: str, facts: IntakeFacts) -> IntakeFacts:
    pending = [name for name in SCALAR_FIELDS
               if getattr(facts, name).status == 'missing' and getattr(facts, name).method is None]
    suggestions = _model_suggest(text, pending)
    if not isinstance(suggestions, dict):
        return facts
    for name, raw in suggestions.items():
        if name not in pending or not isinstance(raw, dict):
            continue
        value = _coerce(name, raw.get('value'))
        quote = raw.get('quote')
        if value is None or not isinstance(quote, str) or not _supports(name, value, quote, text):
            continue
        src, span = _located(text, quote)
        setattr(facts, name, FactCell(value=value, status='extracted', confidence='low', source_quote=src,
                                      source_span=span, method='model'))
    return facts


def load_facts(case: Case) -> IntakeFacts | None:
    if not case.intake_facts:
        return None
    return IntakeFacts.model_validate(case.intake_facts)


def _append_fact(case: Case, field: str, cell: FactCell, *, confirmed: bool) -> None:
    if cell.value is None:
        return
    case.facts.append(Fact(
        field=field, value=cell.value, kind='pointed',
        status='confirmed' if confirmed else 'unconfirmed',
        confidence=_CONF.get(cell.confidence or ''),
        source=Source(type='user_text', ref='applicant' if confirmed else 'description', quote=cell.source_quote)))


def _sync_ledger(case: Case, facts: IntakeFacts) -> None:
    locked = {name for name in SCALAR_FIELDS if getattr(facts, name).method == 'user'}
    alias_locked = {_MIRROR_ALIAS[name] for name in locked if name in _MIRROR_ALIAS}

    def stale(fact: Fact) -> bool:
        return (fact.source.ref == 'description' and fact.status == 'unconfirmed'
                and fact.field not in locked and fact.field not in alias_locked)

    case.facts = [fact for fact in case.facts if not stale(fact)]
    for name in SCALAR_FIELDS:
        if name in locked:
            continue
        cell = getattr(facts, name)
        if cell.value is None or cell.status == 'missing':
            continue
        _append_fact(case, name, cell, confirmed=False)
        alias = _MIRROR_ALIAS.get(name)
        if alias:
            _append_fact(case, alias, cell, confirmed=False)


def record_description(case: Case, text: str, codes=None) -> IntakeFacts:
    fresh = extract(text, codes)
    prior = load_facts(case)
    if prior is not None:
        for name in SCALAR_FIELDS:
            old = getattr(prior, name)
            if old.method == 'user':
                setattr(fresh, name, old)
    case.intake_text = text
    case.intake_facts = fresh.model_dump(mode='json')
    _sync_ledger(case, fresh)
    return fresh


def apply_patch(case: Case, updates: dict) -> IntakeFacts:
    facts = load_facts(case) or blank_facts()
    text = case.intake_text or ''
    for name, value in updates.items():
        if name not in SCALAR_FIELDS:
            raise ValueError(f'unknown field: {name}')
        cell = getattr(facts, name)
        if cell.status == 'missing' or cell.value == value:
            status = 'confirmed'
        else:
            status = 'corrected'
        if cell.value == value and cell.source_quote and cell.source_quote in text:
            quote, span = cell.source_quote, cell.source_span
        elif isinstance(value, str) and value and value in text:
            at = text.find(value)
            quote, span = value, [at, at + len(value)]
        else:
            quote, span = None, None
        updated = FactCell(value=value, status=status, confidence=cell.confidence or 'high',
                           source_quote=quote, source_span=span, method='user', question=cell.question)
        setattr(facts, name, updated)
        _append_fact(case, name, updated, confirmed=True)
        alias = _MIRROR_ALIAS.get(name)
        if alias:
            _append_fact(case, alias, updated, confirmed=True)
    case.intake_facts = facts.model_dump(mode='json')
    return facts


def officer_gaps(case: Case) -> list[Gap]:
    """Administrative gaps read off the intake. They do not decide the exemption or the evidence."""
    facts = load_facts(case)
    if facts is None:
        return []
    gaps = []
    for item in facts.claimed_exemptions:
        if item.provision_ids:
            continue
        gaps.append(Gap(section='B', field='claimed_exemptions', severity='warning',
                        message=EXEMPTION_GAP,
                        fix_hint='Ask for evidence that supports this exemption claim. The officer decides.'))
    for item in facts.evidence_items:
        if not item.question:
            continue
        missing = ', '.join(item.missing_items)
        gaps.append(Gap(section='D', field='evidence_items', severity='warning',
                        message=f'Missing {missing}. {EJ_ROUTE}', fix_hint=EJ_ROUTE))
    return gaps


def gaps_summary(case: Case, codes) -> dict:
    officer = officer_gaps(case)
    try:
        found = check_completeness(case, codes)
    except Exception as exc:
        from .codes import CodeDbMissing
        if isinstance(exc, CodeDbMissing):
            return _unavailable(officer)
        raise
    gaps = list(found) + officer
    return {
        'unavailable': False,
        'detail': None,
        'blocking': sum(gap.severity == 'blocking' for gap in gaps),
        'warning': sum(gap.severity == 'warning' for gap in gaps),
        'fields': sorted({gap.field for gap in gaps}),
        'gaps': [gap.model_dump() for gap in gaps],
    }


def unavailable_summary(case: Case) -> dict:
    return _unavailable(officer_gaps(case))


def _unavailable(officer: list[Gap]) -> dict:
    return {
        'unavailable': True,
        'detail': 'code database not found',
        'blocking': None,
        'warning': len(officer),
        'fields': sorted({gap.field for gap in officer}),
        'gaps': [gap.model_dump() for gap in officer],
    }


def _values_match(gold, pred) -> bool:
    if isinstance(gold, (int, float)) and isinstance(pred, (int, float)):
        return abs(float(gold) - float(pred)) <= 0.02
    return gold == pred


def _list_match(field: str, gold, pred) -> bool:
    pred = pred or []
    if field == 'claimed_provisions':
        got = [item.get('entered') if isinstance(item, dict) else item.entered for item in pred]
        return got == [] if gold == [] else all(any(token in ''.join(got) for token in gold) for token in gold) and len(got) == len(gold)
    if field == 'claimed_exemptions':
        if gold in (None, []):
            return pred == [] or pred is None
        hits = 0
        for item in pred:
            data = item if isinstance(item, dict) else item.model_dump()
            if data.get('status') != gold.get('status', 'applicant_asserted'):
                continue
            if any(part not in data.get('text', '') for part in gold.get('contains', [])):
                continue
            if 'by' in gold and data.get('by') != gold['by']:
                continue
            hits += 1
        return hits == 1 and len(pred) == 1
    if field == 'claims':
        if gold in (None, []):
            return not pred
        hits = 0
        for item in pred:
            data = item if isinstance(item, dict) else item.model_dump()
            if data.get('status') != 'applicant_asserted':
                continue
            if all(part in data.get('text', '') for part in gold.get('contains', [])):
                hits += 1
        return hits == 1 and len(pred) == 1
    if field == 'evidence_items':
        if not gold:
            return not pred
        used = set()
        for expect in gold:
            hit = False
            for index, item in enumerate(pred):
                if index in used:
                    continue
                data = item if isinstance(item, dict) else item.model_dump()
                if data.get('kind') != expect['kind']:
                    continue
                if data.get('author_type') != expect['author_type']:
                    continue
                if data.get('signed') != expect.get('signed'):
                    continue
                if data.get('review_status') != expect.get('review_status', REVIEW_STATUS):
                    continue
                if set(data.get('missing_items') or []) != set(expect.get('missing_items') or []):
                    continue
                if 'stated_role' in expect and data.get('stated_role') != expect['stated_role']:
                    continue
                used.add(index)
                hit = True
                break
            if not hit:
                return False
        return len(used) == len(pred)
    return False


def score_prediction(expect: dict, facts: IntakeFacts) -> dict[str, tuple[int, int, int]]:
    """Per-field (tp, fp, fn). A null gold and a null prediction is not a true positive."""
    data = facts.model_dump(mode='json')
    scores = {field: (0, 0, 0) for field in (*SCALAR_FIELDS, 'claimed_provisions', 'claimed_exemptions', 'claims', 'evidence_items')}
    for field, gold in expect.items():
        if field not in scores:
            continue
        pred = data.get(field)
        if field in SCALAR_FIELDS:
            value = pred.get('value') if isinstance(pred, dict) else None
            if gold is None and value is None:
                continue
            if gold is None and value is not None:
                scores[field] = (0, 1, 0)
            elif gold is not None and value is None:
                scores[field] = (0, 0, 1)
            elif _values_match(gold, value):
                scores[field] = (1, 0, 0)
            else:
                scores[field] = (0, 1, 1)
        else:
            if gold in (None, []) and not pred:
                continue
            if _list_match(field, gold, pred):
                scores[field] = (1, 0, 0)
            elif gold in (None, []) and pred:
                scores[field] = (0, 1, 0)
            elif gold not in (None, []) and not pred:
                scores[field] = (0, 0, 1)
            else:
                scores[field] = (0, 1, 1)
    return scores


def departure_ok(facts: IntakeFacts, spec: dict | None) -> bool | None:
    if not spec:
        return None
    text = facts.proposed_alternative.value or ''
    if spec.get('exact') is not None and text != spec['exact']:
        return False
    if any(part not in text for part in spec.get('includes') or []):
        return False
    if any(part in text for part in spec.get('excludes') or []):
        return False
    return True


def combine(rows: list[dict[str, tuple[int, int, int]]]) -> dict[str, tuple[int, int, int]]:
    totals = {}
    fields = rows[0] if rows else {}
    for field in fields:
        tp = fp = fn = 0
        for row in rows:
            a, b, c = row.get(field, (0, 0, 0))
            tp += a
            fp += b
            fn += c
        totals[field] = (tp, fp, fn)
    return totals


def pr_line(counts: tuple[int, int, int]) -> tuple[float | None, float | None, float | None]:
    tp, fp, fn = counts
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    if precision is None or recall is None or precision + recall == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def micro(counts: dict[str, tuple[int, int, int]]) -> tuple[int, int, int]:
    return (sum(v[0] for v in counts.values()), sum(v[1] for v in counts.values()), sum(v[2] for v in counts.values()))


def _fmt(value: float | None) -> str:
    return '—' if value is None else f'{value:.3f}'


def format_table(title: str, counts: dict[str, tuple[int, int, int]]) -> str:
    lines = [f'### {title}', '', '| Field | TP | FP | FN | Precision | Recall |', '| --- | --- | --- | --- | --- | --- |']
    for field, triple in counts.items():
        if triple == (0, 0, 0):
            continue
        precision, recall, _ = pr_line(triple)
        lines.append(f'| {field} | {triple[0]} | {triple[1]} | {triple[2]} | {_fmt(precision)} | {_fmt(recall)} |')
    precision, recall, f1 = pr_line(micro(counts))
    tp, fp, fn = micro(counts)
    lines.append(f'| **micro** | {tp} | {fp} | {fn} | {_fmt(precision)} | {_fmt(recall)} |')
    lines.append('')
    lines.append(f'Micro F1 {_fmt(f1)}.')
    return '\n'.join(lines)


def score_eval(cases: list[dict]) -> dict:
    """Score the shipped extractor, and both approaches on the held-out pair."""
    def run(split_ok, approach=None):
        rows, departures = [], []
        for item in cases:
            if item['split'] not in split_ok:
                continue
            facts = extract(item['text'], approach=approach)
            rows.append(score_prediction(item['expect'], facts))
            flag = departure_ok(facts, item.get('departure'))
            if flag is not None and item.get('departure'):
                departures.append(flag)
        rate = f'{sum(departures)}/{len(departures)}' if departures else '—'
        return combine(rows), rate

    without, departure_without = run({'persona', 'negation'})
    with_cfx, departure_with = run({'persona', 'negation', 'cfx'})
    held_c, departure_held_c = run({'held_out'})
    held_r, departure_held_r = run({'held_out'}, approach='regex')
    rank = sorted(
        (('classifier', pr_line(micro(held_c))[2] or 0, departure_held_c),
         ('regex', pr_line(micro(held_r))[2] or 0, departure_held_r)),
        key=lambda item: (item[1], item[2]), reverse=True)
    shop = next(item['text'] for item in cases if item['id'] == 'approach-shop')
    classifier = extract(shop)
    regex = extract(shop, approach='regex')
    return {
        'without_cfx': without,
        'with_cfx': with_cfx,
        'held_classifier': held_c,
        'held_regex': held_r,
        'departure_without': departure_without,
        'departure_with': departure_with,
        'departure_held_classifier': departure_held_c,
        'departure_held_regex': departure_held_r,
        'winner': rank[0][0],
        'approach': {
            'classifier_storeys': classifier.storeys.value,
            'classifier_area': classifier.building_area_m2.value,
            'regex_storeys': regex.storeys.value,
            'regex_area': regex.building_area_m2.value,
        },
    }


def render_results(scored: dict) -> str:
    """Human-readable metric note. Labels are agent-authored and model-checked, not human-verified."""
    parts = [
        '# Fact extraction metrics',
        '',
        'Agent-authored, model-checked, not human-verified. Gold values are spans or direct readings of the pasted text. '
        'A field that is empty in both the gold and the prediction is not counted as a true positive.',
        '',
        'The shipped extractor is the sentence classifier. The regex baseline keeps every non-question sentence. '
        'Word-number storeys and square-foot conversion run only in the classifier. '
        'Persona, negation, and cfx scores are in-sample checks of those rules. '
        'The held-out pair was written down before either extractor was tuned, and the rules were not changed after this score. '
        'cfx-001 through cfx-005 are regression slices of '
        '`evals/demo-cases/b-contractor-firestop-nonconformance/input/` at 914b8ec. '
        'They are not the held-out set used to pick the winner.',
        '',
        format_table('Without cfx (persona and negation)', scored['without_cfx']),
        '',
        format_table('With cfx (persona, negation, and cfx-001–cfx-005)', scored['with_cfx']),
        '',
        format_table('Held-out, classifier', scored['held_classifier']),
        '',
        format_table('Held-out, regex', scored['held_regex']),
        '',
        f"Departure-only rate without cfx: {scored['departure_without']}.",
        f"Departure-only rate with cfx: {scored['departure_with']}.",
        f"Held-out departure-only, classifier: {scored['departure_held_classifier']}.",
        f"Held-out departure-only, regex: {scored['departure_held_regex']}.",
        '',
        f"Winner: **{scored['winner']}**. Chosen on held-out micro F1, then held-out departure-only rate.",
        '',
        'Approach check (not in the tables above): "two-storey" and "2,000 sq ft". '
        f"Classifier reads storeys {scored['approach']['classifier_storeys']} and area {scored['approach']['classifier_area']}. "
        f"Regex reads storeys {scored['approach']['regex_storeys']} and area {scored['approach']['regex_area']}.",
        '',
        'cfx-005 records the exemption as applicant_asserted, asks for evidence, and opens an officer gap. '
        'It does not answer the exemption. The speaker on that slice is the words in the slice (`The sub`). '
        'cfx-004 lists the evidence as listed_not_reviewed with the label `evidence_listed (not reviewed)` '
        'and the missing items signature, tested system, job name and location, and issuer qualifications. '
        'The route asks for an EJ from a qualified issuer. The officer decides.',
        '',
    ]
    return '\n'.join(parts)
