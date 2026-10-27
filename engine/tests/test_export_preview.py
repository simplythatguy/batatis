"""GET /cases/{id}/export/preview: the draft export's own bytes and page images, under the export's access policy."""
import base64
import io
import sqlite3

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from engine.api import create_app
from engine.codes import Codes
from engine.export import export_case, form_path
from engine.export.preview import ENTRY_BYTES, PAYLOAD_BUDGET, RESPONSE_CAP, SCALE, encoded, fits, page_images
from engine.export.sample import sample_case
from engine.models import Fact, Source
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import store_with_synthetic_files

pytestmark = pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')


def decoded(url: str, kind: str) -> bytes:
    prefix = f'data:{kind};base64,'
    assert url.startswith(prefix)
    return base64.b64decode(url[len(prefix):], validate=True)


def test_preview_is_the_draft_pdf_and_an_image_of_each_page(tmp_path):
    codes = Codes()
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = sample_case(codes)
    marker = 'UNCONFIRMED PREVIEW VALUE'
    case.facts.append(Fact(field='owner_name', value=marker, kind='pointed', status='unconfirmed',
                           source=Source(type='user_text', ref='test unconfirmed edit')))
    case = store_with_synthetic_files(store, case)
    with TestClient(create_app(store=store, codes=codes)) as client:
        response = client.get(f'/cases/{case.id}/export/preview')
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert len(response.content) < RESPONSE_CAP
    body = response.json()
    assert body['kind'] == 'pages' and body['filename'] == f'{case.id}-scc-variance-DRAFT.pdf'
    reader = PdfReader(io.BytesIO(decoded(body['pdf'], 'application/pdf')))
    assert reader.metadata['/Title'].endswith('(DRAFT)')
    assert set(reader.get_fields()) == {'Signature1', 'Signature2', 'Signature3', 'Signature4',
                                        'Date1', 'Date2', 'SCO Date', 'SCO Date1', 'Check Box14'}
    assert marker not in ' '.join(page.extract_text() for page in reader.pages)     # confirmed values only
    # A long package, attachments included. Images run in page order until the encoded budget (how many fit
    # depends on the platform's rendering); the rest are fetched as windows, and the PDF is whole.
    package = export_case(case, codes=codes, store=store, draft=True)
    assert body['page_count'] == len(reader.pages) == package.page_count > 20
    assert package.form_pages <= len(body['pages']) <= body['page_count']
    for page, preview in zip(reader.pages, body['pages']):
        assert (preview['width'], preview['height']) == pytest.approx(
            (float(page.mediabox.width), float(page.mediabox.height)), abs=0.001)
        image = Image.open(io.BytesIO(decoded(preview['image'], 'image/png')))
        assert image.format == 'PNG' and image.size == (round(preview['width'] * SCALE), round(preview['height'] * SCALE))


def entry(size: int) -> int:
    return encoded(size) + ENTRY_BYTES


def test_page_images_keep_page_order_and_stop_at_the_encoded_budget():
    codes = Codes()
    pdf = export_case(sample_case(codes), codes=codes, draft=True).pdf
    every, count = page_images(pdf, budget=10 ** 9)
    assert len(every) == count
    fitted, total = page_images(pdf)
    assert total == count and [p.png for p in fitted] == [p.png for p in every[:len(fitted)]]
    assert entry(len(pdf)) + sum(entry(len(p.png)) for p in fitted) <= PAYLOAD_BUDGET
    three = entry(len(pdf)) + sum(entry(len(p.png)) for p in every[:3])
    for budget, shown in ((three, 3), (three - 1, 2), (entry(len(pdf)), 0)):
        first, total = page_images(pdf, budget=budget)
        assert total == count and [p.png for p in first] == [p.png for p in every[:shown]]


def test_whether_a_pdf_fits_is_its_base64_size_decided_before_encoding():
    largest = (PAYLOAD_BUDGET - ENTRY_BYTES) // 4 * 3      # base64 of this many bytes exactly fills the room
    assert encoded(largest) + ENTRY_BYTES <= PAYLOAD_BUDGET < encoded(largest + 1) + ENTRY_BYTES
    assert fits(largest) and not fits(largest + 1)
    assert len(base64.b64encode(bytes(largest))) == encoded(largest)


def test_a_saved_application_whose_pdf_alone_is_over_the_budget_gets_no_embedded_preview(tmp_path):
    """Public save path and default budget: the 500 longest Division B sentences (the review's size case),
    as a size boundary only."""
    codes = Codes()
    with sqlite3.connect(f'file:{codes.db_path}?mode=ro', uri=True) as con:
        ids = [row[0] for row in con.execute("SELECT id FROM provisions WHERE division='B' AND level='sentence' "
                                             'ORDER BY length(text) DESC, id LIMIT 500')]
    with TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=codes)) as client:
        case = client.post('/cases', json={'title': 'SYNTHETIC response-size boundary'}).json()
        saved = client.post(f'/cases/{case["id"]}/section-d', json={'provisions': ids,
                                                                   'expected_version': case['version']})
        assert saved.status_code == 200, saved.text[:300]
        response = client.get(f'/cases/{case["id"]}/export/preview')
        assert response.status_code == 200
        body = response.json()
        assert body['kind'] == 'too_large', 'this fixture no longer makes a PDF over the preview budget'
        assert len(response.content) < 2_000 and not fits(body['pdf_bytes']) and body['page_count'] > 500
        assert 'pdf' not in body and 'pages' not in body
        # The fallback, the draft download, still sends the whole PDF that was measured.
        draft = client.post(f'/cases/{case["id"]}/export', json={'draft': True})
        assert draft.status_code == 200 and draft.headers['content-type'] == 'application/pdf'
        assert len(draft.content) == body['pdf_bytes'] and len(PdfReader(io.BytesIO(draft.content)).pages) == body['page_count']


