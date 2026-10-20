"""Case API: jurisdiction gap, uploads, missing code database, and concurrent writes."""
import asyncio
import hashlib
import io
import logging
import sqlite3
import threading
from pathlib import Path

import httpx
import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from engine.api import create_app
from engine.codes import CodeDbMissing, Codes, default_db
from engine.export import FormNotFound
from engine.models import Case, Fact, Source
from engine.section_d import SectionDPlan
from engine.store import CaseStore

EDMONTON = {'id': 'edmonton', 'name': 'Edmonton', 'authority': None}
ORIGIN = {'Origin': 'http://localhost:5173'}


class _GapCodes:
    """Enough of Codes for an empty-case gap check. Citations here are fixtures, not code text."""

    db_path = Path('/unused')

    def provision(self, provision_id, division=None):
        return {'id': provision_id, 'citation': 'fixture citation', 'article_title': 'Fixture'}

    def citation(self, provision_id, division=None):
        return 'fixture citation'


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_FILES', str(tmp_path / 'files'))
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store, _GapCodes()))
    return client, store


def _gap(gaps, field):
    return next((g for g in gaps if g['field'] == field), None)


def test_create_with_edmonton_object_clears_reviewing_jurisdiction_gap(api):
    client, _store = api
    created = client.post('/cases', json={'title': 'New house application', 'jurisdiction': EDMONTON})
    assert created.status_code == 201
    body = created.json()
    assert body['jurisdiction'] == EDMONTON
    assert 'jurisdiction_id' not in body
    gaps = client.get(f"/cases/{body['id']}/gaps").json()
    assert _gap(gaps, 'jurisdiction') is None


def test_put_jurisdiction_clears_gap_left_by_create_without_one(api):
    client, _store = api
    created = client.post('/cases', json={'title': 'New house application'})
    assert created.status_code == 201 and created.json()['jurisdiction'] is None
    cid = created.json()['id']
    before = client.get(f'/cases/{cid}/gaps').json()
    gap = _gap(before, 'jurisdiction')
    assert gap is not None
    assert gap['message'] == 'Your application appears to be missing the reviewing jurisdiction.'
    assert gap['section'] == 'B'

    updated = client.put(f'/cases/{cid}/jurisdiction', json=EDMONTON)
    assert updated.status_code == 200
    assert updated.json()['jurisdiction'] == EDMONTON
    assert _gap(client.get(f'/cases/{cid}/gaps').json(), 'jurisdiction') is None
    assert client.put('/cases/missing/jurisdiction', json=EDMONTON).status_code == 404


def test_jurisdiction_string_and_jurisdiction_id_do_not_set_the_field(api):
    """The gap reads case.jurisdiction. A header string or a jurisdiction_id key is not that field."""
    client, _store = api
    rejected = client.post('/cases', json={'title': 'x', 'jurisdiction': 'edmonton'})
    assert rejected.status_code == 422
    created = client.post('/cases', json={'title': 'x', 'jurisdiction_id': 'edmonton'})
    assert created.status_code == 201
    assert created.json()['jurisdiction'] is None
    assert _gap(client.get(f"/cases/{created.json()['id']}/gaps").json(), 'jurisdiction') is not None
    put = client.put(f"/cases/{created.json()['id']}/jurisdiction", json='edmonton')
    assert put.status_code == 422
    assert client.get(f"/cases/{created.json()['id']}").json()['jurisdiction'] is None


def test_put_authority_name_roundtrip(api):
    client, _store = api
    cid = client.post('/cases').json()['id']
    body = {'id': 'calgary', 'name': 'Calgary', 'authority': 'City of Calgary'}
    assert client.put(f'/cases/{cid}/jurisdiction', json=body).json()['jurisdiction'] == body
    omitted = {'id': 'edmonton', 'name': 'Edmonton'}
    stored = client.put(f'/cases/{cid}/jurisdiction', json=omitted).json()['jurisdiction']
    assert stored == {**omitted, 'authority': None}
    assert _gap(client.get(f'/cases/{cid}/gaps').json(), 'jurisdiction') is None


