import base64
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
import pytest

from engine.api import create_app
from engine.models import Case
from engine.store import CaseStore, VersionConflict
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_accounts import signup, onboard
from engine.workspace import content_hash


def signature_image():
    image = Image.new('RGBA', (400, 100), (255, 255, 255, 0))
    ImageDraw.Draw(image).line([(20, 75), (55, 15), (70, 70), (120, 30), (200, 65), (370, 30)], fill='black', width=3)
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret"}')
    store = CaseStore(tmp_path / 'cases.sqlite')
    with TestClient(create_app(store=store), base_url='http://localhost') as client:
        assert signup(client).status_code == 201
        owner = onboard(client)
        case = store.put(Case(owner_id=owner['id'], authority='edmonton', facts=[fact('owner_name', 'Ada Owner')]))
        yield client, store, case, f'/cases/{case.id}'


def sign(client, path, role='owner', **overrides):
    return client.put(path + '/signatures/' + role, json={
        'name': 'Ada Owner', 'method': 'drawn', 'image': signature_image(), **overrides})


def test_old_case_defaults_and_workspace_roundtrip(workspace):
    client, store, case, path = workspace
    assert Case.model_validate({'id': 'old'}).workspace.signatures == []
    empty = client.get(path + '/workspace').json()
    assert empty['signers'] == [{'role': 'owner', 'name': 'Ada Owner', 'required': True}]
    assert empty['consent'] is None and empty['history'] == []
    result = sign(client, path)
    assert result.status_code == 200, result.text
    signed = result.json()
    assert signed['signed_on'] == datetime.now(ZoneInfo('America/Edmonton')).date().isoformat()
    assert signed['content_hash'] == empty['content_hash']
    assert client.get(path + '/workspace').json()['signatures'][0]['current'] is True
    consent = client.put(path + '/consent', json={'agreed': True})
    assert consent.status_code == 200 and consent.json()['agreed'] is True and consent.json()['at']
    assert client.get(path + '/workspace').json()['content_hash'] == empty['content_hash']
    store.add_fact(case.id, fact('alternative_description', 'Changed proposal'))
    assert client.get(path + '/workspace').json()['signatures'][0]['current'] is False
    assert sign(client, path).status_code == 200
    assert client.get(path + '/workspace').json()['signatures'][0]['current'] is True
    assert client.delete(path + '/signatures/owner').status_code == 200
    assert client.get(path + '/workspace').json()['signatures'] == []


def test_required_representative_respects_latest_value_and_not_applicable(workspace):
    client, store, case, path = workspace
    assert sign(client, path, 'owner_rep').status_code == 422
    store.add_fact(case.id, fact('owner_rep_name', 'Rita Representative'))
    assert len(client.get(path + '/workspace').json()['signers']) == 2
    assert sign(client, path, 'owner_rep', name='Rita Representative').status_code == 200
    store.add_fact(case.id, fact('not_applicable.owner_rep', 'No representative'))
    assert len(client.get(path + '/workspace').json()['signers']) == 1


@pytest.mark.parametrize('changes', [
    {'image': 'data:image/png;base64,bm90IGEgcG5n'}, {'image': 'data:image/png;base64,@@@'},
    {'image': 'data:image/jpeg;base64,aA=='}, {'image': 'data:image/png;base64,' + 'a' * 280000},
    {'name': '  '}, {'method': 'automatic'}, {'content_hash': 'forged'}, {'signed_on': '2001-01-01'},
])
def test_signature_input_cannot_forge_or_bypass_png_bounds(workspace, changes):
    client, _, _, path = workspace
    assert sign(client, path, **changes).status_code == 422
    assert client.get(path + '/workspace').json()['signatures'] == []


def test_history_is_bounded_and_does_not_invalidate_signature(workspace):
    client, _, _, path = workspace
    sign(client, path)
    def entry(i):
        return {'id': str(i), 'at': '2026-10-26T12:00:00Z', 'block': 'process.rationale',
                'label': 'Rationale', 'before': 'Before', 'after': 'After', 'by': 'ai'}
    assert client.post(path + '/history', json={'entries': [entry(i) for i in range(300)]}).status_code == 200
    assert client.post(path + '/history', json={'entries': [entry(300)]}).status_code == 200
    result = client.get(path + '/workspace').json()
    assert len(result['history']) == 300
    assert [result['history'][i]['id'] for i in (0, -1)] == ['300', '1']
    assert result['signatures'][0]['current'] is True


