"""Reference mutations cross the real HTTP/store seam, without provider calls."""
import os
import threading

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case, EvidenceItem, Fact, Gap, SectionCRow, Source
from engine.privacy import PII_NOTICE
from engine.section_d import section_d_plan, supporting_documents
from engine.store import CaseStore, VersionConflict


@pytest.fixture(params=['sqlite', 'postgres'])
def context(request, tmp_path):
    if request.param == 'postgres':
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    else:
        store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store, Codes())), store


def selected_case(store):
    return store.put(Case(
        title='Synthetic last-reference withdrawal',
        provisions=['9.25.5.2.(1)(b)'],
        section_c=[SectionCRow(
            provision_id='9.25.5.2.(1)(b)', citation='Synthetic saved lookup',
            attribution_status='no row in the attribution table', pairs=[], intents=[])],
    ))


def fact(field, value, *, source_type='user_click', source_ref='Synthetic applicant'):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type=source_type, ref=source_ref, quote=str(value)))


def assert_private(response, status):
    assert response.status_code == status, response.text
    assert response.json()['meta']['notice'] == PII_NOTICE
    assert response.headers['x-batatis-notice'] == PII_NOTICE
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'


def replace(client, store, case_id, provisions):
    return client.post(f'/cases/{case_id}/section-d', json={
        'provisions': provisions, 'expected_version': store.get_version(case_id),
    })


def test_explicit_empty_withdraws_last_reference_over_http(context):
    client, store = context
    case = selected_case(store)
    version = store.get_version(case.id)
    response = client.post(f'/cases/{case.id}/section-d', json={
        'provisions': [], 'expected_version': version,
    })
    assert response.status_code == 200, response.text
    saved = store.get(case.id)
    assert saved.provisions == [] and saved.section_c == []
    assert response.json()['items'] == []
    assert response.json()['case_version'] == version + 1
    assert_private(response, 200)


def test_public_case_version_is_stored_row_version(context):
    client, store = context
    created = client.post('/cases', json={'title': 'Synthetic version acknowledgment'})
    assert created.status_code == 201
    case = created.json()
    assert case['version'] == store.get_version(case['id']) == 1
    assert client.get(f"/cases/{case['id']}").json()['version'] == 1


@pytest.mark.parametrize('body', [
    {'provisions': []}, {'provisions': ['9.25.5.2.(1)(b)']},
    {'provisions': None, 'expected_version': 1},
    *({'provisions': [], 'expected_version': value} for value in (0, -1, None, True, '1', 1.5)),
])
def test_ambiguous_or_unversioned_mutations_are_rejected(context, body):
    client, store = context
    case = selected_case(store)
    before = store.get(case.id)
    assert_private(client.post(f'/cases/{case.id}/section-d', json=body), 422)
    assert store.get(case.id) == before


@pytest.mark.parametrize('body', [None, {}, {'expected_version': 1}])
def test_omission_retains_and_rebuilds_the_current_selection(context, body):
    client, store = context
    case = selected_case(store)
    response = client.post(f'/cases/{case.id}/section-d', json=body)
    assert_private(response, 200)
    assert store.get(case.id).provisions == case.provisions
    assert store.get(case.id).section_c
    assert response.json()['items']
    assert response.json()['case_version'] == store.get(case.id).version == 2


@pytest.mark.parametrize('provisions', [[], ['9.27.3.2.(1)']])
def test_stale_client_version_cannot_replace_or_clear_a_newer_case(context, provisions):
    client, store = context
    case = selected_case(store)
    store.add_fact(case.id, fact('project.concurrent', 'keep this answer'))
    before = store.get(case.id)
    response = client.post(f'/cases/{case.id}/section-d', json={
        'provisions': provisions, 'expected_version': 1,
    })
    assert_private(response, 409)
    assert response.json()['detail'] == 'case was updated concurrently'
    assert store.get(case.id) == before


def test_invalid_replacement_is_not_persisted(context):
    client, store = context
    case = selected_case(store)
    before = store.get(case.id)
    response = replace(client, store, case.id, ['9.99.99.99.(1)'])
    assert_private(response, 404)
    assert store.get(case.id) == before


