"""Saved drafting through the actual HTTP guard, file store, source collector and export projection.

The scripted JSON connection tests mechanics and failure gates; it is not a live-provider quality eval.
"""
from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas

from engine import drafting_sources, provider_routing
from engine.api import create_app
from engine.ccmc import Assessment, RegistrySearch, RegistryUnavailable
from engine.codes import Codes
from engine.drafting_provider import DraftingProvider, DraftingUnavailable, configured_provider
from engine.drafting_questions import open_questions
from engine.completeness import check_completeness
from engine.export import ExportBlocked, export_case, form_path
from engine.export.scc import confirmed_values
from engine.models import Case, Fact, Source
from engine.models_drafting import WordingDraft, assembled_text
from engine.models_intake import DocumentReview, EvidenceRef, IntakeRecord, ReviewFact
from engine.process_fields import process_fields
from engine.section_c import section_c_rows
from engine.store import CaseStore
from engine.tests.test_accounts import onboard, signup

DESCRIPTION = 'The applicant proposes a timber wall panel with a drained cavity at the window opening.'
PAGE = 'The concept drawing shows a timber wall panel, a drained cavity and a window head flashing.'


def pdf(*pages):
    stream = io.BytesIO()
    canvas = Canvas(stream)
    for text in pages:
        canvas.drawString(35, 750, text)
        canvas.showPage()
    canvas.save()
    return stream.getvalue()


def fact(field, value):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='description' if field == 'project.description' else 'answer',
                              quote=str(value)))


class Registry:
    def __init__(self):
        self.calls = []
        self.fail = False

    def search(self, query, limit):
        self.calls.append((query, limit))
        if self.fail:
            raise RegistryUnavailable('private transport failure')
        return RegistrySearch(query=query, searched_date='2026-10-26', registry_date='2026-10-20',
            source='snapshot', cached=True, total_matches=1, notice='Offline snapshot; current status unverified.',
            results=[Assessment(number='12345-R', title='SYNTHETIC timber panel', manufacturer='Synthetic Inc',
                assessment_kind='evaluation', report_url='https://nrc.canada.ca/synthetic-report')],
            message='One discovery lead; scope and edition unverified.')


class Connection:
    def __init__(self):
        self.calls = []
        self.change = None
        self.audit_change = None
        self.after_generation = None

    def call(self, name, system, user, schema):
        context = json.loads(user)
        self.calls.append((name, system, context, schema))
        if name == 'applicant_drafts':
            source = next(s for s in context['sources'] if s['kind'] == 'description')
            passage = source['text']
            citation = {'source_id': source['id'], 'quote': passage}
            plans = {
                'evidence_plan': 'Ask the designer for the wall-to-window detail and the basis for evaluating water drainage at that junction.',
                'process.rationale': 'Ask the designer to document the departure and comparison method for the wall panel and window junction.',
                'process.risk_assessment': 'Ask the responsible designer to assess water entry at the wall-to-window junction and document remaining uncertainty.',
                'process.mitigating_measures': 'Request the proposed flashing detail and an explanation of how water would drain from the wall-to-window junction.',
                'process.assumptions_and_limits': 'Confirm the intended exposure and installation limits for the wall panel at the window opening.',
                'process.maintenance_operation': 'Ask who will inspect and maintain the wall drainage path at the window opening.',
                'process.qualifications': 'Ask who takes responsibility for the wall-to-window detail and the comparison method, with their scope and qualifications.',
            }
            drafts = []
            for field in context['fields']:
                kind, text = ('fact', passage) if field == 'alternative_description' else (
                    'plan', plans.get(field, 'Ask the designer to explain the wall-to-window detail against the confirmed benchmark.'))
                citations = [citation]
                if field.startswith('section_c.'):
                    code = next(s for s in context['sources'] if s['kind'] == 'code')
                    citations.append({'source_id': code['id'], 'quote': code['text'][:100]})
                drafts.append({'field': field, 'claims': [{'kind': kind, 'text': text, 'sources': citations}],
                    'questions': [{'text': 'Who will document the wall-to-window detail?',
                        'why': 'The proposed wall and window junction needs a named author and documented scope.',
                        'routed_to': 'professional', 'sources': [citation]}]})
            result = {'drafts': drafts}
            if self.change:
                self.change(result, context)
            if self.after_generation:
                self.after_generation()
            return result, {'input_tokens': 200, 'output_tokens': 300}
        result = {'issues': [], 'items': [{'key': item['key'], 'source_ids': [s['source_id'] for s in item['sources']],
            'supported': True, 'reason': 'The quoted proposal identifies this junction; the request preserves the need for future designer work.',
            'boundary': item['kind']} for item in context['items']]}
        if self.audit_change:
            self.audit_change(result)
        return result, {'input_tokens': None, 'output_tokens': None}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('BATATIS_AI_ACCESS_CODES', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '0')
    monkeypatch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret"}')
    store, codes, connection, registry = CaseStore(tmp_path / 'drafts.sqlite'), Codes(), Connection(), Registry()
    provider = DraftingProvider(connection.call, 'injected-test', 'synthetic-json', 'medium')
    api = create_app(store, codes, drafting_provider_factory=lambda ip: provider, drafting_registry=registry)
    with TestClient(api, base_url='http://localhost') as client:
        assert signup(client).status_code == 201
        owner = onboard(client)
        case = store.put(Case(owner_id=owner['id'], authority='edmonton',
            facts=[fact('project.description', DESCRIPTION)], provisions=['9.27.3.8.(1)'],
            section_c=section_c_rows(['9.27.3.8.(1)'], codes)))
        yield client, store, codes, connection, registry, case


