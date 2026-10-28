"""Code identification routes. Extracted from PR #12's routes_case.py and rebuilt on dev's gate and guard.

POST /cases/{id}/identify            explicit run (JSON, or SSE stage events with Accept: text/event-stream)
GET  /cases/{id}/identify            the stored result; never calls a provider
POST /cases/{id}/identify/{provision}/decision   yes | no | not_sure
POST /cases/{id}/identify/confirm    write provisions after a code-database check
POST /cases/{id}/identify/benchmark  the applicant names the benchmark sentence and confirms the departure
GET  /cases/{id}/identify/information-request the officer draft of not_sure items
GET  /cases/{id}/process-refs        Div A 1.2.1.1. and Div C 2.3.1.1., read-only, from codedb

Writes are owner edits (engine/access.py: POST is mode `edit`), so reviewers are read-only. Every write is
one compare-and-swap against the case version it read (docs/api-contract.md): a concurrent write is a 409,
never a retry. Client writes accept `expected_version` (as `POST /cases/{id}/section-d` does); a supplied
version that is not the stored one is a 409. Responses carry `case_version` for the next write. Outbound
text is redacted with engine/redact.py exactly as routes_relevance.py does. Identify never changes
provisions; only a `yes` decision or confirm does.
"""
from __future__ import annotations

import contextvars
import json
import logging
import queue
import threading
import time
from typing import Callable

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, TypeAdapter

from .codes import Codes
from .copyright import attach_meta, attribute_code
from .identify.answers import AnswerRejected, apply_answers, check_answers
from .identify.config import ConfigError, load_config
from .identify.case_input import active_facts, compose, fingerprint, is_requirement_run, refresh as refresh_identification
from .identify.decisions import information_request, overlay_decisions, record_decision
from .identify.http_models import (BenchmarkConfirmRequest, IdentifyConfirmRequest, IdentifyDecisionRequest,
                                   IdentifyDecisionResponse, IdentifyRequest, RequirementDecisionRequest)
from .identify.pipeline import RunOutput, description_hash, run as identify_run
from .identify.providers import Transports
from .identify.title import short_title, title_should_replace
from .llm_gate import client_ip_from, identify_retry_after
from .models import Case, Fact, now
from .models_identify import IdentifyResult, ProcessRef
from .models_jobs import Job
from .process_refs import ProcessRefMissing, process_refs
from .public_names import public_event
from .redact import known_values, people_names, scrub
from .relevance import CaseScorings, RelevanceInProgress, description, display_probabilities, scoring_bands
from .relevance_models import RelevanceRecord
from .section_c import section_c_rows
from .store import CaseBackend, VersionConflict

logger = logging.getLogger(__name__)
TransportFactory = Callable[[str | None], Transports]


def _require_source(codes: Codes):
    from .identify.requirement_corpus import load, SourceUnavailable
    try:
        return load(codes.db_path).source
    except SourceUnavailable:
        raise HTTPException(503, 'NBC(AE) 2023 second-printing source could not be verified') from None


def _current(result: IdentifyResult, case: Case, store=None, code_reader=None) -> IdentifyResult:
    out = result.model_copy(deep=True)
    out.stale = (out.input_sha256 != fingerprint(case, store) if getattr(out, 'input_sha256', None)
                 else out.description_sha256 != description_hash(description(case)))
    if is_requirement_run(out) and code_reader is not None:
        try:
            out.stale = out.stale or _require_source(code_reader()) != out.requirement_coverage.source
        except HTTPException:
            out.stale = True
    out.persisted = True
    out.case_version = case.version
    if case.title_is_manual:
        out.title = None
    # A `yes` stands only while the article is still a case provision: a reference withdrawal
    # (POST /cases/{id}/section-d) clears provisions and citation.* facts without touching this record.
    kept = {p.split('(')[0] for p in case.provisions}
    out.decisions = {k: v for k, v in out.decisions.items() if v.decision != 'yes' or k in kept}
    for item in out.requirements:
        if item.role == 'varied' and item.provision_id not in kept:
            item.applicability, item.disposition, item.needs_review = 'needs_review', 'review', True
    return overlay_decisions(out)


