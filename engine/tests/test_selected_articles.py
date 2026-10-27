"""An applicant's code-check list is durable before any benchmark is confirmed."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import json
import os
import secrets
import threading
import time

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.account_models import User
from engine.accounts import COOKIE, digest
from engine.codes import Codes
from engine.models import Case, Fact, Gap, Source
from engine.retention import reset_purge_clock
from engine.store import CaseStore
from engine.tests._db_skip import require_repo_db


@pytest.fixture(params=['sqlite', 'postgres'])
def context(request, tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '0')
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    reset_purge_clock()
    if request.param == 'postgres':
        url = os.environ.get('U3_SELECTION_TEST_DATABASE_URL', '')
        if 'batatis-u3-pg-' not in url:
            pytest.skip('U3_SELECTION_TEST_DATABASE_URL must identify an owned batatis-u3-pg-* cluster')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    else:
        store = CaseStore(tmp_path / 'selected-articles.sqlite')
    with TestClient(create_app(store=store)) as client:
        yield client, store
    reset_purge_clock()


def selection(provision='9.27.3.4.', answer=None, **changes):
    return dict(id=f'search-{provision}', provision=provision, answer=answer, pending=False) | changes


def save(client, case, articles):
    return client.put(f'/api/cases/{case.id}/selected-articles', json={
        'selected_articles': articles, 'expected_version': case.version,
    })


def test_unanswered_article_survives_opening_another_application_and_reopening(context):
    require_repo_db()
    client, store = context
    first = store.put(Case(title='SYNTHETIC first application'))
    second = store.put(Case(title='SYNTHETIC second application'))
    articles = [selection()]
    response = save(client, first, articles)
    assert response.status_code == 200, response.text
    assert response.json()['selected_articles'] == articles
    assert response.json()['provisions'] == []
    assert response.json()['section_c'] == []
    assert client.get(f'/api/cases/{second.id}').json()['selected_articles'] is None
    reopened = reopen(store)
    with TestClient(create_app(store=reopened)) as visit:
        saved = visit.get(f'/cases/{first.id}')
    assert saved.status_code == 200, saved.text
    assert saved.json()['selected_articles'] == articles
    assert reopened.get(first.id).provisions == []


def test_legacy_missing_selection_is_distinct_from_explicitly_cleared_list(context):
    client, store = context
    case = store.put(Case(title='SYNTHETIC legacy', provisions=['9.27.3.4.(1)']))
    with store.account_db() as db:
        if db.postgres:
            db.execute("UPDATE cases SET data=data-'selected_articles' WHERE id=?", (case.id,))
        else:
            db.execute("UPDATE cases SET json=json_remove(json, '$.selected_articles') WHERE id=?", (case.id,))
    legacy = client.get(f'/cases/{case.id}')
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()['selected_articles'] is None
    response = save(client, case, [])
    assert response.status_code == 200, response.text
    assert response.json()['selected_articles'] == []
    assert response.json()['provisions'] == case.provisions
    with store.account_db() as db:
        column = 'data' if db.postgres else 'json'
        payload = db.execute(f'SELECT {column} FROM cases WHERE id=?', (case.id,)).fetchone()[0]
        if isinstance(payload, str):
            payload = json.loads(payload)
    assert payload['selected_articles'] == []


def reopen(store):
    return CaseStore(store.path) if isinstance(store, CaseStore) else type(store)(store.url)


def fact():
    return Fact(field='project.description', value='SYNTHETIC applicant words', kind='pointed',
                status='confirmed', source=Source(type='user_text', ref='sent-description',
                                                quote='SYNTHETIC applicant words'))


def test_all_answers_and_pending_confirmation_survive_reopen_without_becoming_benchmarks(context):
    require_repo_db()
    client, store = context
    case = store.put(Case(title='SYNTHETIC mixed cards'))
    articles = [selection(pid, answer, pending=pending) for pid, answer, pending in [
        ('9.27.3.4.', None, False), ('9.25.2.2.(1)', 'yes', False),
        ('9.25.5.2.(1)(b)', 'no', False), ('9.27.3.2.(1)', 'not-sure', False),
        ('9.9.10.1.(1)', 'yes', True),
    ]]
    response = save(client, case, articles)
    assert response.status_code == 200, response.text
    loaded = reopen(store).get(case.id)
    assert [item.model_dump() for item in loaded.selected_articles] == articles
    assert loaded.provisions == loaded.section_c == loaded.facts == loaded.evidence == []
    assert loaded.export_blockers() == [], 'card state is not an applicant fact or professional evidence'
    assert loaded.version == case.version + 1


def test_removal_and_clear_replace_the_saved_snapshot(context):
    require_repo_db()
    client, store = context
    case = store.put(Case())
    first, second = selection(), selection('9.25.2.2.(1)', 'not-sure')
    assert save(client, case, [first, second]).status_code == 200
    assert save(client, store.get(case.id), [second]).status_code == 200
    assert [item.model_dump() for item in reopen(store).get(case.id).selected_articles] == [second]
    assert save(client, store.get(case.id), []).status_code == 200
    assert reopen(store).get(case.id).selected_articles == []


def test_canonical_ids_and_default_unanswered_state_preserve_stable_card_identity(context):
    require_repo_db()
    client, store = context
    case = store.put(Case())
    response = save(client, case, [{'id': 'search-original-id', 'provision': '9.25.2.2 (1)'}])
    assert response.status_code == 200, response.text
    assert response.json()['selected_articles'] == [selection('9.25.2.2.(1)', id='search-original-id')]


@pytest.mark.parametrize('articles', [
    [selection(answer=True)], [selection(answer='not_sure')], [selection(pending='false')],
    [selection(id=' ')], [selection(id=1)], [selection(provision='9.25.')],
    [selection(provision='not-an-article')], [selection(provision=None)],
    [selection(quote='invented code text')], [selection(benchmark=True)],
    [selection(), selection('9.27.3.4', id='other-card')],
    [selection(), selection('9.25.2.2.(1)', id='search-9.27.3.4.')],
    [selection()] * 501, None, {}, '9.27.3.4.',
])
def test_invalid_or_ambiguous_snapshot_is_422_without_any_mutation(context, articles):
    client, store = context
    case = store.put(Case(facts=[fact()]))
    response = save(client, case, articles)
    assert response.status_code == 422, response.text
    assert store.get(case.id) == case


@pytest.mark.parametrize('version', [None, 0, -1, True, 1.0, '1'])
def test_expected_version_is_required_positive_and_strict(context, version):
    client, store = context
    case = store.put(Case())
    response = client.put(f'/cases/{case.id}/selected-articles', json={
        'selected_articles': [], 'expected_version': version,
    })
    assert response.status_code == 422, response.text
    assert store.get(case.id) == case


@pytest.mark.parametrize('body', [{}, {'selected_articles': []}, {'expected_version': 1},
                                 {'selected_articles': [], 'expected_version': 1, 'provisions': []}])
def test_missing_or_extra_fields_are_rejected(context, body):
    client, store = context
    case = store.put(Case())
    response = client.put(f'/cases/{case.id}/selected-articles', json=body)
    assert response.status_code == 422, response.text
    assert store.get(case.id) == case


def test_unknown_division_b_provision_is_not_saved(context):
    require_repo_db()
    client, store = context
    case = store.put(Case())
    response = save(client, case, [selection(), selection('9.99.99.99.')])
    assert response.status_code == 404, response.text
    assert store.get(case.id) == case


def test_selection_does_not_rewrite_confirmed_references_or_other_application_material(context):
    require_repo_db()
    client, store = context
    from engine.section_c import section_c_rows
    codes = Codes()
    case = store.put(Case(title='SYNTHETIC manual title', title_is_manual=True, facts=[fact()],
                          provisions=['9.27.3.4.(1)'], section_c=section_c_rows(['9.27.3.4.(1)'], codes),
                          gaps=[Gap(section='D', field='risk', message='SYNTHETIC pending risk')]))
    before = case.model_dump(exclude={'version', 'updated_at', 'expires_at', 'selected_articles'})
    response = save(client, case, [selection('9.27.3.4.(1)', 'no'), selection('9.25.2.2.(1)', 'yes')])
    assert response.status_code == 200, response.text
    after = store.get(case.id)
    assert after.model_dump(exclude={'version', 'updated_at', 'expires_at', 'selected_articles'}) == before
    # A later legacy writer must keep the added field, including a fact or title save.
    added = store.add_fact(case.id, fact())
    assert added.selected_articles == after.selected_articles
    renamed = client.patch(f'/cases/{case.id}/title', json={'title': 'SYNTHETIC renamed'})
    assert renamed.status_code == 200, renamed.text
    assert store.get(case.id).selected_articles == after.selected_articles


def test_stale_selection_cannot_overwrite_new_answers(context):
    client, store = context
    case = store.put(Case())
    newer = store.add_fact(case.id, fact())
    response = save(client, case, [selection()])
    assert response.status_code == 409, response.text
    assert store.get(case.id) == newer


@pytest.fixture
def actors(context):
    _, store = context
    clients, users = {}, {}
    with ExitStack() as stack:
        app = create_app(store=store)
        for name, role, authority in [('owner', 'applicant', None), ('other', 'applicant', None),
                                      ('reviewer', 'reviewer', 'edmonton'), ('foreign', 'reviewer', 'calgary'),
                                      ('anonymous', None, None)]:
            client = stack.enter_context(TestClient(app, base_url='http://localhost'))
            clients[name] = client
            if role:
                user = User(email=secrets.token_hex(12) + '@example.test', name=name,
                            role=role, authority=authority, onboarded=True)
                assert store.create_user(user)
                users[name] = user
                token = secrets.token_urlsafe(32)
                store.save_session(digest(token), user.id, time.time() + 3600)
                client.cookies.set(COOKIE, token, domain='localhost.local')
        yield clients, users


@pytest.mark.parametrize('status', ['draft', 'returned', 'submitted', 'in_review', 'accepted', 'refused', 'withdrawn'])
@pytest.mark.parametrize('name', ['owner', 'other', 'reviewer', 'foreign', 'anonymous'])
def test_only_owner_can_edit_and_read_only_cases_stay_immutable(context, actors, status, name):
    _, store = context
    clients, users = actors
    editable_owner = name == 'owner' and status in {'draft', 'returned'}
    case = store.put(Case(owner_id=users['owner'].id, authority='edmonton', status=status,
                          selected_articles=None if editable_owner else [selection()]))
    client = clients[name]
    expected = 200 if editable_owner else 409 if name == 'owner' else 404
    if expected == 200:
        require_repo_db()
    before = store.get(case.id)
    response = save(client, before, [selection()])
    assert response.status_code == expected, (name, status, response.text)
    assert response.headers['cache-control'] == 'no-store'
    if expected == 200:
        assert response.json()['selected_articles'] == [selection()]
        assert response.json()['version'] == before.version + 1
    if expected != 200:
        assert store.get(case.id) == before
    if name in {'other', 'anonymous', 'foreign'}:
        read = client.get(f'/cases/{case.id}')
        assert read.status_code == 404
        assert case.id not in read.text and 'selected_articles' not in read.text


def test_list_preferences_are_unchanged_by_selection_save(context, actors):
    require_repo_db()
    _, store = context
    clients, users = actors
    case = store.put(Case(owner_id=users['owner'].id))
    original = store.patch_application_preferences(case.id, users['owner'], {'pinned': True, 'archived': True})
    response = save(clients['owner'], case, [selection()])
    assert response.status_code == 200, response.text
    assert store.list_application_preferences(users['owner'].id)[case.id] == original


def test_nul_card_id_is_422_and_preserves_the_previous_selection(context, actors):
    _, store = context
    clients, users = actors
    case = store.put(Case(owner_id=users['owner'].id, selected_articles=[selection()]))
    with TestClient(create_app(store=store), base_url='http://localhost', raise_server_exceptions=False) as client:
        client.cookies.update(clients['owner'].cookies)
        assert client.get(f'/cases/{case.id}').status_code == 200
        response = save(client, case, [selection(id='card\x00suffix')])
    assert response.status_code == 422, response.text
    assert store.get(case.id) == case


def test_edit_revocation_before_snapshot_wins_over_stale_version_even_with_reviewer_read_access(context, actors, monkeypatch):
    _, store = context
    clients, users = actors
    case = store.put(Case(owner_id=users['reviewer'].id, authority='edmonton'))
    get_snapshot = store.get_snapshot
    first = True

    def after_guard(case_id):
        nonlocal first
        if first and case_id == case.id:
            first = False
            # There is no public ownership-transfer route. Simulate the committed transfer
            # after the public edit guard; the old owner is now only an authorized reviewer.
            latest, version = get_snapshot(case_id)
            latest.owner_id = users['other'].id
            latest.status = 'submitted'
            store.put(latest, expected_version=version)
        return get_snapshot(case_id)

    monkeypatch.setattr(store, 'get_snapshot', after_guard)
    response = save(clients['reviewer'], case, [selection()])
    assert response.status_code == 404, response.text
    assert response.json()['detail'] == 'case not found'
    assert 'selected_articles' not in response.text and case.id not in response.text
    assert save(clients['reviewer'], case, [selection()]).status_code == 404
    assert clients['reviewer'].get(f'/cases/{case.id}').status_code == 200
    loaded = store.get(case.id)
    assert loaded.owner_id == users['other'].id and loaded.status == 'submitted'
    assert loaded.version == case.version + 1 and loaded.selected_articles is None


def test_two_simultaneous_selection_snapshots_have_one_winner(context, monkeypatch):
    require_repo_db()
    _, store = context
    case = store.put(Case())
    barrier, put = threading.Barrier(2), store.put

    def held(candidate, **kwargs):
        barrier.wait(timeout=10)
        return put(candidate, **kwargs)

    monkeypatch.setattr(store, 'put', held)
    app = create_app(store=store)

    def write(pid):
        with TestClient(app) as client:
            return save(client, case, [selection(pid)])

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(write, ['9.27.3.4.', '9.25.2.2.(1)']))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    assert [item.model_dump() for item in store.get(case.id).selected_articles] == winner.json()['selected_articles']
    assert store.get(case.id).version == case.version + 1


@pytest.mark.parametrize('change', ['fact', 'delete', 'submit', 'transfer_owner'])
def test_late_write_or_revocation_cannot_be_overwritten_or_resurrected(context, actors, monkeypatch, change):
    require_repo_db()
    _, store = context
    clients, users = actors
    case = store.put(Case(owner_id=users['owner'].id))
    put = store.put

    def interleave(candidate, **kwargs):
        if change == 'delete':
            assert store.delete(case.id)
        elif change == 'fact':
            store.add_fact(case.id, fact())
        else:
            latest = store.get(case.id)
            if change == 'submit':
                latest.status = 'submitted'
            else:
                latest.owner_id = users['other'].id
            put(latest, expected_version=latest.version)
        return put(candidate, **kwargs)

    monkeypatch.setattr(store, 'put', interleave)
    response = save(clients['owner'], case, [selection()])
    expected = 404 if change in {'delete', 'transfer_owner'} else 409
    assert response.status_code == expected, response.text
    loaded = store.get(case.id)
    if change == 'delete':
        assert loaded is None
    else:
        assert loaded.selected_articles is None
        assert loaded.version == case.version + 1
        if change == 'fact':
            assert loaded.facts[0].value == 'SYNTHETIC applicant words'
        elif change == 'submit':
            assert loaded.status == 'submitted'
        else:
            assert loaded.owner_id == users['other'].id


def test_expired_case_cannot_be_recreated_by_a_selection_save(context):
    client, store = context
    case = store.put(Case(created_at=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat()))
    from engine.tests.test_retention import _set_last_activity
    _set_last_activity(store, case.id, (datetime.now(timezone.utc) - timedelta(days=8)).isoformat())
    response = save(client, case, [selection()])
    assert response.status_code == 404, response.text
    assert store.get(case.id) is None


def test_clearing_needs_no_corpus_and_unavailable_corpus_does_not_erase_selection(context, monkeypatch):
    _, store = context
    case = store.put(Case())
    import engine.api as api
    from engine.codes import CodeDbMissing

    def unavailable():
        raise CodeDbMissing()

    monkeypatch.setattr(api, 'Codes', unavailable)
    with TestClient(create_app(store=store)) as client:
        response = save(client, case, [selection()])
        assert response.status_code == 503, response.text
        assert store.get(case.id) == case
        cleared = save(client, case, [])
        assert cleared.status_code == 200, cleared.text
        assert store.get(case.id).selected_articles == []


def test_public_contract_distinguishes_legacy_empty_and_unanswered_state():
    from engine.schema_export import schema
    definitions = schema()['$defs']
    case_field = definitions['Case']['properties']['selected_articles']
    assert case_field['default'] is None
    assert {'type': 'null'} in case_field['anyOf']
    assert 'selected_articles' in definitions['Case']['required']
    response = definitions['SelectedArticle']
    assert set(response['required']) == {'id', 'provision', 'answer', 'pending'}
    request = definitions['SelectedArticlesRequest']
    assert request['additionalProperties'] is False
    assert set(request['required']) == {'selected_articles', 'expected_version'}
