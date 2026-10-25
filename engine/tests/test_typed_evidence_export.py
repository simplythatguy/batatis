"""Facts-only document listings survive the real SCC form/appendix export path."""
import io
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from engine.api import create_app
from engine.codes import Codes
from engine.export import form_path
from engine.store import CaseStore


pytestmark = pytest.mark.skipif(not form_path().exists(), reason='private SCC form is not available')


@pytest.mark.parametrize('count', [1, 24], ids=['one-listing', 'combined-box-overflow'])
def test_typed_document_titles_are_in_appendix_without_claiming_files_or_review(tmp_path, count):
    store = CaseStore(tmp_path / 'cases.sqlite')
    with TestClient(create_app(store=store, codes=Codes())) as client:
        created = client.post('/api/cases', json={'title': 'TEST typed document export'})
        assert created.status_code == 201
        case_id = created.json()['id']
        titles = [f'TEST typed document {index}' for index in range(1, count + 1)]
        for index, title in enumerate(titles, start=1):
            for name, value in (
                ('title', title), ('description', title),
                ('responsible_party', f'TEST applicant-listed organisation {index}'),
                ('evidence_type', 'evaluation'),
            ):
                saved = client.post(f'/api/cases/{case_id}/facts', json={
                    'field': f'evidence.test_document_{index}.{name}', 'value': value,
                    'kind': 'pointed', 'status': 'confirmed',
                    'source': {'type': 'user_text', 'ref': 'TEST document metadata', 'quote': value},
                })
                assert saved.status_code == 200, saved.text
        before = client.get(f'/api/cases/{case_id}').json()

        response = client.post(f'/api/cases/{case_id}/export', json={'draft': True})
        assert response.status_code == 200, response.text[:300]
        assert response.headers['content-type'] == 'application/pdf'
        assert 'DRAFT' in response.headers['content-disposition']
        reader = PdfReader(io.BytesIO(response.content))
        pages = [' '.join((page.extract_text() or '').split()) for page in reader.pages]
        # Section D can span pages; a continuation need not repeat its heading.
        appendix = ' '.join(pages[int(reader.metadata['/BatatisFormPages']):])
        for index, title in enumerate(titles, start=1):
            assert title in appendix, f'Appendix D omitted {title}'
            assert f'D-{index}' in appendix
        assert 'listed by applicant, no file attached, not reviewed.' in appendix
        assert 'No supporting documents listed.' not in appendix
        if count == 24:
            assert 'appendix only; no file' in appendix
            # The form's box keeps the whole entries it holds and names the rest.
            form = ' '.join(pages[:int(reader.metadata['/BatatisFormPages'])])
            assert 'D-1: TEST typed document 1 - TEST applicant-listed organisation 1' in form
            assert 'to D-24: continued in Appendix D' in form
        assert client.get(f'/api/cases/{case_id}').json() == before
        with closing(sqlite3.connect(store.path)) as con:
            assert con.execute('SELECT COUNT(*) FROM case_files WHERE case_id=?', (case_id,)).fetchone()[0] == 0
