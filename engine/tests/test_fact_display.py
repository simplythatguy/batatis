"""Human fact text, the practice-of-engineering sentence, the short title, and storey parsing."""
import re

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.fact_text import fact_display
from engine.identify.questions import generate_questions
from engine.identify.storeys import parse_storeys
from engine.identify.title import short_title, title_should_replace
from engine.models import Fact, Source
from engine.professional import NOT_SURE_OPTION, ProfessionalReason, ProfessionalResult, professional_involvement
from engine.section_d_issues import render_practice
from engine.store import CaseStore
from engine.tests.test_professional import ordinary_house

_SRC = Source(type='user_text', ref='applicant')
_EXITS = [{'provision': '9.9.8.2.', 'title': 'Number of exits', 'text': 'A single exit.', 'part': 9}]
_WINDOW = {
    'articles': [{
        'provision': '9.9.10.1.', 'provision_id': '9.9.10.1.(2)', 'title': 'Egress window',
    }],
    'benchmark': {'identified': True, 'provision': '9.9.10.1.'},
}


def test_fact_display_keeps_the_raw_field_and_value():
    designed = Fact(field='professional.part4_design', value=False, kind='pointed', source=_SRC)
    assert designed.field == 'professional.part4_design' and designed.value is False
    assert designed.label == 'Designed under Part 4'
    assert designed.display == 'Designed under Part 4: No'
    building = Fact(field='professional.occupancy', value='single_family', kind='pointed', source=_SRC)
    assert building.display == 'Building type: Single-family dwelling'
    assert fact_display('building.storeys', 2) == 'Storeys: 2'
    posted = designed.model_dump()
    assert posted['field'] == 'professional.part4_design' and posted['value'] is False
    assert posted['display'] == 'Designed under Part 4: No'


def test_practice_answer_names_the_missing_fact_once():
    missing = professional_involvement(ordinary_house(part4_design=None), Codes())
    assert missing.required == 'depends'
    assert missing.answer == 'unknown: needs professional.part4_design'
    assert missing.needs == ['professional.part4_design']
    assert 'depends' not in missing.answer.casefold()
    flag = render_practice(missing, Codes())
    assert flag.value == 'unknown' and flag.reason == missing.answer
    assert 'depends. depends' not in flag.reason

    house = professional_involvement(ordinary_house(), Codes())
    assert house.required == 'no' and 'depends' not in house.answer.casefold()
    part4 = professional_involvement(ordinary_house(part4_design=True), Codes())
    assert part4.required == 'yes' and part4.answer.startswith('Part 4 design')
    assert 'depends' not in part4.answer.casefold()


def test_a_duplicated_depends_token_is_not_the_answer():
    screen = ProfessionalResult(
        required='depends', general_required='depends',
        reasons=[ProfessionalReason(code='x', required='depends', message='depends. depends.', citation='rule')],
        questions=['Which fact is still open?'], needs=[])
    assert screen.answer == 'unknown: needs a deciding fact'
    assert 'depends' not in screen.answer.casefold()
    assert screen.prompts[0].text == 'Which fact is still open?'
    assert screen.prompts[-1].text == screen.answer
    assert all(prompt.not_sure == NOT_SURE_OPTION for prompt in screen.prompts)
    assert all('depends. depends' not in prompt.help for prompt in screen.prompts)


def test_short_title_is_type_place_and_provision():
    prose = 'A two-storey single-family house in Edmonton. This design complies and is safe.'
    title = short_title(prose, [], _WINDOW)
    assert title == 'Single-family, Edmonton: 9.9.10.1.(2) egress window'
    assert not re.search(r'\b(?:complies|compliant|compliance|safe)\b', title, re.I)
    assert title_should_replace(prose.split('. ')[0] + '.', prose)
    assert title_should_replace(None, prose)
    assert not title_should_replace('Hempcrete house', prose)


def test_storey_phrases_are_parsed_and_not_asked_again():
    assert parse_storeys('a two-storey house') == (2, 'two-storey')
    assert parse_storeys('The building has 2 storeys and a lane.')[0] == 2
    assert parse_storeys('2-storey infill')[0] == 2
    assert parse_storeys('a bungalow on a corner lot') == (1, 'bungalow')
    assert parse_storeys('single-storey shop')[0] == 1
    assert parse_storeys('two-storey bungalow')[0] == 2
    assert parse_storeys('no height given') is None
    asked = generate_questions('a house beside the lane', _EXITS)
    assert any(q['field'] == 'building.storeys' for q in asked)
    for prose in ('a two-storey house', '2 storeys', 'a bungalow', 'single-storey'):
        questions = generate_questions(prose, _EXITS)
        assert not any(q['field'] == 'building.storeys' for q in questions), prose
    unknown = generate_questions(
        'two-storey', _EXITS, facts=[{'field': 'building.storeys', 'status': 'unknown', 'value': None}])
    assert any(q['field'] == 'building.storeys' and q['status'] == 'unknown' for q in unknown)


def test_identify_stores_the_storey_and_replaces_a_first_sentence_title(tmp_path, monkeypatch):
    def fake_run(prose, db_path=None, judge=None, **kwargs):
        return {
            'articles': [{
                'provision': '9.9.10.1.', 'title': 'Egress window', 'part': 9, 'division': 'B',
                'suggested': False, 'quote': None, 'reason': 'The proposal is compared with this article.',
            }],
            'section_c': [], 'questions': [], 'open_questions': [],
            'benchmark': {'identified': True, 'provision': '9.9.10.1.', 'role': 'benchmark_acceptable_solution',
                          'section_c': []},
            'variance_needed': 'unknown', 'variance_explanation': 'open', 'intake_action': 'ask',
            'engineering_required': 'depends', 'mode': 'bm25_fallback', 'persisted': False, 'cached': False,
        }

    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr('engine.routes_case.identify_run', fake_run)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes()))
    prose = 'A two-storey single-family house in Edmonton with a small bedroom window.'
    case_id = client.post('/cases', json={'title': prose}).json()['id']
    identified = client.post(f'/cases/{case_id}/identify', json={'prose': prose})
    assert identified.status_code == 200
    body = identified.json()
    saved = client.get(f'/cases/{case_id}').json()
    storey = next(fact for fact in saved['facts'] if fact['field'] == 'building.storeys')
    assert storey['value'] == 2 and storey['status'] == 'confirmed'
    assert storey['label'] == 'Storeys' and storey['display'] == 'Storeys: 2'
    assert saved['title'] == 'Single-family, Edmonton: 9.9.10.1. egress window'
    assert body['title'] == saved['title']
    assert 'depends' not in body['engineering_answer'].casefold()
    assert not re.search(r'\b(?:complies|compliant|compliance|safe)\b', saved['title'], re.I)
    kept = client.post('/cases', json={'title': 'Hempcrete house'}).json()['id']
    assert client.post(f'/cases/{kept}/identify', json={'prose': prose}).status_code == 200
    assert client.get(f'/cases/{kept}').json()['title'] == 'Hempcrete house'
    posted = client.post(f'/cases/{kept}/facts', json={
        'field': 'professional.occupancy', 'value': 'single_family', 'kind': 'pointed',
        'source': {'type': 'user_text', 'ref': 'm', 'quote': 'single family'}})
    occupancy = next(fact for fact in posted.json()['facts'] if fact['field'] == 'professional.occupancy')
    assert occupancy['value'] == 'single_family'
    assert occupancy['display'] == 'Building type: Single-family dwelling'
