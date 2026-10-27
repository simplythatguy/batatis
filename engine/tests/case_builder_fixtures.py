"""Synthetic administrative fixtures only; no actual testing, licence or opinion is asserted."""
from pathlib import Path

from engine.codes import Codes
from engine.models import Case, Fact, Jurisdiction, Source
from engine.section_c import section_c_rows
from engine.section_d import section_d_plan

ROOT = Path(__file__).resolve().parents[2]


def fact(field, value, **changes):
    data = dict(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='synthetic-applicant-fixture', quote=str(value)))
    data.update(changes)
    return Fact(**data)


def store_with_synthetic_files(store, case):
    """API fixtures need actual case-owned bytes, not file-presence metadata alone.

    The package carries each named attachment's readable bytes, so the store holds the
    referenced synthetic fixture file itself. No test result, professional authentication,
    parsed document or real evidence is asserted.
    """
    store.put(case)
    references = {}
    for entry in case.facts:
        if (entry.field.startswith('evidence.') and entry.field.endswith('.file_ref')
                and entry.status == 'confirmed' and entry.source.type == 'file'
                and entry.value == entry.source.ref):
            if entry.source.ref not in references:
                source = ROOT / entry.source.ref          # an absolute reference stays as it is
                data = (source.read_bytes() if source.is_file()
                        else b'SYNTHETIC storage-binding text, not a document or result.\n')
                saved = store.put_file(case.id, f'SYNTHETIC-storage-{source.name or "fixture.txt"}', data)
                references[entry.source.ref] = saved['id']
            entry.value = references[entry.source.ref]
            entry.source = entry.source.model_copy(update={'ref': entry.value})
    return store.put(case)


# These Yes/No answers are the authority's, so a clean administrative fixture can resolve.
_AUTHORITY_SCREEN = {
    'part4_design', 'preserved_wood_foundation_part4', 'roof_trusses',
    'prescriptive_route_confirmed', 'ahj_requires_professional', 'special_safety_concerns',
    'professional_judgement_required', 'professional_scope_resolved',
    'fire_suppression', 'fire_alarm',
}
_OFFICER = Source(type='officer', ref='synthetic-authority-fixture', quote='Authority recorded this screen answer.')


def complete_case(provisions=None):
    codes = Codes()
    provisions = provisions or ['9.10.9.16.(1)']
    values = dict(owner_name='Synthetic owner', application_date='2026-10-20',
        civic_address='123 Synthetic Street', legal_description='Synthetic lot 1 block 2 plan 3',
        representative='Synthetic applicant', mailing_address='123 Synthetic Street', scope='site',
        alternative_description='Synthetic test departure, no technical conclusion.',
        rationale='Synthetic applicant rationale.',
        risk_assessment=('Synthetic applicant risk assessment: the departure could let smoke pass between the '
                         'two suites if the separation is breached, delaying occupants leaving the building.'),
        testing_procedures='Synthetic applicant testing procedures: the named test author describes the test method.',
        mitigating_measures='Synthetic applicant measures.', assumptions_and_limits='Synthetic applicant limits.',
        maintenance_operation='Synthetic applicant operation and maintenance conditions.',
        qualifications='Synthetic named test author and their stated test qualifications.',
        occupancy='single_family', part4_design=False, preserved_wood_foundation_part4=False,
        roof_trusses=False, prescriptive_route_confirmed=False, ahj_requires_professional=False,
        special_safety_concerns=False, professional_judgement_required=True, professional_scope_resolved=True,
        fire_suppression=False, fire_alarm=False,
        **{'professional.role': 'R. Singh, P.Eng.', 'professional.registration_number': 'A00000'})
    case = Case(title='Synthetic administrative fixture', jurisdiction=Jurisdiction(id='alberta-other', name='Synthetic AHJ'),
        facts=[fact(k, v, source=_OFFICER) if k in _AUTHORITY_SCREEN else fact(k, v) for k, v in values.items()],
        provisions=provisions, section_c=section_c_rows(provisions, codes))
    file = Source(type='file', ref='engine/tests/fixtures/synthetic-evidence-fixture.txt', quote='Synthetic evidence metadata; no test was performed.')
    case.facts += [fact('evidence.synthetic.file_ref', file.ref, source=file),
                   fact('evidence.synthetic.responsible_party', 'Synthetic test author'),
                   fact('evidence.synthetic.date', '2026-10-20'), fact('evidence.synthetic.title', 'Synthetic test attachment')]
    case.facts += [fact(f'evidence.synthetic.covers.{item.id}', True) for item in section_d_plan(case, codes).items]
    return case
