"""Page images of an exported PDF for the application screen's preview.

The browser's built-in PDF viewer draws a dark frame around the pages that the page cannot restyle, so the
application screen shows these images on its own light background instead, beside the exact PDF bytes they
were drawn from. PDFium draws them, as in Chrome's viewer. A 32-colour PNG at twice the PDF size keeps the
form's text sharp.

Images travel as base64 under the 4.5 MB serverless response cap. `PAYLOAD_BUDGET` bounds their encoded
size. Legacy previews reserve space for the PDF. Windowed previews spend the budget on the requested pages
first, then include the PDF only when both fit, so a large package can still be inspected page by page.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from ..pdfium_lock import pdfium_locked

SCALE = 2.0                   # image pixels per PDF point
WINDOW_MAX_EDGE = 1920        # large drawing sheets still yield a bounded, viewable first image
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
                max_pages: int = MAX_PAGES, start: int = 0,
                reserve_pdf: bool = True) -> tuple[list[PageImage], int]:
    """A page window in order within the encoded budget, and the complete PDF page count."""
    import pypdfium2 as pdfium
    from PIL import Image

    images: list[PageImage] = []
    used = (encoded(len(pdf)) if reserve_pdf else 0) + ENTRY_BYTES
    with pdfium.PdfDocument(pdf) as doc:
        count = len(doc)
        for index in range(start, min(count, start + max_pages)):
            page = doc[index]
            width, height = page.get_size()
            scale = SCALE if reserve_pdf else min(SCALE, WINDOW_MAX_EDGE / max(width, height))
            bitmap = page.render(scale=scale, may_draw_forms=False)
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