def run(app, case=None):
    client, store, _, _, _, original = app
    current = store.get((case or original).id)
    return client.post(f'/cases/{current.id}/drafts', json={'expected_version': current.version})


def decide(app, case, draft, decision='accept', version=None):
    client, store, *_ = app
    return client.post(f'/cases/{case.id}/drafts/{draft["id"]}/decision',
        json={'expected_version': version or store.get(case.id).version, 'decision': decision})


def test_generation_is_saved_draft_only_and_no_lookup_or_evidence_mutates(app):
    client, store, codes, connection, _, original = app
    assert client.get(f'/cases/{original.id}/drafts').status_code == 404
    result = run(app)
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved['facts'] == [f.model_dump() for f in original.facts]
    assert Case.model_validate(saved).section_c == original.section_c
    assert saved['provisions'] == original.provisions and saved['evidence'] == []
    record = saved['drafting']
    assert 'url' not in record
    assert all('url' not in d and all('url' not in c for c in d['claims']) for d in record['drafts'])
    assert len(record['drafts']) == 9 and all(d['status'] == 'draft' for d in record['drafts'])
    assert all(d['text'] == assembled_text(WordingDraft.model_validate(d).claims) for d in record['drafts'])
    assert record['generations'][0]['audit_input_tokens'] is None
    assert any(s['kind'] == 'precedent_structure' and s['metadata']['structure_only'] for s in record['sources'])
    assert any(s['kind'] == 'guidance' and 'comparison' in s['text'].lower() for s in record['sources'])
    assert len(connection.calls) == 2
    assert client.get(f'/cases/{original.id}/drafts').json()['stale'] is False
    assert client.get(f'/cases/{original.id}').json()['drafting']['stale'] is False
    again = run(app)
    assert again.json()['version'] == saved['version'] and len(connection.calls) == 2
    reopened = CaseStore(store.path).get(original.id)
    assert reopened.drafting.drafts[0].text == record['drafts'][0]['text']
    assert all(f.answer is None for f in process_fields(reopened, codes))


def test_accept_is_canonical_confirmed_pointed_idempotent_and_preserves_provenance(app):
    _, store, codes, _, _, case = app
    generated = run(app).json()
    draft = next(d for d in generated['drafting']['drafts'] if d['field'] == 'process.rationale')
    response = decide(app, case, draft, version=generated['version'])
    assert response.status_code == 200, response.text
    saved = response.json()
    added = saved['facts'][-1]
    assert (added['field'], added['kind'], added['status']) == ('process.rationale', 'pointed', 'confirmed')
    assert added['source'] == {'type': 'user_click', 'ref': 'applicant-draft:' + draft['id'],
                               'quote': draft['text'], 'page': None, 'bbox': None}
    assert process_fields(store.get(case.id), codes)[0].answer.value == draft['text']
    assert saved['drafting']['sources'] == generated['drafting']['sources']
    repeated = decide(app, case, draft, version=generated['version'])
    assert repeated.status_code == 200 and repeated.json()['version'] == saved['version']
    assert len(repeated.json()['facts']) == len(saved['facts'])
    assert decide(app, case, draft, 'reject').status_code == 409
    assert repeated.json()['drafting']['stale'] is False


