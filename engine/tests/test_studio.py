import pytest
from fastapi.testclient import TestClient

from engine import studio_store
from engine.api import create_app
from engine.store import CaseStore
from engine.studio_store import CHUNK_BYTES
from engine.tests.test_accounts import signup


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    return create_app(store=CaseStore(tmp_path / 'studio.sqlite'))


@pytest.fixture
def client(app):
    with TestClient(app, base_url='http://localhost') as client:
        assert signup(client).status_code == 201
        yield client


def data(response):
    """The body without the privacy notice the HTTP guard puts on every JSON response."""
    return {key: value for key, value in response.json().items() if key != 'meta'}


def room(client):
    response = client.post('/studio/rooms')
    assert response.status_code == 201
    return data(response)


def take_body(person_id, size, group='intro', **extra):
    return {'groupId': group, 'personId': person_id, 'durationMs': 4200, 'cues': [{'slide': 1, 'atMs': 1500}],
            'mime': 'video/webm;codecs=vp9,opus', 'size': size, 'chunks': -(-size // CHUNK_BYTES), **extra}


def test_every_route_requires_sign_in(app):
    with TestClient(app, base_url='http://localhost') as anonymous:
        assert anonymous.post('/studio/rooms').status_code == 401
        assert anonymous.get('/studio/rooms/ABCDEF').status_code == 401
        assert anonymous.put('/studio/rooms/ABCDEF/takes/x/chunks/0', content=b'x').status_code == 401


def test_create_join_rejoin_and_leave(client):
    created = room(client)
    code = created['code']
    assert len(code) == 6 and not set(code) & set('0O1I')
    assert created['people'] == [] and created['assignments'] == {} and created['takes'] == {}

    ana = data(client.post(f'/studio/rooms/{code.lower()}/people', json={'name': '  Ana  '}))
    assert ana['name'] == 'Ana'
    assert data(client.post(f'/studio/rooms/{code}/people', json={'name': 'ANA'})) == ana
    ben = data(client.post(f'/studio/rooms/{code}/people', json={'name': 'Ben'}))
    assert client.post(f'/studio/rooms/{code}/people', json={'name': '   '}).status_code == 422
    assert client.post(f'/studio/rooms/{code}/people', json={'name': 'x' * 61}).status_code == 422

    state = data(client.get(f'/studio/rooms/{code.lower()}'))
    assert state['people'] == [ana, ben] and state['updatedAt'] > created['updatedAt']

    client.put(f'/studio/rooms/{code}/assignments/intro', json={'personId': ben['id']})
    state = data(client.delete(f'/studio/rooms/{code}/people/{ben["id"]}'))
    assert state['people'] == [ana] and state['assignments'] == {}
    assert client.get('/studio/rooms/ZZZZZZ').status_code == 404


def test_room_is_full_after_twelve(client):
    code = room(client)['code']
    for n in range(12):
        assert client.post(f'/studio/rooms/{code}/people', json={'name': f'P{n}'}).status_code == 200
    assert client.post(f'/studio/rooms/{code}/people', json={'name': 'late'}).status_code == 409
    assert client.post(f'/studio/rooms/{code}/people', json={'name': 'p3'}).status_code == 200


def test_assignments(client):
    code = room(client)['code']
    ana = data(client.post(f'/studio/rooms/{code}/people', json={'name': 'Ana'}))
    state = data(client.put(f'/studio/rooms/{code}/assignments/the-problem', json={'personId': ana['id']}))
    assert state['assignments'] == {'the-problem': ana['id']}
    state = data(client.put(f'/studio/rooms/{code}/assignments/the-problem', json={'personId': None}))
    assert state['assignments'] == {}
    assert client.put(f'/studio/rooms/{code}/assignments/the-problem', json={'personId': 'nobody'}).status_code == 404
    assert client.put(f'/studio/rooms/{code}/assignments/Bad_Id', json={'personId': ana['id']}).status_code == 422


def test_take_upload_download_round_trip_and_replace(client):
    code = room(client)['code']
    ana = data(client.post(f'/studio/rooms/{code}/people', json={'name': 'Ana'}))
    video = bytes(range(256)) * (CHUNK_BYTES // 256) + b'tail-bytes'
    take = client.post(f'/studio/rooms/{code}/takes', json=take_body(ana['id'], len(video)))
    assert take.status_code == 201
    take = data(take)
    assert take['chunks'] == 2 and take['received'] == 0 and take['cues'] == [{'slide': 1, 'atMs': 1500}]
    url = f'/studio/rooms/{code}/takes/{take["id"]}/chunks'
    octet = {'content-type': 'application/octet-stream'}

    assert client.put(f'{url}/0', content=video[:100], headers=octet).status_code == 422
    assert client.put(f'{url}/2', content=b'x', headers=octet).status_code == 404
    assert data(client.put(f'{url}/1', content=video[CHUNK_BYTES:], headers=octet)) == {'received': 1}
    assert data(client.put(f'{url}/1', content=video[CHUNK_BYTES:], headers=octet)) == {'received': 1}
    assert data(client.put(f'{url}/0', content=video[:CHUNK_BYTES], headers=octet)) == {'received': 2}
    assert data(client.get(f'/studio/rooms/{code}'))['takes']['intro']['received'] == 2

    downloaded = client.get(f'{url}/0').content + client.get(f'{url}/1').content
    assert downloaded == video
    assert client.get(f'{url}/0').headers['content-type'] == 'application/octet-stream'

    again = data(client.post(f'/studio/rooms/{code}/takes', json=take_body(ana['id'], 10)))
    assert client.get(f'{url}/0').status_code == 404
    assert client.put(f'{url}/0', content=video[:CHUNK_BYTES], headers=octet).status_code == 404
    state = data(client.get(f'/studio/rooms/{code}'))
    assert state['takes'] == {'intro': again}


def test_take_limits(client, monkeypatch):
    code = room(client)['code']
    ana = data(client.post(f'/studio/rooms/{code}/people', json={'name': 'Ana'}))
    post = lambda body: client.post(f'/studio/rooms/{code}/takes', json=body).status_code
    assert post(take_body(ana['id'], 150 * 1024 * 1024 + 1)) == 422
    assert post(take_body(ana['id'], 10, chunks=2)) == 422
    assert post(take_body(ana['id'], 10, mime='audio/webm')) == 422
    assert post(take_body(ana['id'], 10, cues=[{'slide': 0, 'atMs': 0}] * 101)) == 422
    assert post(take_body('nobody', 10)) == 404
    monkeypatch.setattr(studio_store, 'ROOM_MAX_BYTES', 25)
    assert post(take_body(ana['id'], 10, group='a')) == 201
    assert post(take_body(ana['id'], 10, group='b')) == 201
    assert post(take_body(ana['id'], 10, group='c')) == 413
    assert post(take_body(ana['id'], 15, group='b')) == 201  # replacing b frees its space
    take = data(client.post(f'/studio/rooms/{code}/takes', json=take_body(ana['id'], 5, group='a')))
    oversized = client.put(f'/studio/rooms/{code}/takes/{take["id"]}/chunks/0', content=b'x' * (CHUNK_BYTES + 1))
    assert oversized.status_code == 413


def test_expired_room_is_gone(client, monkeypatch):
    code = room(client)['code']
    later = studio_store.time.time() + studio_store.ROOM_SECONDS + 1
    monkeypatch.setattr(studio_store.time, 'time', lambda: later)
    assert client.get(f'/studio/rooms/{code}').status_code == 404
