"""Postgres case store. Selected by BATATIS_STORE=postgres and DATABASE_URL.

One connection per operation (safe for a stateless function). sslmode=require is forced
when the URL does not already set it, which is what Neon expects.
"""
from __future__ import annotations

import os
import threading
import uuid
from contextlib import contextmanager
from decimal import Decimal

from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from .models import Case, Fact, now
from .store import (FileTooLarge, InvalidAttachment, VersionConflict, attachment_reference,
                    case_with_stored_files, retention_cutoff)
from .uploads import PDF_MAX_BYTES
from .account_store import ACCOUNT_MIGRATIONS, PostgresAccountsMixin, _DB
from .access import enforce_mutation, enforce_stored_mutation, enforce_read
from .identify.title import normalize_title

MIGRATIONS = (
    """CREATE TABLE IF NOT EXISTS cases (
         id text PRIMARY KEY,
         data jsonb NOT NULL,
         version int NOT NULL,
         updated_at timestamptz NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS case_files (
         id text PRIMARY KEY,
         case_id text NOT NULL REFERENCES cases(id),
         name text NOT NULL,
         content_type text NOT NULL,
         size int NOT NULL,
         data bytea NOT NULL,
         created_at timestamptz NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS spend (
         day date PRIMARY KEY,
         usd numeric NOT NULL)""",
) + ACCOUNT_MIGRATIONS


def database_url() -> str:
    url = (os.environ.get('DATABASE_URL') or '').strip()
    if not url:
        raise RuntimeError('DATABASE_URL is not set')
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if not conninfo_to_dict(url).get('sslmode'):
        if url.startswith('postgresql://'):
            url += ('&' if '?' in url else '?') + 'sslmode=require'
        else:
            # make_conninfo() returns keyword form when adding a scoped search_path.
            # URL punctuation would turn that valid DSN into an invalid option.
            url = make_conninfo(url, sslmode='require')
    return url