def _pdf(text='SECRET CODE TEXT') -> bytes:
    buf = io.BytesIO()
    sheet = canvas.Canvas(buf)
    sheet.drawString(36, 72, text)
    sheet.showPage()
    sheet.save()
    return buf.getvalue()


def test_pdf_upload_stores_bytes_and_one_exact_file_fact(api, tmp_path, monkeypatch):
    client, _store = api
    monkeypatch.setenv('BATATIS_FILES', str(tmp_path / 'uploads'))
    cid = client.post('/cases').json()['id']
    data = _pdf()
    opened = client.post(f'/cases/{cid}/files', files={'file': ('../../plans.pdf', data, 'application/octet-stream')})
    assert opened.status_code == 201
    body = opened.json()
    assert body['name'] == 'plans.pdf'
    assert body['pages'] == 1
    assert body['read'] is True
    assert body['sha256'] == hashlib.sha256(data).hexdigest()
    assert '/' not in opened.text
    assert 'SECRET CODE TEXT' not in opened.text
    root = Path(tmp_path / 'uploads').resolve()
    stored = root / cid / f"{body['id']}.pdf"
    assert stored.is_file() and stored.read_bytes() == data
    assert root in stored.parents
    case = client.get(f'/cases/{cid}').json()
    fact = case['facts'][-1]
    assert fact['field'] == f"file.{body['id']}.name"
    assert fact['value'] == 'plans.pdf'
    assert fact['kind'] == 'exact'
    assert fact['status'] == 'confirmed'
    assert fact['source']['type'] == 'file'
    assert fact['source']['ref'] == body['id']
    assert fact['source']['quote'] is None
    assert 'SECRET CODE TEXT' not in str(case)
    assert str(root) not in str(case)


def test_upload_rejects_missing_case_non_pdf_and_oversize(api, monkeypatch):
    client, _store = api
    data = _pdf()
    assert client.post('/cases/missing/files', files={'file': ('a.pdf', data, 'application/pdf')}).status_code == 404
    cid = client.post('/cases').json()['id']
    not_pdf = client.post(f'/cases/{cid}/files', files={'file': ('notes.txt', b'hello', 'text/plain')})
    assert not_pdf.status_code == 415 and not_pdf.json() == {'detail': 'not a PDF'}
    assert '/' not in not_pdf.text
    monkeypatch.setenv('BATATIS_FILE_MAX_BYTES', '32')
    too_big = client.post(f'/cases/{cid}/files', files={'file': ('a.pdf', data, 'application/pdf')})
    assert too_big.status_code == 413 and too_big.json() == {'detail': 'file too large'}
    assert client.get(f'/cases/{cid}').json()['facts'] == []
    missing = client.post(f'/cases/{cid}/files')
    assert missing.status_code == 422
    assert isinstance(missing.json()['detail'], list)
    magic = b'%PDF-1.4\nnot a readable pdf'
    unreadable = client.post(f'/cases/{cid}/files', files={'file': ('bad.pdf', magic, 'application/pdf')})
    assert unreadable.status_code == 415
    assert client.get(f'/cases/{cid}').json()['facts'] == []


@pytest.mark.parametrize('error', [ValueError, KeyError, IndexError, TypeError,
                                 AttributeError, RecursionError, RuntimeError])
@pytest.mark.parametrize('stage', ['reader', 'pages'])
def test_upload_maps_parser_failures_to_415(api, tmp_path, monkeypatch, error, stage):
    client, _store = api
    cid = client.post('/cases').json()['id']

    class BrokenReader:
        def __init__(self, *_args):
            if stage == 'reader':
                raise error('synthetic parser failure')

        @property
        def pages(self):
            raise error('synthetic page-tree failure')

    monkeypatch.setattr('engine.files.PdfReader', BrokenReader)
    response = client.post(f'/cases/{cid}/files', files={'file': ('a.pdf', _pdf(), 'application/pdf')})
    assert response.status_code == 415
    assert response.json() == {'detail': 'not a PDF'}
    assert client.get(f'/cases/{cid}').json()['facts'] == []
    assert not list((tmp_path / 'files').rglob('*'))


