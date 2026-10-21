"""Both real OIDC verification paths run against signed tokens and fake HTTP."""
import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest

from engine import oauth
from engine.api import create_app
from engine.store import CaseStore
from engine.tests.test_accounts import signup

TENANT = '12345678-1234-1234-1234-123456789abc'


@pytest.fixture(scope='module')
def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    return key, dict(public, kid='test-key', use='sig')


@pytest.fixture
def oidc(tmp_path, monkeypatch, keypair):
    monkeypatch.delenv('VERCEL', raising=False)
    for provider in ['GOOGLE', 'MICROSOFT']:
        monkeypatch.setenv('BATATIS_' + provider + '_CLIENT_ID', 'test-client')
        monkeypatch.setenv('BATATIS_' + provider + '_CLIENT_SECRET', 'test-client-secret')
    monkeypatch.setenv('BATATIS_MICROSOFT_TENANT', TENANT)
    monkeypatch.setenv('BATATIS_WEB_ORIGIN', 'http://localhost:5480')
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store=store), base_url='http://localhost')
    params, exchange, changes = {}, [], {}
    key, public = keypair

    def handler(request):
        if request.method == 'POST':
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            assert form['client_secret'] == 'test-client-secret'
            assert form['grant_type'] == 'authorization_code' and form['code'] == 'a-code'
            expected = base64.urlsafe_b64encode(hashlib.sha256(form['code_verifier'].encode()).digest()).rstrip(b'=').decode()
            assert params['code_challenge'] == expected
            assert form['redirect_uri'] == params['redirect_uri']
            exchange.append(form)
            issuer = 'https://accounts.google.com' if 'googleapis' in request.url.host else f'https://login.microsoftonline.com/{TENANT}/v2.0'
            claims = {'iss': issuer, 'aud': 'test-client', 'exp': time.time() + 600, 'iat': time.time(),
                      'sub': 'provider-user', 'nonce': params['nonce'], 'tid': TENANT,
                      'email': 'oidc@example.test', 'email_verified': True}
            claims.update(changes)
            token = jwt.encode(claims, key, algorithm='RS256', headers={'kid': 'test-key'})
            if changes.get('bad_signature'):
                other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                token = jwt.encode(claims, other, algorithm='RS256', headers={'kid': 'test-key'})
            return httpx.Response(200, json={'id_token': token, 'access_token': 'private-provider-token'})
        if request.url.path.endswith(('certs', 'keys')):
            return httpx.Response(200, json={'keys': [public]})
        assert request.headers['authorization'] == 'Bearer private-provider-token'
        return httpx.Response(200, json={'sub': changes.get('userinfo_sub', 'provider-user'),
            'email': 'oidc@example.test', 'name': 'OIDC Person', 'email_verified': changes.get('email_verified', True)})

    real_client = oauth.OAuthClient
    monkeypatch.setattr(oauth, 'OAuthClient', lambda: real_client(transport=httpx.MockTransport(handler)))

    def start(provider, redirect='/applications?from=login', prefix=''):
        result = client.get(prefix + f'/auth/oauth/{provider}/start', params={'redirect': redirect}, follow_redirects=False)
        if result.status_code == 302:
            params.clear()
            params.update({k: v[0] for k, v in parse_qs(urlsplit(result.headers['location']).query).items()})
        return result

    yield client, start, params, changes, exchange, store
    client.close()


@pytest.mark.parametrize('provider', ['google', 'microsoft'])
def test_oidc_pkce_state_nonce_signature_userinfo_and_session(oidc, provider):
    client, start, params, changes, exchange, store = oidc
    assert start(provider).status_code == 302
    assert params['code_challenge_method'] == 'S256'
    assert len(params['state']) >= 43 and len(params['nonce']) >= 43
    r = client.get(f'/auth/oauth/{provider}/callback', params={'state': params['state'], 'code': 'a-code'}, follow_redirects=False)
    assert r.status_code == 302, r.text
    assert r.headers['location'] == 'http://localhost:5480/applications?from=login'
    assert client.get('/auth/me').json()['user']['name'] == 'OIDC Person'
    assert len(exchange) == 1
    r = client.get(f'/auth/oauth/{provider}/callback', params={'state': params['state'], 'code': 'a-code'})
    assert r.status_code == 400


