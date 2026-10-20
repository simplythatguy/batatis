"""Identify HTTP behaviour the applicant UI depends on, without a live model."""
import json

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.identify.answers import apply_answers
from engine.identify.departure import NOT_INDICATED, assess_variance, detect_redirect
from engine.identify.pipeline import run
from engine.identify.questions import generate_questions
from engine.identify.verify import Pick, Verification
from engine.models import Case
from engine.store import CaseStore

ARTS = {
    '9.10.15.5.': {'id': '9.10.15.5.', 'part': 9, 'title': 'Soffit protection', 'section': 's', 'subsection': 'ss',
                   'text': 'The soffit shall be noncombustible.'},
    '9.10.3.1.': {'id': '9.10.3.1.', 'part': 9, 'title': 'Fire-resistance rating', 'section': 's', 'subsection': 'ss',
                  'text': 'A wall assembly requires a fire-resistance rating.'},
    '9.9.8.2.': {'id': '9.9.8.2.', 'part': 9, 'title': 'Number of exits', 'section': 's', 'subsection': 'ss',
                 'text': 'A single exit is permitted in a building of not more than two storeys.'},
}


def test_not_sure_is_an_unknown_fact_and_does_not_stop():
    case = Case()
    created = apply_answers(case, [{'field': 'building.storeys', 'answer': 'not sure'}])
    assert created[0].status == 'unknown' and created[0].value is None
    out = run('hempcrete wall assembly instead of the prescribed wall', arts=ARTS, ranker='bm25', facts=case.facts)
    assert out['articles'] and out['persisted'] is False
    assert any(q['status'] == 'unknown' and q['field'] == 'building.storeys' for q in out['open_questions'])
    assert 'compli' not in out['variance_explanation'].lower()


def test_questions_name_the_assembly_and_the_candidates_they_split():
    questions = generate_questions(
        'We want hempcrete walls',
        [{'provision': art, 'title': row['title'], 'text': row['text'], 'part': row['part']}
         for art, row in ARTS.items()],
        facts=[{'field': 'building.storeys', 'value': '3', 'status': 'unconfirmed'}])
    assert 1 <= len([q for q in questions if q['field'] != 'building.storeys' or q['disambiguates']]) <= 5
    assert any('assembly' in q['text'].lower() and '9.10.3.1.' in q['disambiguates'] for q in questions)
    assert any(q['text'].startswith('Confirm number of storeys') for q in questions)


def test_no_departure_is_not_indicated_and_redirect_follows_the_gold_regimes():
    kind, text = assess_variance('The house follows the acceptable solution as drawn.')
    assert (kind, text) == NOT_INDICATED
    assert 'compli' not in text.lower()
    assert 'air admittance valve' and detect_redirect(
        'Plumbing contractor. We want an air admittance valve under the vanity.')
    assert 'Electrical Code' in detect_redirect('I am moving my electrical panel and the electrician wants a variance.')
    assert 'Gas Code' in detect_redirect('The gas fitter wants an alternative for the natural gas supply only.')
    assert 'Private Sewage' in detect_redirect('I want a different septic tank and disposal-field layout.')
    out = run('air admittance valve instead of a roof vent', arts=ARTS, ranker='bm25')
    assert out['intake_action'] == 'redirect' and out['variance_needed'] == 'unknown'
    assert not any(row['committed'] for row in out['articles'])


def test_a_quote_that_is_not_in_codedb_is_dropped():
    class Verifier:
        def verify(self, query, candidates):
            return Verification(picks=[
                Pick(article='9.99.99.99.', quote='invented sentence', reason='no', confidence=0.9),
                Pick(article='9.10.15.5.', quote='this quote is not in the article', reason='bad', confidence=0.8),
                Pick(article='9.10.15.5.', quote='The soffit shall be noncombustible.', reason='matches', confidence=0.7),
            ], dropped=[])

    out = run('soffit', arts=ARTS, ranker='bm25', verifier=Verifier())
    ids = [row['provision'] for row in out['articles']]
    assert '9.99.99.99.' not in ids and '9.10.15.5.' in ids
    kept = next(row for row in out['articles'] if row['provision'] == '9.10.15.5.')
    assert kept['quote'] == 'The soffit shall be noncombustible.'


def test_new_case_keeps_only_the_applicants_facts_and_unknown_answers(tmp_path, monkeypatch):
    def fake_run(prose, db_path=None, judge=None, **kwargs):
        on_stage = kwargs.get('on_stage')
        for stage in ('screen', 'rerank', 'verify', 'questions'):
            if on_stage:
                on_stage(stage, {'stage': stage})
        result = {'articles': [], 'section_c': [], 'questions': ['How many storeys?'],
                  'open_questions': [{'field': 'building.storeys', 'status': 'unknown', 'text': 'How many storeys?',
                                      'disambiguates': []}],
                  'variance_needed': 'unknown', 'variance_explanation': 'open', 'intake_action': 'ask',
                  'mode': 'bm25_fallback', 'persisted': False, 'cached': False}
        if on_stage:
            on_stage('done', result)
        return result

    monkeypatch.setattr('engine.routes_case.identify_run', fake_run)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes()))
    created = client.post('/cases', json={'title': 'Hempcrete house'})
    assert created.status_code == 201 and created.json()['facts'] == []
    case_id = created.json()['id']
    posted = client.post(f'/cases/{case_id}/facts', json={
        'field': 'assembly.material', 'value': 'hempcrete', 'kind': 'pointed',
        'source': {'type': 'user_text', 'ref': 'applicant description', 'quote': 'hempcrete wall'}})
    assert posted.status_code == 200
    assert [fact['field'] for fact in posted.json()['facts']] == ['assembly.material']
    assert 'NorthCore' not in json.dumps(posted.json())
    other = client.post('/cases').json()
    assert other['id'] != case_id and other['facts'] == []
    identified = client.post(f'/cases/{case_id}/identify', json={
        'prose': 'hempcrete walls', 'answers': [{'field': 'building.storeys', 'answer': 'not sure'}]})
    assert identified.status_code == 200 and identified.json()['persisted'] is False
    saved = client.get(f'/cases/{case_id}').json()
    assert saved['provisions'] == []
    unknown = next(fact for fact in saved['facts'] if fact['field'] == 'building.storeys')
    assert unknown['status'] == 'unknown'
    streamed = client.get(f'/cases/{case_id}/identify/stream', params={'prose': 'hempcrete walls'})
    order = [line.removeprefix('event: ').strip() for line in streamed.text.splitlines() if line.startswith('event:')]
    assert order == ['screen', 'rerank', 'verify', 'questions', 'done']
