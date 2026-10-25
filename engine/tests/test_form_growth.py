"""Long content grows the supplied form's own boxes, or continues in more boxes of the same style, at normal size.

The user asked for this instead of squeezing text into small boxes or moving it to the appendix. Every applicant
or lookup cell keeps its normal size (10 pt; 9 pt in the Section C table). A cell that needs more lines makes its
row taller; a row taller than the page continues in the same form row style on the next page. Nothing is clipped
or dropped, the supplied form's other content keeps its geometry, and the layout hint the export writes is only a
hint: the reader rebuilds the form from it and believes what it can verify on the page.
"""
import hashlib
import io
import re

import pypdfium2 as pdfium
import pytest
from pypdf import PdfReader, PdfWriter

from engine.codes import Codes
from engine.export import export_case, form_path, load_field_map
from engine.export.challenge_form import prepare_form
from engine.export.g3 import norm, page_texts, render_problems
from engine.export.sample import FACTS, sample_case
from engine.export.scc import load_form
from engine.export.text import pdf_safe
from engine.models import INTENT_LABEL, Fact, Source
from engine.review.pdf_reader import read_pdf

pytestmark = pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')

LONG_ADDRESS = ('Unit 1200, Building 4, 000 Example Industrial Business Park Road NW, Edmonton, AB T0T 0T0, '
                'care of the SYNTHETIC Example Holdings site office, attention the property manager, '
                'with copies to the second-floor reception (EXAMPLE DATA)')
LONG_LEGAL = 'Lot 12, Block 3, Plan 1234567; ' + ', '.join(f'parcel {n} of the EXAMPLE DATA subdivision'
                                                         for n in range(1, 13))
DENSE = ['9.23.17.2.(1)', '9.27.5.1.(1)', '9.25.2.2.(1)']
MANY = ['9.25.2.2.(1)', '9.23.17.2.(1)', '9.27.3.4.(1)', '9.32.1.3.(2)', '4.1.6.10.(4)', '4.1.7.13.(6)',
        '9.9.10.1.(1)', '9.25.5.1.(1)', '9.10.9.1.(1)', '9.10.9.2.(1)', '9.10.9.3.(1)', '9.10.9.4.(1)',
        '9.10.9.5.(1)', '9.10.9.6.(1)', '9.10.9.7.(1)', '9.10.9.8.(1)', '9.10.9.9.(1)', '9.10.9.10.(1)',
        '9.10.9.11.(1)', '9.10.9.12.(1)', '9.10.9.13.(1)', '9.10.9.14.(1)', '9.10.9.15.(1)', '9.10.9.16.(1)']
FRAME = (36.0, 69.7, 574.6, 756.1)          # the supplied form's outer blue frame on every form page


@pytest.fixture(scope='module')
def codes():
    return Codes()


def confirmed(field, value):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='test:applicant', quote=str(value)))


def segments(result, name):
    """A field's drawn boxes in reading order: its own cell, then its continuations (`name~2`, `name~3`...)."""
    found = [p for p in result.placements if p.field == name or re.fullmatch(re.escape(name) + r'~\d+', p.field)]
    return sorted(found, key=lambda p: (p.page, -p.rect[3]))


def drawn(result, placements) -> str:
    """The text PDFium finds inside the boxes, joined in order (what a reader of the page sees)."""
    doc = pdfium.PdfDocument(result.pdf)
    return norm(' '.join(doc[p.page].get_textpage().get_text_bounded(*p.rect) for p in placements))


def no_overlaps(result):
    by_page = {}
    for p in result.placements:
        x0, y0, x1, y1 = p.rect
        assert FRAME[0] <= x0 and x1 <= FRAME[2] and FRAME[1] <= y0 and y1 <= FRAME[3], (p.field, p.rect)
        for other in by_page.setdefault(p.page, []):
            ox0, oy0, ox1, oy1 = other.rect
            assert not (x0 < ox1 - 0.5 and ox0 < x1 - 0.5 and y0 < oy1 - 0.5 and oy0 < y1 - 0.5), (p.field, other.field)
        by_page[p.page].append(p)


