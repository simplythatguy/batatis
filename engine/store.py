"""Case store. The file backend is the local default; Postgres is selected with BATATIS_STORE.

`backend/case-api` is also making writes atomic. The shared interface is `put(..., expected_version=)`
plus `VersionConflict`. This module keeps the file backend; `store_postgres.py` is the new one.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from .models import Case, Fact, now
from .uploads import PDF_MAX_BYTES, PDF_TOO_LARGE_DETAIL

DEFAULT_PATH = Path.home() / '.batatis' / 'cases.sqlite'
RETENTION_DAYS = 7


class VersionConflict(Exception):
    """Optimistic concurrency lost. Callers retry or answer HTTP 409."""

    def __init__(self, case_id: str, expected: int | None = None, actual: int | None = None):
        self.case_id, self.expected, self.actual = case_id, expected, actual
        super().__init__(f'version conflict for {case_id}')


class FileTooLarge(Exception):
    def __init__(self, detail: str = PDF_TOO_LARGE_DETAIL):
        self.detail = detail
        super().__init__(detail)


class CaseBackend(Protocol):
    def get(self, case_id: str) -> Case | None: ...
    def get_version(self, case_id: str) -> int | None: ...
    def put(self, case: Case, *, expected_version: int | None = None) -> Case: ...
    def add_fact(self, case_id: str, fact: Fact) -> Case | None: ...
    def put_file(self, case_id: str, name: str, data: bytes, content_type: str = 'application/pdf') -> dict | None: ...
    def get_file(self, case_id: str, file_id: str) -> dict | None: ...
    def delete(self, case_id: str) -> bool: ...
    def purge_expired(self) -> int: ...


def retention_cutoff() -> str:
    """Cases created before this instant are older than the 7-day retention window."""
    return (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat(timespec='seconds')


def default_path() -> Path:
    return Path(os.environ.get('BATATIS_CASES') or DEFAULT_PATH)


def assert_durable_when_hosted() -> None:
    """A Vercel function disk is ephemeral. Refuse the file store instead of dropping cases."""
    if not os.environ.get('VERCEL'):
        return
    kind = (os.environ.get('BATATIS_STORE') or '').strip().lower()
    if kind != 'postgres':
        raise RuntimeError(
            'Refusing to start: VERCEL is set and BATATIS_STORE is not postgres. '
            'Set BATATIS_STORE=postgres and DATABASE_URL. A file store on this host is an ephemeral disk.')
    if not (os.environ.get('DATABASE_URL') or '').strip():
        raise RuntimeError('Refusing to start: VERCEL is set but DATABASE_URL is not set. '
                           'Configure the shared Postgres case store before deploying.')


def open_store(path: Path | str | None = None) -> CaseBackend:
    """File backend unless BATATIS_STORE=postgres, which also needs DATABASE_URL."""
    assert_durable_when_hosted()
    kind = (os.environ.get('BATATIS_STORE') or 'file').strip().lower()
    if kind in ('', 'file', 'sqlite'):
        return CaseStore(path)
    if kind == 'postgres':
        from .store_postgres import PostgresCaseStore
        return PostgresCaseStore()
    raise RuntimeError(f'BATATIS_STORE must be file or postgres, not {kind!r}')


class CaseStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con, con:
            con.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, json TEXT NOT NULL, '
                        'updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1)')
            cols = {row[1] for row in con.execute('PRAGMA table_info(cases)')}
            if 'version' not in cols:
                con.execute('ALTER TABLE cases ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
            con.execute('CREATE TABLE IF NOT EXISTS case_files (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, '
                        'name TEXT NOT NULL, content_type TEXT NOT NULL, size INTEGER NOT NULL, '
                        'data BLOB NOT NULL, created_at TEXT NOT NULL)')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def get_version(self, case_id: str) -> int | None:
        with closing(self._connect()) as con, con:
            self._purge_expired(con, case_id)
            row = con.execute('SELECT version FROM cases WHERE id=?', (case_id,)).fetchone()
        return int(row[0]) if row else None

    def put(self, case: Case, *, expected_version: int | None = None) -> Case:
        case.updated_at = now()
        payload = case.model_dump_json()
        with closing(self._connect()) as con, con:
            if expected_version is None:
                con.execute('INSERT INTO cases (id, json, updated_at, version) VALUES (?,?,?,1) '
                            'ON CONFLICT(id) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at, '
                            'version=cases.version+1', (case.id, payload, case.updated_at))
                return case
            if expected_version == 0:
                try:
                    con.execute('INSERT INTO cases (id, json, updated_at, version) VALUES (?,?,?,1)',
                                (case.id, payload, case.updated_at))
                except sqlite3.IntegrityError as exc:
                    row = con.execute('SELECT version FROM cases WHERE id=?', (case.id,)).fetchone()
                    actual = int(row[0]) if row else None
                    raise VersionConflict(case.id, 0, actual) from exc
                return case
            cur = con.execute('UPDATE cases SET json=?, updated_at=?, version=version+1 '
                              'WHERE id=? AND version=?', (payload, case.updated_at, case.id, expected_version))
            if cur.rowcount != 1:
                row = con.execute('SELECT version FROM cases WHERE id=?', (case.id,)).fetchone()
                raise VersionConflict(case.id, expected_version, int(row[0]) if row else None)
        return case

    def get(self, case_id: str) -> Case | None:
        with closing(self._connect()) as con, con:
            self._purge_expired(con, case_id)
            row = con.execute('SELECT json FROM cases WHERE id=?', (case_id,)).fetchone()
        return Case.model_validate_json(row[0]) if row else None

    def delete(self, case_id: str) -> bool:
        """Remove the case, its facts, its evidence, and its files."""
        with closing(self._connect()) as con, con:
            con.execute('DELETE FROM case_files WHERE case_id=?', (case_id,))
            cur = con.execute('DELETE FROM cases WHERE id=?', (case_id,))
            return cur.rowcount == 1

    def purge_expired(self) -> int:
        """Delete expired cases and files together in one transaction."""
        with closing(self._connect()) as con, con:
            return self._purge_expired(con)

    def _purge_expired(self, con, case_id: str | None = None) -> int:
        # Targeted access uses the case primary key; only periodic sweeps scan all cases.
        where = "julianday(json_extract(json, '$.created_at')) < julianday(?)"
        params = [retention_cutoff()]
        if case_id is not None:
            where += ' AND id=?'
            params.append(case_id)
        con.execute('DELETE FROM case_files WHERE case_id IN '
                    f'(SELECT id FROM cases WHERE {where})', params)
        return con.execute(f'DELETE FROM cases WHERE {where}', params).rowcount

    def add_fact(self, case_id: str, fact: Fact) -> Case | None:
        """Read-modify-write under a reserved lock so two writers cannot drop a fact."""
        for _ in range(5):
            con = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            try:
                con.execute('BEGIN IMMEDIATE')
                self._purge_expired(con, case_id)
                row = con.execute('SELECT json, version FROM cases WHERE id=?', (case_id,)).fetchone()
                if row is None:
                    con.execute('COMMIT')
                    return None
                case = Case.model_validate_json(row[0])
                case.facts = [item for item in case.facts if item.id != fact.id] + [fact]
                case.updated_at = now()
                cur = con.execute('UPDATE cases SET json=?, updated_at=?, version=version+1 '
                                  'WHERE id=? AND version=?',
                                  (case.model_dump_json(), case.updated_at, case_id, row[1]))
                if cur.rowcount != 1:
                    con.execute('ROLLBACK')
                    continue
                con.execute('COMMIT')
                return case
            except sqlite3.OperationalError:
                try:
                    con.execute('ROLLBACK')
                except sqlite3.Error:
                    pass
            finally:
                con.close()
        raise VersionConflict(case_id)

    def put_file(self, case_id: str, name: str, data: bytes, content_type: str = 'application/pdf') -> dict | None:
        if len(data) > PDF_MAX_BYTES:
            raise FileTooLarge()
        file_id = f'file_{uuid.uuid4().hex[:12]}'
        with closing(self._connect()) as con, con:
            self._purge_expired(con, case_id)
            if con.execute('SELECT id FROM cases WHERE id=?', (case_id,)).fetchone() is None:
                return None
            con.execute('INSERT INTO case_files VALUES (?,?,?,?,?,?,?)',
                        (file_id, case_id, name, content_type, len(data), data, now()))
        return {'id': file_id, 'case_id': case_id, 'name': name, 'content_type': content_type, 'size': len(data)}

    def get_file(self, case_id: str, file_id: str) -> dict | None:
        with closing(self._connect()) as con, con:
            self._purge_expired(con, case_id)
            row = con.execute('SELECT name, content_type, size, data FROM case_files WHERE id=? AND case_id=?',
                              (file_id, case_id)).fetchone()
        if row is None:
            return None
        return {'id': file_id, 'case_id': case_id, 'name': row[0], 'content_type': row[1],
                'size': row[2], 'data': row[3]}