def test_actual_intake_rough_b_is_offered_for_explicit_replacement_with_original_provenance(app):
    client, store, _, connection, _, case = app
    text = 'We propose a timber wall panel instead of the usual wall construction. The window head has a drained cavity.'
    intake = client.post(f'/cases/{case.id}/intake', json={'text': text, 'model': False,
                                                        'expected_version': case.version})
    assert intake.status_code == 200, intake.text
    rough = next(f for f in reversed(store.get(case.id).facts) if f.field == 'alternative_description')
    assert rough.status == 'confirmed' and rough.value != text
    generated = run(app)
    assert generated.status_code == 200, generated.text
    b = next(d for d in generated.json()['drafting']['drafts'] if d['field'] == 'alternative_description')
    assert b['replaces_fact_id'] == rough.id
    assert confirmed_values(store.get(case.id))['alternative_description'] == rough.value
    accepted = decide(app, case, b)
    assert accepted.status_code == 200, accepted.text
    saved = store.get(case.id)
    assert confirmed_values(saved)['alternative_description'] == b['text']
    assert next(f for f in saved.facts if f.id == rough.id) == rough
    assert any(s.ref == rough.id for s in saved.drafting.sources)
    assert saved.facts[-1].source.ref == 'applicant-draft:' + b['id']
    assert 'alternative_description' not in drafting_sources.read_inputs(saved, store, app[2]).fields


def test_rough_b_draft_never_replaces_a_later_manual_answer(app):
    client, store, _, _, _, case = app
    text = 'We propose a timber wall panel instead of the usual wall. The window head has a drained cavity.'
    client.post(f'/cases/{case.id}/intake', json={'text': text, 'model': False, 'expected_version': case.version})
    generated = run(app).json()
    b = next(d for d in generated['drafting']['drafts'] if d['field'] == 'alternative_description')
    store.add_fact(case.id, fact('alternative_description', 'My intentional revised applicant wording'))
    assert decide(app, case, b).status_code == 409
    assert confirmed_values(store.get(case.id))['alternative_description'] == 'My intentional revised applicant wording'
    regenerated = run(app).json()
    assert not any(d['field'] == 'alternative_description' and d['status'] == 'draft'
                   for d in regenerated['drafting']['drafts'])


def test_reject_writes_no_fact_and_regeneration_keeps_decisions_not_duplicate_active_fields(app):
    _, store, _, _, _, case = app
    first = run(app).json()
    accepted = first['drafting']['drafts'][0]
    rejected = first['drafting']['drafts'][1]
    assert decide(app, case, accepted).status_code == 200
    assert decide(app, case, rejected, 'reject').status_code == 200
    before = store.get(case.id)
    second = run(app)
    assert second.status_code == 200, second.text
    saved = second.json()
    assert saved['facts'] == [f.model_dump() for f in before.facts]
    assert {d['id'] for d in saved['drafting']['drafts'] if d['status'] != 'draft'} == {accepted['id'], rejected['id']}
    active = [d for d in saved['drafting']['drafts'] if d['status'] == 'draft']
    assert len(active) == len({d['field'] for d in active}) == 8
    assert accepted['field'] not in {d['field'] for d in active}
    assert len(saved['drafting']['generations']) == 2


@pytest.mark.parametrize('change', [
    lambda raw, ctx: raw['drafts'][0]['claims'][0]['sources'][0].update(quote='Invented quotation'),
    lambda raw, ctx: raw['drafts'][0]['claims'][0]['sources'][0].update(source_id='src_absent'),
    lambda raw, ctx: raw['drafts'][0]['claims'][0].update(text='The panel is 98765 mm thick.'),
    lambda raw, ctx: raw['drafts'][0]['claims'][0].update(text='Article 9.99.99.99.(1) applies.'),
    lambda raw, ctx: raw['drafts'][0]['claims'][0].update(text='The wall is safe and equivalent.'),
    lambda raw, ctx: raw['drafts'][0].update(text='Uncited extra prose.'),
    lambda raw, ctx: raw['drafts'].pop(),
])
def test_invalid_or_unsafe_output_never_reaches_saved_case(app, change):
    _, store, _, connection, _, case = app
    connection.change = change
    response = run(app)
    assert response.status_code == 503, response.text
    assert 'no writing was saved' in response.json()['detail']
    assert store.get(case.id).drafting is None and store.get(case.id).version == case.version
    assert len(connection.calls) == 1


