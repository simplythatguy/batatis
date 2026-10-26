"""Application naming through the public API and real isolated storage adapters."""
import os
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.account_models import Decision, MessageAuthor, StoredMessage
from engine.identify.title import short_title
from engine import llm_gate
from engine.models import Case, Fact, Source
from engine.retention import reset_purge_clock
from engine.store import CaseStore
from engine.tests._db_skip import require_repo_db


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1000')
    monkeypatch.setenv('BATATIS_AUTH_RATE_LIMIT', '1000')
    monkeypatch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
    llm_gate.reset_for_tests()
    reset_purge_clock()
    yield
    reset_purge_clock()
    llm_gate.reset_for_tests()


@pytest.fixture(params=['sqlite', 'postgres'])
def context(request, tmp_path):
    if request.param == 'postgres':
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set; real isolated Postgres required')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    else:
        store = CaseStore(tmp_path / 'titles.sqlite')
    with TestClient(create_app(store=store)) as client:
        yield client, store


def rename(client, case_id, title, prefix='/api'):
    return client.patch(f'{prefix}/cases/{case_id}/title', json={'title': title})


def test_rename_normalizes_unicode_persists_and_is_idempotent(context):
    client, store = context
    original = client.post('/api/cases', json={'title': 'Original'}).json()
    response = rename(client, original['id'], '  École\t北側\n 🏗️  ')
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['id'] == original['id']
    assert saved['title'] == 'École 北側 🏗️'
    assert saved['title_is_manual'] is True
    assert saved['version'] == original['version'] + 1
    assert saved['created_at'] == original['created_at']
    assert client.get(f'/api/cases/{original["id"]}').json() == saved
    replay = rename(client, original['id'], '\nÉcole 北側 🏗️\t', prefix='')
    assert replay.status_code == 200, replay.text
    assert replay.json() == saved
    assert store.get(original['id']).title == 'École 北側 🏗️'
    if isinstance(store, CaseStore):
        reopened = CaseStore(store.path)
    else:
        reopened = type(store)(store.url)
    assert reopened.get(original['id']) == Case.model_validate(saved)


def fact(field, value, **changes):
    return Fact(**dict(field=field, value=value, kind='pointed', status='confirmed',
                       source=Source(type='user_text', ref='sent-applicant-message', quote=str(value))) | changes)


@pytest.mark.parametrize('collision', ['generated', 'first_sentence'])
def test_manual_rename_wins_even_when_identical_to_automatic_or_description(context, collision):
    require_repo_db()
    client, store = context
    prose = 'A house in Edmonton needs an egress window. We want a smaller opening.'
    case = store.put(Case(facts=[fact('project.description', prose)]))
    first = client.post(f'/cases/{case.id}/identify', json={})
    assert first.status_code == 200, first.text
    custom = store.get(case.id).title if collision == 'generated' else 'A house in Edmonton needs an egress window.'
    changed = rename(client, case.id, custom)
    assert changed.status_code == 200, changed.text
    assert changed.json()['title_is_manual'] is True
    stored_identification = client.get(f'/cases/{case.id}/identify')
    assert stored_identification.status_code == 200, stored_identification.text
    assert stored_identification.json()['title'] is None
    accepted = client.post(f'/cases/{case.id}/intake', json={
        'text': custom + ' We now propose exterior sheathing instead.', 'model': False,
    })
    assert accepted.status_code == 200, accepted.text
    assert store.get(case.id).title == custom
    identified = client.post(f'/cases/{case.id}/identify', json={})
    assert identified.status_code == 200, identified.text
    assert identified.json()['title'] is None
    saved = store.get(case.id)
    assert saved.title == custom and saved.title_is_manual is True


@pytest.mark.parametrize(('prose', 'expected'), [
    ('We propose exterior sheathing for a house in Edmonton instead of the usual panel, under 9.27.3.4.(1).',
     'Exterior sheathing'),
    ('A bungalow in Calgary needs an egress window with a different opening.', 'Egress window'),
    ('A retail unit in Red Deer needs a narrower exit stair.', 'Exit stair'),
])
def test_sent_intake_gets_a_short_subject_name_without_city_code_or_sentence(context, prose, expected):
    client, store = context
    case = client.post('/cases', json={}).json()
    sent = client.post(f'/cases/{case["id"]}/intake', json={'text': prose, 'model': False})
    assert sent.status_code == 200, sent.text
    saved = store.get(case['id'])
    assert saved.title == expected
    assert saved.title_is_manual is False


