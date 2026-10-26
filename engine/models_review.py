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
# The officer's call on one automated finding. `verify` is "not established: look first" and still counts
# against acceptance when the finding is blocking; only `dismissed` (with a reason) stops it counting.
OfficerState = Literal['ask', 'verify', 'dismissed']
DismissReason = Literal['checked', 'not_needed', 'does_not_fit']


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


class RequestTarget(BaseModel):
    """Where the applicant answers a request item: a form section and, when known, one field.

    `field` is an engine field id the applicant workspace maps to the place to fix it (see
    docs/api/package-review.md, "Where the applicant answers"). `label` is what both sides show.
    """
    model_config = ConfigDict(extra='forbid')
    section: Section
    field: str | None = Field(default=None, max_length=200)
    label: str = Field(min_length=1, max_length=200)


class InformationRequestItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    finding_key: str | None = None    # None for an item the officer added
    section: Section | None = None
    field: str | None = None
    text: str
    authored_by: Literal['batatis', 'officer'] = 'batatis'
    # Server-owned for finding-linked items: True exactly when the finding's officer state is `ask`.
    included: bool = True
    officer_check: bool = False       # a not-found field: the officer looks before asking
    target: RequestTarget | None = None   # every item that is sent has one


class Disposition(BaseModel):
    """The officer's call on one automated finding, kept with the session. It never edits the finding.

    Absent means the default: `ask` for an applicant finding the review established, `verify` for a
    not-found or officer-routed one. `dismissed` needs a reason, and a note when the finding is blocking.
    """
    model_config = ConfigDict(extra='forbid')
    key: str
    state: OfficerState
    reason: DismissReason | None = None
    note: str = Field(default='', max_length=500)
    by_name: str | None = None
    at: str | None = None


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
    # An earlier gap the new version can't establish either way (unreadable, not found). Never "resolved".
    unverified: list[DiffEntry] = Field(default_factory=list)
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
    file_id: str | None = None        # a case upload kept with the case: GET /cases/{case_id}/files/{file_id}


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
    dispositions: list[Disposition] = Field(default_factory=list)


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int
    created_at: str
    created_by_name: str
    input_kind: Literal['case', 'upload']
    required: int                     # ReviewTally.required for that version
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
    """Close-out after a final decision.

    An administrative acceptance is not a variance: it only says the file is complete. The copy to the
    Council is due within 10 days of the variance being issued, which happens outside Batatis and which
    the officer records (`issued_on`). Before that, and after a refusal, nothing is due.
    """
    model_config = ConfigDict(extra='forbid')
    case_id: str
    outcome: Literal['accept', 'refuse']
    decided_at: str
    issued_on: str | None = None    # ISO date the officer says the variance was issued; accept only
    issued_by_name: str | None = None
    due_date: str | None = None     # ISO date, 10 days after issued_on; None until issued
    days_remaining: int | None = None   # negative when overdue
    overdue: bool = False
    sent: bool                      # the officer recorded that they sent it
    sent_at: str | None = None
    sent_by_name: str | None = None
    record_package: RecordPackage
    notice: str = ('Batatis does not send anything to the Safety Codes Council. The officer sends the copy and '
                   'records it here.')


class FindingState(BaseModel):
    """A finding's effective officer state (stored disposition or default), as the server counts it."""
    model_config = ConfigDict(extra='forbid')
    key: str
    state: OfficerState
    reason: DismissReason | None = None
    note: str = ''
    by_name: str | None = None
    at: str | None = None
    # The rulebook still requires this on the saved application, so it can't be dismissed: ask for it.
    locked: bool = False


class ReviewTally(BaseModel):
    """The one definition of every count the officer sees, for one session. The client never recounts."""
    model_config = ConfigDict(extra='forbid')
    required: int       # acceptance blockers: blocking findings not dismissed, plus rulebook blocking gaps no finding covers
    to_check: int       # warnings not dismissed
    verify: int         # not established yet, whatever the severity: the officer looks first
    dismissed: int
    asked: int          # items in the request text
    rulebook: int       # rulebook blocking gaps on the saved application with no finding (shown, never dismissible)


class RulebookGap(BaseModel):
    """A blocking gap from the shared completeness rules that no finding covers. Shown as-is."""
    model_config = ConfigDict(extra='forbid')
    id: str
    field: str | None = None
    section: Section | None = None
    message: str


class AcceptGate(BaseModel):
    """Whether this version can be accepted now, decided by the server (the decision route rechecks it)."""
    model_config = ConfigDict(extra='forbid')
    can_accept: bool
    reason: str = ''


class RequestLimits(BaseModel):
    """Checked when the draft is saved and again on return; the client shows them, never enforces others."""
    model_config = ConfigDict(extra='forbid')
    items: int = 50
    intro: int = 2000
    item_text: int = 2000
    text: int = 12000


class Workspace(BaseModel):
    """The officer's working state for the latest version: per-finding states, counts and the accept gate."""
    model_config = ConfigDict(extra='forbid')
    version: int
    case_version: int | None = None
    current: bool                       # this version read the saved application as it is now
    states: list[FindingState]          # one per finding except the peer-review signal, in finding order
    rulebook: list[RulebookGap] = Field(default_factory=list)
    tally: ReviewTally
    gate: AcceptGate
    limits: RequestLimits = Field(default_factory=RequestLimits)


class PackageReviewIndex(BaseModel):
    model_config = ConfigDict(extra='forbid')
    package_id: str
    case_id: str | None
    authority: str
    sessions: list[SessionSummary]
    latest: ReviewSession | None = None
    workspace: Workspace | None = None  # for `latest`; None when there is no session
    close_out: CloseOut | None = None


class InformationRequestEdit(BaseModel):
    """Officer edits, saved as one write: the item list (text, order, officer items), the intro, and the
    officer's call on findings. `findings` lists changes only; findings left out keep their state."""
    model_config = ConfigDict(extra='forbid')
    intro: str | None = Field(default=None, max_length=2000)
    items: list[EditedItem] = Field(max_length=50)
    findings: list[DispositionEdit] = Field(default_factory=list, max_length=200)


class EditedItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str | None = Field(default=None, max_length=100)   # None adds an officer item
    text: str = Field(min_length=1, max_length=2000)
    # Officer items only; a finding-linked item follows its finding's state and ignores this.
    included: bool = True
    target: RequestTarget | None = None   # required for an officer item; finding-linked items keep theirs


class DispositionEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str = Field(min_length=1, max_length=300)
    state: OfficerState
    reason: DismissReason | None = None
    note: str = Field(default='', max_length=500)


class ReturnWithRequest(BaseModel):
    """Send the saved request and return the application, as one write. Both or neither."""
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1, strict=True)   # the saved application version on screen
    text: str = Field(min_length=1, max_length=12000)   # the exact request text the officer previewed


class VarianceIssued(BaseModel):
    """The officer's statement that they issued the variance (outside Batatis) on this date."""
    model_config = ConfigDict(extra='forbid')
    issued_on: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')


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
