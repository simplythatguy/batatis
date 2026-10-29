"""Synthetic public-report regressions for current policy and source attribution.

These exercise the real HTTP report and owned SQLite, without providers or any
evaluation population. Code lookups use the test environment's read-only corpus.
"""
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.export.scc import blockers, load_field_map
from engine.models import Case, Fact, Source
from engine.section_c import section_c_rows
from engine.store import CaseStore
from engine.tests.test_completeness_saved_case import _complete_package


def fact(field, value, *, confirmed=True, kind='pointed', source_type='user_text',
         ref='SYNTHETIC answer', page=None, bbox=None):
    return Fact(field=field, value=value, kind=kind,
                status='confirmed' if confirmed else 'unconfirmed',
                source=Source(type=source_type, ref=ref, quote='' if value is None else str(value),
                              page=page, bbox=bbox))


@pytest.fixture
def context(tmp_path):
    store, codes = CaseStore(tmp_path / 'policy.sqlite'), Codes()
    with TestClient(create_app(store, codes)) as client:
        yield client, store, codes


def review(context, case):
    client, store, codes = context
    saved = store.put(case)
    before = client.get(f'/api/cases/{saved.id}').json()
    response = client.post(f'/api/cases/{saved.id}/completeness', json={})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['case_version'] == before['version']
    assert client.get(f'/api/cases/{saved.id}').json() == before
    assert data['reviews'][0]['export_reasons'] == blockers(store.get(saved.id), load_field_map(), codes)
    assert data['llm'] is None
    assert data['administrative_only'] is data['not_a_compliance_determination'] is True
    return {e['field']: e for section in data['reviews'][0]['sections'] for e in section['elements']}


@pytest.mark.parametrize('old_key,new_key', [('pathway', 'path'), ('path', 'pathway')])
@pytest.mark.parametrize('value,confirmed,kind,applies', [
    ('acceptable', False, 'pointed', False),
    ('acceptable', False, 'proposed', False),
    ('', True, 'pointed', False),
    (None, True, 'exact', False),
    ('alternative', True, 'pointed', True),
    ('acceptable', True, 'pointed', False),
    ('acceptable_solution', True, 'pointed', False),
])
def test_process_screens_follow_current_canonical_path(context, old_key, new_key, value, confirmed, kind, applies):
    found = review(context, Case(facts=[
        fact(old_key, 'acceptable'), fact(new_key, value, confirmed=confirmed, kind=kind),
        fact('process.risk_assessment', 'low risk'),
        fact('process.mitigating_measures', 'standard measures'),
        fact('process.assumptions_and_limits', 'The capacity is stated as fact without measurements'),
    ]))
    for field, problem in [('risk_assessment', 'generic'), ('mitigating_measures', 'thin'),
                           ('assumptions_and_limits', 'stated_as_fact')]:
        entry = found[field]
        assert entry['verdict'] == ('unclear' if applies else 'present')
        assert entry['problem'] == (problem if applies else None)
        assert bool(entry['prompt']) is applies


@pytest.mark.parametrize('description,unsupported,verdict,skipped', [
    ('SYNTHETIC exterior membrane cladding replacement', True, 'unclear', True),
    ('SYNTHETIC stair width replacement', True, 'unclear', True),
    ('SYNTHETIC stair width replacement', False, 'present', False),
    ('SYNTHETIC exterior membrane cladding replacement', False, 'unclear', False),
])
def test_topic_screen_covers_every_selection_in_either_order(context, description, unsupported, verdict, skipped):
    ids = ['3.1.8.1.(1)' if unsupported else '9.27.3.4.(1)', '9.8.2.1.(1)']
    # When both supported topics are used, include both in the positive control.
    if not unsupported and verdict == 'present':
        description += ' with exterior membrane cladding'
    observed = []
    for selection in (ids, list(reversed(ids))):
        case = Case(provisions=selection, section_c=section_c_rows(selection, context[2]), facts=[
            fact('alternative_description', description), fact('professional_status', 'not_engaged')])
        entry = review(context, case)['section_c.relevance']
        assert entry['verdict'] == verdict
        assert entry['lookup_skipped'] is skipped
        assert all(pid in entry['reason'] for pid in selection)
        assert 'does not address' not in entry['reason']
        assert 'review' in entry['reason'].lower()
        observed.append((entry['verdict'], entry['lookup_skipped'], entry['reason'], entry['problem']))
    assert observed[0] == observed[1]


