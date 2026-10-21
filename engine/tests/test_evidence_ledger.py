"""Synthetic public evidence-listing contract, exercised against both real adapters."""
from __future__ import annotations

import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case, EvidenceItem, Fact, Source
from engine.process_fields import confirmed_value
from engine.privacy import PII_NOTICE
from engine.retention import reset_purge_clock
from engine.store import CaseStore
from engine.section_d import section_d_plan, supporting_documents


@pytest.fixture(params=['sqlite', 'postgres'])
def ledger(request, tmp_path):
    if request.param == 'sqlite':
        store = CaseStore(tmp_path / 'ledger.sqlite')
    else:
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    owned = []

    def create(**kwargs):
        case = store.put(Case(**kwargs), expected_version=0)
        owned.append(case.id)
        return case

    reset_purge_clock()
    try:
        yield store, create, TestClient(create_app(store=store))
    finally:
        for case_id in owned:
            store.delete(case_id)
        reset_purge_clock()


def payload(version=1, **changes):
    return dict(dict(operation='create', evidence_id='doc_wall', expected_version=version,
                title='Synthetic comparison report', description='Applicant lists a report; no file supplied.',
                evidence_type='engineering review', responsible_party='Synthetic applicant organisation',
                date='revision A, 2026-10-21', issuer='Synthetic issuer'), **changes)


def private(response, status):
    assert response.status_code == status, response.text
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'
    assert response.headers['x-batatis-notice'] == PII_NOTICE
    assert response.json()['meta']['notice'] == PII_NOTICE


def fact(field, value, source_type='user_text', source_ref='Synthetic applicant'):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type=source_type, ref=source_ref, quote=str(value)))


def post(client, case_id, body):
    return client.post(f'/api/cases/{case_id}/evidence', json=body)


def delete(client, case_id, evidence_id, version):
    return client.request('DELETE', f'/api/cases/{case_id}/evidence/{evidence_id}',
                          json={'expected_version': version})


def test_actual_missing_post_route_and_durable_acknowledgment(ledger):
    store, create, client = ledger
    case = create()
    response = client.post(f'/api/cases/{case.id}/evidence', json=payload())
    private(response, 200)
    saved = response.json()
    assert saved['evidence']['id'] == 'doc_wall'
    assert saved['evidence']['status'] == 'evidence_listed'
    assert saved['evidence']['kind'] == 'text'
    assert saved['case_version'] == saved['case']['version'] == 2
    assert store.get(case.id).model_dump() == saved['case']
    assert client.get(f'/api/cases/{case.id}').json() == {**saved['case'], 'meta': saved['meta']}


def test_create_edit_reload_and_delete_use_one_actual_slot_and_keep_revisions(ledger):
    store, create, client = ledger
    unrelated = fact('project.description', 'keep unrelated applicant words')
    case = create(facts=[unrelated])
    private(post(client, case.id, payload()), 200)
    before = store.get(case.id)
    edit = payload(2, operation='update', title='Edited report', description='Edited prose',
                   responsible_party='Different responsible person', date='revision B', issuer='New issuer')
    private(post(client, case.id, edit), 200)
    saved = store.get(case.id)
    assert [item.id for item in saved.evidence] == ['doc_wall']
    assert saved.evidence[0].description == 'Edited prose'
    for name in ('title', 'description', 'responsible_party', 'date', 'issuer', 'evidence_type'):
        assert confirmed_value(saved, f'evidence.doc_wall.{name}') == edit[name]
    assert all(entry in saved.facts for entry in before.facts)
    listed = [entry for entry in saved.facts if entry.field.startswith('evidence.doc_wall.')
              and entry.field != 'evidence.doc_wall.auto_link']
    assert all(entry.source.type == 'user_text' and entry.kind == 'pointed' for entry in listed)
    assert all(entry.source.quote == str(entry.value) for entry in listed)
    assert supporting_documents(saved) == []
    fresh = CaseStore(store.path) if isinstance(store, CaseStore) else type(store)(store.url)
    assert fresh.get(case.id) == saved
    response = delete(client, case.id, 'doc_wall', 3)
    private(response, 200)
    assert response.json()['version'] == 4
    assert store.get(case.id).facts == [unrelated] and store.get(case.id).evidence == []
    assert delete(client, case.id, 'doc_wall', 4).status_code == 404
    assert post(client, case.id, payload(4, operation='update')).status_code == 404
    assert store.get_version(case.id) == 4


@pytest.mark.parametrize('value', [None, 0, -1, True, '1', 1.0, 1.5])
def test_post_requires_strict_positive_version(ledger, value):
    store, create, client = ledger
    case = create()
    private(post(client, case.id, payload(value)), 422)
    assert store.get(case.id) == case


