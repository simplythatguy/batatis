"""Account and administrative review wire records. Credentials never enter a Case."""
from __future__ import annotations

from typing import get_args, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from .models_ids import new_id, now

Role = Literal['applicant', 'reviewer']
ApplicantType = Literal['manufacturer', 'contractor', 'homebuilder']
Authority = Literal['calgary', 'edmonton']


def reviewing_authority(value: str | None) -> 'Authority | None':
    """Only authorities that have reviewers; anything else (e.g. alberta-other) is not reviewable."""
    return value if value in get_args(Authority) else None  # type: ignore[return-value]
ApplicationStatus = Literal['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused', 'withdrawn']
DecisionOutcome = Literal['accept', 'return', 'refuse']


class User(BaseModel):
    id: str = Field(default_factory=lambda: new_id('user'))
    email: str
    name: str
    role: Role | None = None
    applicant_type: ApplicantType | None = None
    authority: Authority | None = None
    onboarded: bool = False
    created_at: str = Field(default_factory=now)
    # Notifications created at or before this instant count as read.
    notifications_seen_at: str | None = None


class UserResult(BaseModel):
    user: User


class ApplicationPreferences(BaseModel):
    archived: bool = False
    pinned: bool = False


class ApplicationPreferencesPatch(BaseModel):
    """Omitted fields keep their stored value; explicit values must be booleans."""
    model_config = ConfigDict(extra='forbid', json_schema_extra={'minProperties': 1})
    archived: StrictBool = False
    pinned: StrictBool = False

    @model_validator(mode='after')
    def _nonempty(self):
        if not self.model_fields_set:
            raise ValueError('Supply archived or pinned')
        return self


class Claim(BaseModel):
    reviewer_id: str
    reviewer_name: str
    claimed_at: str = Field(default_factory=now)


class DecisionItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    gap_id: str | None = Field(default=None, min_length=1, max_length=200)
    field: str | None = Field(default=None, min_length=1, max_length=200)
    note: str = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def _location(self):
        if not (self.gap_id or self.field) or not self.note.strip():
            raise ValueError('An item needs gap_id or field and a nonblank note')
        return self


class Decision(BaseModel):
    outcome: DecisionOutcome
    by_id: str
    by_name: str
    at: str = Field(default_factory=now)
    message: str
    items: list[DecisionItem] = Field(default_factory=list)


class StatusChange(BaseModel):
    by_id: str
    by_name: str
    at: str = Field(default_factory=now)
    from_status: ApplicationStatus
    to_status: ApplicationStatus
    note: str = ''


class MessageAuthor(BaseModel):
    id: str
    name: str
    role: Role | None


class StoredMessage(BaseModel):
    id: str = Field(default_factory=lambda: new_id('msg'))
    author: MessageAuthor
    body: str
    items: list[DecisionItem] = Field(default_factory=list)
    kind: Literal['message', 'decision', 'status'] = 'message'
    created_at: str = Field(default_factory=now)
    read_by: list[str] = Field(default_factory=list)


class ThreadMessage(BaseModel):
    id: str
    author: MessageAuthor
    body: str
    items: list[DecisionItem]
    kind: Literal['message', 'decision', 'status']
    created_at: str
    read_by_me: bool


class MessagesResult(BaseModel):
    messages: list[ThreadMessage]
