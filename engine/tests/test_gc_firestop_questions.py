"""A general contractor does not answer the performance benchmark for 3.1.9.4.(4)."""
import pytest

from codedb.tests.mini_db import build
from engine.codes import Codes
from engine.completeness import check_completeness
from engine.models import Case, Jurisdiction
from engine.professional import ProfessionalResult
from engine.section_c import section_c_rows
from engine.section_d_issues import (
    HANDOFF_LABEL, NOT_MY_ROLE, PracticeOfEngineering, section_d_issues,
)
from engine.tests.case_builder_fixtures import fact

DEPARTURE = '3.1.9.1.(1)'
BENCHMARK = '3.1.9.4.(4)'
CITING = '3.1.9.4.(3)'


@pytest.fixture
def codes(tmp_path):
    path = tmp_path / 'mini.sqlite'
    build(path)
    return Codes(path)


def _screen(*_args, **_kwargs):
    return PracticeOfEngineering(
        value=False, rule='2.4.1.1.(1)', division='C', citation='synthetic Div C 2.4.1.1.(1)',
        reason='Synthetic screen for the fixture.')


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr('engine.section_d_issues.practice_of_engineering', _screen)
    monkeypatch.setattr('engine.section_d_issues.process_fields', lambda case, codes: [])
    monkeypatch.setattr('engine.completeness.validate_text', lambda *args, **kwargs: {'errors': []})
    monkeypatch.setattr('engine.completeness.process_fields', lambda case, codes: [])
    monkeypatch.setattr(
        'engine.completeness.professional_involvement',
        lambda case, codes: ProfessionalResult(required='no', general_required='no', reasons=[], questions=[]))


def _case(codes, *extra):
    provisions = [DEPARTURE, BENCHMARK, CITING]
    return Case(
        provisions=provisions,
        section_c=section_c_rows(provisions, codes),
        jurisdiction=Jurisdiction(id='alberta-other', name='Synthetic AHJ'),
        facts=[fact(name, 'synthetic') for name in (
            'owner_name', 'application_date', 'civic_address', 'legal_description',
            'representative', 'mailing_address', 'alternative_description', 'scope')] + [
            fact('applicant_role', 'contractor'),
            fact('provision_role', f'departure:{DEPARTURE}'),
            fact('provision_role', f'departure:{BENCHMARK}'),
            fact('provision_role', f'citing:{CITING}'),
            *extra])


def _for(issues, provision_id):
    return [issue for issue in issues if issue.provision and issue.provision.provision_id == provision_id]


def test_gc_firestop_routes_the_benchmark_and_not_my_role_stays_open(codes, quiet):
    case = _case(codes)
    issues = section_d_issues(case, codes)
    [benchmark] = _for(issues, BENCHMARK)
    assert benchmark.question == f'performance benchmark for {BENCHMARK}'
    assert benchmark.question_kind == 'benchmark'
    assert benchmark.asked_of == 'professional'
    assert benchmark.handoff == HANDOFF_LABEL
    assert benchmark.answers == (NOT_MY_ROLE,)
    assert benchmark.answer is None
    assert benchmark.status == 'open'
    performance = _for(issues, DEPARTURE)
    assert len(performance) == 4
    assert {issue.asked_of for issue in performance} == {'professional'}
    assert {issue.question for issue in performance} == {f'objective performance for {DEPARTURE}'}
    assert {issue.handoff for issue in performance} == {HANDOFF_LABEL}
    [citing] = _for(issues, CITING)
    assert citing.asked_of == 'officer'
    assert citing.question_kind == 'objective_performance'
    assert citing.handoff == HANDOFF_LABEL

    before = check_completeness(case, codes)
    blocking = [gap for gap in before if gap.severity == 'blocking']
    assert blocking
    assert all('performance benchmark' not in gap.message for gap in blocking)
    assert all(gap.provision_id != BENCHMARK for gap in blocking)

    case.facts.append(fact(f'question.{BENCHMARK}', NOT_MY_ROLE))
    [answered] = _for(section_d_issues(case, codes), BENCHMARK)
    assert answered.answer == NOT_MY_ROLE
    assert answered.status == 'open'
    after = check_completeness(case, codes)
    opened = [gap for gap in after if gap.field == f'question.{BENCHMARK}']
    assert len(opened) == 1
    assert opened[0].severity == 'warning'
    assert opened[0].message == HANDOFF_LABEL
    assert [gap.id for gap in after if gap.severity == 'blocking'] == [gap.id for gap in blocking]


def test_owner_is_handed_off_and_a_manufacturer_keeps_the_question(codes, quiet):
    owner = _case(codes)
    owner.facts = [fact for fact in owner.facts if fact.field != 'applicant_role']
    owner.facts.append(fact('applicant_role', 'owner'))
    [benchmark] = _for(section_d_issues(owner, codes), BENCHMARK)
    assert benchmark.asked_of == 'professional' and benchmark.handoff == HANDOFF_LABEL

    maker = _case(codes)
    maker.facts = [fact for fact in maker.facts if fact.field != 'applicant_role']
    maker.facts.append(fact('applicant_role', 'manufacturer'))
    [kept] = _for(section_d_issues(maker, codes), BENCHMARK)
    assert kept.asked_of == 'applicant' and kept.handoff is None and kept.answers == ()
    assert kept.question.startswith('The attribution table has no objective or function')
    assert _for(section_d_issues(maker, codes), DEPARTURE)[0].question is None
