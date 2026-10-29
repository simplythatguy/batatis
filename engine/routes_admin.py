"""The site admin's access-code manager: make a code, see who uses it, cap its seats, switch it off, remove it."""
from __future__ import annotations

import re
import secrets
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from . import ai_access
from .admin import require_admin

NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9 ._-]{0,39}')
NAME_RULE = 'Use letters, numbers, spaces, dots, dashes or underscores, starting with a letter or number.'
TAKEN = 'A code with that name already exists.'


class AccessCodeInfo(BaseModel):
    name: str
    # 'environment' codes come from the server's settings and can be limited or switched off but not read here.
    source: Literal['managed', 'environment']
    max_users: int | None
    accounts: int
    in_use: int
    revoked: bool
    created_at: str | None = None


class AccessCodeList(BaseModel):
    codes: list[AccessCodeInfo]


class AccessCodeCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Checked whole with NAME.fullmatch in the route: a Field pattern only searches, so it let 'a/b' and '<x>' through.
    name: str = Field(min_length=1, max_length=40)
    max_users: int | None = Field(default=None, ge=1, le=100_000)


class AccessCodeCreated(BaseModel):
    """The only time the code itself is shown; the server keeps its hash."""
    code: str
    info: AccessCodeInfo


class AccessCodePatch(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'minProperties': 1})
    # Present as null to remove the limit.
    max_users: int | None = Field(default=None, ge=1, le=100_000)
    revoked: bool | None = None


def create_router(cases):
    router = APIRouter(prefix='/admin', tags=['admin'])

    def info(store, name: str) -> AccessCodeInfo:
        row = ai_access.rows().get(name) or store.access_code(name)
        managed = bool(row and row['code_hash'])
        accounts = len(store.accounts_using_code(name))
        return AccessCodeInfo(name=name, source='managed' if managed else 'environment',
                              max_users=row['max_users'] if row else None, accounts=accounts,
                              in_use=accounts, revoked=bool(row and row['revoked']), created_at=row['created_at'] if row else None)

    @router.get('/access-codes', response_model=AccessCodeList)
    def list_codes(request: Request):
        require_admin(request)
        store = cases()
        ai_access.forget()
        names = sorted({*ai_access.codes(), *(row['name'] for row in store.access_code_rows())} - {ai_access.ADMIN})
        return AccessCodeList(codes=[info(store, name) for name in names])

    @router.post('/access-codes', response_model=AccessCodeCreated, status_code=201)
    def create_code(body: AccessCodeCreate, request: Request):
        require_admin(request)
        store = cases()
        name = body.name.strip()
        if not NAME.fullmatch(name):
            raise HTTPException(400, NAME_RULE)
        # Names differing only in case read as the same code in the list, so they are one name.
        taken = {*ai_access.codes(), *(row['name'] for row in store.access_code_rows())}
        if name.casefold() in {other.casefold() for other in taken} | {ai_access.ADMIN}:
            raise HTTPException(409, TAKEN)
        code = secrets.token_urlsafe(24)
        if not store.create_access_code(name, ai_access.fingerprint(code), body.max_users):
            raise HTTPException(409, TAKEN)
        ai_access.forget()
        return AccessCodeCreated(code=code, info=info(store, name))

    # ':path' lets a name made before names were checked, such as 'qa1 bad/name', still be changed and removed.
    @router.patch('/access-codes/{name:path}', response_model=AccessCodeInfo)
    def change_code(name: str, body: AccessCodePatch, request: Request):
        require_admin(request)
        store = cases()
        ai_access.forget()
        row = store.access_code(name)
        if name == ai_access.ADMIN or (row is None and name not in ai_access.codes()):
            raise HTTPException(404, 'No such access code.')
        if not body.model_fields_set:
            raise HTTPException(422, 'Supply max_users or revoked.')
        max_users = body.max_users if 'max_users' in body.model_fields_set else (row['max_users'] if row else None)
        revoked = body.revoked if body.revoked is not None else bool(row and row['revoked'])
        store.set_access_code(name, max_users=max_users, revoked=revoked)
        ai_access.forget()
        return info(store, name)

    @router.delete('/access-codes/{name:path}', status_code=204)
    def remove_code(name: str, request: Request):
        require_admin(request)
        store = cases()
        row = store.access_code(name)
        if name == ai_access.ADMIN or (row is None and name not in ai_access.codes()):
            raise HTTPException(404, 'No such access code.')
        if row is None or not row['code_hash']:
            raise HTTPException(409, 'This code comes from the server settings; switch it off instead of removing it.')
        if not store.delete_access_code(name):
            raise HTTPException(404, 'No such access code.')
        ai_access.forget()

    return router
