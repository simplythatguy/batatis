"""Cookie-session authentication; all state-changing routes require JSON."""
from __future__ import annotations

import json
import os
import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .account_models import ApplicantType, Authority, Role, User, UserResult
from .accounts import (COOKIE, cookie_secure, digest, email_address, issue_session, limit_auth,
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
        if self.role == 'applicant' and self.applicant_type is None:
            raise ValueError('applicant_type is required')
        if self.role == 'reviewer' and self.authority is None:
            raise ValueError('authority is required')
        return self


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

    @router.post('/signup', response_model=UserResult, status_code=201)
    def signup(body: SignupRequest, request: Request, response: Response):
        store = cases()
        limit_auth(store, request, 'signup')
        user = User(email=body.email, name=body.name)
        if not store.create_user(user, password_hash(body.password)):
            raise HTTPException(409, 'An account with this email already exists')
        issue_session(store, user, request, response)
        return UserResult(user=user)

    @router.post('/login', response_model=UserResult)
    def login(body: LoginRequest, request: Request, response: Response):
        store = cases()
        email = body.email.strip().casefold()
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

    @router.post('/onboarding', response_model=UserResult)
    def onboarding(body: OnboardingRequest, request: Request, response: Response):
        user = require_user(request).model_copy()
        store = cases()
        limit_auth(store, request, 'onboarding')
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
