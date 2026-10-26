"""Administrative submission, officer queue, claims, decisions and conversations."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .access import REVIEWABLE, authorize_case
from .account_models import (reviewing_authority, ApplicationPreferences, ApplicationPreferencesPatch,
                             ApplicationStatus, ApplicantType, Claim, Decision, DecisionItem, DecisionOutcome,
                             MessageAuthor, MessagesResult, StatusChange, StoredMessage,
                             Role, ThreadMessage, User)
from .accounts import require_user
from .completeness import check_completeness
from .jurisdictions import reviewing_authority_names
from .models import Case, ProfessionalRequirementResolution, now
from .process_fields import confirmed_value
from .professional import professional_involvement
from .professional_resolution import requirement_fingerprint
from .review_lifecycle import remember_decision, snapshot, submit_round
from .store import VersionConflict

ACCEPT_TEXT = 'Accepted as administratively complete. Technical review remains the responsibility of the authority.'
RETURN_TEXT = 'Returned for administrative information.'
REFUSE_TEXT = 'Administrative refusal recorded by the reviewing officer. This is not a finding about design compliance or safety.'


class CompletenessSummary(BaseModel):
    answered: int
    total: int


class ReviewerName(BaseModel):
    name: str


class ApplicationSummary(BaseModel):
    id: str
    title: str | None
    status: ApplicationStatus
    authority: str | None
    updated_at: str
    submitted_at: str | None
    submission_number: int
    expires_at: str | None
    completeness: CompletenessSummary | None = None
    unread_messages: int
    reviewer: ReviewerName | None
    archived: bool = False
    pinned: bool = False


class ApplicationsResult(BaseModel):
    applications: list[ApplicationSummary]


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Older callers can omit this; the applicant coordinator pins its acknowledged revision.
    expected_version: int | None = Field(default=None, ge=1, strict=True)


class ApplicantSummary(BaseModel):
    name: str
    applicant_type: ApplicantType | None


class DecisionSummary(BaseModel):
    outcome: DecisionOutcome
    by_name: str
    at: str


class QueueApplication(BaseModel):
    id: str
    title: str | None
    applicant: ApplicantSummary
    authority: str | None
    status: ApplicationStatus
    submitted_at: str | None
    submission_number: int
    expires_at: str | None
    updated_at: str
    completeness: CompletenessSummary | None = None
    claim: Claim | None
    decision: DecisionSummary | None
    unread_messages: int


class QueueResult(BaseModel):
    applications: list[QueueApplication]
    reviewer_id: str
    authority: str


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    take_over: bool = False


class ClaimResult(BaseModel):
    claim: Claim


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    outcome: DecisionOutcome
    # Legacy accept/return callers may omit this. New final refusals pin their displayed revision.
    expected_version: int | None = Field(default=None, ge=1, strict=True,
                                        description='Required for an acceptance and a refusal; the displayed saved application version.')
    # The package-review version on screen. An acceptance needs it whenever the case has a package review:
    # it must be the latest version, read from the saved application as it is now, with nothing required open.
    review_version: int | None = Field(default=None, ge=1, strict=True)
    message: str | None = Field(default=None, max_length=4000)
    items: list[DecisionItem] = Field(default_factory=list, max_length=50)

    @model_validator(mode='after')
    def _reason_required(self):
        if self.outcome == 'refuse' and self.expected_version is None:
            raise ValueError('A refusal requires the displayed application expected_version')
        if self.outcome in {'return', 'refuse'} and (self.message is None or len(self.message.strip()) < 10):
            noun = 'return' if self.outcome == 'return' else 'refusal'
            raise ValueError(f'A {noun} requires a message of at least 10 characters')
        if self.outcome == 'refuse' and self.items:
            raise ValueError('A final refusal has a reason, not a correction checklist')
        return self


class ProfessionalRequirementRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    expected_version: int = Field(ge=1, strict=True)
    required: bool = Field(strict=True)
    scope: str = Field(min_length=3, max_length=1000)
    basis: str = Field(min_length=10, max_length=4000)
    reference: str = Field(min_length=3, max_length=1000)


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(min_length=1, max_length=4000)

    @field_validator('body')
    @classmethod
    def _nonblank(cls, value):
        if not value.strip():
            raise ValueError('Enter a message')
        return value


class MessageReadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Omission keeps the legacy mark-all contract. New readers name only displayed messages.
    message_ids: list[str] | None = Field(default=None, max_length=500)


def reviewer(request: Request) -> User:
    user = require_user(request)
    if user.role != 'reviewer' or not user.authority or not user.onboarded:
        raise HTTPException(403, 'Reviewer account required')
    return user


def unread(case: Case, user: User) -> int:
    return sum(user.id not in message.read_by and message.author.id != user.id and message.kind != 'status'
               for message in case.messages)


def append_message(case, user, body, *, kind='message', items=()):
    message = StoredMessage(author=MessageAuthor(id=user.id, name=user.name, role=user.role), body=body,
                            kind=kind, items=list(items), read_by=[user.id])
    case.messages.append(message)
    return message


def transition(case, user, target, note):
    case.status_history.append(StatusChange(by_id=user.id, by_name=user.name, from_status=case.status,
                                           to_status=target, note=note))
    case.status = target


UNCHANGED = object()


def mutate(store, case_id, user, operation):
    """CAS retries re-run both access and the state-machine preconditions."""
    for _ in range(5):
        case = authorize_case(store.get(case_id), user)
        version = case.version
        result = operation(case)
        if result is UNCHANGED:
            return case, result  # No write: an idempotent operation must not bump the version.
        try:
            return store.put(case, expected_version=version), result
        except VersionConflict as error:
            if error.actual is None:
                raise HTTPException(404, 'case not found') from None
    raise HTTPException(409, 'case was updated concurrently')


def communicate(store, case_id, user, operation):
    """Messages/receipts share the case lock, not its content/workflow revision."""
    saved = store.mutate_messages(case_id, user, operation)
    if saved is None:
        raise HTTPException(404, 'case not found')
    return saved


class NotificationActor(BaseModel):
    name: str
    role: Role | None = None


class Notification(BaseModel):
    id: str
    case_id: str
    case_title: str
    kind: Literal['status', 'message']
    status: ApplicationStatus | None = None
    submission_number: int | None = None
    actor: NotificationActor
    # Not `text`: the NRC attribution layer treats `text` fields as code text.
    summary: str
    created_at: str
    read: bool


class NotificationsResult(BaseModel):
    notifications: list[Notification]
    unread: int


def notification_summary(actor: str, status: str, title: str, submission_number: int | None = None) -> str:
    """What the other party did, in plain words. Never "approved"."""
    if status == 'accepted':
        return f'{actor} accepted {title} as administratively complete'
    verb = ('resubmitted' if status == 'submitted' and (submission_number or 0) > 1
            else {'in_review': 'started reviewing', 'returned': 'returned', 'submitted': 'submitted',
                  'refused': 'recorded an administrative refusal for'}[status])
    return f'{actor} {verb} {title}'


def notifications_for(user, store, limit: int = 50) -> NotificationsResult:
    reviewer = bool(user.role == 'reviewer' and user.authority)
    scoped = ([case for case in store.list_applications(authority=user.authority) if case.owner_id != user.id]
              if reviewer else store.list_applications(owner_id=user.id))
    wanted = {'submitted'} if reviewer else {'in_review', 'returned', 'accepted', 'refused'}
    other_role = 'applicant' if reviewer else 'reviewer'
    seen = user.notifications_seen_at or ''
    items: list[Notification] = []
    for case in scoped:
        title = case.title or 'Untitled application'
        latest: dict[tuple, Notification] = {}
        submission_number = 0
        for index, change in enumerate(case.status_history):
            if change.by_id == case.owner_id and change.to_status == 'submitted' and change.from_status in {'draft', 'returned'}:
                submission_number = max(submission_number + 1, 2 if change.from_status == 'returned' else 1)
            if change.by_id == user.id or change.to_status not in wanted:
                continue
            # Reviewers hear about the applicant's (re)submissions only, not a colleague releasing a claim.
            if reviewer and change.by_id != case.owner_id:
                continue
            note = Notification(
                id=f'{case.id}:status:{index}', case_id=case.id, case_title=title, kind='status',
                status=change.to_status, actor=NotificationActor(name=change.by_name, role=other_role),
                submission_number=submission_number if change.to_status == 'submitted' else None,
                summary=notification_summary(change.by_name, change.to_status, title, submission_number), created_at=change.at,
                read=change.at <= seen)
            # A release and re-claim repeats the same event; keep the newest one.
            latest[(change.by_id, change.to_status)] = note
        items.extend(latest.values())
        for message in case.messages:
            if message.author.id == user.id or message.kind != 'message':
                continue
            items.append(Notification(
                id=f'{case.id}:message:{message.id}', case_id=case.id, case_title=title, kind='message',
                actor=NotificationActor(name=message.author.name, role=message.author.role),
                summary=f'{message.author.name} sent a message about {title}', created_at=message.created_at,
                read=user.id in message.read_by or message.created_at <= seen))
    items.sort(key=lambda item: item.created_at, reverse=True)
    items = items[:limit]
    return NotificationsResult(notifications=items, unread=sum(not item.read for item in items))


MAX_MESSAGES = 500


def threaded(case):
    """Threads exist only between an applicant who owns the case and its authority's reviewers."""
    if not case.owner_id:
        raise HTTPException(404, 'case not found')
    return case


