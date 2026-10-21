"""Code identification routes. Extracted from PR #12's routes_case.py and rebuilt on dev's gate and guard.

POST /cases/{id}/identify            explicit run (JSON, or SSE stage events with Accept: text/event-stream)
GET  /cases/{id}/identify            the stored result; never calls a provider
POST /cases/{id}/identify/{provision}/decision   yes | no | not_sure
POST /cases/{id}/identify/confirm    write provisions after a code-database check
POST /cases/{id}/identify/benchmark  the applicant names the benchmark sentence and confirms the departure
GET  /cases/{id}/information-request the officer draft of not_sure items
GET  /cases/{id}/process-refs        Div A 1.2.1.1. and Div C 2.3.1.1., read-only, from codedb

Writes are owner edits (engine/access.py: POST is mode `edit`), so reviewers are read-only. Outbound
text is redacted with engine/redact.py exactly as routes_relevance.py does. Identify never changes
provisions; only a `yes` decision or confirm does.
"""
from __future__ import annotations

import contextvars
import json
import logging
import queue
import threading
from typing import Callable

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from .codes import Codes
from .copyright import attach_meta, attribute_code
from .identify.answers import apply_answers
from .identify.config import ConfigError, load_config
from .identify.decisions import information_request, overlay_decisions, record_decision
from .identify.http_models import (BenchmarkConfirmRequest, IdentifyConfirmRequest, IdentifyDecisionRequest,
                                   IdentifyRequest)
from .identify.pipeline import RunOutput, description_hash, run as identify_run
from .identify.providers import Transports
from .identify.title import short_title, title_should_replace
from .llm_gate import client_ip_from, identify_retry_after
from .models import Case, now
from .models_identify import IdentifyResult, ProcessRef
from .process_refs import ProcessRefMissing, process_refs
from .redact import known_values, people_names, scrub
from .relevance import BANDS_FILE, CaseScorings, RelevanceInProgress, description, display_probabilities
from .relevance_models import RelevanceBands, RelevanceRecord
from .section_c import section_c_rows
from .store import CaseBackend, VersionConflict

logger = logging.getLogger(__name__)
TransportFactory = Callable[[str | None], Transports]


def _current(result: IdentifyResult, case: Case) -> IdentifyResult:
    out = result.model_copy(deep=True)
    out.stale = out.description_sha256 != description_hash(description(case))
    out.persisted = True
    return overlay_decisions(out)


def _relevance(output: RunOutput, text: str) -> RelevanceRecord | None:
    """The same rings as POST /relevance: the identify run's screen and rerank, stored on the case."""
    if not output.screen:
        return None
    rerank = output.rerank or {}
    return RelevanceRecord(model=output.result.model_ids.get('screen') or 'jev', scored_at=now(),
                           description_sha256=description_hash(text), scores=output.screen, rerank=rerank,
                           display=display_probabilities(output.screen, rerank),
                           bands=RelevanceBands.model_validate_json(BANDS_FILE.read_text()))


def _event(stage: str, payload: dict) -> str:
    return f'event: {stage}\ndata: {json.dumps(payload, default=str)}\n\n'


