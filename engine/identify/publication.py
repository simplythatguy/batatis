"""NRC publication link and printing, read from the codedb source manifest.

`printing` is `2nd` only when the manifest text proves a 2nd printing.
A missing file, or a path that does not say so, leaves it null.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_MANIFEST = Path(__file__).resolve().parents[2] / 'codedb' / 'source_manifest.json'
_SECOND = re.compile(r'(?i)(?:^|[^a-z])2nd[-_ ]printing')
_NRC = 'https://nrc-publications.canada.ca/'


def publication(manifest: Path | None = None) -> dict:
    """`url` is the NRC publication. `printing` is `2nd` or null."""
    path = manifest or _MANIFEST
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {'url': None, 'printing': None}
    nbc = data.get('nbc_ae') if isinstance(data, dict) else None
    if not isinstance(nbc, dict):
        return {'url': None, 'printing': None}
    raw_url = nbc.get('url')
    url = raw_url if isinstance(raw_url, str) and raw_url.startswith(_NRC) else None
    proof = ' '.join(str(nbc.get(key) or '') for key in ('path', 'jsonl', 'printing'))
    printing = '2nd' if _SECOND.search(proof) else None
    return {'url': url, 'printing': printing}
