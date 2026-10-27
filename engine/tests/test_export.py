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
from engine.copyright import NRC_PUBLICATION_URL, has_consecutive_words, words
from engine.export import ExportBlocked, FormMismatch, export_case, form_path, load_field_map
from engine.export.sample import FACTS, sample_case
from engine.export.text import faithful_font_text, pdf_safe
from engine.process_fields import process_fields
from engine.section_c import section_c_rows
from engine.section_d import supporting_documents
from engine.models import INTENT_LABEL, Fact, Gap, Source
from engine.package_format import CONTEXT
from engine.tests.form_layout_helpers import drawn, segments, shown_fields

FORM = form_path()
pytestmark = pytest.mark.skipif(
    not FORM.exists(), reason='SCC form not present at reference/guides/SCC-Variance-Form.pdf (git-excluded)')


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


@pytest.mark.parametrize('version,field_count,applicant_count', [
    ('challenge_2026-09-15', 74, 37), ('scc_2026-10', 87, 50),
])
def test_field_map_covers_every_source_field_once(version, field_count, applicant_count):
    fmap = load_field_map(version)
    source = form_path(version)
    if not source.is_file():
        pytest.skip('legacy SCC form not available (build-time fetch or BATATIS_SCC_FORM)')
    reader = pypdf.PdfReader(source)
    fields = set(reader.get_fields())
    applicant = [*fmap['text_fields'], *fmap['checkboxes'],
                 *[f for r in fmap['section_c_rows'] for f in r.values()],
                 *[f for r in fmap['section_d_rows'] for f in r.values()],
                 *([fmap['supporting_document_field']] if fmap.get('supporting_document_field') else [])]
    skipped = [f for group in fmap['skipped'].values() for f in group]
    assert len(fields) == fmap['field_count'] == field_count
    assert len(applicant) == len(set(applicant)) == applicant_count
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
    assert 'risk assessment not written' in text and 'section A, owner_name:' in text
    assert 'unconfirmed proposed fact "lot"' in text  # the newer unknown revision supersedes the old value
    blocked.facts.append(Fact(field='storeys', value=2, kind='proposed', source=src, confidence=0.6))
    with pytest.raises(ExportBlocked, match='unconfirmed proposed fact "storeys"'):
        export_case(blocked, codes=codes)

    draft = export_case(blocked, codes=codes, draft=True)
    texts = page_texts(draft.pdf)
    assert draft.draft is True
    assert pypdf.PdfReader(io.BytesIO(draft.pdf)).metadata.title.endswith(' (DRAFT)')
    # The draft keeps its open items in the result. The form and appendix carry no to-do list; a saved open
    # item travels only as a labelled administrative source record after them, so an officer reads the same gap.
    assert any('risk assessment not written' in item for item in draft.open_items)
    document = draft.form_pages + draft.appendix_pages
    assert 'risk assessment not written' not in ' '.join(texts[:document])
    assert any(text.startswith(CONTEXT) and 'risk assessment not written' in text for text in texts[document:])
    assert '99' not in norm(texts[0]).split()          # proposed value never reaches the form
    assert 'Lot' not in {p.field for p in draft.placements}  # the older lot value must not silently return


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
    assert len(case.section_c) == 8
    assert final.form_pages > 8 and final.appendix_pages >= 1  # full intents grow the source-style rows
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
    shown = shown_fields(final)
    for pl in final.placements:
        if shown[pl.field] != norm(pl.value):
            assert pl.ref and norm(pl.value) in appendix, f'{pl.field}: full value missing from its boxes or appendix'
    assert shown['Owner'] == FACTS['owner_name'] and shown['Lot'] == FACTS['lot']
    assert shown['Date of Reqeuest'] == FACTS['request_date']