@pytest.mark.parametrize('changes,missing', [
    ({}, 'expected_version'), ({}, 'evidence_id'), ({}, 'operation'),
    ({'operation': 'upsert'}, None), ({'evidence_id': 'wall.child'}, None),
    ({'evidence_id': ' wall '}, None), ({'evidence_id': ''}, None),
    ({'title': ' \n'}, None), ({'description': ''}, None), ({'responsible_party': 42}, None),
    ({'source': {'type': 'professional', 'ref': 'claimed'}}, None),
    ({'source': {'type': 'officer', 'ref': 'claimed'}}, None),
    ({'source': {'type': 'code', 'ref': 'claimed'}}, None),
    ({'kind': 'file'}, None), ({'file_id': 'file_claimed'}, None),
    ({'file_ref': 'file_claimed'}, None), ({'status': 'reviewed'}, None),
    ({'professional_seal': 'claimed authenticated'}, None),
    ({'scope': {'objective': 'OS1.2', 'function': 'F03'}}, None),
    ({'scope': {}}, None), ({'scope': {'item_id': 'ev_fake', 'source': 'code'}}, None),
])
def test_ambiguous_identity_metadata_and_authority_claims_are_rejected(ledger, changes, missing):
    store, create, client = ledger
    case = create()
    body = payload(**changes)
    if missing:
        body.pop(missing)
    private(post(client, case.id, body), 422)
    assert store.get(case.id) == case


def test_distinct_same_title_ids_and_explicit_operations_are_not_upserts(ledger):
    store, create, client = ledger
    case = create()
    private(post(client, case.id, payload()), 200)
    private(post(client, case.id, payload(2)), 409)
    private(post(client, case.id, payload(2, operation='update', evidence_id='absent')), 404)
    private(post(client, case.id, payload(2, evidence_id='doc_wall~2')), 200)
    before = store.get(case.id)
    private(post(client, case.id, payload(2, operation='update')), 409)
    assert store.get(case.id) == before
    private(delete(client, case.id, 'doc_wall', 3), 200)
    saved = store.get(case.id)
    assert [item.id for item in saved.evidence] == ['doc_wall~2']
    assert confirmed_value(saved, 'evidence.doc_wall~2.title') == payload()['title']


def test_omitted_metadata_is_retained_and_text_is_never_parsed_or_truncated(ledger):
    store, create, client = ledger
    case = create()
    description = 'Responsible: prose only. Date: not a date.\n' + 'x' * 6000
    body = payload(description=description)
    for key in ('responsible_party', 'date', 'issuer'):
        body.pop(key)
    private(post(client, case.id, body), 200)
    saved = store.get(case.id)
    assert saved.evidence[0].description == description
    assert confirmed_value(saved, 'evidence.doc_wall.responsible_party') is None
    assert confirmed_value(saved, 'evidence.doc_wall.date') is None
    private(post(client, case.id, payload(2, operation='update')), 200)
    body = payload(3, operation='update')
    for key in ('responsible_party', 'date', 'issuer'):
        body.pop(key)
    private(post(client, case.id, body), 200)
    assert confirmed_value(store.get(case.id), 'evidence.doc_wall.date') == payload()['date']


def test_unscoped_create_edit_delete_never_resolve_corpus(ledger, monkeypatch):
    store, create, client = ledger
    case = create(provisions=['9.27.3.2.(1)'])
    def forbidden(*_args, **_kwargs):
        raise AssertionError('unscoped text must not open corpus')
    monkeypatch.setattr('engine.api.Codes', forbidden)
    private(post(client, case.id, payload()), 200)
    private(post(client, case.id, payload(2, operation='update')), 200)
    private(delete(client, case.id, 'doc_wall', 3), 200)


