"""One case access policy for every route and atomic write.

The app dependency applies even to subsequently included routers. Context is set
in an async dependency, then propagated by Starlette into synchronous endpoints.
Stores recheck the original stored record under their write lock, closing the
submit/edit race. Calls outside HTTP (fixtures, CLI) have no request context.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import json
from types import SimpleNamespace

from fastapi import HTTPException, Request, Response

from .account_models import User
from .accounts import optional_user

REVIEWABLE = {'submitted', 'in_review', 'returned', 'accepted'}
READ_ONLY_DETAIL = 'Submitted applications are read-only until returned'


@dataclass(frozen=True)
class AccessContext:
    user: User | None
    mode: str


current_access: ContextVar[AccessContext | None] = ContextVar('batatis_access', default=None)


def authorize_case(case, user: User | None, *, mode: str = 'read'):
    if case is None:
        raise HTTPException(404, 'case not found')
    if not case.owner_id:
        return case
    owner = user is not None and user.id == case.owner_id
    # Nobody reviews their own application, even after onboarding as a reviewer.
    reviewer = (user is not None and user.role == 'reviewer' and user.authority is not None
                and user.authority == case.authority and case.status in REVIEWABLE and not owner)
    if mode == 'review' and reviewer:
        return case
    if mode in {'read', 'message'} and (owner or reviewer):
        return case
    if owner and mode in {'edit', 'submit', 'delete'}:
        if mode == 'edit' and case.status not in {'draft', 'returned'}:
            raise HTTPException(409, READ_ONLY_DETAIL)
        return case
    raise HTTPException(404, 'case not found')


def enforce_mutation(case):
    access = current_access.get()
    if access is not None:
        # Never allow a store write in a read-only route, including POST /export.
        if access.mode == 'read' and case.owner_id:
            raise HTTPException(409, READ_ONLY_DETAIL)
        authorize_case(case, access.user, mode=access.mode)


def enforce_stored_mutation(payload):
    data = json.loads(payload) if isinstance(payload, str) else payload
    enforce_mutation(SimpleNamespace(owner_id=data.get('owner_id'), authority=data.get('authority'),
                                     status=data.get('status', 'draft')))


def enforce_read(case):
    access = current_access.get()
    if access is not None:
        authorize_case(case, access.user)


def request_mode(request: Request) -> str:
    path = request.url.path.rstrip('/')
    if request.method in {'GET', 'HEAD', 'OPTIONS'} or (request.method == 'POST' and path.endswith('/export')):
        return 'read'
    if '/messages' in path:
        return 'message'
    if path.startswith('/review/'):
        return 'review'
    if path.endswith('/submit'):
        return 'submit'
    if request.method == 'DELETE' and path.startswith('/cases/') and path.count('/') == 2:
        return 'delete'
    return 'edit'


def access_dependency(cases):
    async def guard(request: Request, response: Response):
        user = optional_user(request, response, cases)
        request.state.user = user
        response.headers['Cache-Control'] = 'no-store'
        mode = request_mode(request)
        case_id = request.path_params.get('case_id')
        if not case_id and request.url.path.startswith('/cases/'):
            case_id = request.url.path.split('/')[2]
        if case_id:
            store = cases()
            read = getattr(store, 'access_record', store.get)
            request.state.case = authorize_case(read(case_id), user, mode=mode)
        if request.url.path.startswith('/auth/') and request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            content_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
            if content_type != 'application/json':
                raise HTTPException(415, 'Content-Type must be application/json')
        token = current_access.set(AccessContext(user, mode))
        try:
            yield
        finally:
            current_access.reset(token)
    return guard
