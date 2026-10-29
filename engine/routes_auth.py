"""Cookie-session authentication; all state-changing routes require JSON."""
from __future__ import annotations

import json
import os
import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import ai_access
from .llm_gate import client_ip_from
from .account_models import ApplicantType, Authority, Role, User, UserResult
from .accounts import (CODE_ACCOUNT_DOMAIN, COOKIE, cookie_secure, digest, email_address, issue_session, limit_auth,
                       password_hash, password_matches, require_user)


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(max_length=254)
    password: str = Field(min_length=10, max_length=1024)
    name: str = Field(min_length=1, max_length=160)

    _email = field_validator('email')(email_address)

    @field_validator('name')
    @classmethod
    def _name(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError('Enter a name')
        return value.strip()


class CodeLoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=80)

    @field_validator('name')
    @classmethod
    def _name(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError('Enter a name')
        return value.strip()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Role
    applicant_type: ApplicantType | None = None
    authority: Authority | None = None
    access_code: str | None = Field(default=None, max_length=1024)

    @model_validator(mode='after')
    def _role_fields(self):
        if self.role == 'reviewer' and self.authority is None:
            raise ValueError('authority is required')
        return self


class AiAccessRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1, max_length=200)


class AiAccess(BaseModel):
    """Whether this deployment needs a code for AI, and whether this account has a current one."""
    required: bool
    granted: bool


def reviewer_code(authority: str, supplied: str | None):
    try:
        codes = json.loads(os.environ.get('BATATIS_REVIEWER_CODES') or '{}')
    except (ValueError, TypeError):
        codes = {}
    expected = codes.get(authority) if isinstance(codes, dict) else None
    if not isinstance(expected, str) or not expected:
        raise HTTPException(403, 'Reviewer sign-up is not open for this authority')
    if not secrets.compare_digest(expected.encode(), (supplied or '').encode()):
        raise HTTPException(403, 'Reviewer access code is incorrect')