@pytest.mark.parametrize('key', ['municipal_address', 'civic_address', 'municipalAddress', 'address'])
@pytest.mark.parametrize('value,confirmed,kind,verdict', [
    ('SYNTHETIC revised site', False, 'pointed', 'unclear'),
    ('SYNTHETIC proposed site', False, 'proposed', 'unclear'),
    ('', True, 'pointed', 'missing'),
    (None, True, 'exact', 'missing'),
    ('SYNTHETIC current site', True, 'pointed', 'present'),
])
def test_single_location_uses_one_current_logical_address(context, key, value, confirmed, kind, verdict):
    latest = fact(key, value, confirmed=confirmed, kind=kind, ref='SYNTHETIC current source')
    entry = review(context, Case(facts=[fact('pathway', 'alternative'),
        fact('municipal_address', 'SYNTHETIC old site'), latest]))['single_location']
    assert entry['verdict'] == verdict
    assert all(q['text'] != 'SYNTHETIC old site' for q in entry['quotes'])
    if verdict != 'present':
        assert entry['prompt']['field'] == key
        assert entry['prompt']['question']


@pytest.mark.parametrize('value,confirmed,kind,verdict', [
    ('SYNTHETIC second site', False, 'pointed', 'unclear'),
    ('SYNTHETIC second site', False, 'proposed', 'unclear'),
    ('SYNTHETIC second site', True, 'pointed', 'missing'),
    ('', True, 'pointed', 'present'),
])
def test_explicit_additional_location_keeps_its_current_state(context, value, confirmed, kind, verdict):
    entry = review(context, Case(facts=[fact('pathway', 'alternative'),
        fact('municipal_address', 'SYNTHETIC primary site'),
        fact('additional_location', 'SYNTHETIC former second site'),
        fact('additional_location', value, confirmed=confirmed, kind=kind)]))['single_location']
    assert entry['verdict'] == verdict
    assert all(q['text'] != 'SYNTHETIC former second site' for q in entry['quotes'])
    if not confirmed:
        assert entry['prompt']['field'] == 'additional_location'


@pytest.mark.parametrize('with_rows', [False, True])
@pytest.mark.parametrize('value,confirmed,kind,verdict', [
    ('NBC(AE) 2023, 2nd printing', False, 'pointed', 'unclear'),
    ('NBC(AE) 2023, 2nd printing', False, 'proposed', 'unclear'),
    # A blank saved label is filled from the deterministic Section C lookup in the outgoing file.
    ('', True, 'pointed', 'present'),
    (None, True, 'exact', 'present'),
])
def test_edition_screen_cannot_promote_pending_or_withdrawn_label(context, with_rows, value, confirmed, kind, verdict):
    ids = ['9.8.2.1.(1)'] if with_rows else []
    case = Case(provisions=ids, section_c=section_c_rows(ids, context[2]), facts=[
        fact('code_or_standard', 'NBC(AE) 2023, 2nd printing'),
        fact('code_or_standard', value, confirmed=confirmed, kind=kind)])
    entry = review(context, case)['section_c.edition']
    assert entry['verdict'] == verdict
    if verdict != 'present':
        assert entry['lookup_skipped'] is True
        assert entry['prompt']['field'] == 'code_or_standard'


@pytest.mark.parametrize('old_key,new_key', [('professional_status', 'professional.status'),
                                           ('professional.status', 'professional_status')])
def test_unresolved_professional_requirement_uses_current_engagement_source(context, old_key, new_key):
    newest = fact(new_key, 'not_engaged', ref='SYNTHETIC shared applicant ref', page=7, bbox=(10, 20, 30, 40))
    entry = review(context, Case(facts=[fact(old_key, 'engaged', ref=newest.source.ref, page=2), newest]))[
        'professional_requirement']
    assert entry['reason'] and entry['severity'] == 'blocking' and entry['routed_to'] == 'officer'
    assert entry['sources'] == [newest.source.model_dump(mode='json')]


@pytest.mark.parametrize('source_type', ['user_text', 'file', 'drawing'])
def test_composite_quotes_keep_full_sources_even_when_refs_repeat(context, source_type):
    first = fact('municipal_address', 'SYNTHETIC primary site', source_type=source_type,
                 ref='SYNTHETIC shared source', page=7, bbox=(10, 20, 30, 40))
    second = fact('additional_location', 'SYNTHETIC additional site', source_type=source_type,
                  ref=first.source.ref, page=11, bbox=(50, 60, 70, 80))
    entry = review(context, Case(facts=[first, second]))['single_location']
    expected = [f.source.model_dump(mode='json') for f in (first, second)]
    assert [q['source'] for q in entry['quotes']] == expected
    assert entry['sources'] == expected
    assert all('url' not in q and q['source']['type'] != 'code' for q in entry['quotes'])


