"""Identify ranks articles. Only a user decision accepts one onto the case."""
import json

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import SectionCRow
from engine.store import CaseStore

ARTICLE = '9.10.15.5.'


class FakeCodes:
    db_path = 'fake'

    def provision(self, provision_id, division='B'):
        if provision_id == ARTICLE:
            return {'id': ARTICLE, 'citation': 'Div B 9.10.15.5.', 'level': 'article',
                    'children': [{'id': '9.10.15.5.(1)', 'level': 'sentence'}]}
        return None

    def citation(self, provision_id, division='B'):
        row = self.provision(provision_id, division)
        return row['citation'] if row else None


def _row(provision_id='9.10.15.5.(1)'):
    return SectionCRow(
        provision_id=provision_id,
        citation='Div B 9.10.15.5.(1)',
        attribution_status='no row in the attribution table',
        pairs=[],
        intents=[],
    )


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
    monkeypatch.setattr('engine.routes_case.check_completeness', lambda case, codes, **kwargs: [])
    monkeypatch.setattr('engine.section_c.section_c_rows', lambda ids, codes: [_row()])
    present = tmp_path / 'present.sqlite'
    present.write_bytes(b'')
    monkeypatch.setattr('engine.routes_case.default_db', lambda: present)

    def fake_run(prose, facts=None, on_stage=None, ranker=None, **kwargs):
        return {
            'articles': [{
                'provision': ARTICLE,
                'division': 'B',
                'suggested': True,
                'title': 'Exposing building face',
                'part': 9,
                'probability': 0.91,
                'quote': 'limiting distance',
                'reason': 'The proposal is measured against this article.',
                'stage': 'verify',
            }],
            'section_c': [],
            'benchmark': {'section_c': [], 'citation': None, 'quote': None, 'identified': False},
            'questions': [],
            'open_questions': [],
            'trace': {'verifier': {'picks': [ARTICLE]}},
            'intake_action': 'proceed_conditionally',
            'persisted': False,
        }

    monkeypatch.setattr('engine.routes_case.identify_run', fake_run)
    return TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=FakeCodes()))


def _identify(client):
    case_id = client.post('/cases').json()['id']
    response = client.post(f'/cases/{case_id}/identify', json={'prose': 'a wall close to the lot line'})
    assert response.status_code == 200
    return case_id, response.json()


def test_identify_does_not_auto_commit(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    case_id, body = _identify(client)
    card = body['articles'][0]
    assert card['status'] == 'suggested' and card['verifier_status'] == 'suggested'
    assert card['decision'] is None and card['open_question_id'] is None
    assert 'committed' not in card
    saved = client.get(f'/cases/{case_id}').json()
    assert saved['provisions'] == []
    assert not any(fact['source']['type'] == 'user_click' and fact['field'].startswith('citation.')
                   for fact in saved['facts'])


def test_not_sure_becomes_a_gap_and_an_information_request(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    case_id, _body = _identify(client)
    decided = client.post(f'/cases/{case_id}/identify/{ARTICLE}/decision', json={'decision': 'not_sure'})
    assert decided.status_code == 200
    card = decided.json()['articles'][0]
    question_id = card['open_question_id']
    assert card['decision'] == 'not_sure' and question_id
    gaps = client.get(f'/cases/{case_id}/gaps').json()
    gap = next(item for item in gaps if item['id'] == question_id)
    assert gap['section'] == 'C' and ARTICLE in gap['message']
    draft = client.get(f'/cases/{case_id}/information-request').json()
    item = next(row for row in draft['items'] if row['id'] == question_id)
    assert item['provision_id'] == ARTICLE and item['text'] == gap['message']
    saved = client.get(f'/cases/{case_id}').json()
    assert saved['provisions'] == []


def test_yes_becomes_a_user_click_citation(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    case_id, _body = _identify(client)
    decided = client.post(f'/cases/{case_id}/identify/{ARTICLE}/decision', json={'decision': 'yes'})
    assert decided.status_code == 200
    card = decided.json()['articles'][0]
    assert card['decision'] == 'yes' and card['open_question_id'] is None
    saved = client.get(f'/cases/{case_id}').json()
    assert saved['provisions'] == [ARTICLE]
    citation = next(fact for fact in saved['facts'] if fact['field'] == f'citation.{ARTICLE}')
    assert citation['source']['type'] == 'user_click'
    assert citation['source']['ref'] == ARTICLE and citation['value'] == ARTICLE
    assert citation['status'] == 'confirmed'
    assert decided.json()['section_c_row'] == [json.loads(_row().model_dump_json())]
    assert decided.json()['section_c_row'][0]['provision_id'] == '9.10.15.5.(1)'
    assert 'provision' not in decided.json()['section_c_row'][0]


def test_redecision_is_idempotent(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    case_id, _body = _identify(client)
    path = f'/cases/{case_id}/identify/{ARTICLE}/decision'
    first = client.post(path, json={'decision': 'not_sure'}).json()
    second = client.post(path, json={'decision': 'not_sure'}).json()
    question_id = first['articles'][0]['open_question_id']
    assert second['articles'][0]['open_question_id'] == question_id
    saved = client.get(f'/cases/{case_id}').json()
    assert len([fact for fact in saved['facts'] if fact['field'].startswith('open_question.')]) == 1

    accepted = client.post(path, json={'decision': 'yes'})
    assert accepted.status_code == 200
    assert accepted.json()['articles'][0]['decision'] == 'yes'
    assert accepted.json()['articles'][0]['open_question_id'] is None
    assert accepted.json()['section_c_row'][0]['provision_id'] == '9.10.15.5.(1)'
    assert accepted.json()['section_c_row'][0]['pairs'] == []
    assert accepted.json()['section_c_row'][0]['intents'] == []
    gaps = client.get(f'/cases/{case_id}/gaps').json()
    assert all(item['id'] != question_id for item in gaps)
    saved = client.get(f'/cases/{case_id}').json()
    first_citation = next(fact for fact in saved['facts'] if fact['field'] == f'citation.{ARTICLE}')
    client.post(path, json={'decision': 'yes'})
    saved = client.get(f'/cases/{case_id}').json()
    citations = [fact for fact in saved['facts'] if fact['field'] == f'citation.{ARTICLE}']
    assert len(citations) == 1 and citations[0]['id'] == first_citation['id']
    assert citations[0]['source']['type'] == 'user_click'

    rejected = client.post(path, json={'decision': 'no'})
    assert rejected.status_code == 200
    card = rejected.json()['articles'][0]
    assert card['decision'] == 'no' and card['excluded'] is True and card['open_question_id'] is None
    assert rejected.json()['section_c_row'] is None
    saved = client.get(f'/cases/{case_id}').json()
    assert saved['provisions'] == []
    assert not any(fact['field'].startswith(('citation.', 'open_question.')) for fact in saved['facts'])
    stored = client.get(f'/cases/{case_id}/identify').json()
    assert stored['articles'][0]['decision'] == 'no'
