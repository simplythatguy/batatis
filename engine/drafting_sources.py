"""Build bounded, reproducible drafting inputs from owned bytes and canonical resources."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from pypdfium2 import PdfiumError

from .ccmc import CCMCRegistry, RegistrySearch, RegistryUnavailable
from .drafting_registry import product_queries
from .intake.pdf import MAX_PAGES, NotAPdf, page_texts
from .intake.extract import DESCRIPTION_REF
from .models import Case
from .models_drafting import DraftSource, DraftRegistryQuery
from .process_fields import PROCESS_ALIASES, process_fields
from .professional import professional_involvement
from .redact import PERSONAL_FIELDS, PERSONAL_SUFFIXES, known_values, scrub, scrub_obj
from .section_c import section_c_rows

MAX_SOURCE_CHARS = 16000
MAX_CONTEXT_CHARS = 150000
MAX_FILES = 30
VERSION = 'applicant-drafting-v1'
ARTICLE = re.compile(r'(?<![\w.])\d{1,2}(?:\.\d{1,3}){3}\.?(?:\(\d+\)(?:\([a-z]+\))?)?(?!\w|\.\d)')
TITLES = {
    'alternative_description': 'Proposed alternative', 'evidence_plan': 'Supporting evidence plan',
    **{f'process.{fid}': title for fid, title in (
        ('rationale', 'Rationale'), ('risk_assessment', 'Risk assessment'),
        ('mitigating_measures', 'Mitigating measures'), ('assumptions_and_limits', 'Assumptions and limits'),
        ('maintenance_operation', 'Maintenance and operation'), ('qualifications', 'Qualifications'))},
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def generated_fact(fact, case: Case) -> bool:
    if fact.source.ref.startswith('applicant-draft:'):
        return True
    # Older/generated wording must not become its own corroboration when copied into another fact.
    originals = {s.ref for s in case.drafting.sources if s.kind in {'fact', 'description'}} if case.drafting else set()
    return bool(case.drafting and fact.id not in originals and isinstance(fact.value, str) and any(
        draft.text and fact.value.strip() == draft.text.strip() for draft in case.drafting.drafts))


def input_facts(case: Case):
    accepted_ids = {d.accepted_fact_id for d in case.drafting.drafts if d.status == 'accepted'} if case.drafting else set()
    latest = {}
    for fact in case.facts:
        if fact.id not in accepted_ids:
            latest[fact.field] = fact
    return list(latest.values())


def aliases(field: str) -> tuple[str, ...]:
    if field == 'alternative_description':
        return ('alternative_description', 'alternative')
    if field.startswith('process.'):
        names = PROCESS_ALIASES[field.split('.', 1)[1]]
        return (*('process.' + name for name in names), *names)
    return (field,)


def has_answer(case: Case, field: str) -> bool:
    fact = next((f for f in reversed(case.facts) if f.field in aliases(field)), None)
    # Never replace even an unconfirmed applicant revision. Explicitly empty withdrawals allow new writing.
    return fact is not None and fact.value is not None and str(fact.value).strip() != ''


def rough_alternative(case: Case):
    """Only auto-read, verified verbatim prose may be replaced, and only by an explicit draft decision."""
    latest = next((f for f in reversed(case.facts) if f.field in aliases('alternative_description')), None)
    if (latest is None or case.intake is None or latest.kind != 'pointed' or latest.status != 'confirmed'
            or not isinstance(latest.value, str) or latest.value != latest.source.quote
            or generated_fact(latest, case)):
        return None
    pointer = next((p for p in case.intake.pointers if p.fact_id == latest.id and p.verified
                    and p.method in {'rules', 'model'} and p.start is not None and p.end is not None), None)
    if pointer is None:
        return None
    if latest.source.type == 'user_text' and latest.source.ref == DESCRIPTION_REF and pointer.source_ref == 'description':
        description = next((f for f in reversed(case.facts) if f.field == 'project.description'), None)
        if (description is not None and isinstance(description.value, str)
                and description.value[pointer.start:pointer.end] == latest.value):
            return latest
    if (latest.source.type == 'file' and pointer.source_ref == latest.source.ref
            and pointer.page == latest.source.page):
        return latest
    # A form's typed answer and any subsequent user answer/click are intentional writing, never rough input.
    return None


@dataclass
class Inputs:
    fingerprint: str
    resources: list[DraftSource]
    files: list[dict]
    fields: list[str]
    professional_required: bool
    replacements: dict[str, str] = field(default_factory=dict)


def read_inputs(case: Case, store, codes, *, include_bytes: bool = False) -> Inputs:
    """Also used after slow generation and on reads; hashes every owned file, without calling a provider."""
    resources = []

    def add(kind, ref, label, text, **kw):
        resources.append(DraftSource(id='', kind=kind, ref=ref, label=label, text=text, **kw))

    facts = input_facts(case)
    clean_case = case.model_copy(deep=True, update={'facts': facts})
    rows = section_c_rows(case.provisions, codes) if case.provisions else []
    for pid in dict.fromkeys([*case.provisions, *(row.provision_id for row in rows)]):
        rec = codes.provision(pid, 'B')
        if rec is None:
            raise KeyError('confirmed provision unavailable')
        add('code', pid, rec['citation'], rec['text'], page=rec.get('pdf_page'),
            metadata={'division': 'B', 'provision_id': pid})
    for row in rows:
        add('section_c', row.provision_id, row.citation, row.model_dump_json(exclude={'explainer'}),
            metadata={'provision_id': row.provision_id, 'deterministic': True})
    for item in process_fields(clean_case, codes):
        add('guidance', 'process.' + item.id, item.label,
            '\n'.join((item.prompt, *item.reviewer_looks_for, item.citation)))
        for match in ARTICLE.finditer(item.citation):
            pid = match.group()
            rec = codes.provision(pid, 'C')
            if rec:
                add('code', 'C:' + pid, rec['citation'], rec['text'], page=rec.get('pdf_page'),
                    metadata={'division': 'C', 'provision_id': pid})
        if item.example:
            add('guidance', 'example-structure.' + item.id, item.example.label,
                '\n'.join(item.example.must_address))
            for ref in item.example.precedents:
                add('precedent_structure', ref.number or ref.title,
                    f'{ref.title} — {ref.edition}; structure only, no project facts', ref.structure,
                    page=ref.pdf_page, url=ref.url, metadata={'edition': ref.edition, 'structure_only': True})
    # Use the real case for the screen: accepting new wording can invalidate an older officer
    # determination. Excluding the prose as evidence must not resurrect that determination.
    screen = professional_involvement(case, codes)
    add('professional_screen', 'professional_involvement', 'Deterministic professional-involvement screen',
        screen.model_dump_json())
    files = []
    for meta in sorted(store.list_files(case.id) or [], key=lambda f: f['id']):
        saved = store.get_file(case.id, meta['id'])
        data = saved.get('data') if saved else None
        files.append({'id': meta['id'], 'name': meta['name'],
                      'data': data if include_bytes and len(files) < MAX_FILES else None,
                      'sha256': hashlib.sha256(data).hexdigest() if data is not None else None})
    fields = [*(f for f in TITLES if f != 'evidence_plan'),
              *(f'section_c.{row.provision_id}.explanation' for row in rows), 'evidence_plan']
    fingerprint = digest({'version': VERSION, 'facts': [f.model_dump() for f in facts],
        'provisions': case.provisions, 'jurisdiction': case.jurisdiction.model_dump() if case.jurisdiction else None,
        'resolutions': [r.model_dump() for r in case.professional_resolutions],
        'resources': [s.model_dump() for s in resources],
        'review': case.intake.review.model_dump() if case.intake and case.intake.review else None,
        'files': [{k: v for k, v in f.items() if k != 'data'} for f in files]})
    rough = rough_alternative(case)
    replacements = {'alternative_description': rough.id} if rough else {}
    return Inputs(fingerprint, resources, files,
                  list(dict.fromkeys(f for f in fields if not has_answer(case, f) or f in replacements)),
                  screen.required == 'yes', replacements)


@dataclass
class SourceBundle:
    inputs: Inputs
    sources: list[DraftSource] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    registry_searches: list[RegistrySearch] = field(default_factory=list)
    registry_queries: list[DraftRegistryQuery] = field(default_factory=list)


def collect_sources(case: Case, inputs: Inputs, *, names=(), registry: CCMCRegistry) -> SourceBundle:
    bundle = SourceBundle(inputs)
    known = known_values(case, [*names, *(resolution.by_name for resolution in case.professional_resolutions)])
    used = 0

    def add(kind, ref, label, text, *, verbatim=False, **kw):
        nonlocal used
        original = str(text)
        text = original if verbatim else scrub(original, known)
        budget = max(0, min(MAX_SOURCE_CHARS, MAX_CONTEXT_CHARS - used))
        if len(text) > budget:
            bundle.notices.append(f'{label}: source context truncated ({len(text)} characters; {budget} supplied).')
        text = text[:budget]
        if not text.strip():
            return
        used += len(text)
        values = {'kind': kind, 'ref': ref, 'label': label, 'text': text, **kw}
        if not verbatim:
            values = scrub_obj(values, known)
        source = DraftSource(id='', **values)
        source.id = 'src_' + digest(source.model_dump(exclude={'id'}))[:24]
        if source.id not in {s.id for s in bundle.sources}:
            bundle.sources.append(source)

    # Code sources are not run through personal-pattern redaction (article numbers are legal text).
    for resource in inputs.resources:
        add(**resource.model_dump(exclude={'id'}), verbatim=resource.kind in {'code', 'section_c'})
    actual_pages = {}
    for fact in input_facts(case):
        if (fact.field == 'project.description' and fact.kind != 'proposed' and isinstance(fact.value, str)
                and not generated_fact(fact, case)):
            actual_pages[('description', None)] = fact.value
            add('description', fact.id, 'Saved project description', fact.value,
                metadata={'fact_id': fact.id, 'field': fact.field})
    for index, saved in enumerate(inputs.files):
        label = f'Document {index + 1}'
        if index >= MAX_FILES:
            bundle.notices.append(f'{label}: not read; only the first {MAX_FILES} owned files are in context.')
            continue
        if saved['data'] is None:
            bundle.notices.append(f'{label}: owned file bytes unavailable; not read.')
            continue
        try:
            count, pages = page_texts(saved['data'], MAX_PAGES)
        except (NotAPdf, PdfiumError, ValueError, RuntimeError):
            bundle.notices.append(f'{label}: PDF unreadable or password-protected; not read.')
            continue
        if count > MAX_PAGES:
            bundle.notices.append(f'{label}: only the first {MAX_PAGES} of {count} pages were read.')
        unread = sorted(set(range(1, min(count, MAX_PAGES) + 1)) - {p for p, _ in pages})
        if unread:
            bundle.notices.append(f'{label}: pages {", ".join(map(str, unread))} have no readable text; no OCR was run.')
        for page, text in pages:
            original = case.drafting and any(s.kind == 'document' and s.ref == saved['id'] and s.page == page
                and s.metadata.get('sha256') == saved['sha256'] for s in case.drafting.sources)
            if (case.drafting and not original and any(d.text and d.text in text for d in case.drafting.drafts)):
                bundle.notices.append(f'{label}, page {page}: prior generated applicant prose excluded as a source.')
                continue
            actual_pages[(saved['id'], page)] = text
            add('document', saved['id'], f'{label}, page {page}', text, page=page,
                metadata={'sha256': saved['sha256'], 'name': scrub(saved['name'], known),
                          'authority': 'uploaded document, not legal authority'})
    for fact in input_facts(case):
        if generated_fact(fact, case):
            bundle.notices.append(f'Fact {fact.id}: prior generated applicant prose excluded as a source.')
            continue
        if (fact.field == 'project.description' or fact.status != 'confirmed' or fact.kind == 'proposed'
                or fact.field in PERSONAL_FIELDS or fact.field.endswith(PERSONAL_SUFFIXES)
                or fact.field.endswith('.file_ref') or fact.value is None):
            continue
        if fact.source.type in {'file', 'drawing'}:
            original = actual_pages.get((fact.source.ref, fact.source.page), '')
            if not fact.source.quote or fact.source.quote not in original:
                bundle.notices.append(f'Fact {fact.id}: original owned page/quote unavailable; excluded.')
                continue
            text = fact.source.quote
        elif fact.source.type in {'user_text', 'user_click', 'officer', 'professional'}:
            text = str(fact.value)
        else:
            continue  # A fact labelled "code" cannot replace a canonical code lookup.
        add('fact', fact.id, f'Confirmed fact: {fact.field}', text,
            page=fact.source.page, metadata={'field': fact.field, 'source_ref': scrub(fact.source.ref, known),
                                           'authority': 'saved fact, not legal authority'})
    if case.intake and case.intake.review:
        for index, fact in enumerate(case.intake.review.facts):
            for ref in fact.evidence:
                if ref.quote and ref.quote in actual_pages.get((ref.source_ref, ref.page), ''):
                    add('fact', f'review:{index}', f'Document passage ({fact.status})', ref.quote, page=ref.page,
                        metadata={'source_ref': ref.source_ref, 'review_status': fact.status})
                else:
                    bundle.notices.append(f'Review fact {index + 1}: original source changed/unavailable; excluded.')
    bundle.registry_queries = [q for q in product_queries(bundle.sources)
                               if scrub(q.query, known) == q.query]
    if not bundle.registry_queries:
        bundle.notices.append('No bounded product/manufacturer query was found; supply a product or manufacturer name for CCMC discovery.')
    for candidate in bundle.registry_queries:
        query = candidate.query
        try:
            search = registry.search(query, limit=5)
        except (RegistryUnavailable, ValueError, OSError):
            bundle.notices.append(f'CCMC discovery for {query}: registry unavailable; no negative conclusion can be made.')
            continue
        bundle.registry_searches.append(search)
        add('registry', query, 'CCMC discovery leads; applicability/status/edition unverified',
            json.dumps(scrub_obj(search.model_dump(), known), ensure_ascii=False), url=search.source_url,
            metadata={'source': search.source, 'searched_date': search.searched_date,
                      'registry_date': search.registry_date, 'discovery_only': True,
                      'query_source_id': candidate.source_id, 'query_start': candidate.start, 'query_end': candidate.end})
        if search.notice:
            bundle.notices.append(search.notice)
    bundle.notices.append('Applicant writing remains a draft until accepted. Acceptance is ownership of wording, not professional evidence or a technical finding.')
    return bundle


def refresh_staleness(case: Case, store, codes) -> Case:
    if case.drafting:
        try:
            current = read_inputs(case, store, codes).fingerprint
            case.drafting.stale = current != case.drafting.input_fingerprint
            case.drafting.stale_reasons = ['Saved facts, confirmed provisions, resources or owned document bytes changed.'] if case.drafting.stale else []
        except (KeyError, ValueError, OSError):
            case.drafting.stale = True
            case.drafting.stale_reasons = ['Current drafting inputs could not be verified.']
    return case
