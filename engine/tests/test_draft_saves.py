"""Actual HTTP/SQL regressions for batched answers and unconfirmed applicant editors."""
from concurrent.futures import ThreadPoolExecutor
import os

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, Fact, Source
from engine.store import CaseStore
from engine.tests.test_review import owned, scene


@pytest.fixture(params=['sqlite', 'postgres'])
def store(request, tmp_path):
    if request.param == 'sqlite':
        backend = CaseStore(tmp_path / 'draft.sqlite')
    else:
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set')
        from engine.store_postgres import PostgresCaseStore
        backend = PostgresCaseStore(url)
    created = []
    yield backend, created
    for case_id in created:
        backend.delete(case_id)


def answer(i, value=None):
    text = value if value is not None else f'SYNTHETIC answer {i}'
    return Fact(id=f'answer-{i}', field=f'applicant.answer_{i}', value=text, kind='pointed',
                status='confirmed', source=Source(type='user_text', ref='Applicant', quote=text)).model_dump(mode='json')


def test_one_save_preserves_every_answer_and_restores_editors_after_fresh_client(store):
    backend, created = store
    case = backend.put(Case(facts=[Fact.model_validate(answer(0)), Fact.model_validate(answer(99))]))
    created.append(case.id)
    client = TestClient(create_app(backend))
    draft = {'role': 'designer', 'question_text': {'owner': {'base': '', 'value': 'Unfinished applicant name'}},
             'choices': {'not_sure': 'yes'}, 'skipped': ['permit'], 'seen': ['rationale'],
             'authority_unsure': True, 'packages': {'standing-variance': 'no'}, 'rule_unsure': ['storeys'],
             'evidence_drafts': {'document': {'document': 'Draft report title', 'note': 'Not confirmed'}}}
    response = client.patch(f'/cases/{case.id}/draft', json={
        'expected_version': case.version, 'facts': [answer(i) for i in range(10)], 'applicant_draft': draft,
    })
    assert response.status_code == 200, response.text
    assert response.json()['version'] == case.version + 1
    fresh = TestClient(create_app(backend)).get(f'/cases/{case.id}').json()
    assert len(fresh['facts']) == 11
    assert [fact['id'] for fact in fresh['facts']] == ['answer-0', 'answer-99', *[f'answer-{i}' for i in range(1, 10)]]
    assert fresh['applicant_draft']['question_text']['owner']['value'] == 'Unfinished applicant name'
    assert fresh['applicant_draft']['skipped'] == ['permit']
    assert fresh['applicant_draft']['packages'] == {'standing-variance': 'no'}
    assert fresh['applicant_draft']['evidence_drafts']['document']['note'] == 'Not confirmed'
    assert not fresh['provisions'] and not fresh['evidence']
    assert response.headers['cache-control'] == 'no-store'


def test_conflicting_devices_reject_entire_batch_and_never_erase_acknowledged_answers(store):
    backend, created = store
    case = backend.put(Case())
    created.append(case.id)
    client = TestClient(create_app(backend))

    def save(value):
        return client.patch(f'/cases/{case.id}/draft', json={
            'expected_version': case.version, 'facts': [answer(1, value), answer(2, value)],
        })

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(save, ['Device A', 'Device B']))
    assert sorted(r.status_code for r in responses) == [200, 409]
    winning = next(r.json() for r in responses if r.status_code == 200)
    assert backend.get(case.id).facts == Case.model_validate(winning).facts
    assert len({fact.value for fact in backend.get(case.id).facts}) == 1


def test_noop_save_does_not_advance_version_and_draft_clear_is_explicit(store):
    backend, created = store
    case = backend.put(Case(facts=[Fact.model_validate(answer(1))]))
    created.append(case.id)
    client = TestClient(create_app(backend))
    path = f'/cases/{case.id}/draft'
    same = client.patch(path, json={'expected_version': case.version, 'facts': [answer(1)]})
    assert same.status_code == 200 and same.json()['version'] == case.version
    saved = client.patch(path, json={'expected_version': case.version, 'applicant_draft': {'skipped': ['permit']}}).json()
    kept = client.patch(path, json={'expected_version': saved['version'], 'facts': []}).json()
    assert kept['applicant_draft']['skipped'] == ['permit']
    cleared = client.patch(path, json={'expected_version': kept['version'], 'applicant_draft': None}).json()
    assert cleared['applicant_draft'] is None


@pytest.mark.parametrize('payload', [
    {'status': 'accepted'}, {'provisions': ['9.1.1.1.']},
    {'applicant_draft': {'professional_approved': True}},
    {'facts': [{**answer(1), 'source': {'type': 'officer', 'ref': 'not an officer'}}]},
    {'facts': [{**answer(1), 'field': 'evidence.secret.file_ref', 'value': 'other-case-file',
                'source': {'type': 'file', 'ref': 'other-case-file'}}]},
])
def test_batch_cannot_assert_authority_or_attach_an_unowned_file(store, payload):
    backend, created = store
    case = backend.put(Case())
    created.append(case.id)
    response = TestClient(create_app(backend)).patch(f'/cases/{case.id}/draft',
        json={'expected_version': case.version, **payload})
    assert response.status_code == 422, response.text
    assert backend.get(case.id).version == case.version


def test_drafts_keep_the_owner_and_submitted_record_access_boundaries(scene):
    backend, clients, _ = scene
    case = owned(scene, status='draft')
    path = f'/cases/{case.id}/draft'
    patch = {'expected_version': case.version, 'applicant_draft': {'question_text': {'owner': {'base': '', 'value': 'Private draft'}}}}
    assert clients['other'].patch(path, json=patch).status_code == 404
    assert clients['reviewer'].patch(path, json=patch).status_code == 404
    assert clients['owner'].patch(path, json=patch).status_code == 200
    sent = owned(scene, status='submitted')
    assert clients['owner'].patch(f'/cases/{sent.id}/draft', json={**patch, 'expected_version': sent.version}).status_code == 409
    assert backend.get(sent.id).applicant_draft is None


def test_unconfirmed_editors_remain_private_from_officers_without_erasing_storage(scene):
    from engine.models_draft import ApplicantDraft, DraftText
    backend, clients, _ = scene
    case = owned(scene, status='returned')
    case.applicant_draft = ApplicantDraft(question_text={'owner': DraftText(base='', value='Unsubmitted private note')})
    case = backend.put(case, expected_version=case.version)
    assert clients['owner'].get(f'/cases/{case.id}').json()['applicant_draft']['question_text']['owner']['value'] == 'Unsubmitted private note'
    response = clients['reviewer'].get(f'/cases/{case.id}')
    assert response.status_code == 200
    assert response.json()['applicant_draft'] is None
    assert 'Unsubmitted private note' not in response.text
    assert backend.get(case.id).applicant_draft.question_text['owner'].value == 'Unsubmitted private note'
