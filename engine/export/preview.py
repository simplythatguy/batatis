"""Page images of an exported PDF for the application screen's preview.

The browser's built-in PDF viewer draws a dark frame around the pages that the page cannot restyle, so the
application screen shows these images on its own light background instead, beside the exact PDF bytes they
were drawn from. PDFium draws them, as in Chrome's viewer. A 32-colour PNG at twice the PDF size keeps the
form's text sharp; the byte budget keeps the base64 JSON response under the 4.5 MB serverless response cap.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from ..pdfium_lock import pdfium_locked

SCALE = 2.0                   # image pixels per PDF point
COLORS = 32
MAX_PAGES = 60
BUDGET_BYTES = 3_000_000      # the PDF plus its page images, before base64 (about 4 MB encoded)


@dataclass(frozen=True)
class PageImage:
    width: float              # PDF points
    height: float
    png: bytes


@pdfium_locked
def page_images(pdf: bytes, *, budget: int = BUDGET_BYTES, max_pages: int = MAX_PAGES) -> tuple[list[PageImage], int]:
    """The first pages, in order, whose images fit `budget` together with the PDF; and the PDF's page count."""
    import pypdfium2 as pdfium
    from PIL import Image

    images: list[PageImage] = []
    used = len(pdf)
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
            if used + buf.tell() > budget:
                break
            used += buf.tell()
            images.append(PageImage(width, height, buf.getvalue()))
    return images, count
