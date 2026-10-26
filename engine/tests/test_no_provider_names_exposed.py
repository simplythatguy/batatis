"""No provider name reaches a browser or a downloaded file.

The product owner does not want users to learn which third-party services sit behind Batatis. This holds the
user-visible surface to that: the web source that ships to the browser, the generated wire schema, and a sample
of real route responses (every header and body, the PDF export included) built with TestClient and fakes.

Scope: the scoring provider, by name ("jev") and by vendor ("typesafe"). The privacy notice also names no other
provider. Internal code, docs, environment variable names and server logs are not scanned, because a user cannot
see them. A new web file, route or response field that names the provider fails here.
"""
from __future__ import annotations

import io
import json
import re
import sqlite3
from contextlib import ExitStack, closing
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from engine import llm_gate, schema_export
from engine.api import create_app
from engine.codes import Codes
from engine.export import form_path
from engine.export.sample import sample_case
from engine.identify import Judge
from engine.identify.jevkit import keystore
from engine.models import Fact, Source
from engine.privacy import PRIVACY_NOTICE
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import complete_case, store_with_synthetic_files
from engine.tests.package_review_fixtures import CLEAN_FORM, package, text_pdf
from engine.tests.test_accounts import onboard, signup
from engine.tests.test_relevance import LEGACY_PIN, store_legacy_model, stored_model

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'web'
PROVIDER = re.compile(r'jev|typesafe', re.I)
NOTICE_PROVIDERS = re.compile(r'jev|typesafe|openai|anthropic|claude|gpt', re.I)
# What identify answers must not carry either: it was built neutral for every provider, model and credential.
IDENTIFY_NAMES = re.compile(r'elephant|baseten|openrouter|jev|typesafe|openai|anthropic|claude|\bgpt-?\d|\bluna\b|BATATIS_[A-Z_]+|[A-Z]+_API_KEY', re.I)
TEST_FILE = re.compile(r'\.test\.[cm]?[jt]sx?$')
# Random tokens are not copy: a session cookie could contain these letters by chance.
RANDOM_HEADERS = {'set-cookie', 'cookie'}
DESCRIPTION = ('New two-storey single detached house. The north wall is 0.3 m from the side property line and '
               'the owner wants a 450 mm roof soffit overhang with vented aluminum soffit over that wall.')


# ---------------------------------------------------------------- the scans

def shipped_web_files() -> list[Path]:
    """Everything under web/ that reaches a browser: app source (tests excluded), the page and public assets."""
    files = [p for p in (WEB / 'src').rglob('*') if p.is_file() and not TEST_FILE.search(p.name)]
    files.append(WEB / 'index.html')
    files += [p for p in (WEB / 'public').rglob('*') if p.is_file()]
    return sorted(files)


def text_hits(path: Path, pattern: re.Pattern = PROVIDER) -> list[str]:
    shown = path.relative_to(ROOT) if ROOT in path.parents else path
    text = path.read_text(encoding='utf-8', errors='replace')
    return [f'{shown}:{number}: {line.strip()[:120]}' for number, line in enumerate(text.splitlines(), 1)
            if pattern.search(line)]


def pdf_text(content: bytes) -> str:
    """What a reader of the PDF can see: page text and document metadata. Not raw bytes: compressed
    streams would match a three-letter name by chance."""
    reader = PdfReader(io.BytesIO(content))
    parts = [page.extract_text() or '' for page in reader.pages]
    parts += [str(value) for value in (reader.metadata or {}).values()]
    return '\n'.join(parts)


def leaks(response: httpx.Response, pattern: re.Pattern = PROVIDER) -> list[str]:
    """Where a response names the provider: any header, or the body (a PDF by its text)."""
    where = f'{response.request.method} {response.request.url.path} -> {response.status_code}'
    found = [f'{where}: header {key}: {value[:80]}' for key, value in response.headers.multi_items()
             if key.lower() not in RANDOM_HEADERS and pattern.search(f'{key}: {value}')]
    is_pdf = response.headers.get('content-type', '').startswith('application/pdf')
    body = pdf_text(response.content) if is_pdf else response.text
    for match in list(pattern.finditer(body))[:3]:
        found.append(f'{where}: body ...{body[max(0, match.start() - 50):match.end() + 50]!r}...')
    return found


