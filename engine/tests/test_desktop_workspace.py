"""Desktop workspaces: separate local and development databases, seeded test people in one shared
development database, private actor sessions, and no development path in the hosted composition."""
from __future__ import annotations

import ast
import asyncio
import sqlite3
from pathlib import Path
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from engine.account_models import Authority
from engine.codes import Codes, default_db
from engine.desktop.bridge import ControlError
from engine.desktop.workspace import Config, Workspace, WorkspaceRefused, config_from_env
from engine.models import Case
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import complete_case, store_with_synthetic_files
from engine.tests.desktop_bridge_client import EngineProcess, engine_env

ROOT = Path(__file__).resolve().parents[2]
REVIEWERS = [f'reviewer:{authority}' for authority in get_args(Authority)]


def config(tmp_path: Path, kind: str) -> Config:
    return Config(kind=kind, cases=tmp_path / kind / 'cases.sqlite', codedb=tmp_path / 'none.sqlite')


def session(workspace: Workspace, profile: str, **args) -> dict:
    return asyncio.run(workspace.control('dev.session', {'profile': profile, **args}))


def test_development_seeds_one_applicant_and_one_reviewer_per_authority_with_stable_ids(tmp_path):
    first = Workspace(config(tmp_path, 'dev'))
    assert list(first.profiles) == ['applicant', *REVIEWERS]
    ids = {name: p.user_id for name, p in first.profiles.items()}
    assert len(set(ids.values())) == len(ids), 'every test person is a different user'
    for name, profile in first.profiles.items():
        user = first.store.get_user(profile.user_id)
        assert user.onboarded and user.role == profile.kind
        assert user.authority == (None if name == 'applicant' else name.split(':')[1])
        assert user.applicant_type is None, 'no seeded applicant facts'
        assert user.email.endswith('.invalid')
        assert first.store.user_credentials(user.email)['password'] is None
    assert first.store.list_applications(owner_id=ids['applicant']) == []

    again = Workspace(config(tmp_path, 'dev'))
    assert {name: p.user_id for name, p in again.profiles.items()} == ids
    with sqlite3.connect(tmp_path / 'dev' / 'cases.sqlite') as con:
        assert con.execute('SELECT COUNT(*) FROM account_users').fetchone()[0] == len(ids)


def test_a_crash_between_profile_and_user_converges_on_the_same_person(tmp_path):
    first = Workspace(config(tmp_path, 'dev'))
    reviewer = first.profiles[REVIEWERS[0]].user_id
    with sqlite3.connect(tmp_path / 'dev' / 'cases.sqlite') as con:
        con.execute('DELETE FROM account_users WHERE id=?', (reviewer,))
    again = Workspace(config(tmp_path, 'dev'))
    assert again.profiles[REVIEWERS[0]].user_id == reviewer
    assert again.store.get_user(reviewer).role == 'reviewer'


def test_workspaces_refuse_each_other_and_unmarked_data(tmp_path):
    Workspace(config(tmp_path, 'local'))
    Workspace(config(tmp_path, 'dev'))
    with pytest.raises(WorkspaceRefused, match='local workspace'):
        Workspace(Config('dev', tmp_path / 'local' / 'cases.sqlite', tmp_path / 'none.sqlite'))
    with pytest.raises(WorkspaceRefused, match='dev workspace'):
        Workspace(Config('local', tmp_path / 'dev' / 'cases.sqlite', tmp_path / 'none.sqlite'))
    existing = CaseStore(tmp_path / 'existing' / 'cases.sqlite')
    existing.put(Case(title='Someone else’s work'))
    for kind in ('local', 'dev'):
        with pytest.raises(WorkspaceRefused, match='not a desktop workspace'):
            Workspace(Config(kind, existing.path, tmp_path / 'none.sqlite'))
    with sqlite3.connect(existing.path) as con:
        assert con.execute('SELECT COUNT(*) FROM account_users').fetchone()[0] == 0, 'nothing was seeded into it'


@pytest.mark.parametrize('extra, reason', [
    ({'VERCEL': '1'}, 'hosted'), ({'DATABASE_URL': 'postgresql://x'}, 'hosted'),
    ({'BATATIS_REVIEWER_CODES': '{"calgary":"x"}'}, 'hosted'), ({'BATATIS_STORE': 'postgres'}, 'SQLite'),
    ({'BATATIS_DESKTOP_WORKSPACE': 'admin'}, 'local or dev'), ({'BATATIS_CASES': 'relative.sqlite'}, 'absolute')])
