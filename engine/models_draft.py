"""Unconfirmed applicant editors and choices. These never establish an answer or a credential."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Key = Annotated[str, Field(min_length=1, max_length=300)]
Text = Annotated[str, Field(max_length=20000)]
Keys = Annotated[list[Key], Field(max_length=1000)]


class DraftText(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base: Text
    value: Text


class EvidenceDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document: Text = ''
    responsible: Text = ''
    date: Text = ''
    evidenceType: Text = ''
    note: Text = ''
    step: int | None = Field(default=None, ge=0, le=10)
    editing: Key | None = None
    fileRef: Key | None = None


class ApplicantDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['manufacturer', 'contractor', 'homebuilder', 'builder', 'designer', 'owner'] = 'homebuilder'
    question_text: dict[Key, DraftText] = Field(default_factory=dict, max_length=1000)
    choices: dict[Key, Text] = Field(default_factory=dict, max_length=1000)
    skipped: Keys = Field(default_factory=list)
    seen: Keys = Field(default_factory=list)
    authority_unsure: bool = False
    packages: dict[Key, Literal['yes', 'no']] = Field(default_factory=dict, max_length=1000)
    rule_unsure: Keys = Field(default_factory=list)
    evidence_drafts: dict[Key, EvidenceDraft] = Field(default_factory=dict, max_length=1000)
