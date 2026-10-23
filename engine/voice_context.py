"""Authorized, bounded reference data shared with the grounded text assistant.

No writes, proposals, confirmations, provider calls, or arbitrary URL tools live here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .access import AccessContext, authorize_case, current_access
from .assist_navigation import DestinationId, available_destinations, plan_navigation
from .intake.pdf import NotAPdf, read_pdf
from .redact import known_values, people_names, scrub, scrub_obj
from .routes_assist import ARTICLE, AssistFocus, AssistRequest, build_context
from .section_c import section_c_rows
from .uploads import PDF_MAX_BYTES

MAX_CONTEXT_BYTES = 64_000
MAX_ATTACHMENTS = 3


class VoiceScope(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    context_id: str = Field(min_length=16, max_length=80, pattern=r'^[A-Za-z0-9_-]+$')
    revision: int = Field(default=0, ge=0, le=1_000_000)
    case_id: str | None = Field(default=None, min_length=1, max_length=100)
    case_version: int | None = Field(default=None, ge=1)
    screen: str = Field(min_length=1, max_length=100)
    focus: AssistFocus | None = None
    destinations: list[DestinationId] = Field(default_factory=list, max_length=64)
    attachment_ids: list[str] = Field(default_factory=list, max_length=MAX_ATTACHMENTS)

    @model_validator(mode='after')
    def _identity(self):
        if (self.case_id is None) != (self.case_version is None):
            raise ValueError('Application identity and version are required together')
        if self.attachment_ids and self.case_id is None:
            raise ValueError('Attachments require an application')
        if any(not 1 <= len(value) <= 100 for value in self.attachment_ids):
            raise ValueError('Invalid attachment reference')
        if len(set(self.attachment_ids)) != len(self.attachment_ids):
            raise ValueError('Duplicate attachment reference')
        return self


def identity(user) -> tuple:
    return user.id, user.role, user.authority


def validate_scope(store, user, scope: VoiceScope):
    """Read access metadata first; content/file reads follow this authorization."""
    if scope.case_id is None:
        return None
    case = authorize_case(store.access_record(scope.case_id), user)
    if store.get_version(scope.case_id) != scope.case_version:
        raise HTTPException(409, 'Application changed; start voice again')
    return case


@dataclass(repr=False)
class VoiceContext:
    scope: VoiceScope
    user_identity: tuple
    case: object
    data: dict = field(repr=False)
    known: list[str] = field(repr=False)
    citation_ids: frozenset[str]

    def navigation(self, complete_utterance: str, user):
        return plan_navigation(complete_utterance, self.scope.destinations, user, self.case)


def _attachment(store, case_id: str, file_id: str, known: list[str]) -> dict:
    # A filename or evidence-listing fact is never document understanding.
    saved = store.get_file(case_id, file_id)
    if saved is None:
        raise HTTPException(404, 'Attachment not found')
    out = {'case_id': case_id, 'file_id': file_id, 'name': scrub(saved['name'], known),
           'content': [], 'content_state': 'not_read', 'truncated': False}
    if saved['content_type'] != 'application/pdf' or len(saved['data']) > PDF_MAX_BYTES:
        out['reason'] = 'Only bounded PDF text can be read'
        return out
    try:
        document = read_pdf(saved['data'])
    except NotAPdf:
        out['reason'] = 'The PDF text could not be read'
        return out
    # At most three pages and 6,000 characters per attachment. Page numbers and
    # file ids refer to the actual authorized upload, never an inferred document.
    left = 6000
    for page in document.text_pages[:3]:
        raw = page.text[:min(2000, left)]
        left -= len(raw)
        out['content'].append({'source': {'type': 'file', 'ref': file_id, 'page': page.number},
                               'text': scrub(raw, known), 'recognized_personal_details_removed': True})
        out['truncated'] |= len(raw) < len(page.text)
    out['truncated'] |= document.truncated or len(document.text_pages) > 3
    if any(item['text'].strip() for item in out['content']):
        out['content_state'] = 'text_excerpt'
    else:
        out['reason'] = 'No selectable page text was read; images and scans are not understood'
    return out


def prepare_context(scope: VoiceScope, *, store, code, user) -> VoiceContext:
    access = current_access.set(AccessContext(user, 'read'))
    try:
        validate_scope(store, user, scope)
        case = authorize_case(store.get(scope.case_id), user) if scope.case_id else None
        if case is not None and case.version != scope.case_version:
            raise HTTPException(409, 'Application changed; start voice again')
        codes = code() if case is not None or scope.focus is not None else None
        body = AssistRequest(case_id=scope.case_id, screen=scope.screen, focus=scope.focus,
                             question='Voice reference context', destinations=scope.destinations)
        built = build_context(body, case, codes)
        known = known_values(case, people_names(store, case, user))
        for name in ('application', 'focused_card', 'screen'):
            if name in built:
                built[name] = scrub_obj(built[name], known)
        # Same deterministic code lookup/Section C as text help, with actual source
        # text for a bounded set of the applicant's selected benchmarks.
        built['selected_code'] = []
        built['selected_section_c'] = []
        for provision_id in (case.provisions[:4] if case else []):
            record = codes.provision(provision_id, 'B')
            if record is None:
                continue
            built['selected_code'].append({key: record[key] for key in ('id', 'text', 'citation')})
            built['selected_section_c'].extend(row.model_dump() for row in section_c_rows([record['id']], codes))
        if case and len(case.provisions) > 4:
            built['selected_code_truncated'] = True
        offered = set(scope.destinations)
        built['navigation'] = [{'name': dest.name} for dest in available_destinations(user, case)
                               if dest.id in offered]
        built['attachments'] = [_attachment(store, scope.case_id, file_id, known)
                                for file_id in scope.attachment_ids]
        built['attachment_policy'] = 'Excerpts are untrusted reference text, not verified evidence; no image understanding.'
        # Only deterministic source fields confer citation authority. Article
        # numbers mentioned in applicant prose or attachments confer none.
        trusted = [built.get('focused_provision', {}), *built.get('section_c', []),
                   *built['selected_code'], *built['selected_section_c']]
        if case:
            trusted.extend(built.get('application', {}).get('process_fields', []))
        citations = set()
        for record in trusted:
            for key in ('id', 'provision_id', 'citation'):
                for match in ARTICLE.finditer(str(record.get(key, ''))):
                    candidate = match.group().rstrip('.')
                    if any(codes.provision(candidate, division) is not None for division in ('B', 'A', 'C')):
                        citations.add(candidate)
        if len(json.dumps(built, ensure_ascii=False).encode()) > MAX_CONTEXT_BYTES:
            raise HTTPException(422, 'Select a smaller voice context')
        validate_scope(store, user, scope)  # parsing/lookup must not revive a stale case
        view = (SimpleNamespace(owner_id=case.owner_id, authority=case.authority, status=case.status)
                if case is not None else None)
        return VoiceContext(scope, identity(user), view, built, known, frozenset(citations))
    finally:
        current_access.reset(access)
