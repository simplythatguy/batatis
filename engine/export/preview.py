"""Page images of an exported PDF for the application screen's preview.

The browser's built-in PDF viewer draws a dark frame around the pages that the page cannot restyle, so the
application screen shows these images on its own light background instead, beside the exact PDF bytes they
were drawn from. PDFium draws them, as in Chrome's viewer. A 32-colour PNG at twice the PDF size keeps the
form's text sharp.

The PDF and its images travel as base64 in one JSON response, which must stay under the 4.5 MB serverless
response cap. `PAYLOAD_BUDGET` bounds their encoded size. A PDF whose own encoding does not fit is never
encoded (`fits` is checked first); the screen offers the draft download instead, which sends the bytes as is.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from ..pdfium_lock import pdfium_locked

SCALE = 2.0                   # image pixels per PDF point
COLORS = 32
MAX_PAGES = 60
RESPONSE_CAP = 4_500_000      # serverless response body limit
PAYLOAD_BUDGET = 4_000_000    # the base64 PDF and images; the rest of the JSON stays far inside the margin
ENTRY_BYTES = 128             # one entry's JSON keys, numbers and data-URL prefix


@dataclass(frozen=True)
class PageImage:
    width: float              # PDF points
    height: float
    png: bytes


def encoded(size: int) -> int:
    """The base64 length of `size` bytes."""
    return 4 * -(-size // 3)


def fits(pdf_size: int, budget: int = PAYLOAD_BUDGET) -> bool:
    """Whether a PDF of this many bytes can travel in a preview response at all, before anything is encoded."""
    return encoded(pdf_size) + ENTRY_BYTES <= budget


@pdfium_locked
def page_images(pdf: bytes, *, budget: int = PAYLOAD_BUDGET,
                max_pages: int = MAX_PAGES) -> tuple[list[PageImage], int]:
    """The first pages, in order, whose images fit the encoded `budget` beside the PDF; and its page count."""
    import pypdfium2 as pdfium
    from PIL import Image

    images: list[PageImage] = []
    used = encoded(len(pdf)) + ENTRY_BYTES
    with pdfium.PdfDocument(pdf) as doc:
        count = len(doc)
        for index in range(min(count, max_pages)):
            page = doc[index]
            width, height = page.get_size()
            bitmap = page.render(scale=SCALE, may_draw_forms=False)
            try:
                image = bitmap.to_pil().convert('RGB').quantize(colors=COLORS, method=Image.Quantize.FASTOCTREE)
            finally:
                bitmap.close()
                page.close()
            buf = io.BytesIO()
            image.save(buf, 'PNG')
            size = encoded(buf.tell()) + ENTRY_BYTES
            if used + size > budget:
                break
            used += size
            images.append(PageImage(width, height, buf.getvalue()))
    return images, count
