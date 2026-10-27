"""Owner-only workspace mutations, committed against the exact snapshot they read."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .models import now
from .models_workspace import (HistoryEntry, SignatureInput, SignerRole, WorkspaceConsent,
                               WorkspaceSignature, WorkspaceView, trim_history)
from .store import CaseBackend, VersionConflict
from .workspace import content_hash, signers, workspace_view


SIGNING_SETTINGS = Path(__file__).parent / 'data' / 'jurisdictions' / 'signing.json'
SIGNING_ZONE = ZoneInfo(json.loads(SIGNING_SETTINGS.read_text(encoding='utf-8'))['timezone'])


class ConsentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    agreed: bool = Field(strict=True)


class HistoryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    entries: list[HistoryEntry] = Field(max_length=300)


def create_router(cases: Callable[[], CaseBackend]) -> APIRouter:
    router = APIRouter(tags=['application workspace'])

    def snapshot(case_id, request):
        store = cases()
        saved = store.get_snapshot(case_id)
        if saved is None:
            raise HTTPException(404, 'case not found')
        case, version = saved
        user = request.state.user
        if not user or not case.owner_id or case.owner_id != user.id:
            raise HTTPException(404, 'case not found')
        if case.status not in {'draft', 'returned'}:
            raise HTTPException(409, 'Submitted applications are read-only until returned')
        return store, case, version

    def save(store, case, version):
        try:
            store.put(case, expected_version=version)
        except VersionConflict as error:
            raise HTTPException(409, 'case was updated concurrently') from error

    @router.get('/cases/{case_id}/workspace', response_model=WorkspaceView)
    def get_workspace(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return workspace_view(case)

    @router.put('/cases/{case_id}/signatures/{role}', response_model=WorkspaceSignature)
    def put_signature(case_id: str, role: SignerRole, body: SignatureInput, request: Request):
        store, case, version = snapshot(case_id, request)
        if role not in {signer.role for signer in signers(case)}:
            raise HTTPException(422, 'This application does not name an owner representative.')
        signature = WorkspaceSignature(**body.model_dump(), role=role, content_hash=content_hash(case),
                                       signed_on=datetime.now(SIGNING_ZONE).date().isoformat())
        case.workspace.signatures = [item for item in case.workspace.signatures if item.role != role] + [signature]
        save(store, case, version)
        return signature

    @router.delete('/cases/{case_id}/signatures/{role}', status_code=204)
    def delete_signature(case_id: str, role: SignerRole, request: Request):
        store, case, version = snapshot(case_id, request)
        case.workspace.signatures = [item for item in case.workspace.signatures if item.role != role]
        save(store, case, version)
        return Response(status_code=204)

    @router.put('/cases/{case_id}/consent', response_model=WorkspaceConsent)
    def put_consent(case_id: str, body: ConsentInput, request: Request):
        store, case, version = snapshot(case_id, request)
        case.workspace.consent = WorkspaceConsent(agreed=body.agreed, at=now())
        save(store, case, version)
        return case.workspace.consent

    @router.post('/cases/{case_id}/history', response_model=list[HistoryEntry])
    def append_history(case_id: str, body: HistoryInput, request: Request):
        store, case, version = snapshot(case_id, request)
        case.workspace.history = trim_history(case.workspace.history + body.entries)
        save(store, case, version)
        return list(reversed(case.workspace.history))

    return router