def signup(client, email):
    response = client.post('/auth/signup', json={'email': email, 'password': 'a long test password', 'name': 'TEST'})
    assert response.status_code == 201, response.text


def test_preview_is_bound_to_the_application_like_the_export(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    app = create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes())
    with TestClient(app, base_url='http://localhost') as owner, \
            TestClient(app, base_url='http://localhost') as other, \
            TestClient(app, base_url='http://localhost') as anonymous:
        signup(owner, 'owner@example.test')
        case_id = owner.post('/cases', json={'title': 'TEST preview'}).json()['id']
        assert owner.get(f'/cases/{case_id}/export/preview').status_code == 200
        signup(other, 'other@example.test')
        for client in (other, anonymous):
            assert client.get(f'/cases/{case_id}/export/preview').status_code == 404
            assert client.post(f'/cases/{case_id}/export', json={'draft': True}).status_code == 404


def test_window_pages_match_the_actual_requested_pages_and_official_gates(tmp_path):
    store = CaseStore(tmp_path / 'window.sqlite')
    case = store_with_synthetic_files(store, sample_case(Codes(), provisions=['9.25.2.2.(1)']))
    with TestClient(create_app(store=store)) as client:
        legacy = client.get(f'/cases/{case.id}/export/preview').json()
        second = client.get(f'/cases/{case.id}/export/preview?start=1&count=2')
        assert second.status_code == 200, second.text
        body = second.json()
        assert body['start'] == 1 and len(body['pages']) == 2
        assert body['page_count'] == legacy['page_count']
        assert body['pages'] == legacy['pages'][1:3]
        assert body['filename'].endswith('-DRAFT.pdf')
        ready = client.get(f'/cases/{case.id}/export/preview?start=0&count=2&official=true')
        assert ready.status_code == 200, ready.text
        assert ready.json()['filename'].endswith('-scc-variance.pdf')
        pdf = PdfReader(io.BytesIO(decoded(ready.json()['pdf'], 'application/pdf')))
        assert all('Draft · not for submission' not in page.extract_text() for page in pdf.pages)
        store.add_fact(case.id, Fact(field='process.risk', value='Pending', kind='pointed',
                                    source=Source(type='user_text', ref='pending')))
        blocked = client.get(f'/cases/{case.id}/export/preview?official=true&count=1')
        assert blocked.status_code == 409 and blocked.json()['detail']['reasons']
        for query in ['start=-1', 'count=0', 'count=61', 'start=word']:
            assert client.get(f'/cases/{case.id}/export/preview?{query}').status_code == 422


def test_window_still_renders_when_pdf_bytes_do_not_fit(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject
    from engine.models import Case
    from engine.tests.case_builder_fixtures import fact
    store = CaseStore(tmp_path / 'large-window.sqlite')
    case = store.put(Case())
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    padding = DecodedStreamObject()
    padding.set_data(b'0' * 3_100_000)
    page[NameObject('/SyntheticSizeFixture')] = writer._add_object(padding)
    output = io.BytesIO()
    writer.write(output)
    saved = store.put_file(case.id, 'SYNTHETIC-size-boundary.pdf', output.getvalue())
    source = Source(type='file', ref=saved['id'], quote='SYNTHETIC size boundary, no evidence content.')
    case.facts.append(fact('evidence.size.file_ref', saved['id'], source=source))
    store.put(case)
    with TestClient(create_app(store=store)) as client:
        legacy = client.get(f'/cases/{case.id}/export/preview')
        assert legacy.status_code == 200 and legacy.json()['kind'] == 'too_large'
        response = client.get(f'/cases/{case.id}/export/preview?start=3&count=2')
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['start'] == 3 and len(body['pages']) == 2 and body['page_count'] >= 8
    assert 'pdf' not in body
    assert len(response.content) < RESPONSE_CAP


def test_large_drawing_window_bounds_raster_size_while_preserving_page_dimensions():
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=1800, height=1800)
    output = io.BytesIO(); writer.write(output)
    pages, total = page_images(output.getvalue(), start=1, max_pages=1, reserve_pdf=False)
    assert total == 2 and len(pages) == 1
    assert (pages[0].width, pages[0].height) == (1800, 1800)
    image = Image.open(io.BytesIO(pages[0].png))
    assert max(image.size) <= 1921
    assert encoded(len(pages[0].png)) + ENTRY_BYTES < PAYLOAD_BUDGET


def test_preview_draws_the_normal_appearance_of_retained_live_fields():
    from pypdf import PdfWriter
    from engine.models import Case
    original = export_case(Case(), draft=True).pdf
    reader = PdfReader(io.BytesIO(original))
    page_no = next(index for index, page in enumerate(reader.pages) if any(
        ref.get_object().get('/T') == 'Date1' for ref in page.get('/Annots', [])))
    blank, _ = page_images(original, start=page_no, max_pages=1, reserve_pdf=False)
    writer = PdfWriter(clone_from=io.BytesIO(original))
    writer.update_page_form_field_values(None, {'Date1': '2030-05-10'}, auto_regenerate=False)
    output = io.BytesIO(); writer.write(output)
    filled, _ = page_images(output.getvalue(), start=page_no, max_pages=1, reserve_pdf=False)
    assert filled[0].png != blank[0].png
