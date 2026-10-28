"""The site admin makes, limits and revokes AI access codes; accounts take a code's seats."""
import contextvars
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from engine import ai_access, llm_gate
from engine.account_models import User
from engine.api import create_app
from engine.store import CaseStore

ADMIN_CODE = 'admin-code-zzzzzzzzzzzzzzzzzzzz'


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('BATATIS_AI_ACCESS_CODES', raising=False)
    monkeypatch.setenv('BATATIS_ADMIN_CODE', ADMIN_CODE)
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


def sign_in(client, code, name='Person'):
    response = client.post('/auth/code-login', json={'code': code, 'name': name})
    assert response.status_code == 200, response.text
    return response.json()


def as_admin(client, name='Admin'):
    return sign_in(client, ADMIN_CODE, name)


def probe(client):
    return client.get('/probe-ai').json()['request']


def test_only_the_admin_code_makes_an_admin_and_only_the_admin_reaches_the_manager(app):
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as other:
        made = as_admin(admin)
        assert made['admin'] is True
        assert made['user']['onboarded'] is True, 'the admin skips onboarding: the manager is all their account is for'
        assert admin.get('/auth/me').json()['admin'] is True
        assert admin.get('/auth/me').json()['user']['onboarded'] is True
        assert signup(other, "someone@example.test")["admin"] is False
        assert other.get('/admin/access-codes').status_code == 403
        assert other.post('/admin/access-codes', json={'name': 'x'}).status_code == 403
        assert admin.get('/admin/access-codes').status_code == 200
    with TestClient(app, base_url='http://localhost') as anonymous:
        assert anonymous.get('/admin/access-codes').status_code == 401


def test_an_admin_account_from_an_older_build_skips_onboarding_on_its_next_sign_in(app, tmp_path):
    with TestClient(app, base_url='http://localhost') as admin:
        made = as_admin(admin)
    store = CaseStore(tmp_path / 'accounts.sqlite')
    user = User.model_validate(store.user_credentials(made['user']['email'])['user'])
    user.onboarded = False
    store.update_user(user)
    with TestClient(app, base_url='http://localhost') as back:
        assert as_admin(back)['user']['onboarded'] is True
    store = CaseStore(tmp_path / 'accounts.sqlite')
    assert User.model_validate(store.user_credentials(made['user']['email'])['user']).onboarded is True


def test_a_made_code_turns_ai_on_shows_in_use_and_stops_at_its_limit(app):
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as first, \
            TestClient(app, base_url='http://localhost') as second:
        as_admin(admin)
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
        as_admin(admin)
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


def test_removing_an_unused_managed_code_deletes_only_it(app):
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as first:
        as_admin(admin)
        spare = admin.post('/admin/access-codes', json={'name': 'spare'}).json()['code']
        used = admin.post('/admin/access-codes', json={'name': 'used'}).json()['code']
        assert first.post('/auth/code-login', json={'code': used, 'name': 'First'}).status_code == 200
        assert admin.delete('/admin/access-codes/spare').status_code == 204
        listed = [(c['name'], c['source']) for c in admin.get('/admin/access-codes').json()['codes']]
        assert listed == [('used', 'managed')], 'only the removed code is gone'
        assert first.post('/auth/code-login', json={'code': spare, 'name': 'Anyone'}).status_code == 403, 'a removed code no longer signs anybody in'
        assert first.get('/auth/me').json()['user']['ai_access'] == 'used', "users of a kept code keep their access"
        assert admin.delete('/admin/access-codes/nope').status_code == 404
        assert admin.delete('/admin/access-codes/admin').status_code == 404, "the admin code is the server's own setting"


def test_removing_a_code_in_use_deletes_it_and_an_environment_code_stays(app, monkeypatch):
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', '{"judges": "judges-code-aaaaaaaaaaaaaaaa"}')
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as person:
        as_admin(admin)
        code = admin.post('/admin/access-codes', json={'name': 'team'}).json()['code']
        signup(person, 'person@example.test')
        person.post('/auth/ai-access', json={'code': code})
        assert probe(person) is True
        gone = admin.delete('/admin/access-codes/team')
        assert gone.status_code == 204
        listed = {c['name']: c for c in admin.get('/admin/access-codes').json()['codes']}
        assert 'team' not in listed
        assert person.get('/auth/me').json()['user']['ai_access'] is None
        assert probe(person) is False, 'a removed code no longer grants AI to the accounts that held it'
        assert person.post('/auth/ai-access', json={'code': code}).status_code == 403
        environmental = admin.delete('/admin/access-codes/judges')
        assert environmental.status_code == 409 and 'server settings' in environmental.json()['detail']


