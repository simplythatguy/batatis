"""Read a multipart body carrying the SCC form and attachments (several PDFs, one request).

The whole body is capped at the engine's 4 MB PDF limit plus multipart overhead
(the hosting body limit is 4.5 MB). Files are kept in memory only for the
review; their bytes are not stored.
"""
from __future__ import annotations

import re
from email import policy
from email.message import Message
from email.parser import BytesParser

from fastapi import HTTPException, Request

from ..uploads import MULTIPART_MAX_OVERHEAD_BYTES, PDF_MAX_BYTES, PDF_TOO_LARGE_DETAIL

MAX_FILES = 12
BODY_LIMIT = PDF_MAX_BYTES + MULTIPART_MAX_OVERHEAD_BYTES
TOO_LARGE = 'Upload too large: the files together are limited to 4 MB.'


async def read_body(request: Request) -> bytes:
    declared = request.headers.get('content-length')
    if declared is not None and declared.strip():
        try:
            if int(declared) > BODY_LIMIT:
                raise HTTPException(413, TOO_LARGE)
        except ValueError:
            raise HTTPException(400, 'invalid Content-Length') from None
    buf = bytearray()
    async for chunk in request.stream():
        if len(buf) + len(chunk) > BODY_LIMIT:
            raise HTTPException(413, TOO_LARGE)
        buf += chunk
    return bytes(buf)


def parse_files(body: bytes, content_type: str) -> list[tuple[str, bytes]]:
    if content_type.split(';', 1)[0].strip().lower() != 'multipart/form-data':
        raise HTTPException(415, 'Send the PDFs as multipart/form-data')
    try:
        header = Message(policy=policy.default)
        header['Content-Type'] = content_type
        boundary = header.get_boundary()
        if not boundary:
            raise HTTPException(400, 'multipart body is missing a boundary')
        boundary_bytes = boundary.encode('ascii')
        if not re.fullmatch(rb"[0-9A-Za-z'()+_,./:=? -]{0,69}[0-9A-Za-z'()+_,./:=?-]", boundary_bytes):
            raise ValueError('invalid boundary')
        delimiter = re.compile(rb'(?:\A|(?<=[\r\n]))--' + re.escape(boundary_bytes) +
                               rb'(?:--)?[ \t]*(?:\r\n|\r|\n|\Z)')
        if sum(1 for _ in delimiter.finditer(body)) > MAX_FILES + 2:
            raise HTTPException(400, f'Upload at most {MAX_FILES} files at once')
        message = BytesParser(policy=policy.default.clone(raise_on_defect=True)).parsebytes(
            b'Content-Type: ' + content_type.encode('latin1') + b'\r\nMIME-Version: 1.0\r\n\r\n' + body)
        if not message.is_multipart():
            raise ValueError('missing multipart framing')
        files = []
        for part in message.iter_parts():
            if part.is_multipart() or any(getattr(value, 'defects', ()) for value in part.values()):
                raise ValueError('invalid multipart part')
            if part.get_content_disposition() != 'form-data' or part.get_filename() is None:
                continue
            data = part.get_payload(decode=True)
            if data is None:
                raise ValueError('missing file payload')
            name = re.sub(r'[\x00-\x1f/\\]', '_', part.get_filename())[:200] or 'upload.pdf'
            files.append((name, data))
    except (ValueError, RecursionError) as error:
        raise HTTPException(400, 'invalid multipart body') from error
    if not files:
        raise HTTPException(400, 'Attach at least one PDF')
    if len(files) > MAX_FILES:
        raise HTTPException(400, f'Upload at most {MAX_FILES} files at once')
    if sum(len(data) for _n, data in files) > PDF_MAX_BYTES:
        raise HTTPException(413, PDF_TOO_LARGE_DETAIL)
    return files
