"""Identify service: pipeline, lying-model property, process rows on 60 dev cases, and the HTTP routes.

Offline: BATATIS_PROVIDER=fake (engine/identify/fakes.py). Skipped with the other codedb tests when the
code database is not built.
"""
import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine import llm_gate
from engine.api import create_app
from engine.codes import Codes
from engine.identify import articles
from engine.identify import fakes
from engine.identify.commit import CommitPolicy, load_policy
from engine.identify.config import DIVISION_B_ARTICLES, IdentifyConfig
from engine.identify.corpus import card
from engine.identify.llm import OpenAIVerifier
from engine.identify.pipeline import run
from engine.identify.providers import Transports, transports
from engine.identify.verify import ClaudeVerifier, normalize
from engine.models import Case, Fact, Source
from engine.store import CaseStore

REPO = Path(__file__).resolve().parents[2]
DEV_CASES = sorted((REPO / 'evals_dev' / 'cases').glob('dev-*.json'))
SOFFIT = ('New two-storey single detached house. The north wall is 0.3 m from the side property line and the '
          'owner wants a 450 mm roof soffit overhang with vented aluminum soffit over that wall.')


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    llm_gate.reset_for_tests()
    for name in ('BATATIS_LIVE', 'VERCEL', 'BATATIS_STORE', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY',
                 'BATATIS_IDENTIFY_CONFIG'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1000')
    yield
    llm_gate.reset_for_tests()


@pytest.fixture(scope='module')
def codes():
    return Codes()


@pytest.fixture(scope='module')
def arts(codes):
    return articles(Path(codes.db_path))


def calibrated(config=None, threshold=0.05):
    return CommitPolicy('calibrated', 'test fit', {9: threshold}, 3, (config or IdentifyConfig()).config_hash)


def displayed_text_ok(result, arts):
    """Every shown id is a Division B article; every shown model quote is word for word in that article."""
    for article in result.articles:
        assert article.provision in arts
        if article.quote_source == 'verifier':
            assert normalize(article.quote) in normalize(card(arts[article.provision], None))
    for choice in result.choices:
        assert choice.provision in arts and choice.quote
    for pick in result.trace.picks:
        assert pick in arts


# --- pipeline -------------------------------------------------------------------------------------

def test_screen_judges_all_2080_articles_and_reranks_in_one_request(codes, arts):
    seen = []
    base = fakes.fake_jev_ask()

    def counting(state, questions, timeout):
        seen.append(len(questions))
        return base(state, questions, timeout)
    tp = transports()
    tp.jev = counting
    out = run(SOFFIT, codes=codes, transports=tp)
    assert len(arts) == DIVISION_B_ARTICLES == 2080
    assert len(out.screen) == 2080 and set(out.screen) == set(arts)
    assert sum(seen[:-1]) == 2080 and seen[-1] == 60                   # screen batches, then one rerank request
    stages = {s.stage: s for s in out.result.trace.stages}
    assert stages['rerank'].requests == 1 and stages['rerank'].detail == 'one request'
    assert out.result.trace.articles_scored == 2080 and out.result.trace.exhaustive


def test_incomplete_screen_falls_back_and_commits_nothing(codes):
    base = fakes.fake_jev_ask()

    def drops_one(state, questions, timeout):
        reply = base(state, questions, timeout)
        if len(questions) > 60:
            reply['answers'].pop(next(iter(reply['answers'])))
        return reply
    tp = transports()
    tp.jev = drops_one
    result = run(SOFFIT, codes=codes, transports=tp, policy=calibrated()).result
    assert result.mode == 'bm25_fallback' and result.committed == [] and not result.narrowed
    assert 'Nothing is committed' in result.label and result.message
    assert all(a.status == 'fallback' and a.verifier == 'not_run' for a in result.articles)


def test_offline_without_fakes_is_a_labelled_bm25_fallback(codes, monkeypatch):
    monkeypatch.delenv('BATATIS_PROVIDER')
    result = run(SOFFIT, codes=codes, policy=calibrated()).result
    assert result.mode == 'bm25_fallback' and result.source == 'bm25 fallback'
    assert result.committed == [] and result.model_ids == {'screen': None, 'rerank': None, 'verifier': None}
    assert 'jev gate' in result.trace.fallback_reason or 'BATATIS_LIVE' in result.trace.fallback_reason
    assert result.articles and result.trace.usd == 0 and llm_gate._memory.today() == 0


def test_bm25_v3_fallback_ranks_with_the_ported_search(codes, monkeypatch):
    monkeypatch.delenv('BATATIS_PROVIDER')
    result = run(SOFFIT, codes=codes, config=IdentifyConfig(fallback='bm25_v3')).result
    assert result.trace.ranker == 'bm25_v3 fallback' and result.articles and result.committed == []


def test_uncalibrated_default_commits_nothing_and_offers_three_quoted_choices(codes):
    result = run(SOFFIT, codes=codes, policy=load_policy('no-such-hash')).result
    assert result.mode == 'fake' and result.committed == []
    assert len(result.choices) == 3 and all(c.question.startswith('The code says: "') for c in result.choices)
    assert [q.field for q in result.open_questions] == [f'identify.choice.{c.provision}' for c in result.choices]
    assert result.commit_policy['status'] == 'uncalibrated'
    assert 'Offline fake providers' in result.label


def test_calibrated_part9_commits_only_verifier_picks_at_most_three(codes, arts):
    result = run(SOFFIT, codes=codes, policy=calibrated()).result
    assert result.committed, 'the fake verifier picks a Part 9 article for this description'
    assert len(result.committed) <= 3
    for article_id in result.committed:
        card_ = next(a for a in result.articles if a.provision == article_id)
        assert arts[article_id]['part'] == 9 and card_.verifier == 'picked' and card_.status == 'committed'
    for article in result.articles:
        if article.part != 9:
            assert article.status != 'committed'
    assert result.benchmark.basis == 'committed' and result.benchmark.provision == result.committed[0]


def test_benchmark_record_has_codedb_sentence_and_lookup_codes(codes):
    bench = run(SOFFIT, codes=codes).result.benchmark
    assert bench.identified and bench.role == 'benchmark_acceptable_solution'
    assert bench.citation and bench.citation.startswith('NBC(AE) 2023 p2, Div B')
    if bench.provision_id:
        assert bench.sentence == ' '.join(codes.provision(bench.provision_id, 'B')['text'].split())
    assert bench.departure_status in {'proposed', 'none'}
    assert not bench.attribution_missing and bench.objectives and bench.functions


def test_verifier_failure_means_no_commit(codes):
    class Broken:
        def verify(self, query, candidates):
            raise TimeoutError('down')
    result = run(SOFFIT, codes=codes, verifier=Broken(), policy=calibrated()).result
    assert result.committed == [] and result.trace.verifier.startswith('failed') and not result.narrowed


@pytest.mark.parametrize('seed', range(30))
def test_lying_model_never_shows_a_fabricated_citation(codes, arts, seed):
    """Property: whatever a lying verifier returns, zero fabricated ids or quotes reach the result."""
    liar = ClaudeVerifier(codes.db_path, client=fakes.LyingAnthropic(seed))
    out = run(SOFFIT, codes=codes, verifier=liar, policy=calibrated()).result
    displayed_text_ok(out, arts)
    shown_ids = {a.provision for a in out.articles} | {c.provision for c in out.choices} | set(out.committed)
    assert shown_ids <= set(arts)
    for committed in out.committed:
        assert next(a for a in out.articles if a.provision == committed).quote_source == 'verifier'
    assert out.trace.dropped, 'every liar emits at least one fabrication, and each one is counted'
    for pick in out.trace.picks:                                       # anything kept was verbatim
        assert normalize(next(a.quote for a in out.articles if a.provision == pick)) in normalize(
            card(arts[pick], None))


@pytest.mark.parametrize('seed', range(10))
def test_lying_openai_verifier_is_filtered_the_same_way(codes, arts, seed):
    picker = fakes.lying_picks(seed)

    def lying_json(name, schema, system, user, *, model, max_output_tokens=0, effort=None, timeout=60):
        return {'picks': picker(user)}, {'input_tokens': 1, 'output_tokens': 1}
    out = run(SOFFIT, codes=codes, verifier=OpenAIVerifier(lying_json, arts, model='gpt-6-luna'),
              policy=calibrated()).result
    displayed_text_ok(out, arts)
    assert {d.reason for d in out.trace.dropped} <= {'article not in candidate list', 'duplicate article',
                                                    'quote not found in article text'}


@pytest.mark.parametrize('path', DEV_CASES, ids=[p.stem for p in DEV_CASES])
def test_process_rows_on_every_dev_case(codes, path):
    case = json.loads(path.read_text())
    result = run(case['description'], codes=codes).result
    rows = {(r.division, r.provision_id): r for r in result.process_refs}
    assert set(rows) == {('A', '1.2.1.1.'), ('C', '2.3.1.1.')}
    for (division, provision_id), row in rows.items():
        assert row.read_only is True and row.citation == codes.citation(provision_id, division)
        assert row.text and row.title


def test_sixty_dev_cases_exist():
    assert len(DEV_CASES) == 60


# --- HTTP -----------------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, codes):
    store = CaseStore(tmp_path / 'cases.sqlite')
    app = create_app(store=store, codes=codes)
    with TestClient(app, base_url='http://localhost') as http:
        yield http, store


def described(http, text=SOFFIT):
    case = http.post('/cases', json={}).json()
    fact = Fact(field='project.description', value=text, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='description'))
    assert http.post(f"/cases/{case['id']}/facts", json=fact.model_dump()).status_code == 200
    return case['id']