class PostgresCaseStore(PostgresAccountsMixin):
    def __init__(self, url: str | None = None):
        import psycopg
        self._psycopg = psycopg
        self.url = url or database_url()
        with self._conn() as con:
            # Cold starts run this concurrently after a deploy; serialize the additive DDL.
            con.execute('SELECT pg_advisory_xact_lock(727274)')
            for statement in MIGRATIONS:
                con.execute(statement)

    @contextmanager
    def _conn(self):
        con = self._psycopg.connect(self.url, autocommit=False, connect_timeout=10)
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def get_version(self, case_id: str) -> int | None:
        snapshot = self.get_snapshot(case_id)
        return snapshot[1] if snapshot else None

    def get(self, case_id: str) -> Case | None:
        snapshot = self.get_snapshot(case_id)
        return snapshot[0] if snapshot else None

    def rename_title(self, case_id: str, title: str) -> Case | None:
        """Reauthorize and patch only naming fields of the locked current row."""
        title = normalize_title(title)
        with self._conn() as con:
            row = con.execute('SELECT data, version FROM cases WHERE id=%s FOR UPDATE', (case_id,)).fetchone()
            if row is None or self._purge_expired(con, case_id):
                return None
            payload, version = row[0], int(row[1])
            enforce_stored_mutation(payload)
            if payload.get('title') != title or payload.get('title_is_manual') is not True:
                payload.update(title=title, title_is_manual=True, updated_at=now())
                saved = con.execute('UPDATE cases SET data=%s, updated_at=%s, version=version+1 '
                                    'WHERE id=%s AND version=%s RETURNING version',
                                    (Jsonb(payload), payload['updated_at'], case_id, version)).fetchone()
                if saved is None:
                    raise VersionConflict(case_id, version)
                version = int(saved[0])
            files = {item[0] for item in con.execute('SELECT id FROM case_files WHERE case_id=%s', (case_id,))}
            return case_with_stored_files(payload, files, version)

    def get_snapshot(self, case_id: str) -> tuple[Case, int] | None:
        """Read the case and version together, checking retention after any lock wait."""
        with self._conn() as con:
            row = con.execute('SELECT data, version FROM cases WHERE id=%s FOR UPDATE', (case_id,)).fetchone()
            if row is None or self._purge_expired(con, case_id):
                return None
            files = {item[0] for item in con.execute('SELECT id FROM case_files WHERE case_id=%s', (case_id,))}
            case = case_with_stored_files(row[0], files, int(row[1]))
            enforce_read(case)
            return case, int(row[1])

    def delete(self, case_id: str) -> bool:
        """Remove the case, its facts, its evidence, and its files."""
        with self._conn() as con:
            previous = con.execute('SELECT data FROM cases WHERE id=%s FOR UPDATE', (case_id,)).fetchone()
            if previous:
                enforce_stored_mutation(previous[0])
            con.execute('DELETE FROM case_files WHERE case_id=%s', (case_id,))
            cur = con.execute('DELETE FROM cases WHERE id=%s', (case_id,))
            return cur.rowcount == 1

    def purge_expired(self) -> int:
        """Delete expired cases and files together, locking parents before their files."""
        with self._conn() as con:
            return self._purge_expired(con)

    def _purge_expired(self, con, case_id: str | None = None) -> int:
        self._purge_accounts(_DB(con, postgres=True))
        where = "(data->>'created_at')::timestamptz < %s::timestamptz"
        params = [retention_cutoff()]
        if case_id is not None:
            where += ' AND id=%s'
            params.append(case_id)
        rows = con.execute(f'SELECT id FROM cases WHERE {where} FOR UPDATE', params).fetchall()
        ids = [row[0] for row in rows]
        if not ids:
            return 0
        con.execute('DELETE FROM case_files WHERE case_id = ANY(%s)', (ids,))
        return con.execute('DELETE FROM cases WHERE id = ANY(%s)', (ids,)).rowcount

    def put(self, case: Case, *, expected_version: int | None = None) -> Case:
        case.updated_at = now()
        payload = Jsonb(case.model_dump(mode='json', exclude={'version'}))
        conflict = None
        with self._conn() as con:
            if expected_version is None:
                previous = con.execute('SELECT data FROM cases WHERE id=%s FOR UPDATE', (case.id,)).fetchone()
                if previous:
                    enforce_stored_mutation(previous[0])
                row = con.execute('INSERT INTO cases (id, data, version, updated_at) VALUES (%s, %s, 1, %s) '
                                  'ON CONFLICT (id) DO UPDATE SET data=EXCLUDED.data, '
                                  'version=cases.version+1, updated_at=EXCLUDED.updated_at RETURNING version',
                                  (case.id, payload, case.updated_at)).fetchone()
                case.version = int(row[0])
                return case
            if expected_version == 0:
                row = con.execute('INSERT INTO cases (id, data, version, updated_at) VALUES (%s, %s, 1, %s) '
                                  'ON CONFLICT (id) DO NOTHING RETURNING version',
                                  (case.id, payload, case.updated_at)).fetchone()
                if row is None:
                    actual = con.execute('SELECT version FROM cases WHERE id=%s', (case.id,)).fetchone()
                    raise VersionConflict(case.id, 0, int(actual[0]) if actual else None)
                case.version = int(row[0])
                return case
            row = con.execute('SELECT data, version FROM cases WHERE id=%s FOR UPDATE', (case.id,)).fetchone()
            if row is not None and self._purge_expired(con, case.id):
                row = None
            if row is not None:
                enforce_stored_mutation(row[0])
            if row is None or row[1] != expected_version:
                conflict = VersionConflict(case.id, expected_version, int(row[1]) if row else None)
            else:
                saved = con.execute('UPDATE cases SET data=%s, version=version+1, updated_at=%s '
                                  'WHERE id=%s AND version=%s RETURNING version',
                                  (payload, case.updated_at, case.id, expected_version)).fetchone()
                if saved is None:
                    raise VersionConflict(case.id, expected_version)
                case.version = int(saved[0])
        # Keep an expiry deletion committed even though the optimistic write is rejected.
        if conflict is not None:
            raise conflict
        return case

    def add_fact(self, case_id: str, fact: Fact) -> Case | None:
        """Lock the row, then update only if the version is unchanged."""
        for _ in range(5):
            with self._conn() as con:
                row = con.execute('SELECT data, version FROM cases WHERE id=%s FOR UPDATE', (case_id,)).fetchone()
                if row is None or self._purge_expired(con, case_id):
                    return None
                reference = attachment_reference(fact)
                if reference is not None and con.execute(
                        'SELECT 1 FROM case_files WHERE id=%s AND case_id=%s', (reference, case_id)).fetchone() is None:
                    raise InvalidAttachment('Attach an uploaded file from this application before confirming the document.')
                files = {item[0] for item in con.execute('SELECT id FROM case_files WHERE case_id=%s', (case_id,))}
                case = case_with_stored_files(row[0], files, int(row[1]))
                enforce_mutation(case)
                case.facts = [item for item in case.facts if item.id != fact.id] + [fact]
                case.updated_at = now()
                case.version = int(row[1]) + 1
                cur = con.execute('UPDATE cases SET data=%s, version=version+1, updated_at=%s '
                                  'WHERE id=%s AND version=%s',
                                  (Jsonb(case.model_dump(mode='json', exclude={'version'})), case.updated_at, case_id, row[1]))
                if cur.rowcount == 1:
                    return case
        raise VersionConflict(case_id)

    def remove_evidence(self, case_id: str, evidence_id: str) -> Case | None:
        """Lock the current case so withdrawal cannot lose a fact or recreate a deleted case."""
        prefix = f'evidence.{evidence_id}.'
        with self._conn() as con:
            row = con.execute('SELECT data, version FROM cases WHERE id=%s FOR UPDATE', (case_id,)).fetchone()
            if row is None:
                return None
            # Recheck retention after the lock: a waiting read may see a newly expired row.
            if self._purge_expired(con, case_id):
                return None
            files = {item[0] for item in con.execute('SELECT id FROM case_files WHERE case_id=%s', (case_id,))}
            case = case_with_stored_files(row[0], files, int(row[1]))
            enforce_mutation(case)
            case.facts = [fact for fact in case.facts if not fact.field.startswith(prefix)]
            case.evidence = [item for item in case.evidence if item.id != evidence_id]
            case.updated_at = now()
            case.version = int(row[1]) + 1
            cur = con.execute('UPDATE cases SET data=%s, version=version+1, updated_at=%s '
                              'WHERE id=%s AND version=%s',
                              (Jsonb(case.model_dump(mode='json', exclude={'version'})), case.updated_at, case_id, row[1]))
            if cur.rowcount != 1:
                raise VersionConflict(case_id, row[1])
            return case

    def put_file(self, case_id: str, name: str, data: bytes, content_type: str = 'application/pdf') -> dict | None:
        if len(data) > PDF_MAX_BYTES:
            raise FileTooLarge()
        file_id = f'file_{uuid.uuid4().hex[:12]}'
        with self._conn() as con:
            # Lock before computing expiry; an earlier cutoff could go stale while waiting.
            row = con.execute('SELECT data, version FROM cases WHERE id=%s FOR UPDATE', (case_id,)).fetchone()
            if row is None or self._purge_expired(con, case_id):
                return None
            enforce_stored_mutation(row[0])
            con.execute('INSERT INTO case_files (id, case_id, name, content_type, size, data, created_at) '
                        'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                        (file_id, case_id, name, content_type, len(data), data, now()))
        return {'id': file_id, 'case_id': case_id, 'name': name, 'content_type': content_type, 'size': len(data)}

    def get_file(self, case_id: str, file_id: str) -> dict | None:
        with self._conn() as con:
            self._purge_expired(con, case_id)
            row = con.execute('SELECT name, content_type, size, data FROM case_files WHERE id=%s AND case_id=%s',
                              (file_id, case_id)).fetchone()
        if row is None:
            return None
        return {'id': file_id, 'case_id': case_id, 'name': row[0], 'content_type': row[1],
                'size': row[2], 'data': bytes(row[3])}

    def try_reserve_spend(self, usd: Decimal, cap: Decimal) -> bool:
        """Add `usd` to today's spend only when the result stays within `cap`."""
        with self._conn() as con:
            con.execute('INSERT INTO spend (day, usd) VALUES (CURRENT_DATE, 0) ON CONFLICT (day) DO NOTHING')
            row = con.execute('UPDATE spend SET usd = usd + %s WHERE day = CURRENT_DATE AND usd + %s <= %s '
                              'RETURNING usd', (usd, usd, cap)).fetchone()
        return row is not None

    def adjust_spend(self, delta: Decimal) -> None:
        with self._conn() as con:
            con.execute('INSERT INTO spend (day, usd) VALUES (CURRENT_DATE, 0) ON CONFLICT (day) DO NOTHING')
            con.execute('UPDATE spend SET usd = usd + %s WHERE day = CURRENT_DATE', (delta,))


class PostgresSpend:
    """One connection and one CREATE TABLE for the daily spend cap.

    The case store still opens a connection per operation. The LLM gate must not.
    """

    def __init__(self, url: str | None = None):
        import psycopg
        self._psycopg = psycopg
        self.url = url or database_url()
        self._lock = threading.Lock()
        self._con = self._psycopg.connect(self.url, autocommit=False, connect_timeout=10)
        self._con.execute('CREATE TABLE IF NOT EXISTS spend (day date PRIMARY KEY, usd numeric NOT NULL)')
        self._con.commit()

    def close(self) -> None:
        with self._lock:
            self._con.close()

    def _connection(self):
        # Serverless Postgres (e.g. Neon) closes idle connections; psycopg does not reconnect.
        if self._con.closed or getattr(self._con, 'broken', False):
            self._con = self._psycopg.connect(self.url, autocommit=False, connect_timeout=10)
        return self._con

    def _rollback(self) -> None:
        try:
            self._con.rollback()
        except self._psycopg.Error:
            pass  # A dead connection is replaced on the next call.

    def try_reserve_spend(self, usd: Decimal, cap: Decimal) -> bool:
        with self._lock:
            con = self._connection()
            try:
                con.execute('INSERT INTO spend (day, usd) VALUES (CURRENT_DATE, 0) ON CONFLICT (day) DO NOTHING')
                row = con.execute('UPDATE spend SET usd = usd + %s WHERE day = CURRENT_DATE AND usd + %s <= %s '
                                  'RETURNING usd', (usd, usd, cap)).fetchone()
                con.commit()
            except Exception:
                self._rollback()
                raise
        return row is not None

    def adjust_spend(self, delta: Decimal) -> None:
        with self._lock:
            con = self._connection()
            try:
                con.execute('INSERT INTO spend (day, usd) VALUES (CURRENT_DATE, 0) ON CONFLICT (day) DO NOTHING')
                con.execute('UPDATE spend SET usd = usd + %s WHERE day = CURRENT_DATE', (delta,))
                con.commit()
            except Exception:
                self._rollback()
                raise
