"""Identify HTTP behaviour the applicant UI depends on, without a live model."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import CodeDbMissing, Codes
from engine.identify.answers import apply_answers
from engine.identify.demo_cache import match_demo
from engine.identify.departure import NOT_INDICATED, assess_variance, detect_redirect
from engine.identify.pipeline import overlay_ai_explainers, run
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
    assert all(q['id'] == q['field'] for q in questions)


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
    assert not any(row.get('suggested') for row in out['articles'])
    assert not any(row.get('committed') for row in out['articles'])


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

    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
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


def _brief(case_id: str) -> str:
    return (Path('evals/demo-cases') / case_id / 'input' / 'project-brief.md').read_text()


def test_demo_cache_matches_the_seeded_cases_by_id_or_exact_brief():
    from engine.identify.demo_cache import DEMO_CASE_IDS

    assert match_demo('a different house') is None
    for case_id in DEMO_CASE_IDS:
        by_id = match_demo(case_id)
        by_brief = match_demo('  ' + _brief(case_id).replace('\n', ' ') + '  ')
        assert by_id['cached'] is True and by_id['persisted'] is False and by_id['mode'] == 'cached_demo'
        assert by_brief['mode'] == 'cached_demo' and by_brief['cached'] is True
        assert by_id['articles'][0]['provision'] == by_brief['articles'][0]['provision']
        assert by_id['model_ids']['invoked'] is False
        assert by_id['commit_policy']['status'] == 'placeholder_uncalibrated'
        assert not any(article.get('suggested') for article in by_id['articles'])
        quote = by_id['benchmark']['quote']
        assert quote and len(quote.split()) <= 25
        for article in by_id['articles']:
            assert article['snippet'] and len(article['snippet'].split()) <= 25
            assert 'quote' not in article
        row = by_id['benchmark']['section_c'][0]
        assert row['provision_id'] and 'provision' not in row
        assert row['explainer']['source'] == 'deterministic'
        assert len(row['explainer']['quote'].split()) <= 25
        assert 'compli' not in json.dumps(by_id).lower()
    unknown = match_demo(DEMO_CASE_IDS[0], facts=[{'field': 'building.storeys', 'status': 'unknown', 'value': None}])
    assert any(q['id'] == 'building.storeys' and q['field'] == 'building.storeys' and q['status'] == 'unknown'
               for q in unknown['open_questions'])


def test_missing_database_response_does_not_include_a_path(tmp_path, monkeypatch):
    missing = tmp_path / 'hidden' / 'codedb.sqlite'
    monkeypatch.setattr('engine.routes_case.default_db', lambda: missing)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes()))
    case_id = client.post('/cases').json()['id']
    offline = client.post(f'/cases/{case_id}/identify', json={'prose': 'a proposal that is not a cached demo'})
    assert offline.status_code == 200 and offline.json()['mode'] == 'bm25_fallback'
    assert offline.json()['articles'] == [] and offline.json()['benchmark']['citation'] is None
    assert 'hidden' not in offline.text and 'codedb.sqlite' not in offline.text
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    still_offline = client.post(f'/cases/{case_id}/identify', json={'prose': 'a proposal that is not a cached demo'})
    assert still_offline.status_code == 200 and still_offline.json()['mode'] == 'bm25_fallback'
    monkeypatch.setenv('BATATIS_LIVE', '1')
    live = client.post(f'/cases/{case_id}/identify', json={'prose': 'a proposal that is not a cached demo'})
    assert live.status_code == 503
    assert live.json()['detail'] == 'code database not found'
    assert 'hidden' not in live.text and 'codedb.sqlite' not in live.text
    try:
        run('a proposal that is not a cached demo', db_path=missing)
    except CodeDbMissing as exc:
        assert str(exc) == 'code database not found' and 'hidden' not in str(exc)
    else:
        raise AssertionError('missing database must raise CodeDbMissing')


def test_exact_demo_description_is_cached_without_a_model_or_a_database(tmp_path, monkeypatch):
    from engine.identify.demo_cache import DEMO_CASE_IDS

    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
    monkeypatch.setattr('engine.routes_case.default_db', lambda: Path('/tmp/batatis-missing-codedb.sqlite'))
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes()))
    case_id = client.post('/cases').json()['id']
    identified = client.post(f'/cases/{case_id}/identify', json={
        'prose': _brief(DEMO_CASE_IDS[2]),
        'answers': [{'question_id': 'building.storeys', 'answer': 'not sure'}],
    })
    assert identified.status_code == 200
    body = identified.json()
    assert body['source'] == 'cache' and body['cached'] is True and body['mode'] == 'cached_demo'
    assert all(article['suggested'] is False for article in body['articles'])
    assert all(article['snippet'] and len(article['snippet'].split()) <= 25 for article in body['articles'])
    assert any(q['id'] == 'building.storeys' and q['status'] == 'unknown' for q in body['open_questions'])
    saved = client.get(f'/cases/{case_id}').json()
    assert saved['provisions'] == [] and 'NorthCore' not in json.dumps(saved)
    stored = next(fact for fact in saved['facts'] if fact['field'] == 'building.storeys')
    assert stored['status'] == 'unknown'


def test_identify_routes_publish_response_models(tmp_path):
    app = create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes())
    spec = app.openapi()
    posted = spec['paths']['/cases/{case_id}/identify']['post']['responses']['200']
    stored = spec['paths']['/cases/{case_id}/identify']['get']['responses']['200']
    stream = spec['paths']['/cases/{case_id}/identify/stream']['get']['responses']['200']
    decided = spec['paths']['/cases/{case_id}/identify/{provision_id}/decision']['post']['responses']['200']
    assert posted['content']['application/json']['schema']['$ref'].endswith('/IdentifyResponse')
    assert stored['content']['application/json']['schema']['$ref'].endswith('/IdentifyResponse')
    assert stream['content']['application/json']['schema']['$ref'].endswith('/IdentifyResponse')
    assert decided['content']['application/json']['schema']['$ref'].endswith('/DecisionResponse')


def test_quote_checked_reason_is_ai_written_unless_it_claims_compliance():
    rows = [{
        'provision_id': '9.10.15.5.(8)',
        'explainer': {'text': 'Division B quote.', 'quote': 'projecting roof soffits shall not', 'source': 'deterministic'},
    }]
    overlay_ai_explainers(rows, {
        '9.10.15.5.': Pick(article='9.10.15.5.', quote='projecting roof soffits shall not',
                           reason='The soffit projects over the exposing face this sentence limits.', confidence=0.8),
    })
    assert rows[0]['explainer']['source'] == 'ai_written'
    assert rows[0]['explainer']['quote'] == 'projecting roof soffits shall not'
    claimed = [{
        'provision_id': '9.10.15.5.(8)',
        'explainer': {'text': 'Division B quote.', 'quote': 'projecting roof soffits shall not', 'source': 'deterministic'},
    }]
    overlay_ai_explainers(claimed, {
        '9.10.15.5.': Pick(article='9.10.15.5.', quote='projecting roof soffits shall not',
                           reason='The design complies and is safe.', confidence=0.8),
    })
    assert claimed[0]['explainer']['source'] == 'deterministic'
    codes = Codes()
    rec = codes.provision('9.10.15.5.', 'B')
    arts = {'9.10.15.5.': {
        'id': '9.10.15.5.', 'part': 9, 'title': rec['title'], 'section': rec['section'],
        'subsection': rec['subsection'], 'text': rec['text'],
    }}

    class Verifier:
        def verify(self, query, candidates):
            return Verification(picks=[Pick(
                article='9.10.15.5.',
                quote='projecting roof soffits shall not be constructed above the exposing building face',
                reason='The proposal departs from the soffit limit in this article.',
                confidence=0.91,
            )], dropped=[])

    out = run('soffit variance on the side yard', arts=arts, codes=codes, ranker='bm25', verifier=Verifier())
    explained = [row for row in out['benchmark']['section_c'] if row['provision_id'] == '9.10.15.5.(8)']
    assert explained and explained[0]['explainer']['source'] == 'ai_written'
    assert 'projecting roof soffits' in explained[0]['explainer']['quote']
    assert 'compli' not in explained[0]['explainer']['text'].lower()
    assert out['section_c'] == []
