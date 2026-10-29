"""Real-corpus HTTP regressions, not an expert applicability benchmark."""
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case, Fact, Source
from engine.store import CaseStore


def ledger_b(result):
    """Division B rules in the requirement ledger. A requirement run stores no article cards (compact.py)."""
    return [r['provision_id'] for r in result['requirements'] if r['division'] == 'B']


def input_fact(field, value):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='applicant'))


@pytest.fixture
def scene(tmp_path, monkeypatch):
    for name in ('BATATIS_IDENTIFY_CONFIG', 'BATATIS_IDENTIFY_SCREEN', 'BATATIS_IDENTIFY_RERANK',
                 'BATATIS_IDENTIFY_VERIFIER', 'BATATIS_PROVIDER', 'BATATIS_LIVE', 'VERCEL'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '10000')
    from engine import llm_gate
    from engine.identify import pipeline
    llm_gate.reset_for_tests()
    monkeypatch.setattr(pipeline, 'default_transports', lambda *a, **k: pytest.fail('provider construction'))
    store = CaseStore(tmp_path / 'cases.sqlite')
    with TestClient(create_app(store=store, codes=Codes()), base_url='http://localhost') as client:
        yield client, store
    llm_gate.reset_for_tests()


def test_exact_reference_identification_is_local_and_has_no_hidden_top_ten(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.')]))
    response = client.post(f'/cases/{case.id}/identify', json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['articles'] == []
    assert ledger_b(result)[0] == '9.10.15.5.'
    assert result['input_sha256'] and not result['stale']
    assert sum(stage['requests'] for stage in result['trace']['stages']) == 0
    assert result['trace']['usd'] == 0
    assert store.get(case.id).provisions == []


def test_fact_update_invalidates_even_when_description_is_identical(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', 'Exterior wall near a property line.'),
                               input_fact('storeys', 2)]))
    first = client.post(f'/cases/{case.id}/identify', json={}).json()
    store.add_fact(case.id, input_fact('storeys', 8))
    stored = client.get(f'/cases/{case.id}/identify').json()
    assert stored['stale']
    rerun = client.post(f'/cases/{case.id}/identify', json={}).json()
    assert rerun['input_sha256'] != first['input_sha256'] and not rerun['stale']


def test_readable_plans_alone_run_identification_during_intake(scene):
    client, store = scene
    case = store.put(Case())
    file = store.put_file(case.id, 'plans.txt', b'Exterior wall: see article 9.10.15.5.', 'text/plain')
    response = client.post(f'/cases/{case.id}/intake', json={'file_ids': [file['id']], 'model': False})
    assert response.status_code == 200, response.text
    result = client.get(f'/cases/{case.id}/identify').json()
    assert result['input_sha256'] and not result['stale']
    assert '9.10.15.5.' in ledger_b(result)


