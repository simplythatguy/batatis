"""Synthetic administrative fixtures only; no actual testing, licence or opinion is asserted."""
from engine.codes import Codes
from engine.models import Case, Fact, Jurisdiction, Source
from engine.section_c import section_c_rows
from engine.section_d import section_d_plan


def fact(field, value, **changes):
    data = dict(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='synthetic-applicant-fixture', quote=str(value)))
    data.update(changes)
    return Fact(**data)


def complete_case(provisions=None):
    codes = Codes()
    provisions = provisions or ['9.10.9.16.(1)']
    values = dict(owner_name='Synthetic owner', application_date='2026-10-20',
        civic_address='123 Synthetic Street', legal_description='Synthetic lot 1 block 2 plan 3',
        representative='Synthetic applicant', mailing_address='123 Synthetic Street', scope='site',
        alternative_description='Synthetic test departure, no technical conclusion.',
        rationale='Synthetic applicant rationale.', risk_assessment='Synthetic applicant risk assessment.',
        mitigating_measures='Synthetic applicant measures.', assumptions_and_limits='Synthetic applicant limits.',
        maintenance_operation='Synthetic applicant operation and maintenance conditions.',
        analysis_detail='Synthetic applicant detail conveying design intent for the Code analysis.',
        qualifications='Synthetic named test author and their stated test qualifications.',
        design_coordinator='One person is responsible for this synthetic design.',
        occupancy='single_family', part4_design=False, preserved_wood_foundation_part4=False,
        roof_trusses=False, prescriptive_route_confirmed=True, ahj_requires_professional=False,
        special_safety_concerns=False, professional_judgement_required=False, professional_scope_resolved=True,
        fire_suppression=False, fire_alarm=False,
        division_c_2_3_1='The Division C Section 2.3.1 documentation for this alternative solution is included with this application.')
    # IB-2026-10-16: the authority having jurisdiction is the organisation, not an officer.
    case = Case(title='Synthetic administrative fixture',
                jurisdiction=Jurisdiction(id='alberta-other', name='Synthetic accredited organisation',
                                          authority='Synthetic accredited organisation'),
        facts=[fact(k, v) for k, v in values.items()], provisions=provisions, section_c=section_c_rows(provisions, codes))
    file = Source(type='file', ref='synthetic-evidence-fixture.txt', quote='Synthetic evidence metadata; no test was performed.')
    case.facts += [fact('evidence.synthetic.file_ref', file.ref, source=file),
                   fact('evidence.synthetic.responsible_party', 'Synthetic test author'),
                   fact('evidence.synthetic.date', '2026-10-20'), fact('evidence.synthetic.title', 'Synthetic test attachment')]
    case.facts += [fact(f'evidence.synthetic.covers.{item.id}', True) for item in section_d_plan(case, codes).items]
    return case
