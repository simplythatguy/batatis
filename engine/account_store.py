"""Accounts on the same durable database as cases; no second storage configuration.

Case history/messages are part of the case JSON and its CAS transaction. These
tables contain only accounts, hashed sessions, short-lived OAuth exchanges and
hashed rate-limit keys. SQL is intentionally portable between SQLite and Postgres.
"""
from __future__ import annotations

import json
import time
from contextlib import closing, contextmanager
from types import SimpleNamespace

from .account_models import User

ACCOUNT_MIGRATIONS = (
    'CREATE TABLE IF NOT EXISTS account_users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, data TEXT NOT NULL)',
    'CREATE TABLE IF NOT EXISTS account_sessions (digest TEXT PRIMARY KEY, '
    'user_id TEXT NOT NULL REFERENCES account_users(id) ON DELETE CASCADE, expires_at DOUBLE PRECISION NOT NULL)',
    'CREATE INDEX IF NOT EXISTS account_sessions_expiry ON account_sessions(expires_at)',
    'CREATE INDEX IF NOT EXISTS account_sessions_user ON account_sessions(user_id)',
    'CREATE TABLE IF NOT EXISTS account_identities (provider TEXT NOT NULL, subject TEXT NOT NULL, '
    'user_id TEXT NOT NULL REFERENCES account_users(id) ON DELETE CASCADE, PRIMARY KEY(provider, subject))',
    'CREATE TABLE IF NOT EXISTS account_oauth (digest TEXT PRIMARY KEY, data TEXT NOT NULL, '
    'expires_at DOUBLE PRECISION NOT NULL)',
    'CREATE TABLE IF NOT EXISTS account_rates (bucket TEXT PRIMARY KEY, hits INTEGER NOT NULL, '
    'expires_at DOUBLE PRECISION NOT NULL)',
)


class DuplicateEmail(Exception):
    pass


class IdentityConflict(Exception):
    pass


class _DB:
    def __init__(self, con, postgres=False):
        self.con, self.postgres = con, postgres

    def execute(self, sql, params=()):
        return self.con.execute(sql.replace('?', '%s') if self.postgres else sql, params)


class AccountsMixin:
    def init_accounts(self, con):
        for statement in ACCOUNT_MIGRATIONS:
            con.execute(statement)

    def create_user(self, user: User, password: dict | None = None) -> bool:
        data = json.dumps({'user': user.model_dump(), 'password': password})
        with self.account_db() as db:
            row = db.execute('INSERT INTO account_users(id,email,data) VALUES (?,?,?) '
                             'ON CONFLICT DO NOTHING RETURNING id', (user.id, user.email, data)).fetchone()
        return row is not None

    def get_user(self, user_id: str) -> User | None:
        with self.account_db() as db:
            row = db.execute('SELECT data FROM account_users WHERE id=?', (user_id,)).fetchone()
        return User.model_validate(json.loads(row[0])['user']) if row else None

    def user_credentials(self, email: str) -> dict | None:
        with self.account_db() as db:
            row = db.execute('SELECT data FROM account_users WHERE email=?', (email,)).fetchone()
        return json.loads(row[0]) if row else None

    def update_user(self, user: User, *, revoke_sessions: bool = True):
        with self.account_db() as db:
            lock = ' FOR UPDATE' if db.postgres else ''
            row = db.execute('SELECT data FROM account_users WHERE id=?' + lock, (user.id,)).fetchone()
            data = json.loads(row[0])
            data['user'] = user.model_dump()
            db.execute('UPDATE account_users SET data=? WHERE id=?', (json.dumps(data), user.id))
            # A privilege change invalidates all prior sessions, including other devices.
            if revoke_sessions:
                db.execute('DELETE FROM account_sessions WHERE user_id=?', (user.id,))

    def save_session(self, digest: str, user_id: str, expires_at: float, old_digest: str | None = None):
        with self.account_db() as db:
            self._purge_accounts(db)
            if old_digest:
                db.execute('DELETE FROM account_sessions WHERE digest=?', (old_digest,))
            db.execute('INSERT INTO account_sessions(digest,user_id,expires_at) VALUES (?,?,?)',
                       (digest, user_id, expires_at))

    def session_user(self, digest: str, refresh_to: float) -> User | None:
        with self.account_db() as db:
            row = db.execute('UPDATE account_sessions SET expires_at=? WHERE digest=? AND expires_at>? '
                             'RETURNING user_id', (refresh_to, digest, time.time())).fetchone()
            if not row:
                db.execute('DELETE FROM account_sessions WHERE digest=?', (digest,))
                return None
            user = db.execute('SELECT data FROM account_users WHERE id=?', (row[0],)).fetchone()
        return User.model_validate(json.loads(user[0])['user']) if user else None

    def delete_session(self, digest: str):
        with self.account_db() as db:
            db.execute('DELETE FROM account_sessions WHERE digest=?', (digest,))

    def save_oauth(self, digest: str, data: dict, expires_at: float):
        with self.account_db() as db:
            self._purge_accounts(db)
            db.execute('INSERT INTO account_oauth(digest,data,expires_at) VALUES (?,?,?)',
                       (digest, json.dumps(data), expires_at))

    def consume_oauth(self, digest: str) -> dict | None:
        with self.account_db() as db:
            row = db.execute('DELETE FROM account_oauth WHERE digest=? RETURNING data,expires_at', (digest,)).fetchone()
        return json.loads(row[0]) if row and row[1] > time.time() else None

    def oauth_user(self, provider: str, subject: str, email: str, name: str) -> User:
        """Never link an existing password account by an asserted email (especially Microsoft)."""
        with self.account_db() as db:
            row = db.execute('SELECT u.data FROM account_identities i JOIN account_users u ON u.id=i.user_id '
                             'WHERE i.provider=? AND i.subject=?', (provider, subject)).fetchone()
            if row:
                return User.model_validate(json.loads(row[0])['user'])
            user = User(email=email, name=name)
            data = json.dumps({'user': user.model_dump(), 'password': None})
            inserted = db.execute('INSERT INTO account_users(id,email,data) VALUES (?,?,?) '
                                  'ON CONFLICT DO NOTHING RETURNING id', (user.id, email, data)).fetchone()
            if not inserted:
                # A simultaneous callback for the same subject may have finished.
                row = db.execute('SELECT u.data FROM account_identities i JOIN account_users u ON u.id=i.user_id '
                                 'WHERE i.provider=? AND i.subject=?', (provider, subject)).fetchone()
                if row:
                    return User.model_validate(json.loads(row[0])['user'])
                raise IdentityConflict()
            db.execute('INSERT INTO account_identities(provider,subject,user_id) VALUES (?,?,?)',
                       (provider, subject, user.id))
            return user

    def account_rate(self, bucket: str, limit: int, seconds: float) -> bool:
        stamp = time.time()
        with self.account_db() as db:
            db.execute('DELETE FROM account_rates WHERE expires_at<=?', (stamp,))
            row = db.execute('INSERT INTO account_rates(bucket,hits,expires_at) VALUES (?,1,?) '
                             'ON CONFLICT(bucket) DO UPDATE SET hits=account_rates.hits+1 '
                             'WHERE account_rates.hits<? RETURNING hits', (bucket, stamp + seconds, limit)).fetchone()
        return limit > 0 and row is not None

    def _purge_accounts(self, db):
        stamp = time.time()
        for table in ('account_sessions', 'account_oauth', 'account_rates'):
            db.execute(f'DELETE FROM {table} WHERE expires_at<=?', (stamp,))


