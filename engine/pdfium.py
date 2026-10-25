"""Keep every engine PDFium document's lifetime under one process-wide lock."""
from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock

import pypdfium2 as pdfium

_LOCK = RLock()


@contextmanager
def open_pdf(data: bytes) -> Iterator[pdfium.PdfDocument]:
    # PDFium is not thread-safe, even across different documents. Nested readers
    # re-enter this lock; documents and their children close before it is released.
    with _LOCK, pdfium.PdfDocument(data) as doc:
        yield doc
