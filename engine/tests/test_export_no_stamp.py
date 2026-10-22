"""The public legacy exporter preserves draft semantics without Batatis overlays."""
import io

from fastapi.testclient import TestClient
from pypdf import PdfReader
from pypdf.generic import ContentStream

from engine.api import create_app
from engine.codes import Codes
from engine.export import export_case
from engine.export.sample import sample_case
from engine.models import Fact, Source
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import store_with_synthetic_files


def batatis_stamp_text(reader, page):
    """Recognize only the two added red overlays, not legitimate source wording."""
    color, size, stack, found = None, None, [], []
    for operands, operator in ContentStream(page.get_contents(), reader).operations:
        if operator == b'q':
            stack.append((color, size))
        elif operator == b'Q' and stack:
            color, size = stack.pop()
        elif operator == b'rg':
            color = tuple(round(float(value), 5) for value in operands)
        elif operator == b'Tf':
            size = float(operands[1])
        elif operator == b'Tj':
            text = str(operands[0])
            if ((text == 'DRAFT' and size == 120 and color == (0.8, 0.1, 0.1))
                    or (text == 'DRAFT - not for submission; see appendix for review status'
                        and size == 8 and color == (0.7, 0.1, 0.1))):
                found.append(text)
    return found


def test_draft_export_has_no_added_red_stamp_and_retains_metadata_projection_and_gates(tmp_path):
    codes = Codes()
    store = CaseStore(tmp_path / 'no-stamp.sqlite')
    case = sample_case(codes, provisions=['9.25.2.2.(1)'])
    case.facts += [
        Fact(field='owner_name', value='SYNTHETIC DRAFT Source Owner', kind='pointed', status='confirmed',
             source=Source(type='user_text', ref='synthetic-confirmed')),
        Fact(field='storeys', value='SYNTHETIC UNCONFIRMED VALUE', kind='proposed', confidence=0.2,
             source=Source(type='user_text', ref='synthetic-proposal')),
    ]
    store_with_synthetic_files(store, case)
    before = store.get(case.id).model_dump()
    with TestClient(create_app(store=store, codes=codes), base_url='http://localhost') as client:
        blocked = client.post(f'/cases/{case.id}/export')
        assert blocked.status_code == 409 and any('storeys' in item for item in blocked.json()['detail']['reasons'])
        response = client.post(f'/cases/{case.id}/export', json={'draft': True})
    assert response.status_code == 200 and response.headers['content-type'] == 'application/pdf'
    assert '-DRAFT.pdf' in response.headers['content-disposition']
    pdf = PdfReader(io.BytesIO(response.content))
    assert pdf.metadata.title.endswith(' (DRAFT)')
    text = ' '.join(page.extract_text() for page in pdf.pages)
    assert 'SYNTHETIC DRAFT Source Owner' in text  # legitimate applicant wording is retained
    assert 'SYNTHETIC UNCONFIRMED VALUE' not in text
    assert len(pdf.pages) > 5  # current official form AND generated appendix
    assert all(not batatis_stamp_text(pdf, page) for page in pdf.pages)
    assert '/AcroForm' not in pdf.trailer['/Root'] and not pdf.get_fields()
    result = export_case(case, draft=True, codes=codes)
    assert result.draft is True and result.open_items
    assert store.get(case.id).model_dump() == before