def sse(http, case_id, body=None):
    events = []
    with http.stream('POST', f'/cases/{case_id}/identify', json=body or {},
                     headers={'Accept': 'text/event-stream'}) as response:
        assert response.status_code == 200 and response.headers['content-type'].startswith('text/event-stream')
        assert response.headers['cache-control'] == 'no-store' and response.headers['x-robots-tag']
        name = None
        for line in response.iter_lines():
            if line.startswith('event: '):
                name = line[7:]
            elif line.startswith('data: '):
                events.append((name, json.loads(line[6:])))
    return events


def test_sse_stage_events_arrive_in_order_and_done_matches_get(client):
    http, _ = client
    case_id = described(http)
    events = sse(http, case_id)
    assert [name for name, _ in events] == ['start', 'screen', 'rerank', 'verify', 'questions', 'done']
    done = events[-1][1]
    stored = http.get(f'/cases/{case_id}/identify').json()
    assert done['articles'] == stored['articles'] and done['trace']['config_hash'] == stored['trace']['config_hash']
    for _, payload in events[:-1]:
        assert SOFFIT[:30] not in json.dumps(payload)                  # stage events carry no prose


def test_sse_error_event_on_failure(client, monkeypatch):
    http, _ = client
    case_id = described(http)
    import engine.routes_identify as routes
    monkeypatch.setattr(routes, 'identify_run', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')))
    events = sse(http, case_id)
    assert [name for name, _ in events] == ['start', 'error'] and events[-1][1]['message'] == 'Identification failed'


def test_post_json_persists_and_get_never_calls_a_provider(client, monkeypatch):
    http, store = client
    case_id = described(http)
    assert http.get(f'/cases/{case_id}/identify').status_code == 404
    posted = http.post(f'/cases/{case_id}/identify', json={})
    assert posted.status_code == 200 and posted.json()['persisted'] is True
    import engine.identify.providers as providers
    import engine.routes_identify as routes
    boom = lambda *a, **k: pytest.fail('GET called a provider')   # noqa: E731
    monkeypatch.setattr(providers, 'transports', boom)
    monkeypatch.setattr(routes, 'identify_run', boom)
    got = http.get(f'/cases/{case_id}/identify')
    assert got.status_code == 200 and got.json()['articles'] == posted.json()['articles']
    case = store.get(case_id)
    assert case.provisions == [] and case.relevance is not None and len(case.relevance.scores) == 2080


def test_identify_redacts_personal_details_before_the_provider(client, monkeypatch):
    http, _ = client
    seen = []
    real = fakes.fake_jev_ask

    def recording():
        ask = real()

        def inner(state, questions, timeout):
            seen.append(state['proposal'])
            return ask(state, questions, timeout)
        return inner
    monkeypatch.setattr(fakes, 'fake_jev_ask', recording)
    case_id = described(http, SOFFIT + ' Call Priya Natarajan at 780-555-0199 or priya@example.com.')
    assert http.post(f'/cases/{case_id}/identify', json={}).status_code == 200
    assert seen and all('priya@example.com' not in p and '780-555-0199' not in p and 'Natarajan' not in p
                        for p in seen)


def test_identify_needs_a_description_and_never_changes_provisions(client):
    http, store = client
    empty = http.post('/cases', json={}).json()['id']
    assert http.post(f'/cases/{empty}/identify', json={}).status_code == 409
    case_id = described(http)
    before = store.get(case_id).provisions
    assert http.post(f'/cases/{case_id}/identify', json={}).status_code == 200
    assert store.get(case_id).provisions == before == []


def test_decisions_yes_no_not_sure_and_information_request(client, codes):
    http, store = client
    case_id = described(http)
    result = http.post(f'/cases/{case_id}/identify', json={}).json()
    first, second = result['articles'][0]['provision'], result['articles'][1]['provision']
    yes = http.post(f'/cases/{case_id}/identify/{first}/decision', json={'decision': 'yes'})
    assert yes.status_code == 200
    case = store.get(case_id)
    assert case.provisions == [first] and case.section_c and any(f.field == f'citation.{first}' for f in case.facts)
    unsure = http.post(f'/cases/{case_id}/identify/{second}/decision', json={'decision': 'not_sure'}).json()
    card = next(a for a in unsure['articles'] if a['provision'] == second)
    assert card['decision'] == 'not_sure' and card['open_question_id']
    request = http.get(f'/cases/{case_id}/information-request').json()
    assert [item['provision_id'] for item in request['items']] == [second]
    http.post(f'/cases/{case_id}/identify/{first}/decision', json={'decision': 'no'})
    assert store.get(case_id).provisions == [] and store.get(case_id).section_c == []
    assert http.post(f'/cases/{case_id}/identify/9.99.99.99./decision', json={'decision': 'yes'}).status_code == 404


def test_confirm_checks_the_code_database(client):
    http, store = client
    case_id = described(http)
    assert http.post(f'/cases/{case_id}/identify/confirm', json={'provisions': ['9.99.1.1.']}).status_code == 404
    ok = http.post(f'/cases/{case_id}/identify/confirm', json={'provisions': ['9.10.15.5.(8)']})
    assert ok.status_code == 200 and store.get(case_id).provisions == ['9.10.15.5.(8)']


def test_benchmark_confirmation_looks_up_the_sentence_and_refuses_compliance_claims(client, codes):
    http, _ = client
    case_id = described(http)
    http.post(f'/cases/{case_id}/identify', json={})
    bad = http.post(f'/cases/{case_id}/identify/benchmark',
                    json={'provision': '9.10.15.5.(8)', 'departure': 'The soffit complies anyway.'})
    assert bad.status_code == 422
    ok = http.post(f'/cases/{case_id}/identify/benchmark',
                   json={'provision': '9.10.15.5.(8)', 'departure': 'Soffit projects over a face 0.3 m from the line.'})
    bench = ok.json()['benchmark']
    assert bench['basis'] == 'applicant' and bench['departure_status'] == 'confirmed'
    assert bench['sentence'] == ' '.join(codes.provision('9.10.15.5.(8)', 'B')['text'].split())
    assert [o['id'] for o in bench['objectives']] == ['OP3.1'] and [f['id'] for f in bench['functions']] == ['F03']
    assert http.post(f'/cases/{case_id}/identify/benchmark',
                     json={'provision': '9.99.1.1.', 'departure': 'x'}).status_code == 404


def test_process_refs_route_is_read_only_lookup(client, codes):
    http, _ = client
    case_id = described(http)
    rows = http.get(f'/cases/{case_id}/process-refs').json()['items']     # HttpGuard wraps arrays
    assert [(r['division'], r['provision_id']) for r in rows] == [('A', '1.2.1.1.'), ('C', '2.3.1.1.')]
    assert all(r['read_only'] is True for r in rows)


def test_rate_limit_is_per_ip_and_before_any_provider(client, monkeypatch):
    http, _ = client
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1')
    case_id = described(http)
    assert http.post(f'/cases/{case_id}/identify', json={}).status_code == 200
    limited = http.post(f'/cases/{case_id}/identify', json={})
    assert limited.status_code == 429 and limited.headers['retry-after']


def test_spend_is_settled_per_provider_for_a_run(client):
    http, _ = client
    case_id = described(http)
    trace = http.post(f'/cases/{case_id}/identify', json={}).json()['trace']
    assert set(trace['spend']) == {'jev', 'openai'} and trace['spend']['jev']['requests'] == 21
    assert abs(float(llm_gate._memory.today()) - trace['usd']) < 1e-6


def test_concurrent_run_on_the_same_case_is_refused(client, monkeypatch):
    http, _ = client
    case_id = described(http)
    started, release = threading.Event(), threading.Event()
    real = fakes.fake_jev_ask

    def slow():
        ask = real()

        def inner(state, questions, timeout):
            started.set()
            release.wait(10)
            return ask(state, questions, timeout)
        return inner
    monkeypatch.setattr(fakes, 'fake_jev_ask', slow)
    worker = threading.Thread(target=lambda: http.post(f'/cases/{case_id}/identify', json={}))
    worker.start()
    assert started.wait(10)
    second = http.post(f'/cases/{case_id}/identify', json={})
    release.set()
    worker.join(20)
    assert second.status_code == 409


# --- access guard (#48): identify is an owner write, reviewers read -------------------------------

@pytest.fixture(scope='module')
def scene(tmp_path_factory, codes):
    from contextlib import ExitStack
    from engine.tests.test_accounts import onboard, signup
    with pytest.MonkeyPatch.context() as patch, ExitStack() as stack:
        patch.delenv('VERCEL', raising=False)
        patch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret"}')
        patch.setenv('BATATIS_AUTH_RATE_LIMIT', '100')
        store = CaseStore(tmp_path_factory.mktemp('identify-access') / 'cases.sqlite')
        app = create_app(store=store, codes=codes)
        clients, users = {}, {}
        for name, role in [('owner', 'applicant'), ('other', 'applicant'), ('reviewer', 'reviewer')]:
            clients[name] = stack.enter_context(TestClient(app, base_url='http://localhost'))
            assert signup(clients[name], name + '@example.test', name.title()).status_code == 201
            users[name] = onboard(clients[name], role, 'edmonton')
        yield store, clients, users


def test_reviewer_reads_identify_but_cannot_run_or_decide(scene):
    store, clients, users = scene
    case = Case(title='Access', owner_id=users['owner']['id'], authority='edmonton', facts=[Fact(
        field='project.description', value=SOFFIT, kind='pointed', status='confirmed',
        source=Source(type='user_text', ref='d'))])
    store.put(case)
    owner, reviewer, other = clients['owner'], clients['reviewer'], clients['other']
    assert owner.post(f'/cases/{case.id}/identify', json={}).status_code == 200
    assert other.post(f'/cases/{case.id}/identify', json={}).status_code == 404
    assert other.get(f'/cases/{case.id}/identify').status_code == 404
    submitted = store.get(case.id)
    submitted.status = 'submitted'
    store.put(submitted)
    assert reviewer.get(f'/cases/{case.id}/identify').status_code == 200
    article = reviewer.get(f'/cases/{case.id}/identify').json()['articles'][0]['provision']
    assert reviewer.post(f'/cases/{case.id}/identify', json={}).status_code in {404, 409}
    assert reviewer.post(f'/cases/{case.id}/identify/{article}/decision',
                         json={'decision': 'yes'}).status_code in {404, 409}
    assert owner.post(f'/cases/{case.id}/identify', json={}).status_code == 409    # submitted is read-only
    assert store.get(case.id).provisions == []


def test_reference_withdrawal_clears_a_yes_on_the_identify_cards(client):
    http, store = client
    case_id = described(http)
    first = http.post(f'/cases/{case_id}/identify', json={}).json()['articles'][0]['provision']
    http.post(f'/cases/{case_id}/identify/{first}/decision', json={'decision': 'yes'})
    version = store.get(case_id).version
    withdrawn = http.post(f'/cases/{case_id}/section-d', json={'provisions': [], 'expected_version': version})
    assert withdrawn.status_code == 200 and store.get(case_id).provisions == []
    card = next(a for a in http.get(f'/cases/{case_id}/identify').json()['articles'] if a['provision'] == first)
    assert card['decision'] is None


# --- review fixes: answers scope, no network offline, single compare-and-swap ----------------------

def test_answers_only_fill_questions_identify_asked(client):
    http, store = client
    case_id = described(http)
    result = http.post(f'/cases/{case_id}/identify', json={}).json()
    question = result['open_questions'][0]
    hostile = [
        {'question_id': 'project.description', 'answer': 'replaced'},
        {'field': 'project.description', 'answer': 'replaced'},
        {'question_id': question['id'], 'field': 'project.description', 'answer': 'replaced'},
        {'question_id': question['id'], 'field': f"citation.{question['provision']}", 'answer': 'x'},
        {'question_id': 'evidence.ev_1.file_ref', 'answer': 'x'},
    ]
    for answer in hostile:
        assert http.post(f'/cases/{case_id}/identify', json={'answers': [answer]}).status_code == 422
    kept = [f for f in store.get(case_id).facts if f.field == 'project.description']
    assert len(kept) == 1 and kept[0].status == 'confirmed' and kept[0].value == SOFFIT
    ok = http.post(f'/cases/{case_id}/identify', json={'answers': [{'question_id': question['id'], 'answer': 'yes'}]})
    assert ok.status_code == 200
    filled = [f for f in store.get(case_id).facts if f.field == question['field']]
    assert len(filled) == 1 and filled[0].status == 'unconfirmed' and filled[0].value == 'yes'


def test_answers_are_written_with_the_result_or_not_at_all(client, monkeypatch):
    """A refused run (429) leaves no answer behind; a successful run is one write, answers included."""
    import engine.routes_identify as routes
    http, store = client
    case_id = described(http)
    question = http.post(f'/cases/{case_id}/identify', json={}).json()['open_questions'][0]
    answer = {'question_id': question['id'], 'answer': 'yes'}
    before = store.get(case_id).version
    monkeypatch.setattr(routes, 'identify_retry_after', lambda _ip: 30)
    assert http.post(f'/cases/{case_id}/identify', json={'answers': [answer]}).status_code == 429
    assert store.get(case_id).version == before
    assert not [f for f in store.get(case_id).facts if f.field == question['field']]
    monkeypatch.setattr(routes, 'identify_retry_after', lambda _ip: None)
    assert http.post(f'/cases/{case_id}/identify', json={'answers': [answer]}).status_code == 200
    saved = store.get(case_id)
    assert saved.version == before + 1, 'answers and result are one compare-and-swap'
    assert [f.value for f in saved.facts if f.field == question['field']] == ['yes']


def test_answers_need_a_stored_identification(client):
    http, _ = client
    case_id = described(http)
    reply = http.post(f'/cases/{case_id}/identify', json={'answers': [{'question_id': 'choice_9.10.15.5.', 'answer': 'y'}]})
    assert reply.status_code == 422


def test_acceptable_solution_wording_is_a_valid_departure(client):
    http, _ = client
    case_id = described(http)
    http.post(f'/cases/{case_id}/identify', json={})
    ok = http.post(f'/cases/{case_id}/identify/benchmark', json={
        'provision': '9.10.15.5.(8)', 'departure': 'Departs from the acceptable solution by a 450 mm soffit.'})
    assert ok.status_code == 200 and ok.json()['benchmark']['departure_status'] == 'confirmed'


@pytest.fixture
def no_network(monkeypatch):
    """Any socket connect or real HTTP request fails the test."""
    import socket
    import httpx
    calls = []

    def refuse(*args, **kwargs):
        calls.append(args[:2])
        raise AssertionError('network call in offline mode')
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(socket.socket, 'connect_ex', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', refuse)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', refuse)
    for name in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'JEV_API_KEY', 'TYPESAFE_API_KEY'):
        monkeypatch.setenv(name, 'dummy-' + 'x' * 30)
    return calls


