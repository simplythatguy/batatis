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

from psycopg.types.json import Jsonb

from .models import Case, Fact, now
from .store import FileTooLarge, VersionConflict, retention_cutoff
from .uploads import PDF_MAX_BYTES

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
)


def database_url() -> str:
    url = (os.environ.get('DATABASE_URL') or '').strip()
    if not url:
        raise RuntimeError('DATABASE_URL is not set')
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if 'sslmode=' not in url:
        url += ('&' if '?' in url else '?') + 'sslmode=require'
    return url


class PostgresCaseStore:
    def __init__(self, url: str | None = None):
        import psycopg
        self._psycopg = psycopg
        self.url = url or database_url()
        with self._conn() as con:
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
        with self._conn() as con:
            row = con.execute('SELECT version FROM cases WHERE id=%s', (case_id,)).fetchone()
        return int(row[0]) if row else None

    def get(self, case_id: str) -> Case | None:
        self.purge_expired()
        with self._conn() as con:
            row = con.execute('SELECT data FROM cases WHERE id=%s', (case_id,)).fetchone()
        return Case.model_validate(row[0]) if row else None

    def delete(self, case_id: str) -> bool:
        """Remove the case, its facts, its evidence, and its files."""
        self.purge_expired()
        with self._conn() as con:
            con.execute('DELETE FROM case_files WHERE case_id=%s', (case_id,))
            cur = con.execute('DELETE FROM cases WHERE id=%s', (case_id,))
            return cur.rowcount == 1

    def purge_expired(self) -> int:
        """Delete every case created more than 7 days ago, and its files."""
        cutoff = retention_cutoff()
        with self._conn() as con:
            rows = con.execute("SELECT id FROM cases WHERE data->>'created_at' < %s", (cutoff,)).fetchall()
            ids = [row[0] for row in rows]
            if not ids:
                return 0
            con.execute('DELETE FROM case_files WHERE case_id = ANY(%s)', (ids,))
            con.execute('DELETE FROM cases WHERE id = ANY(%s)', (ids,))
            return len(ids)

    def put(self, case: Case, *, expected_version: int | None = None) -> Case:
        self.purge_expired()
        case.updated_at = now()
        payload = Jsonb(case.model_dump(mode='json'))
        with self._conn() as con:
            if expected_version is None:
                con.execute('INSERT INTO cases (id, data, version, updated_at) VALUES (%s, %s, 1, %s) '
                            'ON CONFLICT (id) DO UPDATE SET data=EXCLUDED.data, '
                            'version=cases.version+1, updated_at=EXCLUDED.updated_at',
                            (case.id, payload, case.updated_at))
                return case
            if expected_version == 0:
                try:
                    con.execute('INSERT INTO cases (id, data, version, updated_at) VALUES (%s, %s, 1, %s)',
                                (case.id, payload, case.updated_at))
                except self._psycopg.errors.UniqueViolation as exc:
                    raise VersionConflict(case.id, 0, self.get_version(case.id)) from exc
                return case
            cur = con.execute('UPDATE cases SET data=%s, version=version+1, updated_at=%s '
                              'WHERE id=%s AND version=%s',
                              (payload, case.updated_at, case.id, expected_version))
            if cur.rowcount != 1:
                raise VersionConflict(case.id, expected_version, self.get_version(case.id))
        return case

    def add_fact(self, case_id: str, fact: Fact) -> Case | None:
        """Lock the row, then update only if the version is unchanged."""
        self.purge_expired()
        for _ in range(5):
            with self._conn() as con:
                row = con.execute('SELECT data, version FROM cases WHERE id=%s FOR UPDATE', (case_id,)).fetchone()
                if row is None:
                    return None
                case = Case.model_validate(row[0])
                case.facts = [item for item in case.facts if item.id != fact.id] + [fact]
                case.updated_at = now()
                cur = con.execute('UPDATE cases SET data=%s, version=version+1, updated_at=%s '
                                  'WHERE id=%s AND version=%s',
                                  (Jsonb(case.model_dump(mode='json')), case.updated_at, case_id, row[1]))
                if cur.rowcount == 1:
                    return case
        raise VersionConflict(case_id)

    def put_file(self, case_id: str, name: str, data: bytes, content_type: str = 'application/pdf') -> dict | None:
        if len(data) > PDF_MAX_BYTES:
            raise FileTooLarge()
        if self.get(case_id) is None:
            return None
        file_id = f'file_{uuid.uuid4().hex[:12]}'
        with self._conn() as con:
            con.execute('INSERT INTO case_files (id, case_id, name, content_type, size, data, created_at) '
                        'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                        (file_id, case_id, name, content_type, len(data), data, now()))
        return {'id': file_id, 'case_id': case_id, 'name': name, 'content_type': content_type, 'size': len(data)}

    def get_file(self, case_id: str, file_id: str) -> dict | None:
        with self._conn() as con:
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

    def try_reserve_spend(self, usd: Decimal, cap: Decimal) -> bool:
        with self._lock:
            try:
                self._con.execute('INSERT INTO spend (day, usd) VALUES (CURRENT_DATE, 0) ON CONFLICT (day) DO NOTHING')
                row = self._con.execute('UPDATE spend SET usd = usd + %s WHERE day = CURRENT_DATE AND usd + %s <= %s '
                                        'RETURNING usd', (usd, usd, cap)).fetchone()
                self._con.commit()
            except Exception:
                self._con.rollback()
                raise
        return row is not None

    def adjust_spend(self, delta: Decimal) -> None:
        with self._lock:
            try:
                self._con.execute('INSERT INTO spend (day, usd) VALUES (CURRENT_DATE, 0) ON CONFLICT (day) DO NOTHING')
                self._con.execute('UPDATE spend SET usd = usd + %s WHERE day = CURRENT_DATE', (delta,))
                self._con.commit()
            except Exception:
                self._con.rollback()
                raise