def test_current_unique_scope_is_ledger_link_not_cross_provision_or_completeness(ledger):
    store, create, client = ledger
    codes = Codes()
    case = create(provisions=['9.27.3.2.(1)', '9.27.3.3.(1)'])
    plan = section_d_plan(case, codes)
    target = next(item for item in plan.items if item.provision_id == '9.27.3.2.(1)' and item.function == 'F61')
    assert any(item.provision_id == '9.27.3.3.(1)' and item.function == target.function
               and item.objective == target.objective for item in plan.items)
    response = post(client, case.id, payload(scope={'item_id': target.id,
        'provision_id': target.provision_id, 'objective': target.objective, 'function': target.function}))
    private(response, 200)
    saved = store.get(case.id)
    assert confirmed_value(saved, 'evidence.doc_wall.item_id') == target.id
    assert confirmed_value(saved, 'evidence.doc_wall.provision_id') == target.provision_id
    assert saved.evidence[0].objective == target.objective
    assert saved.evidence[0].function == target.function
    assert all(item.status == 'needed' for item in section_d_plan(saved, codes).items)
    gaps = client.get(f'/api/cases/{case.id}/gaps').json()['items']
    assert any(gap['id'].startswith('attachment:') for gap in gaps)
    assert any(gap['id'].startswith('evidence:') for gap in gaps)
    data = b'%PDF-1.4 Synthetic unchanged upload\n'
    file = store.put_file(case.id, 'scoped.pdf', data)
    private(client.post(f'/api/cases/{case.id}/facts', json=fact('evidence.doc_wall.file_ref',
        file['id'], 'file', file['id']).model_dump()), 200)
    after = section_d_plan(store.get(case.id), codes)
    assert [item.id for item in after.items if item.attachments] == [target.id]
    assert store.get_file(case.id, file['id'])['data'] == data


def test_scope_must_be_current_consistent_and_unambiguous_and_missing_corpus_is_503(ledger, monkeypatch):
    store, create, client = ledger
    case = create(provisions=['9.27.3.2.(1)'])
    plan = section_d_plan(case, Codes())
    target = plan.items[0]
    for scope in ({'item_id': 'ev_missing'}, {'provision_id': '9.25.5.2.(1)(b)'},
                  {'item_id': target.id, 'provision_id': '9.27.3.2.(2)'},
                  {'item_id': target.id, 'objective': 'invented'}):
        private(post(client, case.id, payload(scope=scope)), 422)
        assert store.get(case.id) == case
    if len(plan.items) > 1:
        private(post(client, case.id, payload(scope={'provision_id': '9.27.3.2.(1)'})), 422)
    # New application closure so a previous successful lookup cannot hide a missing corpus.
    monkeypatch.setenv('BATATIS_CODEDB', '/missing/synthetic-code-corpus.sqlite')
    other_client = TestClient(create_app(store=store))
    private(post(other_client, case.id, payload(scope={'item_id': target.id})), 503)
    assert store.get(case.id) == case


def test_clear_reselect_and_metadata_edit_cannot_relink_but_explicit_scope_can(ledger):
    store, create, client = ledger
    case = create(provisions=['9.27.3.2.(1)'])
    target = section_d_plan(case, Codes()).items[0]
    # Stable plan identity is allowed as a document identity, but never implies linkage here.
    body = payload(evidence_id=target.id, scope={'item_id': target.id})
    private(post(client, case.id, body), 200)
    private(client.post(f'/api/cases/{case.id}/section-d', json={'provisions': [], 'expected_version': 2}), 200)
    private(client.post(f'/api/cases/{case.id}/section-d', json={'provisions': case.provisions, 'expected_version': 3}), 200)
    private(post(client, case.id, payload(4, operation='update', evidence_id=target.id)), 200)
    saved = store.get(case.id)
    assert confirmed_value(saved, f'evidence.{target.id}.auto_link') is False
    assert confirmed_value(saved, f'evidence.{target.id}.item_id') is None
    assert saved.evidence[0].objective is None and saved.evidence[0].function is None
    private(post(client, case.id, payload(5, operation='update', evidence_id=target.id, scope={'item_id': target.id})), 200)
    assert confirmed_value(store.get(case.id), f'evidence.{target.id}.item_id') == target.id
    private(post(client, case.id, payload(6, operation='update', evidence_id=target.id, scope=None)), 200)
    assert confirmed_value(store.get(case.id), f'evidence.{target.id}.item_id') is None


def test_no_attribution_scope_does_not_invent_pair(ledger):
    store, create, client = ledger
    case = create(provisions=['3.1.9.1.(4)'])
    item = section_d_plan(case, Codes()).items[0]
    assert item.objective is item.function is None
    private(post(client, case.id, payload(scope={'item_id': item.id})), 200)
    saved = store.get(case.id)
    assert saved.evidence[0].objective is saved.evidence[0].function is None
    assert section_d_plan(saved, Codes()).items[0].status == 'needed'


