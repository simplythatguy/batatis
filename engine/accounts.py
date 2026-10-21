"""Credentials, cookie sessions and the reviewer-seeding CLI. Never log input."""
from __future__ import annotations

import argparse
import hashlib
import re
import secrets
import time

from fastapi import HTTPException, Request, Response

from .account_models import Authority, User
from .llm_gate import client_ip_from

COOKIE = 'batatis_session'
SESSION_SECONDS = 30 * 24 * 60 * 60
SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN = 2**17, 8, 1, 64


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def email_address(raw: str) -> str:
    value = raw.strip().casefold()
    if len(value) > 254 or not re.fullmatch(r'[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+', value):
        raise ValueError('Enter a valid email address')
    return value


def password_hash(password: str, salt: bytes | None = None) -> dict:
    salt = salt or secrets.token_bytes(32)
    value = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                           dklen=SCRYPT_DKLEN, maxmem=256 * 1024 * 1024)
    return {'salt': salt.hex(), 'hash': value.hex(), 'n': SCRYPT_N, 'r': SCRYPT_R, 'p': SCRYPT_P,
            'dklen': SCRYPT_DKLEN}


def password_matches(password: str, stored: dict | None) -> bool:
    # An absent account or OAuth-only account pays the same hashing cost.
    salt = bytes.fromhex(stored['salt']) if stored else b'\x00' * 32
    actual = password_hash(password, salt)['hash']
    return secrets.compare_digest(actual, stored['hash'] if stored else '0' * 128) and stored is not None


def cookie_secure(request: Request) -> bool:
    return request.url.hostname not in ('localhost', '127.0.0.1', '::1')


def set_cookie(response: Response, request: Request, token: str):
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=cookie_secure(request), samesite='lax', path='/')
    response.headers['Cache-Control'] = 'no-store'


def issue_session(store, user: User, request: Request, response: Response):
    token = secrets.token_urlsafe(32)
    old = request.cookies.get(COOKIE)
    store.save_session(digest(token), user.id, time.time() + SESSION_SECONDS, digest(old) if old else None)
    set_cookie(response, request, token)


def optional_user(request: Request, response: Response, store_factory) -> User | None:
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 128:
        return None
    user = store_factory().session_user(digest(token), time.time() + SESSION_SECONDS)
    if user:
        set_cookie(response, request, token)
    return user


def require_user(request: Request) -> User:
    user = getattr(request.state, 'user', None)
    if user is None:
        raise HTTPException(401, 'Sign in to continue')
    return user


def limit_auth(store, request: Request, operation: str, email: str = ''):
    import os
    limit = int(os.environ.get('BATATIS_AUTH_RATE_LIMIT') or '10')
    window = float(os.environ.get('BATATIS_AUTH_RATE_WINDOW_SECONDS') or '600')
    key = digest(operation + ':' + client_ip_from(request) + ':' + email)
    if not store.account_rate(key, limit, window):
        raise HTTPException(429, 'Too many attempts; try again later', headers={'Retry-After': str(int(window))})


def main(argv=None):
    parser = argparse.ArgumentParser(description='Seed a reviewer; the password is printed once, never logged.')
    commands = parser.add_subparsers(dest='command', required=True)
    seed = commands.add_parser('create-reviewer')
    seed.add_argument('--email', required=True, type=email_address)
    seed.add_argument('--name', required=True)
    seed.add_argument('--authority', required=True, choices=Authority.__args__)
    args = parser.parse_args(argv)
    from .store import open_store
    password = secrets.token_urlsafe(24)
    user = User(email=args.email, name=args.name.strip(), role='reviewer', authority=args.authority, onboarded=True)
    if not user.name or not open_store().create_user(user, password_hash(password)):
        parser.error('Could not create reviewer (check the name or an existing account)')
    print(password)


if __name__ == '__main__':
    main()