class Recording(TestClient):
    """A TestClient that keeps what it fetched, so a test scans exactly the responses it made."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.responses: list[httpx.Response] = []

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)
        self.responses.append(response)
        return response


def assert_no_provider(*clients: Recording, at_least: int = 1, pattern: re.Pattern = PROVIDER) -> int:
    responses = [response for client in clients for response in client.responses]
    assert len(responses) >= at_least, f'the scenario made {len(responses)} requests; expected {at_least}'
    found = [hit for response in responses for hit in leaks(response, pattern)]
    assert not found, '\n'.join(found)
    return len(responses)


# ---------------------------------------------------------------- the scans work

def test_the_scans_catch_a_planted_name(tmp_path):
    source = tmp_path / 'Label.tsx'
    source.write_text('const a = 1;\nexport const label = "No Jev score";\n')
    assert len(text_hits(source)) == 1 and 'Label.tsx:2: export const label' in text_hits(source)[0]
    request = httpx.Request('GET', 'http://testserver/planted')
    assert leaks(httpx.Response(200, json={'label': 'Estimate by JEV'}, request=request))
    assert leaks(httpx.Response(200, json={'label': 'TypeSafe gateway'}, request=request))
    assert leaks(httpx.Response(200, json={}, headers={'X-Ranker': 'jev screen+rerank'}, request=request))
    assert leaks(httpx.Response(200, content=text_pdf(['Estimate by Jev']), request=request,
                                headers={'content-type': 'application/pdf'}))
    assert not leaks(httpx.Response(200, json={'label': 'Batatis estimate'}, request=request,
                                    headers={'set-cookie': 'batatis_session=xJEVx'}))


def test_the_scan_covers_the_files_that_ship():
    names = {p.relative_to(ROOT).as_posix() for p in shipped_web_files()}
    assert {'web/index.html', 'web/public/robots.txt', 'web/src/privacy.ts', 'web/src/calm/relevance.ts',
            'web/src/calm/RelevanceRing.tsx', 'web/src/calm/CodeLibrary.tsx',
            'web/src/api/engine.schema.json', 'web/src/api/types.gen.ts'} <= names
    assert not [n for n in names if TEST_FILE.search(n)]


# ---------------------------------------------------------------- what ships to the browser

def test_web_source_that_ships_to_the_browser_names_no_provider():
    hits = [hit for path in shipped_web_files() for hit in text_hits(path)]
    assert not hits, '\n'.join(hits)


def test_the_generated_wire_schema_and_types_name_no_provider():
    for name in ('engine.schema.json', 'types.gen.ts'):
        assert not text_hits(WEB / 'src' / 'api' / name)
    assert not PROVIDER.search(schema_export.render()), 'the schema the engine models generate today'


def test_the_assistant_notice_names_no_provider():
    from engine.privacy import assistant_notice
    for provider in ('anthropic', 'openai', ''):
        assert not NOTICE_PROVIDERS.search(assistant_notice(provider))


def test_the_privacy_notice_names_no_provider():
    assert not NOTICE_PROVIDERS.search(PRIVACY_NOTICE)
    assert not NOTICE_PROVIDERS.search((WEB / 'src' / 'privacy.ts').read_text())


def test_the_accuracy_report_names_no_provider():
    """The contributor report names no provider or model."""
    files = [ROOT / 'docs' / 'accuracy' / 'report.json', ROOT / 'docs' / 'accuracy' / 'report.md']
    hits = [hit for path in files for hit in text_hits(path, IDENTIFY_NAMES)]
    assert not hits, '\n'.join(hits)


# ---------------------------------------------------------------- real route responses

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    llm_gate.reset_for_tests()
    for name in ('BATATIS_LIVE', 'BATATIS_PROVIDER', 'VERCEL', 'BATATIS_STORE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_RELEVANCE_RATE_LIMIT', '100')
    monkeypatch.setenv('BATATIS_RELEVANCE_DAILY_RUNS', '100')
    monkeypatch.setenv('BATATIS_AUTH_RATE_LIMIT', '100')
    monkeypatch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
    yield
    llm_gate.reset_for_tests()


class FakeProvider:
    """The scoring provider's stand-in. `failure` makes it fail as a real outage does: naming the provider."""

    def __init__(self):
        self.failure: Exception | None = None

    def __call__(self, state, questions, timeout):
        if self.failure:
            raise self.failure
        rerank = len(questions) == 60
        return {'answers': {q: {'noul': 0.8 if rerank else 0.25} for q in questions},
                'usage': {'input_tokens': 10, 'output_tokens': 1}}


