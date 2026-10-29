import sqlite3
from contextlib import closing

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


def signal_room(client):
    code = room(client)['code']
    ana, ben, cy = (data(client.post(f'/studio/rooms/{code}/people', json={'name': name}))['id']
                    for name in ('Ana', 'Ben', 'Cy'))
    return code, ana, ben, cy


def send(client, code, sender, to, kind='offer', payload=None):
    return client.post(f'/studio/rooms/{code}/signals', json={'from': sender, 'to': to, 'kind': kind, 'data': payload})


def inbox(client, code, person, after=None):
    params = {'to': person} if after is None else {'to': person, 'after': after}
    response = client.get(f'/studio/rooms/{code}/signals', params=params)
    assert response.status_code == 200
    return data(response)


def test_signal_routes_require_sign_in(app):
    with TestClient(app, base_url='http://localhost') as anonymous:
        assert anonymous.post('/studio/rooms/ABCDEF/signals', json={}).status_code == 401
        assert anonymous.get('/studio/rooms/ABCDEF/signals', params={'to': 'x', 'after': 0}).status_code == 401


def test_signals_arrive_in_order_for_their_recipient_only(client):
    code, ana, ben, cy = signal_room(client)
    assert inbox(client, code, ben) == {'signals': [], 'last': 0}

    sdp = {'pc': 'p1', 'to': None, 'description': {'type': 'offer', 'sdp': 'v=0'}}
    first = send(client, code, ana, ben, 'offer', sdp)
    assert first.status_code == 201
    seqs = [data(first)['seq']]
    seqs.append(data(send(client, code, ana, cy, 'offer', sdp))['seq'])
    seqs.append(data(send(client, code, ana, ben, 'candidate', {'candidates': [{'candidate': 'c1'}]}))['seq'])
    seqs.append(data(send(client, code, cy, ben, 'bye'))['seq'])
    assert seqs == sorted(seqs) and len(set(seqs)) == 4

    got = inbox(client, code, ben, after=0)
    assert [(s['from'], s['kind']) for s in got['signals']] == [(ana, 'offer'), (ana, 'candidate'), (cy, 'bye')]
    assert got['signals'][0]['data'] == sdp and got['signals'][2]['data'] is None
    assert all(isinstance(s['at'], int) for s in got['signals']) and got['last'] == seqs[-1]
    assert [s['kind'] for s in inbox(client, code, ben, after=got['signals'][0]['seq'])['signals']] == ['candidate', 'bye']
    assert inbox(client, code, ben, after=got['last']) == {'signals': [], 'last': got['last']}
    # Without a cursor a fresh page only learns where the queue ends.
    assert inbox(client, code, ben) == {'signals': [], 'last': seqs[-1]}
    assert [s['kind'] for s in inbox(client, code, cy, after=0)['signals']] == ['offer']

    other = room(client)['code']
    dee = data(client.post(f'/studio/rooms/{other}/people', json={'name': 'Dee'}))['id']
    assert client.get(f'/studio/rooms/{other}/signals', params={'to': ben, 'after': 0}).status_code == 404
    assert inbox(client, other, dee, after=0) == {'signals': [], 'last': 0}


def test_signals_are_checked(client):
    code, ana, ben, _ = signal_room(client)
    assert send(client, code, ana, 'nobody').status_code == 404
    assert send(client, code, 'nobody', ben).status_code == 404
    assert send(client, code, ana, ana).status_code == 422
    assert send(client, code, ana, ben, 'hello').status_code == 422
    assert send(client, 'ZZZZZZ', ana, ben).status_code == 404
    assert client.post(f'/studio/rooms/{code}/signals', json={'from': ana, 'to': ben, 'kind': 'bye', 'x': 1}).status_code == 422
    assert send(client, code, ana, ben, 'offer', {'sdp': 'x' * (64 * 1024)}).status_code == 413
    assert send(client, code, ana, ben, 'offer', {'sdp': 'x' * (60 * 1024)}).status_code == 201
    assert client.get(f'/studio/rooms/{code}/signals', params={'to': 'nobody', 'after': 0}).status_code == 404
    assert client.get(f'/studio/rooms/{code}/signals', params={'to': ben, 'after': -1}).status_code == 422
    client.delete(f'/studio/rooms/{code}/people/{ben}')
    assert send(client, code, ana, ben).status_code == 404


