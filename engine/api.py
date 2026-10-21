"""HTTP interface for the engine. Run: uvicorn engine.api:app --reload"""
from __future__ import annotations

import logging
import os
import re
import secrets
from email import policy
from email.message import Message
from email.parser import BytesParser
from typing import Callable

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from codedb import AmbiguousProvisionError

from .code_library import CodeTOC, ProvisionContext, provision_context, table_of_contents
from .codes import CodeDbMissing, Codes
from .export import (EXPORT_FAILED_DETAIL, ExportBlocked, ExportError, FORM_NOT_FOUND_DETAIL, FormNotFound,
                     export_case)
from .http_guard import HttpGuard
from .jurisdictions import export_notice
from .identify import Judge
from .llm_gate import client_ip_from, search_retry_after
from .models import Case, Fact, Jurisdiction, SectionCRow
from .retention import maybe_purge
from .section_c import section_c_rows
from .store import CaseStore, FileTooLarge, InvalidAttachment, VersionConflict, assert_durable_when_hosted, open_store
from .uploads import (MULTIPART_MAX_OVERHEAD_BYTES, MULTIPART_MAX_PARTS,
                      PDF_MAX_BYTES, PDF_TOO_LARGE_DETAIL)
from .access import access_dependency
from .account_models import Authority, reviewing_authority

logger = logging.getLogger(__name__)


