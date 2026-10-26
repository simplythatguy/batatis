"""Code-edition label for the form and the appendix.

'2nd printing' is written only when the codedb manifest says the NBC-AE source
label is ``NBC(AE) 2023 p2``. That label is stored in the build stats by
``codedb.build``. Any other database, or no database, stays ``NBC(AE) 2023``.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

PROVEN_LABEL = 'NBC(AE) 2023 p2'
EDITION_PROVEN = 'National Building Code - 2023 Alberta Edition (2nd printing), Division B'
EDITION_PLAIN = 'NBC(AE) 2023'
_PRINTING_CLAIM = ('2nd printing', 'second printing')


def second_printing_proven(codes) -> bool:
    path = getattr(codes, 'db_path', None)
    if path is None or not Path(path).is_file():
        return False
    try:
        with closing(sqlite3.connect(f'{Path(path).resolve().as_uri()}?mode=ro', uri=True)) as con:
            row = con.execute("SELECT value FROM meta WHERE key='stats'").fetchone()
    except sqlite3.Error:
        return False
    if not row or not row[0]:
        return False
    try:
        stats = json.loads(row[0])
    except json.JSONDecodeError:
        return False
    label = str(((stats.get('sources') or {}).get('NBC-AE') or {}).get('label') or '')
    return label == PROVEN_LABEL


def edition_label(codes) -> str:
    return EDITION_PROVEN if second_printing_proven(codes) else EDITION_PLAIN


def code_or_standard_value(user, codes) -> str:
    """Tool text for the code field. A user value is kept unless it claims a printing the manifest does not prove."""
    if isinstance(user, str) and user.strip():
        lowered = user.casefold()
        if any(claim in lowered for claim in _PRINTING_CLAIM) and not second_printing_proven(codes):
            return EDITION_PLAIN
        return user.strip()
    return edition_label(codes)