def test_signals_expire_after_ten_minutes(client, monkeypatch, tmp_path):
    code, ana, ben, _ = signal_room(client)
    old = data(send(client, code, ana, ben, 'offer', {'n': 1}))['seq']
    now = studio_store.time.time()
    monkeypatch.setattr(studio_store.time, 'time', lambda: now + 9 * 60)
    send(client, code, ana, ben, 'candidate', {'n': 2})
    assert [s['data']['n'] for s in inbox(client, code, ben, after=0)['signals']] == [1, 2]

    monkeypatch.setattr(studio_store.time, 'time', lambda: now + 10 * 60 + 1)
    assert [s['data']['n'] for s in inbox(client, code, ben, after=0)['signals']] == [2]
    assert data(send(client, code, ana, ben, 'bye'))['seq'] > old
    with closing(sqlite3.connect(tmp_path / 'studio.sqlite')) as db:
        assert db.execute('SELECT seq FROM studio_signals ORDER BY seq').fetchall() == [(old + 1,), (old + 2,)]


def test_named_room_is_made_once_and_shared(client):
    first = client.post('/studio/rooms', json={'code': 'batats'})
    assert first.status_code == 201 and data(first)['code'] == 'BATATS'
    client.post('/studio/rooms/BATATS/people', json={'name': 'Ana'})
    again = client.post('/studio/rooms', json={'code': 'BATATS'})
    assert again.status_code == 200 and [p['name'] for p in data(again)['people']] == ['Ana']
    assert data(client.get('/studio/rooms/BATATS'))['live'] is None
    for bad in ('BATAT', 'BATATSS', 'BAT0TS', 'BATIT1', 'BA-TAT'):
        assert client.post('/studio/rooms', json={'code': bad}).status_code == 422
    assert client.post('/studio/rooms').status_code == 201
    assert client.post('/studio/rooms', json={}).status_code == 201


def live_body(person_id, **extra):
    return {'presenterId': person_id, 'groupId': 'intro', 'slide': 2, 'recording': True, 'remainingMs': 30_000,
            'targetMs': 40_000, 'at': 1_700_000_000_000, **extra}


def test_live_state_is_shared_through_the_room(client):
    code = room(client)['code']
    ana = data(client.post(f'/studio/rooms/{code}/people', json={'name': 'Ana'}))
    ben = data(client.post(f'/studio/rooms/{code}/people', json={'name': 'Ben'}))
    put = client.put(f'/studio/rooms/{code}/live', params={'person': ana['id']}, json=live_body(ana['id']))
    assert put.status_code == 200 and put.json()['slide'] == 2
    live = data(client.get(f'/studio/rooms/{code}'))['live']
    assert live['presenterId'] == ana['id'] and live['groupId'] == 'intro' and live['at'] == 1_700_000_000_000
    assert 29_000 < live['remainingMs'] <= 30_000 and live['targetMs'] == 40_000

    # Someone else's stop does not end Ana's take; hers does.
    assert client.put(f'/studio/rooms/{code}/live', params={'person': ben['id']}, content='null',
                      headers={'Content-Type': 'application/json'}).status_code == 200
    assert data(client.get(f'/studio/rooms/{code}'))['live']['presenterId'] == ana['id']
    client.put(f'/studio/rooms/{code}/live', params={'person': ana['id']}, content='null',
               headers={'Content-Type': 'application/json'})
    assert data(client.get(f'/studio/rooms/{code}'))['live'] is None


def test_live_state_needs_a_person_in_the_room(client):
    code = room(client)['code']
    other = room(client)['code']
    ana = data(client.post(f'/studio/rooms/{code}/people', json={'name': 'Ana'}))
    ben = data(client.post(f'/studio/rooms/{code}/people', json={'name': 'Ben'}))
    assert client.put(f'/studio/rooms/{other}/live', params={'person': ana['id']},
                      json=live_body(ana['id'])).status_code == 404
    assert client.put(f'/studio/rooms/{code}/live', params={'person': 'nobody'},
                      json=live_body('nobody')).status_code == 404
    assert client.put(f'/studio/rooms/{code}/live', params={'person': ben['id']},
                      json=live_body(ana['id'])).status_code == 403
    assert client.put(f'/studio/rooms/{code}/live', json=live_body(ana['id'])).status_code == 422
    assert client.put(f'/studio/rooms/{code}/live', params={'person': ana['id']},
                      json=live_body(ana['id'], remainingMs=1.5)).status_code == 422


def test_live_state_goes_stale_after_ten_seconds(client, monkeypatch):
    code = room(client)['code']
    ana = data(client.post(f'/studio/rooms/{code}/people', json={'name': 'Ana'}))
    client.put(f'/studio/rooms/{code}/live', params={'person': ana['id']}, json=live_body(ana['id']))
    now = studio_store.time.time()
    monkeypatch.setattr(studio_store.time, 'time', lambda: now + 6)
    assert 23_000 < data(client.get(f'/studio/rooms/{code}'))['live']['remainingMs'] <= 24_000
    monkeypatch.setattr(studio_store.time, 'time', lambda: now + 10.5)
    assert data(client.get(f'/studio/rooms/{code}'))['live'] is None