def test_real_quote_does_not_make_unsupported_claim_grounded(app):
    _, store, _, connection, _, case = app
    connection.change = lambda raw, ctx: raw['drafts'][0]['claims'][0].update(
        text='The panel includes a concealed steel anchor at the window opening.')
    connection.audit_change = lambda raw: raw['items'][0].update(supported=False,
        reason='The actual source describes timber and drainage, and does not state a steel anchor exists.')
    response = run(app)
    assert response.status_code == 503 and store.get(case.id).drafting is None
    assert len(connection.calls) == 2


def test_applicant_code_allegation_is_not_whitelisted_legal_authority(app):
    _, store, _, connection, _, case = app
    store.add_fact(case.id, fact('claimed_provision', '9.10.9.16.(1)'))

    def invent(raw, context):
        allegation = next(s for s in context['sources'] if s.get('metadata', {}).get('field') == 'claimed_provision')
        raw['drafts'][0]['claims'][0].update(text='Article 9.10.9.16.(1) applies.', sources=[
            {'source_id': allegation['id'], 'quote': allegation['text']}])
    connection.change = invent
    assert run(app).status_code == 503
    assert store.get(case.id).drafting is None


def test_unresolved_professional_screen_cannot_become_a_mandatory_engineer_claim(app):
    _, store, _, connection, _, case = app
    connection.change = lambda raw, ctx: raw['drafts'][0]['claims'][0].update(text='An engineer is required for this panel.')
    assert run(app).status_code == 503
    assert store.get(case.id).drafting is None


@pytest.mark.parametrize('change', [
    lambda raw: raw['items'].pop(),
    lambda raw: raw['issues'].append('The evidence plan is an irrelevant generic catalogue.'),
    lambda raw: raw['items'][0].update(boundary='professional_work'),
])
def test_incomplete_or_failed_semantic_audit_fails_closed(app, change):
    _, store, _, connection, _, case = app
    connection.audit_change = change
    assert run(app).status_code == 503
    assert store.get(case.id).drafting is None


def test_all_owned_pdf_pages_are_sources_and_old_review_facts_need_current_quotes(app):
    _, store, _, connection, _, case = app
    owned = store.put_file(case.id, 'concept.pdf', pdf(PAGE, '', 'Product: TimberPanelX'))
    other = store.put(Case())
    foreign = store.put_file(other.id, 'foreign.pdf', pdf('FOREIGN_SECRET'))
    current = store.get(case.id)
    current.intake = IntakeRecord(review=DocumentReview(status='live', facts=[
        ReviewFact(text='Untrusted paraphrase not used', status='proposed',
                   evidence=[EvidenceRef(source_ref=owned['id'], page=1, quote='timber wall panel')]),
        ReviewFact(text='Old assertion', status='tested',
                   evidence=[EvidenceRef(source_ref=owned['id'], page=1, quote='REMOVED_SOURCE')]),
        ReviewFact(text='Foreign assertion', status='stated',
                   evidence=[EvidenceRef(source_ref=foreign['id'], page=1, quote='FOREIGN_SECRET')]),
    ]))
    store.put(current, expected_version=current.version)
    response = run(app)
    assert response.status_code == 200, response.text
    sources = response.json()['drafting']['sources']
    pages = [s for s in sources if s['kind'] == 'document']
    assert {(s['ref'], s['page']) for s in pages} == {(owned['id'], 1), (owned['id'], 3)}
    assert any(s['ref'] == 'review:0' for s in sources)
    assert not any(s['ref'] in {'review:1', 'review:2'} for s in sources)
    sent = json.dumps(connection.calls)
    assert PAGE in sent and 'FOREIGN_SECRET' not in sent and 'Untrusted paraphrase' not in sent
    assert any('no readable text' in n for n in response.json()['drafting']['notices'])