def create_router(cases: Callable[[], CaseBackend], code: Callable[[], Codes],
                  transport_factory: TransportFactory | None = None) -> APIRouter:
    router = APIRouter(tags=['code identification'])
    runs = CaseScorings()

    def get_case(case_id: str) -> Case:
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    def save(case_id: str, change: Callable[[Case], object]):
        """Apply `change` to the latest case under the store's optimistic version check."""
        for _ in range(5):
            snapshot = cases().get_snapshot(case_id)
            if snapshot is None:
                raise HTTPException(404, 'case not found')
            case, version = snapshot
            value = change(case)
            try:
                return cases().put(case, expected_version=version), value
            except VersionConflict as error:
                if error.actual is None:
                    raise HTTPException(404, 'case not found') from error
        raise HTTPException(409, 'case was updated concurrently')

    def execute(case_id: str, text: str, outbound: str, client_ip: str, on_stage=None) -> IdentifyResult:
        try:
            config = load_config()
        except (ConfigError, ValueError) as error:
            logger.error('identify config invalid: %s', error)
            raise HTTPException(503, 'Code identification is misconfigured') from None
        codes = code()
        transports = transport_factory(client_ip) if transport_factory else None
        output = identify_run(outbound, codes=codes, config=config, transports=transports, on_stage=on_stage,
                              description_sha256=description_hash(text), client_ip=client_ip,
                              facts=get_case(case_id).facts)
        result = output.result
        relevance = _relevance(output, text)

        def attach(case: Case):
            previous = case.identify.decisions if case.identify else {}
            result.decisions = {k: v for k, v in previous.items() if any(a.provision == k for a in result.articles)}
            if title_should_replace(case.title, text):
                case.title = short_title(text, case.facts, result.model_dump())
            result.title = case.title
            case.identify = result
            if relevance is not None:
                case.relevance = relevance
        saved, _ = save(case_id, attach)
        logger.info('Identify: case=%s mode=%s scored=%s committed=%s choices=%s dropped=%s usd=%.6f seconds=%.3f',
                    case_id, result.mode, result.trace.articles_scored, len(result.committed), len(result.choices),
                    len(result.trace.dropped), result.trace.usd, result.trace.seconds)
        return _current(saved.identify, saved)

    @router.post('/cases/{case_id}/identify', response_model=IdentifyResult,
                 responses={200: {'content': {'text/event-stream': {}}}})
    def identify(case_id: str, request: Request, body: IdentifyRequest | None = None):
        body = body or IdentifyRequest()
        case = get_case(case_id)
        provisions = list(case.provisions)
        if body.answers:
            save(case_id, lambda c: apply_answers(c, body.answers))
            case = get_case(case_id)
        text = body.prose if body.prose and body.prose.strip() else description(case)
        if not text.strip():
            raise HTTPException(409, 'Describe your project first')
        client_ip = client_ip_from(request)
        wait = identify_retry_after(client_ip)
        if wait is not None:
            raise HTTPException(429, f'Identification limit reached; try again in {wait} seconds',
                                headers={'Retry-After': str(wait)})
        user = getattr(request.state, 'user', None)
        outbound = scrub(text, known_values(case, people_names(cases(), case, user)))
        if 'text/event-stream' in request.headers.get('accept', ''):
            return stream(case_id, text, outbound, client_ip)
        try:
            with runs.claim(case_id):
                result = execute(case_id, text, outbound, client_ip)
        except RelevanceInProgress:
            raise HTTPException(409, 'Identification already in progress', headers={'Retry-After': '1'}) from None
        except ProcessRefMissing:
            raise HTTPException(503, 'process references missing from the code database') from None
        if list(get_case(case_id).provisions) != provisions:
            raise HTTPException(500, 'identify must not change provisions')
        return result

    def stream(case_id: str, text: str, outbound: str, client_ip: str) -> StreamingResponse:
        try:
            claim = runs.claim(case_id)
            claim.__enter__()
        except RelevanceInProgress:
            raise HTTPException(409, 'Identification already in progress', headers={'Retry-After': '1'}) from None
        events: queue.Queue = queue.Queue()
        context = contextvars.copy_context()      # the access guard's context, for store write checks

        def worker():
            try:
                result = execute(case_id, text, outbound, client_ip,
                                 on_stage=lambda stage, payload: events.put((stage, payload)))
                events.put(('done', attach_meta(attribute_code(json.loads(result.model_dump_json())))))
            except HTTPException as error:
                events.put(('error', {'message': str(error.detail), 'status': error.status_code}))
            except Exception as error:
                logger.warning('Identify stream failed: %s', type(error).__name__)
                events.put(('error', {'message': 'Identification failed', 'status': 503}))
            finally:
                claim.__exit__(None, None, None)
                events.put(None)

        threading.Thread(target=lambda: context.run(worker), daemon=True).start()

        def generate():
            yield _event('start', {'stage': 'start'})
            while (item := events.get()) is not None:
                yield _event(*item)

        return StreamingResponse(generate(), media_type='text/event-stream',
                                 headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})

    @router.get('/cases/{case_id}/identify', response_model=IdentifyResult)
    def identify_stored(case_id: str, response: Response):
        """The last identification for this case, with decisions and staleness. Never calls a provider."""
        response.headers['Cache-Control'] = 'no-store'
        case = get_case(case_id)
        if case.identify is None:
            raise HTTPException(404, 'identify result not found')
        return _current(case.identify, case)

    @router.post('/cases/{case_id}/identify/confirm', response_model=Case)
    def confirm(case_id: str, body: IdentifyConfirmRequest):
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

        def write(case: Case):
            case.provisions = list(dict.fromkeys(body.provisions))
            case.section_c = section_c_rows(case.provisions, codes)
        saved, _ = save(case_id, write)
        return saved

    @router.post('/cases/{case_id}/identify/{provision_id}/decision', response_model=IdentifyResult)
    def decide(case_id: str, provision_id: str, body: IdentifyDecisionRequest):
        """Record the applicant's decision. `yes` adds the article to provisions and Section C."""
        if get_case(case_id).identify is None:
            raise HTTPException(404, 'identify result not found')
        codes = code()

        def write(case: Case):
            return record_decision(case, provision_id, body.decision, codes)
        try:
            saved, _ = save(case_id, write)
        except KeyError:
            raise HTTPException(404, 'provision not found in this identification') from None
        return _current(saved.identify, saved)

    @router.post('/cases/{case_id}/identify/benchmark', response_model=IdentifyResult)
    def confirm_benchmark(case_id: str, body: BenchmarkConfirmRequest):
        """The applicant's benchmark acceptable solution: a codedb Division B sentence or article, plus their
        one-line departure. The sentence and the objective and function codes are looked up, never typed."""
        from .identify import cards
        if get_case(case_id).identify is None:
            raise HTTPException(404, 'identify result not found')
        codes = code()
        try:
            record = codes.provision(body.provision, 'B')
        except ValueError as exc:
            raise HTTPException(400, f'invalid provision id: {exc}') from exc
        if record is None or record.get('level') not in {'article', 'sentence'}:
            raise HTTPException(404, 'provision not found in Division B')
        reason = cards.model_reason(body.departure)
        if reason is None:
            raise HTTPException(422, 'Describe how the design differs; do not state that it complies or is safe')
        objectives, functions, missing = cards.terms(codes, record['id'])

        def write(case: Case):
            bench = case.identify.benchmark
            bench.identified, bench.basis = True, 'applicant'
            bench.provision = record.get('article') or record['id']
            bench.provision_id = record['id'] if record.get('level') == 'sentence' else None
            bench.citation, bench.sentence = record.get('citation'), cards.flat(record.get('text'))
            bench.departure, bench.departure_status = reason, 'confirmed'
            bench.objectives, bench.functions, bench.attribution_missing = objectives, functions, missing
            bench.question = None
        saved, _ = save(case_id, write)
        return _current(saved.identify, saved)

    @router.get('/cases/{case_id}/information-request')
    def officer_information_request(case_id: str):
        """Draft of what the officer still needs to ask: the applicant's not_sure identify decisions."""
        return information_request(get_case(case_id))

    @router.get('/cases/{case_id}/process-refs', response_model=list[ProcessRef])
    def case_process_refs(case_id: str):
        get_case(case_id)
        try:
            return process_refs(code())
        except ProcessRefMissing:
            raise HTTPException(503, 'process references missing from the code database') from None

    return router

