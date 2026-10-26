"""Case store. The file backend is the local default; Postgres is selected with BATATIS_STORE.

`backend/case-api` is also making writes atomic. The shared interface is `put(..., expected_version=)`
plus `VersionConflict`. This module keeps the file backend; `store_postgres.py` is the new one.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol

from .models import Case, Fact, now
from .uploads import PDF_MAX_BYTES, PDF_TOO_LARGE_DETAIL
from .account_store import FileAccountsMixin, _DB, preserve_messages
from .account_models import ApplicationPreferences, User
from .access import enforce_mutation, enforce_stored_mutation, enforce_read
from .identify.title import normalize_title
from .case_retention import RETENTION_DAYS, DRAFT_RETENTION_DAYS, CLOSED_RETENTION_DAYS

DEFAULT_PATH = Path.home() / '.batatis' / 'cases.sqlite'


class VersionConflict(Exception):
    """Optimistic concurrency lost. Callers retry or answer HTTP 409."""

    def __init__(self, case_id: str, expected: int | None = None, actual: int | None = None):
        self.case_id, self.expected, self.actual = case_id, expected, actual
        super().__init__(f'version conflict for {case_id}')


class FileTooLarge(Exception):
    def __init__(self, detail: str = PDF_TOO_LARGE_DETAIL):
        self.detail = detail
        super().__init__(detail)


class InvalidAttachment(ValueError):
    """A confirmed attachment must name bytes owned by this case."""


def attachment_reference(fact: Fact) -> str | None:
    """Only attachment-presence facts require storage proof; extraction sources do not.

    An unconfirmed empty value remains a valid withdrawal. Public listing text cannot
    become an attached file by labelling it confirmed or copying a file identifier.
    """
    if not (fact.field.startswith('evidence.') and fact.field.endswith('.file_ref')) or fact.status != 'confirmed':
        return None
    if (fact.kind == 'proposed' or fact.source.type != 'file' or not isinstance(fact.value, str)
            or not fact.value.strip() or fact.value != fact.source.ref):
        raise InvalidAttachment('Attach an uploaded file from this application before confirming the document.')
    return fact.value


def case_with_stored_files(payload: str | dict, file_ids: set[str], version: int) -> Case:
    """Old metadata is a listing until this case's stored bytes establish presence.

    Preserve its text and provenance, but do not let a legacy or imported file claim
    silently close an attachment gap. The read and file inventory share a transaction.
    Pure offline Case fixtures do not have storage and are not upload evidence.
    """
    data = json.loads(payload) if isinstance(payload, str) else payload
    case = Case.model_validate({**data, 'version': version})
    for fact in case.facts:
        try:
            reference = attachment_reference(fact)
        except InvalidAttachment:
            fact.status = 'unconfirmed'
            continue
        if reference is not None and reference not in file_ids:
            fact.status = 'unconfirmed'
    # Recompute evidence kind after downgrading any unverified legacy file claim.
    return Case.model_validate(case.model_dump())


class CaseBackend(Protocol):
    def get(self, case_id: str) -> Case | None: ...
    def get_snapshot(self, case_id: str) -> tuple[Case, int] | None: ...
    def get_version(self, case_id: str) -> int | None: ...
    def put(self, case: Case, *, expected_version: int | None = None) -> Case: ...
    def mutate_messages(self, case_id: str, user: User, operation: Callable[[Case], object]) -> tuple[Case, object] | None: ...
    def add_fact(self, case_id: str, fact: Fact) -> Case | None: ...
    def patch_draft(self, case_id: str, changes: dict, *, expected_version: int) -> Case | None: ...
    def rename_title(self, case_id: str, title: str) -> Case | None: ...
    def list_application_preferences(self, user_id: str) -> dict[str, ApplicationPreferences]: ...
    def patch_application_preferences(self, application_id: str, user: User,
                                      changes: dict[str, bool]) -> ApplicationPreferences | None: ...
    def remove_evidence(self, case_id: str, evidence_id: str) -> Case | None: ...
    def put_file(self, case_id: str, name: str, data: bytes, content_type: str = 'application/pdf') -> dict | None: ...
    def get_file(self, case_id: str, file_id: str) -> dict | None: ...
    def list_files(self, case_id: str) -> list[dict] | None: ...
    def delete(self, case_id: str) -> bool: ...
    def purge_expired(self) -> int: ...


def retention_cutoff() -> str:
    """Anonymous inactivity cutoff; longer purpose-based windows derive from the same clock."""
    return (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat(timespec='seconds')


def retention_windows(cutoff: str) -> tuple[str, str, str]:
    base = datetime.fromisoformat(cutoff)
    return (cutoff, (base - timedelta(days=DRAFT_RETENTION_DAYS - RETENTION_DAYS)).isoformat(),
            (base - timedelta(days=CLOSED_RETENTION_DAYS - RETENTION_DAYS)).isoformat())


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


class CaseStore(FileAccountsMixin):
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con, con:
            con.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, json TEXT NOT NULL, '
                        'updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1)')
            cols = {row[1] for row in con.execute('PRAGMA table_info(cases)')}
            if 'version' not in cols:
                con.execute('ALTER TABLE cases ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
            con.execute('CREATE INDEX IF NOT EXISTS cases_activity ON cases(updated_at)')
            con.execute('CREATE TABLE IF NOT EXISTS case_files (id TEXT PRIMARY KEY, case_id TEXT NOT NULL, '
                        'name TEXT NOT NULL, content_type TEXT NOT NULL, size INTEGER NOT NULL, '
                        'data BLOB NOT NULL, created_at TEXT NOT NULL)')
            self.init_accounts(con)

    def _connect(self):
        con = sqlite3.connect(self.path, timeout=5)
        con.execute('PRAGMA foreign_keys=ON')
        return con

    def get_version(self, case_id: str) -> int | None:
        with closing(self._connect()) as con, con:
            self._purge_expired(con, case_id)
            row = con.execute('SELECT version FROM cases WHERE id=?', (case_id,)).fetchone()
        return int(row[0]) if row else None

    def put(self, case: Case, *, expected_version: int | None = None) -> Case:
        case.updated_at = now()
        conflict = None
        with closing(self._connect()) as con, con:
            if expected_version is None:
                # Reserve before reading the thread: communication leaves version unchanged.
                con.execute('BEGIN IMMEDIATE')
                previous = con.execute('SELECT json FROM cases WHERE id=?', (case.id,)).fetchone()
                if previous:
                    enforce_stored_mutation(previous[0])
                    preserve_messages(case, previous[0])
                payload = case.model_dump_json(exclude={'version'})
                row = con.execute('INSERT INTO cases (id, json, updated_at, version) VALUES (?,?,?,1) '
                                  'ON CONFLICT(id) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at, '
                                  'version=cases.version+1 RETURNING version',
                                  (case.id, payload, case.updated_at)).fetchone()
                case.version = int(row[0])
                return case
            if expected_version == 0:
                payload = case.model_dump_json(exclude={'version'})
                try:
                    con.execute('INSERT INTO cases (id, json, updated_at, version) VALUES (?,?,?,1)',
                                (case.id, payload, case.updated_at))
                except sqlite3.IntegrityError as exc:
                    row = con.execute('SELECT version FROM cases WHERE id=?', (case.id,)).fetchone()
                    actual = int(row[0]) if row else None
                    raise VersionConflict(case.id, 0, actual) from exc
                case.version = 1
                return case
            # Lock before taking the cutoff, including time spent waiting for another writer.
            con.execute('BEGIN IMMEDIATE')
            self._purge_expired(con, case.id)
            previous = con.execute('SELECT json FROM cases WHERE id=?', (case.id,)).fetchone()
            if previous:
                enforce_stored_mutation(previous[0])
                preserve_messages(case, previous[0])
            payload = case.model_dump_json(exclude={'version'})
            row = con.execute('UPDATE cases SET json=?, updated_at=?, version=version+1 '
                              'WHERE id=? AND version=? RETURNING version',
                              (payload, case.updated_at, case.id, expected_version)).fetchone()
            if row is None:
                row = con.execute('SELECT version FROM cases WHERE id=?', (case.id,)).fetchone()
                conflict = VersionConflict(case.id, expected_version, int(row[0]) if row else None)
            else:
                case.version = int(row[0])
        # Commit an expiry deletion before reporting the conflict; raising inside would roll it back.
        if conflict is not None:
            raise conflict
        return case

    def get(self, case_id: str) -> Case | None:
        snapshot = self.get_snapshot(case_id)
        return snapshot[0] if snapshot else None

    def rename_title(self, case_id: str, title: str) -> Case | None:
        """Patch the current row under the edit lock, including for an identical rename."""
        title = normalize_title(title)
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            self._purge_expired(con, case_id)
            row = con.execute('SELECT json, version FROM cases WHERE id=?', (case_id,)).fetchone()
            if row is None:
                return None
            payload, version = json.loads(row[0]), int(row[1])
            enforce_stored_mutation(payload)
            if payload.get('title') != title or payload.get('title_is_manual') is not True:
                payload.update(title=title, title_is_manual=True, updated_at=now())
                saved = con.execute('UPDATE cases SET json=?, updated_at=?, version=version+1 '
                                    'WHERE id=? AND version=? RETURNING version',
                                    (json.dumps(payload, ensure_ascii=False), payload['updated_at'], case_id, version)).fetchone()
                if saved is None:
                    raise VersionConflict(case_id, version)
                version = int(saved[0])
            files = {item[0] for item in con.execute('SELECT id FROM case_files WHERE case_id=?', (case_id,))}
            return case_with_stored_files(payload, files, version)

    def get_snapshot(self, case_id: str) -> tuple[Case, int] | None:
        """The case and its optimistic version come from the same stored row."""
        with closing(self._connect()) as con, con:
            self._purge_expired(con, case_id)
            row = con.execute('SELECT json, version FROM cases WHERE id=?', (case_id,)).fetchone()
            if row is None:
                return None
            files = {item[0] for item in con.execute('SELECT id FROM case_files WHERE case_id=?', (case_id,))}
            case = case_with_stored_files(row[0], files, int(row[1]))
            enforce_read(case)
            return case, int(row[1])

    def delete(self, case_id: str) -> bool:
        """Remove the case, its facts, its evidence, and its files."""
        with closing(self._connect()) as con, con:
            con.execute('BEGIN IMMEDIATE')
            previous = con.execute('SELECT json FROM cases WHERE id=?', (case_id,)).fetchone()
            if previous:
                enforce_stored_mutation(previous[0])
            con.execute('DELETE FROM case_files WHERE case_id=?', (case_id,))
            cur = con.execute('DELETE FROM cases WHERE id=?', (case_id,))
            return cur.rowcount == 1

    def purge_expired(self) -> int:
        """Delete expired cases and files together in one transaction."""
        with closing(self._connect()) as con, con:
            return self._purge_expired(con)

    def _purge_expired(self, con, case_id: str | None = None) -> int:
        if not con.in_transaction:
            con.execute('BEGIN IMMEDIATE')
        self._purge_accounts(_DB(con))
        # Targeted access uses the case primary key; only periodic sweeps scan all cases.
        status = "COALESCE(json_extract(json, '$.status'), 'draft')"
        where = (f"(({status} = 'draft' AND json_extract(json, '$.owner_id') IS NULL AND julianday(updated_at) < julianday(?)) "
                 f"OR ({status} = 'draft' AND json_extract(json, '$.owner_id') IS NOT NULL AND julianday(updated_at) < julianday(?)) "
                 f"OR ({status} IN ('accepted','refused','withdrawn') AND julianday(updated_at) < julianday(?)))")
        params = list(retention_windows(retention_cutoff()))
        if case_id is not None:
            where += ' AND id=?'
            params.append(case_id)
        con.execute('DELETE FROM case_files WHERE case_id IN '
                    f'(SELECT id FROM cases WHERE {where})', params)
        return con.execute(f'DELETE FROM cases WHERE {where}', params).rowcount

    def add_fact(self, case_id: str, fact: Fact) -> Case | None:
        """Read-modify-write under a reserved lock so two writers cannot drop a fact."""
        for _ in range(5):
            con = self._connect()
            con.isolation_level = None
            try:
                con.execute('BEGIN IMMEDIATE')
                self._purge_expired(con, case_id)
                row = con.execute('SELECT json, version FROM cases WHERE id=?', (case_id,)).fetchone()
                if row is None:
                    con.execute('COMMIT')
                    return None
                reference = attachment_reference(fact)
                if reference is not None and con.execute(
                        'SELECT 1 FROM case_files WHERE id=? AND case_id=?', (reference, case_id)).fetchone() is None:
                    raise InvalidAttachment('Attach an uploaded file from this application before confirming the document.')
                files = {item[0] for item in con.execute('SELECT id FROM case_files WHERE case_id=?', (case_id,))}
                case = case_with_stored_files(row[0], files, int(row[1]))
                enforce_mutation(case)
                case.facts = [item for item in case.facts if item.id != fact.id] + [fact]
                case.updated_at = now()
                case.version = int(row[1]) + 1
                cur = con.execute('UPDATE cases SET json=?, updated_at=?, version=version+1 '
                                  'WHERE id=? AND version=?',
                                  (case.model_dump_json(exclude={'version'}), case.updated_at, case_id, row[1]))
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

    def remove_evidence(self, case_id: str, evidence_id: str) -> Case | None:
        """Withdraw exactly one slot under the same reserved lock as fact writes."""
        prefix = f'evidence.{evidence_id}.'
        for _ in range(5):
            con = self._connect()
            try:
                con.execute('BEGIN IMMEDIATE')
                self._purge_expired(con, case_id)
                row = con.execute('SELECT json, version FROM cases WHERE id=?', (case_id,)).fetchone()
                if row is None:
                    con.commit()
                    return None
                files = {item[0] for item in con.execute('SELECT id FROM case_files WHERE case_id=?', (case_id,))}
                case = case_with_stored_files(row[0], files, int(row[1]))
                enforce_mutation(case)
                case.facts = [fact for fact in case.facts if not fact.field.startswith(prefix)]
                case.evidence = [item for item in case.evidence if item.id != evidence_id]
                case.updated_at = now()
                case.version = int(row[1]) + 1
                cur = con.execute('UPDATE cases SET json=?, updated_at=?, version=version+1 '
                                  'WHERE id=? AND version=?',
                                  (case.model_dump_json(exclude={'version'}), case.updated_at, case_id, row[1]))
                if cur.rowcount != 1:
                    con.rollback()
                    continue
                con.commit()
                return case
            except sqlite3.OperationalError:
                con.rollback()
            finally:
                con.close()
        raise VersionConflict(case_id)

    def put_file(self, case_id: str, name: str, data: bytes, content_type: str = 'application/pdf') -> dict | None:
        if len(data) > PDF_MAX_BYTES:
            raise FileTooLarge()
        file_id = f'file_{uuid.uuid4().hex[:12]}'
        with closing(self._connect()) as con, con:
            self._purge_expired(con, case_id)
            previous = con.execute('SELECT json FROM cases WHERE id=?', (case_id,)).fetchone()
            if previous is None:
                return None
            enforce_stored_mutation(previous[0])
            con.execute('INSERT INTO case_files VALUES (?,?,?,?,?,?,?)',
                        (file_id, case_id, name, content_type, len(data), data, now()))
        return {'id': file_id, 'case_id': case_id, 'name': name, 'content_type': content_type, 'size': len(data)}

    def get_file(self, case_id: str, file_id: str) -> dict | None:
        with closing(self._connect()) as con, con:
            self._purge_expired(con, case_id)
            case = con.execute('SELECT json FROM cases WHERE id=?', (case_id,)).fetchone()
            if case is None:
                return None
            enforce_read(Case.model_validate_json(case[0]))
            row = con.execute('SELECT name, content_type, size, data FROM case_files WHERE id=? AND case_id=?',
                              (file_id, case_id)).fetchone()
        if row is None:
            return None
        return {'id': file_id, 'case_id': case_id, 'name': row[0], 'content_type': row[1],
                'size': row[2], 'data': row[3]}

    def list_files(self, case_id: str) -> list[dict] | None:
        """Owned upload inventory, including sources whose evidence binding was removed."""
        with closing(self._connect()) as con, con:
            self._purge_expired(con, case_id)
            case = con.execute('SELECT json FROM cases WHERE id=?', (case_id,)).fetchone()
            if case is None:
                return None
            enforce_read(Case.model_validate_json(case[0]))
            rows = con.execute('SELECT id, name, content_type, size FROM case_files WHERE case_id=? '
                               'ORDER BY created_at, id', (case_id,)).fetchall()
        return [dict(zip(('id', 'name', 'content_type', 'size'), row)) for row in rows]