def test_engine_configuration_is_parsed_at_the_boundary(tmp_path, extra, reason):
    env = {'BATATIS_DESKTOP_WORKSPACE': 'dev', 'BATATIS_CASES': str(tmp_path / 'c.sqlite'),
           'BATATIS_CODEDB': str(tmp_path / 'codedb.sqlite'), **extra}
    with pytest.raises(WorkspaceRefused, match=reason):
        config_from_env(env)


def test_test_people_cannot_sign_up_sign_in_sign_out_or_change_role(tmp_path):
    workspace = Workspace(config(tmp_path, 'dev'))
    token = session(workspace, 'applicant')['token']
    client = TestClient(workspace.app(), base_url='http://localhost')
    client.cookies.set('batatis_session', token)
    for path, body in [('/api/auth/signup', {'email': 'a@b.test', 'password': 'x' * 12, 'name': 'A'}),
                       ('/api/auth/login', {'email': 'a@b.test', 'password': 'x' * 12}),
                       ('/api/auth/onboarding', {'role': 'reviewer', 'authority': 'calgary'}),
                       ('/auth/logout', {})]:
        response = client.post(path, json=body)
        assert response.status_code == 403, path
        assert 'quick settings' in response.json()['detail']
    assert client.get('/api/auth/oauth/google/start').status_code == 403
    assert client.get('/api/auth/providers').status_code == 200
    me = client.get('/api/auth/me').json()['user']
    assert me['role'] == 'applicant' and me['id'] == workspace.profiles['applicant'].user_id


def test_a_new_session_for_a_person_revokes_the_one_it_replaces(tmp_path):
    workspace = Workspace(config(tmp_path, 'dev'))
    app = workspace.app()
    applicant = session(workspace, 'applicant')
    reviewer = session(workspace, REVIEWERS[0], revoke=applicant['token'])

    def me(token):
        client = TestClient(app, base_url='http://localhost')
        client.cookies.set('batatis_session', token)
        return client.get('/auth/me')

    assert me(applicant['token']).status_code == 401
    assert me(reviewer['token']).json()['user']['id'] == workspace.profiles[REVIEWERS[0]].user_id
    with pytest.raises(ControlError, match='unknown-profile'):
        session(workspace, 'reviewer:nowhere')
    local = Workspace(config(tmp_path, 'local'))
    with pytest.raises(ControlError, match='unavailable'):
        session(local, 'applicant')