@pytest.mark.parametrize('body', [
    {}, {'title': None}, {'title': ''}, {'title': ' \n\t\u2003 '}, {'title': 'é' * 501},
    {'title': 42}, {'title': False}, {'title': []}, {'title': {}},
    {'title': 'Valid', 'title_is_manual': False}, {'title': 'Valid', 'status': 'draft'},
])
def test_invalid_names_and_extra_fields_are_422_without_mutation(context, body):
    client, store = context
    case = store.put(Case(title='Keep this name'))
    before = client.get(f'/cases/{case.id}').json()
    response = client.patch(f'/api/cases/{case.id}/title', json=body)
    assert response.status_code == 422, response.text
    assert client.get(f'/cases/{case.id}').json() == before


@pytest.mark.parametrize('content', [None, 'null', '[]', '{"title":'])
def test_missing_null_or_malformed_body_is_422(context, content):
    client, store = context
    case = store.put(Case(title='Keep this name'))
    before = store.get(case.id)
    response = client.patch(f'/cases/{case.id}/title', content=content,
                            headers={'content-type': 'application/json'})
    assert response.status_code == 422, response.text
    assert store.get(case.id) == before


def test_500_character_custom_name_is_saved_exactly_without_clipping(context):
    client, store = context
    case = store.put(Case())
    custom = '界' * 500
    response = rename(client, case.id, custom)
    assert response.status_code == 200, response.text
    assert response.json()['title'] == store.get(case.id).title == custom


def test_two_cases_keep_separate_names_facts_and_creation_times(context):
    client, store = context
    a = store.put(Case(title='First', facts=[fact('project.description', 'A first project')]))
    b = store.put(Case(title='Second', facts=[fact('project.description', 'A second project')]))
    before = client.get(f'/cases/{b.id}').json()
    result = rename(client, a.id, 'Renamed first')
    assert result.status_code == 200, result.text
    assert result.json()['facts'] == [f.model_dump() for f in a.facts]
    assert result.json()['created_at'] == a.created_at
    assert client.get(f'/cases/{b.id}').json() == before


def test_identical_manual_rename_returns_latest_facts_without_an_extra_write(context):
    client, store = context
    case = store.put(Case())
    assert rename(client, case.id, 'My name').status_code == 200
    newer = client.post(f'/cases/{case.id}/facts', json=fact('project.answer', 'A later answer').model_dump())
    assert newer.status_code == 200, newer.text
    replay = rename(client, case.id, '  My\nname  ')
    assert replay.status_code == 200, replay.text
    assert replay.json() == newer.json()


@pytest.fixture
def actors(context):
    from engine.tests.test_accounts import onboard, signup
    _, store = context
    with ExitStack() as stack:
        app = create_app(store=store)
        clients, users = {}, {}
        for name, role, authority in [('owner', 'applicant', 'edmonton'), ('other', 'applicant', 'edmonton'),
                                      ('reviewer', 'reviewer', 'edmonton'), ('foreign', 'reviewer', 'calgary'),
                                      ('anonymous', None, None)]:
            client = stack.enter_context(TestClient(app, base_url='http://localhost'))
            clients[name] = client
            if role:
                assert signup(client, f'{name}-{uuid.uuid4().hex}@example.test', name.title()).status_code == 201
                users[name] = onboard(client, role, authority)
        yield clients, users


@pytest.mark.parametrize('status', ['draft', 'returned', 'submitted', 'in_review', 'accepted', 'refused', 'withdrawn'])
def test_rename_uses_existing_owner_reviewer_anonymous_and_lifecycle_policy(context, actors, status):
    _, store = context
    clients, users = actors
    case = store.put(Case(title='Application', owner_id=users['owner']['id'], authority='edmonton', status=status))
    for name, client in clients.items():
        before = store.get(case.id)
        allowed = name == 'owner' and status in {'draft', 'returned'}
        response = rename(client, case.id, f'Renamed by {name}')
        expected = 200 if allowed else 409 if name == 'owner' else 404
        assert response.status_code == expected, (name, status, response.text)
        if allowed:
            assert response.json()['title_is_manual'] is True
        else:
            assert store.get(case.id) == before


def test_legacy_anonymous_draft_remains_editable(context):
    client, store = context
    case = store.put(Case(title='Legacy anonymous'))
    response = rename(client, case.id, 'Anonymous draft')
    assert response.status_code == 200, response.text
    assert store.get(case.id).title_is_manual is True


