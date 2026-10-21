"""Officer package review routes (WP-34). One router for api.py to include.

Administrative completeness only: these routes never fill a missing item, never
state compliance, and never write risk, mitigation or the officer's decision.
"""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter

from .codes import Codes
from .review.routes_completeness import create_router as completeness_router
from .store import CaseBackend


def create_router(cases: Callable[[], CaseBackend], code: Callable[[], Codes]) -> APIRouter:
    router = APIRouter()
    router.include_router(completeness_router(cases, code))
    return router
