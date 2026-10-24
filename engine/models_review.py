"""Officer package review models (WP-34).

A package review reads a Batatis case or an uploaded SCC variance form plus
attachments and lists administrative gaps. It never fills a missing item, never
states compliance, and never writes risk, mitigation or the officer's decision.

These models are standalone (no import from engine.models) so the shared Case
schema is unchanged; sessions are stored in their own table.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REVIEW_SCHEMA = 'batatis.package_review.v1'
REVIEW_NOTICE = (
    'This review lists administrative gaps only. It is not a finding that the design is safe, '
    'that it complies with the code, or that a variance is granted. It does not fill any missing item.'
)

Section = Literal['A', 'B', 'C', 'D', 'process']
FieldStatus = Literal['present', 'blank', 'not_found']
FindingStatus = Literal['blank', 'not_found', 'missing', 'unclear']
FileRole = Literal['scc_form_fillable', 'scc_form_flattened', 'attachment', 'unreadable', 'case_record']


class Pointer(BaseModel):
    """Where a value or gap is: file and 1-based page, form field name, rectangle, exact quote."""
    model_config = ConfigDict(extra='forbid')
    file: str
    page: int | None = Field(default=None, ge=1)
    form_field: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    quote: str | None = None


class FieldReading(BaseModel):
    """One form or record field. `blank` is certain; `not_found` means ask the officer to look."""
    model_config = ConfigDict(extra='forbid')
    field: str
    label: str
    section: Section
    status: FieldStatus
    value: str | None = None          # the exact text read, only when present
    reason: str = ''
    pointer: Pointer


class Finding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str                          # stable across sessions; the re-upload diff matches on it
    section: Section
    field: str
    label: str
    status: FindingStatus
    problem: str | None = None
    defect_class: str | None = None
    message: str
    severity: Literal['blocking', 'warning'] = 'warning'
    routed_to: Literal['applicant', 'officer', 'professional'] = 'applicant'
    pointers: list[Pointer] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class Attribute(BaseModel):
    """A documents-panel cell. `value` is 'unknown' when nothing was read; never a guess."""
    model_config = ConfigDict(extra='forbid')
    value: str = 'unknown'
    known: bool = False
    source: Pointer | None = None


class DocumentRow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    file: str | None = None           # None when listed in Section D but not among the uploaded files
    title: Attribute
    type: Attribute
    issuer: Attribute
    date: Attribute
    evidence_rung: Attribute
    seal: Attribute
    responsible: Attribute
    listed_in_section_d: bool = False
    note: str = ''


class CitationIssue(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str
    message: str


class CitationCheck(BaseModel):
    """Verification of one cited provision against the code database (NBC(AE) 2023, 2nd printing)."""
    model_config = ConfigDict(extra='forbid')
    text: str
    provision_id: str | None = None
    exists: bool | None = None        # None when the database was unavailable
    edition_ok: bool | None = None
    page_ok: bool | None = None       # None when the citation names no page
    canonical_citation: str | None = None
    pdf_page: int | None = None
    issues: list[CitationIssue] = Field(default_factory=list)
    pointer: Pointer


class SectionCCheck(BaseModel):
    model_config = ConfigDict(extra='forbid')
    row: int
    provision_id: str | None
    form_objective: str | None
    form_function: str | None
    table_pairs: list[str] = Field(default_factory=list)
    status: Literal['match', 'mismatch', 'no_table_row', 'provision_not_found', 'not_checked']
    message: str
    pointer: Pointer


class InformationRequestItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    finding_key: str | None = None    # None for an item the officer added
    section: Section | None = None
    field: str | None = None
    text: str
    authored_by: Literal['batatis', 'officer'] = 'batatis'
    included: bool = True
    officer_check: bool = False       # a not-found field: the officer looks before asking


class InformationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    intro: str
    items: list[InformationRequestItem]
    edited: bool = False
    sent_at: str | None = None
    sent_by_name: str | None = None
    message_id: str | None = None
    text: str = ''                    # plain-text rendering of the included items, ready to copy


class DiffEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str
    section: Section
    label: str
    message: str


class ReviewDiff(BaseModel):
    model_config = ConfigDict(extra='forbid')
    previous_version: int
    previous_gaps: int
    resolved: list[DiffEntry]
    still_open: list[DiffEntry]
    new: list[DiffEntry]
    statement: str                    # "x of y gaps resolved"


class InputFile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str
    sha256: str | None = None
    size: int = 0
    pages: int = 0
    role: FileRole
    form_version: str | None = None
    note: str = ''


class ReviewSession(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['batatis.package_review.v1'] = REVIEW_SCHEMA
    administrative_only: Literal[True] = True
    not_a_compliance_determination: Literal[True] = True
    notice: str = REVIEW_NOTICE
    package_id: str
    case_id: str | None = None
    authority: str
    version: int = Field(ge=1)
    created_at: str
    created_by_name: str
    input_kind: Literal['case', 'upload']
    case_version: int | None = None
    files: list[InputFile] = Field(default_factory=list)
    fields: list[FieldReading] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    documents: list[DocumentRow] = Field(default_factory=list)
    citations: list[CitationCheck] = Field(default_factory=list)
    section_c: list[SectionCCheck] = Field(default_factory=list)
    information_request: InformationRequest
    diff: ReviewDiff | None = None
    lookup_skipped: bool = False      # True when the code database was unavailable


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int
    created_at: str
    created_by_name: str
    input_kind: Literal['case', 'upload']
    open_gaps: int
    statement: str | None = None
    sent_at: str | None = None


class RecordItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str
    detail: str = ''
    present: bool = True
    source: Pointer | None = None


class RecordPackage(BaseModel):
    """What the officer sends to the Safety Codes Council and what stays on file. Batatis never sends it."""
    model_config = ConfigDict(extra='forbid')
    send_to_council: list[RecordItem]
    retain_on_file: list[RecordItem]
    basis: list[str]
    note: str


class CloseOut(BaseModel):
    """Close-out after a final decision: the copy goes to the Council within 10 days of the decision."""
    model_config = ConfigDict(extra='forbid')
    case_id: str
    outcome: Literal['accept', 'refuse']
    decided_at: str
    due_date: str                   # ISO date, 10 days after the decision
    days_remaining: int             # negative when overdue
    overdue: bool
    sent: bool                      # the officer recorded that they sent it
    sent_at: str | None = None
    sent_by_name: str | None = None
    record_package: RecordPackage
    notice: str = ('Batatis does not send anything to the Safety Codes Council. The officer sends the copy and '
                   'records it here.')


class PackageReviewIndex(BaseModel):
    model_config = ConfigDict(extra='forbid')
    package_id: str
    case_id: str | None
    authority: str
    sessions: list[SessionSummary]
    latest: ReviewSession | None = None
    close_out: CloseOut | None = None


class InformationRequestEdit(BaseModel):
    """Officer edits: replace the item list (text, inclusion, order) and optionally the intro."""
    model_config = ConfigDict(extra='forbid')
    intro: str | None = Field(default=None, max_length=2000)
    items: list[EditedItem]


class EditedItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str | None = Field(default=None, max_length=100)   # None adds an officer item
    text: str = Field(min_length=1, max_length=2000)
    included: bool = True


InformationRequestEdit.model_rebuild()


class SentInformationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    package_id: str
    version: int
    sent_at: str
    sent_by_name: str
    intro: str
    items: list[str]
    text: str


class SentInformationRequests(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_id: str
    requests: list[SentInformationRequest]
