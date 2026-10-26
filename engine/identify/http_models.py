"""Request bodies for the identify routes. Ported from PR #12; responses are in engine/models_identify.py."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.models import SectionCRow
from engine.models_identify import IdentifyResult

# The case version the client last read (Case.version or IdentifyResult.case_version). Optional, as on
# POST /cases/{id}/section-d; when supplied and not the stored version, the write is a 409.
def ExpectedVersion():                          # noqa: N802 - reads like a field type
    return Field(default=None, ge=1, strict=True)


class AnswerIn(BaseModel):
    """One answer. `question_id` is the question's stable id; `field` is the fact field it fills."""
    model_config = ConfigDict(extra='forbid')
    field: str | None = Field(default=None, max_length=200)
    question_id: str | None = Field(default=None, max_length=200)
    answer: str = Field(default='', max_length=2000)


class IdentifyRequest(BaseModel):
    """`prose` defaults to the case's latest project.description fact when omitted."""
    model_config = ConfigDict(extra='forbid')
    prose: str | None = Field(default=None, max_length=2_000_000)
    answers: list[AnswerIn] = Field(default_factory=list, max_length=20)
    expected_version: int | None = ExpectedVersion()


class IdentifyDecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['yes', 'no', 'not_sure']
    expected_version: int | None = ExpectedVersion()


class IdentifyConfirmRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provisions: list[str] = Field(min_length=1, max_length=50)
    expected_version: int | None = ExpectedVersion()


class BenchmarkConfirmRequest(BaseModel):
    """The applicant names the requirement their design departs from and confirms the one-line departure."""
    model_config = ConfigDict(extra='forbid')
    provision: str = Field(min_length=1, max_length=40)
    departure: str = Field(min_length=1, max_length=300)
    expected_version: int | None = ExpectedVersion()


class IdentifyDecisionResponse(IdentifyResult):
    """The identify result after a decision, plus the Section C rows a `yes` wrote for that article."""
    section_c: list[SectionCRow] = []


class RequirementDecisionRequest(BaseModel):
    """Applicability is independent from the legacy departure question."""
    model_config = ConfigDict(extra='forbid')
    disposition: Literal['include', 'exclude', 'review']
    role: Literal['varied', 'supporting', 'admin', 'conditional', 'unresolved']
    reason: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=1, strict=True)
