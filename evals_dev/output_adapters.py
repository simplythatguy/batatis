"""Where other branches leave outputs for the deterministic checks.

Drop one JSON document per file:

    evals_dev/outputs/identify/*.json
    evals_dev/outputs/section_c/*.json
    evals_dev/outputs/section_d/*.json
    evals_dev/outputs/completeness/*.json
    evals_dev/outputs/case/*.json
    evals_dev/outputs/export/*.json

Identify files contribute article citations. Section C files contribute row
citations. Section D files contribute issue citations (``items`` or ``issues``).
The other three kinds are schema-checked only. A file may be one object or a
list of objects. Nothing here calls a model.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

KINDS = ('identify', 'section_c', 'section_d', 'completeness', 'case', 'export')
_PID = re.compile(
    r'\d{1,2}(?:\.\d{1,3}){3}\.?(?:\(\d{1,2}\))?(?:\([a-z]{1,2}\))?'
    r'(?:\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\))?'
)


def discover(root: Path) -> dict[str, list[dict]]:
    found = {kind: [] for kind in KINDS}
    base = root / 'outputs'
    for kind in KINDS:
        for path in sorted((base / kind).glob('*.json')):
            found[kind].extend(_documents(json.loads(path.read_text())))
    return found


def _documents(payload) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get('cases'), list):
        return [item for item in payload['cases'] if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def provision_of(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    match = _PID.search(value.replace(' ', ''))
    if not match:
        return None
    try:
        from codedb.ids import canon
        return canon(match.group(0))
    except (ImportError, ValueError):
        return match.group(0)


def citation_from(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    provision = raw.get('provision') or raw.get('provision_id')
    if not provision and isinstance(raw.get('citation'), str):
        provision = provision_of(raw['citation'])
    else:
        provision = provision_of(provision) if isinstance(provision, str) else None
    if not provision:
        return None
    division = raw.get('division')
    return {'provision': provision, 'division': division if division in ('A', 'B', 'C') else None}


def citations(kind: str, documents: list[dict]) -> list[dict]:
    """Article citations emitted by one system-output kind."""
    out = []
    for doc in documents:
        if kind == 'identify':
            rows = doc.get('articles') or []
        elif kind == 'section_c':
            rows = doc.get('section_c') or doc.get('rows') or []
        elif kind == 'section_d':
            rows = doc.get('items') or doc.get('issues') or []
        else:
            rows = []
        for row in rows:
            cite = citation_from(row) if isinstance(row, dict) else None
            if cite:
                cite['source'] = kind
                out.append(cite)
    return out