@pytest.mark.parametrize('old_key,new_key,logical', [
    ('owner', 'owner_name', 'owner_name'),
    ('process.risk', 'process.risk_assessment', 'risk_assessment'),
    ('application_date', 'request_date', 'application_date'),
])
def test_public_alias_replacement_removes_phantom_preflight_blocker(context, old_key, new_key, logical):
    client, store, codes = context
    case, _ = _complete_package(store, codes)
    value = next(f.value for f in reversed(case.facts) if f.field == new_key)
    for answer in (fact(old_key, 'SYNTHETIC obsolete value', confirmed=False), fact(new_key, value)):
        response = client.post(f'/api/cases/{case.id}/facts', json=answer.model_dump(mode='json'))
        assert response.status_code == 200, response.text
    response = client.post(f'/api/cases/{case.id}/completeness', json={})
    assert response.status_code == 200, response.text
    reasons = response.json()['reviews'][0]['export_reasons']
    assert len(reasons) == 1 and 'professional_requirement' in reasons[0]
    assert client.post(f'/api/cases/{case.id}/export', json={}).status_code == 409
    found = {e['field']: e for s in response.json()['reviews'][0]['sections'] for e in s['elements']}
    assert not found.get(old_key, found[logical])['in_export_preflight']
    assert all(not e['in_export_preflight'] for e in found.values() if e['field'] != 'professional_requirement')
    assert all(s['quote'] != 'SYNTHETIC obsolete value' for e in found.values() for s in e['sources'])


@pytest.mark.parametrize('path', ['/cases', '/api/cases'])
def test_missing_corpus_error_is_private_and_case_still_checked_first(tmp_path, monkeypatch, path):
    store = CaseStore(tmp_path / 'missing.sqlite')
    saved = store.put(Case())
    private_missing = str(tmp_path / 'SYNTHETIC-private-missing-corpus.sqlite')
    monkeypatch.setenv('BATATIS_CODEDB', private_missing)
    with TestClient(create_app(store)) as client:
        for cid, body, status, detail in [
            ('SYNTHETIC-absent', {}, 404, 'case not found'),
            (saved.id, {'variant': 'C'}, 503, 'provider-assisted completeness is unavailable'),
            (saved.id, {}, 503, 'code database not found'),
        ]:
            response = client.post(f'{path}/{cid}/completeness', json=body)
            assert response.status_code == status
            assert response.json()['detail'] == detail
            assert private_missing not in response.text
            assert response.headers.get('cache-control') == 'no-store'


@pytest.mark.parametrize('old_key,new_key,logical', [
    ('owner_name', 'owner', 'owner_name'),
    ('process.risk_assessment', 'process.risk', 'risk_assessment'),
    ('request_date', 'application_date', 'application_date'),
])
def test_current_pending_alias_keeps_its_actual_input_and_source(context, old_key, new_key, logical):
    newest = fact(new_key, 'SYNTHETIC pending current answer', confirmed=False, page=9)
    entry = review(context, Case(facts=[fact(old_key, 'SYNTHETIC old confirmed answer'), newest]))[logical]
    assert entry['verdict'] == 'unclear'
    assert entry['in_export_preflight'] is True
    assert entry['prompt']['field'] == new_key
    assert entry['sources'] == [newest.source.model_dump(mode='json')]


@pytest.mark.parametrize('pathway', ['acceptable_solution', 'alternative'])
def test_two_public_facts_keep_pending_process_confirmation_action(context, pathway):
    client, _, _ = context
    created = client.post('/api/cases', json={'title': 'SYNTHETIC pending process minimum'})
    assert created.status_code == 201
    case_id = created.json()['id']
    pending = fact('process.risk', 'SYNTHETIC pending', confirmed=False, page=9)
    for answer in (fact('path', pathway), pending):
        assert client.post(f'/api/cases/{case_id}/facts', json=answer.model_dump(mode='json')).status_code == 200
    response = client.post(f'/api/cases/{case_id}/completeness', json={})
    assert response.status_code == 200
    elements = [e for s in response.json()['reviews'][0]['sections'] for e in s['elements']]
    assert 'Risk assessment is not confirmed yet.' in response.json()['reviews'][0]['export_reasons']
    assert any(e['verdict'] in ('missing', 'unclear') and e['in_export_preflight']
               and e['severity'] == 'blocking' and e['prompt']
               and e['prompt']['field'] == pending.field
               and pending.source.model_dump(mode='json') in e['sources'] for e in elements)