def _relevance(output: RunOutput, text: str) -> RelevanceRecord | None:
    """The same rings as POST /relevance: the identify run's screen and rerank, stored on the case."""
    if not output.screen:
        return None
    rerank = output.rerank or {}
    models = {stage: pin for stage, pin in output.result.model_ids.items() if stage != 'verifier'}
    model = models['screen']
    return RelevanceRecord(model=model, config_hash=output.result.trace.config_hash, model_ids=models,
                           scored_at=now(), description_sha256=description_hash(text), scores=output.screen,
                           rerank=rerank,
                           display=display_probabilities(output.screen, rerank),
                           bands=scoring_bands(model, models, output.result.trace.config_hash))


def _event(stage: str, payload: dict) -> str:
    return f'event: {stage}\ndata: {json.dumps(payload, default=str)}\n\n'


class IdentifyComputation(BaseModel):
    result: IdentifyResult
    relevance: RelevanceRecord | None
    text: str
    naming_prose: str
    # The facts the run consumed and fingerprinted, with the request's answers staged on them.
    staged_facts: list[Fact] | None = None


def _identify_input(case: Case, body: IdentifyRequest, store=None, *, require_text: bool = True):
    if body.answers:
        try:
            check_answers(case, body.answers)
        except AnswerRejected as error:
            raise HTTPException(422, str(error)) from None
        # Staged on a copy: they are written with the result, in the same write, or not at all.
        case = case.model_copy(deep=True)
        apply_answers(case, body.answers)
    naming_prose = body.prose if body.prose and body.prose.strip() else ''
    text = naming_prose or description(case)
    if require_text and not text.strip() and not compose(case, store).text.strip():
        raise HTTPException(409, 'Describe your project or attach readable plans first')
    return case, text, naming_prose


def _uses_model() -> bool:
    try:
        return load_config().screen != 'requirements'
    except (ConfigError, ValueError):
        return True


def _compute_identification(base: Case, text: str, outbound: str, client_ip: str, code: Callable,
                            transport_factory, store, on_stage=None, *, naming_prose: str = '',
                            answers=(), user=None) -> IdentifyComputation:
    try:
        config = load_config()
    except (ConfigError, ValueError) as error:
        logger.error('identify config invalid: %s', error)
        raise HTTPException(503, 'Code identification is misconfigured') from None
    codes = code()
    requirements = config.screen == 'requirements'
    if not requirements:
        _require_source(codes)
    started = time.monotonic()
    context = compose(base, store, prose=naming_prose or None) if requirements else None
    if context is not None:
        outbound = scrub(context.text, known_values(base, people_names(store, base, user)))
    transports = transport_factory(client_ip) if transport_factory and not requirements else None
    extra = {'previous': base.identify, 'confirmed_provisions': base.provisions} if requirements else {}
    input_seconds = time.monotonic() - started
    output = identify_run(outbound, codes=codes, config=config, transports=transports, on_stage=on_stage,
                          description_sha256=description_hash(text), client_ip=client_ip,
                          facts=active_facts(base) if context is not None else base.facts, **extra)
    result = output.result
    if context is not None:
        result.trace.seconds = round(result.trace.seconds + input_seconds, 3)
        result.input_sha256 = context.sha256
        result.input_coverage_gaps = list(context.gaps)
    return IdentifyComputation(result=result, relevance=_relevance(output, text), text=text,
                               naming_prose=naming_prose,
                               staged_facts=[fact.model_copy(deep=True) for fact in base.facts] if answers else None)