class NewCase(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    jurisdiction: Jurisdiction | None = None
    authority: Authority | None = None


class SectionCRequest(BaseModel):
    provisions: list[str]


class ExportRequest(BaseModel):
    draft: bool = False


async def read_capped(request: Request, limit: int = PDF_MAX_BYTES) -> bytes:
    """Reject a declared Content-Length over the cap, then stop reading once the cap is passed."""
    declared = request.headers.get('content-length')
    if declared is not None and declared.strip() != '':
        try:
            announced = int(declared)
        except ValueError as exc:
            raise HTTPException(400, 'invalid Content-Length') from exc
        if announced > limit:
            raise HTTPException(413, PDF_TOO_LARGE_DETAIL)
    buf = bytearray()
    async for chunk in request.stream():
        if len(buf) + len(chunk) > limit:
            raise HTTPException(413, PDF_TOO_LARGE_DETAIL)
        buf += chunk
    return bytes(buf)


def _pdf_from_body(body: bytes, content_type: str, filename: str | None) -> tuple[str, bytes]:
    if content_type.split(';', 1)[0].strip().lower() != 'multipart/form-data':
        return filename or 'upload.pdf', body
    if len(body) > PDF_MAX_BYTES + MULTIPART_MAX_OVERHEAD_BYTES:
        raise HTTPException(413, PDF_TOO_LARGE_DETAIL)
    try:
        header = Message(policy=policy.default)
        header['Content-Type'] = content_type
        boundary = header.get_boundary()
        if not boundary:
            raise HTTPException(400, 'multipart body is missing a boundary')
        boundary_bytes = boundary.encode('ascii')
        if not re.fullmatch(rb"[0-9A-Za-z'()+_,./:=? -]{0,69}[0-9A-Za-z'()+_,./:=?-]", boundary_bytes):
            raise ValueError('invalid boundary')
        # Bound the number of parts before the MIME parser allocates their objects.
        delimiter = re.compile(rb'(?:\A|(?<=[\r\n]))--' + re.escape(boundary_bytes) +
                               rb'(?:--)?[ \t]*(?:\r\n|\r|\n|\Z)')
        if sum(1 for _ in delimiter.finditer(body)) > MULTIPART_MAX_PARTS + 1:
            raise HTTPException(400, 'multipart body has too many parts')
        message = BytesParser(policy=policy.default.clone(raise_on_defect=True)).parsebytes(
            b'Content-Type: ' + content_type.encode('latin1') + b'\r\nMIME-Version: 1.0\r\n\r\n' + body)
        if not message.is_multipart():
            raise ValueError('missing multipart framing')
        files = []
        for part in message.iter_parts():
            if part.is_multipart() or any(getattr(value, 'defects', ()) for value in part.values()):
                raise ValueError('invalid multipart part')
            if len(part.get_all('Content-Disposition', [])) != 1:
                raise ValueError('missing or ambiguous disposition')
            if part.get_content_disposition() == 'form-data' and part.get_filename() is not None:
                files.append(part)
        if len(files) != 1:
            raise HTTPException(400, 'multipart body must contain exactly one file')
        part = files[0]
        data = part.get_payload(decode=True)
        if data is None:
            raise ValueError('missing file payload')
        if len(data) > PDF_MAX_BYTES or len(body) - len(data) > MULTIPART_MAX_OVERHEAD_BYTES:
            raise HTTPException(413, PDF_TOO_LARGE_DETAIL)
        return part.get_filename() or filename or 'upload.pdf', data
    except (ValueError, RecursionError) as error:
        raise HTTPException(400, 'invalid multipart body') from error


def create_app(store: CaseStore | None = None, codes: Codes | None = None, *,
               relevance_judge_factory: Callable[[], Judge] | None = None) -> FastAPI:
    if store is None:
        assert_durable_when_hosted()
    state = {'store': store, 'codes': codes}

    def cases() -> CaseStore:
        if state['store'] is None:
            state['store'] = open_store()
        return state['store']

    app = FastAPI(title='Batatis engine', dependencies=[Depends(access_dependency(cases))])

    def sweep():
        current = state['store']
        if current is not None and getattr(current, 'purge_expired', None):
            maybe_purge(current)

    app.add_middleware(CORSMiddleware, allow_origin_regex=r'http://(localhost|127\.0\.0\.1)(:\d+)?',
                       allow_origins=[os.environ.get('BATATIS_WEB_ORIGIN', 'http://localhost:5480').rstrip('/')],
                       allow_credentials=True, allow_methods=['*'], allow_headers=['*'],
                       expose_headers=['Retry-After', 'X-Batatis-Notice', 'X-Batatis-Jurisdiction-Notice',
                                       'Content-Disposition'])
    app.add_middleware(HttpGuard, sweep=sweep)

    def code() -> Codes:
        if state['codes'] is None:
            try:
                state['codes'] = Codes()
            except (CodeDbMissing, FileNotFoundError):
                # Fixed detail. The body has no filesystem path.
                raise HTTPException(503, 'code database not found') from None
        return state['codes']

    def purge_cases(*, force: bool = False) -> int:
        current = cases()
        try:
            return current.purge_expired() if force else maybe_purge(current)
        except Exception as exc:
            logger.warning('case purge failed: %s', type(exc).__name__)
            raise HTTPException(503, 'case purge failed', headers={'Cache-Control': 'no-store'}) from None

    @app.post('/cases', response_model=Case, status_code=201)
    def create_case(request: Request, body: NewCase | None = None):
        purge_cases()
        case = Case(**(body.model_dump() if body else {}))
        user = request.state.user
        if user:
            case.owner_id = user.id
            case.authority = case.authority or reviewing_authority(case.jurisdiction.id if case.jurisdiction else None)
        return cases().put(case)

    @app.get('/retention/purge')
    def retention_purge(request: Request, response: Response):
        """The daily Vercel cron authenticates before an unthrottled purge."""
        secret = os.environ.get('CRON_SECRET') or ''
        private_headers = {'Cache-Control': 'no-store'}
        if not secret and os.environ.get('VERCEL'):
            raise HTTPException(503, 'retention purge not configured', headers=private_headers)
        if secret:
            authorization = request.headers.get('authorization', '').encode('utf-8')
            expected = ('Bearer ' + secret).encode('utf-8')
            if not secrets.compare_digest(authorization, expected):
                raise HTTPException(401, 'unauthorized',
                                    headers={**private_headers, 'WWW-Authenticate': 'Bearer'})
        response.headers['Cache-Control'] = 'no-store'
        return {'deleted': purge_cases(force=True)}

    @app.get('/cases/{case_id}', response_model=Case)
    def get_case(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @app.post('/cases/{case_id}/facts', response_model=Case)
    def add_fact(case_id: str, fact: Fact):
        if fact.source.type not in {'user_text', 'user_click', 'file', 'drawing'}:
            raise HTTPException(422, 'public fact input cannot assert officer, professional, or code authority')
        try:
            case = cases().add_fact(case_id, fact)
        except InvalidAttachment as exc:
            raise HTTPException(422, str(exc)) from exc
        except VersionConflict as exc:
            raise HTTPException(409, 'case was updated concurrently') from exc
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @app.post('/cases/{case_id}/files', status_code=201)
    async def upload_file(case_id: str, request: Request):
        if cases().get(case_id) is None:
            raise HTTPException(404, 'case not found')
        content_type = request.headers.get('content-type', '')
        multipart = content_type.split(';', 1)[0].strip().lower() == 'multipart/form-data'
        limit = PDF_MAX_BYTES + (MULTIPART_MAX_OVERHEAD_BYTES if multipart else 0)
        body = await read_capped(request, limit)
        name, data = _pdf_from_body(body, content_type,
                                    request.headers.get('x-filename'))
        if len(data) > PDF_MAX_BYTES:
            raise HTTPException(413, PDF_TOO_LARGE_DETAIL)
        if not data.startswith(b'%PDF'):
            raise HTTPException(415, 'only PDF files are accepted')
        try:
            saved = cases().put_file(case_id, name, data)
        except FileTooLarge as exc:
            raise HTTPException(413, exc.detail) from exc
        if saved is None:
            raise HTTPException(404, 'case not found')
        return {key: saved[key] for key in ('id', 'name', 'size', 'content_type')}

    @app.delete('/cases/{case_id}', status_code=204)
    def delete_case(case_id: str):
        if not cases().delete(case_id):
            raise HTTPException(404, 'case not found')
        return Response(status_code=204)

    @app.post('/cases/{case_id}/export', response_class=Response,
              responses={200: {'content': {'application/pdf': {}}}, 409: {'description': 'export blocked'}})
    def export(case_id: str, body: ExportRequest | None = None):
        case = get_case(case_id)
        draft = bool(body and body.draft)
        try:
            res = export_case(case, draft=draft, codes=code())
        except ExportBlocked as e:
            raise HTTPException(409, {'message': 'export blocked; resolve these or export a draft', 'reasons': e.reasons})
        except FormNotFound as exc:
            logger.error('PDF export is unavailable on this deployment: %s', exc)
            raise HTTPException(503, FORM_NOT_FOUND_DETAIL) from None
        except ExportError as exc:
            logger.error('%s %s', EXPORT_FAILED_DETAIL, exc)
            raise HTTPException(500, EXPORT_FAILED_DETAIL) from None
        name = f'{case_id}-scc-variance{"-DRAFT" if draft else ""}.pdf'
        headers = {'Content-Disposition': f'attachment; filename="{name}"'}
        notice = export_notice(case)   # from the case's jurisdiction pack; never a block
        if notice:
            # Its own header, so the standard privacy notice in X-Batatis-Notice is kept.
            headers['X-Batatis-Jurisdiction-Notice'] = notice
        return Response(res.pdf, media_type='application/pdf', headers=headers)

    @app.get('/code/search')
    def code_search(request: Request, q: str, division: str | None = Query('B', pattern='^[ABC]$'),
                    limit: int = Query(20, ge=1)):
        if limit > 20:
            raise HTTPException(422, 'The maximum is 20.')
        wait = search_retry_after(client_ip_from(request))
        if wait is not None:
            raise HTTPException(429, f'Search limit reached; try again in {wait} seconds',
                                headers={'Retry-After': str(wait)})
        return code().search(q, division=division, limit=limit)

    @app.get('/code/toc', response_model=CodeTOC)
    def code_toc(division: str = Query('B')):
        if division not in ('A', 'B', 'C'):
            raise HTTPException(400, 'invalid division')
        return table_of_contents(code().db_path, division)

    def lookup_code(provision_id: str, request: Request, division: str | None):
        extra = set(request.query_params) - {'division'}
        if extra:
            raise HTTPException(400, 'this route accepts only division')
        try:
            rec = code().provision(provision_id, division)
        except AmbiguousProvisionError as e:
            raise HTTPException(400, str(e))
        except ValueError as e:
            raise HTTPException(400, f'invalid provision id: {e}')
        if rec is None:
            raise HTTPException(404, 'provision not found')
        return rec

    @app.get('/code/{provision_id}/context', response_model=ProvisionContext)
    def code_context(provision_id: str, request: Request, division: str = Query('B', pattern='^[ABC]$')):
        return provision_context(lookup_code(provision_id, request, division), code())

    @app.get('/code/{provision_id}')
    def code_lookup(provision_id: str, request: Request, division: str | None = Query(None, pattern='^[ABC]$')):
        return lookup_code(provision_id, request, division)

    @app.post('/section-c', response_model=list[SectionCRow])
    def section_c(body: SectionCRequest):
        try:
            return section_c_rows(body.provisions, code())
        except KeyError as e:
            raise HTTPException(404, e.args[0])
        except ValueError as e:
            raise HTTPException(400, f'invalid provision id: {e}')

    @app.exception_handler(CodeDbMissing)
    def missing_codedb(_request, _exc: CodeDbMissing):
        # Not FileNotFoundError. The body is fixed and carries no filesystem path.
        return JSONResponse(status_code=503, content={'detail': 'code database not found'})

    @app.exception_handler(psycopg.OperationalError)
    def store_unreachable(_request, _exc: psycopg.OperationalError):
        # The exception text can name the host. The response does not.
        return JSONResponse(status_code=503, content={'detail': 'case store unavailable'})

    app.include_router(__import__('engine.routes_case', fromlist=['create_router']).create_router(cases, code))
    app.include_router(__import__('engine.routes_evidence', fromlist=['create_router']).create_router(cases, code))
    app.include_router(__import__('engine.routes_auth', fromlist=['create_router']).create_router(cases))
    app.include_router(__import__('engine.routes_review', fromlist=['create_router']).create_router(cases, code))
    app.include_router(__import__('engine.routes_assist', fromlist=['create_router']).create_router(cases, code))
    app.include_router(__import__('engine.routes_intake', fromlist=['create_router']).create_router(cases, code))
    app.include_router(__import__('engine.routes_relevance', fromlist=['create_router']).create_router(
        cases, code, relevance_judge_factory))
    app.include_router(__import__('engine.routes_jurisdictions', fromlist=['create_router']).create_router(cases))
    return app


app = create_app()