def test_section_c_cells_and_appendix_match_section_c_rows(final, case, codes):
    shown = shown_fields(final)
    from engine.export.challenge_form import row_fields
    rows = case.section_c
    assert len(rows) > 5                           # fixture exercises native table expansion
    slots = [row_fields(i) for i in range(len(rows))]
    for slot, row in zip(slots, rows):
        assert shown[slot['article']] == row.provision_id
        objs = list(dict.fromkeys(p.objective for p in row.pairs))
        fns = list(dict.fromkeys(p.function for p in row.pairs))
        assert shown[slot['objective']] in (', '.join(objs) if objs else 'No table row', f'See Appendix C-{rows.index(row) + 1}')
        assert shown[slot['function']] in (', '.join(fns) if fns else 'No table row', f'See Appendix C-{rows.index(row) + 1}')
        if row.attribution_status == 'no row in the attribution table':
            assert 'No row in the NBC(AE) attribution table' in shown[slot['intent']]
    assert [shown[slot['article']] for slot in slots] == [row.provision_id for row in rows]
    assert not any(value.startswith('Rows ') for name, value in shown.items() if name.startswith('Article(s)'))

    appendix = appendix_text(final.pdf, final.form_pages)
    assert INTENT_LABEL in appendix
    for k, row in enumerate(rows, start=1):
        assert f'C-{k} {row.provision_id}' in appendix
        assert row.citation in appendix
        for p in row.pairs:
            for piece in (p.function_text, p.objective_text, p.application_note):
                if piece:
                    assert has_consecutive_words(appendix, words(piece))
        for blk in row.intents:
            for t in [*blk.intents, *blk.notes]:
                if t:
                    assert has_consecutive_words(appendix, words(t))
    assert NRC_PUBLICATION_URL in appendix
    for n in (5, 6):
        assert FACTS[f'supporting_doc.{n}.name'] in appendix


def test_differing_intent_is_labelled(codes):
    case = sample_case(codes, provisions=['9.32.1.3.(2)'])
    [row] = case.section_c
    assert row.differs
    res = export_case(case, codes=codes)
    shown = shown_fields(res)
    assert 'attributed differently' in shown['Intent statement']
    appendix = appendix_text(res.pdf, res.form_pages)
    assert 'attributed differently from NBC(AE) 2023' in appendix
    assert all(re.sub(r'[\[\]]', '', x) in appendix or x in appendix for x in row.only_in_ae)


def test_long_section_a_value_grows_its_form_box(case, codes):
    long = case.model_copy(deep=True)
    addr = 'Unit 1200, ' + ', '.join(f'Building {i} Long Industrial Business Park Road' for i in range(14)) + ', Calgary AB'
    for f in long.facts:
        if f.field == 'mailing_address':
            f.value = addr
    res = export_case(long, codes=codes)
    boxes = segments(res, 'Mailing Address')
    assert all(p.ref is None and p.size == 10 and p.value == addr for p in boxes)
    assert drawn(res, boxes) == addr
    assert addr not in appendix_text(res.pdf, res.form_pages)


def test_direct_export_cannot_bypass_authoritative_completeness(case, codes):
    bypass = case.model_copy(deep=True)
    keep = {'owner_name', 'mailing_address', 'request_date', 'municipal_address'}
    bypass.facts = [f for f in bypass.facts if f.field in keep]
    bypass.evidence = []
    bypass.gaps = []
    with pytest.raises(ExportBlocked) as error:
        export_case(bypass, codes=codes)
    reasons = ' '.join(error.value.reasons)
    assert 'risk_assessment' in reasons and 'mitigating_measures' in reasons
    assert 'assumptions_and_limits' in reasons and 'supporting evidence' in reasons
    assert 'professional' in reasons and 'legal_description' in reasons
    # Omitting the Codes argument cannot turn a verified export into a trust-the-caller path.
    with pytest.raises(ExportBlocked):
        export_case(bypass)


@pytest.mark.parametrize('change', ['wrong_citation', 'fabricated_intent', 'intent_page', 'comparison', 'wrong_pair', 'deleted_row'])
def test_stale_section_c_blocks_final_and_draft_rebuilds_from_database(codes, change):
    case = sample_case(codes, provisions=['9.25.2.2.(1)'])
    row = case.section_c[0]
    if change == 'wrong_citation':
        row.citation = codes.citation('9.9.10.1.(1)', 'B')
    elif change == 'fabricated_intent':
        row.intents[0].intents = ['FORGED INTENT CONTENT MUST NEVER BE EXPORTED']
    elif change == 'intent_page':
        row.intents[0].pdf_page = 1
    elif change == 'comparison':
        row.intent_comparison = 'fabricated'
    elif change == 'wrong_pair':
        row.pairs[0].objective = 'FORGED-OBJECTIVE'
    else:
        case.section_c = []
    case.gaps = []
    before = case.model_dump_json()
    with pytest.raises(ExportBlocked):
        export_case(case, codes=codes)
    result = export_case(case, codes=codes, draft=True)
    text = appendix_text(result.pdf, result.form_pages)
    assert 'FORGED INTENT CONTENT' not in text and 'FORGED-OBJECTIVE' not in text
    fresh = section_c_rows(['9.25.2.2.(1)'], codes)[0]                 # what the database says, not the case
    assert result.open_items and norm(faithful_font_text(fresh.intents[0].intents[0])) in text
    assert codes.citation('9.25.2.2.(1)', 'B') in text
    assert case.model_dump_json() == before


