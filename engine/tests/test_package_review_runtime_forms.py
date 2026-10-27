"""Actual official exports and independently filled editable blanks at the upload-reader seam."""
import io

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, RectangleObject

from engine.codes import Codes
from engine.export import export_case, load_field_map
from engine.export.scc import load_form
from engine.export.sample import sample_case
from engine.package_format import CONTEXT
from engine.review.package import review_uploads
from engine.review.pdf_reader import read_pdf
from engine.tests.test_supplied_form_export import PROVISIONS, prepare_form, legacy_form


def editable(count, *, version='challenge_2026-09-15', flatten=False):
    fmap = load_field_map(version)
    from engine.export import FormNotFound
    try:
        source = load_form(None, fmap)
    except FormNotFound:
        if version == 'scc_2026-10':
            pytest.skip('legacy SCC form requires the build-time fetch or BATATIS_SCC_FORM')
        raise
    blank, runtime = prepare_form(source, fmap, count)
    writer = PdfWriter(clone_from=io.BytesIO(blank))
    values = {'Owner': 'SYNTHETIC actual owner', 'Supporting Doc': 'SYNTHETIC attachment - SYNTHETIC author'}
    values.update({row['article']: PROVISIONS[index] for index, row in enumerate(runtime['section_c_rows'])})
    writer.update_page_form_field_values(None, values, auto_regenerate=False, flatten=flatten)
    if flatten:
        writer.remove_annotations(subtypes='/Widget')
        from pypdf.generic import NameObject
        writer.root_object.pop(NameObject('/AcroForm'), None)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.mark.parametrize('count', [0, 1, 2, 5, 6, 12, 24])
def test_official_export_reupload_uses_only_actual_rows_and_generated_appendix(count):
    codes = Codes()
    case = sample_case(codes, provisions=PROVISIONS[:count])
    result = export_case(case, codes=codes, draft=count == 0)
    read = read_pdf(result.pdf, 'official.pdf')
    assert read.form_version == result.field_map
    rows = [field for name, field in read.fields.items() if name.startswith('Article(s)')]
    assert len(rows) == max(1, count)
    assert [f.value for f in sorted(rows, key=lambda f: int(f.name.removeprefix('Article(s)') or 0))
            if f.status == 'present'] == PROVISIONS[:count]
    assert 'Supporting Doc' in read.fields
    assert read.fields['Owner'].status == 'present'
    assert read.text_pages and read.text_pages[0].page == result.form_pages
    # Labelled administrative records may state the professional basis; the form and appendix do not.
    assert not any('Part 4' in p.text or 'Professional Design' in p.text for p in read.text_pages
                   if not p.text.lstrip().startswith(CONTEXT))
    parts = review_uploads([('official.pdf', result.pdf)], codes)
    assert len(parts.section_c) == count
    assert any(f.field == 'Supporting Doc' and f.section == 'D' for f in parts.fields)


@pytest.mark.parametrize('count', [1, 2, 5, 6, 12, 24])
def test_untouched_dynamic_blank_vector_pages_are_verified_before_blank_fields(count):
    fmap = load_field_map()
    data, _ = prepare_form(load_form(None, fmap), fmap, count)
    read = read_pdf(data, 'native-blank.pdf')
    assert read.form_version == 'challenge_2026-09-15'
    assert len([n for n in read.fields if n.startswith('Article(s)')]) == count
    assert {f.status for f in read.fields.values()} == {'blank'}


@pytest.mark.parametrize('count', [1, 2, 5, 6, 12, 24])
@pytest.mark.parametrize('flatten', [False, True], ids=['editable', 'flattened'])
def test_new_form_geometry_identifies_editable_and_flattened_runtime_rows(count, flatten):
    read = read_pdf(editable(count, flatten=flatten), 'form.pdf')
    assert read.form_version == 'challenge_2026-09-15'
    assert read.role == ('scc_form_flattened' if flatten else 'scc_form_fillable')
    assert read.fields['Owner'].value == 'SYNTHETIC actual owner'
    assert read.fields['Supporting Doc'].value == 'SYNTHETIC attachment - SYNTHETIC author'
    assert len([name for name in read.fields if name.startswith('Article(s)')]) == count


@pytest.mark.parametrize('flatten', [False, True])
def test_legacy_identity_and_fixed_five_rows_survive_default_version_change(flatten):
    read = read_pdf(editable(1, version='scc_2026-10', flatten=flatten), 'legacy.pdf')
    assert read.form_version == 'scc_2026-10'
    assert len([name for name in read.fields if name.startswith('Article(s)')]) == 5
    assert read.fields['Supporting Doc'].value == 'SYNTHETIC attachment - SYNTHETIC author'


def changed(pdf, *, metadata=None, drop=(), move_page=False, move_widget=False):
    writer = PdfWriter(clone_from=io.BytesIO(pdf))
    remaining = dict(writer.metadata or {})
    for key in drop:
        remaining.pop(key, None)
    writer.metadata = remaining
    if metadata:
        writer.add_metadata(metadata)
    if move_page:
        from pypdf import Transformation
        writer.pages[1].add_transformation(Transformation().translate(0, -62))
    if move_widget:
        widget = next(a.get_object() for a in writer.pages[0]['/Annots'] if a.get_object().get('/T') == 'Owner')
        x0, y0, x1, y1 = widget['/Rect']
        widget[NameObject('/Rect')] = RectangleObject((x0, y0 - 20, x1, y1 - 20))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.mark.parametrize('flatten', [False, True])
