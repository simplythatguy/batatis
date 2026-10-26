"""Desktop workspaces: the normal local one and Local development, each its own SQLite file.

Local development seeds one applicant and one reviewer per supported authority into the same
database, with no password, OAuth identity, case or applicant fact. Only the desktop host can pick
which of them is signed in, through a private control frame; nothing over HTTP selects an actor.
Every case rule (ownership, authority, claims, self-review exclusion, retention) is the engine's own.
"""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, get_args

from ..account_models import Authority, User
from ..accounts import SESSION_SECONDS, SESSION_TOKEN, digest
from ..models_ids import now
from ..store import CaseStore
from ..uploads import MULTIPART_MAX_OVERHEAD_BYTES, PDF_MAX_BYTES
from .bridge import ControlError

Kind = Literal['local', 'dev']
SCHEMA = '1'
BODY_LIMIT = PDF_MAX_BYTES + MULTIPART_MAX_OVERHEAD_BYTES
# Hosted and server settings that must never reach a desktop engine.
FORBIDDEN_ENV = ('VERCEL', 'DATABASE_URL', 'TEST_DATABASE_URL', 'BATATIS_REVIEWER_CODES')
DEV_ACCOUNT_ROUTES = re.compile(r'^(?:/api)?/auth/(?:signup|login|logout|onboarding|oauth(?:/.*)?)/?$')
DEV_ACCOUNT_DETAIL = 'Local development uses its test people. Switch person in quick settings.'


class WorkspaceRefused(Exception):
    """The database or configuration is not a desktop workspace of this kind. The text has no path."""


@dataclass(frozen=True)
class Config:
    kind: Kind
    cases: Path
    codedb: Path


@dataclass(frozen=True)
class Profile:
    profile: str
    user_id: str
    kind: Literal['applicant', 'reviewer']
    authority: str | None
    name: str


def config_from_env(env: Mapping[str, str]) -> Config:
    """The host passes the workspace kind and both database paths. Hosted settings are refused."""
    present = [name for name in FORBIDDEN_ENV if env.get(name)]
    if present:
        raise WorkspaceRefused('hosted configuration is not allowed in a desktop engine: ' + ', '.join(present))
    if (env.get('BATATIS_STORE') or 'file').strip().lower() not in ('file', 'sqlite'):
        raise WorkspaceRefused('a desktop workspace uses its own SQLite file')
    kind = env.get('BATATIS_DESKTOP_WORKSPACE')
    if kind not in get_args(Kind):
        raise WorkspaceRefused('BATATIS_DESKTOP_WORKSPACE must be local or dev')
    cases, codedb = env.get('BATATIS_CASES'), env.get('BATATIS_CODEDB')
    if not cases or not codedb or not Path(cases).is_absolute() or not Path(codedb).is_absolute():
        raise WorkspaceRefused('BATATIS_CASES and BATATIS_CODEDB must be absolute paths')
    return Config(kind=kind, cases=Path(cases), codedb=Path(codedb))


def dev_profiles_wanted() -> list[tuple[str, Literal['applicant', 'reviewer'], str | None, str]]:
    """Derived from the engine's own Authority list, so a new authority gets its reviewer."""
    wanted: list[tuple[str, Literal['applicant', 'reviewer'], str | None, str]] = [
        ('applicant', 'applicant', None, 'Test applicant')]
    for authority in get_args(Authority):
        wanted.append((f'reviewer:{authority}', 'reviewer', authority, f'Test reviewer, {authority.title()}'))
    return wanted


