"""Case-builder HTTP routes; storage/code access is supplied by the application's closures."""
from __future__ import annotations

import json
import queue
import threading
from typing import Callable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .ccmc import CCMCRegistry, RegistrySearch, RegistryUnavailable
from .codes import CodeDbMissing, Codes, default_db
from .completeness import Gap, check_completeness
from .identify.answers import apply_answers
from .identify.cards import empty_bm25, present
from .identify.decisions import decision_gaps, information_request, overlay_decisions, record_decision
from .identify.demo_cache import match_demo
from .identify.offline import ProviderOutage, http_live, is_provider_outage
from .identify.pipeline import run as identify_run
from .models import Case
from .process_fields import ProcessField, process_fields
from .professional import ProfessionalResult, professional_involvement
from .section_c import section_c_rows
from .section_d import SectionDPlan, section_d_plan
from .section_d_issues import SectionDIssue, section_d_issues
from .store import CaseStore


class SectionDRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Explicitly confirmed selections. No request field accepts generated process/evidence content.
    provisions: list[str] | None = Field(default=None, min_length=1)


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    field: str | None = None
    question_id: str | None = None
    answer: str = ''


class IdentifyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prose: str = Field(min_length=1)
    answers: list[AnswerIn] = []


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provisions: list[str] = Field(min_length=1)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: str