@pytest.mark.parametrize('outcome', ['missing', 'error', 'cleanup_error'])
def test_upload_discards_pdf_when_case_update_fails(api, tmp_path, monkeypatch, outcome, caplog):
    client, store = api
    cid = client.post('/cases').json()['id']
    failure = sqlite3.OperationalError('synthetic database lock')

    def fail_update(*_args):
        if outcome == 'missing':
            return None
        raise failure

    monkeypatch.setattr(store, 'mutate', fail_update)
    if outcome == 'cleanup_error':
        def fail_cleanup(*_args):
            raise OSError('synthetic cleanup failure')

        monkeypatch.setattr('engine.api.discard_pdf', fail_cleanup)

    if outcome == 'missing':
        response = client.post(f'/cases/{cid}/files', files={'file': ('a.pdf', _pdf(), 'application/pdf')})
        assert response.status_code == 404
        assert response.json() == {'detail': 'case not found'}
    else:
        with pytest.raises(sqlite3.OperationalError) as raised:
            client.post(f'/cases/{cid}/files', files={'file': ('a.pdf', _pdf(), 'application/pdf')})
        assert raised.value is failure

    assert store.get(cid).facts == []
    if outcome == 'cleanup_error':
        assert 'failed to discard PDF' in caplog.text
    else:
        assert not list((tmp_path / 'files').rglob('*.pdf'))


@pytest.mark.parametrize('operation', ['get', 'save_pdf', 'mutate'])
def test_upload_blocking_work_allows_other_requests(api, monkeypatch, operation):
    client, store = api
    cid = client.post('/cases').json()['id']
    entered = threading.Event()
    release = threading.Event()
    if operation == 'save_pdf':
        import engine.api as api_module
        owner = api_module
    else:
        owner = store
    original = getattr(owner, operation)

    def blocked(*args, **kwargs):
        entered.set()
        if not release.wait(3):
            raise RuntimeError('upload blocked the event loop')
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, operation, blocked)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                                     base_url='http://test') as concurrent:
            uploading = asyncio.create_task(concurrent.post(
                f'/cases/{cid}/files', files={'file': ('a.pdf', _pdf(), 'application/pdf')}))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                probe = await asyncio.wait_for(concurrent.get('/openapi.json'), timeout=1)
                assert probe.status_code == 200
            finally:
                release.set()
                response = await uploading
            assert response.status_code == 201

    asyncio.run(exercise())


def test_missing_codedb_is_503_without_a_path(tmp_path, monkeypatch, caplog):
    missing = tmp_path / 'no-such' / 'codedb.sqlite'
    monkeypatch.setenv('BATATIS_CODEDB', str(missing))
    store = CaseStore(tmp_path / 'cases.sqlite')
    app = create_app(store)
    assert FileNotFoundError not in app.exception_handlers
    assert CodeDbMissing in app.exception_handlers
    client = TestClient(app)
    with caplog.at_level(logging.ERROR):
        response = client.get('/code/search', params={'q': 'egress'}, headers=ORIGIN)
    assert response.status_code == 503
    assert response.json() == {'detail': 'code database not found'}
    assert '/' not in response.text
    assert str(missing) not in response.text
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
    assert str(missing) in caplog.text
    with pytest.raises(CodeDbMissing) as raised:
        Codes(missing)
    assert str(raised.value) == 'code database not found'
    assert not isinstance(raised.value, FileNotFoundError)


def test_default_db_is_repo_relative(monkeypatch):
    monkeypatch.delenv('BATATIS_CODEDB', raising=False)
    assert default_db() == Path(__file__).resolve().parents[2] / 'codedb' / 'build' / 'codedb.sqlite'


def test_missing_form_503_has_no_path(tmp_path, monkeypatch, caplog):
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    client = TestClient(create_app(store, codes=object()))

    def boom(*_args, **_kwargs):
        raise FormNotFound('SCC variance form not found at /var/secret/form.pdf (set BATATIS_SCC_FORM)')

    monkeypatch.setattr('engine.api.export_case', boom)
    with caplog.at_level(logging.ERROR):
        response = client.post(f'/cases/{case.id}/export', headers=ORIGIN)
    assert response.status_code == 503
    assert response.json() == {'detail': 'SCC variance form not found'}
    assert '/' not in response.text
    assert '/var/secret/form.pdf' in caplog.text
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'


