"""SQLite case store: one JSON document per case."""
from __future__ import annotations

import json
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
            con.execute('CREATE TABLE IF NOT EXISTS identify_results (case_id TEXT PRIMARY KEY, json TEXT NOT NULL)')

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

    def add_fact(self, case_id: str, fact: Fact) -> Case | None:
        case = self.get(case_id)
        if case is None:
            return None
        case.facts = [f for f in case.facts if f.id != fact.id] + [fact]
        return self.put(case)

    def put_identify(self, case_id: str, payload: dict) -> None:
        """Store the identify response. This does not write case provisions."""
        blob = json.dumps(payload)
        with closing(self._connect()) as con, con:
            con.execute('INSERT INTO identify_results VALUES (?,?) ON CONFLICT(case_id) DO UPDATE SET json=excluded.json',
                        (case_id, blob))

    def get_identify(self, case_id: str) -> dict | None:
        with closing(self._connect()) as con:
            row = con.execute('SELECT json FROM identify_results WHERE case_id=?', (case_id,)).fetchone()
        return json.loads(row[0]) if row else None
