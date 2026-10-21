"""Atomic applicant text listings. Scope is an explicit ledger link, never a review."""
from __future__ import annotations

from typing import Callable, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .codes import Codes
from .models import Case, EvidenceItem, Fact, Source
from .section_d import EvidencePlanItem, section_d_plan, supporting_documents
from .store import CaseBackend, VersionConflict


class EvidenceScope(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    item_id: str | None = Field(default=None, min_length=1)
    provision_id: str | None = Field(default=None, min_length=1)
    objective: str | None = Field(default=None, min_length=1)
    function: str | None = Field(default=None, min_length=1)

    @model_validator(mode='after')
    def _explicit_target(self):
        if not self.item_id and not self.provision_id:
            raise ValueError('scope requires item_id or provision_id')
        return self


class EvidenceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    operation: Literal['create', 'update']
    evidence_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9][A-Za-z0-9_~-]*$')
    expected_version: int = Field(ge=1, strict=True)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    responsible_party: str | None = None
    date: str | None = None
    issuer: str | None = None
    # Omitted = retain; explicit null = withdraw; object = explicit current re-link.
    scope: EvidenceScope | None = None

    @field_validator('title', 'description', 'evidence_type')
    @classmethod
    def _nonblank(cls, value):
        if not value.strip():
            raise ValueError('listing text must not be blank')
        return value


class EvidenceDelete(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1, strict=True)


class EvidenceSaved(BaseModel):
    evidence: EvidenceItem
    case: Case
    case_version: int


def _snapshot(store: CaseBackend, case_id: str, expected_version: int) -> Case:
    snapshot = store.get_snapshot(case_id)
    if snapshot is None:
        raise HTTPException(404, 'case not found')
    case, version = snapshot
    if version != expected_version:
        raise HTTPException(409, 'case was updated concurrently')
    return case


def _commit(store: CaseBackend, case: Case, expected_version: int) -> Case:
    try:
        return store.put(case, expected_version=expected_version)
    except VersionConflict as error:
        if error.actual is None:
            raise HTTPException(404, 'case not found') from error
        raise HTTPException(409, 'case was updated concurrently') from error


def _slots(case: Case) -> set[str]:
    slots = {item.id for item in case.evidence}
    for fact in case.facts:
        if not fact.field.startswith('evidence.'):
            continue
        name = fact.field[len('evidence.'):]
        if '.covers.' in name:
            slots.add(name.split('.covers.', 1)[0])
        elif '.' in name:
            slots.add(name.rsplit('.', 1)[0])
    return slots


def _check_slot(case: Case, evidence_id: str) -> bool:
    # Legacy dotted IDs remain deletable when their exact prefix owns no other slot.
    if (not evidence_id.strip() or any(ord(char) < 32 or char in '/\\' for char in evidence_id)
            or '.covers.' in (evidence_id + '.')):
        raise HTTPException(422, 'ambiguous evidence id')
    slots = _slots(case)
    if (any(slot.startswith(evidence_id + '.') for slot in slots if slot != evidence_id)
            or sum(item.id == evidence_id for item in case.evidence) > 1):
        raise HTTPException(422, 'ambiguous evidence slot prefix')
    return evidence_id in slots


def _text_fact(evidence_id: str, name: str, value) -> Fact:
    return Fact(field=f'evidence.{evidence_id}.{name}', value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref=f'applicant-evidence:{evidence_id}',
                              quote=str(value) if value is not None else None))


def _scope(case: Case, scope: EvidenceScope, code: Callable[[], Codes]) -> EvidencePlanItem:
    try:
        # No cached Section C row, cross-provision pair match, or inferred attribution.
        items = section_d_plan(case, code()).items if case.provisions else []
    except KeyError as error:
        raise HTTPException(404, error.args[0]) from error
    except ValueError as error:
        raise HTTPException(400, f'invalid provision id: {error}') from error
    matches = [item for item in items if all(
        getattr(item, field) == getattr(scope, field)
        for field in scope.model_fields_set
        if field != 'item_id') and (scope.item_id is None or item.id == scope.item_id)]
    if len(matches) != 1:
        raise HTTPException(422, 'scope must resolve to one current evidence plan item')
    return matches[0]


def delete_listing(store: CaseBackend, case_id: str, evidence_id: str, expected_version: int) -> Case:
    """The existing DELETE route uses this same snapshot/CAS contract; bytes stay owned."""
    case = _snapshot(store, case_id, expected_version)
    if not _check_slot(case, evidence_id):
        raise HTTPException(404, 'evidence not found')
    prefix = f'evidence.{evidence_id}.'
    case.facts = [fact for fact in case.facts if not fact.field.startswith(prefix)]
    case.evidence = [item for item in case.evidence if item.id != evidence_id]
    return _commit(store, case, expected_version)


def create_router(cases: Callable[[], CaseBackend], code: Callable[[], Codes]) -> APIRouter:
    router = APIRouter(tags=['applicant evidence'])

    @router.post('/cases/{case_id}/evidence', response_model=EvidenceSaved)
    def save_evidence(case_id: str, body: EvidenceWrite):
        store = cases()
        case = _snapshot(store, case_id, body.expected_version)
        exists = _check_slot(case, body.evidence_id)
        # Text input may never replace an attachment, including a fact-only legacy slot.
        if any(doc.id == body.evidence_id for doc in supporting_documents(case)):
            raise HTTPException(422, 'use the attachment workflow for an attached document')
        if body.operation == 'create' and exists:
            raise HTTPException(409, 'evidence id already exists')
        if body.operation == 'update' and not exists:
            raise HTTPException(404, 'evidence not found')
        prefix = f'evidence.{body.evidence_id}.'
        item = next((entry for entry in case.evidence if entry.id == body.evidence_id), None)
        if item is None:
            item = EvidenceItem(id=body.evidence_id, description=body.description)
            case.evidence.append(item)
        item.description, item.evidence_type = body.description, body.evidence_type
        item.status, item.kind = 'evidence_listed', 'text'
        # Revisions remain inspectable; omitted optional metadata remains unchanged.
        for name in ('title', 'description', 'evidence_type', 'responsible_party', 'date', 'issuer'):
            if name in body.model_fields_set:
                case.facts.append(_text_fact(body.evidence_id, name, getattr(body, name)))
        if 'scope' in body.model_fields_set:
            target = _scope(case, body.scope, code) if body.scope is not None else None
            # Remove old links, so an explicit new scope has exactly one target.
            case.facts = [fact for fact in case.facts if fact.field not in {
                prefix + field for field in ('item_id', 'provision_id', 'objective', 'function')
            } and not fact.field.startswith(prefix + 'covers.')]
            item.objective = target.objective if target else None
            item.function = target.function if target else None
            if target:
                for name, value in (('item_id', target.id), ('provision_id', target.provision_id),
                                    ('objective', target.objective), ('function', target.function)):
                    case.facts.append(_text_fact(body.evidence_id, name, value))
        elif body.operation == 'create':
            item.objective = item.function = None
        # New stable IDs and metadata-only edits cannot acquire implicit plan coverage.
        # Explicit item_id links are still honored by the existing attachment reader.
        case.facts.append(Fact(field=prefix + 'auto_link', value=False, kind='computed', status='confirmed',
            source=Source(type='user_click', ref=f'applicant-evidence:{body.evidence_id}'),
            formula='Document scope requires an explicit current item link; identity alone supplies no scope'))
        saved = _commit(store, case, body.expected_version)
        actual = next(entry for entry in saved.evidence if entry.id == body.evidence_id)
        return EvidenceSaved(evidence=actual, case=saved, case_version=saved.version)

    return router