def test_the_hosted_composition_never_imports_the_desktop_package():
    hosted = [ROOT / 'engine' / 'api.py', *sorted((ROOT / 'engine').glob('routes_*.py')),
              ROOT / 'engine' / 'access.py', ROOT / 'engine' / 'accounts.py', ROOT / 'engine' / 'store.py']
    for path in hosted:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        names = [node.module or '' for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        names += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        assert not [name for name in names if 'desktop' in name], path


def test_forged_development_requests_get_nothing_from_the_hosted_engine(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    from engine.api import create_app
    dev = Workspace(config(tmp_path, 'dev'))
    token = session(dev, 'applicant')['token']
    hosted = TestClient(create_app(store=CaseStore(tmp_path / 'hosted' / 'cases.sqlite')), base_url='http://localhost')
    hosted.cookies.set('batatis_session', token)
    forged = {'X-Dev-Role': 'reviewer', 'X-Batatis-Actor': 'reviewer:calgary', 'X-Forwarded-For': '127.0.0.1'}
    assert hosted.get('/auth/me', headers=forged).status_code == 401
    assert hosted.get('/review/queue', headers=forged).status_code == 401
    paths = {getattr(route, 'path', '') for route in hosted.app.routes}
    assert not [path for path in paths if 'desktop' in path or 'dev' in path.split('/')]


@pytest.fixture
def shared(tmp_path):
    if not default_db().is_file():
        pytest.skip('code database not built at codedb/build/codedb.sqlite')
    engine = EngineProcess(engine_env('dev', tmp_path, codedb=default_db()))
    profiles = {p['profile']: p for p in engine.hello['dev']['profiles']}
    yield engine, profiles, tmp_path / 'dev' / 'cases.sqlite'
    engine.close()


def actor(engine: EngineProcess, profile: str, previous: str | None = None) -> str:
    reply = engine.control('dev.session', {'profile': profile, **({'revoke': previous} if previous else {})})
    assert reply['ok'], reply
    return reply['value']['token']


def test_one_shared_database_carries_a_submission_from_applicant_to_reviewer_and_back(shared):
    engine, profiles, db = shared
    assert engine.hello['codedb']['available'] is True
    assert engine.hello['codedb']['build'] == engine.hello['codedb']['expectedBuild']
    applicant_id = profiles['applicant']['userId']
    case = complete_case()
    case.owner_id, case.authority = applicant_id, 'edmonton'
    case = store_with_synthetic_files(CaseStore(db), case)

    applicant = actor(engine, 'applicant')
    draft_view = engine.request('GET', '/api/me/applications', token=applicant).json()['applications']
    assert [row['id'] for row in draft_view] == [case.id]

    edmonton = actor(engine, 'reviewer:edmonton', applicant)
    assert engine.request('GET', '/api/review/queue', token=edmonton).json()['applications'] == [], \
        'a draft is not in any queue'

    applicant = actor(engine, 'applicant', edmonton)
    submitted = engine.request('POST', f'/api/cases/{case.id}/submit', token=applicant,
                               json_body={'expected_version': case.version})
    assert submitted.status == 200, submitted.body
    assert submitted.json()['status'] == 'submitted'

    calgary = actor(engine, 'reviewer:calgary', applicant)
    assert engine.request('GET', '/api/review/queue', token=calgary).json()['applications'] == []
    assert engine.request('GET', f'/api/cases/{case.id}', token=calgary).status == 404

    edmonton = actor(engine, 'reviewer:edmonton', calgary)
    queue = engine.request('GET', '/api/review/queue', token=edmonton).json()
    assert queue['reviewer_id'] == profiles['reviewer:edmonton']['userId']
    assert [(row['id'], row['status'], row['claim']) for row in queue['applications']] == [(case.id, 'submitted', None)]
    assert engine.request('GET', f'/api/cases/{case.id}', token=edmonton).json()['owner_id'] == applicant_id

    claimed = engine.request('POST', f'/api/review/{case.id}/claim', token=edmonton, json_body={})
    assert claimed.status == 200 and claimed.json()['claim']['reviewer_id'] == profiles['reviewer:edmonton']['userId']
    version = engine.request('GET', f'/api/cases/{case.id}', token=edmonton).json()['version']
    returned = engine.request('POST', f'/api/review/{case.id}/decision', token=edmonton, json_body={
        'outcome': 'return', 'message': 'Add the mailing address for the representative.',
        'items': [{'field': 'mailing_address', 'note': 'Missing unit number.'}], 'expected_version': version})
    assert returned.status == 200, returned.body
    assert returned.json()['status'] == 'returned'

    applicant = actor(engine, 'applicant', edmonton)
    mine = engine.request('GET', '/api/me/applications', token=applicant).json()['applications']
    assert [(row['id'], row['status']) for row in mine] == [(case.id, 'returned')]
    thread = engine.request('GET', f'/api/cases/{case.id}/messages', token=applicant).json()
    assert thread['decision']['outcome'] == 'return'
    assert any('mailing address' in message['body'] for message in thread['messages'])
    assert engine.request('POST', f'/api/review/{case.id}/claim', token=applicant, json_body={}).status == 404, \
        'the access policy hides a case from anyone who may not review it'
    assert engine.request('GET', f'/api/cases/{case.id}', token=applicant).json()['status'] == 'returned'
    assert engine.request('POST', f'/api/auth/onboarding', token=applicant,
                          json_body={'role': 'reviewer', 'authority': 'edmonton'}).status == 403


def test_a_reviewer_never_sees_an_application_they_own(shared):
    engine, profiles, db = shared
    reviewer_id = profiles['reviewer:calgary']['userId']
    case = complete_case()
    case.owner_id, case.authority, case.status = reviewer_id, 'calgary', 'submitted'
    store_with_synthetic_files(CaseStore(db), case)
    token = actor(engine, 'reviewer:calgary')
    assert engine.request('GET', '/api/review/queue', token=token).json()['applications'] == []
    assert engine.request('POST', f'/api/review/{case.id}/claim', token=token, json_body={}).status == 404
    assert engine.request('POST', f'/api/cases/{case.id}/submit', token=token, json_body={}).status in {403, 409}
