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
from .section_c import NOT_ATTRIBUTED, section_c_rows

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


class EvidencePlanItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    id: str
    provision_id: str
    citation: str
    attribution_status: AttributionStatus
    attributed_via: str | None = None
    attribution: Literal['not_attributed'] | None = None
    objective: str | None
    function: str | None
    function_text: str | None = None
    objective_text: str | None = None
    bracket: str | None = None
    clauses: tuple[str, ...] = ()
    application_note: str | None = None
    performance_issue: str
    recommended_types: tuple[EvidenceType, ...]
    responsible_party: str = ''
    status: Literal['not provided', 'provided'] = 'not provided'
    attachments: tuple[SupportingDocument, ...] = ()


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
    return docs


def section_d_plan(case: Case, codes: Codes, documents: list[SupportingDocument] | None = None) -> SectionDPlan:
    """Re-lookup only confirmed provisions; never trust client-supplied pairs or invent a missing row."""
    documents = supporting_documents(case) if documents is None else documents
    rows = section_c_rows(case.provisions, codes)
    recommended = CONFIDENCE_LADDER + (ALTERNATIVE_EVIDENCE_TYPES if alternative_path(case) else ())
    notices = ['Evidence types are recommendations, not results or an automatic acceptance ladder. '
               'The responsible designer must assess scope, code edition, installation differences and limitations.']
    if not rows:
        notices.append('Confirm the benchmark provisions before preparing the Section D evidence plan.')
    from .evidence_gaps import list_documents, no_table_note, pair_words

    confirmed = set(case.provisions)
    items: list[EvidencePlanItem] = []
    seen = set()
    for row in rows:
        # An article expands to every sentence. A sentence with no objectives-table row
        # is not a Section D item unless the applicant confirmed that sentence itself.
        no_table = not row.pairs and row.attribution == NOT_ATTRIBUTED
        if no_table and row.provision_id not in confirmed:
            continue
        pairs = row.pairs or [None]
        if no_table:
            note = no_table_note(row.provision_id)
            notices.append(note)
        for pair in pairs:
            key = (row.provision_id, pair.function if pair else None, pair.objective if pair else None,
                   pair.bracket if pair else None, tuple(pair.clauses) if pair else (), pair.application_note if pair else None)
            if key in seen:
                continue
            seen.add(key)
            eid = 'ev_' + hashlib.sha256(repr(key).encode()).hexdigest()[:16]
            attached = tuple(d for d in documents if eid in d.item_ids)
            if no_table:
                issue = no_table_note(row.provision_id)
            elif pair is None:
                issue = row.attribution_label or list_documents(row.provision_id)
            else:
                words = pair_words(pair.function_text, pair.objective_text)
                issue = list_documents(row.provision_id)
                if words:
                    issue += f' The objectives table describes this as: {words}.'
                if pair.application_note:
                    issue += f' This applies where: {pair.application_note}'
            items.append(EvidencePlanItem(id=eid, provision_id=row.provision_id, citation=row.citation,
                attribution_status=row.attribution_status, attributed_via=row.attributed_via,
                attribution=row.attribution,
                objective=pair.objective if pair else None, function=pair.function if pair else None,
                function_text=pair.function_text if pair else None,
                objective_text=pair.objective_text if pair else None,
                bracket=pair.bracket if pair else None, clauses=tuple(pair.clauses) if pair else (),
                application_note=pair.application_note if pair else None, performance_issue=issue,
                recommended_types=recommended, responsible_party='; '.join(dict.fromkeys(
                    d.responsible_party for d in attached if d.responsible_party.strip())),
                status='provided' if attached else 'not provided', attachments=attached))
    return SectionDPlan(items=items, notices=notices)