class Workspace:
    def __init__(self, config: Config):
        self.config = config
        self.store = CaseStore(config.cases)
        self.id = self._adopt()
        self.profiles: dict[str, Profile] = self._seed() if config.kind == 'dev' else {}

    def _adopt(self) -> str:
        with self.store.account_db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS desktop_workspace (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            marker = dict(db.execute('SELECT key, value FROM desktop_workspace').fetchall())
            if not marker:
                used = (db.execute('SELECT 1 FROM cases LIMIT 1').fetchone()
                        or db.execute('SELECT 1 FROM account_users LIMIT 1').fetchone())
                if used:
                    raise WorkspaceRefused('this database has data but is not a desktop workspace')
                marker = {'kind': self.config.kind, 'workspace_id': uuid.uuid4().hex, 'schema': SCHEMA,
                          'created_at': now()}
                for key, value in marker.items():
                    db.execute('INSERT INTO desktop_workspace(key, value) VALUES (?, ?)', (key, value))
            if marker.get('kind') != self.config.kind:
                raise WorkspaceRefused(f'this database belongs to the {marker.get("kind")} workspace')
            if marker.get('schema') != SCHEMA:
                raise WorkspaceRefused('this workspace was made by a newer version')
            return marker['workspace_id']

    def _seed(self) -> dict[str, Profile]:
        """Idempotent: a profile row names its user id before the user exists, so a crash between the
        two inserts converges on the next start instead of leaving a second account behind."""
        with self.store.account_db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS desktop_dev_profiles (profile_id TEXT PRIMARY KEY, '
                       'user_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, authority TEXT)')
            for profile, kind, authority, _ in dev_profiles_wanted():
                db.execute('INSERT INTO desktop_dev_profiles(profile_id, user_id, kind, authority) '
                           'VALUES (?, ?, ?, ?) ON CONFLICT(profile_id) DO NOTHING',
                           (profile, f'user_{uuid.uuid4().hex}', kind, authority))
            rows = {row[0]: row[1:] for row in db.execute(
                'SELECT profile_id, user_id, kind, authority FROM desktop_dev_profiles').fetchall()}
        profiles = {}
        for profile, kind, authority, name in dev_profiles_wanted():
            user_id, stored_kind, stored_authority = rows[profile]
            if (stored_kind, stored_authority) != (kind, authority):
                raise WorkspaceRefused('a test person in this workspace changed')
            user = self.store.get_user(user_id)
            if user is None:
                slug = profile.replace(':', '.')
                user = User(id=user_id, email=f'{slug}@local-development.invalid', name=name, role=kind,
                            authority=authority, onboarded=True)
                if not self.store.create_user(user):
                    raise WorkspaceRefused('a test person could not be created')
            if user.role != kind or user.authority != authority or not user.onboarded:
                raise WorkspaceRefused('a test person in this workspace changed')
            profiles[profile] = Profile(profile, user.id, kind, authority, user.name)
        return profiles

    def hello(self) -> dict:
        from codedb.build import BUILD_VERSION
        hello = {'workspace': {'kind': self.config.kind, 'id': self.id},
                 'codedb': {'available': self.config.codedb.is_file(), 'build': codedb_build(self.config.codedb),
                            'expectedBuild': BUILD_VERSION}}
        if self.config.kind == 'dev':
            hello['dev'] = {'profiles': [{'profile': p.profile, 'userId': p.user_id, 'name': p.name,
                                          'kind': p.kind, 'authority': p.authority}
                                         for p in self.profiles.values()]}
        return hello

    async def control(self, op: str, args: dict) -> dict:
        if op != 'dev.session' or self.config.kind != 'dev':
            raise ControlError('unavailable')
        profile = self.profiles.get(args.get('profile'))
        if profile is None:
            raise ControlError('unknown-profile')
        revoke = args.get('revoke')
        if isinstance(revoke, str) and SESSION_TOKEN.fullmatch(revoke):
            self.store.delete_session(digest(revoke))
        token = secrets.token_urlsafe(32)
        self.store.save_session(digest(token), profile.user_id, time.time() + SESSION_SECONDS)
        return {'token': token, 'profile': profile.profile, 'userId': profile.user_id}

    def app(self):
        from ..api import create_app
        app = create_app(store=self.store)
        return DevAccountGuard(app) if self.config.kind == 'dev' else app


def codedb_build(path: Path) -> str | None:
    """The build version recorded in a code database, or None when it is absent or unreadable."""
    if not path.is_file():
        return None
    try:
        with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)) as con:
            row = con.execute("SELECT value FROM meta WHERE key='build_version'").fetchone()
    except sqlite3.Error:
        return None
    return row[0] if row else None


class DevAccountGuard:
    """Test people never sign up, sign in, sign out or change role; the host switches them."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and DEV_ACCOUNT_ROUTES.match(scope.get('path') or ''):
            body = json.dumps({'detail': DEV_ACCOUNT_DETAIL}).encode()
            await send({'type': 'http.response.start', 'status': 403,
                        'headers': [(b'content-type', b'application/json'), (b'cache-control', b'no-store'),
                                    (b'content-length', str(len(body)).encode())]})
            await send({'type': 'http.response.body', 'body': body})
            return
        await self.app(scope, receive, send)
