"""Read-only access to the code database. Every citation string comes from `codedb.lookup().citation`."""
from __future__ import annotations

import os
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from codedb import lookup, search, store

_REPO = Path(__file__).resolve().parents[1]
# Canonical build output. `codedb.store.DB_PATH` is the same file the builder writes.
DEFAULT_DB = _REPO / 'codedb' / 'build' / 'codedb.sqlite'
OBJECTIVES_PROVISION = ('2.2.1.1.(1)', 'A')        # Div A listing of objectives
FUNCTIONS_PROVISION = ('3.2.1.1.(1)', 'A')         # Div A listing of functional statements


def repo_codedb_candidates() -> tuple[Path, ...]:
    """Repo-relative databases, starting with the file the codedb package builds."""
    seen: list[Path] = []
    for path in (Path(store.DB_PATH), DEFAULT_DB, _REPO / 'codedb' / 'codedb.sqlite'):
        if path not in seen:
            seen.append(path)
    return tuple(seen)


def _codedb_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(_REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def resolve_codedb() -> Path:
    """First existing file: BATATIS_CODEDB, then repo-relative codedb locations.

    Raises FileNotFoundError with the paths that were checked when none exist.
    """
    tried: list[Path] = []
    env = (os.environ.get('BATATIS_CODEDB') or '').strip()
    if env:
        tried.append(Path(env))
    tried.extend(repo_codedb_candidates())
    for path in tried:
        if path.is_file():
            return path
    looked = '; '.join(_codedb_label(path) for path in tried)
    raise FileNotFoundError(
        'code database not found. Set BATATIS_CODEDB to the SQLite file, or build '
        f'codedb/build/codedb.sqlite. Looked for: {looked}.')


def default_db() -> Path:
    """Database path for callers that open it themselves.

    Same order as `resolve_codedb`. When nothing exists yet, returns BATATIS_CODEDB
    if it is set, otherwise the canonical repo build path.
    """
    try:
        return resolve_codedb()
    except FileNotFoundError:
        env = (os.environ.get('BATATIS_CODEDB') or '').strip()
        if env:
            return Path(env)
        return repo_codedb_candidates()[0]


class CodeDbMissing(Exception):
    """Raised only when the code database file is absent. The message has no path."""

    def __init__(self) -> None:
        super().__init__('code database not found')


class Codes:
    def __init__(self, db_path: Path | str | None = None):
        # An explicit API corpus selection must not fall through to another file.
        # Keep the detailed filesystem diagnostic in the CLI resolver, while the
        # API uses its existing typed, path-free missing-database contract.
        configured = db_path if db_path is not None else (os.environ.get('BATATIS_CODEDB') or '').strip()
        if configured:
            self.db_path = Path(configured)
        else:
            try:
                self.db_path = resolve_codedb()
            except FileNotFoundError as error:
                raise CodeDbMissing() from error
        if not self.db_path.is_file():
            raise CodeDbMissing()
        self._definition = lru_cache(maxsize=None)(self._definition_uncached)

    def provision(self, provision_id: str, division: str | None = 'B') -> dict | None:
        """codedb.lookup with this database. Raises codedb.AmbiguousProvisionError when division is None and
        the id exists in several divisions."""
        return lookup(provision_id, division=division, db_path=self.db_path)

    def citation(self, provision_id: str, division: str | None = 'B') -> str | None:
        r = self.provision(provision_id, division)
        return r['citation'] if r else None

    def search(self, terms: str, division: str | None = 'B', limit: int = 20) -> list[dict]:
        hits = search(terms, division=division, limit=limit, db_path=self.db_path)
        return [{'id': h['id'], 'division': h['division'], 'level': h['level'],
                 'article_title': h['article_title'], 'title': h['title'], 'text': h['text'],
                 'citation': self.citation(h['id'], h['division'])} for h in hits]

    def definition(self, code: str) -> dict | None:
        """Objective (OS1.2) or functional statement (F03) text with its Div A citation."""
        return self._definition(code)

    def _definition_uncached(self, code: str) -> dict | None:
        with closing(store.connect(self.db_path)) as con:
            row = con.execute("SELECT code, kind, title, text, pdf_page FROM definitions WHERE doc='NBC-AE' AND code=?",
                              (code,)).fetchone()
        if not row:
            return None
        pid, div = OBJECTIVES_PROVISION if row['kind'] == 'objective' else FUNCTIONS_PROVISION
        return {'code': row['code'], 'kind': row['kind'], 'title': row['title'], 'text': row['text'],
                'pdf_page': row['pdf_page'], 'citation': self.citation(pid, div)}
