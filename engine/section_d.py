"""Evidence recommendations linked to confirmed, database-derived Section C rows.

Each performance issue offers evidence *types*, in the brief's confidence order. These are
choices to discuss with the responsible designer, not a requirement to commission every type.
No test, evaluation, professional opinion or result is generated here.
"""
from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .codes import Codes
from .models import AttributionStatus, Case, Source
from .process_fields import alternative_path, confirmed_value, latest_fact
from .section_c import section_c_rows

EvidenceType = Literal["manufacturer's literature", 'existing STANDATA variance', 'ISO 17025 test report',
                       'evaluation', 'evaluation + testing', 'qualification', 'ISO 17065 certification',
                       'CCMC evaluation', 'ICC-ES evaluation', 'registered professional opinion', 'engineering review']
CONFIDENCE_LADDER: tuple[EvidenceType, ...] = (
    "manufacturer's literature", 'existing STANDATA variance', 'ISO 17025 test report', 'evaluation',
    'evaluation + testing', 'qualification', 'ISO 17065 certification')
ALTERNATIVE_EVIDENCE_TYPES: tuple[EvidenceType, ...] = (
    'CCMC evaluation', 'ICC-ES evaluation', 'registered professional opinion', 'engineering review')


class FileSource(Source):
    model_config = ConfigDict(frozen=True, extra='forbid')
    type: Literal['file'] = 'file'
    ref: str = Field(min_length=1)


class SupportingDocument(BaseModel):
    """Metadata supplied by the applicant; file presence says nothing about technical adequacy."""
    model_config = ConfigDict(frozen=True, extra='forbid')
    id: str
    title: str
    file: FileSource
    item_ids: tuple[str, ...] = ()
    responsible_party: str = ''
    issuer: str = ''
    date: str | None = None
    professional_seal: str | None = None


class ApplicantStatement(BaseModel):
    """Words the applicant typed. The label is not a verification and not a professional opinion."""
    model_config = ConfigDict(frozen=True, extra='forbid')
    id: str
    title: str
    text: str
    label: Literal['stated by applicant, not verified'] = 'stated by applicant, not verified'
    source_ref: str
    item_ids: tuple[str, ...] = ()
    responsible_party: str = ''


class EvidencePlanItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    id: str
    provision_id: str
    citation: str
    attribution_status: AttributionStatus
    attributed_via: str | None = None
    objective: str | None
    function: str | None
    bracket: str | None = None
    clauses: tuple[str, ...] = ()
    application_note: str | None = None
    performance_issue: str
    recommended_types: tuple[EvidenceType, ...]
    responsible_party: str = ''
    status: Literal['not provided', 'provided'] = 'not provided'
    attachments: tuple[SupportingDocument, ...] = ()
    statements: tuple[ApplicantStatement, ...] = ()


class SectionDPlan(BaseModel):
    items: list[EvidencePlanItem]
    notices: list[str]


def supporting_documents(case: Case) -> list[SupportingDocument]:
    """Read attachment metadata without changing the shared Case schema.

    Ledger contract: ``evidence.<id>.file_ref`` is a confirmed file-source fact whose value
    equals source.ref. Other fields are ``title``, ``responsible_party``, ``issuer``, ``date``,
    ``professional_seal`` and ``item_id``. An id equal to a plan-item id links automatically.
    Repeated ``evidence.<id>.covers.<plan id> = True`` facts link one report to several issues.
    """
    ids = {e.id for e in case.evidence}
    for fact in case.facts:
        if fact.field.startswith('evidence.') and fact.field.endswith('.file_ref'):
            ids.add(fact.field[len('evidence.'):-len('.file_ref')])
    legacy = {e.id: e for e in case.evidence}
    docs = []
    for eid in sorted(ids):
        prefix = f'evidence.{eid}.'
        fact = latest_fact(case, prefix + 'file_ref')
        if not (fact and fact.status == 'confirmed' and fact.kind != 'proposed'
                and fact.source.type == 'file' and fact.value == fact.source.ref and fact.source.ref.strip()):
            continue
        metadata = {name: confirmed_value(case, prefix + name) for name in
                    ('title', 'responsible_party', 'issuer', 'date', 'professional_seal', 'item_id')}
        links = [eid]
        if isinstance(metadata['item_id'], str):
            links.append(metadata['item_id'])
        for entry in case.facts:
            if entry.field.startswith(prefix + 'covers.') and confirmed_value(case, entry.field) is True:
                links.append(entry.field[len(prefix + 'covers.'):])
        text = lambda key: metadata[key] if isinstance(metadata[key], str) else ''  # noqa: E731
        title = text('title')
        if not title:
            title = ('(title not provided or not confirmed)' if latest_fact(case, prefix + 'title') is not None else
                     legacy[eid].description if eid in legacy else eid)
        docs.append(SupportingDocument(id=eid, title=title,
                    file=FileSource(**fact.source.model_dump()), item_ids=tuple(dict.fromkeys(links)),
                    responsible_party=text('responsible_party'), issuer=text('issuer'), date=text('date') or None,
                    professional_seal=text('professional_seal') or None))
    docs.extend(_upload_documents(case, {doc.id for doc in docs}))
    return docs


