"""Public PDF regressions for the user-supplied challenge form, physical pages 5-11."""
import hashlib
import io
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from pypdf import PdfReader, PdfWriter
from fastapi.testclient import TestClient

from engine.codes import Codes
from engine.export import ExportBlocked, FormMismatch, export_case, form_path, load_field_map
from engine.export.scc import load_form
from engine.export.sample import sample_case
from engine.export.g3 import appendix_text, citation_problems, coverage_problems, render_problems
from engine.export.text import faithful_font_text, pdf_safe
from engine.models import INTENT_LABEL, Fact, Source
from engine.api import create_app
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import store_with_synthetic_files
from engine.tests.form_layout_helpers import drawn, segments


def prepare_form(*args):
    from engine.export import prepare_form as prepare
    return prepare(*args)


def row_fields(index):
    from engine.export.challenge_form import row_fields as names
    return names(index)


@pytest.fixture
def legacy_form():
    from engine.export import FormNotFound
    try:
        return load_form(None, load_field_map('scc_2026-10'))
    except FormNotFound:
        pytest.skip('legacy SCC form requires the build-time fetch or BATATIS_SCC_FORM')


VERSION = 'challenge_2026-09-15'
SOURCE_HASH = '761bf8d9d8e93445a49ce58c443a1a8928fa08a45a031a0adc371d45fd5a7d55'


def test_default_public_export_uses_the_exact_seven_page_challenge_form():
    codes = Codes()
    result = export_case(sample_case(codes, provisions=['9.25.2.2.(1)']), codes=codes)
    assert result.field_map == VERSION
    assert result.form_pages == 7
    reader = PdfReader(io.BytesIO(result.pdf))
    assert 'Part 4' in reader.pages[5].extract_text()
    assert 'Professional Design' in reader.pages[6].extract_text()
    # This wording distinguishes the supplied source from the old web form.
    assert 'site-specific' in reader.pages[0].extract_text()
    assert not reader.get_fields()
    assert not any(a.get_object().get('/Subtype') == '/Widget'
                   for page in reader.pages for a in page.get('/Annots', []))


def test_default_template_is_portable_and_hash_checked():
    path = form_path()
    assert path.is_relative_to(Path(__file__).resolve().parents[1] / 'export')
    fmap = load_field_map()
    assert fmap['source']['sha256'] == SOURCE_HASH
    assert fmap['source']['physical_pages'] == list(range(5, 12))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == fmap['sha256']
    assert len(PdfReader(path).pages) == 7


PROVISIONS = [
    '9.25.2.2.(1)', '9.23.17.2.(1)', '9.27.3.4.(1)', '9.32.1.3.(2)',
    '4.1.6.10.(4)', '4.1.7.13.(6)', '9.9.10.1.(1)', '9.25.5.1.(1)',
    '9.10.9.1.(1)', '9.10.9.2.(1)', '9.10.9.3.(1)', '9.10.9.4.(1)',
    '9.10.9.5.(1)', '9.10.9.6.(1)', '9.10.9.7.(1)', '9.10.9.8.(1)',
    '9.10.9.9.(1)', '9.10.9.10.(1)', '9.10.9.11.(1)', '9.10.9.12.(1)',
    '9.10.9.13.(1)', '9.10.9.14.(1)', '9.10.9.15.(1)', '9.10.9.16.(1)',
]


@pytest.mark.parametrize('count', [0, 1, 2, 5, 6, 12, 24])
def test_each_selected_canonical_row_appears_once_in_the_native_table(count):
    codes = Codes()
    case = sample_case(codes, provisions=PROVISIONS[:count])
    result = export_case(case, codes=codes, draft=count == 0)
    articles = [p for p in result.placements if p.field.startswith('Article(s)')]
    assert [p.value for p in articles] == [r.provision_id for r in case.section_c]
    assert len(articles) == count
    reader = PdfReader(io.BytesIO(result.pdf))
    form_text = ' '.join(p.extract_text() for p in reader.pages[:result.form_pages - 5])
    doc = pdfium.PdfDocument(result.pdf)
    article_text = ' '.join(doc[p.page].get_textpage().get_text_bounded(*p.rect) for p in articles)
    for row in case.section_c:
        # Intent prose can legitimately cross-reference another selected article.
        assert article_text.count(row.provision_id) == 1
    assert 'Rows 5-' not in form_text and 'Rows 6-' not in form_text
    assert not render_problems(result)


