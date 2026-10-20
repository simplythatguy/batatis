"""SQLite case store: one JSON document per case."""
from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable
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
        self._locks_guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        with closing(self._connect()) as con, con:
            con.execute('CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, json TEXT NOT NULL, '
                        'updated_at TEXT NOT NULL)')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def _case_lock(self, case_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(case_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[case_id] = lock
            return lock

    def _write(self, case: Case, *, keep_timestamps: bool = False) -> Case:
        if not keep_timestamps:
            case.updated_at = now()
        with closing(self._connect()) as con, con:
            con.execute('INSERT INTO cases VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET json=excluded.json, '
                        'updated_at=excluded.updated_at', (case.id, case.model_dump_json(), case.updated_at))
        return case

    def _read(self, case_id: str) -> Case | None:
        with closing(self._connect()) as con:
            row = con.execute('SELECT json FROM cases WHERE id=?', (case_id,)).fetchone()
        return Case.model_validate_json(row[0]) if row else None

    def put(self, case: Case, *, keep_timestamps: bool = False) -> Case:
        with self._case_lock(case.id):
            return self._write(case, keep_timestamps=keep_timestamps)

    def get(self, case_id: str) -> Case | None:
        return self._read(case_id)

    def mutate(self, case_id: str, fn: Callable[[Case], None]) -> Case | None:
        """Apply fn to one case and write it back while holding that case's lock."""
        with self._case_lock(case_id):
            case = self._read(case_id)
            if case is None:
                return None
            fn(case)
            return self._write(case)

    def add_fact(self, case_id: str, fact: Fact) -> Case | None:
        def apply(case: Case) -> None:
            case.facts = [f for f in case.facts if f.id != fact.id] + [fact]

        return self.mutate(case_id, apply)
