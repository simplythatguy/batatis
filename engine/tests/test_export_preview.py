"""GET /cases/{id}/export/preview: the draft export's own bytes and page images, under the export's access policy."""
import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from engine.api import create_app
from engine.codes import Codes
from engine.export import export_case, form_path
from engine.export.preview import BUDGET_BYTES, SCALE, page_images
from engine.export.sample import sample_case
from engine.models import Fact, Source
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import store_with_synthetic_files

pytestmark = pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')
RESPONSE_CAP = 4_500_000          # serverless response body limit


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
    assert body['filename'] == f'{case.id}-scc-variance-DRAFT.pdf'
    reader = PdfReader(io.BytesIO(decoded(body['pdf'], 'application/pdf')))
    assert reader.metadata['/Title'].endswith('(DRAFT)') and not reader.get_fields()
    assert marker not in ' '.join(page.extract_text() for page in reader.pages)     # confirmed values only
    assert body['page_count'] == len(reader.pages) == len(body['pages']) > 20      # a long package, every page
    for page, preview in zip(reader.pages, body['pages']):
        assert (preview['width'], preview['height']) == (float(page.mediabox.width), float(page.mediabox.height))
        image = Image.open(io.BytesIO(decoded(preview['image'], 'image/png')))
        assert image.format == 'PNG' and image.size == (round(preview['width'] * SCALE), round(preview['height'] * SCALE))


def test_page_images_keep_page_order_and_stop_at_the_budget():
    codes = Codes()
    pdf = export_case(sample_case(codes), codes=codes, draft=True).pdf
    every, count = page_images(pdf)
    assert len(every) == count and sum(len(p.png) for p in every) + len(pdf) <= BUDGET_BYTES
    first, total = page_images(pdf, budget=len(pdf) + sum(len(p.png) for p in every[:3]))
    assert total == count and [p.png for p in first] == [p.png for p in every[:3]]
    assert page_images(pdf, budget=len(pdf))[0] == []


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