def test_actual_attachments_cannot_be_erased_or_converted_by_text_edits(ledger):
    store, create, client = ledger
    case = create()
    data = b'%PDF-1.4 Synthetic owned attachment\n'
    file = store.put_file(case.id, 'retained.pdf', data)
    orphan = store.put_file(case.id, 'unlinked.pdf', b'%PDF-1.4 Synthetic unlinked bytes\n')
    other = create()
    foreign = store.put_file(other.id, 'other-case.pdf', b'%PDF-1.4 Synthetic other case\n')
    inventory = {entry['id']: store.get_file(case.id, entry['id']) for entry in (file, orphan)}
    foreign_before = store.get_file(other.id, foreign['id'])
    store.add_fact(case.id, fact('evidence.doc_wall.file_ref', file['id'], 'file', file['id']))
    before = store.get(case.id)
    private(post(client, case.id, payload(2, operation='update')), 422)
    assert store.get(case.id) == before
    private(post(client, case.id, payload(2, evidence_id='separate')), 200)
    assert store.get_file(case.id, file['id'])['data'] == data
    assert confirmed_value(store.get(case.id), 'evidence.doc_wall.file_ref') == file['id']
    private(delete(client, case.id, 'doc_wall', 3), 200)
    assert {file_id: store.get_file(case.id, file_id) for file_id in inventory} == inventory
    assert store.get_file(other.id, foreign['id']) == foreign_before
    assert store.get(other.id) == other
    assert [item.id for item in store.get(case.id).evidence] == ['separate']


@pytest.mark.parametrize('value', [None, 0, -1, True, '2', 2.0])
def test_delete_requires_strict_current_version(ledger, value):
    store, create, client = ledger
    case = create()
    private(post(client, case.id, payload()), 200)
    before = store.get(case.id)
    private(delete(client, case.id, 'doc_wall', value), 422)
    assert store.get(case.id) == before


def test_delete_missing_body_and_stale_versions_never_acknowledge_success(ledger):
    store, create, client = ledger
    case = create()
    private(post(client, case.id, payload()), 200)
    private(client.delete(f'/api/cases/{case.id}/evidence/doc_wall'), 422)
    private(client.request('DELETE', f'/api/cases/{case.id}/evidence/doc_wall', json={}), 422)
    private(client.request('DELETE', f'/api/cases/{case.id}/evidence/doc_wall',
                           json={'expected_version': 2, 'file_id': 'claimed'}), 422)
    private(delete(client, case.id, 'doc_wall', 1), 409)
    assert store.get_version(case.id) == 2


def test_delete_safe_legacy_nested_id_and_reject_only_destructive_prefix_ambiguity(ledger):
    store, create, client = ledger
    case = create(evidence=[EvidenceItem(id=slot, description=slot) for slot in ('wall', 'wall.child', 'wall~2')],
        facts=[fact(f'evidence.{slot}.title', slot) for slot in ('wall', 'wall.child', 'wall~2')])
    private(delete(client, case.id, 'wall', 1), 422)
    assert store.get(case.id) == case
    private(post(client, case.id, payload(evidence_id='wall', operation='update')), 422)
    private(delete(client, case.id, 'wall.child', 1), 200)
    saved = store.get(case.id)
    assert {item.id for item in saved.evidence} == {'wall', 'wall~2'}
    private(delete(client, case.id, 'wall', 2), 200)
    assert [item.id for item in store.get(case.id).evidence] == ['wall~2']