def test_registry_results_are_actual_dated_discovery_leads_and_failure_is_explicit(app):
    _, store, _, _, registry, case = app
    store.add_fact(case.id, fact('product', 'TimberPanelX'))
    response = run(app)
    assert response.status_code == 200
    assert registry.calls == [('TimberPanelX', 5)]
    search = response.json()['drafting']['registry_searches'][0]
    assert search['source'] == 'snapshot' and search['results'][0]['number'] == '12345-R'
    assert search['searched_date'] == '2026-10-26'
    store.add_fact(case.id, fact('product', 'OtherPanel'))
    registry.fail = True
    response = run(app)
    assert response.status_code == 200, response.text
    assert response.json()['drafting']['registry_searches'] == []
    assert any('no negative conclusion' in n for n in response.json()['drafting']['notices'])


@pytest.mark.parametrize('text,expected', [
    ('We call our proposed board BTRboard.', 'BTRboard'),
    ('We propose **EPW NailBase CI-50** at the wall.', 'EPW NailBase CI-50'),
    ('We propose Example FireSeal 200 for the window penetration.', 'Example FireSeal 200'),
    ('Our team calls this panel AeroCore. The window opening has a cavity.', 'AeroCore'),
])
def test_natural_product_names_really_search_registry_with_verified_exact_source_spans(app, text, expected):
    client, store, _, _, registry, case = app
    response = client.post(f'/cases/{case.id}/intake', json={'text': text + ' ' + DESCRIPTION,
        'model': False, 'expected_version': case.version})
    assert response.status_code == 200, response.text
    generated = run(app)
    assert generated.status_code == 200, generated.text
    assert (expected, 5) in registry.calls
    record = generated.json()['drafting']
    query = next(q for q in record['registry_queries'] if q['query'] == expected)
    source = next(s for s in record['sources'] if s['id'] == query['source_id'])
    assert source['text'][query['start']:query['end']] == query['quote']
    assert query['query'] == ' '.join(query['quote'].split())
    assert any(s['query'] == expected for s in record['registry_searches'])


def test_generic_headings_personal_data_and_code_numbers_do_not_become_product_queries(app):
    _, store, _, _, registry, case = app
    store.add_fact(case.id, fact('project.description',
        DESCRIPTION + ' **Risk Assessment**. Contact Priya Natarajan. NBC 2023 and ISO 17025 are mentioned.'))
    assert run(app).status_code == 200
    assert registry.calls == []


def test_accepted_registry_lead_retains_its_original_query_span_after_regeneration(app):
    _, store, _, connection, _, case = app
    store.add_fact(case.id, fact('product', 'TimberPanelX'))

    def cite_registry(raw, context):
        registry = next(s for s in context['sources'] if s['kind'] == 'registry')
        plan = next(d for d in raw['drafts'] if d['field'] == 'evidence_plan')
        plan['claims'][0]['sources'].append({'source_id': registry['id'], 'quote': registry['text']})

    connection.change = cite_registry
    first = run(app).json()
    plan = next(d for d in first['drafting']['drafts'] if d['field'] == 'evidence_plan')
    assert decide(app, case, plan).status_code == 200
    store.add_fact(case.id, fact('product', 'AeroCoreX'))
    connection.change = None
    response = run(app)
    assert response.status_code == 200, response.text
    record = response.json()['drafting']
    original = next(q for q in record['registry_queries'] if q['query'] == 'TimberPanelX')
    source = next(s for s in record['sources'] if s['id'] == original['source_id'])
    assert source['text'][original['start']:original['end']] == original['quote'] == 'TimberPanelX'
    assert {'TimberPanelX', 'AeroCoreX'} <= {s['query'] for s in record['registry_searches']}


