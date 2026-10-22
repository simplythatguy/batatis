"""Dropped PDFs (WP-21, AC1.6): text-layer facts carry page and box, form values are exact,
a filled SCC form can be read, and a scan says "not read". All PDFs here are synthetic."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from engine.api import create_app
from engine.export.scc import form_path
from engine.intake import service
from engine.intake.extract import read_file
from engine.intake.pdf import ENCRYPTED, FLATTENED_SCC, NO_TEXT, NOT_A_PDF
from engine.store import CaseStore


def pdf(pages: list[list[tuple[float, float, str]]], *, fields: list[tuple[str, str, tuple]] = (),
        shapes_only: set[int] = frozenset()) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for index, lines in enumerate(pages):
        if index in shapes_only:
            c.rect(72, 300, 400, 300, fill=1)            # a "scan": marks on the page, no text layer
            c.line(72, 200, 500, 250)
        for x, y, text in lines:
            c.drawString(x, y, text)
        if index == 0:
            for name, value, (x, y, w, h) in fields:
                c.acroForm.textfield(name=name, value=value, x=x, y=y, width=w, height=h)
        c.showPage()
    c.save()
    return buf.getvalue()


def test_text_layer_facts_carry_page_and_box():
    data = pdf([[(72, 700, 'Project brief')],
                [(72, 700, 'We are building a two-storey house with a building area of 150 m2.'),
                 (72, 680, 'It is not sprinklered.')]])
    out = read_file('file_a', 'brief.pdf', data)
    report = out.files[0]
    assert report.status == 'read' and report.pages == 2 and report.pages_read == [1, 2]
    area = next(f for f in out.facts if f.field == 'building_area_m2')
    assert area.value == 150 and area.kind == 'pointed'
    assert area.source.type == 'file' and area.source.ref == 'file_a' and area.source.page == 2
    left, bottom, right, top = area.source.bbox
    assert 72 < left < right < 612 and 695 <= bottom < top <= 712           # the words on line one of page 2
    sprinkler = next(f for f in out.facts if f.field == 'sprinklered')
    assert sprinkler.value == 'no' and 675 <= sprinkler.source.bbox[1] < 690
    assert all(f.status == 'unconfirmed' for f in out.facts)


def test_a_scan_is_not_read_and_says_so():
    out = read_file('file_s', 'scan.pdf', pdf([[], []], shapes_only={0, 1}))
    report = out.files[0]
    assert report.status == 'not_read' and report.reason == NO_TEXT and report.pages_not_read == [1, 2]
    assert out.facts == []


def test_mixed_text_and_scan_is_partly_read():
    out = read_file('file_m', 'mixed.pdf', pdf([[(72, 700, 'A four-storey office building.')], []], shapes_only={1}))
    report = out.files[0]
    assert (report.status, report.pages_read, report.pages_not_read) == ('partly_read', [1], [2])
    assert report.reason == NO_TEXT
    assert {f.field for f in out.facts} >= {'storeys', 'occupancy'}


def test_generic_fillable_form_values_are_exact_with_the_widget_box():
    data = pdf([[(72, 740, 'Application')]], fields=[('Owner Name', 'Jane Example', (100, 600, 300, 20)),
                                                    ('Mailing_Address', '12 Elm Street NW, Red Deer AB', (100, 560, 300, 20)),
                                                    ('Colour of door', 'blue', (100, 520, 300, 20))])
    out = read_file('file_f', 'form.pdf', data)
    exact = {f.field: f for f in out.facts if f.kind == 'exact'}
    assert exact['owner_name'].value == 'Jane Example' and exact['owner_name'].source.page == 1
    assert exact['owner_name'].source.bbox == (100.0, 600.0, 400.0, 620.0)
    assert exact['mailing_address'].value == '12 Elm Street NW, Red Deer AB'
    report = out.files[0]
    assert report.form == 'acroform' and report.form_fields_read == 2 and 'Colour of door' in report.form_fields_skipped


SCC_FIELDS = [('Owner', 'Jane Example', (113, 481, 458, 15)), ('Owner Rep', 'Sam Agent', (154, 462, 417, 15)),
              ('Mailing Address', 'PO Box 1, Lacombe AB', (119, 429, 452, 30)),
              ('Date of Reqeuest', '2026-10-21', (119, 411, 452, 15)), ('Permit', 'BP-2026-0042', (173, 353, 399, 15)),
              ('Municipal Address', '42 Example Street', (127, 301, 445, 30)), ('Lot', '4', (166, 283, 169, 15)),
              ('Block', '2', (372, 283, 199, 15)), ('Plan', '1234AB', (169, 264, 166, 15)),
              ('Article(s)', '9.10.15.4.(1)', (39, 116, 100, 16)), ('Article(s)1', '9.99.99.9.', (39, 90, 100, 16)),
              ('SCO', 'An officer name', (39, 548, 265, 21)), ('Objective', 'OS1.2', (143, 116, 93, 16))]


def test_a_filled_scc_form_is_read_and_officer_fields_are_not():
    from engine.codes import Codes
    out = read_file('file_scc', 'scc.pdf', pdf([[(72, 740, 'Variance form')]], fields=SCC_FIELDS), codes=Codes())
    report = out.files[0]
    assert report.form == 'scc_variance' and report.status == 'read'
    values = {f.field: f.value for f in out.facts}
    assert values['owner_name'] == 'Jane Example' and values['request_date'] == '2026-10-21'
    assert values['permit_number'] == 'BP-2026-0042' and (values['lot'], values['block'], values['plan']) == ('4', '2', '1234AB')
    assert values['claimed_provision'] == '9.10.15.4.(1)'
    assert [u.entered for u in out.unresolved] == ['9.99.99.9.']
    assert {'SCO', 'Objective'} <= set(report.form_fields_skipped)
    assert all(f.kind == 'exact' for f in out.facts)
    assert 'An officer name' not in values.values() and 'OS1.2' not in values.values()


def test_the_real_scc_form_filled_with_pypdf_is_read():
    path = form_path()
    if not path.is_file():
        pytest.skip('SCC variance form not present (CI fetches it into codedb/build)')
    writer = PdfWriter(clone_from=PdfReader(str(path)))
    writer.update_page_form_field_values(writer.pages[0], {'Owner': 'Jane Example', 'Municipal Address': '42 Example Street',
                                                           'Date of Reqeuest': '2026-10-21'}, auto_regenerate=False)
    buf = io.BytesIO()
    writer.write(buf)
    out = read_file('file_real', 'scc.pdf', buf.getvalue())
    values = {f.field: (f.value, f.source.page) for f in out.facts}
    assert values['owner_name'] == ('Jane Example', 1) and values['municipal_address'] == ('42 Example Street', 1)
    assert 'Edmonton' not in str(values)                    # the Council's printed address is not a fact


def test_a_flattened_scc_form_is_not_read():
    data = pdf([[(72, 740, 'Variance Form for Proposed Alternative Solution'), (72, 720, 'Safety Codes Council'),
                 (72, 700, '500, 1405 Jasper Avenue NW')]])
    out = read_file('file_flat', 'flat.pdf', data)
    assert out.files[0].status == 'not_read' and out.files[0].reason == FLATTENED_SCC and out.facts == []


def test_encrypted_and_broken_pdfs_are_not_read():
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf([[(72, 700, 'A two-storey house.')]]))))
    writer.encrypt('secret')
    buf = io.BytesIO()
    writer.write(buf)
    assert read_file('e', 'e.pdf', buf.getvalue()).files[0].reason == ENCRYPTED
    assert read_file('b', 'b.pdf', b'%PDF-1.7 not really').files[0].reason == NOT_A_PDF
    assert read_file('n', 'n.pdf', b'hello').files[0].reason == NOT_A_PDF


def test_upload_then_intake_reads_the_file(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    http = TestClient(create_app(store))
    case_id = http.post('/cases', json={}).json()['id']
    data = pdf([[(72, 700, 'Owner: Jane Example'), (72, 680, 'A single-storey bungalow, 140 m2, unsprinklered.')]])
    upload = http.post(f'/cases/{case_id}/files', content=data,
                       headers={'content-type': 'application/pdf', 'x-filename': 'brief.pdf'}).json()
    scan = http.post(f'/cases/{case_id}/files', content=pdf([[]], shapes_only={0}),
                     headers={'content-type': 'application/pdf', 'x-filename': 'scan.pdf'}).json()
    body = http.post(f'/cases/{case_id}/intake', json={'file_ids': [upload['id'], scan['id']]}).json()
    reports = {r['name']: r for r in body['record']['files']}
    assert reports['brief.pdf']['status'] == 'read' and reports['scan.pdf']['status'] == 'not_read'
    owner = next(f for f in body['facts'] if f['field'] == 'owner_name')
    assert owner['source']['type'] == 'file' and owner['source']['ref'] == upload['id'] and owner['source']['page'] == 1
    assert len(owner['source']['bbox']) == 4
    assert {f['field'] for f in body['facts']} >= {'storeys', 'building_area_m2', 'sprinklered', 'occupancy'}


def test_files_and_description_merge_without_losing_pointers():
    data = pdf([[(72, 700, 'The building is not sprinklered.')]])
    out = service.run('A two-storey house.', [('f1', 'a.pdf', data)])
    assert {(p.field, p.source_ref) for p in out.pointers} >= {('storeys', 'description'), ('sprinklered', 'f1')}


def test_a_form_without_a_text_layer_reports_its_fields_as_read():
    from engine.intake.pdf import FORM_ONLY
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.acroForm.textfield(name='Owner Name', value='Jane Example', x=100, y=600, width=300, height=20)
    c.showPage()
    c.save()
    out = read_file('file_fo', 'form-only.pdf', buf.getvalue())
    report = out.files[0]
    assert report.form_fields_read == 1 and [f.value for f in out.facts] == ['Jane Example']
    assert report.status in ('read', 'partly_read') and report.reason in (None, FORM_ONLY)
    assert report.reason != NO_TEXT


def test_a_name_read_from_a_file_is_scrubbed_from_the_description_sent_to_the_model():
    seen = []

    def transport(system, user, schema):
        import json
        seen.append(json.loads(user)['text'])
        return {'facts': []}, {}
    form = pdf([[(72, 740, 'Application')]], fields=[('Owner Name', 'Jane Example', (100, 600, 300, 20))])
    service.run('Jane Example wants a single exit for the new office.', [('f', 'form.pdf', form)],
                transport=transport, status='fake')
    assert seen and all('Jane Example' not in text for text in seen)


def test_pushbuttons_are_not_values_and_radio_children_use_their_own_state():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 740, 'Form')
    c.acroForm.radio(name='Kind', value='site', selected=True, x=100, y=600, buttonStyle='circle')
    c.acroForm.radio(name='Kind', value='wide', selected=False, x=140, y=600, buttonStyle='circle')
    c.acroForm.checkbox(name='Agree', checked=True, x=100, y=560)
    c.showPage()
    c.save()
    from engine.intake.pdf import read_pdf
    widgets = read_pdf(buf.getvalue()).widgets
    radios = [w.value for w in widgets if w.name == 'Kind']
    assert radios.count(True) == 1
    assert [w.value for w in widgets if w.name == 'Agree'] == [True]


def test_each_pdf_is_parsed_once_across_the_rules_and_model_passes(monkeypatch):
    """With a model the files run twice (rules first, then the model); the PDF itself is read once."""
    from engine.intake import extract
    calls = []
    real = extract.read_pdf
    monkeypatch.setattr(extract, 'read_pdf', lambda data: calls.append(len(data)) or real(data))
    data = pdf([[(72, 700, 'We are building a two-storey house with a building area of 150 m2.')]])
    out = service.run('A house.', [('f1', 'brief.pdf', data), ('f2', 'notes.pdf', b'not a pdf')],
                      transport=lambda system, user, schema: ({'facts': []}, {}), status='fake')
    assert calls == [len(data), 9]                            # one read per file, not one per pass (two passes ran)
    assert [r.status for r in out.files] == ['read', 'not_read']
