"""SCC variance form export: field map coverage, hash check, gating, and a render-and-extract test.

The render test draws the exported PDF with pypdfium2 and checks every filled value: each shown line must be
found on its page with every character box inside the field rectangle (so clipped or overflowing text fails),
and every value the form shows only as a reference must appear in the appendix text.
"""
import io
import re
import shutil

import pypdf
import pypdfium2 as pdfium
import pytest

from engine.codes import Codes
from engine.export import ExportBlocked, FormMismatch, export_case, form_path, load_field_map
from engine.export.sample import FACTS, sample_case
from engine.models import INTENT_LABEL, Fact, Gap, Source

FORM = form_path()
pytestmark = pytest.mark.skipif(not FORM.exists(), reason=f'SCC form not present at {FORM} (git-excluded)')


@pytest.fixture(scope='module')
def codes():
    return Codes()


@pytest.fixture(scope='module')
def case(codes):
    return sample_case(codes)


@pytest.fixture(scope='module')
def final(case, codes):
    return export_case(case, codes=codes)


def norm(s: str) -> str:
    return ' '.join(s.split())


def page_texts(pdf: bytes) -> list[str]:
    doc = pdfium.PdfDocument(pdf)
    return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]


FOOTER = re.compile(r'Batatis appendix to SCC variance form - case \S+\s+Appendix page \d+')


def appendix_text(pdf: bytes, form_pages: int) -> str:
    """Appendix pages joined with their running footers removed, so text that crosses a page break matches."""
    return norm(' '.join(FOOTER.sub(' ', t) for t in page_texts(pdf)[form_pages:]))


def test_field_map_covers_all_87_fields_once():
    fmap = load_field_map()
    reader = pypdf.PdfReader(FORM)
    fields = set(reader.get_fields())
    applicant = [*fmap['text_fields'], *fmap['checkboxes'],
                 *[f for r in fmap['section_c_rows'] for f in r.values()],
                 *[f for r in fmap['section_d_rows'] for f in r.values()]]
    skipped = [f for group in fmap['skipped'].values() for f in group]
    assert len(fields) == fmap['field_count'] == 87
    assert len(applicant) == 50 and len(set(applicant)) == 50
    assert sorted(applicant + skipped) == sorted(fields)


def test_refuses_a_form_with_a_different_hash(case, codes, tmp_path):
    other = tmp_path / 'form.pdf'
    shutil.copy(FORM, other)
    with open(other, 'ab') as f:
        f.write(b'\n% changed\n')
    with pytest.raises(FormMismatch, match='SHA-256'):
        export_case(case, codes=codes, form=other)


def test_blocks_on_unconfirmed_facts_and_blocking_gaps(case, codes):
    src = Source(type='user_text', ref='m1')
    blocked = case.model_copy(deep=True)
    blocked.facts.append(Fact(field='permit_number', value='BP-1', kind='pointed', source=src))
    blocked.facts.append(Fact(field='lot', value='99', kind='proposed', source=src, confidence=0.6))
    blocked.gaps.append(Gap(section='D', field='risk_assessment', message='risk assessment not written'))
    blocked.facts = [f for f in blocked.facts if f.field != 'owner_name']
    with pytest.raises(ExportBlocked) as e:
        export_case(blocked, codes=codes)
    text = ' '.join(e.value.reasons)
    assert 'risk assessment not written' in text and 'required field "owner_name"' in text
    assert '"lot"' not in text            # an unconfirmed fact with a confirmed value for the field does not block
    blocked.facts.append(Fact(field='storeys', value=2, kind='proposed', source=src, confidence=0.6))
    with pytest.raises(ExportBlocked, match='unconfirmed proposed fact "storeys"'):
        export_case(blocked, codes=codes)

    draft = export_case(blocked, codes=codes, draft=True)
    texts = page_texts(draft.pdf)
    assert all('DRAFT' in t for t in texts)
    assert 'risk assessment not written' in appendix_text(draft.pdf, draft.form_pages)
    assert '99' not in norm(texts[0]).split()          # proposed value never reaches the form
    assert FACTS['lot'] in norm(texts[0]).split()


def test_final_export_has_no_widgets_or_help_popups(final):
    reader = pypdf.PdfReader(io.BytesIO(final.pdf))
    assert '/AcroForm' not in reader.trailer['/Root']
    for page in reader.pages:
        annots = page.get('/Annots')
        assert all(a.get_object()['/Subtype'] != '/Widget' for a in (annots.get_object() if annots else []))
    text = ' '.join(page_texts(final.pdf))
    assert 'full legal description of the property' not in text      # ATS Popup
    assert 'objective-based format' not in text                       # Section C Popup
    assert 'DRAFT' not in text


