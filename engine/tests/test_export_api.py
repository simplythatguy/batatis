import pytest
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
