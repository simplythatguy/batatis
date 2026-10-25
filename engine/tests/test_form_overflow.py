"""Text that has a cell on the supplied challenge form is drawn in that cell before any labelled continuation.

Regression for the seven-page challenge form: a typed legal description, intent statements and the Section D
listing used to leave their cells with only a pointer while the text went to the appended pages (each intent
passage twice), and a typed legal description beside lot, block and plan was dropped from the PDF.
"""
import re

import pypdfium2 as pdfium
import pytest

from engine.codes import Codes
from engine.export import export_case, form_path
from engine.export.g3 import appendix_text, norm, page_texts, render_problems
from engine.export.sample import FACTS, sample_case
from engine.export.text import faithful_font_text
from engine.models import INTENT_LABEL, Fact, Source

pytestmark = pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')

# The printed Section B row "Legal description of property that this variance will apply to:" on page 1.
LEGAL_ROW = (303.3, 333.6, 572.25, 351.1)   # label end, row bottom, right border, row top (PDF points)


@pytest.fixture(scope='module')
def codes():
    return Codes()


def confirmed(field, value):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='test:applicant', quote=str(value)))


def drawn(pdf: bytes, page: int, text: str) -> list[list[tuple]]:
    """Character boxes of every occurrence of `text` on a 0-based page."""
    textpage = pdfium.PdfDocument(pdf)[page].get_textpage()
    search = textpage.search(text, match_case=True)
    hits = []
    while (hit := search.get_next()) is not None:
        start, count = hit
        hits.append([b for b in (textpage.get_charbox(i) for i in range(start, start + count)) if b[2] > b[0]])
    return hits


def inside(boxes, rect) -> bool:
    x0, y0, x1, y1 = rect
    return all(x0 <= b[0] and b[2] <= x1 and y0 <= b[1] and b[3] <= y1 for b in boxes)


def test_a_typed_legal_description_fills_its_printed_row(codes):
    legal = 'Lot 12, Block 3, Plan 1234567 (EXAMPLE DATA)'
    facts = {key: value for key, value in FACTS.items() if key not in ('lot', 'block', 'plan')}
    case = sample_case(codes, provisions=['9.25.2.2.(1)'], facts={**facts, 'legal_description': legal})
    result = export_case(case, codes=codes, draft=True)
    [boxes] = drawn(result.pdf, 0, legal)
    assert inside(boxes, LEGAL_ROW)
    # Never split into invented lot, block and plan parts, and never moved to the appended pages.
    assert not {'Lot', 'Block', 'Plan'} & {p.field for p in result.placements}
    assert legal not in appendix_text(result) and 'See Appendix X' not in page_texts(result.pdf)[0]
    assert not render_problems(result)


def test_a_typed_legal_description_beside_lot_block_and_plan_is_not_dropped(codes):
    legal = 'Lot 0, Block 0, Plan EXAMPLE (EXAMPLE DATA)'
    case = sample_case(codes, provisions=['9.25.2.2.(1)'], facts={**FACTS, 'legal_description': legal})
    result = export_case(case, codes=codes)
    [boxes] = drawn(result.pdf, 0, legal)
    assert inside(boxes, LEGAL_ROW)
    shown = {p.field: norm(' '.join(p.lines)) for p in result.placements}
    assert (shown['Lot'], shown['Block'], shown['Plan']) == (FACTS['lot'], FACTS['block'], FACTS['plan'])


def test_a_legal_description_too_long_for_its_row_continues_once_from_that_row(codes):
    legal = 'Lot 12, Block 3, Plan 1234567; ' + ', '.join(f'parcel {n} of the EXAMPLE DATA subdivision'
                                                        for n in range(1, 13))
    facts = {key: value for key, value in FACTS.items() if key not in ('lot', 'block', 'plan')}
    case = sample_case(codes, provisions=['9.25.2.2.(1)'], facts={**facts, 'legal_description': legal})
    result = export_case(case, codes=codes, draft=True)
    [pointer] = [p for p in result.placements if p.ref and p.value == legal]
    [boxes] = drawn(result.pdf, 0, f'See Appendix {pointer.ref}')
    assert inside(boxes, LEGAL_ROW)
    assert appendix_text(result).count(norm(legal)) == 1
    assert not render_problems(result)


def test_an_intent_cell_shows_the_lookup_text_and_the_appendix_has_each_passage_once(codes):
    case = sample_case(codes, provisions=['9.25.2.2.(1)'])
    result = export_case(case, codes=codes)
    passages = [t for block in case.section_c[0].intents for t in block.intents]
    assert len(passages) > 1 and sum(map(len, passages)) > 1000      # more than one cell can hold
    cell = norm(' '.join(next(p for p in result.placements if p.field == 'Intent statement').lines))
    # The cell carries the passage itself, then says where the whole entry is; not a bare pointer.
    assert cell.startswith(f'{INTENT_LABEL}: {norm(passages[0])[:200]}')
    assert cell.endswith('(full text: Appendix C-1)')
    appendix = appendix_text(result)
    for passage in passages:
        assert appendix.count(norm(faithful_font_text(passage))) == 1   # the C-1 entry, never a second copy
    assert 'Intent entry for' not in appendix
    assert not render_problems(result)


def test_the_supporting_document_box_lists_whole_entries_before_naming_the_rest(codes):
    case = sample_case(codes, provisions=['9.25.2.2.(1)'])
    titles = [f'TEST typed document {n} (EXAMPLE DATA)' for n in range(1, 25)]
    for n, title in enumerate(titles, start=1):
        case.facts += [confirmed(f'evidence.typed_{n:02d}.title', title),
                       confirmed(f'evidence.typed_{n:02d}.responsible_party', f'TEST organisation {n}')]
    result = export_case(case, codes=codes, draft=True)
    box = norm(' '.join(next(p for p in result.placements if p.field == 'Supporting Doc').lines))
    total = 6 + len(titles)                                   # six attached files, then the typed listings
    match = re.search(rf'D-(\d+) to D-{total}: continued in Appendix D$', box)
    assert match and box.startswith('D-1: SYNTHETIC product-literature attachment - SYNTHETIC manufacturer role')
    shown = int(match.group(1)) - 1
    assert shown >= 6
    for n in range(1, shown + 1):
        assert f'D-{n}: ' in box
    assert f'D-{shown + 1}: ' not in box
    appendix = appendix_text(result)
    for title in titles:
        assert title in appendix
    assert not render_problems(result)


def test_every_confirmed_answer_reaches_the_pdf(codes):
    """Nothing the applicant confirmed is silently dropped: it is on the form or in the labelled appendix."""
    legal = 'Lot 0, Block 0, Plan EXAMPLE (EXAMPLE DATA)'
    case = sample_case(codes, facts={**FACTS, 'legal_description': legal})
    result = export_case(case, codes=codes)
    text = norm(' '.join(page_texts(result.pdf)))
    for key in ('owner_name', 'owner_rep_name', 'mailing_address', 'request_date', 'permit_number',
                'municipal_address', 'legal_description', 'alternative_description', 'rationale',
                'risk_assessment', 'mitigating_measures', 'assumptions_limits', 'operation_maintenance',
                'qualifications'):
        value = {**FACTS, 'legal_description': legal}[key]
        assert norm(value) in text, key
