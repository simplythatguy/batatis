"""End-to-end case flow through the HTTP API.

Create a case, add a fact, upload a synthetic PDF, then read administrative gaps
and export. Gaps and export open the code database. When that file is not built,
those steps are skipped through ``engine.tests._db_skip.require_repo_db``.

An empty case export is 409. A draft export is 200 when the blank SCC form is
present; without that form the 409 result still stands. Neither response is a
finding that a design complies or is safe.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from engine.api import create_app
from engine.export import form_path
from engine.store import CaseStore
from engine.tests._db_skip import require_repo_db

FACT = {
    'field': 'municipal_address',
    'value': '100 Example Avenue, Edmonton',
    'kind': 'exact',
    'status': 'confirmed',
    'source': {'type': 'user_text', 'ref': 'e2e-synthetic'},
}


def _pdf() -> bytes:
    buf = io.BytesIO()
    sheet = canvas.Canvas(buf)
    sheet.drawString(36, 72, 'SYNTHETIC e2e attachment')
    sheet.showPage()
    sheet.save()
    return buf.getvalue()


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv('BATATIS_FILES', str(tmp_path / 'files'))
    store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store))


def _create_fact_upload(client: TestClient, pdf: bytes) -> tuple[str, dict]:
    created = client.post('/cases', json={'title': 'Synthetic e2e case'})
    assert created.status_code == 201
    case_id = created.json()['id']
    added = client.post(f'/cases/{case_id}/facts', json=FACT)
    assert added.status_code == 200
    assert added.json()['facts'][0]['field'] == 'municipal_address'
    uploaded = client.post(
        f'/cases/{case_id}/files',
        files={'file': ('sheet.pdf', pdf, 'application/pdf')},
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert body['name'] == 'sheet.pdf'
    assert body['pages'] == 1
    assert body['read'] is True
    assert body['sha256'] == hashlib.sha256(pdf).hexdigest()
    return case_id, body


def test_e2e_create_facts_and_upload_store_pdf_bytes(tmp_path, monkeypatch):
    """The upload is the PDF bytes on disk. The case record stores the name and file id."""
    client = _client(tmp_path, monkeypatch)
    pdf = _pdf()
    case_id, stored = _create_fact_upload(client, pdf)
    path = tmp_path / 'files' / case_id / f"{stored['id']}.pdf"
    assert path.is_file()
    assert path.read_bytes() == pdf
    case = client.get(f'/cases/{case_id}').json()
    file_fact = next(fact for fact in case['facts'] if fact['source']['type'] == 'file')
    assert file_fact['value'] == 'sheet.pdf'
    assert file_fact['source']['ref'] == stored['id']
    assert pdf not in str(case).encode()
    spec = client.get('/openapi.json').json()['paths'][f'/cases/{{case_id}}/files']
    assert 'post' in spec
    assert 'get' not in spec


def test_e2e_gaps_then_export_409_and_draft_200(tmp_path, monkeypatch):
    """Administrative gaps, then a blocked export and a draft PDF when the form exists."""
    require_repo_db()
    client = _client(tmp_path, monkeypatch)
    case_id, _stored = _create_fact_upload(client, _pdf())

    gaps = client.get(f'/cases/{case_id}/gaps')
    assert gaps.status_code == 200
    assert isinstance(gaps.json(), list)
    assert 'complies' not in gaps.text.lower()

    blocked = client.post(f'/cases/{case_id}/export')
    assert blocked.status_code == 409
    detail = blocked.json()['detail']
    assert detail['message'] == 'export blocked; resolve these or export a draft'
    assert detail['reasons']
    assert 'complies' not in blocked.text.lower()

    if not form_path().exists():
        return
    draft = client.post(f'/cases/{case_id}/export', json={'draft': True})
    assert draft.status_code == 200
    assert draft.headers['content-type'] == 'application/pdf'
    assert draft.content.startswith(b'%PDF')
    assert 'DRAFT' in draft.headers['content-disposition']
    assert 'complies' not in draft.headers.get('content-disposition', '').lower()
