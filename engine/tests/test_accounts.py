import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.store import CaseStore
from engine.accounts import COOKIE, digest, SCRYPT_N, SCRYPT_R, SCRYPT_P, password_hash
from engine.models import Case
from engine.account_models import User


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
    return create_app(store=CaseStore(tmp_path / 'accounts.sqlite'))


def signup(client, email='applicant@example.test', name='Applicant'):
    return client.post('/auth/signup', json={'email': email, 'password': 'a long test password', 'name': name})


def test_signup_session_rotation_and_logout(app):
    with TestClient(app, base_url='http://localhost') as client:
        r = signup(client)
        assert r.status_code == 201
        user = r.json()['user']
        assert user['role'] is None and not user['onboarded']
        cookie = client.cookies.get('batatis_session')
        assert len(cookie) >= 43
        assert 'httponly' in r.headers['set-cookie'].lower()
        assert client.get('/auth/me').json()['user'] == user
        r = client.post('/auth/login', json={'email': user['email'], 'password': 'a long test password'})
        assert r.status_code == 200
        assert client.cookies.get('batatis_session') != cookie
        with TestClient(app, base_url='http://localhost') as stolen:
            stolen.cookies.set('batatis_session', cookie)
            assert stolen.get('/auth/me').status_code == 401
        assert client.post('/auth/logout', json={}).status_code == 204
        assert client.get('/auth/me').status_code == 401


def onboard(client, role='applicant', authority='edmonton'):
    body = ({'role': 'applicant', 'applicant_type': 'contractor'} if role == 'applicant' else
            {'role': 'reviewer', 'authority': authority,
             'access_code': 'officer-secret' if authority == 'edmonton' else 'calgary-secret'})
    response = client.post('/auth/onboarding', json=body)
    assert response.status_code == 200, response.text
    return response.json()['user']


@pytest.mark.parametrize('fields', [{}, {'applicant_type': None}, {'applicant_type': 'manufacturer'}])
def test_applicant_onboarding_accepts_no_type_and_keeps_existing_types(app, fields):
    with TestClient(app, base_url='http://localhost') as client:
        signup(client)
        response = client.post('/auth/onboarding', json={'role': 'applicant', **fields})
        assert response.status_code == 200, response.text
        user = response.json()['user']
        assert user['onboarded'] is True and user['role'] == 'applicant'
        assert user['applicant_type'] == fields.get('applicant_type')
        assert user['authority'] is None
        assert client.get('/auth/me').json()['user'] == user


def test_reviewer_leaving_role_without_type_still_needs_current_code(app):
    with TestClient(app, base_url='http://localhost') as client:
        signup(client)
        onboard(client, 'reviewer')
        assert client.post('/auth/onboarding', json={'role': 'applicant'}).status_code == 403
        response = client.post('/auth/onboarding', json={'role': 'applicant', 'access_code': 'officer-secret'})
        assert response.status_code == 200, response.text
        assert response.json()['user']['applicant_type'] is None
        assert response.json()['user']['authority'] is None


def test_account_model_keeps_an_unknown_applicant_type():
    user = User(email='owner@example.test', name='Owner', role='applicant', onboarded=True)
    assert User.model_validate(user.model_dump()).applicant_type is None


def test_product_scope_follows_the_words_not_the_account_role():
    from engine.intake.questions import plan_questions

    arguments = dict(known=set(), conflicts=[], candidates=[], not_sure=set(), departure_known=True)
    asked = lambda prose, role: {q.field for q in plan_questions(prose=prose, role=role, **arguments)}  # noqa: E731
    assert 'product_scope' in asked('A product for use across Alberta', None)
    assert 'product_scope' in asked('A product for use across Alberta', 'manufacturer')
    assert 'product_scope' not in asked('A two-storey house with larger side windows', None)


def test_credentials_validation_normalization_and_generic_failure(app):
    with TestClient(app, base_url='http://localhost') as client:
        assert signup(client, email='  Person@Example.Test ').status_code == 201
        assert signup(client, email='person@example.test').status_code == 409
        for password in ['short', '']:
            assert client.post('/auth/signup', json={'email': 'x@example.test', 'password': password,
                                                   'name': 'X'}).status_code == 422
        assert signup(client, email='not-an-email').status_code == 422
        bad = client.post('/auth/login', json={'email': 'person@example.test', 'password': 'wrong'})
        absent = client.post('/auth/login', json={'email': 'absent@example.test', 'password': 'wrong'})
        assert bad.status_code == absent.status_code == 401
        assert bad.json()['detail'] == absent.json()['detail'] == 'Email or password is incorrect'
        assert client.post('/auth/login', json={'email': 'PERSON@EXAMPLE.TEST',
                                               'password': 'a long test password'}).status_code == 200