def test_the_default_layout_is_unchanged_byte_for_byte():
    """Content that fits still gets exactly today's dynamic blank (pinned pypdf 6.21.1)."""
    fmap = load_field_map()
    source = load_form(None, fmap)
    expected = {0: '37eab94a155320a58174bfe52ed64426247e4f6d9c07fc0b5f72c0ae73d41ef4',
                2: '1c84036a4efe19f481c327dd9a970a4c39dbff79878f82654b73edfdb856ae0e',
                3: 'f90afd8e8bd93cdd4c69895df6e453d21a4c9cdd373e6ac73879b8f0451b96f0',
                5: 'f2749e1273e1b1d5826ac98cc0d8cfcb1204386914751d496f0d162d9014b42a',
                6: '7cf333dafc6c7440129571b5c908013c19dad19a599e349d491e5e317238fa21',
                12: '324eeb410970a2bf28e3e6623374650ad4e04a2cab863cc4b3e97afeadd70857',
                13: '283fcb7c8769fbb495d152b55613ddf108f2a68273d11ce118701d6136615c18',
                24: 'f23ed8d74de7be4de1b0ed338f29e4682bfbdef416dac8fedd0ba3b54d74e451'}
    for count, digest in expected.items():
        assert hashlib.sha256(prepare_form(source, fmap, count)[0]).hexdigest() == digest, count


def test_a_long_mailing_address_grows_its_own_box_at_normal_size(codes):
    case = sample_case(codes, provisions=['9.9.10.1.(1)'], facts={**FACTS, 'mailing_address': LONG_ADDRESS})
    result = export_case(case, codes=codes)
    [box] = segments(result, 'Mailing Address')
    assert box.size == 10.0 and len(box.lines) > 2 and box.ref is None
    assert drawn(result, [box]) == norm(pdf_safe(LONG_ADDRESS))
    form_text = norm(' '.join(page_texts(result.pdf)[:result.form_pages]))
    assert 'See Appendix' not in form_text and 'Date of Request' in form_text
    # The rows below moved down instead of being covered: Date of Request is still its own box below.
    [date] = segments(result, 'Date of Reqeuest')
    assert date.page == box.page and date.rect[3] <= box.rect[1]
    no_overlaps(result)
    assert not render_problems(result)


def test_a_long_typed_legal_description_grows_its_printed_row(codes):
    facts = {key: value for key, value in FACTS.items() if key not in ('lot', 'block', 'plan')}
    case = sample_case(codes, provisions=['9.9.10.1.(1)'], facts={**facts, 'legal_description': LONG_LEGAL})
    result = export_case(case, codes=codes, draft=True)
    rows = segments(result, 'Legal description')
    assert rows and all(p.size == 10.0 and p.ref is None for p in rows)
    assert drawn(result, rows) == norm(pdf_safe(LONG_LEGAL))
    assert 'See Appendix' not in norm(' '.join(page_texts(result.pdf)[:result.form_pages]))
    no_overlaps(result)
    assert not render_problems(result)


@pytest.mark.parametrize('provisions', [DENSE, MANY], ids=['dense-intents', 'many-attributions'])
def test_every_attribution_cell_is_whole_at_9_pt_in_form_rows(codes, provisions):
    case = sample_case(codes, provisions=provisions)
    result = export_case(case, codes=codes)
    from engine.export.challenge_form import row_fields
    for index, row in enumerate(case.section_c):
        cells = row_fields(index)
        intent = segments(result, cells['intent'])
        assert intent and all(p.size == 9.0 for p in intent)
        text = drawn(result, intent)
        assert '(full text' not in text and 'Appendix C-' not in text
        for block in row.intents:
            for passage in block.intents:
                assert norm(pdf_safe(passage)) in text, (row.provision_id, passage[:60])
        if row.intents:
            assert text.startswith(norm(f'{INTENT_LABEL}:')) or INTENT_LABEL in text
        objectives = ', '.join(dict.fromkeys(p.objective for p in row.pairs)) or 'No table row'
        assert drawn(result, segments(result, cells['objective'])) == norm(objectives)
        assert drawn(result, segments(result, cells['article'])) == row.provision_id
    assert result.form_pages > 7
    no_overlaps(result)
    assert not render_problems(result)


