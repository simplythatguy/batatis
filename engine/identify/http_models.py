"""Request bodies for the identify routes. Ported from PR #12; responses are in engine/models_identify.py."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnswerIn(BaseModel):
    """One answer. `question_id` is the question's stable id; `field` is the fact field it fills."""
    model_config = ConfigDict(extra='forbid')
    field: str | None = Field(default=None, max_length=200)
    question_id: str | None = Field(default=None, max_length=200)
    answer: str = Field(default='', max_length=2000)


class IdentifyRequest(BaseModel):
    """`prose` defaults to the case's latest project.description fact when omitted."""
    model_config = ConfigDict(extra='forbid')
    prose: str | None = Field(default=None, max_length=20000)
    answers: list[AnswerIn] = Field(default_factory=list, max_length=20)


class IdentifyDecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['yes', 'no', 'not_sure']


class IdentifyConfirmRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provisions: list[str] = Field(min_length=1, max_length=50)


class BenchmarkConfirmRequest(BaseModel):
    """The applicant names the requirement their design departs from and confirms the one-line departure."""
    model_config = ConfigDict(extra='forbid')
    provision: str = Field(min_length=1, max_length=40)
    departure: str = Field(min_length=1, max_length=300)
