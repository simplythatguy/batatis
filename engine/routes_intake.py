"""Intake routes: read the description and dropped PDFs into unconfirmed, pointed facts.

`POST /cases/{id}/intake` runs the rules, then the model pass when this deployment allows it
(BATATIS_LIVE=1 and the spend gate, or BATATIS_PROVIDER=fake), and writes the facts to the ledger.
`GET /cases/{id}/intake` returns the stored run and never calls a provider. Contract: docs/api/intake.md.
"""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .codes import CodeDbMissing, Codes
from .intake import model as model_pass
from .intake import service
from .intake.extract import scrubbed
from .intake.rules import ROLES
from .llm_gate import client_ip_from
from .models import Fact
from .models_intake import IntakeRecord
from .redact import known_values, people_names
from .store import CaseBackend, VersionConflict

MAX_TEXT = 20000
MAX_FILES = 10


class IntakeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str | None = Field(default=None, max_length=MAX_TEXT)
    file_ids: list[str] = Field(default_factory=list, max_length=MAX_FILES)
    role: str | None = None
    model: bool = True                           # false: rules and forms only, no provider call
    expected_version: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode='after')
    def _something_to_read(self):
        if not (self.text and self.text.strip()) and not self.file_ids:
            raise ValueError('send text, file_ids or both')
        if self.role is not None and self.role not in ROLES:
            raise ValueError(f'role must be one of {", ".join(ROLES)}')
        if len(set(self.file_ids)) != len(self.file_ids):
            raise ValueError('file_ids must not repeat')
        return self


class AnswerItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question_id: str = Field(max_length=200)
    field: str | None = Field(default=None, max_length=200)
    answer: str = Field(default='', max_length=2000)


class AnswersRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answers: list[AnswerItem] = Field(min_length=1, max_length=5)
    expected_version: int | None = Field(default=None, ge=1, strict=True)


class ScopeRequest(BaseModel):
    """`building_code: true` is the applicant's "this is a building-code question" override."""
    model_config = ConfigDict(extra='forbid')
    building_code: bool
    expected_version: int | None = Field(default=None, ge=1, strict=True)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int | None = Field(default=None, ge=1, strict=True)


class IntakeResult(BaseModel):
    case_id: str
    case_version: int
    facts: list[Fact]                            # this run's facts, in the ledger, all unconfirmed
    record: IntakeRecord


def create_router(cases: Callable[[], CaseBackend], code: Callable[[], Codes], *,
                  transport_factory: Callable[[str], tuple[model_pass.Transport | None, str]] | None = None) -> APIRouter:
    router = APIRouter(tags=['intake'])
    pick_transport = transport_factory or model_pass.default_transport

    def codes_or_none():
        try:
            return code()
        except (CodeDbMissing, HTTPException):
            return None

    def result(case) -> IntakeResult:
        if case.intake is None:
            service.refresh(case)
        ids = {pointer.fact_id for pointer in case.intake.pointers}
        return IntakeResult(case_id=case.id, case_version=case.version, record=case.intake,
                            facts=[fact for fact in case.facts if fact.id in ids])

    @router.post('/cases/{case_id}/intake', response_model=IntakeResult)
    def run_intake(case_id: str, body: IntakeRequest, request: Request):
        store = cases()
        case = store.get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        files = []
        for file_id in body.file_ids:
            stored = store.get_file(case_id, file_id)
            if stored is None:
                raise HTTPException(404, 'file not found')
            files.append((file_id, stored['name'], stored['data']))
        transport, status = pick_transport(client_ip_from(request)) if body.model else (None, 'off')
        known = known_values(case, people_names(store, case, getattr(request.state, 'user', None)))
        extraction = service.run(body.text, files, codes=codes_or_none(), transport=transport, status=status,
                                 outbound=lambda text, personal: scrubbed(text, [*known, *personal]))
        # One compare-and-swap against the version the client saw, else the one read above. No retry.
        if body.expected_version is not None and body.expected_version != case.version:
            raise HTTPException(409, 'case was updated concurrently')
        service.apply(case, body.text, extraction, role=body.role)
        try:
            saved = store.put(case, expected_version=case.version)
        except VersionConflict as error:
            if error.actual is None:
                raise HTTPException(404, 'case not found') from error
            raise HTTPException(409, 'case was updated concurrently') from error
        return result(saved)

    def write(case_id: str, expected_version: int | None, change: Callable):
        """Read, change, one compare-and-swap. No retry."""
        store = cases()
        case = store.get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        if expected_version is not None and expected_version != case.version:
            raise HTTPException(409, 'case was updated concurrently')
        change(case)
        try:
            saved = store.put(case, expected_version=case.version)
        except VersionConflict as error:
            if error.actual is None:
                raise HTTPException(404, 'case not found') from error
            raise HTTPException(409, 'case was updated concurrently') from error
        return result(saved)

    @router.post('/cases/{case_id}/intake/plan', response_model=IntakeResult)
    def replan(case_id: str, body: PlanRequest | None = None):
        """Recompute the plan, for example after code identification ran. No provider call."""
        return write(case_id, body.expected_version if body else None, service.refresh)

    @router.post('/cases/{case_id}/intake/answers', response_model=IntakeResult)
    def answer(case_id: str, body: AnswersRequest):
        def change(case):
            try:
                service.answer(case, [item.model_dump() for item in body.answers])
            except service.AnswerRejected as error:
                raise HTTPException(422, str(error)) from error
        return write(case_id, body.expected_version, change)

    @router.post('/cases/{case_id}/intake/scope', response_model=IntakeResult)
    def scope(case_id: str, body: ScopeRequest):
        return write(case_id, body.expected_version, lambda case: service.override_scope(case, body.building_code))

    @router.get('/cases/{case_id}/intake', response_model=IntakeResult)
    def get_intake(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        if case.intake is None:
            raise HTTPException(404, 'intake not run')
        return result(case)

    return router
