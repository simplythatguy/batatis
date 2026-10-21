"""Synthetic jurisdiction edits exercise the real router and both storage adapters."""
import json
import os
import sqlite3
import threading
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, EvidenceItem, Fact, Gap, SectionCRow, Source
from engine.privacy import PII_NOTICE
from engine.retention import reset_purge_clock
from engine.store import CaseStore


FIRST = {'id': 'test-ahj-a', 'name': 'TEST jurisdiction A (synthetic)', 'authority': 'TEST authority A'}
SECOND = {'id': 'test-ahj-b', 'name': 'TEST jurisdiction B (synthetic)', 'authority': None}


@pytest.fixture(params=['sqlite', 'postgres'])
def context(request, tmp_path):
    if request.param == 'postgres':
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set; real Postgres required')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    else:
        store = CaseStore(tmp_path / 'cases.sqlite')
    reset_purge_clock()
    with TestClient(create_app(store=store)) as client:
        yield client, store
    reset_purge_clock()


def assert_private(response, status):
    assert response.status_code == status, response.text
    assert response.json()['meta']['notice'] == PII_NOTICE
    assert response.headers['x-batatis-notice'] == PII_NOTICE
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'


def update(client, case_id, jurisdiction, version, prefix='/api'):
    return client.put(f'{prefix}/cases/{case_id}/jurisdiction', json={
        'jurisdiction': jurisdiction, 'expected_version': version,
    })


def test_create_change_clear_keeps_same_case_and_acknowledges_actual_versions(context):
    client, store = context
    created = client.post('/api/cases', json={'title': 'TEST jurisdiction edits', 'jurisdiction': FIRST})
    assert_private(created, 201)
    original = Case.model_validate(created.json())
    assert original.version == 1
    changed = update(client, original.id, SECOND, original.version)
    assert_private(changed, 200)
    assert changed.json()['id'] == original.id
    assert changed.json()['jurisdiction'] == SECOND
    assert changed.json()['version'] == store.get_version(original.id) == 2
    cleared = update(client, original.id, None, changed.json()['version'], prefix='')
    assert_private(cleared, 200)
    assert cleared.json()['id'] == original.id
    assert cleared.json()['jurisdiction'] is None
    assert cleared.json()['version'] == store.get_version(original.id) == 3
    loaded = client.get(f'/api/cases/{original.id}')
    assert_private(loaded, 200)
    assert loaded.json() == cleared.json()
    assert loaded.json()['created_at'] == original.created_at


def raw_state(store, case_id):
    """Inspect physical state over a new connection; a getter would purge a bad resurrection."""
    if isinstance(store, CaseStore):
        with closing(sqlite3.connect(store.path)) as con:
            row = con.execute('SELECT json, version FROM cases WHERE id=?', (case_id,)).fetchone()
            files = con.execute('SELECT id, name, content_type, size, data, created_at '
                                'FROM case_files WHERE case_id=? ORDER BY id', (case_id,)).fetchall()
        return (json.loads(row[0]), row[1], files) if row else (None, None, files)
    with store._conn() as con:
        row = con.execute('SELECT data, version FROM cases WHERE id=%s', (case_id,)).fetchone()
        files = con.execute('SELECT id, name, content_type, size, data, created_at '
                            'FROM case_files WHERE case_id=%s ORDER BY id', (case_id,)).fetchall()
    return (row[0], row[1], files) if row else (None, None, files)


def case_ids(store):
    if isinstance(store, CaseStore):
        with closing(sqlite3.connect(store.path)) as con:
            return {row[0] for row in con.execute('SELECT id FROM cases')}
    with store._conn() as con:
        return {row[0] for row in con.execute('SELECT id FROM cases')}


def fact(field, value):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='TEST synthetic applicant', quote=str(value)))


