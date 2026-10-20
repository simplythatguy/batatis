"""Store applicant PDFs. Only the page count is read; no text is extracted."""
from __future__ import annotations

import hashlib
import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from .models import new_id

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_FILES = _REPO / '.batatis-files'
DEFAULT_MAX_BYTES = 20 * 1024 * 1024
logger = logging.getLogger(__name__)


class NotAPdf(Exception):
    """The bytes are not a readable PDF. Callers map this to HTTP 415."""


class FileTooLarge(Exception):
    """The upload is over the configured cap. Callers map this to HTTP 413."""


@dataclass(frozen=True)
class StoredPdf:
    id: str
    name: str
    pages: int
    sha256: str


def files_root() -> Path:
    raw = os.environ.get('BATATIS_FILES')
    return Path(raw) if raw else DEFAULT_FILES


def max_upload_bytes() -> int:
    raw = os.environ.get('BATATIS_FILE_MAX_BYTES')
    if raw is None or not raw.strip():
        return DEFAULT_MAX_BYTES
    try:
        limit = int(raw)
        if limit > 0:
            return limit
    except ValueError:
        pass
    logger.warning('invalid BATATIS_FILE_MAX_BYTES; using the default upload limit')
    return DEFAULT_MAX_BYTES


def _safe_name(filename: str | None) -> str:
    name = Path(filename or '').name
    if not name or name in {'.', '..'}:
        return 'document.pdf'
    return name


def _case_dir(case_id: str) -> Path:
    if not case_id or case_id in {'.', '..'} or '/' in case_id or '\\' in case_id or '\x00' in case_id:
        raise ValueError('invalid case id')
    root = files_root().resolve()
    dest = (root / case_id).resolve()
    if dest.parent != root:
        raise ValueError('invalid case id')
    return dest


def _is_pdf(data: bytes) -> bool:
    head = data[:1024]
    if head.startswith(b'\xef\xbb\xbf'):
        head = head[3:]
    return head.lstrip(b' \t\r\n').startswith(b'%PDF-')


def _page_count(data: bytes) -> int:
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception as exc:
        raise NotAPdf() from exc


def save_pdf(case_id: str, filename: str | None, data: bytes) -> StoredPdf:
    directory = _case_dir(case_id)
    if len(data) > max_upload_bytes():
        raise FileTooLarge()
    if not _is_pdf(data):
        raise NotAPdf()
    pages = _page_count(data)
    file_id = new_id('file')
    name = _safe_name(filename)
    digest = hashlib.sha256(data).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f'{file_id}.pdf'
    partial = dest.with_suffix('.pdf.part')
    try:
        partial.write_bytes(data)
        partial.replace(dest)
    finally:
        partial.unlink(missing_ok=True)
    return StoredPdf(id=file_id, name=name, pages=pages, sha256=digest)


def discard_pdf(case_id: str, file_id: str) -> None:
    if not file_id or file_id in {'.', '..'} or '/' in file_id or '\\' in file_id:
        return
    try:
        directory = _case_dir(case_id)
    except ValueError:
        return
    (directory / f'{file_id}.pdf').unlink(missing_ok=True)