def test_accepting_narrative_keeps_real_gap_questions_and_does_not_complete_evidence(app):
    client, store, codes, _, _, case = app
    generated = run(app).json()
    risk = next(d for d in generated['drafting']['drafts'] if d['field'] == 'process.risk_assessment')
    assert decide(app, case, risk).status_code == 200
    saved = store.get(case.id)
    pending = open_questions(saved, accepted_only=True)
    assert len(pending) == 1 and pending[0].draft_id == risk['id']
    key = pending[0].field
    gaps = check_completeness(saved, codes)
    assert not any(g.id == 'D09:risk_assessment' for g in gaps)
    # A visible warning: the applicant has no screen to answer it until the question flow provides one.
    assert any(g.field == key and g.severity == 'warning' and g.routed_to == 'professional' for g in gaps)
    assert any(g['field'] == key for g in client.get(f'/cases/{case.id}/gaps').json()['items'])
    assert any(g.id.startswith('evidence:') for g in gaps)
    assert saved.evidence == []
    from engine.export.scc import blockers, load_field_map
    assert not any(risk['questions'][0]['text'] in reason for reason in blockers(saved, load_field_map(), codes))
    # The separate question flow can answer the stable key with actual applicant words; accepting prose never does so.
    store.add_fact(case.id, fact(key, 'Not sure'))
    assert open_questions(store.get(case.id), accepted_only=True)
    store.add_fact(case.id, fact(key, 'The appointed designer will supply the wall-to-window detail; scope remains to be assessed.'))
    saved = store.get(case.id)
    assert open_questions(saved, accepted_only=True) == []
    assert any(g.id.startswith('evidence:') for g in check_completeness(saved, codes))
    assert saved.evidence == []
    with pytest.raises(ExportBlocked):
        export_case(saved, codes=codes)


def test_archived_accepted_wording_retains_history_without_obsolete_field_gaps(app):
    _, store, codes, _, _, case = app
    generated = run(app).json()
    risk = next(d for d in generated['drafting']['drafts'] if d['field'] == 'process.risk_assessment')
    assert decide(app, case, risk).status_code == 200
    store.add_fact(case.id, fact('process.risk_assessment', 'Applicant replaced this explanation with their own current text.'))
    saved = store.get(case.id)
    assert any(d.id == risk['id'] and d.questions for d in saved.drafting.drafts)
    assert not open_questions(saved, accepted_only=True)
    assert any(g.id.startswith('evidence:') for g in check_completeness(saved, codes))


def test_staleness_detects_file_bytes_even_without_case_version_change_and_reads_are_inert(app):
    client, store, _, connection, registry, case = app
    upload = store.put_file(case.id, 'concept.pdf', pdf(PAGE))
    generated = run(app).json()
    with store.account_db() as db:
        db.execute('UPDATE case_files SET data=? WHERE id=?', (pdf('Changed drawing'), upload['id']))
    assert store.get(case.id).version == generated['version']
    assert client.get(f'/cases/{case.id}/drafts').json()['stale'] is True
    assert client.get(f'/cases/{case.id}').json()['drafting']['stale'] is True
    assert len(connection.calls) == 2 and registry.calls == []
    assert decide(app, case, generated['drafting']['drafts'][0]).status_code == 409


@pytest.mark.parametrize('change', ['fact', 'delete_file', 'replace_file', 'delete_case', 'submit'])
def test_slow_generation_rechecks_current_facts_bytes_access_and_cas(app, change):
    _, store, _, connection, _, case = app
    upload = store.put_file(case.id, 'concept.pdf', pdf(PAGE))

    def mutate():
        if change == 'fact':
            store.add_fact(case.id, fact('storeys', 2))
        elif change == 'delete_case':
            store.delete(case.id)
        elif change == 'submit':
            current = store.get(case.id)
            current.status = 'submitted'
            store.put(current, expected_version=current.version)
        else:
            with store.account_db() as db:
                if change == 'delete_file':
                    db.execute('DELETE FROM case_files WHERE id=?', (upload['id'],))
                else:
                    db.execute('UPDATE case_files SET data=? WHERE id=?', (pdf('New bytes'), upload['id']))
    connection.after_generation = mutate
    response = run(app)
    assert response.status_code == (404 if change == 'delete_case' else 409), response.text
    current = store.get(case.id)
    assert current is None or current.drafting is None


def test_revisions_are_not_overwritten_and_bad_versions_or_client_text_are_rejected(app):
    client, store, _, _, _, case = app
    generated = run(app).json()
    draft = generated['drafting']['drafts'][0]
    store.add_fact(case.id, fact(draft['field'], 'Applicant revised wording'))
    assert decide(app, case, draft, version=generated['version']).status_code == 409
    assert decide(app, case, draft).status_code == 409
    path = f'/cases/{case.id}/drafts/{draft["id"]}/decision'
    assert client.post(path, json={'expected_version': store.get(case.id).version,
                                 'decision': 'accept', 'text': 'Client injection'}).status_code == 422
    assert client.post(f'/cases/{case.id}/drafts', json={'expected_version': True}).status_code == 422
    assert client.post(f'/cases/{case.id}/drafts', json={'expected_version': 1}).status_code == 409
    assert confirmed_values(store.get(case.id))[draft['field']] == 'Applicant revised wording'


