"""Accounts on the same durable database as cases; no second storage configuration.

Messages remain in the case JSON, but have a separate atomic mutation seam:
communication does not advance the content/workflow CAS version. Whole-case
writers preserve the current thread under their lock. These tables contain only
accounts, hashed sessions, short-lived OAuth exchanges, hashed rate-limit keys and
account-relative application-list flags.
SQL is intentionally portable between SQLite and Postgres.
"""
from __future__ import annotations

import json
import time
from contextlib import closing, contextmanager
from types import SimpleNamespace
from typing import Callable, TypeVar

from .account_models import ApplicationPreferences, ApplicationPreferencesPatch, StoredMessage, User
from .access import authorize_case, enforce_stored_mutation
from .models import Case, now
from .draft_store import DraftWritesMixin

T = TypeVar('T')


def preserve_messages(case: Case, stored: str | dict) -> None:
    """Keep stored immutable messages/receipts, then append new workflow messages.

    A content snapshot can predate message-only writes at the same version. Its
    old thread must never replace the current one or undo another user's receipt.
    """
    data = json.loads(stored) if isinstance(stored, str) else stored
    messages = [StoredMessage.model_validate(message) for message in data.get('messages', [])]
    existing = {message.id for message in messages}
    case.messages = messages + [message for message in case.messages if message.id not in existing]


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
    'CREATE TABLE IF NOT EXISTS account_application_preferences ('
    'user_id TEXT NOT NULL REFERENCES account_users(id) ON DELETE CASCADE, '
    'application_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE, '
    'archived BOOLEAN NOT NULL DEFAULT FALSE CHECK (archived IN (FALSE, TRUE)), '
    'pinned BOOLEAN NOT NULL DEFAULT FALSE CHECK (pinned IN (FALSE, TRUE)), '
    'PRIMARY KEY(user_id, application_id))',
    'CREATE INDEX IF NOT EXISTS account_application_preferences_case '
    'ON account_application_preferences(application_id)',
    # Access codes the admin manages in the app. A code is stored only as its hash; a row with no hash holds the
    # limit or revocation of a code that lives in BATATIS_AI_ACCESS_CODES.
    'CREATE TABLE IF NOT EXISTS access_codes (name TEXT PRIMARY KEY, code_hash TEXT, max_users INTEGER, '
    'revoked BOOLEAN NOT NULL DEFAULT FALSE, created_at TEXT NOT NULL)',
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