class FileAccountsMixin(AccountsMixin):
    def access_record(self, case_id: str):
        with self.account_db() as db:
            row = db.execute("SELECT json_extract(json,'$.owner_id'), json_extract(json,'$.authority'), "
                             "COALESCE(json_extract(json,'$.status'),'draft') FROM cases WHERE id=?",
                             (case_id,)).fetchone()
        return SimpleNamespace(owner_id=row[0], authority=row[1], status=row[2]) if row else None

    def list_applications(self, *, owner_id: str | None = None, authority: str | None = None):
        field, value = ('owner_id', owner_id) if owner_id is not None else ('authority', authority)
        visible = (" AND json_extract(json, '$.owner_id') IS NOT NULL AND "
                   "json_extract(json, '$.status') IN ('submitted','in_review','returned','accepted','refused')"
                   if owner_id is None else '')
        with self.account_db() as db:
            rows = db.execute(f"SELECT id FROM cases WHERE json_extract(json, '$.{field}')=? "
                              + visible + ' ORDER BY updated_at DESC, id DESC', (value,)).fetchall()
        return [case for row in rows if (case := self.get(row[0])) is not None]

    @contextmanager
    def account_db(self):
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            yield _DB(con)


class PostgresAccountsMixin(AccountsMixin):
    def access_record(self, case_id: str):
        with self.account_db() as db:
            row = db.execute("SELECT data->>'owner_id', data->>'authority', "
                             "COALESCE(data->>'status','draft') FROM cases WHERE id=?", (case_id,)).fetchone()
        return SimpleNamespace(owner_id=row[0], authority=row[1], status=row[2]) if row else None

    def list_applications(self, *, owner_id: str | None = None, authority: str | None = None):
        field, value = ('owner_id', owner_id) if owner_id is not None else ('authority', authority)
        visible = (" AND data->>'owner_id' IS NOT NULL AND "
                   "data->>'status' IN ('submitted','in_review','returned','accepted','refused')"
                   if owner_id is None else '')
        with self.account_db() as db:
            rows = db.execute(f"SELECT id FROM cases WHERE data->>'{field}'=? "
                              + visible + ' ORDER BY updated_at DESC, id DESC', (value,)).fetchall()
        return [case for row in rows if (case := self.get(row[0])) is not None]

    @contextmanager
    def account_db(self):
        with self._conn() as con:
            yield _DB(con, postgres=True)
