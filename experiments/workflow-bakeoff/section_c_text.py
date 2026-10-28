"""Section C lines taken from the code database.

The draft receives provision ids, attribution status, function-objective pairs,
intent objective codes, and a count of intent statements. Sentence text and
intent prose stay in the database.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.codes import Codes
from engine.section_c import section_c_rows

_CODES: Codes | None = None


def codes() -> Codes:
    global _CODES
    if _CODES is None:
        _CODES = Codes()
    return _CODES


@dataclass(frozen=True)
class SectionCText:
    text: str
    pairs: frozenset[str]
    answered: bool


def section_c_for(article: str | None) -> SectionCText:
    if not article:
        return SectionCText(
            "No Division B sentence was committed. Section C is empty.",
            frozenset(),
            False,
        )
    token = str(article)
    try:
        rows = _cached_rows(token)
    except (KeyError, ValueError):
        return SectionCText(f"Section C lookup missed {token}.", frozenset(), False)
    lines = [f"Section C from the code database for {token}:"]
    pairs: list[str] = []
    for row in rows:
        row_pairs = [f"{pair.function}-{pair.objective}" for pair in row.pairs]
        pairs.extend(row_pairs)
        objectives = [block.objective for block in row.intents if block.objective]
        n_intent = sum(len(block.intents) for block in row.intents)
        via = f" via {row.attributed_via}" if row.attributed_via else ""
        pair_text = " ".join(row_pairs) if row_pairs else "none"
        intent_text = " ".join(objectives) if objectives else "none"
        lines.append(
            f"{row.provision_id} | {row.attribution_status}{via} | pairs {pair_text} | "
            f"intent objectives {intent_text} | intent statements {n_intent}"
        )
    return SectionCText("\n".join(lines), frozenset(pairs), True)


@lru_cache(maxsize=None)
def _cached_rows(article: str):
    return tuple(section_c_rows([article], codes()))
