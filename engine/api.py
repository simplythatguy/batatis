"""HTTP interface for the engine. Run: uvicorn engine.api:app --reload"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from codedb import AmbiguousProvisionError

from .codes import Codes
from .export import ExportBlocked, ExportError, FormNotFound, export_case
from .http_guard import HttpGuard
from .llm_gate import client_ip_from, search_allowed
from .models import Case, Fact, Jurisdiction, SectionCRow
from .section_c import section_c_rows
from .store import CaseStore, FileTooLarge, VersionConflict, open_store
from .uploads import PDF_MAX_BYTES, PDF_TOO_LARGE_DETAIL


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
    app = FastAPI(title='Batatis engine')
    app.add_middleware(CORSMiddleware, allow_origin_regex=r'http://(localhost|127\.0\.0\.1)(:\d+)?',
                       allow_methods=['*'], allow_headers=['*'])
    app.add_middleware(HttpGuard)
    state = {'store': store, 'codes': codes}

    def cases() -> CaseStore:
        if state['store'] is None:
            state['store'] = open_store()
        return state['store']

    def code() -> Codes:
        if state['codes'] is None:
            state['codes'] = Codes()
        return state['codes']

    @app.post('/cases', response_model=Case, status_code=201)
    def create_case(body: NewCase | None = None):
        return cases().put(Case(**(body.model_dump() if body else {})))

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

    @app.post('/cases/{case_id}/export', response_class=Response,
              responses={200: {'content': {'application/pdf': {}}}, 409: {'description': 'export blocked'}})
    def export(case_id: str, body: ExportRequest | None = None):
        case = get_case(case_id)
        draft = bool(body and body.draft)
        try:
            res = export_case(case, draft=draft, codes=code())
        except ExportBlocked as e:
            raise HTTPException(409, {'message': 'export blocked; resolve these or export a draft', 'reasons': e.reasons})
        except FormNotFound as e:
            raise HTTPException(503, str(e))
        except ExportError as e:
            raise HTTPException(500, str(e))
        name = f'{case_id}-scc-variance{"-DRAFT" if draft else ""}.pdf'
        return Response(res.pdf, media_type='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename="{name}"'})

    @app.get('/code/search')
    def code_search(request: Request, q: str, division: str | None = Query('B', pattern='^[ABC]$'),
                    limit: int = Query(20, ge=1, le=20)):
        if not search_allowed(client_ip_from(request)):
            raise HTTPException(429, 'code search is rate-limited')
        return code().search(q, division=division, limit=min(limit, 20))

    @app.get('/code/{provision_id}')
    def code_lookup(provision_id: str, division: str | None = Query(None, pattern='^[ABC]$')):
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

    app.include_router(__import__('engine.routes_case', fromlist=['create_router']).create_router(cases, code))
    return app


app = create_app()