@pytest.fixture
def world(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    ask = FakeProvider()
    app = create_app(store=store, codes=Codes(),
                     relevance_judge_factory=lambda: Judge(ask=ask, workers=1, attempts=1))
    with Recording(app) as client:
        yield app, client, store, ask


def description_fact(text: str, fact_id: str = 'desc-description') -> dict:
    return {'id': fact_id, 'field': 'project.description', 'value': text, 'kind': 'pointed', 'status': 'confirmed',
            'source': {'type': 'user_text', 'ref': 'Your description', 'quote': text}}


def described_case(client: Recording, text: str = DESCRIPTION) -> str:
    case_id = client.post('/cases').json()['id']
    assert client.post(f'/cases/{case_id}/facts', json=description_fact(text)).status_code == 200
    return case_id


def test_document_review_routes_and_legacy_records_name_no_provider(tmp_path, monkeypatch):
    from engine.intake import model as model_pass
    from engine.intake import review as review_pass

    monkeypatch.setattr(model_pass, 'default_transport', lambda _: (None, 'off'))
    monkeypatch.setattr(review_pass, 'default_transport', lambda _: (review_pass.fake_transport, 'live'))
    store = CaseStore(tmp_path / 'review.sqlite')
    with Recording(create_app(store=store, codes=Codes())) as client:
        case_id = client.post('/cases').json()['id']
        uploaded = client.post(f'/cases/{case_id}/files', content=text_pdf(['A two-storey building.']),
                               headers={'content-type': 'application/pdf', 'x-filename': 'brief.pdf'})
        assert uploaded.status_code == 201
        reviewed = client.post(f'/cases/{case_id}/intake',
                               json={'text': 'Read the attached brief.', 'file_ids': [uploaded.json()['id']]})
        assert reviewed.status_code == 200
        assert reviewed.json()['record']['review']['model'] == 'review-1'
        assert client.get(f'/cases/{case_id}/intake').status_code == 200
        stored = store.get(case_id)
        stored.intake.review.model = 'gpt-6-luna'
        store.put(stored)
        assert client.get(f'/cases/{case_id}').json()['intake']['review']['model'] == 'review-1'
        assert_no_provider(client, at_least=5, pattern=IDENTIFY_NAMES)


def test_relevance_responses_name_no_provider(world, monkeypatch):
    _, client, _, ask = world
    case_id = described_case(client)
    path = f'/cases/{case_id}/relevance'
    assert client.get(path).status_code == 404                                    # not scored yet
    scored = client.post(path)
    assert scored.status_code == 200 and scored.json()['model'] == 'relevance-1'
    assert client.get(path).status_code == 200
    changed = client.post(f'/cases/{case_id}/facts', json=description_fact('A different project.', 'later'))
    assert changed.status_code == 200 and client.get(path).json()['stale'] is True
    # A real outage names the provider in its own error text. The response says nothing about who.
    ask.failure = RuntimeError('Jev batch failed: TypeSafe gateway timeout at jev.example')
    failed = client.post(path)
    assert failed.status_code == 503 and failed.json()['detail'] == 'Relevance scoring unavailable'
    ask.failure = None
    monkeypatch.setenv('BATATIS_RELEVANCE_RATE_LIMIT', '1')
    monkeypatch.setenv('BATATIS_RELEVANCE_RATE_WINDOW_SECONDS', '60')
    first = client.post(path, headers={'x-forwarded-for': '203.0.113.9'})
    limited = client.post(path, headers={'x-forwarded-for': '203.0.113.9'})
    assert (first.status_code, limited.status_code) == (200, 429)
    empty = client.post('/cases').json()['id']
    assert client.post(f'/cases/{empty}/relevance').status_code == 409          # nothing described yet
    assert client.post('/cases/case_missing/relevance').status_code == 404
    assert_no_provider(client, at_least=10)


def test_an_unavailable_scoring_service_names_no_provider(tmp_path, monkeypatch):
    with Recording(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes())) as client:
        case_id = described_case(client)
        off = client.post(f'/cases/{case_id}/relevance')                          # the live switch is off
        monkeypatch.setenv('BATATIS_LIVE', '1')
        monkeypatch.setattr(keystore, 'resolve', lambda provider: None)
        no_credential = client.post(f'/cases/{case_id}/relevance')                # the provider credential is absent
        assert (off.status_code, no_credential.status_code) == (503, 503)
        assert off.json()['detail'] == no_credential.json()['detail'] == 'Relevance scoring unavailable'
        assert_no_provider(client, at_least=4)