def test_clear_detaches_coverage_and_preserves_applicant_material(context):
    client, store = context
    case = selected_case(store)
    plan = section_d_plan(case, Codes())
    item = plan.items[0]
    payload = b'%PDF-1.4 Synthetic applicant document bytes\r\n'
    saved_file = store.put_file(case.id, 'synthetic.pdf', payload)
    keep = [
        fact('project.description', 'Applicant description'),
        fact('process.risk_assessment', 'Applicant risk assessment'),
        fact('process.mitigating_measures', 'Applicant mitigating measures'),
        fact('process.assumptions_and_limits', 'Applicant assumptions and limits'),
        fact('professional.name', 'Synthetic professional'),
        fact(f'evidence.{item.id}.file_ref', saved_file['id'],
             source_type='file', source_ref=saved_file['id']),
        *(fact(f'evidence.{item.id}.{field}', value) for field, value in (
            ('title', 'Applicant report title'), ('date', '2026-10-20'),
            ('responsible_party', 'Synthetic P.Eng.'), ('issuer', 'Synthetic organisation'),
            ('professional_seal', 'Applicant-reported seal metadata'))),
    ]
    scope = [
        fact('citation.9.25.5.2.', '9.25.5.2.'),
        fact('citation.9.25.5.2.(1)(b)', '9.25.5.2.(1)(b)'),
        fact('open_question.9.25.5.2.', 'Old applicant decision'),
        fact(f'evidence.{item.id}.item_id', item.id),
        fact(f'evidence.{item.id}.covers.{item.id}', True),
        fact(f'evidence.{item.id}.provision_id', item.provision_id),
        fact(f'evidence.{item.id}.objective', item.objective),
        fact(f'evidence.{item.id}.function', item.function),
    ]
    case.facts = keep + scope
    case.evidence = [EvidenceItem(id=item.id, description='Applicant document description',
                                 objective=item.objective, function=item.function, status='evidence_listed')]
    case.gaps = [Gap(section='D', field='old coverage', message='Synthetic stale derived result')]
    case = store.put(case, expected_version=1)
    assert section_d_plan(store.get(case.id), Codes()).items[0].attachments
    old_snapshot, old_version = store.get_snapshot(case.id)

    cleared = replace(client, store, case.id, [])
    assert_private(cleared, 200)
    current = store.get(case.id)
    assert current.provisions == current.section_c == current.gaps == []
    assert current.version == old_version + 1 == cleared.json()['case_version']
    assert {entry.id: entry for entry in current.facts if entry.id in {f.id for f in keep}} == {f.id: f for f in keep}
    assert not ({entry.id for entry in current.facts} & {entry.id for entry in scope})
    assert current.evidence[0].id == item.id
    assert current.evidence[0].description == 'Applicant document description'
    assert current.evidence[0].kind == 'file'
    assert current.evidence[0].objective is current.evidence[0].function is None
    documents = supporting_documents(current)
    assert len(documents) == 1 and documents[0].item_ids == ()
    assert store.get_file(case.id, saved_file['id'])['data'] == payload
    with pytest.raises(VersionConflict):
        store.put(old_snapshot, expected_version=old_version)

    # Stable ids survive clear/reselection, so identity must not silently re-link the old report.
    reselected = replace(client, store, case.id, case.provisions)
    assert_private(reselected, 200)
    same = next(row for row in reselected.json()['items'] if row['id'] == item.id)
    assert same['attachments'] == [] and same['status'] == 'needed'
    linked = client.post(f'/cases/{case.id}/facts', json=fact(
        f'evidence.{item.id}.covers.{item.id}', True).model_dump())
    assert_private(linked, 200)
    rebuilt = client.post(f'/cases/{case.id}/section-d', json={})
    assert next(row for row in rebuilt.json()['items'] if row['id'] == item.id)['attachments']
    deleted = client.delete(f'/cases/{case.id}/evidence/{item.id}')
    assert_private(deleted, 200)
    assert store.get(case.id).evidence == []
    assert not any(entry.field.startswith(f'evidence.{item.id}.') for entry in store.get(case.id).facts)
    assert store.get_file(case.id, saved_file['id'])['data'] == payload


def test_clear_and_empty_rebuild_do_not_open_missing_codedb(context, monkeypatch):
    _, store = context
    case = selected_case(store)
    monkeypatch.setattr('engine.api.Codes', lambda: pytest.fail('Empty selection must not open CodeDB'))
    client = TestClient(create_app(store=store))
    assert_private(replace(client, store, case.id, []), 200)
    response = client.post(f'/cases/{case.id}/section-d', json={})
    assert_private(response, 200)
    assert response.json()['items'] == []
    assert any('benchmark' in notice for notice in response.json()['notices'])


