"""Division B benchmark from identify output stored on the case.

Identify output is a list of provision ids already stored on the case, under the
fact field ``identify.ranked`` (a JSON list of strings). This module keeps the ids
the code database resolves in Division B, in that order. An id the database does
not resolve is dropped. Nothing here substitutes a different article.
"""
from __future__ import annotations

import json

from .models import Case
from .process_fields import latest_fact

IDENTIFY_RANKED = 'identify.ranked'


def ranked_ids(case: Case) -> list[str]:
    """Ids stored as identify output. An empty or unreadable value is no output."""
    fact = latest_fact(case, IDENTIFY_RANKED)
    if fact is None or fact.value is None:
        return []
    raw = fact.value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    ids = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            ids.append(item.strip())
        elif isinstance(item, dict) and isinstance(item.get('id'), str) and item['id'].strip():
            ids.append(item['id'].strip())
    return ids


def resolve_div_b_benchmark(case: Case, codes) -> list[str]:
    """Division B ids from identify output that this code database can resolve."""
    resolved: list[str] = []
    for pid in ranked_ids(case):
        try:
            rec = codes.provision(pid, 'B')
        except Exception:
            rec = None
        if rec:
            resolved.append(pid)
    return list(dict.fromkeys(resolved))


def apply_identify_benchmark(case: Case, codes) -> list[str]:
    """Set ``case.provisions`` from identify output. Section C stays a later lookup."""
    case.provisions = resolve_div_b_benchmark(case, codes)
    return case.provisions