def test_the_case_the_client_receives_names_no_provider(world):
    _, client, store, _ = world
    case_id = described_case(client)
    assert client.post(f'/cases/{case_id}/relevance').status_code == 200
    assert client.get(f'/cases/{case_id}').json()['relevance']['model'] == 'relevance-1'
    # A case saved before the public version existed holds the provider's pin in its row. Reads must not repeat it.
    store_legacy_model(store, case_id)
    assert stored_model(store, case_id) == LEGACY_PIN
    assert client.get(f'/cases/{case_id}').json()['relevance']['model'] == 'relevance-1'
    assert client.get(f'/cases/{case_id}/relevance').json()['model'] == 'relevance-1'
    assert client.post(f'/cases/{case_id}/facts', json=description_fact('Edited.', 'edit')).status_code == 200
    for tail in ('gaps', 'process-fields', 'professional', 'jurisdiction/pack'):
        assert client.get(f'/cases/{case_id}/{tail}').status_code == 200, tail
    assert client.get('/jurisdictions').status_code == 200 and client.get('/code/toc').status_code == 200
    assert_no_provider(client, at_least=10)


def test_the_api_description_names_no_provider(world):
    _, client, _, _ = world
    spec = client.get('/openapi.json')
    assert spec.status_code == 200 and '/cases/{case_id}/relevance' in spec.json()['paths']
    assert client.get('/docs').status_code == 200 and client.get('/redoc').status_code == 200
    assert_no_provider(client, at_least=3)


def test_the_privacy_notice_is_served_without_a_provider_name(world):
    _, client, _, _ = world
    served = [client.post('/cases'), client.get('/cases/case_missing'), client.get('/jurisdictions')]
    assert [response.status_code for response in served] == [201, 404, 200]
    for response in served:
        assert response.headers['x-batatis-notice'] == PRIVACY_NOTICE
        assert response.json()['meta']['notice'] == PRIVACY_NOTICE
        assert not NOTICE_PROVIDERS.search(response.headers['x-batatis-notice'])
    assert_no_provider(client, at_least=3)


@pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')
def test_the_export_headers_and_pdf_name_no_provider(world):
    _, client, store, _ = world
    case = store_with_synthetic_files(store, sample_case(Codes()))
    store.add_fact(case.id, Fact.model_validate(description_fact(DESCRIPTION)))
    assert client.post(f'/cases/{case.id}/relevance').status_code == 200         # the case carries a scored record
    final = client.post(f'/cases/{case.id}/export')
    draft = client.post(f'/cases/{case.id}/export', json={'draft': True})
    for response in (final, draft):
        assert response.status_code == 200 and response.headers['content-type'] == 'application/pdf'
        assert 'x-batatis-jurisdiction-notice' in response.headers, 'the export headers are part of the sample'
    assert 'SYNTHETIC' in pdf_text(draft.content), 'the PDF text is readable, so the scan is not vacuous'
    assert_no_provider(client, at_least=3)