def create_router(cases: Callable[[], CaseStore], code: Callable[[], Codes],
                  registry: CCMCRegistry | None = None) -> APIRouter:
    router = APIRouter(tags=['case building'])
    registry = registry or CCMCRegistry()

    def get_case(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @router.post('/cases/{case_id}/section-d', response_model=SectionDPlan)
    def section_d(case_id: str, body: SectionDRequest | None = None):
        case = get_case(case_id)
        if body and body.provisions is not None:
            case.provisions = body.provisions
        try:
            case.section_c = section_c_rows(case.provisions, code())
            plan = section_d_plan(case, code())
        except KeyError as error:
            raise HTTPException(404, error.args[0]) from error
        except ValueError as error:
            raise HTTPException(400, f'invalid provision id: {error}') from error
        cases().put(case)
        return plan

    @router.get('/cases/{case_id}/section-d/issues', response_model=list[SectionDIssue])
    def section_d_issues_route(case_id: str):
        try:
            return section_d_issues(get_case(case_id), code())
        except KeyError as error:
            raise HTTPException(404, error.args[0]) from error

    @router.get('/cases/{case_id}/professional', response_model=ProfessionalResult)
    def professional(case_id: str):
        return professional_involvement(get_case(case_id), code())

    @router.get('/ccmc/search', response_model=RegistrySearch)
    def ccmc_search(q: str = Query(min_length=1, max_length=200), limit: int = Query(20, ge=1, le=50)):
        try:
            return registry.search(q, limit=limit)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RegistryUnavailable as error:
            raise HTTPException(503, str(error)) from error

    @router.get('/cases/{case_id}/process-fields', response_model=list[ProcessField])
    def fields(case_id: str):
        return process_fields(get_case(case_id), code())

    @router.get('/cases/{case_id}/gaps', response_model=list[Gap])
    def gaps(case_id: str):
        case = get_case(case_id)
        codes = code()
        found = check_completeness(case, codes)
        extra = decision_gaps(case, codes)
        seen = {item.id for item in found}
        return found + [item for item in extra if item.id not in seen]

    @router.get('/cases/{case_id}/information-request')
    def officer_information_request(case_id: str):
        """Draft of what the officer still needs to ask. Includes identify not_sure questions."""
        return information_request(get_case(case_id))

    def _codes_or_none() -> Codes | None:
        try:
            if not default_db().exists():
                return None
            return code()
        except CodeDbMissing:
            return None

    def _stages(on_stage):
        """Forward stage markers. The done event is emitted once, after card fields are attached."""
        if on_stage is None:
            return None

        def inner(stage, payload=None):
            if stage == 'done':
                return
            on_stage(stage, payload)

        return inner

    def _bm25(prose: str, facts, on_stage) -> dict:
        if not default_db().exists():
            return empty_bm25()
        try:
            return identify_run(prose, facts=facts, on_stage=_stages(on_stage), ranker='bm25')
        except (CodeDbMissing, FileNotFoundError):
            return empty_bm25()
        except Exception as exc:
            if isinstance(exc, ProviderOutage) or is_provider_outage(exc):
                return empty_bm25()
            raise

    def _without_provider(prose: str, facts, on_stage) -> tuple[dict, str]:
        cached = match_demo(prose, facts)
        if cached is not None:
            return cached, 'cached_demo'
        return _bm25(prose, facts, on_stage), 'bm25_fallback'

    def _identify_result(case_id: str, prose: str, facts, on_stage=None) -> dict:
        if http_live():
            if not default_db().exists():
                raise CodeDbMissing()
            try:
                raw = identify_run(prose, facts=facts, on_stage=_stages(on_stage))
                mode = 'live'
            except Exception as exc:
                if isinstance(exc, ProviderOutage) or is_provider_outage(exc):
                    raw, mode = _without_provider(prose, facts, on_stage)
                else:
                    raise
        else:
            raw, mode = _without_provider(prose, facts, on_stage)
        result = present(raw, _codes_or_none(), mode, facts)
        overlay_decisions(result, cases().get(case_id))
        cases().put_identify(case_id, result)
        if on_stage:
            on_stage('done', result)
        return result

    def _stream(case_id: str, prose: str, facts):
        events: queue.Queue = queue.Queue()

        def on_stage(stage, payload=None):
            events.put((stage, payload))

        def worker():
            try:
                _identify_result(case_id, prose, facts, on_stage=on_stage)
            except Exception as exc:
                events.put(('error', {'message': type(exc).__name__}))
            finally:
                events.put(None)

        threading.Thread(target=worker, daemon=True).start()

        def generate():
            while True:
                item = events.get()
                if item is None:
                    break
                stage, payload = item
                yield f'event: {stage}\ndata: {json.dumps(payload, default=str)}\n\n'

        return StreamingResponse(generate(), media_type='text/event-stream')

    @router.post('/cases/{case_id}/identify')
    def identify(case_id: str, body: IdentifyRequest, request: Request):
        """Rank articles and record unknown answers. Does not write provisions."""
        case = get_case(case_id)
        provisions = list(case.provisions)
        if body.answers:
            apply_answers(case, body.answers)
            cases().put(case)
        if 'text/event-stream' in request.headers.get('accept', ''):
            return _stream(case_id, body.prose, case.facts)
        try:
            result = _identify_result(case_id, body.prose, case.facts)
        except (CodeDbMissing, FileNotFoundError):
            raise HTTPException(503, 'code database not found') from None
        saved = cases().get(case_id)
        if list(saved.provisions) != provisions:
            raise HTTPException(500, 'identify must not change provisions')
        return result

    @router.get('/cases/{case_id}/identify')
    def identify_stored(case_id: str):
        """The last identify response for this case. The same card shape as POST."""
        get_case(case_id)
        stored = cases().get_identify(case_id)
        if stored is None:
            raise HTTPException(404, 'identify result not found')
        return overlay_decisions(stored, get_case(case_id))

    @router.get('/cases/{case_id}/identify/stream')
    def identify_stream(case_id: str, prose: str = Query(min_length=1)):
        case = get_case(case_id)
        return _stream(case_id, prose, case.facts)

    @router.post('/cases/{case_id}/identify/confirm', response_model=Case)
    def confirm(case_id: str, body: ConfirmRequest):
        case = get_case(case_id)
        codes = code()
        missing = []
        for provision_id in body.provisions:
            try:
                found = codes.provision(provision_id, 'B')
            except ValueError as exc:
                raise HTTPException(400, f'invalid provision id: {exc}') from exc
            if found is None:
                missing.append(provision_id)
        if missing:
            raise HTTPException(404, {'message': 'citation not in the code database', 'provisions': missing})
        case.provisions = list(body.provisions)
        case.section_c = section_c_rows(body.provisions, codes)
        return cases().put(case)

    @router.post('/cases/{case_id}/identify/{provision_id}/decision')
    def identify_decision(case_id: str, provision_id: str, body: DecisionRequest):
        """Record the applicant's decision. Identify itself never accepts an article."""
        if body.decision not in {'yes', 'no', 'not_sure'}:
            raise HTTPException(422, 'decision must be yes, no, or not_sure')
        case = get_case(case_id)
        stored = cases().get_identify(case_id)
        if stored is None:
            raise HTTPException(404, 'identify result not found')
        try:
            codes = code()
        except CodeDbMissing:
            if body.decision == 'yes':
                raise
            codes = None
        try:
            record_decision(case, stored, provision_id, body.decision, codes)
        except KeyError:
            raise HTTPException(404, 'provision not found') from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        cases().put(case)
        cases().put_identify(case_id, stored)
        return stored

    return router
