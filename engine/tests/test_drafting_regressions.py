"""Isolated source/provenance regressions. Registry and generation connections are scripted, never live."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import drafting_sources
from engine.completeness import check_completeness
from engine.drafting_questions import open_questions
from engine.drafting_registry import product_queries
from engine.intake import service
from engine.models import Fact, Source
from engine.models_drafting import DraftSource
from engine.models_intake import FactPointer
from engine.tests.test_applicant_drafts import DESCRIPTION, app, decide, fact, pdf, run


def source(text, identity='description'):
    return DraftSource(id=identity, kind='description', ref=identity, label=identity, text=text)


def raw_input(case_id):
    path = Path(__file__).resolve().parents[2] / 'evals_dev/intake_facts/pr30_held_out.json'
    return next(row['text'] for row in json.loads(path.read_text()) if row['id'] == case_id)


@pytest.mark.parametrize('text', [
    'Bedroom 3 has a 400 mm opening.', 'Replaces 11 mm OSB on the wall.',
    'Room 12 contains two windows.', 'Use 11 panels with 400 mm spacing.',
    'Building 5 has 64 dwelling units.', 'Window 7 is narrower.',
    '**Bedroom 3** has a 400 mm opening.', 'Lot 0, Block 0, Plan 1234.',
])
def test_room_numbers_and_quantities_are_not_product_names(text):
    assert product_queries([source(text)]) == []


@pytest.mark.parametrize('text,expected', [
    ('We call our proposed board BTRboard.', 'BTRboard'),
    ('We use EPW NailBase CI-50 at the wall.', 'EPW NailBase CI-50'),
    ('The sealant is Example FireSeal 200.', 'Example FireSeal 200'),
    ('Product: Hilti CP 606', 'Hilti CP 606'),
    ('We named our panel Acme.', 'Acme'),
])
def test_named_and_distinctive_products_keep_exact_source_spans(text, expected):
    original = source(text)
    result = product_queries([original])
    assert [q.query for q in result] == [expected]
    assert original.text[result[0].start:result[0].end] == result[0].quote


@pytest.mark.parametrize('texts,limit', [
    (['EPW NailBase CI-50. Later we use **NailBase CI-50**.'], 3),
    (['EPW NailBase CI-50', 'NailBase CI-50'], 3),
    (['NailBase CI-50', 'EPW NailBase CI-50'], 3),
    (['NailBase CI-50', 'OtherBrand 10', 'EPW NailBase CI-50'], 1),
])
def test_full_product_name_covers_shorter_repetitions_across_sources(texts, limit):
    originals = [source(text, str(index)) for index, text in enumerate(texts)]
    result = product_queries(originals, limit=limit)
    assert [q.query for q in result] == ['EPW NailBase CI-50']
    assert next(s for s in originals if s.id == result[0].source_id).text[
        result[0].start:result[0].end] == result[0].quote


def test_different_numeric_models_remain_different_products():
    assert [q.query for q in product_queries([source('FireSeal 20. FireSeal 200.')])] == ['FireSeal 20', 'FireSeal 200']


def test_actual_raw_manufacturer_intake_searches_only_the_full_product_name(app):
    _, store, codes, _, registry, case = app
    text = raw_input('brief-a-manufacturer')
    extraction = service.run(text, [], codes=codes, transport=None, review_transport=None)
    service.apply(case, text, extraction)
    case = store.put(case, expected_version=case.version)
    bundle = drafting_sources.collect_sources(case, drafting_sources.read_inputs(case, store, codes, include_bytes=True),
                                              registry=registry)
    assert registry.calls == [('EPW NailBase CI-50', 5)]
    assert [q.query for q in bundle.registry_queries] == ['EPW NailBase CI-50']


def intake(app, text, *, file_ids=()):
    client, store, _, _, _, case = app
    response = client.post(f'/cases/{case.id}/intake', json={'text': text, 'file_ids': list(file_ids),
        'model': False, 'expected_version': store.get(case.id).version})
    assert response.status_code == 200, response.text
    return store.get(case.id)


def generation_context(app):
    response = run(app)
    assert response.status_code == 200, response.text
    return response.json(), app[3].calls[-2][2]


def test_withdrawn_description_facts_do_not_reach_the_generator_after_real_intake_runs(app):
    first = intake(app, DESCRIPTION + ' The building has three storeys.')
    original = next(f for f in reversed(first.facts) if f.field == 'storeys')
    assert original.status == 'confirmed' and original.value == 3
    second = intake(app, DESCRIPTION + ' The previous height description is withdrawn; the number of storeys is unknown.')
    assert original in second.facts  # History is retained; it is no longer current source material.
    _, context = generation_context(app)
    assert not any(s['metadata'].get('field') == 'storeys' for s in context['sources'])
    assert any('description' in notice and 'excluded' in notice for notice in context['notices'])


@pytest.mark.parametrize('kind,ref', [('user_text', 'intake answer'), ('user_click', 'Your answer')])
def test_intentional_manual_answers_survive_description_withdrawal(app, kind, ref):
    intake(app, DESCRIPTION + ' The building has three storeys.')
    intake(app, DESCRIPTION + ' The height in the earlier description is withdrawn. Storeys are unknown.')
    _, store, _, _, _, case = app
    store.add_fact(case.id, Fact(field='storeys', value=2, status='confirmed', kind='pointed',
        source=Source(type=kind, ref=ref, quote='Two storeys, confirmed by the applicant.')))
    _, context = generation_context(app)
    values = [s['text'] for s in context['sources'] if s['metadata'].get('field') == 'storeys']
    assert values == ['2']


@pytest.mark.parametrize('from_file', [False, True])
def test_identical_repeated_intake_keeps_rough_b_draftable_without_changing_the_fact(app, from_file):
    _, store, _, _, _, case = app
    text = 'We propose a timber wall panel instead of the usual wall construction.'
    files = [store.put_file(case.id, 'rough.pdf', pdf(text))['id']] if from_file else []
    first = intake(app, DESCRIPTION if from_file else text, file_ids=files)
    rough = next(f for f in reversed(first.facts) if f.field == 'alternative_description')
    second = intake(app, DESCRIPTION if from_file else text, file_ids=files)
    assert next(f for f in reversed(second.facts) if f.field == 'alternative_description') == rough
    generated, _ = generation_context(app)
    draft = next(d for d in generated['drafting']['drafts'] if d['field'] == 'alternative_description')
    assert draft['replaces_fact_id'] == rough.id
    assert decide(app, case, draft).status_code == 200


def test_legacy_description_rough_b_is_verified_without_a_current_intake_pointer(app):
    _, store, _, _, _, case = app
    first = intake(app, 'We propose a timber wall panel instead of the usual wall.')
    rough = next(f for f in reversed(first.facts) if f.field == 'alternative_description')
    first.intake.pointers = []  # Records written before the duplicate-pointer fix.
    store.put(first, expected_version=first.version)
    generated, _ = generation_context(app)
    assert next(d for d in generated['drafting']['drafts'] if d['field'] == 'alternative_description')['replaces_fact_id'] == rough.id


@pytest.mark.parametrize('ref', ['intake answer', 'applicant-draft:already-accepted'])
def test_missing_pointer_never_reclassifies_manual_or_accepted_b(app, ref):
    _, store, _, _, _, case = app
    current = intake(app, 'We propose a timber wall panel instead of the usual wall.')
    rough = next(f for f in reversed(current.facts) if f.field == 'alternative_description')
    store.add_fact(case.id, Fact(field='alternative_description', value=rough.value, kind='pointed', status='confirmed',
                               source=Source(type='user_text' if ref == 'intake answer' else 'user_click',
                                             ref=ref, quote=rough.value)))
    generated, _ = generation_context(app)
    assert not any(d['field'] == 'alternative_description' and d['status'] == 'draft' for d in generated['drafting']['drafts'])


@pytest.mark.parametrize('copy_kind', ['assembled', 'claim', 'labelled_claim'])
def test_pending_generated_passages_stay_excluded_from_facts_and_pdfs_across_three_generations(app, copy_kind):
    _, store, _, connection, _, case = app

    def multi_claim(raw, context):
        risk = next(d for d in raw['drafts'] if d['field'] == 'process.risk_assessment')
        risk['claims'].append({'kind': 'plan', 'text': 'Request a documented account of drainage failure at the window head.',
                               'sources': risk['claims'][0]['sources']})
    connection.change = multi_claim
    first, _ = generation_context(app)
    pending = next(d for d in first['drafting']['drafts'] if d['field'] == 'process.risk_assessment')
    copied = {'assembled': pending['text'], 'claim': pending['claims'][1]['text'],
              'labelled_claim': 'Plan: ' + pending['claims'][1]['text']}[copy_kind]
    copied_fact = fact('copied_notes', copied)
    store.add_fact(case.id, copied_fact)
    copied_file = store.put_file(case.id, 'copied.pdf', pdf(*copied.split('\n\n')))

    def new_wording(raw, context):
        risk = next(d for d in raw['drafts'] if d['field'] == 'process.risk_assessment')
        risk['claims'][0]['text'] = 'Ask the designer for a written account of the window junction and its drainage path.'
    connection.change = new_wording
    second, second_context = generation_context(app)
    assert not any(s['ref'] in {copied_fact.id, copied_file['id']} for s in second_context['sources'])
    assert pending['id'] not in {d['id'] for d in second['drafting']['drafts']}
    store.add_fact(case.id, fact('another_applicant_detail', 'The window head will be documented by the designer.'))
    third, third_context = generation_context(app)
    assert not any(s['ref'] in {copied_fact.id, copied_file['id']} for s in third_context['sources'])
    assert {d['status'] for d in third['drafting']['drafts']} == {'draft'}
    reopened = type(store)(store.path).get(case.id)
    bundle = drafting_sources.collect_sources(reopened, drafting_sources.read_inputs(reopened, store, app[2], include_bytes=True),
                                              registry=app[4])
    assert not any(s.ref in {copied_fact.id, copied_file['id']} for s in bundle.sources)


def test_authentic_source_facts_and_pages_remain_readable_when_claims_copy_them(app, monkeypatch):
    _, store, codes, connection, registry, case = app
    passage = 'The window head includes a drained cavity and a flashing detail.'
    original_fact = fact('authentic_note', passage)
    store.add_fact(case.id, original_fact)
    original_file = store.put_file(case.id, 'original.pdf', pdf(passage))

    def copy_authentic(raw, context):
        original = next(s for s in context['sources'] if s['ref'] == original_fact.id)
        risk = next(d for d in raw['drafts'] if d['field'] == 'process.risk_assessment')
        risk['claims'][0] = {'kind': 'fact', 'text': passage, 'sources': [{'source_id': original['id'], 'quote': passage}]}
    connection.change = copy_authentic
    first, _ = generation_context(app)
    # A later bounded context can omit an authentic source without turning it into generated prose.
    current = store.get(case.id)
    current.drafting.sources = [s for s in current.drafting.sources if s.ref not in {original_fact.id, original_file['id']}]
    store.put(current, expected_version=current.version)
    bundle = drafting_sources.collect_sources(current, drafting_sources.read_inputs(current, store, codes, include_bytes=True), registry=registry)
    assert {original_fact.id, original_file['id']} <= {s.ref for s in bundle.sources}


@pytest.mark.parametrize('alias', ['risk_assessment', 'risk', 'process.risk'])
def test_newer_logical_alias_answer_supersedes_accepted_risk_draft_questions(app, alias):
    _, store, codes, _, _, case = app
    generated, _ = generation_context(app)
    risk = next(d for d in generated['drafting']['drafts'] if d['field'] == 'process.risk_assessment')
    assert decide(app, case, risk).status_code == 200
    store.add_fact(case.id, fact(alias, 'The applicant supplied a newer risk narrative.'))
    current = store.get(case.id)
    assert not open_questions(current, accepted_only=True)
    assert not any(g.id.startswith('draft-question:') for g in check_completeness(current, codes))
    assert next(d for d in current.drafting.drafts if d.id == risk['id']).questions


def test_removed_provision_no_longer_has_accepted_c_question_gaps(app):
    client, store, codes, _, _, case = app
    generated, _ = generation_context(app)
    c_draft = next(d for d in generated['drafting']['drafts'] if d['field'].startswith('section_c.'))
    assert decide(app, case, c_draft).status_code == 200
    response = client.post(f'/cases/{case.id}/section-d', json={'expected_version': store.get(case.id).version,
                                                             'provisions': []})
    assert response.status_code == 200, response.text
    current = store.get(case.id)
    assert not open_questions(current, accepted_only=True)
    assert not any(g.id.startswith('draft-question:') for g in check_completeness(current, codes))
    assert next(d for d in current.drafting.drafts if d.id == c_draft['id']).questions