def test_native_intent_uses_deterministic_source_text_with_lossless_overflow():
    codes = Codes()
    case = sample_case(codes, provisions=['9.25.2.2.(1)'])
    result = export_case(case, codes=codes)
    boxes = segments(result, 'Intent statement')
    passages = [text for block in case.section_c[0].intents for text in block.intents]
    shown = drawn(result, boxes)
    assert all(p.size == 9 and p.ref is None for p in boxes)
    assert shown == f'{INTENT_LABEL}: ' + ' '.join(' '.join(pdf_safe(t) for t in passages).split())
    appendix = appendix_text(result)
    for text in passages:
        assert ' '.join(faithful_font_text(text).split()) in appendix
    assert not render_problems(result)


@pytest.mark.parametrize('count', [0, 1, 2, 5, 6, 12, 24])
def test_dynamic_editable_blank_has_independent_canonical_widgets_and_appearances(count):
    fmap = load_field_map()
    original = load_form(None, fmap)
    blank, mapped = prepare_form(original, fmap, count)
    assert prepare_form(original, fmap, count)[0] == blank
    reader = PdfReader(io.BytesIO(blank))
    fields = reader.get_fields()
    widgets = [a for page in reader.pages for a in page.get('/Annots', [])
               if a.get_object().get('/Subtype') == '/Widget']
    assert len(widgets) == len(fields) == mapped['field_count'] == 54 + 4 * max(1, count)
    assert len({str(a.get_object()['/T']) for a in widgets}) == len(widgets)
    canonical = {r.idnum for r in reader.trailer['/Root']['/AcroForm']['/Fields']}
    assert canonical == {r.idnum for r in widgets}
    assert len(mapped['section_c_rows']) == max(1, count)
    assert int(reader.metadata['/BatatisAttributionRows']) == max(1, count)
    assert int(reader.metadata['/BatatisFormPages']) == len(reader.pages) == mapped['form_pages']
    expected = {'Owner': 'SYNTHETIC editable owner'}
    expected.update({name: f'ROW-{i + 1}-{key}' for i in range(max(1, count))
                     for key, name in row_fields(i).items()})
    writer = PdfWriter(clone_from=io.BytesIO(blank))
    writer.update_page_form_field_values(None, expected, auto_regenerate=False)
    buf = io.BytesIO()
    writer.write(buf)
    filled = PdfReader(io.BytesIO(buf.getvalue()))
    for name, value in expected.items():
        assert filled.get_fields()[name]['/V'] == value
    appearances = []
    for page in filled.pages:
        for ref in page.get('/Annots', []):
            w = ref.get_object()
            if w.get('/T') in expected:
                assert '/Parent' not in w and w['/V'] == expected[w['/T']]
                appearance = w['/AP']['/N']
                assert appearance.get_data()
                appearances.append(appearance.indirect_reference.idnum)
    assert len(appearances) == len(set(appearances)) == len(expected)


@pytest.mark.parametrize('count', [1, 2, 5, 6, 12])
def test_review_appeal_and_original_appendix_pages_are_unchanged(count):
    fmap = load_field_map()
    source = load_form(None, fmap)
    original = pdfium.PdfDocument(source)
    result = export_case(sample_case(Codes(), provisions=PROVISIONS[:count]), codes=Codes())
    doc = pdfium.PdfDocument(result.pdf)
    for i in range(5):
        expected = original[i + 2].render(scale=1).to_pil()
        actual = doc[result.form_pages - 5 + i].render(scale=1).to_pil()
        assert actual.tobytes() == expected.tobytes()
    # The original printed Appendix is outside the generated citation narrative.
    assert '2.2.2.1.(1) Information Required' not in '\n'.join(result.text)


def test_legacy_form_remains_explicit_and_hash_matching(legacy_form):
    legacy = load_field_map('scc_2026-10')
    source = load_form(None, legacy)
    assert hashlib.sha256(source).hexdigest() == 'f44640ca005c957c11a2387d2768fffc35ef93c97125dcca37436fcc0b9afc1d'
    result = export_case(sample_case(Codes()), codes=Codes(), version=legacy['version'])
    assert result.form_pages == 5 and result.field_map == legacy['version']
    assert len(PdfReader(form_path(legacy['version'])).get_fields()) == 87
    with pytest.raises(FormMismatch):
        load_form(form_path(), legacy)


def test_an_old_download_override_cannot_silently_replace_the_supplied_default(monkeypatch, legacy_form):
    legacy_path = form_path('scc_2026-10')
    monkeypatch.setenv('BATATIS_SCC_FORM', str(legacy_path))
    result = export_case(sample_case(Codes(), provisions=PROVISIONS[:1]), codes=Codes(), draft=True)
    assert result.field_map == VERSION and result.form_pages == 7
    assert form_path() != legacy_path
    assert load_form(None, load_field_map('scc_2026-10')) == legacy_path.read_bytes()
    with pytest.raises(FormMismatch, match='SHA-256'):
        export_case(sample_case(Codes()), codes=Codes(), form=legacy_path, draft=True)