def test_environment_codes_can_be_limited_and_revoked_too(app, monkeypatch):
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', '{"judges": "judges-code-aaaaaaaaaaaaaaaa"}')
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as one, \
            TestClient(app, base_url='http://localhost') as two:
        as_admin(admin)
        listed = admin.get('/admin/access-codes').json()['codes']
        assert [(c['name'], c['source'], c['max_users']) for c in listed] == [('judges', 'environment', None)]
        assert admin.patch('/admin/access-codes/judges', json={'max_users': 1}).json()['max_users'] == 1
        signup(one, 'one@example.test'); signup(two, 'two@example.test')
        assert one.post('/auth/ai-access', json={'code': 'judges-code-aaaaaaaaaaaaaaaa'}).status_code == 200
        assert two.post('/auth/ai-access', json={'code': 'judges-code-aaaaaaaaaaaaaaaa'}).status_code == 403
        admin.patch('/admin/access-codes/judges', json={'revoked': True})
        assert probe(one) is False


def test_deleting_all_accounts_clears_users_and_sessions(app, tmp_path):
    with TestClient(app, base_url='http://localhost') as client:
        as_admin(client)
    from engine.store import CaseStore
    direct = CaseStore(tmp_path / 'accounts.sqlite')
    counts = direct.delete_all_accounts()
    assert counts['account_users'] == 1 and counts['account_sessions'] == 1
    assert direct.delete_all_accounts()['account_users'] == 0
    with TestClient(app, base_url='http://localhost') as again:
        assert again.get('/auth/me').status_code == 401, 'the old session is gone with its account'
        assert as_admin(again)['admin'] is True


@pytest.fixture(params=['sqlite', 'postgres'])
def cleanup_store(request, tmp_path):
    if request.param == 'sqlite':
        yield CaseStore(tmp_path / 'accounts.sqlite')
        return
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is not set; real isolated Postgres required')
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from engine.store_postgres import PostgresCaseStore
    schema = 'account_cleanup_' + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as con:
        con.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    try:
        yield PostgresCaseStore(make_conninfo(url, options=f'-c search_path={schema}'))
    finally:
        with psycopg.connect(url, autocommit=True) as con:
            con.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_deleting_all_accounts_clears_legacy_install_records(cleanup_store):
    store = cleanup_store
    assert 'access_installs' not in store.delete_all_accounts()
    with store.account_db() as db:
        db.execute('CREATE TABLE access_installs (code_name TEXT, install_hash TEXT, last_seen DOUBLE PRECISION)')
        db.execute('INSERT INTO access_installs VALUES (?, ?, ?)', ('old', 'digest', 0))

    counts = store.delete_all_accounts()

    with store.account_db() as db:
        assert db.execute('SELECT COUNT(*) FROM access_installs').fetchone()[0] == 0
    assert counts['access_installs'] == 1
    assert store.delete_all_accounts()['access_installs'] == 0


def test_signing_in_with_a_code_and_a_name_makes_one_account_per_name_and_turns_ai_on(app):
    with TestClient(app, base_url='http://localhost') as admin:
        as_admin(admin)
        code = admin.post('/admin/access-codes', json={'name': 'Judges', 'max_users': 2}).json()['code']
    with TestClient(app, base_url='http://localhost') as ada, TestClient(app, base_url='http://localhost') as again, \
            TestClient(app, base_url='http://localhost') as bob, TestClient(app, base_url='http://localhost') as carol:
        first = sign_in(ada, code, 'Ada')
        assert first['user']['name'] == 'Ada' and first['admin'] is False and first['user']['email'].endswith('@code.batatis.invalid')
        assert probe(ada) is True, 'the code that signed her in turns AI on'
        assert sign_in(again, code, ' ada ')['user']['id'] == first['user']['id'], 'the same code and name reach the same account'
        sign_in(bob, code, 'Bob')
        full = carol.post('/auth/code-login', json={'code': code, 'name': 'Carol'})
        assert full.status_code == 403 and 'full' in full.json()['detail']
        assert sign_in(again, code, 'Ada')['user']['id'] == first['user']['id'], 'a returning person keeps their seat when the code is full'


def test_a_wrong_code_is_refused_and_counted_while_right_ones_never_are(app, monkeypatch):
    monkeypatch.setenv('BATATIS_AUTH_RATE_LIMIT', '3')
    with TestClient(app, base_url='http://localhost') as admin:
        as_admin(admin)
        code = admin.post('/admin/access-codes', json={'name': 'team'}).json()['code']
    for number in range(5):
        with TestClient(app, base_url='http://localhost') as person:
            sign_in(person, code, f'Person {number}')
    with TestClient(app, base_url='http://localhost') as guesser:
        statuses = [guesser.post('/auth/code-login', json={'code': 'x' * 24, 'name': 'Eve'}).status_code for _ in range(5)]
    assert statuses == [403, 403, 403, 429, 429]


def test_the_admin_code_alone_makes_an_admin_and_changing_it_ends_admin_sign_ins(app, monkeypatch):
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as person:
        as_admin(admin)
        assert admin.get('/admin/access-codes').status_code == 200
        assert admin.get('/admin/access-codes').json()['codes'] == [], 'the admin code is never listed'
        assert admin.patch('/admin/access-codes/admin', json={'revoked': True}).status_code == 404
        assert admin.post('/admin/access-codes', json={'name': 'Admin'}).status_code == 409
        code = admin.post('/admin/access-codes', json={'name': 'team'}).json()['code']
        assert sign_in(person, code, 'Person')['admin'] is False
        assert person.get('/admin/access-codes').status_code == 403
        monkeypatch.setenv('BATATIS_ADMIN_CODE', 'another-admin-code-zzzzzzzzzzzz')
        assert admin.get('/admin/access-codes').status_code == 403, 'a changed admin code locks out the old sign-in'


