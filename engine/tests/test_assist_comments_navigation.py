"""Comments navigation uses the current authorized application, never model prose.

All accounts, databases, code text and voice events here are synthetic. No live
provider or browser is used; the client owns applying a plan to its bound case.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from engine import llm_gate, routes_assist
from engine.account_models import MessageAuthor, StoredMessage, User
from engine.api import create_app
from engine.assist_navigation import available_destinations, plan_navigation
from engine.models import Case
from engine.store import CaseStore
from engine.tests.test_accounts import onboard, signup
from engine.tests.test_voice_api import SCOPE, begin, commit_turn, upstream, voice_app
from engine.tests.test_voice_context import synthetic_codes


EXPLICIT = [
    'Open comments',
    'Open my officer comments.',
    "Open my officer's comments",
    'Please show me the officer’s comments.',
    'Can you open my reviewer’s feedback?',
    'Could you please take me to my SCO’s messages?',
    'Go to the Safety Codes Officer’s comments page.',
    'Bring up officer feedback for me.',
    'Let me see the officer messages.',
]

ORDINARY = [
    'What do my officer’s comments mean?',
    'Can you explain the officer’s comments?',
    'How do I respond to the officer?',
    'How do I open the officer comments?',
    'Show me how to open my officer’s comments.',
    "Don't open my officer's comments.",
    'Please do not show the officer comments.',
    'Could you not open officer comments?',
    'If I open my officer’s comments, will I lose my answers?',
    'Open officer comments when I ask later.',
    'My officer said "open officer comments".',
    '"Open officer comments"',
    'Open "officer comments".',
    "Open 'officer comments'.",
    "Open 'officer's comments'.",
    "Open 'reviewer’s feedback'.",
    "Open 'SCO's messages'.",
    'Open “officer’s comments”.',
    "Open ‘officer's comments’.",
    'Open `officer’s comments`.',
    'Open officer’s "comments".',
    'Open officer comments and delete my application.',
    'Open officer comments or settings.',
    'Open officer comments for my other application.',
    'Open comments for Garden suite.',
]


@pytest.mark.parametrize('question', EXPLICIT)
def test_explicit_whole_request_selects_only_the_comments_destination(question):
    user = SimpleNamespace(id='owner', role='applicant', authority=None)
    case = SimpleNamespace(owner_id='owner', authority='edmonton', status='returned')
    result = plan_navigation(question, ['comments', 'officer-view', 'review-messages'], user, case)
    assert result is not None
    assert result.model_dump() == {'destination': 'comments'}


@pytest.mark.parametrize('question', ORDINARY)
def test_comments_help_quotes_negation_and_other_cases_never_become_navigation(question):
    user = SimpleNamespace(id='owner', role='applicant', authority=None)
    case = SimpleNamespace(owner_id='owner', authority='edmonton', status='returned')
    assert plan_navigation(question, ['comments', 'settings'], user, case) is None


@pytest.fixture
def comments_api(tmp_path, monkeypatch):
    for name in ('VERCEL', 'BATATIS_STORE', 'BATATIS_LIVE', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'XAI_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '5')
    llm_gate.reset_for_tests()
    store = CaseStore(tmp_path / 'comments.sqlite')
    calls = []

    def explain(**kwargs):
        calls.append(kwargs)
        return routes_assist.ModelAnswer('Read the officer message in your application.', 10, 10)

    monkeypatch.setattr(routes_assist, 'call_model', explain)
    with TestClient(create_app(store=store, codes=synthetic_codes(tmp_path / 'codes.sqlite')),
                    base_url='http://localhost') as client:
        assert signup(client, 'comments-owner@example.test').status_code == 201
        onboard(client)
        yield client, store, calls
    llm_gate.reset_for_tests()


def ask_comments(client, **changes):
    return client.post('/assist', json={'screen': 'application', 'question': "Open my officer's comments",
                                       'destinations': ['comments'], **changes})


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused', 'withdrawn'])
def test_comments_http_plan_needs_no_provider_and_does_not_mark_comments_read(comments_api, status):
    client, store, calls = comments_api
    owner = client.get('/auth/me').json()['user']
    case = store.put(Case(owner_id=owner['id'], status=status, title='Current synthetic application',
        messages=[StoredMessage(author=MessageAuthor(id='synthetic-officer', name='Officer', role='reviewer'),
                                body='Synthetic officer comment.', read_by=['synthetic-officer'])]))
    before = store.get(case.id).model_dump()
    response = ask_comments(client, case_id=case.id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert {key: body[key] for key in ('answer', 'cited', 'removed_citations', 'notice', 'navigation')} == {
        'answer': '', 'cited': [], 'removed_citations': [], 'notice': '',
        'navigation': {'destination': 'comments'}}
    assert store.get(case.id).model_dump() == before
    assert not calls and llm_gate._memory.today() == 0


def test_comments_http_authentication_and_current_case_are_required(comments_api):
    client, store, calls = comments_api
    owner = client.get('/auth/me').json()['user']
    case = store.put(Case(owner_id=owner['id']))
    with TestClient(client.app, base_url='http://localhost') as other:
        assert ask_comments(other, case_id=case.id).status_code == 401
        assert signup(other, 'comments-outsider@example.test').status_code == 201
        onboard(other)
        assert ask_comments(other, case_id=case.id).status_code == 404
    assert ask_comments(client, case_id='case_missing').status_code == 404
    # With no current case there is no plan; explanatory AI is disabled in this fixture.
    assert ask_comments(client).status_code == 503
    assert not calls


@pytest.mark.parametrize('question', [ORDINARY[0], ORDINARY[2], ORDINARY[12], ORDINARY[-1]])
def test_ordinary_comments_questions_still_use_grounded_assistant_help(comments_api, monkeypatch, question):
    client, store, calls = comments_api
    owner = client.get('/auth/me').json()['user']
    case = store.put(Case(owner_id=owner['id']))
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key-never-used-on-network')
    response = ask_comments(client, case_id=case.id, question=question)
    assert response.status_code == 200, response.text
    assert response.json()['navigation'] is None and len(calls) == 1
    assert calls[0]['body'].case_id == case.id


def test_comments_requires_an_enabled_native_destination_and_an_applicant_case():
    applicant = User(email='owner@example.test', name='Owner', role='applicant')
    case = Case(owner_id=applicant.id, authority='edmonton', status='returned')
    assert 'comments' in {dest.id for dest in available_destinations(applicant, case)}
    assert 'comments' not in {dest.id for dest in available_destinations(applicant, None)}
    assert plan_navigation('Open comments', ['settings'], applicant, case) is None
    reviewer = User(email='officer@example.test', name='Officer', role='reviewer', authority='edmonton')
    assert plan_navigation('Open comments', ['comments'], reviewer, case) is None


def test_completed_voice_comments_plan_keeps_the_current_turn_and_context_binding(voice_app):
    client, store, providers = voice_app
    owner = client.get('/auth/me').json()['user']
    case = store.put(Case(owner_id=owner['id'], authority='edmonton', status='returned'))
    before = store.get(case.id).model_dump()
    scope = {**SCOPE, 'case_id': case.id, 'case_version': case.version,
             'screen': 'application', 'destinations': ['comments']}
    socket, started = begin(client, scope)
    try:
        assert started['type'] == 'session.started', started
        provider = providers[0]
        commit_turn(client, provider, socket, started, 'comments-turn')
        upstream(client, provider, type='conversation.item.input_audio_transcription.updated',
                 item_id='comments-turn', transcript="Open my officer's comments")
        upstream(client, provider, type='conversation.item.input_audio_transcription.completed',
                 item_id='comments-turn', transcript="Open my officer's comments")
        result = socket.receive_json()
        assert result['type'] == 'transcript.completed'
        assert result['navigation'] == {'destination': 'comments'}
        assert (result['session_id'], result['context_id'], result['revision'], result['turn_id']) == (
            started['session_id'], scope['context_id'], 0, 'comments-turn')
        assert not any(event['type'] == 'response.create' for event in provider.sent)
        assert store.get(case.id).model_dump() == before
    finally:
        socket.__exit__(None, None, None)


def test_old_voice_comments_turn_cannot_navigate_after_context_changes(voice_app):
    client, store, providers = voice_app
    owner = client.get('/auth/me').json()['user']
    case = store.put(Case(owner_id=owner['id'], authority='edmonton', status='returned'))
    scope = {**SCOPE, 'case_id': case.id, 'case_version': case.version, 'destinations': ['comments']}
    socket, started = begin(client, scope)
    try:
        assert started['type'] == 'session.started', started
        provider = providers[0]
        commit_turn(client, provider, socket, started, 'old-comments-turn')
        socket.send_json({'type': 'context.update', 'session_id': started['session_id'],
                          'context_id': scope['context_id'], 'revision': 0,
                          'scope': {**scope, 'revision': 1, 'destinations': ['settings']}})
        assert socket.receive_json()['type'] == 'audio.clear'
        assert socket.receive_json()['type'] == 'context.updated'
        upstream(client, provider, type='conversation.item.input_audio_transcription.completed',
                 item_id='old-comments-turn', transcript='Open officer comments')
        commit_turn(client, provider, socket, started, 'new-comments-turn', revision=1)
        upstream(client, provider, type='conversation.item.input_audio_transcription.completed',
                 item_id='new-comments-turn', transcript='Open officer comments')
        result = socket.receive_json()
        assert result['type'] == 'transcript.completed' and result['navigation'] is None
        assert result['turn_id'] == 'new-comments-turn' and result['revision'] == 1
    finally:
        socket.__exit__(None, None, None)


def test_voice_comments_request_cannot_be_rebound_to_another_application(voice_app):
    client, store, providers = voice_app
    owner = client.get('/auth/me').json()['user']
    first = store.put(Case(owner_id=owner['id'], status='returned'))
    second = store.put(Case(owner_id=owner['id'], status='in_review'))
    scope = {**SCOPE, 'case_id': first.id, 'case_version': first.version, 'destinations': ['comments']}
    socket, started = begin(client, scope)
    try:
        assert started['type'] == 'session.started', started
        provider = providers[0]
        commit_turn(client, provider, socket, started, 'first-application-turn')
        socket.send_json({'type': 'context.update', 'session_id': started['session_id'],
                          'context_id': scope['context_id'], 'revision': 0,
                          'scope': {**scope, 'revision': 1, 'case_id': second.id,
                                    'case_version': second.version}})
        result = socket.receive_json()
        assert result['type'] == 'session.ended' and result['reason'] == 'context_changed'
        assert 'navigation' not in result
    finally:
        socket.__exit__(None, None, None)
