"""Navigation crosses the assistant API without spending tokens or changing a case."""
import json

import pytest
from fastapi.testclient import TestClient

from engine import llm_gate
from engine.models import Case
from engine.tests.test_accounts import signup
from engine.tests.test_assist import assistant, ask, enable


def test_explicit_navigation_uses_only_client_offered_real_destinations(assistant):
    client, _, calls = assistant
    before = llm_gate._memory.today()
    response = ask(client, question='Please open the code library.', destinations=['code-library'])
    assert response.status_code == 200, response.text
    assert response.json()['navigation'] == {'destination': 'code-library'}
    assert response.json()['answer'] == ''  # the client acknowledges actual completion, not the model
    assert calls == [] and llm_gate._memory.today() == before


@pytest.mark.parametrize('question', [
    "Don't open the code library.",
    'If I open the code library, will I lose my answers?',
    'My officer said "open the code library".',
    '"Open the code library"',
    'Open the code library and delete my application.',
    'Open code library or settings.',
    'How do I open the code library?',
])
def test_quoted_negated_hypothetical_or_mixed_commands_do_not_navigate(assistant, monkeypatch, question):
    client, _, calls = assistant
    enable(monkeypatch)
    response = ask(client, question=question, destinations=['code-library', 'settings'])
    assert response.status_code == 200, response.text
    assert response.json()['navigation'] is None
    assert len(calls) == 1


def test_unoffered_destination_never_becomes_an_action(assistant, monkeypatch):
    client, _, calls = assistant
    enable(monkeypatch)
    response = ask(client, question='Open settings', destinations=['code-library'])
    assert response.status_code == 200
    assert response.json()['navigation'] is None and len(calls) == 1


@pytest.mark.parametrize('destination', ['https://evil.example', '#/settings', 'delete', 'review-case-private'])
def test_unknown_destination_ids_are_rejected(assistant, destination):
    assert ask(assistant[0], destinations=[destination]).status_code == 422


def test_field_navigation_requires_an_authorized_current_case_and_changes_nothing(assistant):
    client, store, calls = assistant
    user = client.get('/auth/me').json()['user']
    case = store.put(Case(owner_id=user['id'], title='Synthetic navigation'))
    before = store.get(case.id).model_dump()
    response = ask(client, case_id=case.id, question='Take me to the request date', destinations=['question-date'])
    assert response.status_code == 200, response.text
    assert response.json()['navigation'] == {'destination': 'question-date'}
    assert store.get(case.id).model_dump() == before and not calls
    with TestClient(client.app, base_url='http://localhost') as other:
        assert signup(other, 'navigation-other@example.test').status_code == 201
        response = ask(other, case_id=case.id, question='Open request date', destinations=['question-date'])
        assert response.status_code == 404
    assert not calls


def test_applicant_cannot_offer_reviewer_navigation(assistant, monkeypatch):
    client, _, calls = assistant
    enable(monkeypatch)
    response = ask(client, question='Open the review queue', destinations=['review-queue'])
    assert response.status_code == 200
    assert response.json()['navigation'] is None and len(calls) == 1


def test_anonymous_navigation_does_not_bypass_assistant_authentication(assistant):
    client, _, calls = assistant
    with TestClient(client.app, base_url='http://localhost') as anonymous:
        response = ask(anonymous, question='Open the code library', destinations=['code-library'])
        assert response.status_code == 401
    assert not calls


def test_old_clients_receive_real_product_destinations_without_an_action(assistant, monkeypatch):
    client, _, calls = assistant
    enable(monkeypatch)
    response = ask(client, question='Which screen lets me view my code references?')
    assert response.status_code == 200 and response.json()['navigation'] is None
    context = json.loads(calls[0]['context'])
    names = [item['name'] for item in context['navigation']]
    assert 'Code library' in names and 'Settings' in names
    assert 'Review queue' not in names
    assert 'one way' in context['help'].lower()
