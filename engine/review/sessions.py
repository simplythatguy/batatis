"""Versioned package-review sessions in their own table, next to the case store.

Rows live in the same SQLite file or PostgreSQL database as the cases. A
case-linked package is removed when its case is gone (deleted or purged by
retention); a standalone upload package follows the same creation-based
retention as cases. The sweep runs on every package-review access.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import closing

from ..models_review import ReviewSession
from ..store import retention_cutoff

MAX_SESSIONS = 50
_DDL = ('CREATE TABLE IF NOT EXISTS package_review_sessions (package_id TEXT NOT NULL, version INTEGER NOT NULL, '
        'case_id TEXT, authority TEXT NOT NULL, created_at TEXT NOT NULL, json TEXT NOT NULL, '
        'PRIMARY KEY (package_id, version))')
# The officer's own statement that the close-out copy went to the Council. Batatis never sends it.
_CLOSEOUT_DDL = ('CREATE TABLE IF NOT EXISTS package_review_closeouts (case_id TEXT PRIMARY KEY, '
                 'decided_at TEXT NOT NULL, sent_at TEXT NOT NULL, sent_by_name TEXT NOT NULL)')


class SessionConflict(Exception):
    pass


class _Sqlite:
    def __init__(self, path):
        self.path = path
        with closing(self._connect()) as con, con:
            con.execute(_DDL)
            con.execute(_CLOSEOUT_DDL)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def _sweep(self, con):
        con.execute('DELETE FROM package_review_sessions WHERE case_id IS NOT NULL AND case_id NOT IN '
                    '(SELECT id FROM cases)')
        con.execute('DELETE FROM package_review_sessions WHERE case_id IS NULL AND created_at < ?',
                    (retention_cutoff(),))
        con.execute('DELETE FROM package_review_closeouts WHERE case_id NOT IN (SELECT id FROM cases)')

    def closeout(self, case_id):
        with closing(self._connect()) as con, con:
            self._sweep(con)
            return con.execute('SELECT decided_at, sent_at, sent_by_name FROM package_review_closeouts '
                               'WHERE case_id=?', (case_id,)).fetchone()

    def set_closeout(self, case_id, decided_at, sent_at, sent_by_name):
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT decided_at FROM package_review_closeouts WHERE case_id=?', (case_id,)).fetchone()
            if row is not None and row[0] == decided_at:
                raise SessionConflict(case_id)
            con.execute('INSERT OR REPLACE INTO package_review_closeouts VALUES (?,?,?,?)',
                        (case_id, decided_at, sent_at, sent_by_name))

    def rows(self, package_id):
        with closing(self._connect()) as con, con:
            self._sweep(con)
            return [r[0] for r in con.execute('SELECT json FROM package_review_sessions WHERE package_id=? '
                                              'ORDER BY version', (package_id,))]

    def insert(self, session: ReviewSession):
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            self._sweep(con)
            latest = con.execute('SELECT MAX(version) FROM package_review_sessions WHERE package_id=?',
                                 (session.package_id,)).fetchone()[0] or 0
            if latest != session.version - 1:
                raise SessionConflict(session.package_id)
            con.execute('INSERT INTO package_review_sessions VALUES (?,?,?,?,?,?)',
                        (session.package_id, session.version, session.case_id, session.authority,
                         session.created_at, session.model_dump_json()))

    def update(self, session: ReviewSession, expected: str):
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            cur = con.execute('UPDATE package_review_sessions SET json=? WHERE package_id=? AND version=? AND json=?',
                              (session.model_dump_json(), session.package_id, session.version, expected))
            if cur.rowcount != 1:
                raise SessionConflict(session.package_id)


class _Postgres:
    def __init__(self, url):
        import psycopg
        self._psycopg = psycopg
        self.url = url
        with closing(self._connect()) as con, con:
            con.execute('SELECT pg_advisory_xact_lock(727275)')
            con.execute(_DDL)
            con.execute(_CLOSEOUT_DDL)

    def _connect(self):
        return self._psycopg.connect(self.url, autocommit=False, connect_timeout=10)

    def _sweep(self, con):
        con.execute('DELETE FROM package_review_sessions WHERE case_id IS NOT NULL AND case_id NOT IN '
                    '(SELECT id FROM cases)')
        con.execute('DELETE FROM package_review_sessions WHERE case_id IS NULL AND created_at < %s',
                    (retention_cutoff(),))
        con.execute('DELETE FROM package_review_closeouts WHERE case_id NOT IN (SELECT id FROM cases)')

    def closeout(self, case_id):
        with closing(self._connect()) as con, con:
            self._sweep(con)
            return con.execute('SELECT decided_at, sent_at, sent_by_name FROM package_review_closeouts '
                               'WHERE case_id=%s', (case_id,)).fetchone()

    def set_closeout(self, case_id, decided_at, sent_at, sent_by_name):
        with closing(self._connect()) as con, con:
            con.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('closeout:' + case_id,))
            row = con.execute('SELECT decided_at FROM package_review_closeouts WHERE case_id=%s',
                              (case_id,)).fetchone()
            if row is not None and row[0] == decided_at:
                raise SessionConflict(case_id)
            con.execute('INSERT INTO package_review_closeouts VALUES (%s,%s,%s,%s) ON CONFLICT (case_id) DO UPDATE '
                        'SET decided_at=EXCLUDED.decided_at, sent_at=EXCLUDED.sent_at, '
                        'sent_by_name=EXCLUDED.sent_by_name', (case_id, decided_at, sent_at, sent_by_name))

    def rows(self, package_id):
        with closing(self._connect()) as con, con:
            self._sweep(con)
            return [r[0] for r in con.execute('SELECT json FROM package_review_sessions WHERE package_id=%s '
                                              'ORDER BY version', (package_id,)).fetchall()]

    def insert(self, session: ReviewSession):
        with closing(self._connect()) as con, con:
            con.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (session.package_id,))
            self._sweep(con)
            latest = con.execute('SELECT MAX(version) FROM package_review_sessions WHERE package_id=%s',
                                 (session.package_id,)).fetchone()[0] or 0
            if latest != session.version - 1:
                raise SessionConflict(session.package_id)
            con.execute('INSERT INTO package_review_sessions VALUES (%s,%s,%s,%s,%s,%s)',
                        (session.package_id, session.version, session.case_id, session.authority,
                         session.created_at, session.model_dump_json()))

    def update(self, session: ReviewSession, expected: str):
        with closing(self._connect()) as con, con:
            cur = con.execute('UPDATE package_review_sessions SET json=%s WHERE package_id=%s AND version=%s '
                              'AND json=%s', (session.model_dump_json(), session.package_id, session.version, expected))
            if cur.rowcount != 1:
                raise SessionConflict(session.package_id)


class _Memory:
    """For stores without a database (test doubles). Not durable."""

    def __init__(self):
        self.data: dict[str, dict[int, str]] = {}
        self.closeouts: dict[str, tuple] = {}
        self.lock = threading.Lock()

    def closeout(self, case_id):
        return self.closeouts.get(case_id)

    def set_closeout(self, case_id, decided_at, sent_at, sent_by_name):
        with self.lock:
            if self.closeouts.get(case_id, (None,))[0] == decided_at:
                raise SessionConflict(case_id)
            self.closeouts[case_id] = (decided_at, sent_at, sent_by_name)

    def rows(self, package_id):
        return [self.data.get(package_id, {})[v] for v in sorted(self.data.get(package_id, {}))]

    def insert(self, session):
        with self.lock:
            versions = self.data.setdefault(session.package_id, {})
            if (max(versions) if versions else 0) != session.version - 1:
                raise SessionConflict(session.package_id)
            versions[session.version] = session.model_dump_json()

    def update(self, session, expected):
        with self.lock:
            if self.data.get(session.package_id, {}).get(session.version) != expected:
                raise SessionConflict(session.package_id)
            self.data[session.package_id][session.version] = session.model_dump_json()


_BACKENDS: dict[tuple, object] = {}
_LOCK = threading.Lock()


def backend_for(store):
    if getattr(store, 'path', None) is not None and hasattr(store, '_connect'):
        key = ('sqlite', str(store.path))
        factory = lambda: _Sqlite(store.path)  # noqa: E731
    elif getattr(store, 'url', None):
        key = ('postgres', store.url)
        factory = lambda: _Postgres(store.url)  # noqa: E731
    else:
        key = ('memory', id(store))
        factory = _Memory
    with _LOCK:
        if key not in _BACKENDS:
            _BACKENDS[key] = factory()
        return _BACKENDS[key]


class Sessions:
    def __init__(self, store):
        self.db = backend_for(store)

    def list(self, package_id: str) -> list[ReviewSession]:
        return [ReviewSession.model_validate_json(row) for row in self.db.rows(package_id)]

    def get(self, package_id: str, version: int) -> tuple[ReviewSession, str] | None:
        for row in self.db.rows(package_id):
            session = ReviewSession.model_validate_json(row)
            if session.version == version:
                return session, row
        return None

    def add(self, session: ReviewSession) -> ReviewSession:
        if session.version > MAX_SESSIONS:
            raise SessionConflict(session.package_id)
        self.db.insert(session)
        return session

    def closeout(self, case_id: str):
        """(decided_at, sent_at, sent_by_name) of the officer's recorded close-out, or None."""
        return self.db.closeout(case_id)

    def record_closeout(self, case_id: str, decided_at: str, sent_at: str, sent_by_name: str) -> None:
        self.db.set_closeout(case_id, decided_at, sent_at, sent_by_name)

    def replace(self, session: ReviewSession, expected_json: str) -> ReviewSession:
        self.db.update(session, expected_json)
        return session


