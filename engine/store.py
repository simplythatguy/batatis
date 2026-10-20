"""SQLite case store: one JSON document per case."""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .models import Case, Fact, now

DEFAULT_PATH = Path.home() / '.batatis' / 'cases.sqlite'


def default_path() -> Path:
    return Path(os.environ.get('BATATIS_CASES') or DEFAULT_PATH)


class CaseStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con, con:
            con.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, json TEXT NOT NULL, '
                        'updated_at TEXT NOT NULL)')

    def _connect(self):
        return sqlite3.connect(self.path)

    def put(self, case: Case) -> Case:
        case.updated_at = now()
        with closing(self._connect()) as con, con:
            con.execute('INSERT INTO cases VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET json=excluded.json, '
                        'updated_at=excluded.updated_at', (case.id, case.model_dump_json(), case.updated_at))
        return case

    def get(self, case_id: str) -> Case | None:
        with closing(self._connect()) as con:
            row = con.execute('SELECT json FROM cases WHERE id=?', (case_id,)).fetchone()
        return Case.model_validate_json(row[0]) if row else None

    def delete(self, case_id: str) -> bool:
        """Remove one case. False when that id is not stored."""
        with closing(self._connect()) as con, con:
            cursor = con.execute('DELETE FROM cases WHERE id=?', (case_id,))
            return cursor.rowcount == 1

    def add_fact(self, case_id: str, fact: Fact) -> Case | None:
        case = self.get(case_id)
        if case is None:
            return None
        case.facts = [f for f in case.facts if f.id != fact.id] + [fact]
        return self.put(case)