@pytest.mark.parametrize('method', ['post', 'delete'])
@pytest.mark.parametrize('mutation,status', [('fact', 409), ('clear', 409), ('remove', 409), ('delete', 404), ('expire', 404)])
def test_racing_mutation_cannot_lose_new_data_or_resurrect_absence(ledger, monkeypatch, method, mutation, status):
    store, create, client = ledger
    case = create()
    file = store.put_file(case.id, 'race-retained.pdf', b'%PDF-1.4 Synthetic race-owned bytes\n')
    file_before = store.get_file(case.id, file['id'])
    private(post(client, case.id, payload()), 200)
    put = store.put
    raced = []

    def race(stale, *, expected_version=None):
        if not raced:
            raced.append(True)
            if mutation == 'fact':
                store.add_fact(case.id, fact('project.concurrent', 'newer answer'))
            elif mutation == 'remove':
                store.remove_evidence(case.id, 'doc_wall')
            elif mutation == 'delete':
                store.delete(case.id)
            else:
                current, version = store.get_snapshot(case.id)
                if mutation == 'expire':
                    current.created_at = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
                else:
                    from engine.reference_selection import replace_references
                    replace_references(current, [], [])
                put(current, expected_version=version)
        return put(stale, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', race)
    response = (post(client, case.id, payload(2, operation='update', title='must not save'))
                if method == 'post' else delete(client, case.id, 'doc_wall', 2))
    private(response, status)
    assert raced == [True]
    saved = store.get(case.id)
    if mutation in ('delete', 'expire'):
        assert saved is None and store.get_version(case.id) is None
        assert store.get_file(case.id, file['id']) is None
        assert store.purge_expired() == 0
    elif mutation == 'remove':
        assert saved.evidence == [] and saved.version == 3
    else:
        assert saved.version == 3
        assert confirmed_value(saved, 'evidence.doc_wall.title') == payload()['title']
        if mutation == 'fact':
            assert confirmed_value(saved, 'project.concurrent') == 'newer answer'
    if mutation not in ('delete', 'expire'):
        assert store.get_file(case.id, file['id']) == file_before


@pytest.mark.parametrize('method', ['post', 'delete'])
@pytest.mark.parametrize('state', ['missing', 'deleted', 'expired'])
def test_terminal_case_never_created_by_evidence(ledger, method, state):
    store, create, client = ledger
    if state == 'missing':
        case_id = 'case_synthetic_absent'
    else:
        case = create(created_at=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
                      if state == 'expired' else datetime.now(timezone.utc).isoformat())
        case_id = case.id
        if state == 'deleted':
            store.delete(case.id)
    response = post(client, case_id, payload()) if method == 'post' else delete(client, case_id, 'doc_wall', 1)
    private(response, 404)
    assert store.get(case_id) is None and store.get_version(case_id) is None


def test_two_actual_writers_one_snapshot_commit_exactly_one_whole_listing(ledger, monkeypatch):
    store, create, client = ledger
    case = create()
    snapshot = store.get_snapshot
    barrier = threading.Barrier(2)
    responses, errors = [], []

    def simultaneous(case_id):
        result = snapshot(case_id)
        if threading.current_thread().name.startswith('evidence-writer-'):
            barrier.wait(timeout=15)
        return result

    def write(slot):
        try:
            responses.append(post(client, case.id, payload(evidence_id=slot, title=slot, issuer=slot)))
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(store, 'get_snapshot', simultaneous)
    threads = [threading.Thread(target=write, args=(slot,), name=f'evidence-writer-{slot}')
               for slot in ('one', 'two')]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(25)
    assert not errors and not any(thread.is_alive() for thread in threads)
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json()['evidence']['id'] for response in responses if response.status_code == 200)
    saved = store.get(case.id)
    assert saved.version == 2 and [item.id for item in saved.evidence] == [winner]
    assert all(entry.field.startswith(f'evidence.{winner}.') for entry in saved.facts)
    assert confirmed_value(saved, f'evidence.{winner}.title') == winner
    assert confirmed_value(saved, f'evidence.{winner}.issuer') == winner


def test_legacy_unowned_file_claim_is_normalized_and_preserved_as_uncertain(ledger):
    store, create, client = ledger
    ghost = fact('evidence.legacy.file_ref', 'file_missing', 'file', 'file_missing')
    case = create(evidence=[EvidenceItem(id='legacy', description='Legacy listing', status='evidence_listed')],
                  facts=[ghost, fact('evidence.legacy.title', 'Legacy title')])
    # A normal snapshot must downgrade the claim; raw JSON byte identity is not promised.
    response = post(client, case.id, payload(evidence_id='new'))
    private(response, 200)
    acknowledged = Case.model_validate(response.json()['case'])
    preserved = next(entry for entry in acknowledged.facts if entry.id == ghost.id)
    assert preserved.source == ghost.source and preserved.value == ghost.value
    assert preserved.status == 'unconfirmed'
    assert next(item for item in acknowledged.evidence if item.id == 'legacy').kind == 'text'
    assert store.get(case.id) == acknowledged


def test_real_loopback_api_http_has_current_acknowledgment_and_privacy(ledger, monkeypatch):
    import httpx
    import uvicorn
    store, create, _ = ledger
    case = create()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    # The private runner permits only this own loopback port; provider sockets stay denied.
    monkeypatch.setenv('BATATIS_EVIDENCE_TEST_HTTP_PORT', str(port))
    server = uvicorn.Server(uvicorn.Config(create_app(store=store), log_level='error', lifespan='off'))
    errors = []

    def run():
        try:
            server.run(sockets=[listener])
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and not errors and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started and not errors
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=10) as http:
            response = post(http, case.id, payload())
            private(response, 200)
            assert response.json()['case_version'] == 2
            read = http.get(f'/api/cases/{case.id}')
            private(read, 200)
            assert read.json()['facts'] == response.json()['case']['facts']
            private(delete(http, case.id, 'doc_wall', 1), 409)
            removed = delete(http, case.id, 'doc_wall', 2)
            private(removed, 200)
            assert removed.json()['version'] == 3 and removed.json()['evidence'] == []
    finally:
        server.should_exit = True
        thread.join(10)
        listener.close()
    assert not thread.is_alive() and not errors
