import io

import pytest
from pypdf import PdfReader
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.export import form_path
from engine.export.sample import sample_case
from engine.models import Fact, Source
from engine.store import CaseStore

pytestmark = pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')


@pytest.fixture(scope='module')
def ctx(tmp_path_factory):
    codes = Codes()
    store = CaseStore(tmp_path_factory.mktemp('cases') / 'cases.sqlite')
    return TestClient(create_app(store=store, codes=codes)), store, codes


def test_export_route(ctx):
    client, store, codes = ctx
    case = store.put(sample_case(codes))
    r = client.post(f'/cases/{case.id}/export')
    assert r.status_code == 200 and r.headers['content-type'] == 'application/pdf'
    assert r.content.startswith(b'%PDF') and 'DRAFT' not in r.headers['content-disposition']

    store.add_fact(case.id, Fact(field='storeys', value=2, kind='proposed', source=Source(type='user_text', ref='m'),
                                 confidence=0.5))
    r = client.post(f'/cases/{case.id}/export')
    assert r.status_code == 409 and any('storeys' in x for x in r.json()['detail']['reasons'])
    r = client.post(f'/cases/{case.id}/export', json={'draft': True})
    assert r.status_code == 200 and 'DRAFT' in r.headers['content-disposition']
    assert client.post('/cases/case_nope/export').status_code == 404


def test_final_roundtrip_and_direct_api_bypass(ctx):
    client, store, codes = ctx
    complete = sample_case(codes, provisions=['9.25.2.2.(1)'])
    incomplete = complete.model_copy(deep=True)
    incomplete.facts = [f for f in incomplete.facts if f.field in
                        {'owner_name', 'mailing_address', 'request_date', 'municipal_address'}]
    incomplete.gaps = []
    incomplete.evidence = []
    store.put(incomplete)
    # No GET /gaps or preflight call before this direct export request.
    assert client.post(f'/cases/{incomplete.id}/export').status_code == 409
    draft = client.post(f'/cases/{incomplete.id}/export', json={'draft': True})
    assert draft.status_code == 200 and 'DRAFT' in draft.headers['content-disposition']
    store.put(complete)
    assert not any(g['severity'] == 'blocking' for g in client.get(f'/cases/{complete.id}/gaps').json()['gaps'])
    final = client.post(f'/cases/{complete.id}/export')
    assert final.status_code == 200
    pdf = PdfReader(io.BytesIO(final.content))
    assert not pdf.get_fields() and '/AcroForm' not in pdf.trailer['/Root']
    text = ' '.join(p.extract_text() for p in pdf.pages)
    assert 'SYNTHETIC applicant risk passage' in text and 'SYNTHETIC product-literature attachment' in text
    assert codes.citation('9.25.2.2.(1)', 'B') in text
    assert store.get(complete.id).model_dump() == complete.model_dump()

    fact = Fact(field='process.risk', value='UNKNOWN NEW RISK', kind='pointed',
                source=Source(type='user_text', ref='synthetic-revision'))
    assert client.post(f'/cases/{complete.id}/facts', json=fact.model_dump()).status_code == 200
    assert client.post(f'/cases/{complete.id}/export').status_code == 409
    draft = client.post(f'/cases/{complete.id}/export', json={'draft': True})
    text = ' '.join(p.extract_text() for p in PdfReader(io.BytesIO(draft.content)).pages)
    assert 'SYNTHETIC applicant risk passage' not in text and 'UNKNOWN NEW RISK' not in text