@pytest.mark.parametrize(('legacy_title', 'description'), [
    ('My special project', 'A house in Edmonton with an egress window.'),
    ('Variance application', 'A house in Edmonton with an egress window.'),
    ('北側の増築', 'A retail unit in Calgary.'),
])
def test_old_serialized_custom_titles_keep_precedence_on_open_intake_and_identify(context, legacy_title, description):
    require_repo_db()
    client, store = context
    # Load a payload that predates the marker rather than using an opt-in manual flag.
    payload = Case(title=legacy_title, facts=[fact('project.description', description)]).model_dump(exclude={'title_is_manual'})
    case = store.put(Case.model_validate(payload))
    if isinstance(store, CaseStore):
        with closing(store._connect()) as con, con:
            con.execute("UPDATE cases SET json=json_remove(json, '$.title_is_manual') WHERE id=?", (case.id,))
    else:
        with store._conn() as con:
            con.execute("UPDATE cases SET data=data-'title_is_manual' WHERE id=%s", (case.id,))
    version = case.version
    opened = client.get(f'/cases/{case.id}')
    assert opened.status_code == 200 and opened.json()['title'] == legacy_title
    assert opened.json()['version'] == version
    intake = client.post(f'/cases/{case.id}/intake', json={'text': description, 'model': False})
    assert intake.status_code == 200, intake.text
    identified = client.post(f'/cases/{case.id}/identify', json={})
    assert identified.status_code == 200, identified.text
    assert identified.json()['title'] is None
    assert store.get(case.id).title == legacy_title
    assert store.get(case.id).title_is_manual is False


@pytest.mark.parametrize('clip', [False, True])
def test_legacy_sentence_seed_can_be_replaced_without_changing_applicant_words(context, clip):
    require_repo_db()
    client, store = context
    prose = ('A house in Edmonton needs an egress window with a different opening and a project-specific design. '
             'These are the applicant’s exact words.')
    sentence = prose.split('. ')[0] + '.'
    title = sentence[:69] + '…' if clip else sentence
    case = store.put(Case(title=title, facts=[fact('project.description', prose)]))
    response = client.post(f'/cases/{case.id}/identify', json={})
    assert response.status_code == 200, response.text
    saved = store.get(case.id)
    assert saved.title == 'Egress window'
    assert saved.facts == case.facts


def test_greetings_and_unaccepted_model_suggestions_cannot_invent_a_subject(context):
    client, store = context
    case = store.put(Case(facts=[
        fact('alternative_description', 'Use a fire separation', status='unconfirmed', kind='proposed'),
        fact('occupancy', 'industrial', status='unconfirmed'),
        fact('building.type', 'hotel', status='unconfirmed', kind='proposed'),
    ]))
    sent = client.post(f'/cases/{case.id}/intake', json={'text': 'Hello, can you help me?', 'model': False})
    assert sent.status_code == 200, sent.text
    assert store.get(case.id).title is None
    # A code result, even an offered or committed topic, is not applicant subject input.
    result = {'articles': [{'title': 'Fire separation', 'provision': '9.10.9.1.', 'status': 'committed'}]}
    assert short_title('Hello', case.facts, result) == 'Variance application'
    meaningful = client.post(f'/cases/{case.id}/intake', json={'text': 'We propose exterior sheathing.', 'model': False})
    assert meaningful.status_code == 200, meaningful.text
    assert store.get(case.id).title == 'Exterior sheathing'


@pytest.mark.parametrize('streaming', [False, True])
def test_unaccepted_saved_description_is_not_treated_as_explicit_identify_naming_input(context, streaming):
    require_repo_db()
    client, store = context
    case = store.put(Case(facts=[fact('project.description', 'An industrial warehouse needs firestopping.',
                                     kind='proposed', status='unconfirmed')]))
    result = client.post(f'/cases/{case.id}/identify', json={},
                         headers={'accept': 'text/event-stream'} if streaming else {})
    assert result.status_code == 200, result.text
    if streaming:
        done = next(event for event in result.text.split('\n\n') if event.startswith('event: done\n'))
        assert json.loads(done.split('data: ', 1)[1])['title'] == 'Variance application'
    else:
        assert result.json()['title'] == 'Variance application'
    assert store.get(case.id).title == 'Variance application'


def test_file_only_intake_does_not_name_from_an_unaccepted_saved_description(context):
    client, store = context
    case = store.put(Case(facts=[fact('project.description', 'An industrial warehouse needs firestopping.',
                                     kind='proposed', status='unconfirmed')]))
    file = store.put_file(case.id, 'SYNTHETIC unreadable.pdf', b'%PDF-1.4\nSYNTHETIC unreadable file')
    result = client.post(f'/cases/{case.id}/intake', json={'file_ids': [file['id']], 'model': False})
    assert result.status_code == 200, result.text
    assert store.get(case.id).title is None