@pytest.mark.parametrize('target,logical', [
    ('process.risk', 'risk_assessment'),
    ('process.mitigation', 'mitigating_measures'),
    ('process.assumptions', 'assumptions_and_limits'),
])
@pytest.mark.parametrize('kind', ['pointed', 'proposed'])
@pytest.mark.parametrize('pathway', ['acceptable_solution', 'alternative'])
def test_pending_process_alias_action_and_public_resolution_preserve_export_policy(
        context, target, logical, kind, pathway):
    client, store, codes = context
    case, _ = _complete_package(store, codes)
    current = fact(target, 'SYNTHETIC pending current process answer', confirmed=False, kind=kind,
                   source_type='file', ref='SYNTHETIC shared process source', page=9, bbox=(1, 2, 3, 4))
    for answer in (fact('path', pathway), current):
        assert client.post(f'/api/cases/{case.id}/facts', json=answer.model_dump(mode='json')).status_code == 200
    before = client.get(f'/api/cases/{case.id}').json()
    response = client.post(f'/api/cases/{case.id}/completeness', json={})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert client.get(f'/api/cases/{case.id}').json() == before
    assert response.json()['case_version'] == before['version']
    reasons = response.json()['reviews'][0]['export_reasons']
    requirement_reasons = [r for r in reasons if r.startswith('blocking gap in section D, professional_requirement:')]
    assert len(requirement_reasons) == 1, 'An unresolved officer determination is independent of process alias edits'
    process_reasons = [r for r in reasons if r not in requirement_reasons]
    assert reasons[0] == f'{logical.replace("_", " ").capitalize()} is not confirmed yet.'  # plain words, no fact id
    if pathway == 'acceptable_solution':
        assert len(process_reasons) == 1
    else:
        assert len(process_reasons) == 2 and process_reasons[1].startswith(f'blocking gap in section process, {logical}:')
    official = client.post(f'/api/cases/{case.id}/export', json={'draft': False})
    assert official.status_code == 409 and official.json()['detail']['reasons'] == reasons
    elements = [e for s in response.json()['reviews'][0]['sections'] for e in s['elements']]
    actions = [e for e in elements if e['verdict'] in ('missing', 'unclear') and e['in_export_preflight']
               and e['severity'] == 'blocking' and e['prompt'] and e['prompt']['field'] == target]
    assert actions
    assert any(current.source.model_dump(mode='json') in e['sources'] for e in actions)
    if pathway == 'acceptable_solution':
        assert any('confirm' in e['reason'].lower() and 'withdraw' in e['reason'].lower()
                   or 'confirm' in e['prompt']['question'].lower() for e in actions)

    # Resolve through the other alias, then explicitly blank and withdraw it.
    # Only the acceptable path exempts these alternative-process answers.
    original_value = next(f.value for f in reversed(case.facts) if f.field == f'process.{logical}')
    for value, resolution_kind in ((original_value, 'pointed'), ('', 'pointed'), (None, 'exact')):
        resolution = fact(f'process.{logical}', value, kind=resolution_kind,
                          ref=current.source.ref, page=10)
        assert client.post(f'/api/cases/{case.id}/facts', json=resolution.model_dump(mode='json')).status_code == 200
        response = client.post(f'/api/cases/{case.id}/completeness', json={})
        assert response.status_code == 200
        reasons = response.json()['reviews'][0]['export_reasons']
        elements = [e for s in response.json()['reviews'][0]['sections'] for e in s['elements']]
        assert all(current.source.model_dump(mode='json') not in e['sources'] for e in elements)
        assert not any('unconfirmed' in r for r in reasons)
        official = client.post(f'/api/cases/{case.id}/export', json={'draft': False})
        assert official.status_code == 409 and official.json()['detail']['reasons'] == reasons
        process_reasons = [r for r in reasons if not r.startswith('blocking gap in section D, professional_requirement:')]
        if pathway == 'acceptable_solution' or value == original_value:
            assert process_reasons == []
        else:
            assert any(f'blocking gap in section process, {logical}:' in r for r in process_reasons)
        if pathway == 'acceptable_solution':
            entry = next(e for e in elements if e['field'] == logical)
            assert entry['verdict'] == 'present' and entry['prompt'] is None
            assert entry['in_export_preflight'] is False


def test_a_drafted_open_question_is_named_not_shown_as_its_key():
    from engine.models_completeness import field_label
    assert field_label('drafting.questions.draft_8a33dedfa8b9.0') == 'Open question from the drafted wording'
    assert field_label('owner_name') == 'owner name'


def test_a_stored_raw_label_reads_as_the_drafted_question():
    from engine.review.package_sources import _label
    field = 'drafting.questions.draft_8a33dedfa8b9.0'
    assert _label({'Field': field, 'Label': field.replace('_', ' ')}) == 'Open question from the drafted wording'
    assert _label({'Field': 'owner_name', 'Label': "Owner's name"}) == "Owner's name"
