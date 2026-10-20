"""The web notice and the engine notice are one sentence, and no other notice remains."""
from __future__ import annotations

import re
from pathlib import Path

from engine.copyright import PII_NOTICE
from engine.privacy import PRIVACY_NOTICE

ROOT = Path(__file__).resolve().parents[2]
SKIP = {'.git', 'node_modules', 'dist', '__pycache__', '.venv', 'reference'}
OLD = 'Demo data ' + 'may be deleted.'


def _web_notice() -> str:
    text = (ROOT / 'web/src/privacy.ts').read_text()
    match = re.search(r'export const PRIVACY_NOTICE =\s*"([^"]*)"', text)
    assert match, 'web/src/privacy.ts does not export PRIVACY_NOTICE as one string'
    return match.group(1)


def _text_files():
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        if SKIP.intersection(path.parts):
            continue
        if path.suffix.lower() not in {'.py', '.ts', '.tsx', '.md', '.json', '.yml', '.css', '.mjs'}:
            continue
        yield path


def test_web_and_engine_notices_match_and_no_other_notice_remains():
    web = _web_notice()
    assert web == PRIVACY_NOTICE == PII_NOTICE
    assert 'https://openai.com/policies/api-data-usage-policies' in web
    assert web.endswith('after 7 days or on request.')
    needle = 'Do not upload personal information'
    here = Path(__file__).resolve()
    for path in _text_files():
        if path.resolve() == here:
            continue
        text = path.read_text(encoding='utf-8')
        assert OLD not in text, path.relative_to(ROOT)
        start = 0
        while True:
            found = text.find(needle, start)
            if found < 0:
                break
            assert text.startswith(PRIVACY_NOTICE, found), path.relative_to(ROOT)
            start = found + len(PRIVACY_NOTICE)
