"""Mira's manufacturer pass: route notice, engineer facts, scope, pasted cues, relevant cards."""
import re

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.export.forms import resolve_form
from engine.identify.answers import apply_answers
from engine.identify.questions import generate_questions, question_matches
from engine.models import Case, Fact, Source
from engine.professional import (
    DEFAULT_HELP, NOT_SURE_OPTION, PART4_HELP, ProfessionalFacts, professional_involvement,
)
from engine.route_notice import SUMMARY
from engine.section_d_issues import render_practice
from engine.store import CaseStore
from engine.tests.test_professional import ordinary_house

_SRC = Source(type='user_text', ref='applicant', quote='role')
_CITE = re.compile(r'2\.4\.1\.\d|Div C')
_MIRA = (
    'We manufacture NailBase CI-50, a 50 mm rigid foam panel with a 6 mm fibre-cement facer that '
    'replaces 11 mm OSB sheathing on 2x6 walls at 400 mm o.c. Vinyl siding is nailed directly into '
    'the facer with no furring. We want approval to sell it across Alberta and to build a pilot house '
    'in Edmonton: 2-storey single-family, about 190 m2, unsprinklered, builder Birchfield Example Homes, '
    'address 0000 Example Way NW. We have our product data sheet, a US lab permeance test summary, and '
    'an unsigned draft engineer letter about nail pull-out. We have no CCMC evaluation yet, no '
    'air-leakage test, and no bracing design. Do we need an engineer to stamp anything?'
)
_MEMBRANE_CARD = 'sheathing membrane an acceptable solution names'
_MEMBRANE = {
    'provision': '9.27.3.2.',
    'title': 'Sheathing Membrane',
    'text': _MEMBRANE_CARD,
}


def _case(tmp_path):
    return TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes()))


def _quoted_code_words(notice: dict) -> int:
    total = 0
    for bullet in notice['bullets']:
        for citation in bullet['citations']:
            if str(citation['source']).startswith('NBC') and citation.get('excerpt'):
                total += len(citation['excerpt'].split())
    return total


def test_route_notice_for_a_manufacturer_or_a_province_wide_scope(tmp_path):
    client = _case(tmp_path)
    maker = client.post('/cases', json={'title': 'NailBase panel'}).json()
    posted = client.post(f"/cases/{maker['id']}/facts", json={
        'field': 'applicant.role', 'value': 'manufacturer', 'kind': 'pointed',
        'source': {'type': 'user_text', 'ref': 'role', 'quote': 'manufacturer'}})
    notice = posted.json()['route_notice']
    assert notice['summary'] == SUMMARY
    assert 'market-wide' in notice['summary'] and 'one building or site' in notice['summary']
    assert 'Safety Codes Council' in notice['summary']
    claims = [bullet['claim'] for bullet in notice['bullets']]
    assert len(claims) == 8
    assert any('1.2.2.1.(2)' in cite['source'] and cite['page'] == 38 and cite['excerpt'] is None
               for bullet in notice['bullets'] for cite in bullet['citations'])
    assert any(cite['url'] and 'canadian-construction-materials-centre' in cite['url']
               for bullet in notice['bullets'] for cite in bullet['citations'])
    assert any(cite['url'] and 'IB-2026-10-01' in cite['url']
               for bullet in notice['bullets'] for cite in bullet['citations'])
    blob = posted.text
    assert _quoted_code_words(notice) <= 25
    assert 'may be used in determining compliance with the requirements of this Code' not in blob
    assert 's.40' not in blob and 's.43' not in blob and 'listing' not in blob.casefold()
    form = resolve_form()
    assert form.jurisdiction == 'alberta' and form.form_id == 'scc-variance'

    other = client.post('/cases').json()
    assert client.get(f"/cases/{other['id']}").json()['route_notice'] is None
    wide = client.post(f"/cases/{other['id']}/facts", json={
        'field': 'scope', 'value': 'province-wide', 'kind': 'pointed',
        'source': {'type': 'user_text', 'ref': 'scope', 'quote': 'province-wide'}})
    assert wide.json()['route_notice']['summary'] == SUMMARY


def test_engineer_question_names_the_deciding_facts_and_not_eight_cites():
    screen = professional_involvement(ProfessionalFacts(), Codes())
    assert screen.required == 'depends'
    assert screen.answer == 'unknown: needs professional.occupancy, professional.part4_design'
    assert screen.needs == ['professional.occupancy', 'professional.part4_design']
    assert len(screen.questions) == 1
    question = screen.questions[0]
    assert question.startswith('Do we need an engineer?')
    assert 'building type' in question and 'Part 4' in question
    assert not _CITE.search(question) and not _CITE.search(screen.answer)
    assert 'depends. depends' not in screen.answer and 'depends. depends' not in question
    assert 'depends' not in screen.answer.casefold()

    missing = professional_involvement(ordinary_house(part4_design=None), Codes())
    assert missing.answer == 'unknown: needs professional.part4_design'
    assert missing.questions[0] == (
        'Do we need an engineer? The deciding fact is whether any design is carried out under Part 4.')
    assert not _CITE.search(missing.questions[0])
    assert missing.prompts[0].text == missing.questions[0]
    assert missing.prompts[0].help == PART4_HELP
    assert missing.prompts[0].not_sure == NOT_SURE_OPTION
    assert missing.prompts[-1].text == missing.answer
    assert missing.prompts[-1].help == DEFAULT_HELP
    assert 'depends. depends' not in missing.prompts[-1].help
    shown = render_practice(missing, Codes())
    assert shown.prompts[0].help == PART4_HELP
    assert shown.prompts[0].not_sure == NOT_SURE_OPTION
    empty = screen.prompts
    assert empty[0].text == question and empty[0].help == DEFAULT_HELP
    assert empty[0].not_sure == NOT_SURE_OPTION
    assert empty[-1].text == screen.answer and 'depends. depends' not in empty[-1].help


