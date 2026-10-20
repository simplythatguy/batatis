"""Read-only access to the code database. Every citation string comes from `codedb.lookup().citation`."""
from __future__ import annotations

import os
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from codedb import lookup, search, store

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = _REPO / 'codedb' / 'build' / 'codedb.sqlite'
OBJECTIVES_PROVISION = ('2.2.1.1.(1)', 'A')        # Div A listing of objectives
FUNCTIONS_PROVISION = ('3.2.1.1.(1)', 'A')         # Div A listing of functional statements


def default_db() -> Path:
    return Path(os.environ.get('BATATIS_CODEDB') or DEFAULT_DB)


class CodeDbMissing(Exception):
    """Raised only when the code database file is absent. The message has no path."""

    def __init__(self) -> None:
        super().__init__('code database not found')


class Codes:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else default_db()
        if not self.db_path.exists():
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
                 'pdf_page': h.get('pdf_page'),
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