class AccountsMixin(DraftWritesMixin):
    def mutate_messages(self, case_id: str, user: User, operation: Callable[[Case], T]) -> tuple[Case, T] | None:
        """Authorize and mutate only the thread under the case write lock.

        No content version is adopted or advanced. All other JSON fields come
        from the locked row, even if the operation changes its working copy.
        Missing/expired cases return None after committing retention cleanup.
        """
        with self.account_db() as db:
            column = 'data' if db.postgres else 'json'
            lock = ' FOR UPDATE' if db.postgres else ''
            row = db.execute(f'SELECT {column}, version FROM cases WHERE id=?' + lock, (case_id,)).fetchone()
            if row is None or self._purge_expired(db.con, case_id):
                return None
            data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            enforce_stored_mutation(data)
            case = authorize_case(Case.model_validate({**data, 'version': int(row[1])}), user, mode='message')
            result = operation(case)
            messages = [message.model_dump(mode='json') for message in case.messages]
            if messages != data.get('messages', []):
                previous_ids = {message.get('id') for message in data.get('messages', [])}
                if any(message.id not in previous_ids for message in case.messages):
                    case.updated_at = now()
                else:
                    case.updated_at = data.get('updated_at', case.updated_at)
                data = {**data, 'messages': messages, 'updated_at': case.updated_at}
                if db.postgres:
                    from psycopg.types.json import Jsonb
                    payload = Jsonb(data)
                else:
                    payload = json.dumps(data)
                db.execute(f'UPDATE cases SET {column}=?, updated_at=? WHERE id=?',
                           (payload, case.updated_at, case_id))
            return case, result

    def init_accounts(self, con):
        for statement in ACCOUNT_MIGRATIONS:
            con.execute(statement)

    def list_application_preferences(self, user_id: str) -> dict[str, ApplicationPreferences]:
        """Only the account's preferences for its currently owned applications."""
        with self.account_db() as db:
            owner = "c.data->>'owner_id'" if db.postgres else "json_extract(c.json, '$.owner_id')"
            rows = db.execute('SELECT p.application_id, p.archived, p.pinned '
                              'FROM account_application_preferences p JOIN cases c ON c.id=p.application_id '
                              f'WHERE p.user_id=? AND {owner}=?', (user_id, user_id)).fetchall()
        return {row[0]: ApplicationPreferences(archived=row[1], pinned=row[2]) for row in rows}

    def patch_application_preferences(self, application_id: str, user: User,
                                      changes: dict[str, bool]) -> ApplicationPreferences | None:
        """Authorize the locked current case and patch only the supplied flags.

        The case lock serializes this with deletion/ownership changes and other
        preference patches. No Case/User read-modify-write or session revocation.
        """
        from .access import authorize_application_preferences

        patch = ApplicationPreferencesPatch.model_validate(changes).model_dump(exclude_unset=True)
        with self.account_db() as db:
            column, lock = ('data', ' FOR UPDATE') if db.postgres else ('json', '')
            row = db.execute(f'SELECT {column} FROM cases WHERE id=?' + lock, (application_id,)).fetchone()
            if row is None or self._purge_expired(db.con, application_id):
                return None  # Commit an expiry deletion before the route reports 404.
            payload = row[0] if db.postgres else json.loads(row[0])
            authorize_application_preferences(SimpleNamespace(owner_id=payload.get('owner_id')), user)
            # Keep account deletion from racing the foreign-key insert. Role does not
            # affect ownership of list metadata; a reviewer can organize their own cases.
            account_lock = ' FOR KEY SHARE' if db.postgres else ''
            if db.execute('SELECT id FROM account_users WHERE id=?' + account_lock, (user.id,)).fetchone() is None:
                return None
            updates = ', '.join(f'{field}=excluded.{field}' for field in patch)
            saved = db.execute('INSERT INTO account_application_preferences '
                               '(user_id,application_id,archived,pinned) VALUES (?,?,?,?) '
                               f'ON CONFLICT(user_id,application_id) DO UPDATE SET {updates} '
                               'RETURNING archived,pinned',
                               (user.id, application_id, patch.get('archived', False), patch.get('pinned', False))).fetchone()
            return ApplicationPreferences(archived=saved[0], pinned=saved[1])

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

    def access_code_rows(self) -> list[dict]:
        with self.account_db() as db:
            rows = db.execute('SELECT name, code_hash, max_users, revoked, created_at FROM access_codes ORDER BY created_at, name').fetchall()
        return [{'name': r[0], 'code_hash': r[1], 'max_users': r[2], 'revoked': bool(r[3]), 'created_at': r[4]} for r in rows]

    def access_code(self, name: str) -> dict | None:
        return next((row for row in self.access_code_rows() if row['name'] == name), None)

    def access_code_by_hash(self, code_hash: str) -> dict | None:
        return next((row for row in self.access_code_rows() if row['code_hash'] == code_hash), None)

    def create_access_code(self, name: str, code_hash: str, max_users: int | None) -> bool:
        with self.account_db() as db:
            row = db.execute('INSERT INTO access_codes(name, code_hash, max_users, revoked, created_at) VALUES (?,?,?,?,?) '
                             'ON CONFLICT DO NOTHING RETURNING name', (name, code_hash, max_users, False, now())).fetchone()
        return row is not None

    def set_access_code(self, name: str, *, max_users: int | None, revoked: bool) -> None:
        """Writes the limit and revocation of a code, creating the hash-less row an environment code needs."""
        with self.account_db() as db:
            db.execute('INSERT INTO access_codes(name, code_hash, max_users, revoked, created_at) VALUES (?,?,?,?,?) '
                       'ON CONFLICT(name) DO UPDATE SET max_users=?, revoked=?',
                       (name, None, max_users, revoked, now(), max_users, revoked))

    def delete_access_code(self, name: str) -> bool:
        """Removes a managed code, in use or not, and drops it from every account that held it."""
        with self.account_db() as db:
            row = db.execute('DELETE FROM access_codes WHERE name=? AND code_hash IS NOT NULL RETURNING name', (name,)).fetchone()
            if row is None:
                return False
            for user_id, raw in db.execute('SELECT id, data FROM account_users').fetchall():
                payload = json.loads(raw)
                user = payload.get('user') or {}
                if user.get('ai_access') != name:
                    continue
                user['ai_access'] = None
                user['ai_access_fingerprint'] = None
                payload['user'] = user
                db.execute('UPDATE account_users SET data=? WHERE id=?', (json.dumps(payload), user_id))
        return True

    def accounts_using_code(self, name: str, *, excluding: str | None = None) -> list[User]:
        with self.account_db() as db:
            rows = db.execute('SELECT data FROM account_users').fetchall()
        users = (User.model_validate(json.loads(row[0])['user']) for row in rows)
        return [user for user in users if user.ai_access == name and user.id != excluding]

    def delete_all_accounts(self) -> dict:
        """Every account, with its sessions, sign-ins and application list flags. Applications keep no owner to find them."""
        with self.account_db() as db:
            counts = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                      for table in ('account_users', 'account_sessions', 'account_identities', 'account_oauth', 'account_rates')}
            legacy_installs = db.execute(
                "SELECT to_regclass('access_installs') IS NOT NULL" if db.postgres else
                "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='access_installs')"
            ).fetchone()[0]
            if legacy_installs:
                counts['access_installs'] = db.execute('SELECT COUNT(*) FROM access_installs').fetchone()[0]
                db.execute('DELETE FROM access_installs')
            for table in ('account_application_preferences', 'account_sessions', 'account_identities', 'account_oauth', 'account_rates',
                          'account_users'):
                db.execute(f'DELETE FROM {table}')
        return counts

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
