"""HTTP interface for the engine. Run: uvicorn engine.api:app --reload"""
from __future__ import annotations

import logging
import os
import secrets

import psycopg
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from codedb import AmbiguousProvisionError

from .codes import CodeDbMissing, Codes
from .export import (EXPORT_FAILED_DETAIL, ExportBlocked, ExportError, FORM_NOT_FOUND_DETAIL, FormNotFound,
                     export_case)
from .http_guard import HttpGuard
from .llm_gate import client_ip_from, search_retry_after
from .models import Case, Fact, Jurisdiction, SectionCRow
from .retention import maybe_purge
from .section_c import section_c_rows
from .store import CaseStore, FileTooLarge, VersionConflict, assert_durable_when_hosted, open_store
from .uploads import PDF_MAX_BYTES, PDF_TOO_LARGE_DETAIL

logger = logging.getLogger(__name__)


class NewCase(BaseModel):
    title: str | None = None
    jurisdiction: Jurisdiction | None = None


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
    if 'multipart/form-data' not in content_type.lower():
        return filename or 'upload.pdf', body
    marker = content_type.lower().split('boundary=', 1)
    if len(marker) != 2:
        raise HTTPException(400, 'multipart body is missing a boundary')
    boundary = marker[1].split(';', 1)[0].strip().strip('"').encode()
    for part in body.split(b'--' + boundary):
        if b'Content-Disposition' not in part:
            continue
        header, _, payload = part.partition(b'\r\n\r\n')
        if payload.endswith(b'\r\n'):
            payload = payload[:-2]
        if not payload:
            continue
        name = filename or 'upload.pdf'
        for line in header.decode('latin1').split('\r\n'):
            if 'filename=' in line:
                name = line.split('filename=', 1)[1].strip().strip('"') or name
        return name, payload
    raise HTTPException(400, 'multipart body has no file')


def create_app(store: CaseStore | None = None, codes: Codes | None = None) -> FastAPI:
    if store is None:
        assert_durable_when_hosted()
    app = FastAPI(title='Batatis engine')
    state = {'store': store, 'codes': codes}

    def sweep():
        current = state['store']
        if current is not None and getattr(current, 'purge_expired', None):
            maybe_purge(current)

    app.add_middleware(CORSMiddleware, allow_origin_regex=r'http://(localhost|127\.0\.0\.1)(:\d+)?',
                       allow_methods=['*'], allow_headers=['*'])
    app.add_middleware(HttpGuard, sweep=sweep)

    def cases() -> CaseStore:
        if state['store'] is None:
            state['store'] = open_store()
        return state['store']

    def code() -> Codes:
        if state['codes'] is None:
            state['codes'] = Codes()
        return state['codes']

    def purge_cases(*, force: bool = False) -> int:
        current = cases()
        try:
            return current.purge_expired() if force else maybe_purge(current)
        except Exception as exc:
            logger.warning('case purge failed: %s', type(exc).__name__)
            raise HTTPException(503, 'case purge failed', headers={'Cache-Control': 'no-store'}) from None

    @app.post('/cases', response_model=Case, status_code=201)
    def create_case(body: NewCase | None = None):
        purge_cases()
        return cases().put(Case(**(body.model_dump() if body else {})))

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
        try:
            case = cases().add_fact(case_id, fact)
        except VersionConflict as exc:
            raise HTTPException(409, 'case was updated concurrently') from exc
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @app.post('/cases/{case_id}/files', status_code=201)
    async def upload_file(case_id: str, request: Request):
        if cases().get(case_id) is None:
            raise HTTPException(404, 'case not found')
        body = await read_capped(request)
        name, data = _pdf_from_body(body, request.headers.get('content-type', ''),
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
        return Response(res.pdf, media_type='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename="{name}"'})

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

    @app.get('/code/{provision_id}')
    def code_lookup(provision_id: str, request: Request, division: str | None = Query(None, pattern='^[ABC]$')):
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
    return app


app = create_app()