def _apply_identification(case: Case, output: IdentifyComputation):
    if output.staged_facts is not None:
        # Keep the same fact ids that the run consumed and fingerprinted. The write is pinned
        # to the facts the run read (CAS version, or the job's read-field fingerprint).
        case.facts = [fact.model_copy(deep=True) for fact in output.staged_facts]
    result = output.result.model_copy(deep=True)
    previous = case.identify.decisions if case.identify else {}
    result.decisions = (dict(previous) if is_requirement_run(result) else
                        {k: v for k, v in previous.items() if any(a.provision == k for a in result.articles)})
    generated = case.identify.title if case.identify else None
    if title_should_replace(case.title, output.text, generated, manual=case.title_is_manual):
        # `text` may be an unconfirmed saved description. Only explicit sent
        # prose and the helper's confirmed applicant facts are naming inputs.
        case.title = short_title(output.naming_prose, case.facts, result.model_dump())
        result.title = case.title
    else:
        result.title = generated if not case.title_is_manual and case.title == generated else None
    case.identify = result
    if output.relevance is not None:
        case.relevance = output.relevance


def create_job_handler(code: Callable[[], Codes], transport_factory: TransportFactory | None = None):
    from .jobs import JobHandler

    def validate(case, body):
        # Attachments live outside the case; compute checks for readable input with the store.
        _identify_input(case, body, require_text=False)

    def compute(case, body, context):
        base, text, naming_prose = _identify_input(case, body, context.store)
        outbound = scrub(text, known_values(base, people_names(context.store, base, context.user)))
        context.progress('screen')
        next_stage = {'screen': 'rerank', 'rerank': 'verify', 'verify': 'questions', 'questions': 'questions'}
        # Applying does no I/O, so attachments changed during the run are not rejected here as the
        # direct route does; the stored result's input fingerprint then reports it as stale.
        return _compute_identification(
            base, text, outbound, context.client_key, code, transport_factory, context.store,
            on_stage=lambda stage, payload: context.progress(next_stage[stage]), naming_prose=naming_prose,
            answers=body.answers, user=context.user)

    return JobHandler(kind='identify', revision='identify.v1', request_model=IdentifyRequest,
                      result_adapter=TypeAdapter(IdentifyComputation),
                      read_fields=('facts', 'identify', 'title', 'title_is_manual', 'provisions', 'relevance', 'jurisdiction'),
                      write_fields=('facts', 'identify', 'title', 'relevance'),
                      stages=('screen', 'rerank', 'verify', 'questions'), compute=compute,
                      apply=lambda case, body, output: _apply_identification(case, output),
                      validate_input=validate, result_path='/identify', uses_ai=lambda body: _uses_model())


