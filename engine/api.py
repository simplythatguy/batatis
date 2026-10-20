"""HTTP interface for the engine. Run: uvicorn engine.api:app --reload"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from codedb import AmbiguousProvisionError

from .codes import CodeDbMissing, Codes
from .export import ExportBlocked, ExportError, FormNotFound, export_case
from .identify_http import CODEDB_DOWNLOADS, IdentifyRequest, IdentifyResponse, identify
from .models import Case, Fact, Jurisdiction, SectionCRow
from .privacy import privacy_notice
from .spend import BudgetStatus, budget_status, live_enabled
from .section_c import section_c_rows
from .store import CaseStore


class NewCase(BaseModel):
    title: str | None = None
    jurisdiction: Jurisdiction | None = None


class SectionCRequest(BaseModel):
    provisions: list[str]


class ExportRequest(BaseModel):
    draft: bool = False


def create_app(store: CaseStore | None = None, codes: Codes | None = None, identify_client=None,
               registry=None) -> FastAPI:
    app = FastAPI(title='Batatis engine')
    app.add_middleware(CORSMiddleware, allow_origin_regex=r'http://(localhost|127\.0\.0\.1)(:\d+)?',
                       allow_methods=['*'], allow_headers=['*'])

    @app.middleware('http')
    async def privacy_and_codedb(request: Request, call_next):
        # The code database is not a download. The body is fixed and has no file bytes.
        if request.url.path in CODEDB_DOWNLOADS:
            denied = JSONResponse(status_code=404, content={'detail': 'not found'})
            _public_headers(denied)
            return denied
        response = await call_next(request)
        _public_headers(response)
        return response

    def _public_headers(response: Response) -> None:
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        notice = privacy_notice(live=live_enabled())
        if notice:
            response.headers['X-Batatis-Notice'] = notice

    state = {'store': store, 'codes': codes, 'identify_client': identify_client}

    def cases() -> CaseStore:
        if state['store'] is None:
            state['store'] = CaseStore()
        return state['store']

    def code() -> Codes:
        if state['codes'] is None:
            state['codes'] = Codes()
        return state['codes']

    @app.get('/status/budget', response_model=BudgetStatus)
    def status_budget():
        # Ledger problems stay on this 200. The body has no key and no per-call rows.
        return budget_status()

    @app.post('/identify', response_model=IdentifyResponse, responses={429: {'description': 'per-IP limit'}})
    def identify_route(body: IdentifyRequest, request: Request):
        outcome = identify(request, body, codes=state['codes'], client=state['identify_client'] or _refuse_live_client)
        if isinstance(outcome, tuple):
            status, payload, retry_after = outcome
            return JSONResponse(status_code=status, content=payload, headers={'Retry-After': str(retry_after)})
        return outcome

    @app.post('/cases', response_model=Case, status_code=201)
    def create_case(body: NewCase | None = None):
        return cases().put(Case(**(body.model_dump() if body else {})))

    @app.get('/cases/{case_id}', response_model=Case)
    def get_case(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @app.delete('/cases/{case_id}', status_code=204)
    def delete_case(case_id: str):
        if not cases().delete(case_id):
            raise HTTPException(404, 'case not found')
        return Response(status_code=204)

    @app.post('/cases/{case_id}/facts', response_model=Case)
    def add_fact(case_id: str, fact: Fact):
        case = cases().add_fact(case_id, fact)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

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

    @app.exception_handler(CodeDbMissing)
    def missing_codedb(_request, _exc: CodeDbMissing):
        # Not FileNotFoundError. The body is fixed and carries no filesystem path.
        return JSONResponse(status_code=503, content={'detail': 'code database not found'})

    app.include_router(__import__('engine.routes_case', fromlist=['create_router']).create_router(cases, code, registry))
    return app


def _refuse_live_client():
    """No injected client. A live call that reached here did not reserve a provider request."""
    raise RuntimeError('OpenAI client is not configured')


app = create_app()
