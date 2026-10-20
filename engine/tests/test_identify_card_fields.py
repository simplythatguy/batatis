"""Card fields Artisty renders: codedb snippet, attribution, and the numeric benchmark."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes, default_db
from engine.identify.publication import publication
from engine.identify.requirement import benchmark
from engine.store import CaseStore

WINDOW = '9.9.10.1.'
SENTENCE = '9.9.10.1.(2)'
AREA_FACT = 'fact_w07_area'


def test_printing_is_null_unless_the_manifest_proves_a_second_printing(tmp_path):
    missing = publication(tmp_path / 'absent.json')
    assert missing == {'url': None, 'printing': None}
    plain = tmp_path / 'manifest.json'
    plain.write_text(json.dumps({'nbc_ae': {
        'url': 'https://nrc-publications.canada.ca/eng/view/ft/?id=example',
        'path': 'reference/codes/NBC-AE-2023.pdf',
    }}), encoding='utf-8')
    assert publication(plain)['printing'] is None
    assert publication(plain)['url'].startswith('https://nrc-publications.canada.ca/')
    proved = publication()
    assert proved['printing'] == '2nd'
    assert proved['url'].startswith('https://nrc-publications.canada.ca/')


def test_a_single_requirement_is_parsed_and_a_second_number_is_not_guessed():
    one = benchmark('9.1.1.1.(1)', 'The opening shall be not less than 1 m.', [])
    assert one['required_value'] == 1 and one['required_unit'] == 'm'
    assert one['proposed_value'] is None and one['comparison'] is None and one['fact_id'] is None
    two = benchmark('9.1.1.1.(1)', 'not less than 1.0 m and not more than 2.0 m', [
        {'id': 'fact_width', 'field': 'opening.width', 'value': '1.5 m', 'status': 'confirmed'},
    ])
    assert two['required_value'] is None and two['proposed_value'] is None and two['comparison'] is None
    ignored = benchmark('9.1.1.1.(1)', 'not less than 1 m', [
        {'id': 'fact_open', 'field': 'opening.width', 'value': '2 m', 'status': 'unconfirmed'},
    ])
    assert ignored['required_value'] == 1 and ignored['proposed_value'] is None
    above = benchmark('9.1.1.1.(1)', 'not less than 1 m', [
        {'id': 'fact_width', 'field': 'opening.width', 'value': '2 m', 'status': 'confirmed'},
    ])
    assert above['comparison'] == 'above' and above['fact_id'] == 'fact_width'
    equal = benchmark('9.1.1.1.(1)', 'not less than 1 m', [
        {'id': 'fact_width', 'field': 'opening.width', 'value': '1 m', 'status': 'confirmed'},
    ])
    assert equal['comparison'] == 'equal'


def test_window_benchmark_uses_case_c_accepted_opening(tmp_path, monkeypatch):
    """Demo case C: Bedroom 3 clear opening 400 mm × 780 mm = 0.312 m², below the 0.35 m² minimum."""
    if not default_db().exists():
        pytest.skip('code database not built at codedb/build/codedb.sqlite')
    codes = Codes()
    sentence = codes.provision(SENTENCE, 'B')
    flat = ' '.join(sentence['text'].split())
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)

    def fake_run(prose, facts=None, on_stage=None, ranker=None, **kwargs):
        return {
            'articles': [{
                'provision': WINDOW,
                'division': 'B',
                'suggested': True,
                'title': codes.provision(WINDOW, 'B')['title'],
                'part': 9,
                'probability': 0.9,
                'quote': 'the model says the opening should be about 0.99 m²',
                'reason': 'Bedroom window.',
                'stage': 'verify',
            }],
            'section_c': [{
                'provision_id': SENTENCE,
                'citation': sentence['citation'],
                'explainer': {'quote': 'unobstructed opening of not less than 0.35', 'text': 'lookup',
                              'source': 'deterministic'},
            }],
            'benchmark': {'section_c': [], 'identified': True, 'provision': WINDOW, 'quote': sentence['text']},
            'questions': [],
            'open_questions': [],
            'trace': {'verifier': {'picks': [WINDOW]}},
        }

    monkeypatch.setattr('engine.routes_case.identify_run', fake_run)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=codes))
    case_id = client.post('/cases').json()['id']
    area = client.post(f'/cases/{case_id}/facts', json={
        'id': AREA_FACT,
        'field': 'window.w07.clear_opening',
        'value': '0.312 m²',
        'kind': 'exact',
        'status': 'confirmed',
        'source': {'type': 'user_text', 'ref': 'drawing-notes', 'quote': 'clear opening 400×780 (supplier)'},
    })
    assert area.status_code == 200
    client.post(f'/cases/{case_id}/facts', json={
        'id': 'fact_unconfirmed',
        'field': 'window.w07.rounded',
        'value': '0.31 m²',
        'kind': 'exact',
        'status': 'unconfirmed',
        'source': {'type': 'user_text', 'ref': 'note', 'quote': 'about 0.31'},
    })
    client.post(f'/cases/{case_id}/facts', json={
        'id': 'fact_dims',
        'field': 'window.w07.dimensions',
        'value': '400 mm × 780 mm',
        'kind': 'exact',
        'status': 'confirmed',
        'source': {'type': 'user_text', 'ref': 'drawing-notes', 'quote': 'clear opening 400×780 (supplier)'},
    })
    identified = client.post(f'/cases/{case_id}/identify', json={'prose': 'Bedroom 3 slot window'})
    assert identified.status_code == 200
    card = identified.json()['articles'][0]
    assert card['provision_id'] == SENTENCE
    assert card['snippet'] and len(card['snippet'].split()) <= 25
    assert flat.startswith(card['snippet']) and card['snippet'] != flat
    assert 'quote' not in card and flat not in json.dumps(card)
    assert '380' not in json.dumps(card)
    assert '0.99' not in json.dumps(card['benchmark'])
    assert card['explainer']['quote'] == card['snippet']
    assert card['page'] == sentence['pdf_page'] == 873
    assert card['printing'] == '2nd'
    assert card['url'] == publication()['url']
    assert card['objectives'] == [{'id': 'OS3.7', 'label': codes.definition('OS3.7')['title']}]
    assert card['functions'] == [{'id': 'F10', 'label': codes.definition('F10')['title']}]
    assert card['attribution_missing'] is False
    compared = card['benchmark']
    assert compared['provision_id'] == SENTENCE
    assert compared['requirement_snippet'] == 'not less than 0.35 m²'
    assert len(compared['requirement_snippet'].split()) <= 25
    assert compared['requirement_snippet'] in flat
    assert compared['required_value'] == 0.35 and compared['required_unit'] == 'm²'
    assert compared['proposed_value'] == 0.312 and compared['proposed_unit'] == 'm²'
    assert compared['fact_id'] == AREA_FACT
    assert compared['comparison'] == 'below'

    decided = client.post(f'/cases/{case_id}/identify/{SENTENCE}/decision', json={'decision': 'yes'})
    assert decided.status_code == 200
    row = next(item for item in decided.json()['section_c_row'] if item['provision'] == SENTENCE)
    intent = sentence['intents'][0]['intents'][0]
    assert row['objectives'] == card['objectives']
    assert row['functions'] == card['functions']
    assert row['intent'] == intent
    assert row['intent'] != 'lookup not available'
    assert row['attribution_missing'] is False
    saved = client.get(f'/cases/{case_id}').json()
    assert WINDOW in saved['provisions']
