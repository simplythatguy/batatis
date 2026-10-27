"""The site admin makes, limits and revokes AI access codes; accounts and desktop installs share a code's seats."""
import contextvars

import pytest
from fastapi.testclient import TestClient

from engine import ai_access, llm_gate
from engine.api import create_app
from engine.store import CaseStore

ADMIN = 'aabdelwaly7@gmail.com'


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('BATATIS_AI_ACCESS_CODES', raising=False)
    monkeypatch.delenv('BATATIS_ADMIN_EMAILS', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-synthetic-not-used')
    monkeypatch.setenv('BATATIS_AUTH_RATE_LIMIT', '1000')
    app = create_app(store=CaseStore(tmp_path / 'accounts.sqlite'))

    @app.get('/probe-ai')
    def probe():
        return {'request': llm_gate.live_enabled('openai')}

    return app


def signup(client, email):
    response = client.post('/auth/signup', json={'email': email, 'password': 'a long test password', 'name': 'Person'})
    assert response.status_code == 201, response.text
    return response.json()


def probe(client):
    return client.get('/probe-ai').json()['request']


def test_only_the_admin_email_is_admin_and_only_the_admin_reaches_the_manager(app):
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as other:
        assert signup(admin, ADMIN.upper())['admin'] is True
        assert admin.get('/auth/me').json()['admin'] is True
        assert signup(other, 'someone@example.test')['admin'] is False
        assert other.get('/admin/access-codes').status_code == 403
        assert other.post('/admin/access-codes', json={'name': 'x'}).status_code == 403
        assert admin.get('/admin/access-codes').status_code == 200
    with TestClient(app, base_url='http://localhost') as anonymous:
        assert anonymous.get('/admin/access-codes').status_code == 401


def test_a_made_code_turns_ai_on_shows_in_use_and_stops_at_its_limit(app):
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as first, \
            TestClient(app, base_url='http://localhost') as second:
        signup(admin, ADMIN)
        made = admin.post('/admin/access-codes', json={'name': 'Judges', 'max_users': 1})
        assert made.status_code == 201, made.text
        code = made.json()['code']
        assert len(code) >= 20 and 'code' not in made.json()['info']
        listed = admin.get('/admin/access-codes').json()['codes']
        assert [(c['name'], c['source'], c['max_users'], c['in_use']) for c in listed] == [('Judges', 'managed', 1, 0)]
        assert code not in admin.get('/admin/access-codes').text, 'the code is shown once, never listed'

        signup(first, 'first@example.test')
        assert probe(first) is False
        assert first.post('/auth/ai-access', json={'code': code}).status_code == 200
        assert probe(first) is True
        assert admin.get('/admin/access-codes').json()['codes'][0]['in_use'] == 1

        signup(second, 'second@example.test')
        full = second.post('/auth/ai-access', json={'code': code})
        assert full.status_code == 403 and 'full' in full.json()['detail']
        assert probe(second) is False
        # The person already holding the seat can enter it again.
        assert first.post('/auth/ai-access', json={'code': code}).status_code == 200

        raised = admin.patch('/admin/access-codes/Judges', json={'max_users': 2})
        assert raised.status_code == 200 and raised.json()['max_users'] == 2
        assert second.post('/auth/ai-access', json={'code': code}).status_code == 200
        assert admin.get('/admin/access-codes').json()['codes'][0]['in_use'] == 2

        unlimited = admin.patch('/admin/access-codes/Judges', json={'max_users': None})
        assert unlimited.json()['max_users'] is None


def test_revoking_a_code_turns_its_accounts_off_and_restoring_turns_them_back_on(app):
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as person:
        signup(admin, ADMIN)
        code = admin.post('/admin/access-codes', json={'name': 'team'}).json()['code']
        signup(person, 'person@example.test')
        person.post('/auth/ai-access', json={'code': code})
        assert probe(person) is True
        assert admin.patch('/admin/access-codes/team', json={'revoked': True}).json()['revoked'] is True
        assert probe(person) is False
        assert person.post('/auth/ai-access', json={'code': code}).status_code == 403, 'a revoked code cannot be entered'
        assert admin.patch('/admin/access-codes/team', json={'revoked': False}).json()['revoked'] is False
        assert probe(person) is True
        assert admin.patch('/admin/access-codes/nope', json={'revoked': True}).status_code == 404
        assert admin.post('/admin/access-codes', json={'name': 'team'}).status_code == 409


def test_environment_codes_can_be_limited_and_revoked_too(app, monkeypatch):
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', '{"judges": "judges-code-aaaaaaaaaaaaaaaa"}')
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as one, \
            TestClient(app, base_url='http://localhost') as two:
        signup(admin, ADMIN)
        listed = admin.get('/admin/access-codes').json()['codes']
        assert [(c['name'], c['source'], c['max_users']) for c in listed] == [('judges', 'environment', None)]
        assert admin.patch('/admin/access-codes/judges', json={'max_users': 1}).json()['max_users'] == 1
        signup(one, 'one@example.test'); signup(two, 'two@example.test')
        assert one.post('/auth/ai-access', json={'code': 'judges-code-aaaaaaaaaaaaaaaa'}).status_code == 200
        assert two.post('/auth/ai-access', json={'code': 'judges-code-aaaaaaaaaaaaaaaa'}).status_code == 403
        admin.patch('/admin/access-codes/judges', json={'revoked': True})
        assert probe(one) is False


def test_desktop_installs_take_seats_and_a_limited_code_needs_an_install_id(app, monkeypatch):
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as desktop:
        signup(admin, ADMIN)
        code = admin.post('/admin/access-codes', json={'name': 'desk', 'max_users': 1})
        code = code.json()['code']
        body = {'body': '{"model": "wrong"}'}
        headers = lambda install=None: {'X-Batatis-Access-Code': code, **({'X-Batatis-Install': install} if install else {})}  # noqa: E731
        # Past the seat check the request fails on its own profile (422), which is how the check is seen to pass.
        assert desktop.post('/hosted-ai/screen', json=body, headers=headers()).status_code == 403
        assert desktop.post('/hosted-ai/screen', json=body, headers=headers('install-one-aaaaaaaaaaaa')).status_code == 422
        assert desktop.post('/hosted-ai/screen', json=body, headers=headers('install-two-bbbbbbbbbbbb')).status_code == 403
        assert desktop.post('/hosted-ai/screen', json=body, headers=headers('install-one-aaaaaaaaaaaa')).status_code == 422
        info = admin.get('/admin/access-codes').json()['codes'][0]
        assert (info['installs'], info['accounts'], info['in_use']) == (1, 0, 1)
        admin.patch('/admin/access-codes/desk', json={'max_users': 2})
        assert desktop.post('/hosted-ai/screen', json=body, headers=headers('install-two-bbbbbbbbbbbb')).status_code == 422
        assert desktop.post('/hosted-ai/screen', json=body, headers=headers('bad id')).status_code == 422


def test_deleting_all_accounts_clears_users_sessions_and_installs(app, tmp_path):
    with TestClient(app, base_url='http://localhost') as client:
        signup(client, ADMIN)
    from engine.store import CaseStore
    direct = CaseStore(tmp_path / 'accounts.sqlite')
    counts = direct.delete_all_accounts()
    assert counts['account_users'] == 1 and counts['account_sessions'] == 1
    assert direct.delete_all_accounts()['account_users'] == 0
    with TestClient(app, base_url='http://localhost') as again:
        assert again.get('/auth/me').status_code == 401, 'the old session is gone with its account'
        assert signup(again, ADMIN)['admin'] is True