def _upload_documents(case: Case, seen: set[str]) -> list[SupportingDocument]:
    """Files stored by POST /cases/{id}/files on backend/case-api (#21).

    That route writes ``file.{id}.name`` with ``source.type`` ``file`` and ``source.ref`` equal to the id.
    The bytes stay on disk under BATATIS_FILES. This reader uses the fact, not the bytes.
    """
    found = []
    for fact in case.facts:
        if not fact.field.startswith('file.') or not fact.field.endswith('.name'):
            continue
        file_id = fact.field[len('file.'):-len('.name')]
        if not file_id or '/' in file_id or '\\' in file_id or file_id in seen:
            continue
        if not (fact.status == 'confirmed' and fact.kind != 'proposed' and fact.source.type == 'file'
                and fact.source.ref == file_id and isinstance(fact.value, str) and fact.value.strip()):
            continue
        found.append(SupportingDocument(
            id=file_id, title=fact.value.strip(), file=FileSource(**fact.source.model_dump())))
    return found


def applicant_statements(case: Case) -> list[ApplicantStatement]:
    """Confirmed ``evidence.<id>.statement`` facts typed by the applicant.

    ``provided`` on a plan item means the applicant supplied this text. It does not mean the text was verified,
    and this function does not create a professional seal or an evidence result.
    """
    ids = set()
    for fact in case.facts:
        if fact.field.startswith('evidence.') and fact.field.endswith('.statement'):
            ids.add(fact.field[len('evidence.'):-len('.statement')])
    statements = []
    for eid in sorted(ids):
        prefix = f'evidence.{eid}.'
        fact = latest_fact(case, prefix + 'statement')
        if not (fact and fact.status == 'confirmed' and fact.kind != 'proposed'
                and fact.source.type == 'user_text' and isinstance(fact.value, str) and fact.value.strip()):
            continue
        title = confirmed_value(case, prefix + 'title')
        if not isinstance(title, str) or not title.strip():
            title = ' '.join(fact.value.split()[:12])
        who = confirmed_value(case, prefix + 'responsible_party')
        links = [eid]
        for entry in case.facts:
            if entry.field.startswith(prefix + 'covers.') and confirmed_value(case, entry.field) is True:
                links.append(entry.field[len(prefix + 'covers.'):])
        statements.append(ApplicantStatement(
            id=eid, title=title.strip(), text=fact.value.strip(), source_ref=fact.source.ref,
            item_ids=tuple(dict.fromkeys(links)),
            responsible_party=who.strip() if isinstance(who, str) else ''))
    return statements


def supply_status(has_file: bool, has_statement: bool) -> Literal['not provided', 'provided']:
    """Applicant-supplied material is ``provided``. Nothing in this module is ``verified``."""
    return 'provided' if has_file or has_statement else 'not provided'


def section_d_plan(case: Case, codes: Codes, documents: list[SupportingDocument] | None = None) -> SectionDPlan:
    """Re-lookup only confirmed provisions; never trust client-supplied pairs or invent a missing row."""
    documents = supporting_documents(case) if documents is None else documents
    statements = applicant_statements(case)
    rows = section_c_rows(case.provisions, codes)
    recommended = CONFIDENCE_LADDER + (ALTERNATIVE_EVIDENCE_TYPES if alternative_path(case) else ())
    notices = ['Evidence types are recommendations, not results or an automatic acceptance ladder. '
               'The responsible designer must assess scope, code edition, installation differences and limitations.']
    if not rows:
        notices.append('Confirm the benchmark provisions before preparing the Section D evidence plan.')
    items: list[EvidencePlanItem] = []
    seen = set()
    for row in rows:
        pairs = row.pairs or [None]
        if not row.pairs:
            notices.append(f'{row.provision_id}: no row in the attribution table. Identify the applicable performance '
                           'benchmark with the responsible designer; no objective/function is inferred.')
        for pair in pairs:
            key = (row.provision_id, pair.function if pair else None, pair.objective if pair else None,
                   pair.bracket if pair else None, tuple(pair.clauses) if pair else (), pair.application_note if pair else None)
            if key in seen:
                continue
            seen.add(key)
            eid = 'ev_' + hashlib.sha256(repr(key).encode()).hexdigest()[:16]
            attached = tuple(d for d in documents if eid in d.item_ids)
            stated = tuple(s for s in statements if eid in s.item_ids)
            issue = (f'Provide a comparison with the acceptable-solution performance for {row.provision_id}. '
                     f'Address {pair.function}: {pair.function_text or pair.function}; '
                     f'{pair.objective}: {pair.objective_text or pair.objective}. '
                     'Identify the proposed configuration, comparison method, supporting report passages, differences and limits.'
                     if pair else 'The attribution table has no row for this provision. Ask the responsible designer '
                     'to identify the applicable benchmark before selecting performance evidence.')
            if pair and pair.application_note:
                issue += f' Attribution condition: {pair.application_note}'
            items.append(EvidencePlanItem(id=eid, provision_id=row.provision_id, citation=row.citation,
                attribution_status=row.attribution_status, attributed_via=row.attributed_via,
                objective=pair.objective if pair else None, function=pair.function if pair else None,
                bracket=pair.bracket if pair else None, clauses=tuple(pair.clauses) if pair else (),
                application_note=pair.application_note if pair else None, performance_issue=issue,
                recommended_types=recommended, responsible_party='; '.join(dict.fromkeys(
                    d.responsible_party for d in attached if d.responsible_party.strip())),
                status=supply_status(bool(attached), bool(stated)), attachments=attached, statements=stated))
    return SectionDPlan(items=items, notices=notices)
