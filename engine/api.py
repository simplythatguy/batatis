"""HTTP interface for the engine. Run: uvicorn engine.api:app --reload"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from codedb import AmbiguousProvisionError

from .codes import CodeDbMissing, Codes
from .codes import default_db
from .export import ExportBlocked, ExportError, FormNotFound, export_case
from .files import FileTooLarge, NotAPdf, discard_pdf, max_upload_bytes, save_pdf
from .models import Case, Fact, Jurisdiction, SectionCRow, Source
from .section_c import section_c_rows
from .store import CaseStore

logger = logging.getLogger(__name__)

# Names the browser may read. Any other X-Batatis-* response header is added on the way out.
EXPOSE_HEADERS = (
    'Content-Disposition',
    'X-Batatis-Form-Version',
    'X-Batatis-Form-Date',
    'X-Batatis-Form-Id',
    'X-Batatis-Jurisdiction',
)


class ExposeBatatisHeaders:
    """Keep Content-Disposition and every X-Batatis-* response header visible to the browser."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        async def send_with_expose(message: Message) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                names = [part.strip() for part in headers.get('access-control-expose-headers', '').split(',')
                         if part.strip()]
                seen = {name.lower() for name in names}
                if 'content-disposition' not in seen:
                    names.append('Content-Disposition')
                    seen.add('content-disposition')
                for key in headers:
                    if key.lower().startswith('x-batatis-') and key.lower() not in seen:
                        names.append(key)
                        seen.add(key.lower())
                headers['access-control-expose-headers'] = ', '.join(names)
            await send(message)

        await self.app(scope, receive, send_with_expose)


class NewCase(BaseModel):
    title: str | None = None
    jurisdiction: Jurisdiction | None = None


class SectionCRequest(BaseModel):
    provisions: list[str]


class ExportRequest(BaseModel):
    draft: bool = False


class StoredFile(BaseModel):
    id: str
    name: str
    pages: int
    sha256: str
    read: Literal[True] = True


def create_app(store: CaseStore | None = None, codes: Codes | None = None) -> FastAPI:
    app = FastAPI(title='Batatis engine')
    app.add_middleware(CORSMiddleware, allow_origin_regex=r'http://(localhost|127\.0\.0\.1)(:\d+)?',
                       allow_methods=['*'], allow_headers=['*'], expose_headers=list(EXPOSE_HEADERS))
    app.add_middleware(ExposeBatatisHeaders)
    state = {'store': store, 'codes': codes}

    def cases() -> CaseStore:
        if state['store'] is None:
            state['store'] = CaseStore()
        return state['store']

    def code() -> Codes:
        if state['codes'] is None:
            try:
                state['codes'] = Codes()
            except CodeDbMissing:
                # The exception message is fixed and has no path. The path stays in this log line.
                logger.error('code database not found: %s', default_db())
                raise
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

    @app.put('/cases/{case_id}/jurisdiction', response_model=Case)
    def set_jurisdiction(case_id: str, body: Jurisdiction):
        def apply(case: Case) -> None:
            case.jurisdiction = body

        case = cases().mutate(case_id, apply)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @app.post('/cases/{case_id}/facts', response_model=Case)
    def add_fact(case_id: str, fact: Fact):
        case = cases().add_fact(case_id, fact)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @app.post('/cases/{case_id}/files', response_model=StoredFile, status_code=201)
    def upload_file(case_id: str, file: UploadFile = File(...)):
        # FastAPI runs sync endpoints in its threadpool, including SQLite, locks,
        # PDF parsing, and file I/O. Keep the save and case update in one worker.
        try:
            if cases().get(case_id) is None:
                raise HTTPException(404, 'case not found')
            limit = max_upload_bytes()
            data = file.file.read(limit + 1)
        finally:
            file.file.close()
        if len(data) > limit:
            raise HTTPException(413, 'file too large')
        try:
            stored = save_pdf(case_id, file.filename, data)
        except FileTooLarge:
            raise HTTPException(413, 'file too large') from None
        except NotAPdf:
            raise HTTPException(415, 'not a PDF') from None
        try:
            fact = Fact(field=f'file.{stored.id}.name', value=stored.name, kind='exact', status='confirmed',
                        source=Source(type='file', ref=stored.id))

            def apply(case: Case) -> None:
                case.facts.append(fact)

            if cases().mutate(case_id, apply) is None:
                raise HTTPException(404, 'case not found')
        except BaseException:
            try:
                discard_pdf(case_id, stored.id)
            except Exception:
                logger.exception('failed to discard PDF after case update failure')
            raise
        return StoredFile(id=stored.id, name=stored.name, pages=stored.pages, sha256=stored.sha256)

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
            logger.error('SCC variance form not found: %s', e)
            raise HTTPException(503, 'SCC variance form not found') from None
        except ExportError as e:
            raise HTTPException(500, str(e))
        name = f'{case_id}-scc-variance{"-DRAFT" if draft else ""}.pdf'
        return Response(res.pdf, media_type='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename="{name}"'})

    @app.get('/code/search')
    def code_search(q: str, division: str | None = Query('B', pattern='^[ABC]$'), limit: int = Query(20, ge=1, le=100)):
        return code().search(q, division=division, limit=limit)

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

    from fastapi.responses import JSONResponse

    @app.exception_handler(CodeDbMissing)
    def missing_codedb(_request, _exc: CodeDbMissing):
        # Not FileNotFoundError. The body is fixed and carries no filesystem path.
        return JSONResponse(status_code=503, content={'detail': 'code database not found'})

    app.include_router(__import__('engine.routes_case', fromlist=['create_router']).create_router(cases, code))
    return app


app = create_app()
