"""Synthetic source-failure contracts; the real CodeDB/SCC probes run separately.

The imported package deliberately stubs citation validation. These tests exercise
administrative policy and public responses, not source acceptance or qualifications.
"""
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.completeness import professional_involvement_gaps
from engine.export.scc import blockers, load_field_map
from engine.human_review import human_reviews
from engine.models import Case, Source
from engine.professional import NOT_ENGAGED_ITEM, professional_involvement
from engine.section_d_issues import render_practice
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_professional_export_gate import package  # noqa: F401 - shared fixture
from engine.tests.test_professional_review_regressions import _cleared

_OFFICER = Source(type='officer', ref='SYNTHETIC internal authority control')


def _withhold(codes, division, provision_id, failure):
    key = (division, provision_id)
    if failure == 'record':
        del codes.rows[key]
    else:
        codes.rows[key]['citation'] = '' if failure == 'blank' else ' \t '


def _client(case, codes, tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    store.put(case)
    return TestClient(create_app(store, codes), raise_server_exceptions=False)


@pytest.mark.parametrize('division,provision_id', [('C', '2.4.1.2.(1)'), ('B', '9.15.3.3.(2)')])
@pytest.mark.parametrize('failure', ['record', 'blank', 'whitespace'])
def test_detected_joist_trigger_abstains_across_public_seams(package, tmp_path, division, provision_id, failure):
    case, codes = package
    _cleared(case)
    assert professional_involvement(case, codes).required == 'no'
    assert blockers(case, load_field_map(), codes) == []
    case.facts.append(fact('supported_joist_span_m', 5.2))
    _withhold(codes, division, provision_id, failure)
    client = _client(case, codes, tmp_path)

    response = client.get(f'/cases/{case.id}/professional')
    assert response.status_code == 200
    result = response.json()
    assert result['required'] == 'depends'
    assert result['involvement'] == 'unresolved'
    assert any(provision_id in q and 'code reviewer' in q for q in result['questions'])
    issues = client.get(f'/cases/{case.id}/section-d/issues')
    assert issues.status_code == 200
    flag = issues.json()['items'][0]['practice_of_engineering']
    assert flag['value'] == 'unknown'
    assert (flag['division'], flag['rule']) == (division, provision_id)
    assert flag['citation'] is None
    assert 'HR-06' not in [r.trigger_id for r in human_reviews(case, codes)]
    gaps = client.get(f'/cases/{case.id}/gaps')
    assert gaps.status_code == 200
    assert any(g['severity'] == 'blocking' and g['field'] == 'professional_source'
               and provision_id in g['message'] for g in gaps.json()['items'])
    assert client.post(f'/cases/{case.id}/export', json={'draft': False}).status_code == 409


@pytest.mark.parametrize('field,value', [
    ('supported_joist_span_m', 5.2), ('hourly_wind_pressure_1in50_kPa', 1.25),
    ('reinforced_concrete', True),
])
@pytest.mark.parametrize('confirmed', [False, True])
def test_mandatory_promotion_derives_involvement_from_the_combined_decision(package, field, value, confirmed):
    case, codes = package
    _cleared(case)
    if confirmed:
        case.facts += [fact('professional.role', 'SYNTHETIC engineer'),
                       fact('professional.registration_number', 'SYNTHETIC-123')]
    case.facts.append(fact(field, value))
    result = professional_involvement(case, codes)
    assert result.required == 'yes'
    assert result.involvement == ('professional_involved' if confirmed else 'unresolved')
    assert result.routed_to == 'professional'
    assert ('professional.role' in result.missing_facts) is not confirmed


@pytest.mark.parametrize('provision_id', ['2.4.1.3.(1)', '2.4.1.4.(1)'])
@pytest.mark.parametrize('failure', ['record', 'blank', 'whitespace'])
def test_each_combined_system_dependency_abstains_with_its_own_identity(package, tmp_path, provision_id, failure):
    _, codes = package
    case = Case(title='SYNTHETIC unresolved system scope', provisions=['3.1.9.1.(1)'])
    _withhold(codes, 'C', provision_id, failure)
    client = _client(case, codes, tmp_path)
    response = client.get(f'/cases/{case.id}/professional')
    assert response.status_code == 200
    result = response.json()
    assert result['required'] == 'depends'
    assert any(provision_id in q and 'code reviewer' in q for q in result['questions'])
    issues = client.get(f'/cases/{case.id}/section-d/issues')
    assert issues.status_code == 200
    flag = issues.json()['items'][0]['practice_of_engineering']
    assert flag['value'] == 'unknown' and flag['citation'] is None
    assert (flag['division'], flag['rule']) == ('C', provision_id)
    gaps = client.get(f'/cases/{case.id}/gaps')
    assert gaps.status_code == 200
    assert any(g['severity'] == 'blocking' and provision_id in g['message']
               for g in gaps.json()['items'])
    assert client.post(f'/cases/{case.id}/export', json={'draft': False}).status_code == 409


@pytest.mark.parametrize('withhold_source', [False, True])
def test_qualified_professional_does_not_clear_a_missing_mandatory_source(package, tmp_path, withhold_source):
    case, codes = package
    _cleared(case)
    case.facts += [fact('supported_joist_span_m', 5.2), fact('ahj_requires_professional', True, source=_OFFICER),
                   fact('professional.role', 'SYNTHETIC engineer'),
                   fact('professional.registration_number', 'SYNTHETIC-123'),
                   fact('professional_seal', 'SYNTHETIC applicant authentication metadata'),
                   fact('professional_name', 'SYNTHETIC engineer'),
                   fact('professional.qualifications', 'SYNTHETIC stated qualifications')]
    if withhold_source:
        _withhold(codes, 'B', '9.15.3.3.(2)', 'blank')
    result = professional_involvement(case, codes)
    assert result.required == 'yes'  # The independent AHJ requirement remains positive.
    assert any(r.code == 'ahj_direction' and r.required == 'yes' for r in result.reasons)
    source_gaps = [g for g in professional_involvement_gaps(case, codes, [])
                   if g.field == 'professional_source']
    if withhold_source:
        assert any(g.severity == 'blocking' and '9.15.3.3.(2)' in g.message for g in source_gaps)
        assert any('professional_source' in reason for reason in blockers(case, load_field_map(), codes))
        client = _client(case, codes, tmp_path)
        assert client.post(f'/cases/{case.id}/export', json={'draft': False}).status_code == 409
    else:
        assert source_gaps == []
        assert blockers(case, load_field_map(), codes) == []


def test_source_gap_preserves_existing_professional_gaps_and_not_engaged_policy(package):
    case, codes = package
    _cleared(case)
    case.facts += [fact('supported_joist_span_m', 5.2), fact('ahj_requires_professional', True, source=_OFFICER)]
    _withhold(codes, 'B', '9.15.3.3.(2)', 'record')
    gaps = professional_involvement_gaps(case, codes, [])
    assert {'professional_source', 'professional_confirmation', 'responsible_professional',
            'professional_qualifications', 'professional_authentication'} <= {g.field for g in gaps}
    case.facts.append(fact('professional_status', 'not_engaged'))
    gaps = professional_involvement_gaps(case, codes, [])
    assert len(gaps) == 1 and gaps[0].severity == 'warning'
    assert gaps[0].message == NOT_ENGAGED_ITEM


@pytest.mark.parametrize('field,value,division,provision_id', [
    ('hourly_wind_pressure_1in50_kPa', 1.25, 'B', '9.23.3.5.(4)'),
    ('reinforced_concrete', True, 'B', '9.3.1.1.(3)'),
])
def test_other_part4_triggers_retain_the_missing_shared_dependency(package, field, value, division, provision_id):
    case, codes = package
    _cleared(case)
    case.facts.append(fact(field, value))
    _withhold(codes, 'C', '2.4.1.2.(1)', 'record')
    result = professional_involvement(case, codes)
    assert result.required == 'depends'
    assert any(r.code == f'mandatory:{division}:{provision_id}' for r in result.reasons)
    flag = render_practice(result, codes)
    assert flag.value == 'unknown' and flag.rule == '2.4.1.2.(1)' and flag.division == 'C'


@pytest.mark.parametrize('extra,division,provision_id,trigger_id', [
    ({'storeys': 4}, 'A', '1.3.3.3.(1)', 'HR-04'),
    ({'part10_building': True, 'part10_sprinklers': True}, 'B', '10.1.1.2.(2)', 'HR-12'),
])
def test_other_prerequisite_lookups_cannot_erase_a_detected_trigger(package, extra, division, provision_id, trigger_id):
    case, codes = package
    _cleared(case)
    case.facts += [fact(key, value) for key, value in extra.items()]
    assert professional_involvement(case, codes).required == 'yes'
    _withhold(codes, division, provision_id, 'blank')
    result = professional_involvement(case, codes)
    assert result.required == 'depends'
    assert any(provision_id in q for q in result.questions)
    assert trigger_id not in [r.trigger_id for r in human_reviews(case, codes)]
    assert any(g.severity == 'blocking' and provision_id in g.message
               for g in professional_involvement_gaps(case, codes, []))


def test_missing_source_reopens_previously_resolved_alternative_involvement(package):
    case, codes = package
    _cleared(case)
    case.facts += [fact('pathway', 'alternative'), fact('professional_judgement_required', True, source=_OFFICER),
                   fact('professional.role', 'SYNTHETIC engineer'),
                   fact('professional.registration_number', 'SYNTHETIC-123')]
    assert professional_involvement(case, codes).involvement == 'professional_involved'
    case.facts.append(fact('supported_joist_span_m', 5.2))
    assert professional_involvement(case, codes).involvement == 'professional_involved'
    _withhold(codes, 'B', '9.15.3.3.(2)', 'blank')
    result = professional_involvement(case, codes)
    assert result.required == 'depends' and result.involvement == 'unresolved'


def test_uncited_act_scope_is_not_mislabelled_as_a_failed_code_lookup(package):
    case, codes = package
    _cleared(case)
    case.facts += [fact('occupancy', 'multi_family'), fact('principal_dwelling_units', 4),
                   fact('total_unit_count', 5)]
    result = professional_involvement(case, codes)
    assert any(r.code == 'acts_units' and not r.citation for r in result.reasons)
    assert not any(g.field == 'professional_source' for g in professional_involvement_gaps(case, codes, []))
