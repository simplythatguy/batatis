"""Small input guards: exact citation matching and a broken fillable form never raising."""
from __future__ import annotations

import io

import pytest

from engine.review import pdf_reader
from engine.review.citations import _same_provision


@pytest.mark.parametrize('a, b, same', [
    ('3.2.1.1.', '3.2.1.1.', True),
    ('3.2.1.1.', '3.2.1.1.(2)', True),
    ('9.10.15.4.(1)', '9.10.15.4.(1)(a)', True),
    ('3.2.1.1.', '3.2.1.10.', False),
    ('3.2.1.1.(1)', '3.2.1.1.(10)', False),
    ('9.10.15.4.', '9.10.15.5.', False),
])
def test_validator_errors_match_only_the_same_provision(a, b, same):
    assert _same_provision(a, b) is same and _same_provision(b, a) is same


def test_a_fillable_reader_failure_is_reported_not_raised(monkeypatch):
    from pypdf import PdfWriter
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    writer.write(buffer)

    def broken(*_args, **_kwargs):
        raise KeyError('/Rect')

    monkeypatch.setattr(pdf_reader, '_fillable', broken)
    result = pdf_reader.read_pdf(buffer.getvalue(), 'broken.pdf')
    assert result.name == 'broken.pdf'