def post_message(case, user, body: str):
    threaded(case)
    if user.role != 'reviewer':
        raise HTTPException(403, 'Only reviewing officers can send notices')
    # Runs against the currently locked row, including concurrent ownership/authority changes.
    authorize_case(case, user, mode='review')
    if len(case.messages) >= MAX_MESSAGES:
        raise HTTPException(409, 'This application has reached its message limit')
    return append_message(case, user, body)


def as_thread(message, user):
    return ThreadMessage(**message.model_dump(exclude={'read_by'}), read_by_me=user.id in message.read_by)


def create_router(cases, code):
    router = APIRouter(tags=['applications and administrative review'])

    @router.get('/me/notifications', response_model=NotificationsResult)
    def notifications(request: Request):
        return notifications_for(require_user(request), cases())

    @router.post('/me/notifications/read', status_code=204)
    def notifications_read(request: Request):
        user = require_user(request).model_copy()
        user.notifications_seen_at = now()
        cases().update_user(user, revoke_sessions=False)  # a read marker is not a privilege change
        return Response(status_code=204)

    @router.get('/me/applications', response_model=ApplicationsResult)
    def applications(request: Request):
        user = require_user(request)
        store = cases()
        preferences = store.list_application_preferences(user.id)
        result = []
        for case in store.list_applications(owner_id=user.id):
            if case.owner_id != user.id:  # A former owner may still have reviewer read access.
                continue
            name = case.claim.reviewer_name if case.claim else case.decision.by_name if case.decision else None
            flags = preferences.get(case.id, ApplicationPreferences())
            result.append(ApplicationSummary(id=case.id, title=case.title, status=case.status,
                authority=case.authority, updated_at=case.updated_at, submitted_at=case.submitted_at,
                submission_number=case.submission_number, expires_at=case.expires_at,
                unread_messages=unread(case, user), reviewer=ReviewerName(name=name) if name else None,
                archived=flags.archived, pinned=flags.pinned))
        return ApplicationsResult(applications=result)

    @router.patch('/me/applications/{application_id}/preferences', response_model=ApplicationPreferences)
    def preferences(application_id: str, body: ApplicationPreferencesPatch, user: User = Depends(require_user)):
        """Owner-only list metadata at any status; never edits or withdraws a case."""
        saved = cases().patch_application_preferences(application_id, user, body.model_dump(exclude_unset=True))
        if saved is None:
            raise HTTPException(404, 'case not found')
        return saved

    @router.post('/cases/{case_id}/submit', response_model=Case)
    def submit(case_id: str, request: Request, body: SubmitRequest | None = None):
        user = require_user(request)

        def apply(case):
            if case.owner_id != user.id:
                raise HTTPException(404, 'case not found')
            if user.role == 'reviewer':
                raise HTTPException(403, 'Reviewer accounts cannot submit applications')
            if case.status not in {'draft', 'returned'}:
                raise HTTPException(409, 'Only draft or returned applications may be submitted')
            if body and body.expected_version is not None and case.version != body.expected_version:
                raise HTTPException(409, 'The saved application changed. Review it before submitting again.')
            blocking = [gap for gap in check_completeness(case, code())
                        if gap.severity == 'blocking' and gap.submission_blocking]
            if blocking:
                raise HTTPException(409, {'message': 'Resolve blocking administrative gaps before submitting',
                                          'gaps': [gap.model_dump() for gap in blocking]})
            if not reviewing_authority(case.authority):
                raise HTTPException(409, f'Choose {reviewing_authority_names()} as the reviewing authority before submitting')
            at = now()
            number = submit_round(case, cases(), at)
            label = 'Resubmitted' if number > 1 else 'Submitted'
            transition(case, user, 'submitted', f'{label} for administrative review · submission {number}')
            case.submitted_at = at
            append_message(case, user, f'{label} for administrative review. Submission {number}.', kind='status')

        return mutate(cases(), case_id, user, apply)[0]

    @router.get('/review/queue', response_model=QueueResult)
    def queue(request: Request, status: ApplicationStatus | None = None, mine: bool = False):
        user = reviewer(request)
        result = []
        store = cases()
        for case in store.list_applications(authority=user.authority):
            if (not case.owner_id or case.owner_id == user.id or case.status not in REVIEWABLE
                    or (status and case.status != status)
                    or (mine and (case.claim is None or case.claim.reviewer_id != user.id))):
                continue
            applicant = store.get_user(case.owner_id)
            result.append(QueueApplication(id=case.id, title=case.title,
                applicant=ApplicantSummary(name=applicant.name if applicant else 'Applicant',
                                           applicant_type=applicant.applicant_type if applicant else None),
                authority=case.authority, status=case.status, submitted_at=case.submitted_at,
                submission_number=case.submission_number, expires_at=case.expires_at,
                updated_at=case.updated_at, claim=case.claim,
                decision=DecisionSummary(**case.decision.model_dump()) if case.decision else None,
                unread_messages=unread(case, user)))
        return QueueResult(applications=result, reviewer_id=user.id, authority=user.authority)

    @router.post('/review/{case_id}/claim', response_model=ClaimResult)
    def claim(case_id: str, request: Request, body: ClaimRequest | None = None):
        user = reviewer(request)

        def apply(case):
            if case.authority != user.authority or not case.owner_id or case.owner_id == user.id:
                raise HTTPException(404, 'case not found')
            if case.status not in {'submitted', 'in_review'}:
                raise HTTPException(409, 'Only submitted applications may be claimed')
            previous = case.claim
            if previous and previous.reviewer_id != user.id:
                if not body or not body.take_over:
                    # Top-level claim is part of the fixed conflict contract.
                    raise ClaimConflict(previous)
                note = f'{user.name} took over administrative review from {previous.reviewer_name}'
            else:
                note = f'{user.name} claimed administrative review'
            if previous and previous.reviewer_id == user.id:
                if case.status == 'submitted':
                    transition(case, user, 'in_review', f'{user.name} resumed administrative review')
                return previous
            case.claim = Claim(reviewer_id=user.id, reviewer_name=user.name)
            transition(case, user, 'in_review', note)
            return case.claim

        try:
            _, saved = mutate(cases(), case_id, user, apply)
        except ClaimConflict as error:
            return JSONResponse(status_code=409, content={'detail': 'Already being reviewed',
                                                         'claim': error.claim.model_dump()})
        return ClaimResult(claim=saved)

    @router.delete('/review/{case_id}/claim', status_code=204)
    def release(case_id: str, request: Request):
        user = reviewer(request)

        def apply(case):
            if not case.claim or case.claim.reviewer_id != user.id:
                raise HTTPException(409, 'Only the current reviewer may release this claim')
            if case.status != 'in_review' or case.decision:
                raise HTTPException(409, 'A completed review cannot be released')
            case.claim = None
            transition(case, user, 'submitted', f'{user.name} released administrative review')

        mutate(cases(), case_id, user, apply)
        return Response(status_code=204)

    @router.post('/review/{case_id}/decision', response_model=Case)
    def decide(case_id: str, body: DecisionRequest, request: Request):
        user = reviewer(request)

        def apply(case):
            if case.owner_id == user.id:
                raise HTTPException(404, 'case not found')
            if not case.claim or case.claim.reviewer_id != user.id:
                raise HTTPException(409, 'Only the current reviewer may record a decision')
            if case.status != 'in_review':
                raise HTTPException(409, 'Only an application in review may receive a decision')
            if body.expected_version is not None and case.version != body.expected_version:
                raise HTTPException(409, 'The application changed. Refresh it before recording a decision.')
            if body.outcome == 'accept':
                # Handoffs allowed at submission still block acceptance and the official PDF.
                blocking = [gap for gap in check_completeness(case, code()) if gap.severity == 'blocking']
                if blocking:
                    raise HTTPException(409, {'message': 'Resolve blocking administrative gaps before accepting',
                                              'gaps': [gap.model_dump() for gap in blocking]})
            status, label = {'accept': ('accepted', ACCEPT_TEXT), 'return': ('returned', RETURN_TEXT),
                             'refuse': ('refused', REFUSE_TEXT)}[body.outcome]
            message = (body.message or '').strip()
            text = label + ('\n\n' + message if message else '')
            remember_decision(case)
            case.decision = Decision(outcome=body.outcome, by_id=user.id, by_name=user.name,
                                     message=text, items=body.items)
            case.decision_history.append(case.decision.model_copy(deep=True))
            if body.outcome == 'return':
                case.return_snapshot = snapshot(case, case.decision.at)
            transition(case, user, status, label)
            append_message(case, user, text, kind='decision', items=body.items)

        return mutate(cases(), case_id, user, apply)[0]

    @router.post('/review/{case_id}/professional-requirement', response_model=Case)
    def resolve_professional_requirement(case_id: str, body: ProfessionalRequirementRequest, request: Request):
        user = reviewer(request)

        def apply(case):
            if case.owner_id == user.id:
                raise HTTPException(404, 'case not found')
            if not case.claim or case.claim.reviewer_id != user.id or case.status != 'in_review':
                raise HTTPException(409, 'Only the current reviewer of an application in review may resolve this requirement')
            if case.version != body.expected_version:
                raise HTTPException(409, 'The application changed. Reload before recording the professional requirement.')
            codes = code()
            # Evaluate the underlying duties, independent of a previous officer determination.
            screen = professional_involvement(case.model_copy(update={'professional_resolutions': []}), codes)
            if (any(reason.source_unresolved for reason in screen.reasons)
                    or not codes.provision('2.4.1.1.(4)', 'C')):
                raise HTTPException(409, 'Resolve the professional source lookups before recording a determination')
            if not body.required and (screen.required == 'yes'
                                      or confirmed_value(case, 'engineering_required') in ('yes', True)):
                raise HTTPException(409, 'A mandatory professional requirement cannot be waived through administrative review')
            case.professional_resolutions.append(ProfessionalRequirementResolution(
                required=body.required, scope=body.scope, basis=body.basis, reference=body.reference,
                by_id=user.id, by_name=user.name or user.email, content_fingerprint=requirement_fingerprint(case)))

        return mutate(cases(), case_id, user, apply)[0]

    @router.get('/cases/{case_id}/messages', response_model=MessagesResult)
    def messages(case_id: str, request: Request):
        user = require_user(request)
        case = threaded(authorize_case(cases().get(case_id), user))
        return MessagesResult(messages=[as_thread(message, user) for message in case.messages], decision=case.decision)

    @router.post('/cases/{case_id}/messages', response_model=ThreadMessage, status_code=201)
    def message(case_id: str, body: MessageRequest, request: Request):
        user = require_user(request)
        _, saved = communicate(cases(), case_id, user, lambda case: post_message(case, user, body.body))
        return as_thread(saved, user)

    @router.post('/cases/{case_id}/messages/read', status_code=204)
    def read(case_id: str, request: Request, body: MessageReadRequest | None = None):
        user = require_user(request)
        displayed = set(body.message_ids) if body is not None and body.message_ids is not None else None

        def apply(case):
            threaded(case)
            changed = False
            for message in case.messages:
                if (displayed is None or message.id in displayed) and user.id not in message.read_by:
                    message.read_by.append(user.id)
                    changed = True
            return None if changed else UNCHANGED

        communicate(cases(), case_id, user, apply)
        return Response(status_code=204)

    return router


class ClaimConflict(Exception):
    def __init__(self, claim):
        self.claim = claim
