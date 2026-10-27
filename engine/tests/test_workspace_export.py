import base64
import io

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, RectangleObject
from reportlab.pdfgen import canvas

from engine.codes import Codes
from engine.api import create_app
from engine.export import export_case
from engine.export.demo_cases import CASES, demo_case
from engine.export.sample import sample_case
from engine.export.signatures import live_fields
from engine.models import Case, EvidenceItem, Source
from engine.models_workspace import WorkspaceConsent, WorkspaceSignature
from engine.review.pdf_reader import read_pdf
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_accounts import signup, onboard
from engine.tests.test_workspace import signature_image
from engine.workspace import content_hash


def signed(case, role='owner'):
    case.workspace.signatures.append(WorkspaceSignature(role=role, name='Ada Synthetic Owner', method='drawn',
        image=signature_image(), signed_on='2026-10-26', content_hash=content_hash(case)))
    return case


def attachment_pdf():
    buf = io.BytesIO()
    draw = canvas.Canvas(buf)
    for n in (1, 2):
        draw.drawString(60, 700, f'SYNTHETIC attached document page {n}')
        draw.showPage()
    draw.save()
    return buf.getvalue()


class _Files:
    """An in-memory stand-in for the case store's saved attachment bytes."""
    def __init__(self, case_id, pdf):
        self.case_id, self.pdf = case_id, pdf

    def get_file(self, case_id, ref):
        return {'name': 'report.pdf', 'data': self.pdf} if (case_id, ref) == (self.case_id, 'file_test') else None


def attach(case, pdf, name='Synthetic supporting report'):
    source = Source(type='file', ref='file_test', quote='Synthetic attachment')
    case.evidence.append(EvidenceItem(id='test', description=name, status='evidence_listed'))
    case.facts += [fact('evidence.test.file_ref', source.ref, source=source), fact('evidence.test.title', name)]
    return _Files(case.id, pdf)


def test_unsigned_fields_are_live_and_canonical_appearances_are_preserved():
    case = Case()
    result = export_case(case, draft=True)
    reader = PdfReader(io.BytesIO(result.pdf))
    fields = reader.get_fields()
    assert set(fields) == live_fields(case)
    widgets = {str(a.get_object()['/T']): a.get_object() for page in reader.pages for a in page.get('/Annots', [])
               if a.get_object().get('/Subtype') == '/Widget'}
    assert set(widgets) == set(fields)
    canonical = {ref.idnum for ref in reader.trailer['/Root']['/AcroForm']['/Fields']}
    assert canonical == {widget.indirect_reference.idnum for widget in widgets.values()}
    for widget in widgets.values():
        assert widget['/AP']['/N'] is not None
    assert widgets['Check Box14']['/AS'] == '/Off'
    assert '/Off' in widgets['Check Box14']['/AP']['/N']
    # Another tool can still fill the retained date and consent fields.
    writer = PdfWriter(clone_from=io.BytesIO(result.pdf))
    writer.update_page_form_field_values(None, {'Date1': '2026-10-27', 'Check Box14': '/Yes'}, auto_regenerate=False)
    buf = io.BytesIO(); writer.write(buf)
    assert PdfReader(buf).get_fields()['Date1']['/V'] == '2026-10-27'


def test_current_signature_image_date_printed_name_and_consent_are_drawn():
    case = signed(Case(facts=[fact('owner_name', 'Ada Synthetic Owner')]))
    case.workspace.consent = WorkspaceConsent(agreed=True, at='2026-10-26T12:00:00Z')
    result = export_case(case, draft=True)
    reader = PdfReader(io.BytesIO(result.pdf))
    assert set(reader.get_fields()) == live_fields(case)
    assert 'Signature1' not in reader.get_fields() and 'Date1' not in reader.get_fields()
    assert 'Check Box14' not in reader.get_fields()
    page = reader.pages[1]
    assert 'Ada Synthetic Owner' in page.extract_text() and '2026-10-26' in page.extract_text()
    assert page.images
    assert {'Signature2', 'Date2', 'Signature3', 'Signature4', 'SCO Date', 'SCO Date1'} <= set(reader.get_fields())
    case.facts.append(fact('alternative_description', 'A later edit'))
    stale = PdfReader(io.BytesIO(export_case(case, draft=True).pdf))
    assert 'Signature1' in stale.get_fields() and 'Date1' in stale.get_fields()
    assert '2026-10-26' not in stale.pages[1].extract_text()
    assert not stale.pages[1].images


def test_draft_marks_all_pages_and_attachments_follow_appendix_with_bookmarks():
    case = Case(facts=[fact('process.rationale', 'Synthetic applicant rationale.')])
    loader = attach(case, attachment_pdf())
    result = export_case(case, draft=True, store=loader)
    reader = PdfReader(io.BytesIO(result.pdf))
    assert result.appendix_pages > 0 and len(reader.pages) == result.page_count
    assert 'SYNTHETIC attached document page 1' in reader.pages[-2].extract_text()
    assert 'SYNTHETIC attached document page 2' in reader.pages[-1].extract_text()
    assert all('Draft · not for submission' in page.extract_text() for page in reader.pages)
    assert [item.title for item in reader.outline] == ['Form Part 1', 'Appendix', 'Synthetic supporting report']
    assert [reader.get_destination_page_number(item) for item in reader.outline] == [
        0, result.form_pages, len(reader.pages) - 2]


def test_official_pdf_has_no_draft_mark():
    result = export_case(sample_case(Codes(), provisions=['9.25.2.2.(1)']))
    assert all('Draft · not for submission' not in page.extract_text()
               for page in PdfReader(io.BytesIO(result.pdf)).pages)