def test_clear_keeps_missing_benchmark_process_and_professional_export_holds(context):
    client, store = context
    case = selected_case(store)
    assert_private(replace(client, store, case.id, []), 200)
    gaps = client.get(f'/cases/{case.id}/gaps').json()['items']
    assert any(row['field'] == 'provisions' and row['section'] == 'C' for row in gaps)
    fields = client.get(f'/cases/{case.id}/process-fields').json()['items']
    assert {'risk_assessment', 'mitigating_measures', 'assumptions_and_limits'} <= {row['id'] for row in fields}
    assert client.get(f'/cases/{case.id}/professional').json()['required'] != 'no'
    exported = client.post(f'/cases/{case.id}/export')
    assert_private(exported, 409)
    assert any('benchmark' in str(reason).lower() for reason in exported.json()['detail']['reasons'])


@pytest.mark.parametrize('mutation,status', [('fact', 409), ('delete', 404), ('expire', 404)])
def test_clear_cas_retains_concurrent_facts_and_never_recreates(context, monkeypatch, mutation, status):
    from engine.tests.test_retention import _age
    from engine.tests.test_privacy_interleavings import raw_rows
    client, store = context
    case = selected_case(store)
    store.put_file(case.id, 'synthetic.pdf', b'%PDF-1.4 synthetic')
    entered, release = threading.Event(), threading.Event()
    put = store.put

    def paused_put(current, *, expected_version=None):
        entered.set()
        assert release.wait(15)
        return put(current, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', paused_put)
    responses, errors = [], []

    def clear():
        try:
            responses.append(client.post(f'/cases/{case.id}/section-d', json={
                'provisions': [], 'expected_version': 1,
            }))
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=clear)
    thread.start()
    try:
        assert entered.wait(15)
        if mutation == 'fact':
            store.add_fact(case.id, fact('project.concurrent', 'preserved'))
        elif mutation == 'delete':
            assert store.delete(case.id)
        else:
            _age(store, case.id, 8)
    finally:
        release.set()
        thread.join(20)
    assert not thread.is_alive() and errors == []
    assert_private(responses[0], status)
    saved, version, files = raw_rows(store, case.id)
    if mutation == 'fact':
        assert version == 2 and files == 1 and saved.provisions == case.provisions
        assert any(entry.field == 'project.concurrent' for entry in saved.facts)
    else:
        assert saved is None and files == 0


@pytest.mark.parametrize('state', ['missing', 'deleted', 'expired'])
def test_clear_of_absent_or_expired_case_is_404_without_insert(context, state):
    from engine.tests.test_retention import _age
    from engine.tests.test_privacy_interleavings import raw_rows
    client, store = context
    case = selected_case(store)
    if state == 'missing':
        case_id = 'case_synthetic_nonexistent'
    else:
        case_id = case.id
        store.put_file(case.id, 'synthetic.pdf', b'%PDF-1.4 synthetic')
        if state == 'deleted':
            store.delete(case.id)
        else:
            _age(store, case.id, 8)
    response = client.post(f'/cases/{case_id}/section-d', json={'provisions': [], 'expected_version': 1})
    assert_private(response, 404)
    assert raw_rows(store, case_id) == (None, None, 0)


def test_store_acknowledgments_ignore_supplied_payload_version(context):
    client, store = context
    case = store.put(Case(version=987654))
    assert case.version == 1
    case.version = 567890
    case = store.put(case, expected_version=1)
    assert case.version == 2
    snapshot, version = store.get_snapshot(case.id)
    assert snapshot.version == version == 2
    response = client.post(f'/cases/{case.id}/facts', json=fact('project.note', 'saved').model_dump())
    assert response.json()['version'] == store.get_version(case.id) == 3
    response = client.delete(f'/cases/{case.id}/evidence/absent')
    assert response.json()['version'] == store.get_version(case.id) == 4
    case.version = 999999
    assert store.put(case).version == store.get_version(case.id) == 5


