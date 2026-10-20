"""HTTP interface for the engine. Run: uvicorn engine.api:app --reload"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from codedb import AmbiguousProvisionError

from .codes import Codes
from .export import ExportBlocked, ExportError, FormMismatch, FormNotFound, export_case
from .models import Case, Fact, Jurisdiction, SectionCRow
from .section_c import section_c_rows
from .store import CaseStore


class NewCase(BaseModel):
    title: str | None = None
    jurisdiction: Jurisdiction | None = None


class SectionCRequest(BaseModel):
    provisions: list[str]


class ExportRequest(BaseModel):
    draft: bool = False
    jurisdiction: str | None = None
    form_id: str | None = None


def create_app(store: CaseStore | None = None, codes: Codes | None = None) -> FastAPI:
    app = FastAPI(title='Batatis engine')
    app.add_middleware(CORSMiddleware, allow_origin_regex=r'http://(localhost|127\.0\.0\.1)(:\d+)?',
                       allow_methods=['*'], allow_headers=['*'])
    state = {'store': store, 'codes': codes}

    def cases() -> CaseStore:
        if state['store'] is None:
            state['store'] = CaseStore()
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
            res = export_case(case, draft=draft, codes=code(),
                              jurisdiction=body.jurisdiction if body else None,
                              form_id=body.form_id if body else None)
        except ExportBlocked as e:
            raise HTTPException(409, {'message': 'export blocked; resolve these or export a draft', 'reasons': e.reasons})
        except FormNotFound as e:
            raise HTTPException(503, str(e))
        except FormMismatch as e:
            raise HTTPException(422, str(e))
        except ExportError as e:
            raise HTTPException(500, str(e))
        name = f'{case_id}-{res.form_id or "variance"}{"-DRAFT" if draft else ""}.pdf'
        return Response(res.pdf, media_type='application/pdf', headers={
            'Content-Disposition': f'attachment; filename="{name}"',
            'X-Batatis-Form-Version': res.form_version,
            'X-Batatis-Form-Date': res.form_date,
            'X-Batatis-Form-Id': res.form_id,
            'X-Batatis-Jurisdiction': res.jurisdiction,
        })

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

    app.include_router(__import__('engine.routes_case', fromlist=['create_router']).create_router(cases, code))
    return app


app = create_app()