def test_new_attachment_marks_previous_result_stale_without_a_fact_write(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.')]))
    first = client.post(f'/cases/{case.id}/identify', json={}).json()
    store.put_file(case.id, 'new-plan.txt', b'Building height: eight storeys.', 'text/plain')
    result = client.get(f'/cases/{case.id}/identify').json()
    assert result['stale'] and result['input_sha256'] == first['input_sha256']


def test_identify_accepts_long_prose_without_a_provider(scene):
    client, store = scene
    case = store.put(Case())
    response = client.post(f'/cases/{case.id}/identify', json={'prose': ('description ' * 2500) + '9.10.15.5.'})
    assert response.status_code == 200, response.text
    assert '9.10.15.5.' in ledger_b(response.json())


def test_supporting_application_scope_survives_no_departure_and_a_rerun(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.')]))
    first = client.post(f'/cases/{case.id}/identify', json={}).json()
    requirement = next(r for r in first['requirements'] if r['division'] == 'B' and r['provision_id'] == '9.10.15.5.')
    url = f'/cases/{case.id}/identify/requirements/{requirement["id"]}/decision'
    chosen = client.post(url, json={'disposition': 'include', 'role': 'supporting',
        'reason': 'Retain the exterior-wall requirement for the application analysis.',
        'expected_version': first['case_version']})
    assert chosen.status_code == 200, chosen.text
    no = client.post(f'/cases/{case.id}/identify/9.10.15.5./decision',
                     json={'decision': 'no', 'expected_version': chosen.json()['case_version']})
    assert no.status_code == 200, no.text
    rerun = client.post(f'/cases/{case.id}/identify', json={}).json()
    kept = next(r for r in rerun['requirements'] if r['id'] == requirement['id'])
    assert kept['role'] == 'supporting' and kept['disposition'] == 'include'
    assert kept['confirmation_reason'] == 'Retain the exterior-wall requirement for the application analysis.'
    assert store.get(case.id).provisions == []


def test_input_change_keeps_an_earlier_confirmation_for_review_after_a_rerun(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.'), input_fact('storeys', 2)]))
    first = client.post(f'/cases/{case.id}/identify', json={}).json()
    requirement = next(r for r in first['requirements'] if r['division'] == 'B' and r['provision_id'] == '9.10.15.5.')
    url = f'/cases/{case.id}/identify/requirements/{requirement["id"]}/decision'
    body = {'disposition': 'include', 'role': 'supporting', 'reason': 'Exterior wall for the described project.',
            'expected_version': first['case_version']}
    chosen = client.post(url, json=body)
    assert chosen.status_code == 200, chosen.text
    store.add_fact(case.id, input_fact('storeys', 8))
    rerun = client.post(f'/cases/{case.id}/identify', json={}).json()
    kept = next(r for r in rerun['requirements'] if r['id'] == requirement['id'])
    assert kept['human_confirmed'] and kept['needs_review'] and kept['disposition'] == 'review'
    assert kept['confirmation_reason'] == 'Exterior wall for the described project.'


def test_legacy_confirmation_cannot_bypass_second_printing_provenance(tmp_path):
    import shutil
    import sqlite3
    db = tmp_path / 'wrong-edition.sqlite'
    shutil.copyfile(Codes().db_path, db)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE docs SET label='NBC(AE) 2023 p1' WHERE doc='NBC-AE'")
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    with TestClient(create_app(store=store, codes=Codes(db)), base_url='http://localhost') as client:
        response = client.post(f'/cases/{case.id}/identify/confirm', json={'provisions': ['9.10.15.5.']})
    assert response.status_code == 503
    assert store.get(case.id).provisions == [] and store.get(case.id).section_c == []


def test_stored_identification_becomes_stale_when_the_code_source_changes(tmp_path):
    import shutil
    import sqlite3
    db = tmp_path / 'source.sqlite'
    shutil.copyfile(Codes().db_path, db)
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.')]))
    with TestClient(create_app(store=store, codes=Codes(db)), base_url='http://localhost') as client:
        first = client.post(f'/cases/{case.id}/identify', json={})
        assert first.status_code == 200 and not first.json()['stale']
        with sqlite3.connect(db) as con:
            con.execute("UPDATE docs SET label='NBC(AE) 2023 p1' WHERE doc='NBC-AE'")
        current = client.get(f'/cases/{case.id}/identify')
        assert current.status_code == 200 and current.json()['stale']


DEMO_TEXT = """Owner: Larkspur Example Ltd.
Representative: Priya Natarajan
Mailing address: 0000 Example Way NW, Edmonton, AB
Municipal address: 0000 Example Crescent NW, Edmonton, AB
Legal description: Lot 0, Block 0, Plan 0000000

We are building a two-storey house on a narrow lot. The side wall faces the neighbouring lot and is 1.2 m from \
the property line. The architect drew a large window wall on that side. Its glazed area is bigger than the limit \
for that distance in the code's table. We propose a fire-rated window assembly and an exterior wall rated for fire \
exposure instead."""


def _read_and_check(client, store):
    case = store.put(Case())
    read = client.post(f'/cases/{case.id}/intake', json={'text': DEMO_TEXT, 'model': False})
    assert read.status_code == 200, read.text
    first = client.get(f'/cases/{case.id}/identify')
    assert first.status_code == 200 and not first.json()['stale'], first.text
    requirement = next(r for r in first.json()['requirements']
                       if r['division'] == 'B' and r['provision_id'] == '9.10.15.4.')
    return store.get(case.id), requirement


def _patch_facts(client, case, facts):
    patched = client.patch(f'/cases/{case.id}/draft', json={
        'expected_version': case.version, 'facts': [f.model_dump(mode='json') for f in facts]})
    assert patched.status_code == 200, patched.text
    return patched.json()['version']


def _answer(client, case_id, requirement, version):
    return client.post(f'/cases/{case_id}/identify/requirements/{requirement["id"]}/decision', json={
        'disposition': 'include', 'role': 'supporting', 'reason': 'The side wall is 1.2 m from the property line.',
        'expected_version': version})


def test_demo_rule_card_answer_after_looks_right_is_saved(scene):
    """Reading runs the code check; "Looks right" then re-confirms every row with the same value (new fact
    ids and a click source). That is not an input change: the result stays current and the answer saves."""
    client, store = scene
    case, requirement = _read_and_check(client, store)
    looks_right = [Fact(field=f.field, value=f.value, kind='pointed', status='confirmed',
                        source=Source(type='user_click', ref='Confirmed by applicant', quote=str(f.value)))
                   for f in case.facts if f.field != 'project.description']
    version = _patch_facts(client, case, looks_right)
    assert not client.get(f'/cases/{case.id}/identify').json()['stale']
    answer = _answer(client, case.id, requirement, version)
    assert answer.status_code == 200, answer.text
    kept = next(r for r in answer.json()['requirements'] if r['id'] == requirement['id'])
    assert kept['human_confirmed'] and kept['disposition'] == 'include'


def test_rule_card_answer_after_a_changed_fact_reruns_the_local_check_first(scene):
    """A real input change saved through the draft makes the result stale; the next rule-card answer
    recomputes the deterministic profile in the same save instead of failing with a 409."""
    client, store = scene
    case, requirement = _read_and_check(client, store)
    version = _patch_facts(client, case, [input_fact('limiting_distance_m', 1.5)])
    assert client.get(f'/cases/{case.id}/identify').json()['stale']
    answer = _answer(client, case.id, requirement, version)
    assert answer.status_code == 200, answer.text
    result = answer.json()
    assert not result['stale']
    kept = next(r for r in result['requirements'] if r['id'] == requirement['id'])
    assert kept['human_confirmed'] and kept['disposition'] == 'include'


CARD_GAPS = {'section_c.article', 'section_c.intent', 'provisions'}


def _blocking_card_gaps(client, case_id):
    items = client.get(f'/cases/{case_id}/gaps').json()['items']
    return [g for g in items if g['severity'] == 'blocking' and g.get('submission_blocking', True)
            and (g['field'] in CARD_GAPS or g['field'].startswith(('identify.', 'section_c.')))]


def test_demo_rule_cards_save_and_section_c_lists_the_differing_sentence(scene):
    """The deck's demo path over HTTP: "Yes, it applies" on "Openings in Exposing Building Face", then the
    follow-up card ("Does your design do something different…") for the sentence the rule was quoted by,
    then the one-line departure. Every answer saves, the cards leave no submission-blocking gap, and
    Section C lists that sentence (not the bare article or all eleven of its sentences)."""
    client, store = scene
    case = store.put(Case())
    assert client.post(f'/cases/{case.id}/intake', json={'text': DEMO_TEXT, 'model': False}).status_code == 200
    case = store.get(case.id)
    looks_right = [Fact(field=f.field, value=f.value, kind='pointed', status='confirmed',
                        source=Source(type='user_click', ref='Confirmed by applicant', quote=str(f.value)))
                   for f in case.facts if f.field != 'project.description']
    version = _patch_facts(client, case, looks_right)
    assert {g['field'] for g in _blocking_card_gaps(client, case.id)} >= {'provisions'}

    ledger = client.get(f'/cases/{case.id}/identify').json()
    rule = next(r for r in ledger['requirements'] if r['division'] == 'B' and r['provision_id'] == '9.10.14.4.')
    assert rule['title'] == 'Openings in Exposing Building Face'
    applies = client.post(f'/cases/{case.id}/identify/requirements/{rule["id"]}/decision', json={
        'disposition': 'include', 'role': 'conditional',
        'reason': 'The applicant confirmed this rule applies to this project.', 'expected_version': version})
    assert applies.status_code == 200, applies.text
    confirmed = next(r for r in applies.json()['requirements'] if r['id'] == rule['id'])
    # The follow-up card is about the sentence the rule was quoted by.
    sentence = confirmed['quote_provision_id']
    assert sentence == '9.10.14.4.(1)'

    differs = client.post(f'/cases/{case.id}/identify/{sentence}/decision', json={
        'decision': 'yes', 'expected_version': applies.json()['case_version']})
    assert differs.status_code == 200, differs.text
    assert [row['provision_id'] for row in differs.json()['section_c']] == [sentence]
    departure = client.post(f'/cases/{case.id}/identify/benchmark', json={
        'provision': sentence, 'departure': 'We propose a fire-rated window assembly and a fire-rated exterior wall.',
        'expected_version': differs.json()['case_version']})
    assert departure.status_code == 200, departure.text

    saved = store.get(case.id)
    assert saved.provisions == [sentence]
    assert [row.provision_id for row in saved.section_c] == [sentence]
    assert _blocking_card_gaps(client, case.id) == []

    # The answer can be changed: "No, it follows" takes the sentence back out of Section C.
    follows = client.post(f'/cases/{case.id}/identify/{sentence}/decision', json={
        'decision': 'no', 'expected_version': store.get(case.id).version})
    assert follows.status_code == 200, follows.text
    assert store.get(case.id).provisions == [] and store.get(case.id).section_c == []


def test_no_on_one_sentence_keeps_the_other_sentence_of_the_rule(scene):
    """Cards split from one rule decide their own sentence: a No on one never wipes another's Section C row."""
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.14.4.')]))
    assert client.post(f'/cases/{case.id}/identify', json={}).status_code == 200
    for sentence in ('9.10.14.4.(1)', '9.10.14.4.(2)'):
        response = client.post(f'/cases/{case.id}/identify/{sentence}/decision', json={'decision': 'yes'})
        assert response.status_code == 200, response.text
    assert store.get(case.id).provisions == ['9.10.14.4.(1)', '9.10.14.4.(2)']
    assert client.post(f'/cases/{case.id}/identify/9.10.14.4.(2)/decision', json={'decision': 'no'}).status_code == 200
    saved = store.get(case.id)
    assert saved.provisions == ['9.10.14.4.(1)']
    assert [row.provision_id for row in saved.section_c] == ['9.10.14.4.(1)']
    assert any(f.field == 'citation.9.10.14.4.' for f in saved.facts)


def test_no_on_one_sentence_of_a_whole_stored_rule_keeps_its_other_sentences(scene):
    """A rule stored whole (its sentence was not found) loses only the sentence answered No."""
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.14.4.')]))
    assert client.post(f'/cases/{case.id}/identify', json={}).status_code == 200
    stored = store.get(case.id)
    stored.provisions = ['9.10.14.4.']
    store.put(stored)
    assert client.post(f'/cases/{case.id}/identify/9.10.14.4.(2)/decision', json={'decision': 'no'}).status_code == 200
    saved = store.get(case.id)
    rows = [row.provision_id for row in saved.section_c]
    assert rows and '9.10.14.4.(2)' not in rows and all(r.startswith('9.10.14.4.') for r in rows)
    assert '9.10.14.4.' not in saved.provisions and '9.10.14.4.(2)' not in saved.provisions