@pytest.mark.parametrize('jurisdiction', [SECOND, None], ids=['change', 'clear'])
def test_preserves_all_unrelated_case_fields_document_metadata_and_file_bytes(context, jurisdiction):
    client, store = context
    reference = 'TEST-synthetic-reference-not-a-Code-citation'
    case = store.put(Case(
        title='TEST applicant material retention', jurisdiction=FIRST,
        facts=[fact('project.description', 'TEST applicant wording'),
               fact('process.risk_assessment', 'TEST existing process wording'),
               fact('evidence.test-report.title', 'TEST listed report'),
               fact('evidence.test-report.date', '2026-10-20'),
               fact('evidence.test-report.responsible_party', 'TEST existing responsible party'),
               fact('evidence.test-report.issuer', 'TEST existing issuer'),
               fact('evidence.test-report.professional_seal', 'TEST applicant-listed metadata'),
               fact('evidence.test-report.provision_id', reference)],
        provisions=[reference],
        section_c=[SectionCRow(provision_id=reference, citation='TEST saved row; not a Code citation',
                              attribution_status='no row in the attribution table', pairs=[], intents=[])],
        evidence=[EvidenceItem(id='test-report', description='TEST existing document listing',
                               evidence_type='TEST listing', status='evidence_listed')],
        gaps=[Gap(section='D', field='TEST existing gap', message='TEST administrative gap')],
    ))
    payload = b'%PDF-1.4\r\nTEST synthetic bytes\x00\xff\r\nendstream\r\n'
    uploaded = client.post(f'/api/cases/{case.id}/files', content=payload,
                           headers={'content-type': 'application/pdf', 'x-filename': 'TEST report.pdf'})
    assert_private(uploaded, 201)
    file_id = uploaded.json()['id']
    attached = Fact(field='evidence.test-report.file_ref', value=file_id, kind='pointed', status='confirmed',
                    source=Source(type='file', ref=file_id, quote='TEST attachment provenance'))
    acknowledged = client.post(f'/api/cases/{case.id}/facts', json=attached.model_dump())
    assert_private(acknowledged, 200)
    # The existing fact writer normalizes its acknowledgment's derived kind after writing.
    # Establish that canonical snapshot in storage before comparing physical retention.
    snapshot, snapshot_version = store.get_snapshot(case.id)
    before = store.put(snapshot, expected_version=snapshot_version)
    assert before.model_dump(exclude={'version', 'updated_at'}) == Case.model_validate(
        acknowledged.json()).model_dump(exclude={'version', 'updated_at'})
    assert before.evidence[0].kind == 'file'
    before_raw, version, before_files = raw_state(store, case.id)
    ids_before = case_ids(store)

    response = update(client, case.id, jurisdiction, version)
    assert_private(response, 200)
    after = Case.model_validate(response.json())
    assert (after.jurisdiction.model_dump() if after.jurisdiction else None) == jurisdiction
    assert after.version == version + 1
    assert after.model_dump(exclude={'jurisdiction', 'version', 'updated_at'}) == before.model_dump(
        exclude={'jurisdiction', 'version', 'updated_at'})
    after_raw, actual_version, after_files = raw_state(store, case.id)
    assert actual_version == after.version
    assert {key: value for key, value in after_raw.items() if key not in ('jurisdiction', 'updated_at')} == {
        key: value for key, value in before_raw.items() if key not in ('jurisdiction', 'updated_at')}
    assert after_files == before_files
    assert store.get_file(case.id, file_id)['data'] == payload
    assert case_ids(store) == ids_before
    assert Case.model_validate(client.get(f'/api/cases/{case.id}').json()) == after


@pytest.mark.parametrize('body', [
    {}, {'expected_version': 1}, {'jurisdiction': None},
    *({'jurisdiction': None, 'expected_version': value} for value in
      (None, True, False, '1', 1.0, 1.5, 0, -1)),
    {'jurisdiction': None, 'expected_version': 1, 'authority': 'TEST unsupported wrapper'},
    {'jurisdiction': None, 'expected_version': 1, 'title': 'TEST must not overwrite'},
    {'jurisdiction': {}, 'expected_version': 1},
    {'jurisdiction': {'name': 'TEST missing id'}, 'expected_version': 1},
    {'jurisdiction': {'id': 'test-missing-name'}, 'expected_version': 1},
    {'jurisdiction': {'id': None, 'name': 'TEST null id'}, 'expected_version': 1},
    {'jurisdiction': {'id': 'test-null-name', 'name': None}, 'expected_version': 1},
    {'jurisdiction': 'test-not-an-object', 'expected_version': 1},
])
def test_rejects_missing_fields_coerced_versions_and_unsupported_wrappers(context, body):
    client, store = context
    case = store.put(Case(title='TEST invalid request retention', jurisdiction=FIRST))
    before = raw_state(store, case.id)
    ids_before = case_ids(store)
    response = client.put(f'/api/cases/{case.id}/jurisdiction', json=body)
    assert_private(response, 422)
    assert raw_state(store, case.id) == before
    assert case_ids(store) == ids_before