@pytest.mark.parametrize('live', ['0', '1'])
def test_fake_mode_never_reaches_the_network_with_keys_set(codes, no_network, monkeypatch, client, live):
    from engine import cli_sut
    from engine.identify import identify as default_identify
    from engine.relevance import live_judge
    monkeypatch.setenv('BATATIS_LIVE', live)
    out = cli_sut.run(SOFFIT, codes.db_path)                       # default Judge() and ClaudeVerifier(db)
    assert out['articles'] and 'fallback' not in out['trace']['ranker']
    assert default_identify(SOFFIT, codes.db_path).ranked
    assert ClaudeVerifier(codes.db_path).verify(SOFFIT, ['9.10.15.5.']).stop_reason == 'end_turn'
    if live == '1':                                                # the relevance route's live judge, fake transport
        assert live_judge().judge(SOFFIT, articles(Path(codes.db_path)), ['9.10.15.5.'])
    assert run(SOFFIT, codes=codes).result.mode == 'fake'
    http, _ = client
    case_id = described(http)
    assert http.post(f'/cases/{case_id}/identify', json={}).json()['mode'] == 'fake'
    assert no_network == []


def test_without_the_live_switch_nothing_reaches_the_network(codes, no_network, monkeypatch):
    monkeypatch.delenv('BATATIS_PROVIDER')
    from engine import cli_sut
    out = cli_sut.run(SOFFIT, codes.db_path)
    assert out['trace']['ranker'] == 'bm25 fallback' and not any(a['committed'] for a in out['articles'])
    assert run(SOFFIT, codes=codes).result.mode == 'bm25_fallback'
    with pytest.raises(RuntimeError):
        ClaudeVerifier(codes.db_path)
    assert no_network == []