def test_json_csrf_stance_cors_and_secure_cookie(app):
    with TestClient(app, base_url='http://localhost') as client:
        for path in ['/auth/signup', '/auth/login', '/auth/logout', '/auth/onboarding']:
            assert client.post(path, content='{}', headers={'Content-Type': 'text/plain'}).status_code == 415
            assert client.post(path, content='{}').status_code == 415
        r = client.options('/auth/signup', headers={'Origin': 'http://localhost:5480',
                    'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
        assert r.headers['access-control-allow-credentials'] == 'true'
        assert r.headers['access-control-allow-origin'] == 'http://localhost:5480'
        r = client.options('/auth/login', headers={'Origin': 'https://attacker.example',
                                                  'Access-Control-Request-Method': 'POST'})
        assert 'access-control-allow-origin' not in r.headers
    with TestClient(app, base_url='https://app.example.test') as client:
        r = signup(client)
        assert '; Secure' in r.headers['set-cookie']
        assert 'SameSite=lax' in r.headers['set-cookie']
        assert r.headers['cache-control'] == 'no-store'
        assert client.get('/auth/me').status_code == 200


def test_reviewer_codes_and_bidirectional_role_change(app, monkeypatch):
    with TestClient(app, base_url='http://localhost') as client:
        signup(client)
        onboard(client)
        payload = {'role': 'reviewer', 'authority': 'edmonton', 'access_code': 'bad'}
        assert client.post('/auth/onboarding', json=payload).status_code == 403
        old = client.cookies.get(COOKIE)
        user = onboard(client, 'reviewer')
        assert user['authority'] == 'edmonton' and user['applicant_type'] is None
        assert client.cookies.get(COOKIE) != old
        payload = {'role': 'applicant', 'applicant_type': 'homebuilder'}
        assert client.post('/auth/onboarding', json=payload).status_code == 403
        payload['access_code'] = 'officer-secret'
        r = client.post('/auth/onboarding', json=payload)
        assert r.status_code == 200 and r.json()['user']['authority'] is None
        monkeypatch.delenv('BATATIS_REVIEWER_CODES')
        r = client.post('/auth/onboarding', json={'role': 'reviewer', 'authority': 'calgary'})
        assert r.status_code == 403
        assert r.json()['detail'] == 'Reviewer sign-up is not open for this authority'


def test_rates_apply_to_signup_ip_and_login_ip_email(app, monkeypatch):
    monkeypatch.setenv('BATATIS_AUTH_RATE_LIMIT', '1')
    with TestClient(app, base_url='http://localhost') as client:
        assert signup(client).status_code == 201
        assert signup(client, 'second@example.test').status_code == 429
        assert client.post('/auth/login', json={'email': 'a@example.test', 'password': 'wrong'}).status_code == 401
        assert client.post('/auth/login', json={'email': 'a@example.test', 'password': 'wrong'}).status_code == 429
        assert client.post('/auth/login', json={'email': 'b@example.test', 'password': 'wrong'}).status_code == 429


def test_storage_hashes_secrets_and_refreshes_then_expires_sessions(tmp_path, monkeypatch):
    import time
    store = CaseStore(tmp_path / 'auth.sqlite')
    app = create_app(store=store)
    with TestClient(app, base_url='http://localhost') as client:
        user = signup(client).json()['user']
        token = client.cookies.get(COOKIE)
        record = store.user_credentials(user['email'])
        assert record['password']['n'] == SCRYPT_N == 2**17
        assert record['password']['r'] == SCRYPT_R == 8
        assert record['password']['p'] == SCRYPT_P == 1
        assert record['password']['hash'] != 'a long test password'
        assert len(record['password']['salt']) == 64
        assert password_hash('a long test password')['salt'] != record['password']['salt']
        with store.account_db() as db:
            assert db.execute('SELECT digest FROM account_sessions').fetchone()[0] == digest(token)
            db.execute('UPDATE account_sessions SET expires_at=?', (time.time() + 60,))
        assert client.get('/auth/me').status_code == 200
        with store.account_db() as db:
            assert db.execute('SELECT expires_at FROM account_sessions').fetchone()[0] > time.time() + 29 * 86400
            db.execute('UPDATE account_sessions SET expires_at=?', (time.time() - 1,))
        assert client.get('/auth/me').status_code == 401


def test_credentials_and_emails_are_never_logged(app, caplog):
    import logging
    caplog.set_level(logging.INFO, logger='engine.access')
    with TestClient(app, base_url='http://localhost') as client:
        r = signup(client)
        token = client.cookies.get(COOKIE)
        client.post('/auth/login', json={'email': 'private@example.test', 'password': 'private password'})
    assert 'POST /auth/signup 201' in caplog.text
    for secret in ('applicant@example.test', 'private@example.test', 'private password', token):
        assert secret not in caplog.text
