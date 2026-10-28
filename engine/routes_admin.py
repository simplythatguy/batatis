"""The site admin's access-code manager: make a code, see who uses it, cap its seats, switch it off, remove an unused one."""
from __future__ import annotations

import re
import secrets
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from . import ai_access
from .admin import require_admin

NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9 ._-]{0,39}')


class AccessCodeInfo(BaseModel):
    name: str
    # 'environment' codes come from the server's settings and can be limited or switched off but not read here.
    source: Literal['managed', 'environment']
    max_users: int | None
    accounts: int
    installs: int
    in_use: int
    revoked: bool
    created_at: str | None = None


class AccessCodeList(BaseModel):
    codes: list[AccessCodeInfo]


class AccessCodeCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=40, pattern=NAME.pattern)
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
        installs = store.installs_using_code(name)
        return AccessCodeInfo(name=name, source='managed' if managed else 'environment',
                              max_users=row['max_users'] if row else None, accounts=accounts, installs=installs,
                              in_use=accounts + installs, revoked=bool(row and row['revoked']), created_at=row['created_at'] if row else None)

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
        if name in ai_access.codes() or name.casefold() == ai_access.ADMIN:
            raise HTTPException(409, 'A code with that name already exists')
        code = secrets.token_urlsafe(24)
        if not store.create_access_code(name, ai_access.fingerprint(code), body.max_users):
            raise HTTPException(409, 'A code with that name already exists')
        ai_access.forget()
        return AccessCodeCreated(code=code, info=info(store, name))

    @router.patch('/access-codes/{name}', response_model=AccessCodeInfo)
    def change_code(name: str, body: AccessCodePatch, request: Request):
        require_admin(request)
        store = cases()
        ai_access.forget()
        row = store.access_code(name)
        if name == ai_access.ADMIN or (row is None and name not in ai_access.codes()):
            raise HTTPException(404, 'No such access code')
        if not body.model_fields_set:
            raise HTTPException(422, 'Supply max_users or revoked')
        max_users = body.max_users if 'max_users' in body.model_fields_set else (row['max_users'] if row else None)
        revoked = body.revoked if body.revoked is not None else bool(row and row['revoked'])
        store.set_access_code(name, max_users=max_users, revoked=revoked)
        ai_access.forget()
        return info(store, name)

    @router.delete('/access-codes/{name}', status_code=204)
    def remove_code(name: str, request: Request):
        """Deletes a managed code that nobody uses. A code in use or from the environment is refused."""
        require_admin(request)
        store = cases()
        row = store.access_code(name)
        if name == ai_access.ADMIN or (row is None and name not in ai_access.codes()):
            raise HTTPException(404, 'No such access code')
        if row is None or not row['code_hash']:
            raise HTTPException(409, 'This code comes from the server settings; switch it off instead of removing it')
        used = len(store.accounts_using_code(name)) + store.installs_using_code(name)
        if used:
            raise HTTPException(409, f'{used} still using this code. Turn it off instead of removing it.')
        if not store.delete_access_code(name):
            raise HTTPException(404, 'No such access code')
        ai_access.forget()

    return router