def require_identify(client: Recording) -> None:
    if '/cases/{case_id}/identify' not in client.get('/openapi.json').json()['paths']:
        pytest.skip('this branch has no code-identification route')


def test_identify_responses_name_no_provider(world, monkeypatch):
    _, client, _, _ = world
    require_identify(client)
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')                                # offline stand-ins, never a live call
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1000')
    case_id = described_case(client)
    run = client.post(f'/cases/{case_id}/identify')
    assert run.status_code == 200, run.text
    result = run.json()
    assert result['mode'] == 'fake' and result['model_ids'] == {
        'screen': 'relevance-1', 'rerank': 'relevance-1', 'verifier': 'verifier-1'}
    assert client.get(f'/cases/{case_id}/identify').status_code == 200
    stream = client.post(f'/cases/{case_id}/identify', headers={'accept': 'text/event-stream'})
    assert stream.status_code == 200 and 'event: done' in stream.text and '"method": "model"' in stream.text
    shown = result['articles']
    assert shown, 'the fake run returns article cards'
    provision = shown[0]['provision']
    decided = client.post(f"/cases/{case_id}/identify/{provision}/decision", json={'decision': 'not_sure'})
    assert decided.status_code == 200, decided.text
    benchmark = client.post(f'/cases/{case_id}/identify/benchmark', json={
        'provision': provision, 'departure': 'The design uses continuous exterior insulation instead of the listed material.'})
    assert benchmark.status_code == 200, benchmark.text
    assert client.post(f'/cases/{case_id}/identify/confirm', json={'provisions': [provision]}).status_code == 200
    assert client.get(f'/cases/{case_id}/process-refs').status_code == 200
    client.get(f'/cases/{case_id}/information-request')            # the officer draft; its status depends on who asks
    case = client.get(f'/cases/{case_id}')
    assert case.status_code == 200 and case.json()['relevance']['model'] == 'relevance-1'
    assert_no_provider(client, at_least=12, pattern=IDENTIFY_NAMES)


def test_identify_with_the_gate_closed_names_no_provider(world, monkeypatch):
    """No fake selected and no live switch: the run takes the labelled keyword fallback, whose cause names a provider."""
    _, client, _, _ = world
    require_identify(client)
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1000')
    case_id = described_case(client)
    run = client.post(f'/cases/{case_id}/identify')
    assert run.status_code == 200, run.text
    result = run.json()
    assert result['mode'] == 'bm25_fallback' and result['trace']['fallback_reason'] == 'scoring unavailable'
    assert 'scoring unavailable' in result['label'] and result['model_ids'] == {
        'screen': None, 'rerank': None, 'verifier': None}
    stream = client.post(f'/cases/{case_id}/identify', headers={'accept': 'text/event-stream'})
    assert stream.status_code == 200 and 'event: done' in stream.text
    assert client.get(f'/cases/{case_id}/identify').status_code == 200 and client.get(f'/cases/{case_id}').status_code == 200
    assert_no_provider(client, at_least=6, pattern=IDENTIFY_NAMES)


def test_identify_with_a_failing_provider_names_no_provider(world, monkeypatch):
    """The provider fails with an error that names it. The run falls back, and the response does not say who."""
    monkeypatch.setenv('BATATIS_IDENTIFY_SCREEN', 'jev')
    monkeypatch.setenv('BATATIS_IDENTIFY_RERANK', 'jev')
    from engine.identify import fakes
    _, client, _, _ = world
    require_identify(client)

    def outage(state, questions, timeout):
        raise RuntimeError('Jev gateway timeout at jev.example (TypeSafe), OPENAI_API_KEY rejected')
    monkeypatch.setattr(fakes, 'fake_jev_ask', lambda: outage)
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1000')
    case_id = described_case(client)
    run = client.post(f'/cases/{case_id}/identify')
    assert run.status_code == 200 and run.json()['mode'] == 'bm25_fallback', run.text
    stream = client.post(f'/cases/{case_id}/identify', headers={'accept': 'text/event-stream'})
    assert stream.status_code == 200 and 'event: done' in stream.text
    assert_no_provider(client, at_least=4, pattern=IDENTIFY_NAMES)


