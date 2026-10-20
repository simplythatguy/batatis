"""PDF checks the deploy file route calls. Nothing here writes a file."""
import io

import pytest
from reportlab.pdfgen import canvas

from engine.files import (
    PDF_MAX_BYTES, PDF_TOO_LARGE_DETAIL, FileTooLarge, NotAPdf, inspect_upload, read_pdf, stored_file_fields,
)


def _tiny_pdf() -> bytes:
    buf = io.BytesIO()
    sheet = canvas.Canvas(buf)
    sheet.drawString(36, 72, 'SYNTHETIC')
    sheet.showPage()
    sheet.save()
    return buf.getvalue()


def _contract(case_id: str, data: bytes) -> tuple[int, str]:
    """Status the deploy route returns for these bytes.

    The bytes are the raw body, or the file part taken out of multipart.
    A readable PDF is not a rejection.
    """
    try:
        inspect_upload(case_id, data)
    except ValueError as exc:
        assert str(exc) == 'invalid case id'
        return 400, 'invalid case id'
    except FileTooLarge as exc:
        return 413, exc.detail
    except NotAPdf:
        return 415, 'only PDF files are accepted'
    raise AssertionError('expected a rejection')


def test_readable_pdf_returns_a_page_count():
    pages = read_pdf(_tiny_pdf())
    assert pages == 1
    assert inspect_upload('case_ok', _tiny_pdf()) == 1
    assert stored_file_fields(pages) == {'pages': 1, 'stored': True, 'text_read': False}
    assert 'read' not in stored_file_fields(pages)


def test_truncated_or_garbage_pdf_is_not_a_pdf():
    truncated = _tiny_pdf()[:24]
    assert truncated.startswith(b'%PDF-')
    with pytest.raises(NotAPdf):
        read_pdf(truncated)
    with pytest.raises(NotAPdf):
        read_pdf(b'this is not a pdf')
    assert _contract('case_ok', truncated) == (415, 'only PDF files are accepted')
    assert _contract('case_ok', b'this is not a pdf') == (415, 'only PDF files are accepted')


def test_parser_valueerror_is_not_an_invalid_case_id(monkeypatch):
    class BrokenReader:
        def __init__(self, *_args, **_kwargs):
            raise ValueError('invalid case id')

    monkeypatch.setattr('engine.files.PdfReader', BrokenReader)
    with pytest.raises(NotAPdf):
        read_pdf(_tiny_pdf())


def test_invalid_case_id_is_rejected_before_parsing(monkeypatch):
    def unexpected_parse(_data):
        pytest.fail('invalid case id reached PDF parsing')

    monkeypatch.setattr('engine.files._page_count', unexpected_parse)
    with pytest.raises(ValueError, match='invalid case id'):
        inspect_upload('../escape', b'%PDF-synthetic')


def test_bad_case_id_is_400_and_a_file_over_4mb_is_413():
    assert _contract('..', _tiny_pdf()) == (400, 'invalid case id')
    assert _contract('.', _tiny_pdf()) == (400, 'invalid case id')
    over = b'%PDF-' + (b'0' * (PDF_MAX_BYTES - 4))
    assert len(over) == PDF_MAX_BYTES + 1
    status, detail = _contract('case_ok', over)
    assert status == 413
    assert detail == PDF_TOO_LARGE_DETAIL
    within = b'%PDF-' + (b'0' * (PDF_MAX_BYTES - 5))
    assert len(within) == PDF_MAX_BYTES
    with pytest.raises(NotAPdf):
        inspect_upload('case_ok', within)


@pytest.mark.parametrize('error', [ValueError, KeyError, IndexError, TypeError,
                                 AttributeError, RecursionError, RuntimeError])
@pytest.mark.parametrize('stage', ['reader', 'pages'])
def test_parser_failures_are_not_a_pdf(monkeypatch, error, stage):
    class BrokenReader:
        def __init__(self, *_args):
            if stage == 'reader':
                raise error('synthetic parser failure')

        @property
        def pages(self):
            raise error('synthetic page-tree failure')

    monkeypatch.setattr('engine.files.PdfReader', BrokenReader)
    with pytest.raises(NotAPdf):
        read_pdf(_tiny_pdf())
