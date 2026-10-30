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
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .access import authorize_case
from .account_models import Decision, DecisionItem, User
from .codes import CodeDbMissing, Codes
from .completeness import check_completeness
from .data.jurisdictions.time_zones import ALBERTA_TIME_ZONE
from .models import Case, now
from .models_review import (CloseOut, Disposition, InformationRequestEdit, PackageReviewIndex, ReturnWithRequest, ReviewSession, SentInformationRequest,
                            SentInformationRequests, SessionSummary, VarianceIssued)
from .review import close_out as closeout
from .review import information_request as ir
from .review import workspace
from .review.package import Parts, review_case, review_uploads
from .review.routes_completeness import create_router as completeness_router
from .review.sessions import SessionConflict, Sessions, return_message_id, claim_live
from .review.uploads import parse_files, read_body
from .routes_review import RETURN_TEXT, append_message, mutate, reviewer, transition
from .review_lifecycle import remember_decision, snapshot
from .store import CaseBackend, ReviewRevision

logger = logging.getLogger(__name__)
def _in_flight(request_) -> bool:
    return not request_.message_id and claim_live(request_.sent_at)

NOT_FOUND = 'package review not found'
CLAIM_NEEDED = 'Claim this application before running or changing its package review'


def _summary(session: ReviewSession, case=None, gaps=()) -> SessionSummary:
    return SessionSummary(version=session.version, created_at=session.created_at,
                          created_by_name=session.created_by_name, input_kind=session.input_kind,
                          required=workspace.build(session, case, gaps).tally.required,
                          statement=session.diff.statement if session.diff else None,
                          sent_at=session.information_request.sent_at if session.information_request.message_id else None)


def same_round(last: ReviewSession | None, case) -> bool:
    """The previous review belongs to the submission on screen and its request was never sent: a re-run
    (after a determination, an edit, or "Review again") continues the officer's work instead of restarting it."""
    if last is None or case is None or last.information_request.message_id:
        return False
    return not case.submitted_at or last.created_at >= case.submitted_at


def carried(last: ReviewSession, findings, request):
    """The officer's calls and own items from the previous review of the same submission. A call on a
    finding that is gone is dropped; workspace.build still refuses a dismissal the rulebook requires."""
    keys = {f.key for f in findings}
    dispositions = [d for d in last.dispositions if d.key in keys]
    own = [item for item in last.information_request.items if not item.finding_key]
    if own:
        request = request.model_copy(update={'items': [*request.items, *own], 'edited': True})
    return dispositions, request


def _build(package_id: str, case_id: str | None, authority: str, user: User, kind: str, parts: Parts,
           previous: list[ReviewSession], case=None) -> ReviewSession:
    last = previous[-1] if previous else None
    diff = ir.diff(last.version, last.findings, parts.findings, lookup_skipped=parts.lookup_skipped) if last else None
    findings = parts.findings + (ir.carry_unverified(last.findings, parts.findings, diff) if last and diff else [])
    request, dispositions = ir.build(findings), []
    if same_round(last, case):
        dispositions, request = carried(last, findings, request)
    return workspace.sync_request(ReviewSession(
        package_id=package_id, case_id=case_id, authority=authority, version=(last.version if last else 0) + 1,
        created_at=now(), created_by_name=user.name, input_kind=kind, case_version=parts.case_version,
        files=parts.files, fields=parts.fields, findings=findings, documents=parts.documents,
        citations=parts.citations, section_c=parts.section_c, information_request=request,
        dispositions=dispositions, diff=diff, lookup_skipped=parts.lookup_skipped, policy=parts.policy))


def rulebook_gaps(case, codes, store=None):
    """The one shared completeness result's gaps for a saved case: computed from its exported package, or
    the case's own when the code database is missing. Every route uses this, so the index, the edit and the
    decision agree."""
    if case is None:
        return []
    return check_completeness(case, codes, store=store) if codes is not None else case.gaps