@pytest.mark.parametrize('field', ['owner_name', 'owner', 'request_date', 'lot', 'assumptions_limits',
    'process.assumptions_and_limits', 'evidence.synthetic_1.responsible_party', 'evidence.synthetic_1.file_ref',
    'evidence.synthetic_1.title'])
def test_latest_unknown_revision_blocks_final_and_does_not_restore_old_values(case, codes, field):
    revised = case.model_copy(deep=True)
    revised.facts.append(Fact(field=field, value='NEW UNCONFIRMED VALUE', kind='pointed', status='unconfirmed',
                             source=Source(type='user_text', ref='synthetic-revision')))
    with pytest.raises(ExportBlocked):
        export_case(revised, codes=codes)
    draft = export_case(revised, codes=codes, draft=True)
    shown = {p.field: p.value for p in draft.placements}
    assert 'NEW UNCONFIRMED VALUE' not in ' '.join(page_texts(draft.pdf))
    if field in ('owner_name', 'owner'):
        assert 'Owner' not in shown and 'Owner Print' not in shown
    if field == 'request_date':
        assert 'Date of Reqeuest' not in shown
    if field == 'lot':
        assert 'Lot' not in shown
    if field in ('assumptions_limits', 'process.assumptions_and_limits'):
        assert FACTS['assumptions_limits'] not in appendix_text(draft.pdf, draft.form_pages)
    if field == 'evidence.synthetic_1.title':
        assert FACTS['supporting_doc.1.name'] not in appendix_text(draft.pdf, draft.form_pages)


def test_authentic_process_answers_and_linked_files_are_in_final_appendix(final, case, codes):
    text = appendix_text(final.pdf, final.form_pages)
    assert 'P. Alternative solution (Div C 2.3.1): applicant-written documentation' in text and 'SYNTHETIC' in text
    for field in process_fields(case, codes):
        assert field.answer is not None
        assert norm(field.answer.value) in text and field.answer.source.ref in text
    for doc in supporting_documents(case):
        assert norm(doc.title) in text and norm(doc.responsible_party) in text and doc.file.ref in text
    assert 'Section C performance issues addressed' in text


def test_generated_or_altered_process_content_never_exports(codes):
    case = sample_case(codes, provisions=['9.25.2.2.(1)'])
    for fact in case.facts:
        if fact.field == 'risk_assessment':
            fact.value = 'GENERATED RISK CONTENT MUST NOT APPEAR'
    with pytest.raises(ExportBlocked):
        export_case(case, codes=codes)
    draft = export_case(case, codes=codes, draft=True)
    assert 'GENERATED RISK CONTENT' not in ' '.join(page_texts(draft.pdf))


def test_source_units_use_explicit_fallbacks_instead_of_question_marks(codes):
    assert faithful_font_text('10⁻⁴ W/(m²·K), m⁴, CO₂, μ, ≤') == '10^(-4) W/(m²·K), m^(4), CO_(2), µ, <='
    assert 'U+03B4 GREEK SMALL LETTER DELTA' in faithful_font_text('δ')
    assert '?' not in pdf_safe('10⁻⁴ m⁴ δ')
    case = sample_case(codes, provisions=['9.25.2.2.(1)'])
    for fact in case.facts:
        if fact.field == 'assumptions_limits':
            fact.value = 'SYNTHETIC units passage, assumed only: 10⁻⁴ W/(m²·K), m⁴, CO₂ and μ.'
            fact.source.quote = fact.value
    result = export_case(case, codes=codes)
    assert 'assumed only: 10^(-4) W/(m²·K), m^(4), CO_(2) and µ.' in appendix_text(result.pdf, result.form_pages)


def test_scientific_notation_in_real_provision_text_survives_export(codes):
    # With the rebuilt database these source sentences contain x₃₀, h₁/h₂ and Greek α.
    # The same test also verifies faithful source text when run against the older build.
    provisions = ['4.1.6.10.(4)', '4.1.7.13.(6)']
    case = sample_case(codes, provisions=provisions)
    case.title = 'SYNTHETIC source-notation export test (no technical assessment)'
    result = export_case(case, codes=codes)
    text = appendix_text(result.pdf, result.form_pages)
    for pid in provisions:
        source = codes.provision(pid, 'B')['text']
        rendered = faithful_font_text(source)
        assert has_consecutive_words(text, words(rendered))
        assert NRC_PUBLICATION_URL in text
        for glyphs, notation in [('x₃₀', 'x_(30)'), ('h₁', 'h_(1)'), ('h₂', 'h_(2)')]:
            if glyphs in source:
                assert notation in text
        if 'α' in source:
            assert '[U+03B1 GREEK SMALL LETTER ALPHA]' in text
