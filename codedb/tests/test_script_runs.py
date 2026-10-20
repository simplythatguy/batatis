"""A text-layer fragment must not acquire a fabricated mixed-baseline number."""
import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from codedb import store, textnorm


def test_p477_homogeneous_60_is_not_partly_lowered():
    # Rendered source: N-bar with the whole 60 subscript. N-bar is an image,
    # absent from the text layer; this regression must not invent that symbol.
    con = store.connect()
    try:
        row = con.execute("SELECT text_raw,text,pdf_page FROM provisions "
                          "WHERE division='B' AND id='4.1.8.2.(1)'").fetchone()
    finally:
        con.close()
    raw = next(ln for ln in row['text_raw'].splitlines() if 'penetration resistance' in ln)
    assert row['pdf_page'] == 477 and raw.startswith('60 =')
    value = textnorm.source_text(raw, 'NBC-AE', 477)
    assert str(value) == raw
    assert textnorm.repair(value, None).startswith('₆₀ = average standard penetration resistance')


@pytest.mark.parametrize('token,offset,expected', [
    ('60', -2, '₆₀'),
    ('1234567890', -2, '₁₂₃₄₅₆₇₈₉₀'),
    ('1234567890', 3, '¹²³⁴⁵⁶⁷⁸⁹⁰'),
    ('12+-34', -2, '₁₂₊₋₃₄'),
    ('12ab34', -2, None),  # unsupported script letters: preserve/audit the whole raw line
    ('0.2', 3, None),
    ('3/4', 3, None),
    ('60', 0, '60'),
])
def test_synthetic_homogeneous_runs(tmp_path, monkeypatch, token, offset, expected):
    """Real positioned PDF glyphs, including runs longer than the old window."""
    import pypdfium2
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
        NameObject('/F1'): DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                            NameObject('/Subtype'): NameObject('/Type1'),
                                            NameObject('/BaseFont'): NameObject('/Helvetica')})})})
    content = DecodedStreamObject()
    content.set_data((f'BT /F1 7 Tf 1 0 0 1 30 {100+offset} Tm ({token}) Tj '
                      f'/F1 10 Tf 1 0 0 1 {30+len(token)*5} 100 Tm (= average) Tj ET').encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(content)
    path = tmp_path / 'homogeneous-run.pdf'
    writer.write(path)
    doc = pypdfium2.PdfDocument(path)
    monkeypatch.setattr(textnorm, '_pdf', lambda _: doc)
    textnorm.page_text.cache_clear()
    try:
        value = textnorm.page_text('synthetic', 1)
        raw_line = f'{token} = average'
        if expected is None:
            assert value.uncertain
            assert value.candidates(raw_line) == set()
            source = textnorm.source_text(raw_line, 'synthetic', 1)
            assert source.readable == str(source) == raw_line
            assert source.unmatched == (raw_line,)
            assert source.uncertain_lines == (raw_line,)
        else:
            assert value.candidates(raw_line) == {f'{expected} = average'}
    finally:
        textnorm.page_text.cache_clear()
        doc.close()