@pytest.mark.parametrize('content', [None, 'null', '{"jurisdiction":', '[]'])
def test_rejects_missing_null_malformed_and_nonobject_bodies(context, content):
    client, store = context
    case = store.put(Case(title='TEST malformed request', jurisdiction=FIRST))
    before = raw_state(store, case.id)
    response = client.put(f'/api/cases/{case.id}/jurisdiction', content=content,
                          headers={'content-type': 'application/json'})
    assert_private(response, 422)
    assert raw_state(store, case.id) == before


@pytest.mark.parametrize('jurisdiction', [SECOND, None], ids=['change', 'clear'])
def test_stale_version_preserves_newer_fact_and_jurisdiction(context, jurisdiction):
    client, store = context
    case = store.put(Case(title='TEST stale edit', jurisdiction=FIRST))
    written = client.post(f'/api/cases/{case.id}/facts', json=fact('project.newer', 'TEST keep me').model_dump())
    assert_private(written, 200)
    assert written.json()['version'] == 2
    before = raw_state(store, case.id)
    response = update(client, case.id, jurisdiction, 1)
    assert_private(response, 409)
    assert response.json()['detail'] == 'case was updated concurrently'
    assert raw_state(store, case.id) == before


@pytest.mark.parametrize('state', ['unknown', 'deleted', 'expired'])
def test_unknown_deleted_expired_remain_physically_absent(context, state):
    from engine.tests.test_retention import _age
    client, store = context
    case = Case(title='TEST terminal edit', jurisdiction=FIRST)
    if state != 'unknown':
        store.put(case)
        store.put_file(case.id, 'TEST terminal.pdf', b'%PDF-1.4 TEST terminal bytes')
        if state == 'deleted':
            assert client.delete(f'/api/cases/{case.id}').status_code == 204
        else:
            # Consume the middleware sweep so targeted snapshot expiry must commit cleanup.
            assert client.get(f'/api/cases/{case.id}').status_code == 200
            _age(store, case.id, 8)
            assert raw_state(store, case.id)[2]
    ids_before = case_ids(store) - {case.id}
    for jurisdiction in (SECOND, None):
        response = update(client, case.id, jurisdiction, 1)
        assert_private(response, 404)
        assert response.json()['detail'] == 'case not found'
        assert raw_state(store, case.id) == (None, None, [])
        assert case_ids(store) == ids_before


@pytest.mark.parametrize('jurisdiction', [SECOND, None], ids=['change', 'clear'])
@pytest.mark.parametrize('mutation,status', [('fact', 409), ('delete', 404), ('expire', 404)])
def test_racing_write_delete_expiry_preserves_data_without_retry_or_recreation(
        context, monkeypatch, jurisdiction, mutation, status):
    from engine.tests.test_retention import _age
    client, store = context
    case = store.put(Case(title='TEST concurrent edit', jurisdiction=FIRST))
    store.put_file(case.id, 'TEST preserved.pdf', b'%PDF-1.4 TEST preserved bytes')
    ids_before = case_ids(store)
    entered, release = threading.Event(), threading.Event()
    put = store.put
    attempts, responses, errors = [], [], []

    def paused_put(current, *, expected_version=None):
        attempts.append((current.id, expected_version))
        entered.set()
        assert release.wait(20)
        return put(current, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', paused_put)

    def edit():
        try:
            responses.append(update(client, case.id, jurisdiction, 1))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=edit)
    thread.start()
    try:
        assert entered.wait(20)
        if mutation == 'fact':
            response = client.post(f'/api/cases/{case.id}/facts', json=fact(
                'project.concurrent', 'TEST preserve newer answer').model_dump())
            assert_private(response, 200)
            preserved = raw_state(store, case.id)
        elif mutation == 'delete':
            assert client.delete(f'/api/cases/{case.id}').status_code == 204
        else:
            _age(store, case.id, 8)
    finally:
        release.set()
        thread.join(25)
    assert not thread.is_alive() and errors == []
    assert attempts == [(case.id, 1)]
    assert_private(responses[0], status)
    assert responses[0].json()['detail'] == ('case was updated concurrently' if status == 409 else 'case not found')
    if mutation == 'fact':
        assert raw_state(store, case.id) == preserved
        assert preserved[0]['jurisdiction'] == FIRST and preserved[1] == 2
        assert case_ids(store) == ids_before
    else:
        assert raw_state(store, case.id) == (None, None, [])
        assert case_ids(store) == ids_before - {case.id}