@pytest.mark.parametrize('options', [
    {'drop': ['/BatatisFormVersion']}, {'drop': ['/BatatisAttributionRows']},
    {'drop': ['/BatatisFormPages']}, {'drop': ['/BatatisSourceSHA256']}, {'drop': ['/BatatisSourcePages']},
    {'metadata': {'/BatatisFormVersion': 'unknown'}}, {'metadata': {'/BatatisAttributionRows': '0'}},
    {'metadata': {'/BatatisAttributionRows': '-1'}}, {'metadata': {'/BatatisAttributionRows': '257'}},
    {'metadata': {'/BatatisAttributionRows': '10000000000'}}, {'metadata': {'/BatatisAttributionRows': '2'}},
    {'metadata': {'/BatatisFormPages': '8'}}, {'metadata': {'/BatatisSourceSHA256': '0' * 64}},
    {'metadata': {'/BatatisSourcePages': '4-10'}}, {'move_page': True},
    {'drop': ['/BatatisFormVersion', '/BatatisAttributionRows', '/BatatisFormPages',
              '/BatatisSourceSHA256', '/BatatisSourcePages']},
])
def test_untrusted_hints_and_actual_layout_conflicts_cannot_establish_any_value(flatten, options):
    data = changed(editable(1, flatten=flatten), **options)
    read = read_pdf(data, 'conflict.pdf')
    assert read.form_version is None
    assert read.fields and {v.status for v in read.fields.values()} == {'not_found'}
    assert not any(v.value for v in read.fields.values())
    assert not read.text_pages, 'unverified boundaries must not expose printed Part 4 as applicant evidence'
    parts = review_uploads([('conflict.pdf', data)], None)
    owner = next(f for f in parts.fields if f.field == 'Owner')
    assert owner.pointer.file == 'conflict.pdf' and owner.pointer.page is None and owner.pointer.bbox is None


def test_metadata_does_not_attest_widget_geometry():
    read = read_pdf(changed(editable(1), move_widget=True), 'moved.pdf')
    assert read.form_version is None and read.fields['Owner'].status == 'not_found'


def test_scanned_dynamic_page_cannot_attest_a_tampered_row_hint():
    from engine.tests.package_review_fixtures import scanned
    actual = editable(5, flatten=True)
    scan = PdfReader(io.BytesIO(scanned(actual)))
    writer = PdfWriter(clone_from=io.BytesIO(actual))
    writer.insert_page(scan.pages[1], 1)
    writer.remove_page(2)
    writer.add_metadata({'/BatatisAttributionRows': '1'})
    buf = io.BytesIO()
    writer.write(buf)
    read = read_pdf(buf.getvalue(), 'unverifiable-row-count.pdf')
    assert read.form_version is None
    assert read.fields and {f.status for f in read.fields.values()} == {'not_found'}


@pytest.mark.parametrize('version', ['scc_2026-10', 'challenge_2026-09-15'])
def test_each_version_refuses_its_own_source_hash_mismatch(monkeypatch, tmp_path, version, request):
    if version == 'scc_2026-10':
        request.getfixturevalue('legacy_form')
    bad = tmp_path / 'source.pdf'
    bad.write_bytes(load_form(None, load_field_map(version)) + b'\n% altered\n')
    data = editable(1, version=version, flatten=True)
    if version == 'scc_2026-10':
        monkeypatch.setenv('BATATIS_SCC_FORM', str(bad))
    else:
        # Option B: the environment override is deliberately legacy-only.
        from engine.export import scc
        original = scc.form_path
        target_version = version
        def source_path(version=scc.CURRENT_MAP):
            return bad if version == target_version else original(version)
        monkeypatch.setattr(scc, 'form_path', source_path)
    read = read_pdf(data, 'source-unavailable.pdf')
    assert read.form_version is None
    assert {v.status for v in read.fields.values()} == {'not_found'}


def test_legacy_selected_row_metadata_keeps_fixed_five_rows_and_overflow(legacy_form):
    codes = Codes()
    result = export_case(sample_case(codes, provisions=PROVISIONS), codes=codes, version='scc_2026-10')
    read = read_pdf(result.pdf, 'legacy-overflow.pdf')
    assert read.form_version == 'scc_2026-10'
    assert len([name for name in read.fields if name.startswith('Article(s)')]) == 5
    assert read.fields['Article(s)4'].value == 'Rows 5-24'
    assert read.text_pages[0].page == 5


def test_combined_supporting_listing_retains_its_exact_field_and_source():
    data = editable(1, flatten=True)
    parts = review_uploads([('listing.pdf', data)], None)
    row = next(d for d in parts.documents if d.listed_in_section_d)
    assert row.title.value == 'SYNTHETIC attachment - SYNTHETIC author'
    assert row.title.source.file == 'listing.pdf' and row.title.source.page == 2
    assert row.title.source.form_field == 'Supporting Doc'
    assert not row.responsible.known, 'a free-text hyphen is not a verified title/person delimiter'
    assert not any(f.field == 'professional_name' and f.status == 'present' for f in parts.fields)
