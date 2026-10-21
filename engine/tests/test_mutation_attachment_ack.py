"""K26-14: a full-Case mutation acknowledgment must agree with the owned-file snapshot."""
import pytest

from engine.models import Case, EvidenceItem, Fact, Source
from engine.section_d import supporting_documents
from engine.tests.test_reference_withdrawal import context  # noqa: F401 - both real backend adapters


def attachment(slot, reference):
    return Fact(field=f'evidence.{slot}.file_ref', value=reference, kind='pointed', status='confirmed',
                source=Source(type='file', ref=reference, quote='Synthetic retained provenance'))


@pytest.mark.parametrize('writer', ['add_fact', 'remove_evidence'])
@pytest.mark.parametrize('ghost_kind', ['missing', 'cross_case'])
def test_mutation_ack_uses_current_owned_inventory_and_row_version(context, writer, ghost_kind):
    client, store = context
    case = store.put(Case())
    other = store.put(Case())
    payload = b'%PDF-1.4 Synthetic owned bytes\r\n'
    owned = store.put_file(case.id, 'owned.pdf', payload)['id']
    foreign = store.put_file(other.id, 'foreign.pdf', b'%PDF-1.4 synthetic foreign bytes')['id']
    reference = foreign if ghost_kind == 'cross_case' else 'file_synthetic_missing'
    ghost = attachment('nested.legacy', reference)
    actual = attachment('actual', owned)
    case.facts = [ghost, actual]
    case.evidence = [EvidenceItem(id='nested.legacy', description='Applicant legacy listing', status='evidence_listed'),
                     EvidenceItem(id='actual', description='Applicant actual upload', status='evidence_listed'),
                     EvidenceItem(id='discard', description='Only this slot may be removed')]
    store.put(case, expected_version=1)
    before = store.get_version(case.id)
    assert client.get(f'/cases/{case.id}').json()['evidence'][0]['kind'] == 'text'

    if writer == 'add_fact':
        note = Fact(field='project.note', value='Applicant ordinary answer', kind='pointed', status='confirmed',
                    source=Source(type='user_text', ref='Synthetic applicant', quote='Applicant ordinary answer'))
        response = client.post(f'/cases/{case.id}/facts', json=note.model_dump())
    else:
        response = client.delete(f'/cases/{case.id}/evidence/discard')
    assert response.status_code == 200, response.text
    # Assert the reported attachment state before the new version contract, so this
    # reproduces the parent's ghost-response bug rather than merely a missing version.
    body = response.json()
    assert body['evidence'][0]['kind'] == 'text'
    assert body['evidence'][1]['kind'] == 'file'
    assert next(f for f in body['facts'] if f['id'] == ghost.id)['status'] == 'unconfirmed'
    acknowledged = Case.model_validate(body)
    assert acknowledged.evidence[0].description == 'Applicant legacy listing'
    returned_ghost = next(f for f in acknowledged.facts if f.id == ghost.id)
    assert returned_ghost.status == 'unconfirmed'
    assert returned_ghost.value == ghost.value and returned_ghost.source == ghost.source
    assert next(f for f in acknowledged.facts if f.id == actual.id).status == 'confirmed'
    assert acknowledged.evidence[1].kind == 'file'
    assert [doc.id for doc in supporting_documents(acknowledged)] == ['actual']
    assert acknowledged.version == before + 1 == store.get_version(case.id)
    assert acknowledged == store.get(case.id)
    assert store.get_file(case.id, owned)['data'] == payload
    assert store.get_file(other.id, foreign)['data'] == b'%PDF-1.4 synthetic foreign bytes'
    if writer == 'remove_evidence':
        assert not any(item.id == 'discard' for item in acknowledged.evidence)
