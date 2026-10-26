"""Versioned package-review sessions in their own table, next to the case store.

Rows live in the same SQLite file or PostgreSQL database as the cases. A
case-linked package is removed when its case is gone (deleted or purged by
retention); a standalone upload package follows the same creation-based
retention as cases. The sweep runs on every package-review access and after every
retention purge, so nothing outlives its case.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import NamedTuple
from contextlib import closing

from ..models_review import ReviewSession
from ..store import retention_cutoff

MAX_SESSIONS = 50
_DDL = ('CREATE TABLE IF NOT EXISTS package_review_sessions (package_id TEXT NOT NULL, version INTEGER NOT NULL, '
        'case_id TEXT, authority TEXT NOT NULL, created_at TEXT NOT NULL, json TEXT NOT NULL, '
        'rulebook_json TEXT, PRIMARY KEY (package_id, version))')
# The officer's own statement that the close-out copy went to the Council. Batatis never sends it.
_CLOSEOUT_DDL = ('CREATE TABLE IF NOT EXISTS package_review_closeouts (case_id TEXT PRIMARY KEY, '
                 'decided_at TEXT NOT NULL, sent_at TEXT NOT NULL, sent_by_name TEXT NOT NULL, '
                 'issued_on TEXT, issued_by_name TEXT)')


class SessionConflict(Exception):
    pass


class CloseoutRecord(NamedTuple):
    decided_at: str
    sent_at: str
    sent_by_name: str
    issued_on: str | None = None
    issued_by_name: str | None = None


def _closeout_change(previous, decided_at, kind, at, by_name):
    record = CloseoutRecord(*previous) if previous and previous[0] == decided_at else CloseoutRecord(decided_at, '', '')
    if kind == 'issue':
        if record.issued_on:
            raise SessionConflict('Issuance already recorded')
        return record._replace(issued_on=at, issued_by_name=by_name)
    if not record.issued_on or record.sent_at:
        raise SessionConflict('Record issuance before sending, and record sending only once')
    return record._replace(sent_at=at, sent_by_name=by_name)


def _check_session_write(session, case_data):
    if not case_data:
        return
    data = json.loads(case_data) if isinstance(case_data, str) else case_data
    committed = any(m['id'] == return_message_id(session.version) for m in data.get('messages', []))
    if committed:
        if session.information_request.message_id != return_message_id(session.version):
            raise SessionConflict(session.package_id)
    elif data.get('status') in {'accepted', 'refused', 'returned', 'withdrawn'}:
        raise SessionConflict(session.package_id)


def _check_new_session(previous, case_data):
    if previous is None:
        return
    session = ReviewSession.model_validate_json(previous)
    request = session.information_request
    if request.sent_at and not request.message_id:
        data = json.loads(case_data) if isinstance(case_data, str) else case_data or {}
        if not any(m['id'] == return_message_id(session.version) for m in data.get('messages', [])):
            raise SessionConflict(session.package_id)


class _Sqlite:
    def __init__(self, path):
        self.path = path
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            con.execute(_DDL)
            session_columns = {row[1] for row in con.execute('PRAGMA table_info(package_review_sessions)')}
            if 'rulebook_json' not in session_columns:
                con.execute('ALTER TABLE package_review_sessions ADD COLUMN rulebook_json TEXT')
            con.execute(_CLOSEOUT_DDL)
            columns = {row[1] for row in con.execute('PRAGMA table_info(package_review_closeouts)')}
            for column in ('issued_on', 'issued_by_name'):
                if column not in columns:
                    con.execute(f'ALTER TABLE package_review_closeouts ADD COLUMN {column} TEXT')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def sweep(self):
        with closing(self._connect()) as con, con:
            self._sweep(con)

    def _sweep(self, con):
        con.execute('DELETE FROM package_review_sessions WHERE case_id IS NOT NULL AND case_id NOT IN '
                    '(SELECT id FROM cases)')
        con.execute('DELETE FROM package_review_sessions WHERE case_id IS NULL AND created_at < ?',
                    (retention_cutoff(),))
        con.execute('DELETE FROM package_review_closeouts WHERE case_id NOT IN (SELECT id FROM cases)')

    def closeout(self, case_id):
        with closing(self._connect()) as con, con:
            self._sweep(con)
            return con.execute('SELECT decided_at, sent_at, sent_by_name, issued_on, issued_by_name FROM package_review_closeouts '
                               'WHERE case_id=?', (case_id,)).fetchone()

    def change_closeout(self, case_id, decided_at, kind, at, by_name):
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT decided_at, sent_at, sent_by_name, issued_on, issued_by_name '
                              'FROM package_review_closeouts WHERE case_id=?', (case_id,)).fetchone()
            record = _closeout_change(row, decided_at, kind, at, by_name)
            con.execute('INSERT INTO package_review_closeouts '
                        '(case_id, decided_at, sent_at, sent_by_name, issued_on, issued_by_name) VALUES (?,?,?,?,?,?) '
                        'ON CONFLICT(case_id) DO UPDATE SET decided_at=excluded.decided_at, sent_at=excluded.sent_at, '
                        'sent_by_name=excluded.sent_by_name, issued_on=excluded.issued_on, issued_by_name=excluded.issued_by_name',
                        (case_id, *record))

    def rulebook(self, package_id, version):
        with closing(self._connect()) as con:
            row = con.execute('SELECT rulebook_json FROM package_review_sessions WHERE package_id=? AND version=?',
                              (package_id, version)).fetchone()
            return row[0] if row else None

    def rows(self, package_id):
        with closing(self._connect()) as con, con:
            self._sweep(con)
            return [r[0] for r in con.execute('SELECT json FROM package_review_sessions WHERE package_id=? '
                                              'ORDER BY version', (package_id,))]

    def insert(self, session: ReviewSession, rulebook=None):
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            self._sweep(con)
            latest = con.execute('SELECT MAX(version) FROM package_review_sessions WHERE package_id=?',
                                 (session.package_id,)).fetchone()[0] or 0
            if latest != session.version - 1:
                raise SessionConflict(session.package_id)
            if latest:
                previous = con.execute('SELECT json FROM package_review_sessions WHERE package_id=? AND version=?',
                                       (session.package_id, latest)).fetchone()
                case = con.execute('SELECT json FROM cases WHERE id=?', (session.case_id,)).fetchone() if session.case_id else None
                _check_new_session(previous[0], case[0] if case else None)
            con.execute('INSERT INTO package_review_sessions '
                        '(package_id, version, case_id, authority, created_at, json, rulebook_json) VALUES (?,?,?,?,?,?,?)',
                        (session.package_id, session.version, session.case_id, session.authority,
                         session.created_at, session.model_dump_json(), rulebook))

    def update(self, session: ReviewSession, expected: str, rulebook=None):
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            case = con.execute('SELECT json FROM cases WHERE id=?', (session.case_id,)).fetchone() if session.case_id else None
            _check_session_write(session, case[0] if case else None)
            cur = con.execute('UPDATE package_review_sessions SET json=?, rulebook_json=COALESCE(?, rulebook_json) WHERE package_id=? AND version=? AND json=? '
                              'AND version=(SELECT MAX(version) FROM package_review_sessions WHERE package_id=?)',
                              (session.model_dump_json(), rulebook, session.package_id, session.version, expected, session.package_id))
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
            con.execute('ALTER TABLE package_review_sessions ADD COLUMN IF NOT EXISTS rulebook_json TEXT')
            con.execute(_CLOSEOUT_DDL)
            con.execute('ALTER TABLE package_review_closeouts ADD COLUMN IF NOT EXISTS issued_on TEXT')
            con.execute('ALTER TABLE package_review_closeouts ADD COLUMN IF NOT EXISTS issued_by_name TEXT')

    def _connect(self):
        return self._psycopg.connect(self.url, autocommit=False, connect_timeout=10)

    def sweep(self):
        with closing(self._connect()) as con, con:
            self._sweep(con)

    def _sweep(self, con):
        con.execute('DELETE FROM package_review_sessions WHERE case_id IS NOT NULL AND case_id NOT IN '
                    '(SELECT id FROM cases)')
        con.execute('DELETE FROM package_review_sessions WHERE case_id IS NULL AND created_at < %s',
                    (retention_cutoff(),))
        con.execute('DELETE FROM package_review_closeouts WHERE case_id NOT IN (SELECT id FROM cases)')

    def closeout(self, case_id):
        with closing(self._connect()) as con, con:
            self._sweep(con)
            return con.execute('SELECT decided_at, sent_at, sent_by_name, issued_on, issued_by_name FROM package_review_closeouts '
                               'WHERE case_id=%s', (case_id,)).fetchone()

    def change_closeout(self, case_id, decided_at, kind, at, by_name):
        with closing(self._connect()) as con, con:
            con.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('closeout:' + case_id,))
            row = con.execute('SELECT decided_at, sent_at, sent_by_name, issued_on, issued_by_name '
                              'FROM package_review_closeouts WHERE case_id=%s', (case_id,)).fetchone()
            record = _closeout_change(row, decided_at, kind, at, by_name)
            con.execute('INSERT INTO package_review_closeouts '
                        '(case_id, decided_at, sent_at, sent_by_name, issued_on, issued_by_name) VALUES (%s,%s,%s,%s,%s,%s) '
                        'ON CONFLICT (case_id) DO UPDATE SET decided_at=EXCLUDED.decided_at, sent_at=EXCLUDED.sent_at, '
                        'sent_by_name=EXCLUDED.sent_by_name, issued_on=EXCLUDED.issued_on, issued_by_name=EXCLUDED.issued_by_name',
                        (case_id, *record))

    def rulebook(self, package_id, version):
        with closing(self._connect()) as con:
            row = con.execute('SELECT rulebook_json FROM package_review_sessions WHERE package_id=%s AND version=%s',
                              (package_id, version)).fetchone()
            return row[0] if row else None

    def rows(self, package_id):
        with closing(self._connect()) as con, con:
            self._sweep(con)
            return [r[0] for r in con.execute('SELECT json FROM package_review_sessions WHERE package_id=%s '
                                              'ORDER BY version', (package_id,)).fetchall()]

    def insert(self, session: ReviewSession, rulebook=None):
        with closing(self._connect()) as con, con:
            con.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (session.package_id,))
            self._sweep(con)
            latest = con.execute('SELECT MAX(version) FROM package_review_sessions WHERE package_id=%s',
                                 (session.package_id,)).fetchone()[0] or 0
            if latest != session.version - 1:
                raise SessionConflict(session.package_id)
            if latest:
                previous = con.execute('SELECT json FROM package_review_sessions WHERE package_id=%s AND version=%s',
                                       (session.package_id, latest)).fetchone()
                case = con.execute('SELECT data FROM cases WHERE id=%s', (session.case_id,)).fetchone() if session.case_id else None
                _check_new_session(previous[0], case[0] if case else None)
            con.execute('INSERT INTO package_review_sessions '
                        '(package_id, version, case_id, authority, created_at, json, rulebook_json) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                        (session.package_id, session.version, session.case_id, session.authority,
                         session.created_at, session.model_dump_json(), rulebook))

    def update(self, session: ReviewSession, expected: str, rulebook=None):
        with closing(self._connect()) as con, con:
            con.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (session.package_id,))
            case = con.execute('SELECT data FROM cases WHERE id=%s', (session.case_id,)).fetchone() if session.case_id else None
            _check_session_write(session, case[0] if case else None)
            cur = con.execute('UPDATE package_review_sessions SET json=%s, rulebook_json=COALESCE(%s, rulebook_json) WHERE package_id=%s AND version=%s '
                              'AND json=%s AND version=(SELECT MAX(version) FROM package_review_sessions WHERE package_id=%s)',
                              (session.model_dump_json(), rulebook, session.package_id, session.version, expected, session.package_id))
            if cur.rowcount != 1:
                raise SessionConflict(session.package_id)


class _Memory:
    """For stores without a database (test doubles). Not durable."""

    def __init__(self):
        self.data: dict[str, dict[int, str]] = {}
        self.closeouts: dict[str, tuple] = {}
        self.rulebooks = {}
        self.lock = threading.Lock()

    def sweep(self):
        pass

    def closeout(self, case_id):
        return self.closeouts.get(case_id)

    def change_closeout(self, case_id, decided_at, kind, at, by_name):
        with self.lock:
            self.closeouts[case_id] = _closeout_change(self.closeouts.get(case_id), decided_at, kind, at, by_name)

    def rulebook(self, package_id, version):
        return self.rulebooks.get((package_id, version))

    def rows(self, package_id):
        return [self.data.get(package_id, {})[v] for v in sorted(self.data.get(package_id, {}))]

    def insert(self, session, rulebook=None):
        with self.lock:
            versions = self.data.setdefault(session.package_id, {})
            if (max(versions) if versions else 0) != session.version - 1:
                raise SessionConflict(session.package_id)
            versions[session.version] = session.model_dump_json()
            self.rulebooks[session.package_id, session.version] = rulebook

    def update(self, session, expected, rulebook=None):
        with self.lock:
            versions = self.data.get(session.package_id, {})
            if versions.get(session.version) != expected or session.version != max(versions, default=0):
                raise SessionConflict(session.package_id)
            self.data[session.package_id][session.version] = session.model_dump_json()
            if rulebook is not None:
                self.rulebooks[session.package_id, session.version] = rulebook


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


def return_message_id(version: int) -> str:
    # A case-scoped, durable link without adding a second decision/version contract.
    return f'msg_package_review_return_{version}'


class Sessions:
    def __init__(self, store):
        self.store = store
        self.db = backend_for(store)

    def _reconcile(self, session: ReviewSession) -> ReviewSession:
        if session.case_id is None:
            return session
        case = self.store.get(session.case_id)
        message = next((m for m in case.messages if m.id == return_message_id(session.version)
                        and m.kind == 'decision'), None) if case else None
        if message is None:
            return session
        # The case CAS is the commit point. This projection also works when session finalization writes fail.
        from ..routes_review import RETURN_TEXT
        sent = session.information_request.model_copy(update={'sent_at': message.created_at,
            'sent_by_name': message.author.name, 'message_id': message.id,
            'text': message.body.removeprefix(RETURN_TEXT + '\n\n')})
        return session.model_copy(update={'information_request': sent})

    def list(self, package_id: str) -> list[ReviewSession]:
        return [self._reconcile(ReviewSession.model_validate_json(row)) for row in self.db.rows(package_id)]

    def get(self, package_id: str, version: int) -> tuple[ReviewSession, str] | None:
        for row in self.db.rows(package_id):
            session = ReviewSession.model_validate_json(row)
            if session.version == version:
                return self._reconcile(session), row
        return None

    def add(self, session: ReviewSession, gaps=None) -> ReviewSession:
        if session.version > MAX_SESSIONS:
            raise SessionConflict(session.package_id)
        self.db.insert(session, self._gap_json(gaps))
        return session

    @staticmethod
    def _gap_json(gaps):
        return json.dumps([g.model_dump() for g in gaps if g.severity == 'blocking']) if gaps is not None else None

    def rulebook(self, package_id: str, version: int):
        from ..models import Gap
        raw = self.db.rulebook(package_id, version)
        return [Gap.model_validate(gap) for gap in json.loads(raw)] if raw is not None else None

    def closeout(self, case_id: str):
        """The issuance/sending record, scoped to a particular final decision, or None."""
        row = self.db.closeout(case_id)
        return CloseoutRecord(*row) if row else None

    def record_issuance(self, case_id: str, decided_at: str, issued_on: str, issued_by_name: str) -> None:
        self.db.change_closeout(case_id, decided_at, 'issue', issued_on, issued_by_name)

    def record_closeout(self, case_id: str, decided_at: str, sent_at: str, sent_by_name: str) -> None:
        self.db.change_closeout(case_id, decided_at, 'send', sent_at, sent_by_name)

    def replace(self, session: ReviewSession, expected_json: str, *, gaps=None) -> ReviewSession:
        if session.case_id and self._reconcile(session).information_request.message_id == return_message_id(session.version):
            # A completed return can only be finalized to the projection already committed on the case.
            if session != self._reconcile(session):
                raise SessionConflict(session.package_id)
        self.db.update(session, expected_json, self._gap_json(gaps))
        return session




def sweep(store) -> None:
    """Drop sessions and close-outs whose case is gone, and expired standalone packages."""
    backend_for(store).sweep()
