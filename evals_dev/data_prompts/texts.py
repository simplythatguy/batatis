"""Attachment text for the gold side only: which reference facts a reader of the attachments could find.

This extractor is deliberately independent of the engine's readers, so an improvement to the system
under test never changes which facts count as available. Page text is cached by attachment sha256.
Images have no text here; facts that live only in an image are reported separately.
"""
from __future__ import annotations

import html
import io
import json
import os
import re
import threading
import zipfile
from html.parser import HTMLParser
from pathlib import Path

from .corpus import Attachment, Case

CACHE = Path(__file__).resolve().parents[2] / '.dpe-cache' / 'texts'


class _Text(HTMLParser):
    SKIP = {'script', 'style', 'noscript', 'svg', 'head'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in ('p', 'br', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td', 'th'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(data: bytes) -> str:
    parser = _Text()
    parser.feed(data.decode('utf-8', errors='replace'))
    return re.sub(r'[ \t]+', ' ', html.unescape(''.join(parser.parts)))


def docx_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read('word/document.xml').decode('utf-8', errors='replace')
    xml = re.sub(r'</w:p>', '\n', xml)
    return html.unescape(re.sub(r'<[^>]+>', '', xml))


def pdf_pages(data: bytes) -> list[str]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    out = []
    for page in reader.pages:
        try:
            out.append(page.extract_text() or '')
        except Exception:
            out.append('')
    return out


def pages(case: Case, attachment: Attachment) -> list[str]:
    """One string per page (PDF), or one string for HTML/DOCX; [] for images and unreadable files."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f'{attachment.sha256}.json'
    if path.exists():
        return json.loads(path.read_text())
    data = case.read(attachment)
    kind = attachment.kind
    try:
        if kind == 'pdf':
            out = pdf_pages(data)
        elif kind in ('html', 'htm'):
            out = [html_text(data)]
        elif kind == 'docx':
            out = [docx_text(data)]
        elif kind == 'txt':
            out = [data.decode('utf-8', errors='replace')]
        else:
            out = []
    except Exception:
        out = []
    tmp = path.with_suffix(f'.{os.getpid()}.{threading.get_ident()}.tmp')
    tmp.write_text(json.dumps(out))
    os.replace(tmp, path)
    return out