def decision_items(items):
    return [DecisionItem(section=item.target.section, field=item.target.field or f'request_answer.{item.id}',
        label=item.target.label, request_item_id=item.id, finding_key=item.finding_key, note=item.text)
        for item in items]

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
        except HTTPException as error:
            if error.status_code == 503 and error.detail == 'code database not found':
                return None
            raise

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

    def save(session: ReviewSession, gaps=None) -> ReviewSession:
        try:
            return sessions().add(session, gaps)
        except SessionConflict:
            raise HTTPException(409, 'package review was updated concurrently') from None

    async def uploaded(request: Request) -> list[tuple[str, bytes]]:
        return parse_files(await read_body(request), request.headers.get('content-type', ''))

    def index(package_id: str, found: list[ReviewSession], case=None) -> PackageReviewIndex:
        codes = optional_codes() if case else None
        gaps = rulebook_gaps(case, codes, cases())
        if found:
            found = [*found[:-1], workspace.sync_request(found[-1], case, gaps)]
        summaries = []
        for session in found:
            historical = sessions().rulebook(package_id, session.version) if session != found[-1] else None
            summaries.append(_summary(session, case, historical if historical is not None else gaps))
        return PackageReviewIndex(package_id=package_id, case_id=case.id if case else None,
            authority=case.authority if case else found[0].authority,
            sessions=summaries, latest=found[-1] if found else None,
            workspace=workspace.build(found[-1], case, gaps, codes_available=codes is not None)
                if found else None, close_out=close_out_for(case, found) if case else None)

    def editable(package_id: str, version: int):
        found = sessions().list(package_id)
        session = one(found, version)
        if version != found[-1].version:
            raise HTTPException(409, 'Only the latest package review can be changed')
        if session.information_request.message_id:
            raise HTTPException(409, 'This information request was already sent; run a new review to ask again')
        if _in_flight(session.information_request):
            raise HTTPException(409, 'This information request is being sent', headers={'Retry-After': '5'})
        current = sessions().get(package_id, version)
        if current is None:
            raise HTTPException(404, NOT_FOUND)
        return current

    def validate_request(request_):
        try:
            return ir.validate(request_, targets=True)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    def edit_request(package_id: str, version: int, body: InformationRequestEdit, user: User, case=None):
        session, raw = editable(package_id, version)
        codes = optional_codes() if case else None
        gaps = rulebook_gaps(case, codes, cases())
        state = workspace.build(session, case, gaps)
        states = {s.key: s for s in state.states}
        findings = {f.key: f for f in session.findings}
        linked = {item.finding_key for item in session.information_request.items}
        dispositions = {d.key: d for d in session.dispositions}
        for change in body.findings:
            if change.key not in states:
                raise HTTPException(422, f'Unknown finding {change.key}')
            finding = findings[change.key]
            if change.state == 'dismissed':
                if states[change.key].locked:
                    raise HTTPException(422, 'The completeness rules still require this; ask for it')
                if change.reason is None:
                    raise HTTPException(422, 'Choose a reason for dismissing the finding')
            if change.state == 'ask' and change.key not in linked:
                raise HTTPException(422, 'This finding has no linked request item; add a targeted officer item')
            dispositions[change.key] = Disposition(**change.model_dump(), by_name=user.name, at=now())
        try:
            updated = ir.edit(session.information_request, body.items, body.intro).model_copy(
                update={'sent_at': None, 'sent_by_name': None})
        except KeyError as error:
            raise HTTPException(422, f'unknown information request item {error.args[0]}') from None
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        session = workspace.sync_request(session.model_copy(update={
            'information_request': updated, 'dispositions': list(dispositions.values())}), case, gaps)
        validate_request(session.information_request)
        try:
            # Without the code database the saved rulebook snapshot for this version stays as it was.
            sessions().replace(session, raw, gaps=gaps if codes is not None else None)
        except SessionConflict:
            raise HTTPException(409, 'package review was updated concurrently') from None
        return index(package_id, sessions().list(package_id), case)

    # ------------------------------------------------ case in the reviewer queue (#48)

    @router.post('/review/{case_id}/package-review', response_model=ReviewSession, status_code=201)
    async def run_case_review(case_id: str, request: Request):
        case, user = case_for_reviewer(case_id, request, claimed=True)
        source_case = case
        content_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
        previous = await run_in_threadpool(sessions().list, case_id)
        if content_type == 'multipart/form-data':
            files = await uploaded(request)
            codes = await run_in_threadpool(optional_codes)
            parts = await run_in_threadpool(review_uploads, files, codes)
            parts.case_version = case.version
            for input_file, (name, data) in zip(parts.files, files):
                try:
                    kept = await run_in_threadpool(lambda: cases().put_file(case_id, input_file.name, data, touch=False))
                    input_file.file_id = kept['id'] if kept else None
                except Exception:
                    logger.warning('package upload could not be kept: case=%s file=%s', case_id, name)
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
            source_case = snapshot[0]
            parts = await run_in_threadpool(review_case, source_case, codes, cases())
            current = await run_in_threadpool(cases().get_snapshot, case_id)
            if current is None:
                raise HTTPException(404, 'case not found')
            if current[1] != snapshot[1]:
                raise HTTPException(409, 'case was updated concurrently')
            kind = 'case'
        session = _build(case_id, case_id, case.authority, user, kind, parts, previous, case)
        gaps = await run_in_threadpool(rulebook_gaps, source_case, codes, cases())
        return await run_in_threadpool(save, session, gaps)

    def close_out_for(case, found: list[ReviewSession]) -> CloseOut | None:
        if case.decision is None:
            return None
        from .review.documents import case_rows
        documents = found[-1].documents if found else case_rows(case, cases())
        codes = optional_codes()
        gaps = rulebook_gaps(case, codes, cases())
        return closeout.build(case, found, sessions().closeout(case.id), documents, gaps=gaps)

    @router.get('/review/{case_id}/package-review', response_model=PackageReviewIndex)
    def case_index(case_id: str, request: Request):
        case, _user = case_for_reviewer(case_id, request, claimed=False)
        found = sessions().list(case_id)
        return index(case_id, found, case)

    @router.get('/review/{case_id}/close-out', response_model=CloseOut)
    def case_close_out(case_id: str, request: Request):
        case, _user = case_for_reviewer(case_id, request, claimed=False)
        result = close_out_for(case, sessions().list(case_id))
        if result is None:
            raise HTTPException(404, 'No final decision to close out')
        return result

    @router.post('/review/{case_id}/close-out/issued', response_model=CloseOut)
    def case_close_out_issued(case_id: str, body: VarianceIssued, request: Request):
        case, user = case_for_reviewer(case_id, request, claimed=False)
        if case.decision is None or case.decision.outcome != 'accept':
            raise HTTPException(409, 'Only an accepted application can record variance issuance')
        if case.decision.by_id != user.id and (case.claim is None or case.claim.reviewer_id != user.id):
            raise HTTPException(409, 'Only the deciding reviewer or current claimant may record issuance')
        try:
            issued = date.fromisoformat(body.issued_on)
        except ValueError:
            raise HTTPException(422, 'Enter a valid issuance date') from None
        alberta = ZoneInfo(ALBERTA_TIME_ZONE)
        decided_on = datetime.fromisoformat(case.decision.at).astimezone(alberta).date()
        if issued < decided_on or issued > datetime.now(alberta).date():
            raise HTTPException(422, 'Issuance must be on or after the decision date and not in the future')
        try:
            sessions().record_issuance(case_id, case.decision.at, issued.isoformat(), user.name)
        except SessionConflict:
            raise HTTPException(409, 'Issuance is already recorded for this decision') from None
        return close_out_for(case, sessions().list(case_id))

    @router.post('/review/{case_id}/close-out/sent', response_model=CloseOut)
    def case_close_out_sent(case_id: str, request: Request):
        """The officer records that they sent the copy. Batatis sends nothing."""
        case, user = case_for_reviewer(case_id, request, claimed=False)
        if case.decision is None or case.decision.outcome not in closeout.FINAL_OUTCOMES:
            raise HTTPException(404, 'No final decision to close out')
        if case.decision.by_id != user.id and (case.claim is None or case.claim.reviewer_id != user.id):
            raise HTTPException(409, 'Only the reviewer who recorded the decision may record the close-out')
        recorded = sessions().closeout(case_id)
        if (case.decision.outcome != 'accept' or recorded is None or recorded.decided_at != case.decision.at
                or not recorded.issued_on):
            raise HTTPException(409, 'Record variance issuance before marking the Council copy as sent')
        try:
            sessions().record_closeout(case_id, case.decision.at, now(), user.name)
        except SessionConflict:
            raise HTTPException(409, 'The close-out is already recorded') from None
        return close_out_for(case, sessions().list(case_id))

    @router.get('/review/{case_id}/package-review/{version}', response_model=ReviewSession)
    def case_session(case_id: str, version: int, request: Request):
        case_for_reviewer(case_id, request, claimed=False)
        return one(sessions().list(case_id), version)

    @router.put('/review/{case_id}/package-review/{version}/information-request', response_model=PackageReviewIndex)
    def case_edit(case_id: str, version: int, body: InformationRequestEdit, request: Request):
        case, user = case_for_reviewer(case_id, request, claimed=True)
        return edit_request(case_id, version, body, user, case)

    @router.post('/review/{case_id}/package-review/{version}/return', response_model=Case)
    def return_with_request(case_id: str, version: int, body: ReturnWithRequest, request: Request):
        case, user = case_for_reviewer(case_id, request, claimed=True)
        if case.version != body.expected_version:
            raise HTTPException(409, 'The application changed. Refresh it before returning it.')
        session, raw = editable(case_id, version)
        if session.case_version != case.version:
            # A request drafted from an earlier application must not reach the applicant as current.
            raise HTTPException(409, 'The application changed after this review. Run the review again first.')
        codes = optional_codes()
        gaps = rulebook_gaps(case, codes, cases())
        session = workspace.sync_request(session, case, gaps)
        request_ = session.information_request
        text = validate_request(request_)
        if body.text != text:
            raise HTTPException(409, 'The request changed. Review it again.')
        included = [item for item in request_.items if item.included]
        if not included:
            raise HTTPException(409, 'Include at least one item before returning')
        # A CAS reservation excludes edits while the case commit runs. It is not a sent request.
        claimed = session.model_copy(update={'information_request': request_.model_copy(update={
            'sent_at': now(), 'sent_by_name': user.name, 'text': text})})
        try:
            sessions().replace(claimed, raw)
        except SessionConflict:
            raise HTTPException(409, 'package review was updated concurrently') from None
        claimed_raw = claimed.model_dump_json()

        def apply(case):
            if case.claim is None or case.claim.reviewer_id != user.id or case.status != 'in_review':
                raise HTTPException(409, CLAIM_NEEDED)
            if case.version != body.expected_version:
                raise HTTPException(409, 'The application changed. Refresh it before returning it.')
            current = sessions().get(case_id, version)
            found = sessions().list(case_id)
            if (current is None or found[-1].version != version or current[1] != claimed_raw):
                raise HTTPException(409, 'The request changed. Review it again.')
            if any(m.id == return_message_id(version) for m in case.messages):
                raise HTTPException(409, 'This information request was already sent')
            items = decision_items(included)
            message_text = RETURN_TEXT + '\n\n' + text
            remember_decision(case)
            case.decision = Decision(outcome='return', by_id=user.id, by_name=user.name,
                                     message=message_text, items=items)
            case.decision_history.append(case.decision.model_copy(deep=True))
            case.return_snapshot = snapshot(case, case.decision.at, cases())
            transition(case, user, 'returned', RETURN_TEXT)
            message = append_message(case, user, message_text, kind='decision', items=items)
            message.id = return_message_id(version)
            return ReviewRevision(version, claimed_raw)

        try:
            saved, _message = mutate(cases(), case_id, user, apply)
        except BaseException:
            # A backend can fail after committing. Only release a reservation when the case proves no send.
            try:
                current = sessions().get(case_id, version)
                if current is not None and not current[0].information_request.message_id:
                    sessions().replace(session, claimed_raw)
            except Exception:
                logger.warning('return reservation release failed: case=%s version=%s', case_id, version)
            raise
        try:
            done, _ = sessions().get(case_id, version)
            sessions().replace(done, claimed_raw)
        except Exception:
            # Reads always reconcile from the decision message, so success does not depend on this write.
            logger.warning('return session finalization deferred: case=%s version=%s', case_id, version)
        return saved

    @router.post('/review/{case_id}/package-review/{version}/information-request/send', response_model=ReviewSession)
    def case_send(case_id: str, version: int, request: Request):
        case, user = case_for_reviewer(case_id, request, claimed=True)
        current = sessions().get(case_id, version)
        if current is None:
            raise HTTPException(404, NOT_FOUND)
        session, raw = current
        codes = optional_codes()
        gaps = rulebook_gaps(case, codes, cases())
        session = workspace.sync_request(session, case, gaps)
        request_ = session.information_request
        if request_.message_id:
            raise HTTPException(409, 'This information request was already sent')
        if _in_flight(request_):
            raise HTTPException(409, 'This information request is being sent', headers={'Retry-After': '5'})
        included = [item for item in request_.items if item.included]
        if not included:
            raise HTTPException(409, 'Include at least one item before sending')
        text = validate_request(request_)
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
            items = decision_items(included)
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
        return index(package_id, found)

    @router.get('/package-review/{package_id}/{version}', response_model=ReviewSession)
    def package_session(package_id: str, version: int, request: Request):
        user = reviewer(request)
        return one(standalone(package_id, user), version)

    @router.put('/package-review/{package_id}/{version}/information-request', response_model=PackageReviewIndex)
    def package_edit(package_id: str, version: int, body: InformationRequestEdit, request: Request):
        user = reviewer(request)
        standalone(package_id, user)
        return edit_request(package_id, version, body, user)

    return router