def test_actual_row_version_overrides_embedded_legacy_metadata(context):
    client, store = context
    case = store.put(Case(title='TEST embedded stale version', jurisdiction=FIRST))
    if isinstance(store, CaseStore):
        with closing(sqlite3.connect(store.path)) as con, con:
            con.execute("UPDATE cases SET json=json_set(json, '$.version', 999) WHERE id=?", (case.id,))
    else:
        with store._conn() as con:
            con.execute("UPDATE cases SET data=jsonb_set(data, '{version}', '999'::jsonb) WHERE id=%s", (case.id,))
    response = update(client, case.id, SECOND, 1)
    assert_private(response, 200)
    assert response.json()['version'] == store.get_version(case.id) == 2


def test_update_clear_and_idempotent_value_do_not_resolve_corpus_or_provider(context, monkeypatch):
    client, store = context
    case = store.put(Case(title='TEST offline jurisdiction', jurisdiction=FIRST))

    def forbidden(*args, **kwargs):
        pytest.fail('Jurisdiction edits must not resolve CodeDB or authorize a provider')

    monkeypatch.setattr('engine.api.Codes', forbidden)
    monkeypatch.setattr('engine.llm_gate.authorize', forbidden)
    get_env = os.environ.get

    def no_provider_keys(key, default=None):
        if key.endswith('_API_KEY'):
            pytest.fail('Jurisdiction edits must not look up provider keys')
        return get_env(key, default)

    monkeypatch.setattr(os.environ, 'get', no_provider_keys)
    for version, jurisdiction in enumerate((SECOND, SECOND, None, None), start=1):
        response = update(client, case.id, jurisdiction, version)
        assert_private(response, 200)
        assert response.json()['version'] == version + 1
    assert store.get(case.id).jurisdiction is None


def test_expiry_after_waiting_for_actual_write_lock_commits_physical_cleanup(context, monkeypatch):
    client, store = context
    cutoff = [datetime.now(timezone.utc) - timedelta(days=7)]
    monkeypatch.setattr('engine.store.retention_cutoff', lambda: cutoff[0].isoformat())
    monkeypatch.setattr('engine.store_postgres.retention_cutoff', lambda: cutoff[0].isoformat())
    case = store.put(Case(title='TEST expiry during lock wait', jurisdiction=FIRST,
                          created_at=(cutoff[0] + timedelta(seconds=1)).isoformat()))
    store.put_file(case.id, 'TEST expiring.pdf', b'%PDF-1.4 TEST expiring bytes')
    ready, resume, attempted, done = (threading.Event() for _ in range(4))
    put = store.put
    responses, errors = [], []

    def paused_put(current, *, expected_version=None):
        ready.set()
        assert resume.wait(20)
        return put(current, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', paused_put)

    class Observed:
        def __init__(self, con):
            self.con = con

        def execute(self, query, *args):
            text = str(query)
            if ready.is_set() and ('BEGIN IMMEDIATE' in text or text.startswith('SELECT data, version')):
                attempted.set()
            return self.con.execute(query, *args)

        def __enter__(self):
            self.con.__enter__()
            return self

        def __exit__(self, *args):
            return self.con.__exit__(*args)

        def __getattr__(self, key):
            return getattr(self.con, key)

    def edit():
        try:
            responses.append(update(client, case.id, SECOND, 1))
        except BaseException as exc:
            errors.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=edit)
    thread.start()
    try:
        assert ready.wait(20)  # The real snapshot completed before taking the competing write lock.
        if isinstance(store, CaseStore):
            connect = store._connect
            monkeypatch.setattr(store, '_connect', lambda: Observed(connect()))
            holder = sqlite3.connect(store.path, isolation_level=None)
            holder.execute('BEGIN IMMEDIATE')
        else:
            connect = store._conn

            @contextmanager
            def observed_connection():
                with connect() as con:
                    yield Observed(con)

            monkeypatch.setattr(store, '_conn', observed_connection)
            holder_context = connect()
            holder = holder_context.__enter__()
            holder.execute('SELECT id FROM cases WHERE id=%s FOR UPDATE', (case.id,))
        try:
            resume.set()
            assert attempted.wait(20) and not done.wait(.2)
            cutoff[0] += timedelta(seconds=2)
        finally:
            if isinstance(store, CaseStore):
                holder.commit()
                holder.close()
            else:
                holder_context.__exit__(None, None, None)
    finally:
        resume.set()
        thread.join(25)
    assert not thread.is_alive() and not errors
    assert_private(responses[0], 404)
    assert responses[0].json()['detail'] == 'case not found'
    assert raw_state(store, case.id) == (None, None, [])