def create_router(cases: Callable[[], CaseBackend], code: Callable[[], Codes],
                  transport_factory: TransportFactory | None = None, *, jobs: Callable | None = None) -> APIRouter:
    from .jobs import JobRegistry, JobRuntime, schedule_hosted_drain
    router = APIRouter(tags=['code identification'])
    runs = CaseScorings()
    local_runtime = []

    def runtime():
        if jobs is not None:
            return jobs()
        if not local_runtime:
            registry = JobRegistry()
            registry.register(create_job_handler(code, transport_factory))
            local_runtime.append(JobRuntime(cases(), registry))
        return local_runtime[0]

    def get_case(case_id: str) -> Case:
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    def save(case_id: str, change: Callable[[Case], object], expected_version: int | None = None):
        """One compare-and-swap: apply `change` to the snapshot and write it against that snapshot's version.

        `expected_version` (from the client, or the version a run started from) must equal the stored version.
        A conflict is a 409; the change is never re-applied to a newer case.
        """
        snapshot = cases().get_snapshot(case_id)
        if snapshot is None:
            raise HTTPException(404, 'case not found')
        case, version = snapshot
        if expected_version is not None and expected_version != version:
            raise HTTPException(409, 'case was updated concurrently')
        value = change(case)
        try:
            return cases().put(case, expected_version=version), value
        except VersionConflict as error:
            if error.actual is None:
                raise HTTPException(404, 'case not found') from error
            raise HTTPException(409, 'case was updated concurrently') from error

    def execute(case_id: str, text: str, outbound: str, client_ip: str, base: Case,
                on_stage=None, answers=(), *, naming_prose: str = '') -> IdentifyResult:
        """Run identification and store it, with the request's answers, in one CAS against `base`."""
        output = _compute_identification(base, text, outbound, client_ip, code, transport_factory, cases(), on_stage,
                                         naming_prose=naming_prose, answers=answers)
        result = output.result

        def attach(case: Case):
            if result.input_sha256 and fingerprint(base, cases()) != result.input_sha256:
                raise HTTPException(409, 'identification source attachments changed')
            _apply_identification(case, output)
        saved, _ = save(case_id, attach, expected_version=base.version)
        if list(saved.provisions) != list(base.provisions):   # the CAS pinned `base`; `attach` never touches provisions
            raise HTTPException(500, 'identify must not change provisions')
        logger.info('Identify: case=%s mode=%s scored=%s committed=%s choices=%s dropped=%s usd=%s seconds=%.3f',
                    case_id, result.mode, result.trace.articles_scored, len(result.committed), len(result.choices),
                    len(result.trace.dropped), result.trace.usd, result.trace.seconds)
        return _current(saved.identify, saved, cases(), code)

    @router.post('/cases/{case_id}/identify', response_model=IdentifyResult,
                 responses={200: {'content': {'text/event-stream': {}}}})
    def identify(case_id: str, request: Request, body: IdentifyRequest | None = None):
        body = body or IdentifyRequest()
        case = get_case(case_id)
        if body.expected_version is not None and body.expected_version != case.version:
            raise HTTPException(409, 'case was updated concurrently')
        case, text, naming_prose = _identify_input(case, body, cases())
        client_ip = client_ip_from(request)
        wait = identify_retry_after(client_ip)
        if wait is not None:
            raise HTTPException(429, f'Identification limit reached; try again in {wait} seconds',
                                headers={'Retry-After': str(wait)})
        user = getattr(request.state, 'user', None)
        outbound = scrub(text, known_values(case, people_names(cases(), case, user)))
        if 'text/event-stream' in request.headers.get('accept', ''):
            return stream(case_id, text, outbound, client_ip, case, body.answers, naming_prose=naming_prose)
        try:
            with runs.claim(case_id):
                result = execute(case_id, text, outbound, client_ip, case, answers=body.answers,
                                 naming_prose=naming_prose)
        except RelevanceInProgress:
            raise HTTPException(409, 'Identification already in progress', headers={'Retry-After': '1'}) from None
        except ProcessRefMissing:
            raise HTTPException(503, 'process references missing from the code database') from None
        return result

    @router.post('/cases/{case_id}/identify/jobs', response_model=Job, status_code=202)
    def start_identify(case_id: str, request: Request, response: Response, background: BackgroundTasks,
                       body: IdentifyRequest | None = None,
                       idempotency_key: str | None = Header(default=None, alias='Idempotency-Key')):
        client_ip = client_ip_from(request)

        def admit():
            wait = identify_retry_after(client_ip)
            if wait is not None:
                raise HTTPException(429, f'Identification limit reached; try again in {wait} seconds',
                                    headers={'Retry-After': str(wait)})

        host = runtime()
        job = host.enqueue(case_id, 'identify', body or IdentifyRequest(), getattr(request.state, 'user', None),
                           idempotency_key=idempotency_key, client_ip=client_ip, admit=admit)
        schedule_hosted_drain(background.add_task, host)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Location'] = f'/cases/{case_id}/jobs/{job.id}'
        return job

    def stream(case_id: str, text: str, outbound: str, client_ip: str, base: Case, answers=(), *,
               naming_prose: str = '') -> StreamingResponse:
        try:
            claim = runs.claim(case_id)
            claim.__enter__()
        except RelevanceInProgress:
            raise HTTPException(409, 'Identification already in progress', headers={'Retry-After': '1'}) from None
        events: queue.Queue = queue.Queue()
        context = contextvars.copy_context()      # the access guard's context, for store write checks

        def worker():
            try:
                result = execute(case_id, text, outbound, client_ip, base, answers=answers, naming_prose=naming_prose,
                                 on_stage=lambda stage, payload: events.put((stage, public_event(payload))))
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
        return _current(case.identify, case, cases(), code)

    @router.post('/cases/{case_id}/identify/confirm', response_model=Case)
    def confirm(case_id: str, body: IdentifyConfirmRequest):
        codes = code()
        _require_source(codes)
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
            refresh_identification(case, cases(), codes, force=True)
        try:
            saved, _ = save(case_id, write, expected_version=body.expected_version)
        except KeyError as error:   # a section or subsection id: pass an article, sentence or clause
            raise HTTPException(404, {'message': 'pass an article, sentence or clause', 'detail': str(error.args[0])}) from None
        return saved

    @router.post('/cases/{case_id}/identify/{provision_id}/decision', response_model=IdentifyDecisionResponse)
    def decide(case_id: str, provision_id: str, body: IdentifyDecisionRequest):
        """Record the applicant's decision. `yes` adds the article to provisions and Section C."""
        if get_case(case_id).identify is None:
            raise HTTPException(404, 'identify result not found')
        codes = code()
        _require_source(codes)

        def write(case: Case):
            return record_decision(case, provision_id, body.decision, codes)
        try:
            saved, written = save(case_id, write, expected_version=body.expected_version)
        except KeyError:
            raise HTTPException(404, 'provision not found in this identification') from None
        # `section_c`: the rows a `yes` wrote for this article (empty for no and not_sure).
        return IdentifyDecisionResponse(**_current(saved.identify, saved, cases(), code).model_dump(), section_c=written)

    @router.post('/cases/{case_id}/identify/benchmark', response_model=IdentifyDecisionResponse)
    def confirm_benchmark(case_id: str, body: BenchmarkConfirmRequest):
        """The applicant's benchmark acceptable solution: a codedb Division B sentence or article, plus their
        one-line departure. The sentence and the objective and function codes are looked up, never typed."""
        from .identify import cards
        if get_case(case_id).identify is None:
            raise HTTPException(404, 'identify result not found')
        codes = code()
        _require_source(codes)
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
            from .identify.decisions import record_departure
            return record_departure(case, record['id'], codes, reason=reason)

        saved, written = save(case_id, write, expected_version=body.expected_version)
        return IdentifyDecisionResponse(**_current(saved.identify, saved, cases(), code).model_dump(), section_c=written)

    @router.post('/cases/{case_id}/identify/requirements/{requirement_id}/decision', response_model=IdentifyResult)
    def decide_requirement(case_id: str, requirement_id: str, body: RequirementDecisionRequest):
        """Confirm application scope without treating “no departure” as “irrelevant”."""
        from .identify.requirement_decisions import record

        def write(case: Case):
            if case.identify is None:
                raise HTTPException(404, 'identify result not found')
            if _current(case.identify, case, cases(), code).stale:
                raise HTTPException(409, 'Identification inputs changed; rerun before confirming applicability')
            try:
                record(case.identify, requirement_id, body, code())
            except KeyError:
                raise HTTPException(404, 'requirement not found') from None
            except ValueError as error:
                raise HTTPException(422, str(error)) from None
        saved, _ = save(case_id, write, expected_version=body.expected_version)
        return _current(saved.identify, saved, cases(), code)

    @router.get('/cases/{case_id}/identify/information-request')
    def officer_information_request(case_id: str):
        """Saved contextual questions for officer review, plus the legacy not_sure decision items."""
        from .review_questions import review_questions
        case = get_case(case_id)
        return {**information_request(case), 'case_version': case.version, 'questions': review_questions(case)}

    @router.get('/cases/{case_id}/process-refs', response_model=list[ProcessRef])
    def case_process_refs(case_id: str):
        get_case(case_id)
        try:
            codes = code()
            _require_source(codes)
            return process_refs(codes)
        except ProcessRefMissing:
            raise HTTPException(503, 'process references missing from the code database') from None

    return router