def test_decision_cas_cannot_lose_a_concurrent_applicant_edit(app, monkeypatch):
    _, store, _, _, _, case = app
    generated = run(app).json()
    draft = generated['drafting']['drafts'][0]
    original_put = store.put

    def race(saved, *, expected_version=None, expected_files=None):
        store.add_fact(case.id, fact('alternative_description', 'Concurrent applicant answer'))
        return original_put(saved, expected_version=expected_version, expected_files=expected_files)

    monkeypatch.setattr(store, 'put', race)
    response = decide(app, case, draft)
    assert response.status_code == 409
    saved = store.get(case.id)
    assert saved.drafting.drafts[0].status == 'draft'
    assert confirmed_values(saved)['alternative_description'] == 'Concurrent applicant answer'
    assert not any(f.source.ref.startswith('applicant-draft:') for f in saved.facts)


@pytest.mark.parametrize('stage', ['generation', 'decision'])
def test_file_bytes_are_rechecked_under_the_final_write_lock(app, monkeypatch, stage):
    _, store, _, _, _, case = app
    uploaded = store.put_file(case.id, 'detail.pdf', pdf(PAGE))
    generated = run(app).json() if stage == 'decision' else None
    original_put = store.put

    def race(saved, *, expected_version=None, expected_files=None):
        with store.account_db() as db:
            db.execute('UPDATE case_files SET data=? WHERE id=?', (pdf('Late file replacement'), uploaded['id']))
        return original_put(saved, expected_version=expected_version, expected_files=expected_files)

    monkeypatch.setattr(store, 'put', race)
    response = decide(app, case, generated['drafting']['drafts'][0]) if generated else run(app)
    assert response.status_code == 409
    saved = store.get(case.id)
    assert saved.drafting is None if stage == 'generation' else saved.drafting.drafts[0].status == 'draft'
    assert not any(f.source.ref.startswith('applicant-draft:') for f in saved.facts)


def test_accepted_or_copied_generated_prose_is_not_reused_as_evidence(app):
    client, store, _, connection, _, case = app
    first = run(app).json()
    accepted = next(d for d in first['drafting']['drafts'] if d['field'] == 'process.rationale')
    assert decide(app, case, accepted).status_code == 200
    copied = store.add_fact(case.id, fact('proposal_notes', accepted['text']))
    store.put_file(case.id, 'previous-draft.pdf', pdf(accepted['text']))
    assert client.get(f'/cases/{case.id}/drafts').json()['stale'] is True
    regenerated = run(app)
    assert regenerated.status_code == 200, regenerated.text
    context = connection.calls[-2][2]
    assert not any(s['kind'] == 'fact' and s['ref'] == copied.facts[-1].id for s in context['sources'])
    assert not any(s['kind'] == 'document' for s in context['sources'])
    assert all('applicant-draft:' not in s['ref'] for s in context['sources'])
    assert any('generated applicant prose excluded' in n for n in context['notices'])


def test_other_applicants_and_reviewers_cannot_generate_or_decide_and_submitted_is_locked(app):
    client, store, _, connection, _, case = app
    generated = run(app).json()
    draft = generated['drafting']['drafts'][0]
    with TestClient(client.app, base_url='http://localhost') as other:
        assert signup(other, 'other@example.test').status_code == 201
        onboard(other)
        assert other.post(f'/cases/{case.id}/drafts', json={'expected_version': generated['version']}).status_code == 404
        assert other.get(f'/cases/{case.id}/drafts').status_code == 404
    current = store.get(case.id)
    current.status = 'submitted'
    store.put(current, expected_version=current.version)
    assert run(app).status_code == 409 and decide(app, case, draft).status_code == 409
    with TestClient(client.app, base_url='http://localhost') as reviewer:
        assert signup(reviewer, 'officer@example.test').status_code == 201
        onboard(reviewer, 'reviewer')
        assert reviewer.get(f'/cases/{case.id}/drafts').status_code == 200
        assert reviewer.post(f'/cases/{case.id}/drafts', json={'expected_version': store.get(case.id).version}).status_code == 404
    assert len(connection.calls) == 2