def test_a_long_supporting_document_listing_grows_the_section_d_box(codes):
    case = sample_case(codes, provisions=['9.9.10.1.(1)'])
    titles = [f'TEST typed document {n} (EXAMPLE DATA)' for n in range(1, 25)]
    for n, title in enumerate(titles, start=1):
        case.facts += [confirmed(f'evidence.typed_{n:02d}.title', title),
                       confirmed(f'evidence.typed_{n:02d}.responsible_party', f'TEST organisation {n}')]
    result = export_case(case, codes=codes, draft=True)
    boxes = segments(result, 'Supporting Doc')
    assert boxes and all(p.size == 10.0 for p in boxes)
    listing = drawn(result, boxes)
    for n, title in enumerate(titles, start=7):
        assert f'D-{n}: {title} - TEST organisation {n - 6}' in listing
    assert 'continued in Appendix D' not in listing and 'See Appendix D' not in listing
    no_overlaps(result)
    assert not render_problems(result)


def test_grown_cells_leave_the_form_head_and_the_officer_pages_as_supplied(codes):
    case = sample_case(codes, provisions=DENSE, facts={**FACTS, 'mailing_address': LONG_ADDRESS})
    result = export_case(case, codes=codes)
    source = pdfium.PdfDocument(load_form(None, load_field_map()))
    doc = pdfium.PdfDocument(result.pdf)
    for i in range(5):                      # Part 2(a), 2(b), 3 and the printed Part 4 appendix
        assert doc[result.form_pages - 5 + i].render(scale=1).to_pil().tobytes() == \
            source[i + 2].render(scale=1).to_pil().tobytes()
    # Above the first applicant row (title, address block, Part 1 and the Section A heading), page 1 is pixel
    # for pixel the supplied page. `crop` removes points from (left, bottom, right, top).
    head = (0, 499.0, 0, 0)
    assert doc[0].render(scale=1, crop=head).to_pil().tobytes() == \
        source[0].render(scale=1, crop=head).to_pil().tobytes()


def test_a_grown_export_reads_back_and_its_layout_hint_alone_proves_nothing(codes):
    case = sample_case(codes, provisions=DENSE, facts={**FACTS, 'mailing_address': LONG_ADDRESS})
    result = export_case(case, codes=codes)
    read = read_pdf(result.pdf, 'grown.pdf')
    assert read.role == 'scc_form_flattened' and read.form_version == 'challenge_2026-09-15' and not read.note
    assert read.fields['Mailing Address'].status == 'present'
    assert read.fields['Mailing Address'].value == norm(pdf_safe(LONG_ADDRESS))
    assert read.fields['Article(s)'].value == DENSE[0]
    meta = PdfReader(io.BytesIO(result.pdf)).metadata
    hint = meta['/BatatisLayout']
    for forged in (None, hint + ' ', re.sub(r'\d+', lambda m: str(int(m.group()) + 1), hint, count=1)):
        writer = PdfWriter(clone_from=io.BytesIO(result.pdf))
        values = {key: value for key, value in meta.items() if key != '/BatatisLayout'}
        if forged is not None:
            values['/BatatisLayout'] = forged
        writer.metadata = None
        writer.add_metadata(values)
        buf = io.BytesIO()
        writer.write(buf)
        altered = read_pdf(buf.getvalue(), 'altered.pdf')
        assert altered.note and all(v.status == 'not_found' for v in altered.fields.values()), forged
