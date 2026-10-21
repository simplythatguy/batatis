"""The engagement exception cannot waive an independently unresolved source chain.

These synthetic-corpus tests isolate policy, not CodeDB validation or credentials.
The accompanying private replay uses the actual read-only CodeDB and SCC exporter.
"""
import pytest

from engine.professional import NOT_ENGAGED_ITEM
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_professional_export_gate import package  # noqa: F401 - shared fixture
from engine.tests.test_professional_review_regressions import _cleared
from engine.tests.test_professional_source_failclosed import _OFFICER, _client, _withhold


@pytest.mark.parametrize('division,provision_id', [('B', '9.15.3.3.(2)'), ('C', '2.4.1.2.(1)')])
@pytest.mark.parametrize('failure', ['record', 'blank', 'whitespace'])
@pytest.mark.parametrize('ahj_requires', [False, True], ids=['source-duty', 'independent-ahj-duty'])
def test_not_engaged_keeps_source_blocker_and_identity_warning(
        package, tmp_path, division, provision_id, failure, ahj_requires):
    case, codes = package
    _cleared(case)
    case.facts += [fact('supported_joist_span_m', 5.2), fact('professional_status', 'not_engaged')]
    if ahj_requires:
        case.facts.append(fact('ahj_requires_professional', True, source=_OFFICER))
    _withhold(codes, division, provision_id, failure)
    client = _client(case, codes, tmp_path)
    before = client.get(f'/cases/{case.id}').json()

    response = client.get(f'/cases/{case.id}/gaps')
    assert response.status_code == 200, response.text
    gaps = response.json()['items']
    assert any(g['field'] == 'professional_source' and g['severity'] == 'blocking'
               and provision_id in g['message'] for g in gaps)
    warnings = [g for g in gaps if g['id'] == 'professional:not_engaged']
    assert len(warnings) == 1
    assert warnings[0]['severity'] == 'warning' and warnings[0]['message'] == NOT_ENGAGED_ITEM
    assert not {'professional_confirmation', 'responsible_professional', 'professional_qualifications',
                'professional_authentication'} & {g['field'] for g in gaps}

    response = client.post(f'/cases/{case.id}/export', json={'draft': False})
    assert response.status_code == 409, response.text[:300]
    assert any('professional_source' in reason and provision_id in reason
               for reason in response.json()['detail']['reasons'])
    if ahj_requires:
        assert client.get(f'/cases/{case.id}/professional').json()['required'] == 'yes'
    assert client.get(f'/cases/{case.id}').json() == before