def test_personal_data_is_scrubbed_from_all_outbound_source_text(app):
    _, store, _, connection, registry, case = app
    store.add_fact(case.id, fact('owner', 'Priya Natarajan'))
    store.add_fact(case.id, fact('project.description', DESCRIPTION + ' Contact Priya Natarajan at priya@example.test.'))
    store.put_file(case.id, 'Priya Natarajan.pdf', pdf('Prepared by Priya Natarajan. ' + PAGE))
    assert run(app).status_code == 200
    sent = json.dumps(connection.calls)
    assert 'Priya' not in sent and 'Natarajan' not in sent and 'priya@example.test' not in sent
    assert registry.calls == []


def test_source_truncation_and_unread_files_are_explicit(app, monkeypatch):
    _, store, _, _, _, case = app
    store.put_file(case.id, 'bad.pdf', b'%PDF-broken')
    store.put_file(case.id, 'long.pdf', pdf(PAGE * 4))
    monkeypatch.setattr(drafting_sources, 'MAX_SOURCE_CHARS', 90)
    response = run(app)
    assert response.status_code == 200, response.text
    notices = response.json()['drafting']['notices']
    assert any('truncated' in n for n in notices) and any('not read' in n for n in notices)
    assert all(len(s['text']) <= 90 for s in response.json()['drafting']['sources'])


def test_no_live_provider_means_honest_503_without_canned_drafts(app):
    client, store, codes, connection, registry, case = app
    plain = TestClient(create_app(store, codes, drafting_registry=registry), base_url='http://localhost')
    plain.cookies.update(client.cookies)
    response = plain.post(f'/cases/{case.id}/drafts', json={'expected_version': case.version})
    assert response.status_code == 503 and store.get(case.id).drafting is None
    assert not connection.calls and not registry.calls


def test_desktop_uses_supported_leased_workflow_slot_and_never_hosted_fallback(monkeypatch):
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(provider_routing, 'local_active', lambda: True)
    monkeypatch.setattr(provider_routing, 'local_profile', lambda slot: SimpleNamespace(generation='chatgpt', lease='lease'))
    monkeypatch.setattr(provider_routing, 'local_transport', lambda *a, **kw: calls.append((a, kw)) or
                        (lambda *args: ({'ok': True}, {'input_tokens': None})))
    selected = configured_provider()
    assert selected.provider == 'desktop-workflow:chatgpt'
    assert calls[0][0] == ('document-review',)
    assert calls[0][1]['lease'] == 'lease' and calls[0][1]['model'] == provider_routing.LOCAL_MODEL
    monkeypatch.setattr(provider_routing, 'local_profile', lambda slot: SimpleNamespace(generation='off', lease=''))
    with pytest.raises(DraftingUnavailable):
        configured_provider()


@pytest.mark.skipif(not form_path().exists(), reason='Copyrighted supplied form is not installed in this worktree')
def test_only_accepted_b_and_c_appear_in_export_and_professional_gates_remain(app):
    _, store, codes, _, _, case = app
    generated = run(app).json()
    draft_b = next(d for d in generated['drafting']['drafts'] if d['field'] == 'alternative_description')
    draft_c = next(d for d in generated['drafting']['drafts'] if d['field'].startswith('section_c.'))
    before = export_case(store.get(case.id), draft=True, codes=codes)
    assert not any('Applicant explanation (confirmed wording)' in text for text in before.appendix_text)
    assert decide(app, case, draft_b).status_code == 200
    assert decide(app, case, draft_c).status_code == 200
    saved = store.get(case.id)
    result = export_case(saved, draft=True, codes=codes)
    assert confirmed_values(saved)['alternative_description'] == draft_b['text']
    assert any(draft_b['text'] in text for text in result.appendix_text)
    assert any(draft_c['text'] in text for text in result.appendix_text)
    assert saved.section_c == case.section_c and saved.evidence == []
    with pytest.raises(ExportBlocked):
        export_case(saved, codes=codes)
