"""An officer's "Required" asks only for what is missing, and survives a resubmission that leaves it alone.

QA 2026-10-28: after "Required", two asks appeared ("authentication information…" and "a named registered
professional…") although the applicant had named Example Engineer, registration EXAMPLE-0000, on the
attached document, so Accept never came back. Every resubmission then reset the determination.
"""
import pytest

from engine.codes import Codes
from engine.completeness import check_completeness
from engine.models import ProfessionalRequirementResolution
from engine.professional_resolution import current_resolution, requirement_fingerprint
from engine.tests.case_builder_fixtures import complete_case, fact


@pytest.fixture(scope='module')
def codes():
    return Codes()


def required(case):
    case.professional_resolutions.append(ProfessionalRequirementResolution(
        required=True, scope='SYNTHETIC rated assembly', basis='SYNTHETIC an engineer takes responsibility.',
        reference='SYNTHETIC-REF-1', by_id='officer', by_name='Officer', content_fingerprint=requirement_fingerprint(case)))
    return case


def professional_gaps(case, codes):
    return {gap.field: gap for gap in check_completeness(case, codes)
            if gap.field in ('responsible_professional', 'professional_authentication', 'professional_confirmation')}


def named_on_their_document():
    case = complete_case()
    case.facts.append(fact('evidence.synthetic.responsible_party', 'R. Singh, P.Eng. (A00000)'))
    return case


def test_required_is_met_by_the_confirmed_professional_named_on_their_document(codes):
    case = required(named_on_their_document())
    gaps = professional_gaps(case, codes)
    assert set(gaps) == {'professional_authentication'}
    check = gaps['professional_authentication']
    # The seal is on the attached document: the officer looks; the applicant is not asked and Accept stays open.
    assert check.severity == 'warning' and check.routed_to == 'officer'
    assert 'Synthetic test attachment' in check.message
    assert not [gap for gap in check_completeness(case, codes) if gap.severity == 'blocking']


@pytest.mark.parametrize('responsible', [None, 'Synthetic test author'])
def test_required_still_asks_when_no_document_names_the_professional(codes, responsible):
    case = complete_case()
    case.facts = [f for f in case.facts if not f.field.endswith('.responsible_party')]
    if responsible:
        case.facts.append(fact('evidence.synthetic.responsible_party', responsible))
    gaps = professional_gaps(required(case), codes)
    assert {field: gap.severity for field, gap in gaps.items()} == {
        'responsible_professional': 'blocking', 'professional_authentication': 'blocking'}


def test_a_determination_carries_over_unless_the_professional_answers_change():
    case = required(named_on_their_document())
    resolution = case.professional_resolutions[-1]
    # A resubmission that answers other questions keeps it, as does saving the same professional answer again.
    case.facts += [fact('building_area_m2', '120'), fact('journey.answer.understood%3A1', '{"value":"acknowledged"}'),
                   fact('permit_number', 'Not yet issued'), fact('evidence.synthetic.date', '2026-10-28'),
                   fact('professional.registration_number', 'A00000')]
    assert current_resolution(case) == resolution
    changed = case.model_copy(deep=True)
    changed.facts.append(fact('professional.registration_number', 'B11111'))
    assert current_resolution(changed) is None
    scope = case.model_copy(deep=True)
    scope.facts.append(fact('alternative_description', 'SYNTHETIC a different alternative.'))
    assert current_resolution(scope) is None
