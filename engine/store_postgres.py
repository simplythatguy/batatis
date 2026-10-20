"""Postgres case store. Selected when the spend URL is Postgres.

#24 is not on dev, so this file is the DELETE /cases/{id} implementation for
Postgres. It does not purge cases on a timer and it does not keep a daily
spend table. When #24 is on dev, use its delete and purge and do not keep a
second copy.
"""
from __future__ import annotations

from contextlib import contextmanager

from .models import Case, Fact, now

_DDL = """
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY,
  json TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""


class PostgresCaseStore:
    def __init__(self, url: str):
        import psycopg
        self._psycopg = psycopg
        self.url = url
        self._ensure()

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

    def _ensure(self) -> None:
        last: BaseException | None = None
        for _ in range(4):
            try:
                with self._conn() as con:
                    con.execute(_DDL)
                return
            except Exception as exc:
                last = exc
                state = getattr(exc, 'sqlstate', None)
                if state not in {'23505', '42P07', '40P01'}:
                    raise
        if last is not None:
            raise last

    def put(self, case: Case) -> Case:
        case.updated_at = now()
        with self._conn() as con:
            con.execute(
                """INSERT INTO cases (id, json, updated_at) VALUES (%s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET json=EXCLUDED.json, updated_at=EXCLUDED.updated_at""",
                (case.id, case.model_dump_json(), case.updated_at),
            )
        return case

    def get(self, case_id: str) -> Case | None:
        with self._conn() as con:
            row = con.execute('SELECT json FROM cases WHERE id=%s', (case_id,)).fetchone()
        return Case.model_validate_json(row[0]) if row else None

    def delete(self, case_id: str) -> bool:
        """Remove one case. False when that id is not stored."""
        with self._conn() as con:
            cur = con.execute('DELETE FROM cases WHERE id=%s', (case_id,))
            return cur.rowcount == 1

    def add_fact(self, case_id: str, fact: Fact) -> Case | None:
        case = self.get(case_id)
        if case is None:
            return None
        case.facts = [item for item in case.facts if item.id != fact.id] + [fact]
        return self.put(case)
