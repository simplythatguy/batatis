"""Standing-package checklists (WP-32). Docs: docs/api/checklists.md.

Two reads and one versioned write. Case access is the app-wide policy in `engine/access.py`: GET is `read`,
the answer POST is `edit` (owner only, draft or returned). Nothing here calls a provider or judges a design;
an answer is the applicant's declaration and a checklist is never a determination.
"""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException

from .jurisdictions import registry
from .jurisdictions.checklists import (NONE_IN_PACK, NONE_NO_JURISDICTION, NOTICE, case_view, field, for_pack,
                                       historical_for, jurisdiction_view)
from .models import Case, Fact, Source
from .models_checklists import (CaseChecklists, ChecklistAnswerRequest, ChecklistAnswerResult,
                                JurisdictionChecklists)
from .store import CaseBackend, VersionConflict

CONFLICT = 'case was updated concurrently'
ALWAYS_APPLIES = ('This condition always applies when the package is used. If it cannot be met, the package '
                  'cannot be used as published; answer not_yet, or use a site-specific variance instead.')


def _case_checklists(case: Case) -> CaseChecklists:
    reg = registry()
    found = reg.resolve_case(case)
    if found is None:
        return CaseChecklists(case_id=case.id, case_version=case.version, jurisdiction=None, matched_by=None,
                              checklists=[], historical=[], none_reason=NONE_NO_JURISDICTION, notice=NOTICE)
    provisions = {p.id: p.provisions for p in found.pack.standing_packages}
    rows = [case_view(case, c, provisions.get(c.package, [])) for c in for_pack(reg, found.pack)]
    rows.sort(key=lambda r: not r.matches_case_provisions)      # stable: pack order within each half
    return CaseChecklists(case_id=case.id, case_version=case.version, jurisdiction=found.pack.id,
                          matched_by=found.matched_by, checklists=rows, historical=historical_for(found.pack),
                          none_reason=None if rows else NONE_IN_PACK, notice=NOTICE)


def create_router(cases: Callable[[], CaseBackend]) -> APIRouter:
    router = APIRouter(tags=['checklists'])

    @router.get('/jurisdictions/{jurisdiction_id}/checklists', response_model=JurisdictionChecklists)
    def jurisdiction_checklists(jurisdiction_id: str):
        reg = registry()
        pack = reg.get(jurisdiction_id)
        if pack is None:
            raise HTTPException(404, 'jurisdiction not found')
        return JurisdictionChecklists(jurisdiction=pack.id, checklists=[jurisdiction_view(c) for c in for_pack(reg, pack)],
                                      historical=historical_for(pack), notice=NOTICE)

    @router.get('/cases/{case_id}/checklists', response_model=CaseChecklists)
    def case_checklists(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return _case_checklists(case)

    @router.post('/cases/{case_id}/checklists/{checklist_id}/answers', response_model=ChecklistAnswerResult)
    def answer(case_id: str, checklist_id: str, body: ChecklistAnswerRequest):
        store = cases()
        snapshot = store.get_snapshot(case_id)
        if snapshot is None:
            raise HTTPException(404, 'case not found')
        case, version = snapshot
        if body.expected_version != version:
            raise HTTPException(409, CONFLICT)
        reg = registry()
        found = reg.resolve_case(case)
        checklist = next((c for c in (for_pack(reg, found.pack) if found else []) if c.id == checklist_id), None)
        if checklist is None:
            raise HTTPException(404, "checklist not found for this case's jurisdiction")
        condition = next((c for c in checklist.conditions if c.id == body.condition_id), None)
        if condition is None:
            raise HTTPException(422, 'condition not found in this checklist')
        if body.state == 'does_not_apply' and not condition.may_not_apply:
            raise HTTPException(422, ALWAYS_APPLIES)
        ref = f'checklist:{checklist.id}:{condition.id}'
        reason = body.reason.strip() if body.reason and body.reason.strip() else None
        case.facts += [
            Fact(field=field(checklist.id, condition.id), value=body.state, kind='exact', status='confirmed',
                 source=Source(type='user_click', ref=ref)),
            # Always written, so a later answer without a reason clears an earlier one.
            Fact(field=field(checklist.id, condition.id, reason=True), value=reason, kind='exact',
                 status='confirmed', source=Source(type='user_text', ref=ref)),
        ]
        try:
            saved = store.put(case, expected_version=version)
        except VersionConflict as error:
            if error.actual is None:
                raise HTTPException(404, 'case not found') from error
            raise HTTPException(409, CONFLICT) from error
        provisions = next((p.provisions for p in found.pack.standing_packages if p.id == checklist.package), [])
        return ChecklistAnswerResult(case_version=saved.version, checklist=case_view(saved, checklist, provisions))

    return router
