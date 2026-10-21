"""OIDC code flow with browser-bound state, S256 PKCE and signed ID tokens.

Only fixed provider hosts are contacted. No provider tokens are persisted. The
HTTP client is an external seam; tests supply an httpx.MockTransport there.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import time
from urllib.parse import unquote, urlencode, urlsplit

import httpx
import jwt
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from .account_store import IdentityConflict
from .accounts import cookie_secure, digest, email_address, issue_session, limit_auth

STATE_COOKIE = 'batatis_oauth_state'
OAUTH_SECONDS = 600


def configuration(provider: str) -> dict | None:
    prefix = 'BATATIS_' + provider.upper()
    client_id = (os.environ.get(prefix + '_CLIENT_ID') or '').strip()
    secret = (os.environ.get(prefix + '_CLIENT_SECRET') or '').strip()
    if provider not in {'google', 'microsoft'} or not client_id or not secret:
        return None
    if provider == 'google':
        return {'client_id': client_id, 'secret': secret,
                'authorize': 'https://accounts.google.com/o/oauth2/v2/auth',
                'token': 'https://oauth2.googleapis.com/token',
                'jwks': 'https://www.googleapis.com/oauth2/v3/certs',
                'userinfo': 'https://openidconnect.googleapis.com/v1/userinfo'}
    tenant = (os.environ.get(prefix + '_TENANT') or '').strip()
    if not tenant or not re.fullmatch(r'[a-zA-Z0-9.-]{1,253}', tenant):
        return None
    root = f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0'
    return {'client_id': client_id, 'secret': secret, 'tenant': tenant,
            'authorize': root + '/authorize', 'token': root + '/token',
            'jwks': f'https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys',
            'userinfo': 'https://graph.microsoft.com/oidc/userinfo'}


def redirect_path(value: str) -> str:
    if len(value) > 2000:
        raise HTTPException(400, 'Invalid redirect path')
    # Decode repeatedly so double-encoded slashes/backslashes cannot become a host.
    decoded = value
    for _ in range(4):
        decoded = unquote(decoded)
    parts = urlsplit(decoded)
    if (not decoded.startswith('/') or decoded.startswith('//') or parts.scheme or parts.netloc
            or '\\' in decoded or any(ord(c) < 32 or ord(c) == 127 for c in decoded)):
        raise HTTPException(400, 'Invalid redirect path')
    return value


def web_origin() -> str:
    value = os.environ.get('BATATIS_WEB_ORIGIN', 'http://localhost:5480').rstrip('/')
    parsed = urlsplit(value)
    if (parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise HTTPException(503, 'Authentication unavailable')
    return value


def callback_uri(request: Request, provider: str) -> str:
    origin = os.environ.get('BATATIS_API_ORIGIN') or str(request.base_url).rstrip('/')
    return origin.rstrip('/') + request.scope.get('batatis_api_prefix', '') + f'/auth/oauth/{provider}/callback'


class OAuthClient:
    def __init__(self, transport=None):
        self.transport = transport

    def exchange(self, provider: str, config: dict, code: str, pending: dict) -> dict:
        with httpx.Client(transport=self.transport, timeout=10, follow_redirects=False) as client:
            response = client.post(config['token'], data={
                'grant_type': 'authorization_code', 'code': code, 'client_id': config['client_id'],
                'client_secret': config['secret'], 'redirect_uri': pending['redirect_uri'],
                'code_verifier': pending['verifier'],
            })
            response.raise_for_status()
            tokens = response.json()
            encoded = tokens['id_token']
            header = jwt.get_unverified_header(encoded)
            if header.get('alg') != 'RS256':
                raise ValueError('invalid signing algorithm')
            response = client.get(config['jwks'])
            response.raise_for_status()
            keys = response.json()['keys']
            matching = [key for key in keys if key.get('kid') == header.get('kid') and key.get('kty') == 'RSA'
                        and key.get('use', 'sig') == 'sig']
            if len(matching) != 1:
                raise ValueError('unknown signing key')
            key = jwt.PyJWK.from_dict(matching[0], algorithm='RS256').key
            claims = jwt.decode(encoded, key=key, algorithms=['RS256'], audience=config['client_id'],
                                options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'nonce']}, leeway=30)
            if not secrets.compare_digest(str(claims['nonce']), pending['nonce']):
                raise ValueError('invalid nonce')
            if claims.get('azp', config['client_id']) != config['client_id']:
                raise ValueError('invalid authorized party')
            if provider == 'google':
                if claims['iss'] not in {'https://accounts.google.com', 'accounts.google.com'}:
                    raise ValueError('invalid issuer')
            else:
                tid = claims.get('tid', '')
                if not re.fullmatch(r'[0-9a-fA-F-]{36}', tid):
                    raise ValueError('invalid tenant')
                if claims['iss'] != f'https://login.microsoftonline.com/{tid}/v2.0':
                    raise ValueError('invalid issuer')
                tenant = config['tenant']
                if re.fullmatch(r'[0-9a-fA-F-]{36}', tenant) and tenant.casefold() != tid.casefold():
                    raise ValueError('wrong tenant')
                # Tenant-domain aliases must be resolved to a pinned GUID by configuration.
                if tenant not in {'common', 'organizations', 'consumers'} and not re.fullmatch(r'[0-9a-fA-F-]{36}', tenant):
                    raise ValueError('configure tenant GUID')
            response = client.get(config['userinfo'], headers={'Authorization': 'Bearer ' + tokens['access_token']})
            response.raise_for_status()
            profile = response.json()
            if not secrets.compare_digest(str(profile.get('sub', '')), str(claims['sub'])):
                raise ValueError('userinfo subject mismatch')
            if provider == 'google' and (claims.get('email_verified') is not True or profile.get('email_verified') is not True):
                raise ValueError('unverified email')
            # Microsoft email is display metadata, not a linking credential. Subject owns identity.
            email = email_address(profile.get('email') or claims.get('email') or '')
            name = str(profile.get('name') or claims.get('name') or email.split('@')[0])[:160].strip()
            return {'subject': claims['iss'] + '|' + claims['sub'], 'email': email, 'name': name}


def add_oauth_routes(router, cases):
    @router.get('/providers')
    def providers():
        return {'providers': [{'id': 'password', 'label': 'Email'}] + [
            {'id': provider, 'label': label} for provider, label in [('google', 'Google'), ('microsoft', 'Microsoft')]
            if configuration(provider)]}

    @router.get('/oauth/{provider}/start')
    def start(provider: str, request: Request, redirect: str = '/'):
        config = configuration(provider)
        if config is None:
            raise HTTPException(404, 'Authentication provider unavailable')
        target = redirect_path(redirect)
        web_origin()
        store = cases()
        limit_auth(store, request, 'oauth-start')
        state, verifier, nonce = (secrets.token_urlsafe(32) for _ in range(3))
        uri = callback_uri(request, provider)
        store.save_oauth(digest(state), {'provider': provider, 'verifier': verifier, 'nonce': nonce,
                                       'redirect_uri': uri, 'redirect': target}, time.time() + OAUTH_SECONDS)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        url = config['authorize'] + '?' + urlencode({
            'client_id': config['client_id'], 'redirect_uri': uri, 'response_type': 'code',
            'scope': 'openid email profile', 'state': state, 'nonce': nonce,
            'code_challenge': challenge, 'code_challenge_method': 'S256', 'response_mode': 'query',
        })
        response = RedirectResponse(url, status_code=302, headers={'Cache-Control': 'no-store'})
        response.set_cookie(STATE_COOKIE, state, max_age=OAUTH_SECONDS, httponly=True,
                            secure=cookie_secure(request), samesite='lax', path='/')
        return response

    @router.get('/oauth/{provider}/callback')
    def callback(provider: str, request: Request, state: str = '', code: str = '', error: str | None = None):
        config = configuration(provider)
        browser_state = request.cookies.get(STATE_COOKIE, '')
        if (config is None or not state or len(state) > 128 or not browser_state
                or not secrets.compare_digest(state.encode(), browser_state.encode())):
            raise HTTPException(400, 'Invalid or expired authentication state')
        store = cases()
        pending = store.consume_oauth(digest(state))
        if not pending or pending['provider'] != provider or error or not code or len(code) > 8192:
            raise HTTPException(400, 'Invalid or expired authentication state')
        try:
            identity = OAuthClient().exchange(provider, config, code, pending)
            user = store.oauth_user(provider, identity['subject'], identity['email'], identity['name'])
        except IdentityConflict:
            raise HTTPException(409, 'Use your existing sign-in method for this email') from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError, jwt.PyJWTError):
            raise HTTPException(400, 'Authentication could not be verified') from None
        response = RedirectResponse(web_origin() + redirect_path(pending['redirect']), status_code=302,
                                    headers={'Cache-Control': 'no-store'})
        response.delete_cookie(STATE_COOKIE, path='/', httponly=True,
                               secure=cookie_secure(request), samesite='lax')
        issue_session(store, user, request, response)
        return response
