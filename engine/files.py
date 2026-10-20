"""PDF checks for the case file route.

The route itself lives on the deploy branch: it stores the bytes in the case
database, accepts a raw body or a multipart part, and caps the body at 4 MB.
This module does not write a file. The route calls ``inspect_upload`` after it
has the bytes.
"""
from __future__ import annotations

import io

from pypdf import PdfReader

# Same cap and 413 text as the deploy route. Vercel rejects bodies over 4.5 MB.
PDF_MAX_BYTES = 4 * 1024 * 1024
PDF_TOO_LARGE_DETAIL = 'PDF too large: the limit is 4 MB. Try compressing the file or splitting it.'


class NotAPdf(Exception):
    """The bytes are not a readable PDF. The route maps this to HTTP 415."""


class FileTooLarge(Exception):
    """The upload is over 4 MB. The route maps this to HTTP 413."""

    detail = PDF_TOO_LARGE_DETAIL

    def __init__(self) -> None:
        super().__init__(PDF_TOO_LARGE_DETAIL)


def validate_case_id(case_id: str) -> None:
    """Reject an id the route answers with HTTP 400.

    Empty, ``.``, ``..``, a slash, a backslash, or NUL. Checked before the
    parser runs, so a parser error is never this message.
    """
    if not case_id or case_id in {'.', '..'} or '/' in case_id or '\\' in case_id or '\x00' in case_id:
        raise ValueError('invalid case id')


def _is_pdf(data: bytes) -> bool:
    head = data[:1024]
    if head.startswith(b'\xef\xbb\xbf'):
        head = head[3:]
    return head.lstrip(b' \t\r\n').startswith(b'%PDF-')


def _page_count(data: bytes) -> int:
    """Page count, or NotAPdf. A parser ValueError is not an invalid case id."""
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except NotAPdf:
        raise
    except Exception as exc:
        raise NotAPdf() from exc


def read_pdf(data: bytes) -> int:
    """Page count. Raises NotAPdf for a missing magic header or a parser error.

    The deploy route passes the raw body, or the file part taken out of a
    multipart body. Either way these are the PDF bytes, and nothing is stored.
    """
    if not _is_pdf(data):
        raise NotAPdf()
    return _page_count(data)


def inspect_upload(case_id: str, data: bytes) -> int:
    """Checks the deploy route applies before it stores the PDF.

    A bad id raises ``ValueError('invalid case id')`` (HTTP 400). More than
    4 MB raises ``FileTooLarge`` (HTTP 413, ``PDF_TOO_LARGE_DETAIL``). Bytes
    that are not a readable PDF raise ``NotAPdf`` (HTTP 415). Returns the
    page count.
    """
    validate_case_id(case_id)
    if len(data) > PDF_MAX_BYTES:
        raise FileTooLarge()
    return read_pdf(data)
