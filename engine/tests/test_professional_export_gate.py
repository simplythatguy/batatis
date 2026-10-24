"""Synthetic public-export regression; no licence authenticity is asserted."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.export.scc import ExportBlocked, blockers, export_case, load_field_map
from engine.models import Case, Jurisdiction, Source
from engine.professional import professional_confirmed
from engine.section_c import section_c_rows
from engine.section_d_issues import section_d_issues
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_section_d_issues import NO_ROW, codes_with_rules


@pytest.fixture
def package(monkeypatch):
    # This fake corpus isolates identity gating; it is not citation-validation evidence.
    codes = codes_with_rules()
    codes.db_path = Path('unused-synthetic-corpus')
    monkeypatch.setattr('engine.completeness.validate_text', lambda *args, **kwargs: {'errors': []})
    values = dict(
        owner_name='SYNTHETIC owner', request_date='2026-10-20',
        mailing_address='SYNTHETIC address', municipal_address='SYNTHETIC site',
        legal_description='SYNTHETIC lot', representative='SYNTHETIC applicant', scope='site',
        alternative_description='SYNTHETIC departure', rationale='SYNTHETIC rationale',
        risk_assessment='SYNTHETIC risks', mitigating_measures='SYNTHETIC measures',
        assumptions_and_limits='SYNTHETIC limits', maintenance_operation='SYNTHETIC conditions',
        qualifications='SYNTHETIC author qualifications', occupancy='mercantile',
        storeys=5, part4_design=True, professional_name='SYNTHETIC named person',
        professional_seal='SYNTHETIC authentication metadata',
    )
    case = Case(title='SYNTHETIC export-gate fixture',
                jurisdiction=Jurisdiction(id='alberta-other', name='SYNTHETIC authority'),
                facts=[fact(key, value) for key, value in values.items()],
                provisions=[NO_ROW], section_c=section_c_rows([NO_ROW], codes))
    return case, codes


def test_named_and_sealed_person_cannot_bypass_professional_confirmation(package, tmp_path):
    case, codes = package
    assert professional_confirmed(case) is False
    assert any(issue.status == 'needs_professional' for issue in section_d_issues(case, codes))
    store = CaseStore(tmp_path / 'cases.sqlite')
    store.put(case)
    response = TestClient(create_app(store, codes)).post(f'/cases/{case.id}/export', json={'draft': False})
    assert response.status_code == 409
    assert any('professional_confirmation' in reason for reason in response.json()['detail']['reasons'])
    reasons = blockers(case, load_field_map(), codes)
    assert reasons and all('professional_confirmation' in reason for reason in reasons)


@pytest.mark.parametrize('source_type,status', [('file', 'confirmed'), ('user_text', 'unconfirmed')])
def test_file_or_unconfirmed_role_does_not_clear_the_export_gap(package, source_type, status):
    case, codes = package
    case.facts.append(fact('professional.role', 'SYNTHETIC engineer', status=status,
                           source=Source(type=source_type, ref='synthetic-fixture', quote='SYNTHETIC engineer')))
    assert professional_confirmed(case) is False
    assert any('professional_confirmation' in reason for reason in blockers(case, load_field_map(), codes))


def test_applicant_confirmation_closes_only_the_identity_gap_and_withdrawal_reopens_it(package):
    case, codes = package
    case.facts.append(fact('professional.role', 'SYNTHETIC engineer'))
    assert professional_confirmed(case) is True
    assert blockers(case, load_field_map(), codes) == []
    case.facts.append(fact('professional.role', '', status='unconfirmed'))
    assert professional_confirmed(case) is False
    assert any('professional_confirmation' in reason for reason in blockers(case, load_field_map(), codes))


def test_draft_remains_available_but_not_engaged_never_waives_a_professional_gate(package, monkeypatch):
    from engine.export.scc import FormNotFound

    case, codes = package
    def no_form(*args, **kwargs):
        raise FormNotFound('fixture')

    monkeypatch.setattr('engine.export.scc.load_form', no_form)
    with pytest.raises(FormNotFound):
        export_case(case, draft=True, codes=codes)
    with pytest.raises(ExportBlocked):
        export_case(case, draft=False, codes=codes)
    case.facts.append(fact('professional_status', 'not_engaged'))
    assert any('professional_confirmation' in reason for reason in blockers(case, load_field_map(), codes))
    with pytest.raises(ExportBlocked):
        export_case(case, draft=False, codes=codes)
