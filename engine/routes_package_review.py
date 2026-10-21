"""Officer package review routes (WP-34). One router for api.py to include.

Administrative completeness only: these routes never fill a missing item, never
state compliance, and never write risk, mitigation or the officer's decision.

Access goes through the central guard (engine/access.py): `/review/{case_id}/...`
paths run in review mode (a reviewer of the case's authority, application
submitted or later), `/cases/{case_id}/information-request` in read mode (owner
or that reviewer). Running a review, editing or sending its information request
additionally needs the current claim. Standalone uploads (`/package-review`) are
reviewer-only and scoped to the reviewer's authority.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .access import authorize_case
from .account_models import DecisionItem, User
from .codes import CodeDbMissing, Codes
from .models import now
from .models_review import (CloseOut, InformationRequestEdit, PackageReviewIndex, ReviewSession, SentInformationRequest,
                            SentInformationRequests, SessionSummary)
from .review import close_out as closeout
from .review import information_request as ir
from .review.package import Parts, review_case, review_uploads
from .review.routes_completeness import create_router as completeness_router
from .review.sessions import SessionConflict, Sessions
from .review.uploads import parse_files, read_body
from .routes_review import append_message, mutate, reviewer
from .store import CaseBackend

logger = logging.getLogger(__name__)
# A send claims the request (sent_at, no message_id yet) before posting. A claim older than this
# never finished, because the post failed and its release failed too, so it no longer blocks a retry.
SEND_CLAIM_TTL = timedelta(minutes=2)


def _in_flight(request_) -> bool:
    if request_.message_id or not request_.sent_at:
        return False
    try:
        claimed_at = datetime.fromisoformat(request_.sent_at)
    except ValueError:
        return False
    if claimed_at.tzinfo is None:
        claimed_at = claimed_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - claimed_at < SEND_CLAIM_TTL

NOT_FOUND = 'package review not found'
CLAIM_NEEDED = 'Claim this application before running or changing its package review'


def _summary(session: ReviewSession) -> SessionSummary:
    return SessionSummary(version=session.version, created_at=session.created_at,
                          created_by_name=session.created_by_name, input_kind=session.input_kind,
                          open_gaps=len(ir.open_gaps(session.findings)),
                          statement=session.diff.statement if session.diff else None,
                          sent_at=session.information_request.sent_at)


def _build(package_id: str, case_id: str | None, authority: str, user: User, kind: str, parts: Parts,
           previous: list[ReviewSession]) -> ReviewSession:
    last = previous[-1] if previous else None
    return ReviewSession(
        package_id=package_id, case_id=case_id, authority=authority, version=(last.version if last else 0) + 1,
        created_at=now(), created_by_name=user.name, input_kind=kind, case_version=parts.case_version,
        files=parts.files, fields=parts.fields, findings=parts.findings, documents=parts.documents,
        citations=parts.citations, section_c=parts.section_c, information_request=ir.build(parts.findings),
        diff=ir.diff(last.version, last.findings, parts.findings) if last else None,
        lookup_skipped=parts.lookup_skipped)


def create_router(cases: Callable[[], CaseBackend], code: Callable[[], Codes]) -> APIRouter:
    router = APIRouter(tags=['package review'])
    router.include_router(completeness_router(cases, code))

    def sessions() -> Sessions:
        return Sessions(cases())

    def optional_codes():
        try:
            return code()
        except CodeDbMissing:
            return None

    def case_for_reviewer(case_id: str, request: Request, *, claimed: bool):
        """Central policy in review mode first, so applicants and other authorities see 404, never a 403."""
        case = authorize_case(cases().get(case_id), getattr(request.state, 'user', None), mode='review')
        if not case.owner_id:
            raise HTTPException(404, 'case not found')   # unowned legacy cases have no reviewer workflow
        user = reviewer(request)
        if case.authority != user.authority or case.owner_id == user.id:
            raise HTTPException(404, 'case not found')
        if claimed and (case.claim is None or case.claim.reviewer_id != user.id or case.status != 'in_review'):
            raise HTTPException(409, CLAIM_NEEDED)
        return case, user

    def standalone(package_id: str, user: User) -> list[ReviewSession]:
        found = sessions().list(package_id)
        if not found or found[0].case_id is not None or found[0].authority != user.authority:
            raise HTTPException(404, NOT_FOUND)
        return found

    def one(found: list[ReviewSession], version: int) -> ReviewSession:
        for session in found:
            if session.version == version:
                return session
        raise HTTPException(404, NOT_FOUND)

    def save(session: ReviewSession) -> ReviewSession:
        try:
            return sessions().add(session)
        except SessionConflict:
            raise HTTPException(409, 'package review was updated concurrently') from None

    async def uploaded(request: Request) -> list[tuple[str, bytes]]:
        return parse_files(await read_body(request), request.headers.get('content-type', ''))

    def edit_request(package_id: str, version: int, body: InformationRequestEdit) -> ReviewSession:
        current = sessions().get(package_id, version)
        if current is None:
            raise HTTPException(404, NOT_FOUND)
        session, raw = current
        if session.information_request.message_id:
            raise HTTPException(409, 'This information request was already sent; run a new review to ask again')
        if _in_flight(session.information_request):
            raise HTTPException(409, 'This information request is being sent', headers={'Retry-After': '5'})
        try:
            # An expired, never-posted claim is cleared by the edit.
            updated = ir.edit(session.information_request, body.items, body.intro).model_copy(
                update={'sent_at': None, 'sent_by_name': None})
        except KeyError as error:
            raise HTTPException(422, f'unknown information request item {error.args[0]}') from None
        session = session.model_copy(update={'information_request': updated})
        try:
            return sessions().replace(session, raw)
        except SessionConflict:
            raise HTTPException(409, 'package review was updated concurrently') from None

    # ------------------------------------------------ case in the reviewer queue (#48)

    @router.post('/review/{case_id}/package-review', response_model=ReviewSession, status_code=201)
    async def run_case_review(case_id: str, request: Request):
        case, user = case_for_reviewer(case_id, request, claimed=True)
        content_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
        previous = await run_in_threadpool(sessions().list, case_id)
        if content_type == 'multipart/form-data':
            files = await uploaded(request)
            parts = await run_in_threadpool(review_uploads, files, await run_in_threadpool(optional_codes))
            kind = 'upload'
        else:
            body = await request.body()
            if body.strip() not in (b'', b'{}'):
                raise HTTPException(422, 'Send no body to review the saved case, or multipart PDFs to review uploads')
            snapshot = await run_in_threadpool(cases().get_snapshot, case_id)
            if snapshot is None:
                raise HTTPException(404, 'case not found')
            try:
                codes = await run_in_threadpool(code)
            except CodeDbMissing:
                raise HTTPException(503, 'code database not found') from None
            parts = await run_in_threadpool(review_case, snapshot[0], codes, cases())
            current = await run_in_threadpool(cases().get_snapshot, case_id)
            if current is None:
                raise HTTPException(404, 'case not found')
            if current[1] != snapshot[1]:
                raise HTTPException(409, 'case was updated concurrently')
            kind = 'case'
        session = _build(case_id, case_id, case.authority, user, kind, parts, previous)
        return await run_in_threadpool(save, session)

    def close_out_for(case, found: list[ReviewSession]) -> CloseOut | None:
        if case.decision is None:
            return None
        from .review.documents import case_rows
        documents = found[-1].documents if found else case_rows(case, cases())
        return closeout.build(case, found, sessions().closeout(case.id), documents)

    @router.get('/review/{case_id}/package-review', response_model=PackageReviewIndex)
    def case_index(case_id: str, request: Request):
        case, _user = case_for_reviewer(case_id, request, claimed=False)
        found = sessions().list(case_id)
        return PackageReviewIndex(package_id=case_id, case_id=case_id, authority=case.authority,
                                  sessions=[_summary(s) for s in found], latest=found[-1] if found else None,
                                  close_out=close_out_for(case, found))

    @router.get('/review/{case_id}/close-out', response_model=CloseOut)
    def case_close_out(case_id: str, request: Request):
        case, _user = case_for_reviewer(case_id, request, claimed=False)
        result = close_out_for(case, sessions().list(case_id))
        if result is None:
            raise HTTPException(404, 'No final decision to close out')
        return result

    @router.post('/review/{case_id}/close-out/sent', response_model=CloseOut)
    def case_close_out_sent(case_id: str, request: Request):
        """The officer records that they sent the copy. Batatis sends nothing."""
        case, user = case_for_reviewer(case_id, request, claimed=False)
        if case.decision is None or case.decision.outcome not in closeout.FINAL_OUTCOMES:
            raise HTTPException(404, 'No final decision to close out')
        if case.decision.by_id != user.id and (case.claim is None or case.claim.reviewer_id != user.id):
            raise HTTPException(409, 'Only the reviewer who recorded the decision may record the close-out')
        try:
            sessions().record_closeout(case_id, case.decision.at, now(), user.name)
        except SessionConflict:
            raise HTTPException(409, 'The close-out is already recorded') from None
        return close_out_for(case, sessions().list(case_id))

    @router.get('/review/{case_id}/package-review/{version}', response_model=ReviewSession)
    def case_session(case_id: str, version: int, request: Request):
        case_for_reviewer(case_id, request, claimed=False)
        return one(sessions().list(case_id), version)

    @router.put('/review/{case_id}/package-review/{version}/information-request', response_model=ReviewSession)
    def case_edit(case_id: str, version: int, body: InformationRequestEdit, request: Request):
        case_for_reviewer(case_id, request, claimed=True)
        return edit_request(case_id, version, body)

    @router.post('/review/{case_id}/package-review/{version}/information-request/send', response_model=ReviewSession)
    def case_send(case_id: str, version: int, request: Request):
        _case, user = case_for_reviewer(case_id, request, claimed=True)
        current = sessions().get(case_id, version)
        if current is None:
            raise HTTPException(404, NOT_FOUND)
        session, raw = current
        request_ = session.information_request
        if request_.message_id:
            raise HTTPException(409, 'This information request was already sent')
        if _in_flight(request_):
            raise HTTPException(409, 'This information request is being sent', headers={'Retry-After': '5'})
        included = [item for item in request_.items if item.included]
        if not included:
            raise HTTPException(409, 'Include at least one item before sending')
        text = ir.render(request_)[:4000]
        # Claim the send first, so a concurrent send or edit gets 409 before anything reaches the applicant.
        claimed = session.model_copy(update={'information_request': request_.model_copy(
            update={'sent_at': now(), 'sent_by_name': user.name, 'text': text})})
        try:
            sessions().replace(claimed, raw)
        except SessionConflict:
            raise HTTPException(409, 'package review was updated concurrently') from None
        claimed_raw = claimed.model_dump_json()

        def post(case):
            # Re-checked on the version actually written: a take-over or a decision stops the send.
            if case.claim is None or case.claim.reviewer_id != user.id or case.status != 'in_review':
                raise HTTPException(409, CLAIM_NEEDED)
            items = [DecisionItem(field=(item.field or 'information_request')[:200], note=item.text[:2000])
                     for item in included]
            return append_message(case, user, text, items=items)

        try:
            _, message = mutate(cases(), case_id, user, post)
        except BaseException:
            try:
                sessions().replace(session, claimed_raw)   # nothing was posted: release the claim
            except Exception:  # noqa: BLE001 - keep the original error; a stuck claim expires (_in_flight)
                logger.warning('information request claim release failed: case=%s version=%s', case_id, version)
            raise
        done = claimed.model_copy(update={'information_request': claimed.information_request.model_copy(
            update={'message_id': message.id})})
        # Only this request holds the claim, and edits refuse a sent request, so this write cannot conflict.
        return sessions().replace(done, claimed_raw)

    @router.get('/cases/{case_id}/information-request', response_model=SentInformationRequests)
    def sent_requests(case_id: str, request: Request):
        # The guard has authorized the caller (owner, or a reviewer of this authority). Drafts stay private.
        if getattr(request.state, 'case', None) is None:
            raise HTTPException(404, 'case not found')
        if not request.state.case.owner_id:
            raise HTTPException(404, 'case not found')
        out = []
        for session in sessions().list(case_id):
            sent = session.information_request
            if not sent.message_id:   # never posted (or still being posted): not visible to the applicant
                continue
            out.append(SentInformationRequest(
                package_id=session.package_id, version=session.version, sent_at=sent.sent_at,
                sent_by_name=sent.sent_by_name or '', intro=sent.intro,
                items=[item.text for item in sent.items if item.included], text=sent.text))
        return SentInformationRequests(case_id=case_id, requests=out)

    # ------------------------------------------------ standalone upload (third-party package)

    @router.post('/package-review', response_model=ReviewSession, status_code=201)
    async def run_upload_review(request: Request):
        user = reviewer(request)
        files = await uploaded(request)
        parts = await run_in_threadpool(review_uploads, files, await run_in_threadpool(optional_codes))
        session = _build(f'pkg_{uuid.uuid4().hex[:12]}', None, user.authority, user, 'upload', parts, [])
        return await run_in_threadpool(save, session)

    @router.post('/package-review/{package_id}', response_model=ReviewSession, status_code=201)
    async def reupload(package_id: str, request: Request):
        user = reviewer(request)
        previous = await run_in_threadpool(standalone, package_id, user)
        files = await uploaded(request)
        parts = await run_in_threadpool(review_uploads, files, await run_in_threadpool(optional_codes))
        session = _build(package_id, None, user.authority, user, 'upload', parts, previous)
        return await run_in_threadpool(save, session)

    @router.get('/package-review/{package_id}', response_model=PackageReviewIndex)
    def package_index(package_id: str, request: Request):
        user = reviewer(request)
        found = standalone(package_id, user)
        return PackageReviewIndex(package_id=package_id, case_id=None, authority=found[0].authority,
                                  sessions=[_summary(s) for s in found], latest=found[-1])

    @router.get('/package-review/{package_id}/{version}', response_model=ReviewSession)
    def package_session(package_id: str, version: int, request: Request):
        user = reviewer(request)
        return one(standalone(package_id, user), version)

    @router.put('/package-review/{package_id}/{version}/information-request', response_model=ReviewSession)
    def package_edit(package_id: str, version: int, body: InformationRequestEdit, request: Request):
        user = reviewer(request)
        standalone(package_id, user)
        return edit_request(package_id, version, body)

    return router
