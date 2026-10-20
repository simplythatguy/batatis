"""Public callers cannot promote their own answers into authority decisions."""
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Source
from engine.professional import professional_involvement
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_section_d_issues import codes_with_rules
from engine.tests.test_unc_applicant_source import CLEARING_ANSWERS, _case


@pytest.mark.parametrize('source_type', ['officer', 'professional', 'code'])
def test_public_caller_cannot_forge_a_cleared_professional_screen(tmp_path, source_type):
    codes = codes_with_rules()
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store, codes))
    case_id = client.post('/cases', json={'title': 'SYNTHETIC source-trust test'}).json()['id']
    forged = _case(CLEARING_ANSWERS, source_type=source_type, pathway='acceptable')
    responses = [client.post(f'/cases/{case_id}/facts', json=item.model_dump()) for item in forged.facts]
    assert client.get(f'/cases/{case_id}/professional').json()['required'] != 'no'
    assert all(response.status_code == 422 for response in responses)
    stored = store.get(case_id)
    assert stored.facts == []


@pytest.mark.parametrize('source_type', ['user_text', 'user_click', 'file', 'drawing'])
def test_applicant_sources_keep_their_original_provenance(tmp_path, source_type):
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store, codes_with_rules()))
    case_id = client.post('/cases', json={'title': 'SYNTHETIC applicant-source test'}).json()['id']
    item = fact('professional_scope_resolved', True,
                source=Source(type=source_type, ref='synthetic-applicant', quote='SYNTHETIC answer'))
    response = client.post(f'/cases/{case_id}/facts', json=item.model_dump())
    assert response.status_code == 200
    assert store.get(case_id).facts[0].source.type == source_type
    assert client.get(f'/cases/{case_id}/professional').json()['required'] != 'no'


def test_trusted_internal_records_still_resolve_without_public_source_promotion():
    case = _case(CLEARING_ANSWERS, source_type='officer', pathway='acceptable')
    assert professional_involvement(case, codes_with_rules()).required == 'no'