def test_workspace_writes_return_the_case_version_the_next_save_needs(workspace):
    # QA 2026-10-28: draft save, then history save, then the next draft save or submit was a false 409.
    client, store, case, path = workspace
    entry = {'id': 'h1', 'at': '2026-10-28T12:00:00Z', 'block': 'process.rationale',
             'label': 'Rationale', 'before': 'Before', 'after': 'After', 'by': 'you'}
    saved = client.patch(path + '/draft', json={'expected_version': case.version, 'facts': []})
    assert saved.status_code == 200, saved.text
    stale = saved.json()['version']
    history = client.post(path + '/history', json={'entries': [entry]})
    assert history.status_code == 200, history.text
    assert history.json()['history'][0]['id'] == 'h1'
    version = history.json()['case_version']
    assert version == store.get_version(case.id) == stale + 1
    assert client.patch(path + '/draft', json={'expected_version': stale, 'facts': []}).status_code == 409
    after_history = client.patch(path + '/draft', json={'expected_version': version, 'facts': []})
    assert after_history.status_code == 200, after_history.text
    writes = [sign(client, path), client.put(path + '/consent', json={'agreed': True}),
              client.delete(path + '/signatures/owner')]
    for write in writes:
        assert write.status_code == 200, write.text
    assert [w.json()['case_version'] for w in writes] == [after_history.json()['version'] + n for n in (1, 2, 3)]
    submit = client.post(path + '/submit', json={'expected_version': writes[-1].json()['case_version']})
    assert 'concurrent' not in submit.text and 'changed' not in submit.text, submit.text


def test_access_owner_only_writes_and_reviewer_read(workspace):
    client, store, case, path = workspace
    with TestClient(client.app, base_url='http://localhost') as other:
        assert other.get(path + '/workspace').status_code == 404
        assert signup(other, 'officer@example.test').status_code == 201
        onboard(other, 'reviewer')
        assert other.get(path + '/workspace').status_code == 404
        current = store.get(case.id)
        current.status = 'submitted'
        store.put(current)
        assert other.get(path + '/workspace').status_code == 200
        assert sign(other, path).status_code == 404
        assert other.put(path + '/consent', json={'agreed': True}).status_code == 404
    assert sign(client, path).status_code == 409
    assert client.post(path + '/history', json={'entries': []}).status_code == 409
    current = store.get(case.id)
    current.status = 'returned'
    store.put(current)
    assert sign(client, path).status_code == 200


def test_workspace_concurrent_write_reports_conflict(workspace, monkeypatch):
    client, store, _, path = workspace
    def concurrent(case, **kwargs):
        raise VersionConflict(case.id, expected=kwargs.get('expected_version'), actual=999)
    monkeypatch.setattr(store, 'put', concurrent)
    assert sign(client, path).status_code == 409
    assert client.get(path + '/workspace').json()['signatures'] == []


def test_hash_uses_current_confirmed_content_and_documents():
    case = Case(facts=[fact('owner_name', 'Ada'), fact('process.rationale', 'Applicant words')])
    original = content_hash(case)
    case.title = 'Only the application label'
    case.facts.append(fact('owner_signature_date', '2020-01-01'))
    assert content_hash(case) == original
    case.facts.append(fact('process.rationale', 'Applicant words'))
    assert content_hash(case) == original
    proposed = fact('process.rationale', 'Unconfirmed words')
    proposed.status = 'unconfirmed'
    case.facts.append(proposed)
    assert content_hash(case) != original


def test_history_keeps_one_copy_of_a_retried_entry_and_stays_within_its_size_limit():
    from engine.models_workspace import HISTORY_MAX_CHARS, HistoryEntry, trim_history
    entry = lambda n, size=10: HistoryEntry(id=f'h{n}', at=f'2026-10-26T00:00:{n:02d}Z', block='process.risk',
                                             label='Risk', before='a' * size, after='b' * size, by='you')
    assert [e.id for e in trim_history([entry(1), entry(2), entry(1)])] == ['h1', 'h2']
    kept = trim_history([entry(n, 60000) for n in range(12)])
    assert [e.id for e in kept] == [f'h{n}' for n in range(4, 12)], 'the newest entries that fit are kept'
    assert sum(len(e.before) + len(e.after) for e in kept) <= HISTORY_MAX_CHARS