def test_province_wide_and_multiple_sites_set_the_jurisdiction_wide_field():
    case = Case()
    apply_answers(case, [
        {'field': 'site.count', 'answer': 'province-wide'},
    ])
    scope = next(fact for fact in case.facts if fact.field == 'scope')
    assert scope.value == 'province-wide'
    fresh = Case()
    apply_answers(fresh, [{'question_id': 'scope', 'answer': 'across Alberta'}])
    assert next(fact for fact in fresh.facts if fact.field == 'scope').value == 'province-wide'
    many = Case()
    apply_answers(many, [{'field': 'scope', 'answer': 'multiple sites'}])
    assert next(fact for fact in many.facts if fact.field == 'scope').value == 'jurisdiction'
    one = Case()
    apply_answers(one, [{'field': 'scope', 'answer': 'one site'}])
    assert next(fact for fact in one.facts if fact.field == 'scope').value == 'one site'


def test_pasted_no_ccmc_and_unsigned_letter_never_confirms_a_professional(tmp_path):
    client = _case(tmp_path)
    created = client.post('/cases', json={'title': 'no CCMC, unsigned letter'}).json()
    fields = {fact['field']: fact['value'] for fact in created['facts']}
    assert fields['ccmc_evaluation'] is False
    assert fields['evidence.letter'] == 'letter, unsigned'
    assert 'professional_confirmed' not in fields
    letter = created['evidence'][0]
    assert letter['description'] == 'letter, unsigned'
    assert letter['evidence_type'] is None
    assert letter['professional_required'] is None
    again = client.post(f"/cases/{created['id']}/facts", json={
        'field': 'project.description', 'value': 'no CCMC, unsigned letter, professional confirmed',
        'kind': 'pointed', 'source': {'type': 'user_text', 'ref': 'paste', 'quote': 'no CCMC, unsigned letter'}})
    body = again.json()
    assert [fact['field'] for fact in body['facts']].count('ccmc_evaluation') == 1
    assert not any(fact['field'] == 'professional_confirmed' for fact in body['facts'])
    assert sum(item['description'] == 'letter, unsigned' for item in body['evidence']) == 1


def test_sheathing_membrane_card_is_not_shown_for_a_structural_nail_base_panel():
    candidates = [
        _MEMBRANE,
        {'provision': '9.27.5.1.', 'title': 'Attachment of Cladding',
         'text': 'Cladding shall be fastened to framing, furring or blocking.'},
    ]
    questions = generate_questions(_MIRA, candidates, provisions=['9.27.5.1.'])
    blob = ' '.join(q['text'] + ' ' + q['why'] + ' ' + ' '.join(q['disambiguates']) for q in questions).lower()
    assert _MEMBRANE_CARD not in blob
    assert '9.27.3.2.' not in blob
    card = {
        'field': 'assembly.sheathing_membrane',
        'text': _MEMBRANE_CARD,
        'why': 'The card asks about the sheathing membrane.',
        'disambiguates': ['9.27.3.2.'],
    }
    assert question_matches(
        card, description=_MIRA, provisions=['9.27.5.1.'], candidates=candidates) is False
    assert question_matches(
        card, description='The wall has no sheathing membrane.', provisions=['9.27.3.2.'],
        candidates=candidates) is True
    shown = generate_questions(
        'The wall has no sheathing membrane.', candidates, provisions=['9.27.3.2.'])
    assert any(q['field'] == 'assembly.sheathing_membrane' for q in shown)


def test_mira_description_parse_records_the_house_the_evidence_and_the_route(tmp_path):
    client = _case(tmp_path)
    created = client.post('/cases', json={'title': _MIRA}).json()
    fields = {fact['field']: fact['value'] for fact in created['facts']}
    assert fields['building.storeys'] == 2
    assert fields['building.area'] == 'about 190 m²'
    assert fields['occupancy'] == 'single_family'
    assert fields['building.sprinklered'] is False
    assert fields['site.city'] == 'Edmonton'
    assert fields['scope'] == 'province-wide; one site'
    assert fields['role'] == 'manufacturer'
    assert fields['ccmc_evaluation'] is False
    assert fields['air_leakage_test'] is False
    assert fields['bracing_design'] is False
    assert 'professional_confirmed' not in fields
    descriptions = {item['description'] for item in created['evidence']}
    assert descriptions == {
        'product data sheet',
        'US lab permeance summary',
        'unsigned draft engineer letter',
    }
    assert all(item['professional_required'] is None for item in created['evidence'])
    assert created['route_notice']['summary']
    again = client.post(f"/cases/{created['id']}/facts", json={
        'field': 'project.description', 'value': _MIRA, 'kind': 'pointed',
        'source': {'type': 'user_text', 'ref': 'paste', 'quote': 'NailBase'}})
    body = again.json()
    assert [fact['field'] for fact in body['facts']].count('ccmc_evaluation') == 1
    assert sum(item['description'] == 'unsigned draft engineer letter' for item in body['evidence']) == 1
    assert not any(fact['field'] == 'professional_confirmed' for fact in body['facts'])


def test_a_stated_role_fact_round_trips_with_its_notice(tmp_path):
    """The notice is computed. Storing the case does not turn it into a different form."""
    case = Case(facts=[Fact(field='role', value='manufacturer', kind='pointed', source=_SRC)])
    assert case.route_notice and case.route_notice.summary == SUMMARY
    store = CaseStore(tmp_path / 'cases.sqlite')
    loaded = store.get(store.put(case).id)
    assert loaded.route_notice == case.route_notice
    assert resolve_form().form_id == 'scc-variance'
