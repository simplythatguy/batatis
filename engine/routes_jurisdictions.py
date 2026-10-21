"""Jurisdiction pack reads. Public data; a case's pack is read under the case access policy."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from .jurisdictions import MatchedBy, registry
from .models_jurisdictions import JurisdictionDetail, JurisdictionsResult
from .store import CaseBackend


class CaseJurisdictionPack(BaseModel):
    """`pack` is null when the case names no jurisdiction or authority yet."""
    model_config = ConfigDict(extra='forbid')
    case_id: str
    matched_by: MatchedBy | None
    pack: JurisdictionDetail | None


def create_router(cases: Callable[[], CaseBackend]) -> APIRouter:
    router = APIRouter(tags=['jurisdictions'])

    @router.get('/jurisdictions', response_model=JurisdictionsResult)
    def list_jurisdictions():
        return registry().listing()

    @router.get('/jurisdictions/{jurisdiction_id}', response_model=JurisdictionDetail)
    def get_jurisdiction(jurisdiction_id: str):
        pack = registry().get(jurisdiction_id)
        if pack is None:
            raise HTTPException(404, 'jurisdiction not found')
        return registry().detail(pack)

    @router.get('/cases/{case_id}/jurisdiction/pack', response_model=CaseJurisdictionPack)
    def case_pack(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        found = registry().resolve_case(case)
        return CaseJurisdictionPack(case_id=case.id, matched_by=found.matched_by if found else None,
                                    pack=registry().detail(found.pack) if found else None)

    return router
