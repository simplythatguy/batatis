"""Administrative submission, officer queue, claims, decisions and conversations."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .access import REVIEWABLE, authorize_case
from .account_models import (reviewing_authority, ApplicationStatus, ApplicantType, Claim, Decision, DecisionItem, DecisionOutcome,
                             MessageAuthor, MessagesResult, StatusChange, StoredMessage,
                             Role, ThreadMessage, User)
from .accounts import require_user
from .completeness import check_completeness
from .jurisdictions import reviewing_authority_names
from .models import Case, now
from .store import VersionConflict

ACCEPT_TEXT = 'Accepted as administratively complete. Technical review remains the responsibility of the authority.'
RETURN_TEXT = 'Returned for administrative information.'
REFUSE_TEXT = 'Refusal recorded by the reviewing officer.'


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
    completeness: CompletenessSummary | None = None
    unread_messages: int
    reviewer: ReviewerName | None


class ApplicationsResult(BaseModel):
    applications: list[ApplicationSummary]


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
    updated_at: str
    completeness: CompletenessSummary | None = None
    claim: Claim | None
    decision: DecisionSummary | None
    unread_messages: int


class QueueResult(BaseModel):
    applications: list[QueueApplication]


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    take_over: bool = False


class ClaimResult(BaseModel):
    claim: Claim


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    outcome: DecisionOutcome
    message: str | None = Field(default=None, max_length=4000)
    items: list[DecisionItem] = Field(default_factory=list, max_length=50)

    @model_validator(mode='after')
    def _reason_required(self):
        if self.outcome in {'return', 'refuse'} and (self.message is None or len(self.message.strip()) < 10):
            noun = 'return' if self.outcome == 'return' else 'refusal'
            raise ValueError(f'A {noun} requires a message of at least 10 characters')
        return self


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(min_length=1, max_length=4000)

    @field_validator('body')
    @classmethod
    def _nonblank(cls, value):
        if not value.strip():
            raise ValueError('Enter a message')
        return value


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


class NotificationActor(BaseModel):
    name: str
    role: Role | None = None


class Notification(BaseModel):
    id: str
    case_id: str
    case_title: str
    kind: Literal['status', 'message']
    status: ApplicationStatus | None = None
    actor: NotificationActor
    # Not `text`: the NRC attribution layer treats `text` fields as code text.
    summary: str
    created_at: str
    read: bool


class NotificationsResult(BaseModel):
    notifications: list[Notification]
    unread: int


def notification_summary(actor: str, status: str, title: str) -> str:
    """What the other party did, in plain words. Never "approved"."""
    if status == 'accepted':
        return f'{actor} accepted {title} as administratively complete'
    verb = {'in_review': 'started reviewing', 'returned': 'returned', 'submitted': 'submitted',
            'refused': 'recorded a refusal for'}[status]
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
        for index, change in enumerate(case.status_history):
            if change.by_id == user.id or change.to_status not in wanted:
                continue
            # Reviewers hear about the applicant's (re)submissions only, not a colleague releasing a claim.
            if reviewer and change.by_id != case.owner_id:
                continue
            note = Notification(
                id=f'{case.id}:status:{index}', case_id=case.id, case_title=title, kind='status',
                status=change.to_status, actor=NotificationActor(name=change.by_name, role=other_role),
                summary=notification_summary(change.by_name, change.to_status, title), created_at=change.at,
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
        result = []
        for case in cases().list_applications(owner_id=user.id):
            name = case.claim.reviewer_name if case.claim else case.decision.by_name if case.decision else None
            result.append(ApplicationSummary(id=case.id, title=case.title, status=case.status,
                authority=case.authority, updated_at=case.updated_at, submitted_at=case.submitted_at,
                unread_messages=unread(case, user), reviewer=ReviewerName(name=name) if name else None))
        return ApplicationsResult(applications=result)

    @router.post('/cases/{case_id}/submit', response_model=Case)
    def submit(case_id: str, request: Request):
        user = require_user(request)

        def apply(case):
            if case.owner_id != user.id:
                raise HTTPException(404, 'case not found')
            if user.role == 'reviewer':
                raise HTTPException(403, 'Reviewer accounts cannot submit applications')
            if case.status not in {'draft', 'returned'}:
                raise HTTPException(409, 'Only draft or returned applications may be submitted')
            blocking = [gap for gap in check_completeness(case, code()) if gap.severity == 'blocking']
            if blocking:
                raise HTTPException(409, {'message': 'Resolve blocking administrative gaps before submitting',
                                          'gaps': [gap.model_dump() for gap in blocking]})
            if not reviewing_authority(case.authority):
                raise HTTPException(409, f'Choose {reviewing_authority_names()} as the reviewing authority before submitting')
            transition(case, user, 'submitted', 'Submitted for administrative review')
            case.submitted_at = now()
            case.claim = case.decision = None
            append_message(case, user, 'Submitted for administrative review.', kind='status')

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
                updated_at=case.updated_at, claim=case.claim,
                decision=DecisionSummary(**case.decision.model_dump()) if case.decision else None,
                unread_messages=unread(case, user)))
        return QueueResult(applications=result)

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
            if body.outcome == 'accept':
                # Same gate as submission and the official PDF: never accept with blocking gaps.
                blocking = [gap for gap in check_completeness(case, code()) if gap.severity == 'blocking']
                if blocking:
                    raise HTTPException(409, {'message': 'Resolve blocking administrative gaps before accepting',
                                              'gaps': [gap.model_dump() for gap in blocking]})
            status, label = {'accept': ('accepted', ACCEPT_TEXT), 'return': ('returned', RETURN_TEXT),
                             'refuse': ('refused', REFUSE_TEXT)}[body.outcome]
            message = (body.message or '').strip()
            text = label + ('\n\n' + message if message else '')
            case.decision = Decision(outcome=body.outcome, by_id=user.id, by_name=user.name,
                                     message=text, items=body.items)
            transition(case, user, status, label)
            append_message(case, user, text, kind='decision', items=body.items)

        return mutate(cases(), case_id, user, apply)[0]

    @router.get('/cases/{case_id}/messages', response_model=MessagesResult)
    def messages(case_id: str, request: Request):
        user = require_user(request)
        case = threaded(authorize_case(cases().get(case_id), user))
        return MessagesResult(messages=[as_thread(message, user) for message in case.messages])

    @router.post('/cases/{case_id}/messages', response_model=ThreadMessage, status_code=201)
    def message(case_id: str, body: MessageRequest, request: Request):
        user = require_user(request)

        def apply(case):
            threaded(case)
            # One way only: the officer tells the applicant. The applicant answers by updating the
            # application and sending it again, never by chatting (less work for the officer).
            if user.role != 'reviewer':
                raise HTTPException(403, 'Messages go one way, from the reviewing officer. Update the application and send it again instead.')
            return post_message(case, user, body.body)

        _, saved = mutate(cases(), case_id, user, apply)
        return as_thread(saved, user)

    @router.post('/cases/{case_id}/messages/read', status_code=204)
    def read(case_id: str, request: Request):
        user = require_user(request)

        def apply(case):
            threaded(case)
            changed = False
            for message in case.messages:
                if user.id not in message.read_by:
                    message.read_by.append(user.id)
                    changed = True
            return None if changed else UNCHANGED

        mutate(cases(), case_id, user, apply)
        return Response(status_code=204)

    return router


class ClaimConflict(Exception):
    def __init__(self, claim):
        self.claim = claim