def test_confirmed_applicant_facts_can_supply_subject_without_using_evidence_metadata():
    facts = [fact('alternative_description', 'A different egress window'),
             fact('evidence.report.title', 'Fire separation test report')]
    assert short_title('', facts, None) == 'Egress window'
    assert short_title('', [facts[1]], None) == 'Variance application'
    assert short_title('Please help', [fact('occupancy', 'mercantile')], None) == 'Mercantile'


@pytest.mark.parametrize('status', ['candidate', 'fallback', 'committed', 'choice'])
def test_code_result_status_does_not_turn_a_suggested_topic_into_project_identity(status):
    result = {'articles': [{'provision': '9.9.10.1.(2)', 'title': 'A different topic', 'status': status}]}
    assert short_title('A house in Red Deer with an egress window', [], result) == 'Egress window'
    assert short_title('Please help me', [], result) == 'Variance application'


def test_rename_keeps_the_latest_concurrent_record_including_decision_messages_and_provenance(context, monkeypatch):
    client, store = context
    case = store.put(Case(title='Before', facts=[fact('project.description', 'A house')]))
    original = store.rename_title
    committed = []

    def after_preflight(case_id, title):
        # A separate writer commits after HTTP authorization and before rename takes its lock.
        current = store.get(case_id)
        current.facts.append(fact('project.newer', 'A saved applicant answer'))
        current.messages.append(StoredMessage(author=MessageAuthor(id='officer', name='Officer', role='reviewer'),
                                              body='Existing administrative notice', read_by=['officer']))
        current.decision = Decision(outcome='return', by_id='officer', by_name='Officer', message='Need documents')
        committed.append(store.put(current, expected_version=current.version))
        return original(case_id, title)

    monkeypatch.setattr(store, 'rename_title', after_preflight)
    result = rename(client, case.id, 'Latest title')
    assert result.status_code == 200, result.text
    saved = Case.model_validate(result.json())
    excluded = {'title', 'title_is_manual', 'updated_at', 'expires_at', 'version'}
    assert saved.model_dump(exclude=excluded) == committed[0].model_dump(exclude=excluded)
    assert datetime.fromisoformat(saved.expires_at) > datetime.fromisoformat(committed[0].expires_at)
    assert saved.version == committed[0].version + 1


def test_fact_and_rename_can_commit_together_without_lost_updates(context):
    client, store = context
    case = store.put(Case(title='Before'))
    barrier = threading.Barrier(2)

    def name():
        barrier.wait(timeout=10)
        return rename(client, case.id, 'Concurrent title')

    def answer():
        barrier.wait(timeout=10)
        return client.post(f'/cases/{case.id}/facts', json=fact('project.answer', 'Keep my answer').model_dump())

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = [workers.submit(name), workers.submit(answer)]
        responses = [future.result(timeout=20) for future in results]
    assert [response.status_code for response in responses] == [200, 200]
    saved = store.get(case.id)
    assert saved.title == 'Concurrent title' and saved.title_is_manual is True
    assert [row.value for row in saved.facts] == ['Keep my answer']
    assert saved.version == case.version + 2


@pytest.mark.parametrize('same_title', [False, True])
def test_lifecycle_is_reauthorized_inside_store_even_for_idempotent_rename(context, actors, monkeypatch, same_title):
    _, store = context
    clients, users = actors
    case = store.put(Case(title='Manual name', owner_id=users['owner']['id'], authority='edmonton'))
    if same_title:
        assert rename(clients['owner'], case.id, 'Manual name').status_code == 200
    original = store.rename_title

    def submit_before_lock(case_id, title):
        def submit():
            current = store.get(case_id)
            current.status = 'submitted'
            store.put(current, expected_version=current.version)
        with ThreadPoolExecutor(max_workers=1) as writer:
            writer.submit(submit).result(timeout=10)
        return original(case_id, title)

    monkeypatch.setattr(store, 'rename_title', submit_before_lock)
    result = rename(clients['owner'], case.id, 'Manual name' if same_title else 'Other name')
    assert result.status_code == 409, result.text
    saved = store.get(case.id)
    assert saved.title == 'Manual name' and saved.status == 'submitted'
    assert saved.title_is_manual is same_title