def test_export_route_appends_case_owned_saved_bytes(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    saved = store.put_file(case.id, 'report.pdf', attachment_pdf())
    source = Source(type='file', ref=saved['id'], quote='Synthetic saved attachment')
    case.facts += [fact('evidence.report.file_ref', saved['id'], source=source),
                   fact('evidence.report.title', 'Stored report')]
    store.put(case)
    with TestClient(create_app(store=store)) as client:
        result = client.post(f'/cases/{case.id}/export', json={'draft': True})
    assert result.status_code == 200, result.text
    reader = PdfReader(io.BytesIO(result.content))
    assert 'SYNTHETIC attached document page 2' in reader.pages[-1].extract_text()
    assert reader.outline[-1].title == 'Stored report'


def test_demo_export_with_live_fields_and_attachment_is_read_through_upload_route(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret"}')
    case = demo_case(CASES[0])
    # The demo's source files are text fixtures; this actual synthetic PDF is
    # the attachment under test and is resolved in memory by its saved reference.
    case.facts = [entry for entry in case.facts if not entry.field.endswith('.file_ref')]
    loader = attach(case, attachment_pdf())
    signed(case)
    result = export_case(case, draft=True, store=loader)
    with TestClient(create_app(store=CaseStore(tmp_path / 'review.sqlite')), base_url='http://localhost') as client:
        signup(client, 'reader@example.test'); onboard(client, 'reviewer')
        response = client.post('/package-review', files=[('files', ('own-export.pdf', result.pdf, 'application/pdf'))])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['files'][0]['form_version'] == result.field_map, body['files']
    owner = next(item for item in body['fields'] if item['field'] == 'Owner')
    assert owner['status'] == 'present' and 'Birchfield' in owner['value']
    assert any('SYNTHETIC attached document' in item.text for item in read_pdf(result.pdf, 'export.pdf').text_pages)


def test_live_signature_widget_geometry_is_still_verified():
    data = export_case(Case(), draft=True).pdf
    writer = PdfWriter(clone_from=io.BytesIO(data))
    widget = next(a.get_object() for page in writer.pages for a in page.get('/Annots', [])
                  if a.get_object().get('/T') == 'Signature1')
    x0, y0, x1, y1 = widget['/Rect']
    widget[NameObject('/Rect')] = RectangleObject((x0, y0 + 10, x1, y1 + 10))
    buf = io.BytesIO(); writer.write(buf)
    read = read_pdf(buf.getvalue(), 'moved.pdf')
    assert read.form_version is None
    assert all(value.status == 'not_found' for value in read.fields.values())


def test_attachment_field_name_cannot_mask_the_same_name_on_the_form():
    output = io.BytesIO()
    draw = canvas.Canvas(output)
    draw.drawString(48, 720, 'SYNTHETIC attachment with its own form field')
    draw.acroForm.textfield(name='Signature1', x=48, y=650, width=200, height=24,
                           value='SYNTHETIC attachment value')
    draw.showPage(); draw.save()
    case = Case()
    result = export_case(case, draft=True, store=attach(case, output.getvalue()))
    read = read_pdf(result.pdf, 'package.pdf')
    assert read.form_version == result.field_map
    assert read.fields['Owner'].status == 'blank'


def test_an_owner_password_attachment_is_kept_and_a_locked_one_is_named():
    from engine.export.scc import ExportBlocked
    sealed = PdfWriter(clone_from=PdfReader(io.BytesIO(attachment_pdf())))
    sealed.encrypt(user_password='', owner_password='owner-only')
    buf = io.BytesIO(); sealed.write(buf)
    case = Case(facts=[fact('process.rationale', 'Synthetic applicant rationale.')])
    result = export_case(case, draft=True, store=attach(case, buf.getvalue()))
    reader = PdfReader(io.BytesIO(result.pdf))
    assert 'SYNTHETIC attached document page 2' in reader.pages[-1].extract_text()
    assert not any('Synthetic supporting report' in item for item in result.open_items)
    locked = PdfWriter(clone_from=PdfReader(io.BytesIO(attachment_pdf())))
    locked.encrypt('needs-a-password')
    buf = io.BytesIO(); locked.write(buf)
    case = Case(facts=[fact('process.rationale', 'Synthetic applicant rationale.')])
    draft = export_case(case, draft=True, store=attach(case, buf.getvalue()))
    named = [item for item in draft.open_items if 'Synthetic supporting report' in item]
    assert named and 'without a password' in named[0]
    with pytest.raises(ExportBlocked) as blocked:
        export_case(case, store=attach(case, buf.getvalue()))
    assert any('Synthetic supporting report' in reason for reason in blocked.value.reasons)


def test_intake_does_not_read_a_batatis_export_as_applicant_words():
    from engine.intake.extract import read_file
    from engine.intake.pdf import BATATIS_EXPORT
    exported = export_case(demo_case(CASES[0], Codes()), draft=True).pdf
    out = read_file('file_export', 'export.pdf', exported)
    assert out.files[0].status == 'not_read' and out.files[0].reason == BATATIS_EXPORT and out.facts == []


def test_signatures_go_stale_when_the_benchmark_departure_changes_but_not_for_an_ai_proposal():
    case = demo_case(CASES[0], Codes())
    before = content_hash(case)
    case.facts.append(fact('process.rationale', 'An AI draft.', kind='proposed', status='unconfirmed'))
    assert content_hash(case) == before, 'an unaccepted proposal is not part of the signed application'
    case.identify.benchmark.departure = 'A different departure the signer never saw.'
    assert content_hash(case) != before

