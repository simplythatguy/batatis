"""The page extract must be byte-identical on every platform.

`scripts/fetch_sources.py` checks each extract against a pinned sha256. Text mode
translates LF to CRLF on Windows, so the same PDF produced a different digest
there and `python -m codedb build` could not run from the documented steps.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('fetch_sources_newlines', ROOT / 'scripts' / 'fetch_sources.py')
fetch_sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch_sources)


@pytest.fixture()
def one_page_pdf(tmp_path):
    reportlab = pytest.importorskip('reportlab.pdfgen.canvas')
    path = tmp_path / 'page.pdf'
    canvas = reportlab.Canvas(str(path))
    canvas.drawString(72, 720, 'Caf\u00e9 \u2014 exit width')
    canvas.showPage()
    canvas.save()
    return path


def test_extract_uses_unix_line_endings(one_page_pdf, tmp_path):
    dest = tmp_path / 'text' / 'page.jsonl'
    fetch_sources.extract_jsonl(one_page_pdf, dest, None)

    raw = dest.read_bytes()
    assert b'\r' not in raw, 'CRLF breaks the pinned sha256 of the page extract'

    lines = raw.decode('utf-8').splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record['page'] == 1
    assert record['doc'] == 'page'


def test_extract_digest_matches_the_pinned_style(tmp_path, one_page_pdf):
    """The digest of the same content is stable: LF only, UTF-8, one record per page."""
    dest = tmp_path / 'page.jsonl'
    fetch_sources.extract_jsonl(one_page_pdf, dest, None)
    expected = fetch_sources.sha256(dest)
    dest.unlink()
    fetch_sources.extract_jsonl(one_page_pdf, dest, expected)  # raises if the digest moved
    assert fetch_sources.sha256(dest) == expected