def create_router(cases):
    router = APIRouter(prefix='/auth', tags=['accounts'])

    @router.post('/code-login', response_model=UserResult)
    def code_login(body: CodeLoginRequest, request: Request, response: Response):
        """Sign in with an access code and a name. The same code and name always reach the same account."""
        store = cases()
        # Only wrong codes count and only wrong codes are refused for it: a room on one network address
        # keeps signing in with the right code while somebody there mistypes. Codes are too long to guess.
        found = ai_access.find(body.code)
        if found is None:
            bucket = digest('code-login-fail:' + client_ip_from(request))
            limit, window = int(os.environ.get('BATATIS_AUTH_RATE_LIMIT') or '10'), float(os.environ.get('BATATIS_AUTH_RATE_WINDOW_SECONDS') or '600')
            if not store.account_rate(bucket, limit, window):
                raise HTTPException(429, 'Too many wrong codes. Try again later.', headers={'Retry-After': str(int(window))})
            raise HTTPException(403, 'That access code isn’t valid.')
        code_name, fingerprint = found
        email = f"{digest('code-login:' + code_name + ':' + body.name.casefold())[:32]}@{CODE_ACCOUNT_DOMAIN}"
        data = store.user_credentials(email)
        if data is None:
            seats = ai_access.limit(code_name)
            if seats is not None and len(store.accounts_using_code(code_name)) >= seats:
                raise HTTPException(403, 'That access code is full')
            user = User(email=email, name=body.name, ai_access=code_name, ai_access_fingerprint=fingerprint)
            if code_name == ai_access.ADMIN:
                # The admin account exists for the manager, onboarding offers nothing it needs to answer.
                user.onboarded = True
            if not store.create_user(user, None):
                data = store.user_credentials(email)
        if data is not None:
            user = User.model_validate(data['user'])
            user.name = body.name
            user.ai_access, user.ai_access_fingerprint = code_name, fingerprint
            if code_name == ai_access.ADMIN:
                # The admin signs the account in even before this change existed: old admin accounts skip onboarding too.
                user.onboarded = True
            store.update_user(user, revoke_sessions=False)
        issue_session(store, user, request, response)
        return UserResult(user=user)

    @router.post('/signup', response_model=UserResult, status_code=201)
    def signup(body: SignupRequest, request: Request, response: Response):
        store = cases()
        limit_auth(store, request, 'signup')
        if body.email.endswith('@' + CODE_ACCOUNT_DOMAIN):
            raise HTTPException(422, 'Enter a valid email address')
        user = User(email=body.email, name=body.name)
        if not store.create_user(user, password_hash(body.password)):
            raise HTTPException(409, 'An account with this email already exists')
        issue_session(store, user, request, response)
        return UserResult(user=user)

    @router.post('/login', response_model=UserResult)
    def login(body: LoginRequest, request: Request, response: Response):
        store = cases()
        email = body.email.strip().casefold()
        if email.endswith('@' + CODE_ACCOUNT_DOMAIN):
            raise HTTPException(401, 'Email or password is incorrect')
        limit_auth(store, request, 'login', email)
        # Also cap the IP across different email guesses.
        limit_auth(store, request, 'login-ip')
        data = store.user_credentials(email)
        if not password_matches(body.password, data['password'] if data else None):
            raise HTTPException(401, 'Email or password is incorrect')
        user = User.model_validate(data['user'])
        issue_session(store, user, request, response)
        return UserResult(user=user)

    @router.post('/logout', status_code=204)
    def logout(request: Request):
        token = request.cookies.get(COOKIE)
        if token:
            cases().delete_session(digest(token))
        response = Response(status_code=204, headers={'Cache-Control': 'no-store'})
        response.delete_cookie(COOKIE, path='/', httponly=True, secure=cookie_secure(request), samesite='lax')
        return response

    @router.get('/me', response_model=UserResult)
    def me(request: Request):
        return UserResult(user=require_user(request))

    @router.get('/ai-access', response_model=AiAccess)
    def ai_access_status(request: Request):
        user = require_user(request)
        return AiAccess(required=ai_access.required(), granted=ai_access.granted(user))

    @router.post('/ai-access', response_model=AiAccess)
    def ai_access_enter(body: AiAccessRequest, request: Request):
        user = require_user(request).model_copy()
        store = cases()
        limit_auth(store, request, 'ai-access')
        found = ai_access.find(body.code)
        if found is None:
            raise HTTPException(403, 'That access code isn’t valid.')
        name, fingerprint = found
        seats = ai_access.limit(name)
        if seats is not None and user.ai_access != name:
            # Seats count accounts; the person's own account never counts against itself.
            if len(store.accounts_using_code(name, excluding=user.id)) >= seats:
                raise HTTPException(403, 'That access code is full')
        user.ai_access, user.ai_access_fingerprint = name, fingerprint
        store.update_user(user, revoke_sessions=False)
        return AiAccess(required=ai_access.required(), granted=True)

    @router.delete('/ai-access', response_model=AiAccess)
    def ai_access_remove(request: Request):
        user = require_user(request).model_copy()
        user.ai_access = user.ai_access_fingerprint = None
        cases().update_user(user, revoke_sessions=False)
        return AiAccess(required=ai_access.required(), granted=ai_access.granted(user))

    @router.post('/onboarding', response_model=UserResult)
    def onboarding(body: OnboardingRequest, request: Request, response: Response):
        user = require_user(request).model_copy()
        store = cases()
        limit_auth(store, request, 'onboarding')
        # A live testing access code already opened the product, including reviewer.
        if not ai_access.holds(user):
            if body.role == 'reviewer':
                reviewer_code(body.authority, body.access_code)
            elif user.role == 'reviewer':
                # A reviewer leaving the role must demonstrate the same authority code.
                reviewer_code(user.authority, body.access_code)
        user.role, user.onboarded = body.role, True
        user.applicant_type = body.applicant_type if body.role == 'applicant' else None
        user.authority = body.authority if body.role == 'reviewer' else None
        store.update_user(user)
        issue_session(store, user, request, response)
        return UserResult(user=user)

    from .oauth import add_oauth_routes
    add_oauth_routes(router, cases)
    return router