def test_confirmed_unmapped_decisions_consent_and_signatures_never_fill_the_source():
    case = sample_case(Codes(), provisions=PROVISIONS[:1])
    marker = 'UNAUTHORIZED HUMAN DECISION MARKER'
    case.facts.extend(Fact(field=name, value=marker, kind='pointed', status='confirmed',
                          source=Source(type='user_text', ref='synthetic', quote=marker))
                      for name in ['Jurisdiction', 'SCO', 'Must be Met', 'Reasons for Refusal',
                                   'Signature1', 'Signature3', 'Check Box14', 'Date1', 'Date2'])
    result = export_case(case, codes=Codes())
    assert marker not in ' '.join(p.extract_text() for p in PdfReader(io.BytesIO(result.pdf)).pages)
    skipped = {n for names in load_field_map()['skipped'].values() for n in names}
    assert not skipped & {p.field for p in result.placements}


def test_saved_answers_change_the_real_http_pdf_bytes(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    codes = Codes()
    case = store_with_synthetic_files(store, sample_case(codes, provisions=PROVISIONS[:6]))
    with TestClient(create_app(store=store, codes=codes)) as client:
        before = client.post(f'/cases/{case.id}/export', json={'draft': True})
        assert before.status_code == 200 and before.headers['content-type'] == 'application/pdf'
        value = 'SYNTHETIC revised PDF preview owner'
        fact = Fact(field='owner_name', value=value, kind='pointed', status='confirmed',
                    source=Source(type='user_text', ref='synthetic saved edit', quote=value))
        assert client.post(f'/cases/{case.id}/facts', json=fact.model_dump()).status_code == 200
        after = client.post(f'/cases/{case.id}/export', json={'draft': True})
        assert after.status_code == 200 and before.content != after.content
        reader = PdfReader(io.BytesIO(after.content))
        assert value in reader.pages[0].extract_text()
        assert reader.metadata['/BatatisFormVersion'] == VERSION
        assert reader.metadata['/BatatisAttributionRows'] == '6'
        count = int(reader.metadata['/BatatisFormPages'])
        assert count > 8 and count < len(reader.pages)
        assert 'Part 4' in reader.pages[count - 2].extract_text()
        assert 'Professional Design' in reader.pages[count - 1].extract_text()
        assert not reader.get_fields()


def test_existing_validator_passes_for_the_new_native_intent_projection():
    from engine.export.demo_cases import CASES, demo_case
    codes = Codes()
    for case in [sample_case(codes, provisions=PROVISIONS[:12]), *(demo_case(name, codes) for name in CASES)]:
        result = export_case(case, codes=codes)
        assert not citation_problems(result, db_path=codes.db_path)


def test_coverage_detects_a_missing_last_native_article_instead_of_shrinking_the_expected_table():
    codes = Codes()
    case = sample_case(codes, provisions=PROVISIONS[:6])
    result = export_case(case, codes=codes)
    result.placements = [p for p in result.placements if p.field != 'Article(s)5']
    assert 'Article(s)5 is blank' in coverage_problems(case, result)


@pytest.mark.parametrize('version,count', [(VERSION, 0), (VERSION, 1), (VERSION, 6), (VERSION, 12),
                                          ('scc_2026-10', 0), ('scc_2026-10', 12)])
def test_draft_pdf_has_no_added_visible_draft_marks_but_keeps_the_validation_contract(version, count, request):
    if version == 'scc_2026-10':
        request.getfixturevalue('legacy_form')
    codes = Codes()
    case = sample_case(codes, provisions=PROVISIONS[:count])
    marker = 'UNCONFIRMED SHOULD NEVER APPEAR'
    case.facts.append(Fact(field='owner_name', value=marker, kind='pointed', status='unconfirmed',
                          source=Source(type='user_text', ref='synthetic unconfirmed edit')))
    with pytest.raises(ExportBlocked):
        export_case(case, codes=codes, version=version)
    result = export_case(case, codes=codes, version=version, draft=True)
    assert result.draft and result.open_items
    reader = PdfReader(io.BytesIO(result.pdf))
    assert reader.metadata['/Title'].endswith('(DRAFT)')
    assert marker not in ' '.join(p.extract_text() for p in reader.pages)
    assert 'Owner' not in {p.field for p in result.placements}
    for page in reader.pages:
        text = page.extract_text()
        assert 'DRAFT' not in text and 'not for submission; see appendix' not in text
    # The draft's open items stay in the result for the questions and Review; the document never lists them.
    pdf_text = ' '.join(' '.join(p.extract_text().split()) for p in reader.pages)
    assert 'Open items' not in pdf_text and 'Not provided or not confirmed' not in pdf_text
    assert not any(' '.join(item.split())[:60] in pdf_text for item in result.open_items)