@pytest.mark.parametrize('provider', ['google', 'microsoft'])
@pytest.mark.parametrize('change', [{'nonce': 'wrong'}, {'aud': 'someone-else'}, {'iss': 'https://attacker.test'},
    {'exp': 1}, {'bad_signature': True}, {'userinfo_sub': 'another-user'}])
def test_oidc_rejects_invalid_id_tokens_and_subjects(oidc, provider, change):
    client, start, params, changes, exchange, store = oidc
    start(provider)
    changes.update(change)
    r = client.get(f'/auth/oauth/{provider}/callback', params={'state': params['state'], 'code': 'a-code'})
    assert r.status_code == 400
    assert r.json()['detail'] == 'Authentication could not be verified'
    assert client.get('/auth/me').status_code == 401


def test_browser_state_mismatch_and_expiry_do_not_authenticate(oidc):
    client, start, params, changes, exchange, store = oidc
    start('google')
    state = params['state']
    client.cookies.clear()
    assert client.get('/auth/oauth/google/callback', params={'state': state, 'code': 'a-code'}).status_code == 400
    assert exchange == []
    start('google')
    with store.account_db() as db:
        db.execute('UPDATE account_oauth SET expires_at=1')
    assert client.get('/auth/oauth/google/callback', params={'state': params['state'], 'code': 'a-code'}).status_code == 400
    assert exchange == []


@pytest.mark.parametrize('redirect', ['https://attacker.test', '//attacker.test', '/\\attacker.test',
    '/%2fattack.test', '/%252fattack.test', '/%0d%0aLocation:evil', 'relative/path',
    '%2F@attacker.test', '%252F@attacker.test'])
def test_redirect_paths_cannot_escape_the_web_origin(oidc, redirect):
    client, start, *_ = oidc
    assert start('google', redirect).status_code == 400


def test_api_prefix_callback_and_provider_visibility(oidc, monkeypatch):
    client, start, params, *_ = oidc
    assert [x['id'] for x in client.get('/auth/providers').json()['providers']] == ['password', 'google', 'microsoft']
    start('google', prefix='/api')
    assert params['redirect_uri'] == 'http://localhost/api/auth/oauth/google/callback'
    monkeypatch.delenv('BATATIS_GOOGLE_CLIENT_SECRET')
    monkeypatch.delenv('BATATIS_MICROSOFT_TENANT')
    assert client.get('/auth/providers').json()['providers'] == [{'id': 'password', 'label': 'Email'}]
    assert client.get('/auth/oauth/google/start').status_code == 404


def test_provider_identity_never_takes_over_a_password_account(oidc):
    client, start, params, *_ = oidc
    signup(client, 'oidc@example.test')
    client.post('/auth/logout', json={})
    start('microsoft')
    r = client.get('/auth/oauth/microsoft/callback', params={'state': params['state'], 'code': 'a-code'}, follow_redirects=False)
    assert r.status_code == 409
    assert client.get('/auth/me').status_code == 401


def test_google_requires_verified_email(oidc):
    client, start, params, changes, *_ = oidc
    start('google')
    changes['email_verified'] = False
    assert client.get('/auth/oauth/google/callback', params={'state': params['state'], 'code': 'a-code'}).status_code == 400


def test_google_issuer_spellings_map_to_one_identity(oidc):
    client, start, params, changes, exchange, store = oidc
    start('google')
    assert client.get('/auth/oauth/google/callback', params={'state': params['state'], 'code': 'a-code'},
                      follow_redirects=False).status_code == 302
    first = client.get('/auth/me').json()['user']['id']
    client.post('/auth/logout', json={})
    changes['iss'] = 'accounts.google.com'  # Google's other documented issuer spelling
    start('google')
    assert client.get('/auth/oauth/google/callback', params={'state': params['state'], 'code': 'a-code'},
                      follow_redirects=False).status_code == 302
    assert client.get('/auth/me').json()['user']['id'] == first
