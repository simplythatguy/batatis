"""Process references listed on every case: Div A Article 1.2.1.1. and Div C Article 2.3.1.1.

Div A 1.2.1.1. is where the code allows an alternative solution instead of a Division B acceptable
solution; Div C 2.3.1.1. lists the documentation the person requesting it provides. They are the
same for every variance application, so they are not identified by a model: ids, titles, text and
citations are read from the code database, and the rows are read-only in Section C and in the
appendix. A missing row is an error, never a made-up citation.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .codes import Codes
from .models_identify import ProcessRef

PROCESS_PROVISIONS = (
    ('1.2.1.1.', 'A', 'Allows compliance by an alternative solution in place of a Division B acceptable solution.'),
    ('2.3.1.1.', 'C', 'Lists the documentation the person requesting an alternative solution provides.'),
)


class ProcessRefMissing(LookupError):
    pass


def _flat(text: str | None) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


@lru_cache(maxsize=4)
def _rows(db_path: Path) -> tuple[ProcessRef, ...]:
    codes = Codes(db_path)
    rows = []
    for provision_id, division, role in PROCESS_PROVISIONS:
        record = codes.provision(provision_id, division)
        if record is None or not record.get('citation'):
            raise ProcessRefMissing(f'Div {division} {provision_id} is not in the code database')
        page = record.get('pdf_page')
        rows.append(ProcessRef(
            provision_id=record['id'], division=division, title=record.get('title') or '',
            citation=record['citation'], text=_flat(record.get('text')), role=role,
            pdf_page=int(page) if isinstance(page, (int, str)) and str(page).isdigit() else None))
    return tuple(rows)


def process_refs(codes: Codes) -> list[ProcessRef]:
    """The two read-only process rows, from this code database."""
    return [row.model_copy() for row in _rows(Path(codes.db_path))]
