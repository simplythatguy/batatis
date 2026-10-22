"""Coded rules (WP-31): read-only. Docs: docs/api/rules.md.

Case access is the app-wide policy in `engine/access.py` (`authorize_case`, mode `read` for GET): the owner
and a reviewer of the case's authority can read; anyone else gets 404.
"""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException

from .rules import load_index, load_rules
from .rules.case import case_rules
from .rules.models import CaseRules, RuleSet
from .store import CaseBackend


def create_router(cases: Callable[[], CaseBackend]) -> APIRouter:
    router = APIRouter(tags=['coded rules'])

    @router.get('/rules', response_model=RuleSet)
    def rule_definitions():
        """Rule data for the live browser evaluator. Static; no case."""
        index = load_index()
        return RuleSet(version=index['version'], edition=index['edition'], index=index, rules=load_rules())

    @router.get('/cases/{case_id}/rules', response_model=CaseRules)
    def rules_for_case(case_id: str):
        """Evaluate the case's facts against every coded rule. Writes nothing; calls no provider."""
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case_rules(case)

    return router