def test_selection_change_keeps_other_reference_decisions_and_document_links(context):
    client, store = context
    case = selected_case(store)
    first, second = case.provisions[0], '9.27.3.2.(1)'
    assert_private(replace(client, store, case.id, [first, second]), 200)
    case = store.get(case.id)
    plan = section_d_plan(case, Codes())
    kept_item = next(item for item in plan.items if item.provision_id == second)
    old_item = next(item for item in plan.items if item.provision_id == first)
    saved_file = store.put_file(case.id, 'synthetic.pdf', b'%PDF-1.4 synthetic')
    keep = [fact('citation.' + second, second), fact('open_question.9.27.3.2.', 'Unchanged decision'),
            fact(f'evidence.{kept_item.id}.file_ref', saved_file['id'], source_type='file', source_ref=saved_file['id'])]
    case.facts = keep + [fact('citation.' + first, first),
                        fact('citation.9.25.5.2.', '9.25.5.2.'),
                        fact('open_question.9.25.5.2.', 'Obsolete decision'),
                        fact('evidence.shared.item_id', old_item.id),
                        fact(f'evidence.{old_item.id}.file_ref', saved_file['id'],
                             source_type='file', source_ref=saved_file['id'])]
    case.evidence = [EvidenceItem(id=kept_item.id, description='Keep scoped metadata',
                                 objective=kept_item.objective, function=kept_item.function)]
    store.put(case, expected_version=case.version)
    response = replace(client, store, case.id, [second])
    assert_private(response, 200)
    current = store.get(case.id)
    assert {f.id for f in keep} <= {f.id for f in current.facts}
    assert not any(f.field in {'citation.' + first, 'citation.9.25.5.2.', 'open_question.9.25.5.2.',
                               'evidence.shared.item_id'} for f in current.facts)
    assert current.evidence[0].objective == kept_item.objective
    assert current.evidence[0].function == kept_item.function
    assert next(item for item in response.json()['items'] if item['id'] == kept_item.id)['attachments']
    reselected = replace(client, store, case.id, [first, second])
    assert_private(reselected, 200)
    assert next(item for item in reselected.json()['items'] if item['id'] == old_item.id)['attachments'] == []


def test_old_inflight_rebuild_cannot_restore_a_completed_clear(context, monkeypatch):
    import engine.routes_case as routes
    client, store = context
    case = selected_case(store)
    entered, release = threading.Event(), threading.Event()
    original = routes.section_d_plan
    responses, errors = [], []

    def rebuild():
        try:
            responses.append(client.post(f'/cases/{case.id}/section-d', json={}))
        except BaseException as exc:
            errors.append(exc)

    old_request = threading.Thread(target=rebuild)
    # The FastAPI handler runs in a worker, so identify its request by the nonempty selection.
    def paused_handler_plan(current, codes):
        result = original(current, codes)
        if current.provisions:
            entered.set()
            assert release.wait(15)
        return result

    monkeypatch.setattr(routes, 'section_d_plan', paused_handler_plan)
    old_request.start()
    try:
        assert entered.wait(15)
        assert_private(replace(client, store, case.id, []), 200)
    finally:
        release.set()
        old_request.join(20)
    assert not old_request.is_alive() and errors == []
    assert_private(responses[0], 409)
    assert store.get(case.id).provisions == store.get(case.id).section_c == []


def test_legacy_json_version_is_overridden_by_the_same_stored_row(context):
    client, store = context
    case = store.put(Case())
    if isinstance(store, CaseStore):
        import sqlite3
        with sqlite3.connect(store.path) as con:
            con.execute("UPDATE cases SET json=json_set(json, '$.version', 999999) WHERE id=?", (case.id,))
    else:
        with store._conn() as con:
            con.execute("UPDATE cases SET data=jsonb_set(data, '{version}', '999999'::jsonb) WHERE id=%s", (case.id,))
    snapshot, version = store.get_snapshot(case.id)
    assert snapshot.version == version == 1
    assert client.get(f'/cases/{case.id}').json()['version'] == 1
    updated = store.add_fact(case.id, fact('project.version_note', 'Synthetic'))
    assert updated.version == store.get(case.id).version == 2


def test_reselection_requires_a_fresh_lookup_and_cannot_use_old_rows(context, monkeypatch):
    from engine.codes import CodeDbMissing
    client, store = context
    case = selected_case(store)
    assert_private(replace(client, store, case.id, []), 200)
    before = store.get(case.id)
    calls = []

    def missing(_self, provision_id, division='B'):
        calls.append((provision_id, division))
        raise CodeDbMissing()

    monkeypatch.setattr(Codes, 'provision', missing)
    response = replace(client, store, case.id, case.provisions)
    assert_private(response, 503)
    assert calls == [(case.provisions[0], 'B')]
    assert store.get(case.id) == before
