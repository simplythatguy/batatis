"""Applicant-only saved generation/decisions. Reads never run a model or a registry search."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from .access import READ_ONLY_DETAIL, enforce_mutation
from .ccmc import CCMCRegistry
from .drafting_generation import generate
from .drafting_provider import DraftingUnavailable, configured_provider
from .drafting_sources import collect_sources, has_answer, read_inputs, refresh_staleness, rough_alternative
from .llm_gate import client_ip_from
from .models import Case, Fact, Source, now
from .models_drafting import DraftModel, DraftingRecord, draft_passages
from .redact import people_names
from .store import VersionConflict


class GenerateDrafts(DraftModel):
    expected_version: int = Field(ge=1, strict=True)


class DecideDraft(GenerateDrafts):
    decision: Literal['accept', 'reject']


def create_router(cases, code, *, provider_factory=None, registry=None):
    router = APIRouter(tags=['applicant drafts'])
    registry = registry if registry is not None else CCMCRegistry()

    def snapshot(case_id, *, editing=False):
        saved = cases().get_snapshot(case_id)
        if saved is None:
            raise HTTPException(404, 'case not found')
        case, version = saved
        if editing:
            enforce_mutation(case)
            if case.status not in {'draft', 'returned'}:
                raise HTTPException(409, READ_ONLY_DETAIL)
        return case, version

    def inputs(case, *, include_bytes=False):
        try:
            return read_inputs(case, cases(), code(), include_bytes=include_bytes)
        except (KeyError, ValueError, OSError) as error:
            raise HTTPException(503, 'Drafting inputs could not be verified.') from error

    def persist(case, version, current_inputs):
        try:
            return cases().put(case, expected_version=version,
                               expected_files={f['id']: (f['name'], f['sha256']) for f in current_inputs.files})
        except VersionConflict as error:
            raise HTTPException(404 if error.actual is None else 409,
                                'case not found' if error.actual is None else 'case was updated concurrently') from error

    @router.get('/cases/{case_id}/drafts', response_model=DraftingRecord)
    def get_drafts(case_id: str):
        case, _ = snapshot(case_id)
        if case.drafting is None:
            raise HTTPException(404, 'No saved applicant drafts.')
        return refresh_staleness(case, cases(), code()).drafting

    @router.post('/cases/{case_id}/drafts', response_model=Case)
    def generate_drafts(case_id: str, body: GenerateDrafts, request: Request):
        case, version = snapshot(case_id, editing=True)
        if body.expected_version != version:
            raise HTTPException(409, 'case was updated concurrently')
        original = inputs(case, include_bytes=True)
        if not original.fields:
            return refresh_staleness(case, cases(), code())
        if (case.drafting and case.drafting.input_fingerprint == original.fingerprint
                and {d.field for d in case.drafting.drafts if d.status == 'draft'} == set(original.fields)):
            return refresh_staleness(case, cases(), code())
        try:
            provider = (provider_factory or configured_provider)(client_ip_from(request))
            bundle = collect_sources(case, original,
                names=people_names(cases(), case, request.state.user), registry=registry)
            record = generate(bundle, provider)
        except DraftingUnavailable as error:
            raise HTTPException(503, str(error)) from error
        # A provider/registry request is slow. Check access, version and actual current bytes again.
        current, current_version = snapshot(case_id, editing=True)
        if current_version != version or inputs(current).fingerprint != original.fingerprint:
            raise HTTPException(409, 'Drafting inputs changed during generation; generate again from the current case.')
        if current.drafting:
            record.generated_texts = list(dict.fromkeys([*current.drafting.generated_texts,
                *(text for draft in current.drafting.drafts for text in draft_passages(draft) if text.strip()),
                *record.generated_texts]))
            origins = [*current.drafting.source_history,
                       *(s for s in current.drafting.sources if s.kind in {'fact', 'description', 'document'}),
                       *record.source_history]
            record.source_history = list({s.id: s for s in origins}.values())
            history = [d for d in current.drafting.drafts if d.status != 'draft']
            source_ids = {c.source_id for d in history for part in [*d.claims, *d.questions] for c in part.sources}
            # A cited registry result also retains the original span that supplied its search query.
            source_ids.update(s.metadata['query_source_id'] for s in current.drafting.sources
                              if s.id in source_ids and s.kind == 'registry' and s.metadata.get('query_source_id'))
            sources = {s.id: s for s in current.drafting.sources if s.id in source_ids}
            sources.update((s.id, s) for s in record.sources)
            record.sources = list(sources.values())
            record.drafts = [*history, *record.drafts]
            generation_ids = {d.generation_id for d in history}
            record.generations = [*[g for g in current.drafting.generations if g.id in generation_ids],
                                  *record.generations]
            queries = [q for q in current.drafting.registry_queries if q.source_id in source_ids]
            record.registry_queries = list({q.model_dump_json(): q for q in [*queries, *record.registry_queries]}.values())
            search_terms = {s.ref for s in current.drafting.sources if s.id in source_ids and s.kind == 'registry'}
            searches = [s for s in current.drafting.registry_searches if s.query in search_terms]
            record.registry_searches = list({s.model_dump_json(): s for s in [*searches, *record.registry_searches]}.values())
        current.drafting = record
        return persist(current, version, original)

    @router.post('/cases/{case_id}/drafts/{draft_id}/decision', response_model=Case)
    def decide_draft(case_id: str, draft_id: str, body: DecideDraft, request: Request):
        case, version = snapshot(case_id, editing=True)
        draft = next((d for d in case.drafting.drafts if d.id == draft_id), None) if case.drafting else None
        if draft is None:
            raise HTTPException(404, 'draft not found')
        target = 'accepted' if body.decision == 'accept' else 'rejected'
        if draft.status != 'draft':
            if draft.status != target:
                raise HTTPException(409, 'This draft already has a different decision; generate a new draft.')
            if body.expected_version not in {version, draft.decision_expected_version}:
                raise HTTPException(409, 'case was updated concurrently')
            return refresh_staleness(case, cases(), code())
        if body.expected_version != version:
            raise HTTPException(409, 'case was updated concurrently')
        current_inputs = inputs(case)
        if current_inputs.fingerprint != draft.input_fingerprint:
            raise HTTPException(409, 'This draft is stale; generate again from the current case.')
        if target == 'accepted':
            if not draft.text.strip():
                raise HTTPException(422, 'This draft contains only gap questions; answer them before accepting writing.')
            rough = rough_alternative(case, cases()) if draft.field == 'alternative_description' else None
            replacing_rough = rough is not None and rough.id == draft.replaces_fact_id
            if has_answer(case, draft.field) and not replacing_rough:
                raise HTTPException(409, 'This field already has an answer; a draft cannot overwrite it.')
            fact = Fact(field=draft.field, value=draft.text, kind='pointed', status='confirmed',
                        source=Source(type='user_click', ref='applicant-draft:' + draft.id, quote=draft.text))
            case.facts.append(fact)
            draft.accepted_fact_id = fact.id
        draft.status = target
        draft.decided_at = now()
        draft.decided_by = request.state.user.id if request.state.user else None
        draft.decision_expected_version = version
        # No Section C attribution, evidence row, file-presence flag or professional result is written.
        return refresh_staleness(persist(case, version, current_inputs), cases(), code())

    return router
