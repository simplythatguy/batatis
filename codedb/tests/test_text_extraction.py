"""Source-backed regressions; copyrighted source data stays in ignored build/."""
import json
import random
import re
import sqlite3
import unicodedata

import pytest

from codedb import store
from codedb import textnorm
from codedb.sources import BUILD_DIR, DOCS, load_pages


def provision(pid):
    con = store.connect()
    try:
        return con.execute("SELECT text FROM provisions WHERE division='B' AND id=?", (pid,)).fetchone()[0]
    finally:
        con.close()


def test_justification_and_raised_units_in_9_25_5_1():
    text = provision('9.25.5.1.(1)')
    assert 'characteristic less than 0.1 L/(s×m²) at 75 Pa' in text
    assert '60 ng/(Pa×s×m²)' in text


@pytest.mark.parametrize('sentence', [2, 4])
def test_generated_spaces_before_raised_unit_digits(sentence):
    assert '10 m².' in provision(f'3.1.11.3.({sentence})')


def test_italic_boundaries_in_9_10_14_2():
    assert 'fire compartments by fire separations' in provision('9.10.14.2.(1)')
    assert 'exposing building face shall' in provision('9.10.14.2.(2)')


def test_liquid_water_hyphenation_in_intent():
    con = store.connect()
    try:
        row = con.execute("SELECT intents FROM intents WHERE provision_id='9.27.3.2.(1)' AND block_seq=0").fetchone()
        assert 'resistance to liquid-water transfer' in json.loads(row[0])[0]
    finally:
        con.close()


def test_of_t_he_in_notes_and_intents():
    con = store.connect()
    try:
        note = con.execute("SELECT text FROM notes WHERE division='B' AND note_id='A-3.3.6.2.(2)'").fetchone()[0]
        assert 'nature of the oxidizing agent' in note
        intent = con.execute("SELECT intents FROM intents WHERE provision_id='2.2.1.4.(2)'").fetchone()[0]
        assert 'rating of the fire separation' in json.loads(intent)[0]
    finally:
        con.close()


def test_unalignable_lines_and_unknown_words_are_left_verbatim():
    text = textnorm.source_text('unverifiableglyphsequence 12345', 'NBC-AE', 999)
    assert text.unmatched == ('unverifiableglyphsequence 12345',)
    assert textnorm.repair(text, None) == str(text)


def test_discretionary_hyphens_do_not_remove_real_compounds_or_unknown_text():
    seg = textnorm.Segmenter(['liquid liquid fire-resistance fire-resistance'])
    text = textnorm.SourceText('raw', 'liq\u00ad\nuid fire\u00ad\nresistance xyz\u00ad\nabc')
    assert textnorm.repair(text, seg) == 'liquid fire-resistance xyz-abc'


def test_geometry_retains_raw_text_and_source_multiplication_operator():
    line = next(ln for ln in load_pages('NBC-AE')[998].lines if '0.1 L/' in ln)
    text = textnorm.source_text(line, 'NBC-AE', 999)
    assert str(text) == line
    assert text.unmatched == ()
    assert '0.1 L/(s×m²) at 75 Pa' in textnorm.repair(text, None)
    con = sqlite3.connect(':memory:')
    try:
        assert con.execute('SELECT ?', (text,)).fetchone()[0] == line
    finally:
        con.close()


def test_ambiguous_word_boundaries_are_not_guessed(monkeypatch):
    page = textnorm.PageText('not able; notable', 'not able; notable')
    monkeypatch.setattr(textnorm, 'page_text', lambda *_: page)
    value = textnorm.source_text('n o t a b l e', 'test-source', 1)
    assert value.unmatched == ('n o t a b l e',)
    assert value.readable == str(value)


def test_partial_ligatures_cannot_expand_the_source_text():
    page = textnorm.PageText('ﬁ', 'ﬁ')
    assert page.candidates('i') == set()
    assert page.candidates('fi') == {'ﬁ'}


def test_twenty_seeded_provisions_against_independent_pdf_page_text():
    """Check reading boundaries with PDFium and characters with pypdf layout.

    Neither reference calls the normalization pipeline. NFKC lets the text-layer
    comparison accept actual raised digits; it does not validate formula meaning
    or replace visual/OCR proofreading of the rendered PDF.
    """
    pdfium = pytest.importorskip('pypdfium2')
    from pypdf import PdfReader
    con = store.connect()
    try:
        pool = [dict(r) for r in con.execute("SELECT * FROM provisions WHERE level='sentence' "
                                            "AND pdf_page=pdf_page_end ORDER BY division,sort_key")]
    finally:
        con.close()
    sample = random.Random(20261020).sample(pool, 20)
    pdf = pdfium.PdfDocument(DOCS['NBC-AE'].pdf)
    other = PdfReader(DOCS['NBC-AE'].pdf)
    checks = []
    canonical = lambda t: ' '.join(unicodedata.normalize('NFKC', t).split())
    try:
        for r in sample:
            page = pdf[r['pdf_page'] - 1]
            tp = page.get_textpage()
            try:
                reference = canonical(tp.get_text_range().replace('\ufffe', ''))
                value = canonical(r['text'])
                layout = canonical(other.pages[r['pdf_page'] - 1].extract_text(extraction_mode='layout'))
                boundaries = value in reference
                characters = re.sub(r'\s+', '', value) in re.sub(r'\s+', '', layout)
                checks.append({'division': r['division'], 'id': r['id'], 'pdf_page': r['pdf_page'],
                               'pdfium_word_boundaries': boundaries, 'pypdf_layout_characters': characters})
            finally:
                tp.close()
                page.close()
    finally:
        pdf.close()
    (BUILD_DIR / 'text-source-sample.json').write_text(json.dumps({'seed': 20261020, 'checks': checks}, indent=2)+'\n')
    assert all(r['pdfium_word_boundaries'] and r['pypdf_layout_characters'] for r in checks), checks