def test_cors_exposes_content_disposition_and_any_x_batatis_header(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    app = create_app(store, _GapCodes())

    @app.get('/probe-headers')
    def probe():
        return Response(content=b'ok', headers={'X-Batatis-Probe': 'yes', 'Content-Disposition': 'attachment; filename="a.pdf"'})

    client = TestClient(app)
    options = client.options('/cases', headers={**ORIGIN, 'Access-Control-Request-Method': 'POST'})
    assert options.headers.get('access-control-allow-origin') == 'http://localhost:5173'
    cid = client.post('/cases').json()['id']
    got = client.get(f'/cases/{cid}', headers=ORIGIN)
    exposed = got.headers['access-control-expose-headers'].lower()
    for name in ('content-disposition', 'x-batatis-form-version', 'x-batatis-form-date',
                 'x-batatis-form-id', 'x-batatis-jurisdiction'):
        assert name in exposed
    probed = client.get('/probe-headers', headers=ORIGIN)
    probed_exposed = probed.headers['access-control-expose-headers'].lower()
    assert 'x-batatis-probe' in probed_exposed
    assert 'content-disposition' in probed_exposed


def test_mutate_holds_the_case_lock_while_add_fact_waits(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    entered = threading.Event()
    release = threading.Event()

    def slow(current):
        assert store._case_lock(current.id).locked()
        entered.set()
        assert release.wait(5)
        current.title = 'updated'

    holder = threading.Thread(target=lambda: store.mutate(case.id, slow))
    holder.start()
    assert entered.wait(5)
    fact = Fact(field='storeys', value=2, kind='pointed', source=Source(type='user_text', ref='m'))
    adder = threading.Thread(target=lambda: store.add_fact(case.id, fact))
    adder.start()
    adder.join(0.2)
    assert adder.is_alive()
    release.set()
    adder.join(5)
    holder.join(5)
    got = store.get(case.id)
    assert got.title == 'updated'
    assert [item.id for item in got.facts] == [fact.id]


def test_concurrent_add_facts_all_persist(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    facts = [Fact(field=f'n{i}', value=i, kind='exact', status='confirmed', source=Source(type='user_text', ref='m'))
             for i in range(12)]
    barrier = threading.Barrier(len(facts))
    errors = []

    def add(fact):
        try:
            barrier.wait()
            if store.add_fact(case.id, fact) is None:
                errors.append(fact.id)
        except Exception as exc:  # noqa: BLE001 — the assertion reports the thread failure
            errors.append(repr(exc))

    threads = [threading.Thread(target=add, args=(fact,)) for fact in facts]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert {item.id for item in store.get(case.id).facts} == {fact.id for fact in facts}


def test_section_d_does_not_drop_a_fact_added_during_lookup(tmp_path, monkeypatch):
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    entered = threading.Event()
    release = threading.Event()

    def slow_rows(provisions, codes):
        assert store._case_lock(case.id).locked()
        entered.set()
        assert release.wait(5)
        return []

    monkeypatch.setattr('engine.routes_case.section_c_rows', slow_rows)
    monkeypatch.setattr('engine.routes_case.section_d_plan', lambda current, codes: SectionDPlan(items=[], notices=[]))
    client = TestClient(create_app(store, codes=object()))
    result = {}

    def post_section():
        result['response'] = client.post(f'/cases/{case.id}/section-d', json={'provisions': ['9.25.5.2.(1)']})

    worker = threading.Thread(target=post_section)
    worker.start()
    assert entered.wait(5)
    fact = Fact(field='storeys', value=2, kind='pointed', source=Source(type='user_text', ref='m'))
    adder = threading.Thread(target=lambda: result.update(added=store.add_fact(case.id, fact)))
    adder.start()
    adder.join(0.2)
    assert adder.is_alive()
    release.set()
    adder.join(5)
    worker.join(5)
    assert result['response'].status_code == 200
    stored = store.get(case.id)
    assert stored.provisions == ['9.25.5.2.(1)']
    assert [item.field for item in stored.facts] == ['storeys']
