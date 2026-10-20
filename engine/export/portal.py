"""Package prepared for the safety codes officer to register on the Orders and Variances Portal.

IB-2026-10-01: from 2026-12-01 the portal is the sole method; only a safety codes
officer registers; registration is not Council approval; the filled form and
supporting documentation go together; one variance is for one location;
unnecessary personal information in supporting documents is flagged so it can be
removed or redacted. This module does not edit files and does not decide that a
file is safe.

The 10-day copy in IB-2025-11-18 is a copy of the issued variance, attached as a
reminder, not as a pre-flight failure. Pre-flight reuses the completeness gates.

The OVP field list used below is unofficial. It was read from the public front
end at https://ovp.safetycodes.ab.ca/ before login on 2026-10-20, and mapped
field by field in docs/ovp-portal-fields.md. It is not SCC documentation. It
may change without notice, and it was not checked against the logged-in form.
Variance status, discipline, AHJ, employer, and code-set options load after
login, so those values are free text with a TODO. See docs/ovp-portal-fields.md.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..bulletin_gates import applicant_reminder, bulletin_gaps
from ..models import Case
from ..process_fields import confirmed_value

_EMAIL = re.compile(r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}', re.I)
_PHONE = re.compile(r'(?<!\d)(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4})(?!\d)')
# Sentence-level or finer, as the public bundle requires for the code disciplines:
# 3.5.2.1.(2), and an optional clause and subclause. Article-only ids do not match.
_SENTENCE = re.compile(r'^\d+\.\d+\.\d+\.\d+\.\(\d+\)(\([a-z]\)(\([ivxlcdm]+\))?)?$', re.I)
_POSTAL = re.compile(r'\b([A-Z]\d[A-Z])\s?(\d[A-Z]\d)\b', re.I)
_SPECIAL = re.compile(r'[\\/:*?"<>|]')
_PLAIN_NAME = re.compile(r'^[A-Za-z0-9._ -]{1,100}$')
_ALLOWED_SUFFIXES = {'.pdf', '.txt', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.csv'}
_MAX_BYTES = 25 * 1024 * 1024
_MAX_NAME = 100
_SENTENCE_FLAG = 'needs sentence-level reference'
_CIVIC_FLAG = 'civic address could not be parsed'
_FILE_MISSING = 'supporting document file missing'
# Retrieved 2026-10-20 from the pre-login bundle. The live lists are unknown.
_LIST_TODO = ('TODO: this OVP list loads after login. The value is free text until the official list is known. '
              'Unofficial field list, retrieved 2026-10-20; it may change.')
_BUILDING_CODE = re.compile(r'national building code|\bNBC\b', re.I)
_OTHER_CODE = re.compile(r'fire code|\bNFC\b|gas code|plumbing|electrical', re.I)
_PID_IN_TEXT = re.compile(
    r'\d+\.\d+\.\d+\.\d+\.?\s*\(\d+\)(?:\s*\([a-z]\))?(?:\s*\([ivxlcdm]+\))?', re.I)
_ARTICLE = re.compile(r'^\d+\.\d+\.\d+\.\d+\.?$')
_HOUSE_STREET = re.compile(r'^(\d+[A-Za-z]?)\s+(.+)$')
_SUITE = re.compile(r'^(?:suite|ste\.?|unit|apt\.?|#)\s*#?\s*([A-Za-z0-9-]+)$', re.I)
_PROVINCE = re.compile(r'^(?:Alberta|AB)$', re.I)
_QUARTER = {'NE', 'NW', 'SE', 'SW'}

# Unofficial labels. The registering officer fills these unless a value is derived below.
SCO_FIELDS = (
    'Issuing SCO',
    'Designation of Power',
    'Employer',
    'Discipline',
    'AHJ',
    'Variance status',
    'Issue Date',
)
# Dropdowns the bundle loads only after login. Never treat our text as the list value.
_LIST_FIELDS = ('Employer', 'Discipline', 'AHJ', 'Variance status')
DERIVED_ROLE = 'derived, free text'
# These stay inside the variance form PDF. The public bundle does not collect them for a variance.
NOT_OVP_FIELDS = ('owner', 'signature', 'objectives')
SCO_ROLE = 'filled by the registering SCO'


@dataclass
class PortalAttachment:
    name: str
    text: str
    needs_personal_information: bool = False
    size_bytes: int | None = None
    document_type: str = 'Supporting Document'
    data: bytes | None = None


@dataclass
class ManifestEntry:
    name: str
    role: str
    needs_personal_information: bool
    included: bool
    note: str
    value: str = ''


@dataclass
class RedactionFlag:
    attachment: str
    kind: str
    match: str
    bulletin_id: str
    message: str


@dataclass
class PortalLocation:
    """One of civic address, lot/block/plan, or ATS. Civic is not a hard requirement."""

    label: str
    ready: bool
    civic_street: str
    postal_code: str
    lot: str
    block: str
    plan: str
    ats_qtr: str
    ats_sec: str
    ats_twp: str
    ats_rge: str
    ats_mer: str
    note: str
    suite: str = ''
    house: str = ''
    municipality: str = ''
    unparsed: str = ''
    parsed: bool = False
    flag: str | None = None


@dataclass
class CodeItem:
    code_set: str
    reference: str
    sentence_level: bool
    flag: str | None = None
    candidates: list[str] = field(default_factory=list)


@dataclass
class NamedAttachment:
    document_type: str
    filename: str
    suggested_name: str
    data: bytes | None
    present: bool


@dataclass
class AttachmentCheck:
    name: str
    document_type: str
    format_ok: bool
    size_ok: bool | None
    name_ok: bool
    suggested_name: str
    problems: list[str] = field(default_factory=list)
    present: bool = True


@dataclass
class PortalPackage:
    bulletin_ids: tuple[str, ...]
    form_pdf: bytes | None
    form_included: bool
    form_note: str
    manifest: list[ManifestEntry] = field(default_factory=list)
    redaction_flags: list[RedactionFlag] = field(default_factory=list)
    preflight_reasons: list[str] = field(default_factory=list)
    reminder_verdict: str = 'reminder'
    reminder: str = ''
    reminder_links: list[str] = field(default_factory=list)
    location: PortalLocation | None = None
    code_items: list[CodeItem] = field(default_factory=list)
    attachment_checks: list[AttachmentCheck] = field(default_factory=list)
    documents_ready: bool = False
    not_ovp_fields: tuple[str, ...] = NOT_OVP_FIELDS
    portal_gaps: list[str] = field(default_factory=list)
    sidecar: dict = field(default_factory=dict)
    named_attachments: list[NamedAttachment] = field(default_factory=list)

    def text(self) -> str:
        lines = [
            'Portal registration package prepared for the safety codes officer to register',
            'Registration is not Council approval.',
            'OVP field list: unofficial, from the public front end before login, and it may change.',
            'Bulletins: ' + ', '.join(self.bulletin_ids),
            self.form_note,
            'Owner, signature and objectives stay in the variance form PDF. They are not OVP fields.',
            'Pre-flight:',
        ]
        lines += [f'- {reason}' for reason in self.preflight_reasons] or ['- none']
        lines.append('Manifest:')
        for item in self.manifest:
            value = ' value=(blank);' if item.role == SCO_ROLE else f' value={item.value!r};'
            lines.append(
                f'- {item.role}: {item.name}; included={item.included};{value} '
                f'needs_personal_information={item.needs_personal_information}; {item.note}')
        if self.location is not None:
            lines.append(
                f'{self.location.label}: ready={self.location.ready}; '
                f'street={self.location.civic_street!r}; postal_code={self.location.postal_code!r}; '
                f'{self.location.note}')
        lines.append('Code items:')
        lines += [
            f'- {item.code_set or "(no code set)"} {item.reference}'
            + (f' [{item.flag}]' if item.flag else '')
            + (f' candidates={", ".join(item.candidates)}' if item.candidates else '')
            for item in self.code_items] or ['- none']
        lines.append('Attachment checks:')
        lines += [
            f'- {item.document_type}: {item.name}; format_ok={item.format_ok}; '
            f'size_ok={item.size_ok}; name_ok={item.name_ok}; suggested={item.suggested_name}'
            for item in self.attachment_checks] or ['- none']
        lines.append(f'Documents ready (Variance Form and Supporting Document)={self.documents_ready}')
        lines.append('Redaction flags (not edited, not a safety finding):')
        lines += [f'- {flag.attachment}: {flag.kind} ({flag.bulletin_id})' for flag in self.redaction_flags] or ['- none']
        lines.append(self.reminder)
        return '\n'.join(lines) + '\n'


def _text(value) -> str:
    return '' if value is None else str(value).strip()


def parse_civic(raw: str) -> dict:
    """Split suite, house, street, municipality, and postal code from one address string.

    A string that does not match is kept whole and flagged. Components are not guessed.
    """
    text = re.sub(r'\s+', ' ', (raw or '').strip())
    empty = {'parsed': False, 'suite': '', 'house': '', 'street': '', 'municipality': '',
             'postal_code': '', 'unparsed': text, 'flag': _CIVIC_FLAG if text else None}
    if not text:
        return empty
    match = None
    for found in _POSTAL.finditer(text):
        match = found
    if match is None or text[match.end():].strip(' ,'):
        return empty
    postal = f'{match.group(1).upper()} {match.group(2).upper()}'
    body = text[:match.start()].strip(' ,')
    parts = [part.strip() for part in body.split(',') if part.strip()]
    if parts and _PROVINCE.match(parts[-1]):
        parts = parts[:-1]
    suite = ''
    if parts and (suite_match := _SUITE.match(parts[0])):
        suite = suite_match.group(1)
        parts = parts[1:]
    elif len(parts) >= 3 and (suite_match := _SUITE.match(parts[1])):
        suite = suite_match.group(1)
        parts = [parts[0], *parts[2:]]
    if len(parts) < 2:
        return empty
    municipality = parts[-1]
    street_part = parts[0]
    house_match = _HOUSE_STREET.match(street_part)
    if house_match is None or not municipality:
        return empty
    house, street = house_match.group(1), house_match.group(2).strip()
    if not street or not (house or suite):
        return empty
    return {'parsed': True, 'suite': suite, 'house': house, 'street': street, 'municipality': municipality,
            'postal_code': postal, 'unparsed': '', 'flag': None}


def _in_range(value: str, low: int, high: int) -> bool:
    return bool(re.fullmatch(r'\d+', value)) and low <= int(value) <= high


def _ats_complete(ats: dict[str, str]) -> bool:
    if not all(ats.values()):
        return False
    quarter = ats['ats_qtr'].upper()
    meridian = ats['ats_mer'].upper()
    return (quarter in _QUARTER and _in_range(ats['ats_sec'], 1, 36) and _in_range(ats['ats_twp'], 1, 126)
            and _in_range(ats['ats_rge'], 1, 30) and meridian in {'4', '5', '6', 'W4', 'W5', 'W6'})


def portal_location(case: Case) -> PortalLocation:
    """Civic Address, lot/block/plan, or ATS. Any one complete set is enough.

    The civic string is `municipal_address` (aliases `civic_address` and `address`).
    `municipal_address` is not required. A lot/block/plan or a complete ATS record
    satisfies the location without a civic string.
    """
    civic = _text(confirmed_value(case, 'municipal_address', 'municipalAddress', 'civic_address', 'address'))
    parsed = parse_civic(civic)
    civic_ok = parsed['parsed']
    lot = _text(confirmed_value(case, 'lot'))
    block = _text(confirmed_value(case, 'block'))
    plan = _text(confirmed_value(case, 'plan'))
    legal_ok = bool(lot and block and plan)
    ats = {key: _text(confirmed_value(case, key))
           for key in ('ats_qtr', 'ats_sec', 'ats_twp', 'ats_rge', 'ats_mer')}
    ats_ok = _ats_complete(ats)
    ready = civic_ok or legal_ok or ats_ok
    notes = []
    if parsed['flag']:
        notes.append(parsed['flag'] + '. The original string is kept.')
    if any(ats.values()) and not ats_ok:
        notes.append('ATS is incomplete or outside the unofficial OVP ranges '
                     '(section 1–36, township 1–126, range 1–30, meridian 4, 5, or 6).')
    if ready:
        notes.append('One of Civic Address, lot/block/plan, or ATS is complete. municipal_address is not required.')
    else:
        notes.append('Location is not ready for OVP. Provide a Civic Address that splits into house or suite, '
                     'street, municipality, and postal code, or lot, block and plan, or a complete ATS description. '
                     'Do not invent the missing parts.')
    return PortalLocation(
        'Civic Address', ready, parsed['street'], parsed['postal_code'], lot, block, plan,
        ats['ats_qtr'], ats['ats_sec'], ats['ats_twp'], ats['ats_rge'], ats['ats_mer'], ' '.join(notes),
        suite=parsed['suite'], house=parsed['house'], municipality=parsed['municipality'],
        unparsed=parsed['unparsed'], parsed=parsed['parsed'], flag=parsed['flag'])


def _references(case: Case) -> list[str]:
    found: list[str] = []
    for provision in list(case.provisions) + [row.provision_id for row in case.section_c]:
        token = _text(provision)
        if token and token not in found:
            found.append(token)
    article = confirmed_value(case, 'section_c.article', 'article')
    token = _text(article)
    if token and token not in found:
        found.append(token)
    return found


def _canon_sentence_id(token: str) -> str | None:
    compact = re.sub(r'\s+', '', token)
    match = re.fullmatch(
        r'(\d+\.\d+\.\d+\.\d+)\.?\((\d+)\)(\([a-z]\))?(\([ivxlcdm]+\))?', compact, re.I)
    if match is None:
        return None
    sentence = f'{match.group(1)}.({match.group(2)})'
    clause = (match.group(3) or '').lower()
    subclause = (match.group(4) or '').lower()
    canon = sentence + clause + subclause
    return canon if _SENTENCE.match(canon) else None


def _mentioned_sentences(case: Case, article: str) -> list[str]:
    """Sentence ids the case itself states. Nothing is read from the code database."""
    prefix = article.rstrip('.')
    blobs = [str(provision) for provision in case.provisions]
    blobs += [row.provision_id for row in case.section_c]
    for fact in case.facts:
        blobs.append('' if fact.value is None else str(fact.value))
        if fact.source.quote:
            blobs.append(fact.source.quote)
    found: list[str] = []
    for blob in blobs:
        for match in _PID_IN_TEXT.finditer(blob):
            canon = _canon_sentence_id(match.group(0))
            if canon and canon.startswith(prefix + '.') and canon not in found:
                found.append(canon)
    return found


def _codedb_sentences(article_id: str) -> list[str] | None:
    """Sentence children from codedb, or None when the database is not on this machine."""
    try:
        from codedb.api import children
    except ImportError:
        return None
    token = article_id if article_id.endswith('.') else article_id + '.'
    try:
        rows = children(token)
    except FileNotFoundError:
        return None
    except Exception:
        return None
    found = []
    for row in rows:
        if row.get('level') == 'sentence' and row.get('id') and row['id'] not in found:
            found.append(row['id'])
    return found


def _sentence_root(sentence_id: str) -> str:
    match = re.match(r'(\d+\.\d+\.\d+\.\d+\.\(\d+\))', sentence_id)
    return match.group(1) if match else sentence_id


def code_items_for(case: Case, *, sentence_lookup=None) -> list[CodeItem]:
    """Code Set / Standard plus each cited id.

    An article becomes a sentence only when the case's own facts or quote name that
    sentence and codedb lists it. Several possible sentences stay candidates under
    'needs sentence-level reference'. One is never picked for the applicant.
    """
    code_set = _text(confirmed_value(case, 'code_or_standard', 'code_set'))
    lookup = _codedb_sentences if sentence_lookup is None else sentence_lookup
    items = []
    for reference in _references(case):
        compact = re.sub(r'\s+', '', reference)
        sentence = _canon_sentence_id(compact)
        if sentence and _SENTENCE.match(sentence):
            items.append(CodeItem(code_set, sentence, True, None))
            continue
        if not _ARTICLE.match(compact):
            items.append(CodeItem(code_set, reference, False, _SENTENCE_FLAG))
            continue
        article = compact if compact.endswith('.') else compact + '.'
        mentioned = _mentioned_sentences(case, article)
        # The article id itself is not a sentence the case identified.
        mentioned = [item for item in mentioned if item.rstrip('.') != article.rstrip('.')]
        known = lookup(article)
        if known is None:
            items.append(CodeItem(code_set, reference, False, _SENTENCE_FLAG, mentioned))
            continue
        known_roots = {_sentence_root(item) for item in known}
        identified = [item for item in mentioned if _sentence_root(item) in known_roots or item in known]
        if len(identified) == 1:
            items.append(CodeItem(code_set, identified[0], True, None))
            continue
        candidates = identified or list(known)
        items.append(CodeItem(code_set, reference, False, _SENTENCE_FLAG, candidates))
    return items


def suggest_filename(name: str) -> str:
    """A file name within 100 characters and without special characters. The original is not renamed."""
    cleaned = _SPECIAL.sub('-', name or '')
    cleaned = re.sub(r'[^A-Za-z0-9._ -]', '-', cleaned)
    cleaned = re.sub(r'-{2,}', '-', cleaned).strip(' .-')
    if not cleaned:
        cleaned = 'attachment'
    suffix = ''
    if '.' in cleaned:
        base, ext = cleaned.rsplit('.', 1)
        if 1 <= len(ext) <= 5:
            suffix = '.' + ext
            cleaned = base
    room = _MAX_NAME - len(suffix)
    cleaned = cleaned[:room].rstrip(' .-')
    if not cleaned:
        cleaned = 'attachment'
    return (cleaned + suffix)[:_MAX_NAME]


def check_attachment(name: str, document_type: str, size_bytes: int | None) -> AttachmentCheck:
    suffix = ''
    if '.' in (name or ''):
        suffix = name[name.rfind('.'):].casefold()
    format_ok = suffix in _ALLOWED_SUFFIXES
    if size_bytes is None:
        size_ok = None
    else:
        size_ok = 0 <= size_bytes <= _MAX_BYTES
    name_ok = bool(_PLAIN_NAME.match(name or ''))
    problems = []
    if document_type not in ('Variance Form', 'Supporting Document'):
        problems.append('Tag the file Variance Form or Supporting Document.')
    if not format_ok:
        problems.append('Allowed formats are PDF, TXT, JPG, PNG, TIF, and CSV.')
    if size_ok is False:
        problems.append('The file is over the 25 MB limit.')
    elif size_ok is None:
        problems.append('File size was not supplied, so the 25 MB limit was not checked.')
    if not name_ok:
        problems.append('The file name must be 100 characters or fewer and have no special characters.')
    return AttachmentCheck(
        name or '', document_type, format_ok, size_ok, name_ok, suggest_filename(name or ''), problems)


def _blank_sco(label: str) -> ManifestEntry:
    note = 'Left blank for the registering safety codes officer. Not auto-filled. Unofficial OVP field; the list may change.'
    if label in _LIST_FIELDS:
        note = f'{note} {_LIST_TODO}'
    return ManifestEntry(label, SCO_ROLE, False, False, note, value='')


def derive_ahj(case: Case) -> str:
    """The organisation on Case.jurisdiction, only when name and authority do not disagree."""
    jurisdiction = case.jurisdiction
    if jurisdiction is None:
        return ''
    name = (jurisdiction.name or '').strip()
    authority = (jurisdiction.authority or '').strip()
    if name and authority and name.casefold() != authority.casefold():
        return ''
    return authority or name


def derive_discipline(case: Case) -> str:
    """Free-text Building only when the jurisdiction is set and the code set is NBC alone.

    Case.jurisdiction has no discipline. A fire, gas, plumbing, or electrical code,
    or a missing code set, is not an unambiguous map, so the field stays blank.
    """
    if case.jurisdiction is None:
        return ''
    code = _text(confirmed_value(case, 'code_or_standard', 'code_set'))
    if not code or _OTHER_CODE.search(code) or not _BUILDING_CODE.search(code):
        return ''
    return 'Building'


def _sco_entries(case: Case) -> list[ManifestEntry]:
    derived = {'AHJ': derive_ahj(case), 'Discipline': derive_discipline(case)}
    entries = []
    for label in SCO_FIELDS:
        value = derived.get(label, '')
        if not value:
            entries.append(_blank_sco(label))
            continue
        entries.append(ManifestEntry(
            label, DERIVED_ROLE, False, True,
            f'{_LIST_TODO} Derived from Case.jurisdiction. Not an OVP list id.',
            value=value))
    return entries


def _permit_entry(case: Case) -> ManifestEntry:
    permit = _text(confirmed_value(case, 'permit_number', 'permitNumber'))
    return ManifestEntry(
        'Permit #', 'optional', False, bool(permit),
        'Optional. Not invented.' if permit else 'Optional. Not supplied.',
        value=permit)


def _preflight_reasons(case: Case, codes) -> list[str]:
    from ..completeness_variants import format_export_reason

    if codes is not None:
        from ..completeness import check_completeness
        gaps = check_completeness(case, codes)
    else:
        gaps = bulletin_gaps(case)
    return [format_export_reason(gap.section, gap.field, gap.message, gap.fix_hint)
            for gap in gaps if gap.severity == 'blocking']


def _flags(attachments: list[PortalAttachment]) -> list[RedactionFlag]:
    found = []
    for attachment in attachments:
        if attachment.needs_personal_information or attachment.document_type == 'Variance Form':
            continue
        for kind, pattern in (('email', _EMAIL), ('phone', _PHONE)):
            for match in pattern.findall(attachment.text or ''):
                found.append(RedactionFlag(
                    attachment=attachment.name, kind=kind, match=match, bulletin_id='IB-2026-10-01',
                    message=(f'IB-2026-10-01: supporting attachment "{attachment.name}" includes a {kind}. '
                             'Unnecessary personal information should be removed or redacted before the safety '
                             'codes officer registers the variance. Registration is not Council approval. '
                             'This check does not edit the file and does not decide that the file is safe.')))
    return found


def _list_value(value: str) -> dict:
    return {'value': value or None, 'free_text': True, 'todo': _LIST_TODO}


def _attachment_bytes(attachment: PortalAttachment) -> bytes | None:
    if attachment.data is not None:
        return attachment.data
    if attachment.text:
        return attachment.text.encode('utf-8')
    return None


def _covered(name: str, attachments: list[PortalAttachment]) -> bool:
    wanted = Path(name).name
    for attachment in attachments:
        if attachment.document_type != 'Supporting Document':
            continue
        if _attachment_bytes(attachment) is None:
            continue
        if Path(attachment.name).name == wanted:
            return True
    return False


def name_only_supporting(case: Case, attachments: list[PortalAttachment]) -> list[str]:
    """Names the case stores without file bytes.

    POST /cases/{id}/files on backend/case-api (PR #21) writes `file.<id>.name`
    onto the case and keeps the PDF bytes outside the case JSON. A supporting
    document whose file ref is not a readable file is the same situation.
    """
    missing: list[str] = []

    def add(name: str) -> None:
        token = _text(name)
        if token and token not in missing and not _covered(token, attachments):
            missing.append(token)

    for fact in case.facts:
        if fact.status != 'confirmed' or fact.kind == 'proposed':
            continue
        if re.fullmatch(r'file\.[^.]+\.name', fact.field):
            add(str(fact.value))
        elif re.fullmatch(r'supporting_doc\.\d+\.name', fact.field):
            add(str(fact.value))
    from ..section_d import supporting_documents
    for document in supporting_documents(case):
        ref = document.file.ref
        if Path(ref).is_file():
            continue
        add(document.title or ref)
    return missing


def _sidecar(case: Case, location: PortalLocation, items: list[CodeItem],
             named: list[NamedAttachment], gaps: list[str], sco: list[ManifestEntry]) -> dict:
    by_name = {entry.name: entry for entry in sco}
    permit = _text(confirmed_value(case, 'permit_number', 'permitNumber'))

    def plain(label: str):
        entry = by_name[label]
        return entry.value or None

    return {
        'unofficial': True,
        'retrieved': '2026-10-20',
        'source': ('OVP public front end before login, plus IB-2026-10-01. Not official documentation. '
                   'It may change.'),
        'issuing_sco': plain('Issuing SCO'),
        'designation_of_power': plain('Designation of Power'),
        'employer': _list_value(by_name['Employer'].value),
        'discipline': _list_value(by_name['Discipline'].value),
        'ahj': _list_value(by_name['AHJ'].value),
        'variance_status': _list_value(by_name['Variance status'].value),
        'issue_date': plain('Issue Date'),
        'permit_number': permit or None,
        'civic_address': {
            'label': 'Civic Address',
            'suite': location.suite,
            'house': location.house,
            'street': location.civic_street,
            'municipality': location.municipality,
            'postal_code': location.postal_code,
            'unparsed': location.unparsed or None,
            'flag': location.flag,
        },
        'legal_description': {'lot': location.lot, 'block': location.block, 'plan': location.plan},
        'ats': {
            'quarter': location.ats_qtr, 'section': location.ats_sec, 'township': location.ats_twp,
            'range': location.ats_rge, 'meridian': location.ats_mer,
        },
        'code_items': [{
            'code_set': _list_value(item.code_set),
            'reference': item.reference,
            'sentence_level': item.sentence_level,
            'flag': item.flag,
            'candidates': list(item.candidates),
        } for item in items],
        'not_ovp_fields': list(NOT_OVP_FIELDS),
        'attachments': [{
            'document_type': item.document_type,
            'name': item.filename,
            'suggested_name': item.suggested_name,
            'present': item.present,
        } for item in named],
        'portal_gaps': list(gaps),
    }


def write_portal_package(package: PortalPackage, directory: Path) -> Path:
    """Write the JSON sidecar and any named attachment bytes. Files are not renamed on the case."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'ovp-sidecar.json'
    path.write_text(json.dumps(package.sidecar, indent=2) + '\n')
    used: set[str] = set()
    for item in package.named_attachments:
        if not item.present or item.data is None:
            continue
        name = item.suggested_name
        if name in used:
            stem, dot, ext = name.rpartition('.')
            count = 2
            while f'{stem}-{count}.{ext}' in used:
                count += 1
            name = f'{stem}-{count}.{ext}'
        used.add(name)
        (directory / name).write_bytes(item.data)
    return path


def portal_package(case: Case, *, codes=None, attachments: list[PortalAttachment] | None = None,
                   form=None, sentence_lookup=None) -> PortalPackage:
    """Filled form, attachment manifest, redaction flags, and the shared completeness pre-flight.

    SCO-side OVP fields are appended to the manifest blank. Owner, signature and
    objectives are not copied onto those fields.
    """
    from .scc import ExportBlocked, FormNotFound, export_case

    attachments = list(attachments or [])
    reminder = applicant_reminder()
    reasons = _preflight_reasons(case, codes)
    form_pdf = None
    if reasons:
        form_note = (
            'The filled form was not produced because the completeness pre-flight has open items. '
            'This package is prepared for the safety codes officer to register. Registration is not '
            'Council approval. IB-2026-10-01.')
    else:
        try:
            # Import stays local so this module does not change scc.py path handling.
            result = export_case(case, codes=codes, form=form)
        except ExportBlocked as exc:
            form_note = (
                'The filled form was not produced because export pre-flight refused the case. '
                'This package is prepared for the safety codes officer to register. Registration is not '
                'Council approval. IB-2026-10-01.')
            if not reasons:
                reasons = list(exc.reasons)
        except FormNotFound:
            form_note = (
                'The SCC variance form file is not on this machine, so the filled form was not produced. '
                'This package is prepared for the safety codes officer to register. Registration is not '
                'Council approval. IB-2026-10-01.')
        except FileNotFoundError:
            form_note = (
                'The code database is not on this machine, so the filled form was not produced. '
                'This package is prepared for the safety codes officer to register. Registration is not '
                'Council approval. IB-2026-10-01.')
        else:
            form_pdf = result.pdf
            form_note = (
                'Filled variance form included in the package prepared for the safety codes officer to register. '
                'IB-2026-10-01. Registration is not Council approval. '
                'The form does not replace the supporting documentation.')
    attachment_checks: list[AttachmentCheck] = []
    if form_pdf is not None:
        attachment_checks.append(check_attachment('Variance-form.pdf', 'Variance Form', len(form_pdf)))
    manifest = [ManifestEntry(
        'Variance form', 'form', True, form_pdf is not None,
        'Variance Form. Personal information belongs on the form. Prepared for the safety codes officer '
        'to register. Registration is not Council approval. IB-2026-10-01. '
        'Owner, signature and objectives stay in this PDF and are not separate OVP fields.')]
    saw_supporting = False
    for attachment in attachments:
        document_type = attachment.document_type or 'Supporting Document'
        if document_type == 'Supporting Document':
            saw_supporting = True
        check = check_attachment(attachment.name, document_type, attachment.size_bytes)
        attachment_checks.append(check)
        manifest.append(ManifestEntry(
            attachment.name, 'supporting' if document_type == 'Supporting Document' else 'form',
            attachment.needs_personal_information, True,
            f'{document_type}. Suggested file name: {check.suggested_name}. '
            'Registration is not Council approval. IB-2026-10-01.',
            value=''))
    has_variance_form = form_pdf is not None or any(
        item.document_type == 'Variance Form' for item in attachments)
    if not has_variance_form:
        missing_form = check_attachment('Variance-form.pdf', 'Variance Form', None)
        missing_form.present = False
        missing_form.problems.append('A Variance Form file is required.')
        attachment_checks.append(missing_form)
    if not saw_supporting:
        missing_support = AttachmentCheck(
            '', 'Supporting Document', False, None, False, 'supporting-document.pdf',
            ['A Supporting Document is required.'], present=False)
        attachment_checks.append(missing_support)
    sco = _sco_entries(case)
    manifest.extend(sco)
    manifest.append(_permit_entry(case))
    present = [item for item in attachment_checks if item.present]
    present_types = {item.document_type for item in present}
    documents_ready = (
        'Variance Form' in present_types and 'Supporting Document' in present_types
        and all(item.format_ok and item.name_ok and item.size_ok is True and not item.problems
                for item in present))
    from ..completeness_variants import format_export_reason

    missing_files = name_only_supporting(case, attachments)
    portal_gaps: list[str] = []
    if missing_files:
        portal_gaps.append(_FILE_MISSING)
        reasons.append(format_export_reason(
            'D', 'supporting_document', _FILE_MISSING,
            'The case stores these supporting files by name only: ' + ', '.join(missing_files) + '. '
            'POST /cases/{id}/files on backend/case-api keeps the bytes outside the case JSON. '
            'Attach the file before registration.'))
        documents_ready = False
    location = portal_location(case)
    items = code_items_for(case, sentence_lookup=sentence_lookup)
    named: list[NamedAttachment] = []
    if form_pdf is not None:
        named.append(NamedAttachment('Variance Form', 'Variance-form.pdf', 'Variance-form.pdf', form_pdf, True))
    for attachment in attachments:
        payload = _attachment_bytes(attachment)
        check = next((item for item in attachment_checks if item.name == attachment.name), None)
        suggested = check.suggested_name if check else suggest_filename(attachment.name)
        named.append(NamedAttachment(
            attachment.document_type or 'Supporting Document', attachment.name, suggested, payload,
            payload is not None))
    for name in missing_files:
        if not any(item.filename == name for item in named):
            named.append(NamedAttachment('Supporting Document', name, suggest_filename(name), None, False))
    sidecar = _sidecar(case, location, items, named, portal_gaps, sco)
    return PortalPackage(
        bulletin_ids=('IB-2026-10-01', 'IB-2025-11-18', 'IB-2026-10-16'),
        form_pdf=form_pdf, form_included=form_pdf is not None, form_note=form_note, manifest=manifest,
        redaction_flags=_flags(attachments), preflight_reasons=reasons,
        reminder_verdict=reminder['verdict'], reminder=reminder['text'], reminder_links=list(reminder['links']),
        location=location, code_items=items,
        attachment_checks=attachment_checks, documents_ready=documents_ready,
        portal_gaps=portal_gaps, sidecar=sidecar, named_attachments=named)