def test_live_mode_never_builds_anthropic_by_default(codes, no_network, monkeypatch):
    monkeypatch.delenv('BATATIS_PROVIDER')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    import anthropic
    monkeypatch.setattr(anthropic, 'Anthropic', lambda *a, **k: pytest.fail('Anthropic client built'))
    assert transports().anthropic is None
    with pytest.raises(RuntimeError, match='not a configured identify provider'):
        ClaudeVerifier(codes.db_path)
    assert no_network == []


def test_stale_expected_version_is_a_409_and_changes_nothing(client):
    http, store = client
    case_id = described(http)
    result = http.post(f'/cases/{case_id}/identify', json={}).json()
    version = result['case_version']
    assert version == store.get(case_id).version
    first = result['articles'][0]['provision']
    stale = version - 1
    assert http.post(f'/cases/{case_id}/identify/{first}/decision',
                     json={'decision': 'yes', 'expected_version': stale}).status_code == 409
    assert http.post(f'/cases/{case_id}/identify/confirm',
                     json={'provisions': ['9.10.15.5.(8)'], 'expected_version': stale}).status_code == 409
    assert http.post(f'/cases/{case_id}/identify/benchmark', json={
        'provision': '9.10.15.5.(8)', 'departure': 'A 450 mm soffit.', 'expected_version': stale}).status_code == 409
    assert http.post(f'/cases/{case_id}/identify', json={'expected_version': stale}).status_code == 409
    case = store.get(case_id)
    assert case.version == version and case.provisions == [] and case.identify.benchmark.basis != 'applicant'
    yes = http.post(f'/cases/{case_id}/identify/{first}/decision', json={'decision': 'yes', 'expected_version': version})
    assert yes.status_code == 200 and yes.json()['case_version'] == version + 1
    assert yes.json()['section_c'] and all(r['provision_id'].startswith(first) for r in yes.json()['section_c'])
    assert http.post(f'/cases/{case_id}/identify/{first}/decision',
                     json={'decision': 'no', 'expected_version': version}).status_code == 409


def test_identify_run_is_one_cas_and_a_write_during_it_is_a_409(client, monkeypatch):
    http, store = client
    case_id = described(http)
    real = fakes.fake_jev_ask

    def edits_midway():
        ask, done = real(), []

        def inner(state, questions, timeout):
            if not done:
                done.append(1)
                case = store.get(case_id)
                case.title = 'edited during the run'
                store.put(case, expected_version=case.version)
            return ask(state, questions, timeout)
        return inner
    monkeypatch.setattr(fakes, 'fake_jev_ask', edits_midway)
    reply = http.post(f'/cases/{case_id}/identify', json={})
    assert reply.status_code == 409
    case = store.get(case_id)
    assert case.identify is None and case.title == 'edited during the run'