def test_an_identify_result_stored_before_the_names_were_hidden_is_cleaned_when_read(world, monkeypatch):
    """A row written while identify still returned provider names, as the rows of the first release did."""
    _, client, store, _ = world
    require_identify(client)
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1000')
    case_id = described_case(client)
    assert client.post(f'/cases/{case_id}/identify').status_code == 200
    with closing(sqlite3.connect(store.path)) as con, con:
        raw = json.loads(con.execute('SELECT json FROM cases WHERE id=?', (case_id,)).fetchone()[0])
        identify, trace = raw['identify'], raw['identify']['trace']
        identify['label'] = 'Jev (jev-1.13.0) judged all 2080 Division B articles; gpt-6-luna read the top 15 in full.'
        identify['model_ids'] = {'screen': 'jev-1.13.0', 'rerank': 'jev-1.13.0', 'verifier': 'gpt-6-luna'}
        trace.update(ranker='jev screen + jev rerank', fallback_reason='BATATIS_LIVE is off or the TypeSafe credential is absent',
                     verifier='failed: openai gate: offline-cap',
                     config={'screen': 'jev', 'screen_model': 'jev-1.13.0', 'verifier': 'openai', 'verifier_model': 'gpt-6-luna'},
                     stages=[{'stage': 'screen', 'method': 'jev', 'model': 'jev-1.13.0'}],
                     spend={'jev': {'requests': 21}, 'openai': {'requests': 1}})
        con.execute('UPDATE cases SET json=? WHERE id=?', (json.dumps(raw), case_id))

    def stored():
        with closing(sqlite3.connect(store.path)) as con:
            return con.execute('SELECT json FROM cases WHERE id=?', (case_id,)).fetchone()[0]
    assert IDENTIFY_NAMES.search(stored()), 'the stored row really does name providers'
    assert client.get(f'/cases/{case_id}/identify').status_code == 200
    assert client.get(f'/cases/{case_id}').status_code == 200
    assert_no_provider(client, at_least=4, pattern=IDENTIFY_NAMES)
    # The next write stores the neutral form.
    assert client.post(f'/cases/{case_id}/facts', json=description_fact('Edited.', 'edit')).status_code == 200
    assert not IDENTIFY_NAMES.search(stored())


# ---------------------------------------------------------------- officer review (#53)

def multipart(files):
    return [('files', (name, data, 'application/pdf')) for name, data in files]