def test_a_valid_access_code_opens_reviewer_without_an_authority_code(app, monkeypatch):
    """A testing access code admits the whole product. Reviewer must not ask for a second authority code."""
    monkeypatch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
    with TestClient(app, base_url='http://localhost') as admin, TestClient(app, base_url='http://localhost') as person, \
            TestClient(app, base_url='http://localhost') as password, TestClient(app, base_url='http://localhost') as entered, \
            TestClient(app, base_url='http://localhost') as late:
        as_admin(admin)
        code = admin.post('/admin/access-codes', json={'name': 'Judges'}).json()['code']
        admin_reviewer = admin.post('/auth/onboarding', json={'role': 'reviewer', 'authority': 'calgary'})
        assert admin_reviewer.status_code == 200, admin_reviewer.text
        assert admin_reviewer.json()['app_access'] is True
        assert admin_reviewer.json()['user']['role'] == 'reviewer'
        assert admin.get('/review/queue').status_code == 200

        signed = sign_in(person, code, 'Ada')
        assert signed['app_access'] is True
        opened = person.post('/auth/onboarding', json={'role': 'reviewer', 'authority': 'edmonton'})
        assert opened.status_code == 200, opened.text
        assert opened.json()['user']['role'] == 'reviewer' and opened.json()['user']['authority'] == 'edmonton'
        assert 'officer-secret' not in opened.text and 'calgary-secret' not in opened.text
        queue = person.get('/review/queue')
        assert queue.status_code == 200, queue.text
        assert queue.json()['authority'] == 'edmonton'
        # A wrong authority code is not a second gate, and leaving the role does not demand one either.
        switched = person.post('/auth/onboarding', json={'role': 'reviewer', 'authority': 'calgary', 'access_code': 'not-the-authority-code'})
        assert switched.status_code == 200, switched.text
        assert switched.json()['user']['authority'] == 'calgary'
        left = person.post('/auth/onboarding', json={'role': 'applicant'})
        assert left.status_code == 200, left.text
        assert left.json()['user']['role'] == 'applicant' and left.json()['user']['authority'] is None

        signup(password, 'officer@example.test')
        blocked = password.post('/auth/onboarding', json={'role': 'reviewer', 'authority': 'edmonton'})
        assert blocked.status_code == 403
        assert blocked.json()['detail'] == 'Reviewer access code is incorrect'
        assert password.get('/review/queue').status_code == 403
        allowed = password.post('/auth/onboarding', json={'role': 'reviewer', 'authority': 'edmonton', 'access_code': 'officer-secret'})
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()['app_access'] is False

        signup(entered, 'builder@example.test')
        assert entered.post('/auth/ai-access', json={'code': code}).status_code == 200
        became = entered.post('/auth/onboarding', json={'role': 'reviewer', 'authority': 'edmonton'})
        assert became.status_code == 200, became.text
        assert became.json()['app_access'] is True and became.json()['user']['role'] == 'reviewer'
        assert entered.get('/review/queue').status_code == 200

        assert admin.patch('/admin/access-codes/Judges', json={'revoked': True}).status_code == 200
        refused = person.post('/auth/onboarding', json={'role': 'reviewer', 'authority': 'edmonton'})
        assert refused.status_code == 403
        assert refused.json()['detail'] == 'Reviewer access code is incorrect'
        assert person.get('/review/queue').status_code == 403
        # The authority code still works for an account whose testing code was turned off.
        restored = person.post('/auth/onboarding', json={'role': 'reviewer', 'authority': 'edmonton', 'access_code': 'officer-secret'})
        assert restored.status_code == 200, restored.text
        assert person.get('/review/queue').status_code == 200
        assert late.post('/auth/code-login', json={'code': code, 'name': 'Eve'}).status_code == 403


def test_nobody_can_sign_up_or_log_in_with_a_code_account_address(app):
    with TestClient(app, base_url='http://localhost') as client:
        address = 'abc@code.batatis.invalid'
        assert client.post('/auth/signup', json={'email': address, 'password': 'a long test password', 'name': 'X'}).status_code == 422
        assert client.post('/auth/login', json={'email': address, 'password': 'a long test password'}).status_code == 401


def test_the_sign_in_page_asks_for_a_code_only_where_codes_are_needed(app, monkeypatch, tmp_path):
    with TestClient(app, base_url='http://localhost') as client:
        assert client.get('/auth/providers').json()['sign_in'] == 'code'
    monkeypatch.delenv('BATATIS_ADMIN_CODE')
    with TestClient(create_app(store=CaseStore(tmp_path / 'plain.sqlite')), base_url='http://localhost') as plain:
        assert plain.get('/auth/providers').json()['sign_in'] == 'password'