def test_render_and_extract_every_filled_value(final, case):
    doc = pdfium.PdfDocument(final.pdf)
    appendix = appendix_text(final.pdf, final.form_pages)
    assert final.form_pages == 5 and final.appendix_pages >= 1
    assert len(final.placements) >= 40
    for pl in final.placements:
        tp = doc[pl.page].get_textpage()
        x0, y0, x1, y1 = pl.rect
        for line in pl.lines:
            searcher = tp.search(line, match_case=True)
            hits = []
            while (hit := searcher.get_next()) is not None:
                hits.append(hit)
            boxes_ok = [all(x0 - 0.5 <= b[0] and b[2] <= x1 + 0.5 and y0 - 0.5 <= b[1] and b[3] <= y1 + 0.5
                            for b in (tp.get_charbox(i) for i in range(start, start + count)) if b[2] > b[0])
                        for start, count in hits]
            assert any(boxes_ok), f'{pl.field}: "{line}" not drawn inside {pl.rect} on page {pl.page + 1}'
        if norm(' '.join(pl.lines)) != norm(pl.value):
            assert pl.ref and norm(pl.value) in appendix, f'{pl.field}: full value missing from appendix'
    shown = {pl.field: norm(' '.join(pl.lines)) for pl in final.placements}
    assert shown['Owner'] == FACTS['owner_name'] and shown['Lot'] == FACTS['lot']
    assert shown['Date of Reqeuest'] == FACTS['request_date']


def test_section_c_cells_and_appendix_match_section_c_rows(final, case, codes):
    shown = {pl.field: norm(' '.join(pl.lines)) for pl in final.placements}
    fmap = load_field_map()
    rows = case.section_c
    assert len(rows) > 5                           # fixture exercises the overflow path
    for slot, row in zip(fmap['section_c_rows'][:4], rows):
        assert shown[slot['article']] == row.provision_id
        objs = list(dict.fromkeys(p.objective for p in row.pairs))
        fns = list(dict.fromkeys(p.function for p in row.pairs))
        assert shown[slot['objective']] in (', '.join(objs) if objs else 'No table row', f'See Appendix C-{rows.index(row) + 1}')
        assert shown[slot['function']] in (', '.join(fns) if fns else 'No table row', f'See Appendix C-{rows.index(row) + 1}')
        if row.attribution_status == 'no row in the attribution table':
            assert 'No row in the NBC(AE) attribution table' in shown[slot['intent']]
    assert f'rows 5 to {len(rows)}' in shown[fmap['section_c_rows'][4]['intent']]

    appendix = appendix_text(final.pdf, final.form_pages)
    assert INTENT_LABEL in appendix
    for k, row in enumerate(rows, start=1):
        assert f'C-{k} {row.provision_id}' in appendix
        assert row.citation in appendix
        for p in row.pairs:
            assert f'{p.function} {norm(p.function_text or "")}' in appendix
            assert f'{p.objective} {norm(p.objective_text or "")}' in appendix
        for blk in row.intents:
            for t in blk.intents:
                assert norm(t) in appendix
    for n in (5, 6):
        assert FACTS[f'supporting_doc.{n}.name'] in appendix


def test_differing_intent_is_labelled(codes):
    case = sample_case(codes, provisions=['9.32.1.3.(2)'])
    [row] = case.section_c
    assert row.differs
    res = export_case(case, codes=codes)
    shown = {pl.field: norm(' '.join(pl.lines)) for pl in res.placements}
    assert 'attributed differently' in shown['Intent statement']
    appendix = appendix_text(res.pdf, res.form_pages)
    assert 'attributed differently from NBC(AE) 2023' in appendix
    assert all(re.sub(r'[\[\]]', '', x) in appendix or x in appendix for x in row.only_in_ae)


def test_long_section_a_value_moves_to_appendix(case, codes):
    long = case.model_copy(deep=True)
    addr = 'Unit 1200, ' + ', '.join(f'Building {i} Long Industrial Business Park Road' for i in range(14)) + ', Calgary AB'
    for f in long.facts:
        if f.field == 'mailing_address':
            f.value = addr
    res = export_case(long, codes=codes)
    pl = next(p for p in res.placements if p.field == 'Mailing Address')
    assert pl.lines == [f'See Appendix {pl.ref}'] and pl.value == addr
    assert addr in appendix_text(res.pdf, res.form_pages)
