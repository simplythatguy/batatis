"""J01: the submit transition must match the acknowledged applicant save."""
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_review import owned, scene


def test_submit_pins_the_saved_version_and_preserves_private_access(scene):
    store, clients, _ = scene
    case = owned(scene, status='returned', complete=True)
    current = store.add_fact(case.id, fact('legalDescription', 'SYNTHETIC latest revision C'))
    before = current.model_dump()

    other = clients['other'].post(f'/cases/{case.id}/submit', json={'expected_version': case.version})
    missing = clients['owner'].post('/cases/not-a-visible-case/submit', json={'expected_version': case.version})
    assert other.status_code == missing.status_code == 404
    stale = clients['owner'].post(f'/cases/{case.id}/submit', json={'expected_version': case.version})
    assert stale.status_code == 409
    assert store.get(case.id).model_dump() == before

    sent = clients['owner'].post(f'/cases/{case.id}/submit', json={'expected_version': current.version})
    assert sent.status_code == 200, sent.text
    assert sent.json()['version'] == current.version + 1
    assert sent.json()['status'] == 'submitted'
    assert any(entry['value'] == 'SYNTHETIC latest revision C' for entry in sent.json()['facts'])
    assert clients['owner'].post(f'/cases/{case.id}/submit',
                                 json={'expected_version': current.version}).status_code == 409


def test_submit_cas_retry_rechecks_the_pinned_version(scene, monkeypatch):
    store, clients, _ = scene
    case = owned(scene, status='returned', complete=True)
    original_put = store.put
    raced = False

    def put_with_concurrent_save(candidate, *, expected_version=None):
        nonlocal raced
        if candidate.id == case.id and not raced:
            raced = True
            other = store.get(case.id)
            other.facts.append(fact('legalDescription', 'SYNTHETIC concurrent edit'))
            original_put(other, expected_version=other.version)
        return original_put(candidate, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', put_with_concurrent_save)
    response = clients['owner'].post(f'/cases/{case.id}/submit', json={'expected_version': case.version})
    assert raced and response.status_code == 409
    saved = store.get(case.id)
    assert saved.version == case.version + 1
    assert saved.status == 'returned'
    assert saved.messages == case.messages
    assert saved.status_history == case.status_history
    assert saved.facts[-1].value == 'SYNTHETIC concurrent edit'