def test_owner_is_reauthorized_inside_mutation(context, actors, monkeypatch):
    _, store = context
    clients, users = actors
    case = store.put(Case(title='Keep', owner_id=users['owner']['id'], authority='edmonton'))
    original = store.rename_title

    def transfer_before_lock(case_id, title):
        def transfer():
            current = store.get(case_id)
            current.owner_id = users['other']['id']
            store.put(current, expected_version=current.version)
        with ThreadPoolExecutor(max_workers=1) as writer:
            writer.submit(transfer).result(timeout=10)
        return original(case_id, title)

    monkeypatch.setattr(store, 'rename_title', transfer_before_lock)
    response = rename(clients['owner'], case.id, 'Must not save')
    assert response.status_code == 404, response.text
    assert store.get(case.id).title == 'Keep'
    assert store.get(case.id).title_is_manual is False


@pytest.mark.parametrize('stage', ['identify', 'intake'])
def test_late_automatic_run_cannot_undo_a_rename_or_overwrite_newer_facts(context, monkeypatch, stage):
    if stage == 'identify':
        require_repo_db()
    client, store = context
    case = store.put(Case(facts=[fact('project.description', 'A house with an egress window.')]))
    entered, release = threading.Event(), threading.Event()
    if stage == 'identify':
        from engine import routes_identify as module
        attr = 'identify_run'
        body = {}
    else:
        from engine.intake import service as module
        attr = 'run'
        body = {'text': 'We propose exterior sheathing.', 'model': False}
    original = getattr(module, attr)

    def delayed(*args, **kwargs):
        result = original(*args, **kwargs)
        entered.set()
        assert release.wait(timeout=10)
        return result

    monkeypatch.setattr(module, attr, delayed)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(client.post, f'/cases/{case.id}/{stage}', json=body)
        try:
            assert entered.wait(timeout=10)
            changed = rename(client, case.id, 'Chosen name')
            assert changed.status_code == 200, changed.text
            answered = client.post(f'/cases/{case.id}/facts', json=fact('project.newer', 'Keep').model_dump())
            assert answered.status_code == 200, answered.text
        finally:
            release.set()
        late = future.result(timeout=15)
    assert late.status_code == 409, late.text
    saved = store.get(case.id)
    assert saved.title == 'Chosen name' and saved.title_is_manual is True
    assert saved.facts[-1].field == 'project.newer'
    assert saved.identify is None and saved.intake is None


@pytest.mark.parametrize('disappearance', ['deleted', 'expired'])
def test_deleted_or_expired_case_is_never_recreated_by_rename(context, monkeypatch, disappearance):
    client, store = context
    case = store.put(Case(title='Gone'))
    original = store.rename_title

    def disappear_before_lock(case_id, title):
        if disappearance == 'deleted':
            assert store.delete(case_id)
        else:
            from engine.tests.test_retention import _set_last_activity
            _set_last_activity(store, case_id, (datetime.now(timezone.utc) - timedelta(days=8)).isoformat())
        return original(case_id, title)

    monkeypatch.setattr(store, 'rename_title', disappear_before_lock)
    response = rename(client, case.id, 'Must not resurrect')
    assert response.status_code == 404, response.text
    assert store.get(case.id) is None


def test_unknown_case_is_404(context):
    client, _ = context
    response = rename(client, 'case_missing_' + uuid.uuid4().hex, 'A name')
    assert response.status_code == 404, response.text


def test_rejected_database_write_is_not_reported_as_saved(context):
    _, store = context
    case = store.put(Case(title='Keep before failure'))
    if isinstance(store, CaseStore):
        with closing(store._connect()) as con, con:
            con.execute("CREATE TRIGGER reject_title BEFORE UPDATE ON cases "
                        "WHEN json_extract(NEW.json, '$.title') = 'TEST rejected title' "
                        "BEGIN SELECT RAISE(ABORT, 'TEST failure'); END")
    else:
        with store._conn() as con:
            con.execute("ALTER TABLE cases ADD CONSTRAINT reject_title CHECK ((data->>'title') <> 'TEST rejected title')")
    try:
        with TestClient(create_app(store=store), raise_server_exceptions=False) as client:
            response = rename(client, case.id, 'TEST rejected title')
        assert response.status_code == 500, response.text
        assert store.get(case.id) == case
    finally:
        if isinstance(store, CaseStore):
            with closing(store._connect()) as con, con:
                con.execute('DROP TRIGGER reject_title')
        else:
            with store._conn() as con:
                con.execute('ALTER TABLE cases DROP CONSTRAINT reject_title')