@pytest.fixture
def reviewing(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    app = create_app(store=store, codes=Codes())
    with ExitStack() as stack:
        owner = stack.enter_context(Recording(app, base_url='http://localhost'))
        reviewer = stack.enter_context(Recording(app, base_url='http://localhost'))
        assert signup(owner, 'owner@example.test', 'Owner').status_code == 201
        owner_user = onboard(owner, 'applicant', 'edmonton')
        assert signup(reviewer, 'reviewer@example.test', 'Reviewer').status_code == 201
        onboard(reviewer, 'reviewer', 'edmonton')

        def owned(status: str):
            case = complete_case()
            case.owner_id, case.authority, case.status = owner_user['id'], 'edmonton', status
            return store_with_synthetic_files(store, case)

        yield store, owner, reviewer, owned


def test_officer_review_completeness_and_close_out_name_no_provider(reviewing):
    _, owner, reviewer, owned = reviewing
    draft = owned('draft')
    for body in (None, {}, {'variant': 'A'}, {'variant': 'B'}):
        response = owner.post(f'/cases/{draft.id}/completeness', **({} if body is None else {'json': body}))
        assert response.status_code == 200, response.text
    assert owner.post(f'/cases/{draft.id}/completeness', json={'variant': 'C'}).status_code == 503
    assert owner.get(f'/cases/{draft.id}/gaps').status_code == 200

    case = owned('submitted')
    assert reviewer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    first = reviewer.post(f'/review/{case.id}/package-review')
    assert first.status_code == 201, first.text
    items = [{'id': item['id'], 'text': item['text'], 'included': item['included']}
             for item in first.json()['information_request']['items']]
    items.append({'text': 'Please send the stamped drawing set referenced in Section D.', 'included': True,
                  'target': {'section': 'D', 'label': 'Section D · Drawing set'}})
    edited = reviewer.put(f'/review/{case.id}/package-review/1/information-request',
                          json={'items': items, 'intro': 'Officer intro.'})
    assert edited.status_code == 200, edited.text
    sent = reviewer.post(f'/review/{case.id}/package-review/1/information-request/send')
    assert sent.status_code == 200, sent.text
    assert len(owner.get(f'/cases/{case.id}/information-request').json()['requests']) == 1
    assert owner.get(f'/cases/{case.id}/messages').status_code == 200
    assert owner.get('/me/notifications').status_code == 200 and owner.get('/me/applications').status_code == 200
    second = reviewer.post(f'/review/{case.id}/package-review')
    assert second.status_code == 201 and second.json()['diff'] is not None
    index = reviewer.get(f'/review/{case.id}/package-review')
    assert index.status_code == 200 and [s['version'] for s in index.json()['sessions']] == [1, 2]
    assert reviewer.get(f'/review/{case.id}/package-review/2').status_code == 200
    assert reviewer.get(f'/review/{case.id}/close-out').status_code == 404       # no decision yet
    from engine.tests.case_builder_fixtures import acceptance_request
    assert reviewer.post(f'/review/{case.id}/decision', json=acceptance_request(reviewer, case.id, run=False)).status_code == 200
    from datetime import datetime
    from zoneinfo import ZoneInfo
    issued_on = datetime.now(ZoneInfo('America/Edmonton')).date().isoformat()
    assert reviewer.post(f'/review/{case.id}/close-out/issued', json={'issued_on': issued_on}).status_code == 200
    assert reviewer.get(f'/review/{case.id}/close-out').status_code == 200
    assert reviewer.post(f'/review/{case.id}/close-out/sent').status_code == 200
    assert reviewer.get('/review/queue').status_code == 200
    assert_no_provider(owner, reviewer, at_least=25)


def test_officer_uploads_and_standalone_reviews_name_no_provider(reviewing):
    _, _, reviewer, owned = reviewing
    case = owned('submitted')
    assert reviewer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    planted = dict(CLEAN_FORM, Owner='', **{'Date of Reqeuest': '', 'Name Responsible': ''})
    first = reviewer.post(f'/review/{case.id}/package-review', files=multipart(package(planted)))
    assert first.status_code == 201, first.text
    fixed = dict(CLEAN_FORM, **{'Date of Reqeuest': '', 'Lot': 'TBD'})
    second = reviewer.post(f'/review/{case.id}/package-review', files=multipart(package(fixed, flat=True)))
    assert second.status_code == 201 and second.json()['diff']['statement']
    created = reviewer.post('/package-review', files=multipart(package(dict(CLEAN_FORM, Owner=''))))
    assert created.status_code == 201, created.text
    package_id = created.json()['package_id']
    again = reviewer.post(f'/package-review/{package_id}', files=multipart(package()))
    assert again.status_code == 201 and again.json()['version'] == 2
    assert reviewer.get(f'/package-review/{package_id}').status_code == 200
    assert reviewer.get(f'/package-review/{package_id}/2').status_code == 200
    edit = reviewer.put(f'/package-review/{package_id}/2/information-request',
                        json={'items': [{'text': 'Please confirm the owner name.', 'included': True,
                                            'target': {'section': 'A', 'field': 'owner_name', 'label': 'Section A · Owner'}}]})
    assert edit.status_code == 200, edit.text
    unreadable = reviewer.post('/package-review', files=[('files', ('notes.txt', b'hello', 'text/plain'))])
    assert unreadable.status_code == 201 and unreadable.json()['files'][0]['role'] == 'unreadable'
    assert reviewer.post('/package-review', content=b'%PDF-1.4',
                         headers={'content-type': 'application/pdf'}).status_code == 415
    big = [('files', ('big.pdf', b'%PDF' + b'0' * (4 * 1024 * 1024), 'application/pdf'))]
    assert reviewer.post('/package-review', files=big).status_code == 413
    assert_no_provider(reviewer, at_least=12)
