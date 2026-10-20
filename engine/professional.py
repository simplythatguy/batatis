"""Conservative, deterministic professional-involvement screening, not a licence determination.

The general building exception and component duties are independent. All code citations are
looked up in the adopted second printing. Missing facts cannot produce an overall ``no``.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .codes import Codes
from .models import Case
from .process_fields import confirmed_value, latest_fact

Requirement = Literal['yes', 'no', 'depends']
Occupancy = Literal['single_family', 'multi_family', 'hotel', 'assembly', 'care', 'treatment',
                    'detention', 'business', 'mercantile', 'industrial', 'farm',
                    'relocatable_industrial_camp', 'mixed', 'other']
Count = Annotated[int, Field(strict=True, ge=1)]


class ProfessionalFacts(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    occupancy: Occupancy | None = None
    storeys: Count | None = None
    building_area_m2: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    principal_dwelling_units: Count | None = None  # Confirmed count, excluding qualifying secondary suites.
    farm_public_use: bool | None = None
    part4_design: bool | None = None
    preserved_wood_foundation_part4: bool | None = None
    roof_trusses: bool | None = None
    prescriptive_route_confirmed: bool | None = None
    ahj_requires_professional: bool | None = None
    special_safety_concerns: bool | None = None
    professional_judgement_required: bool | None = None
    professional_scope_resolved: bool | None = None  # Includes independent professional law/local requirements.
    fire_suppression: bool | None = None
    fire_alarm: bool | None = None

    @classmethod
    def from_case(cls, case: Case) -> ProfessionalFacts:
        data = {}
        for name in cls.model_fields:
            value = confirmed_value(case, f'professional.{name}', name)
            if value is not None:
                try:
                    cls.model_validate({name: value})
                except ValidationError:
                    continue  # Bad/ambiguous types are unknown; e.g. the string "false" is not False.
                data[name] = value
        return cls(**data)


# Applicant-confirmed role. A name or seal copied off a document does not count.
# Same rule as PR #26: engineer or architect, plus a seal or registration number.
_APPLICANT_SOURCES = frozenset({'user_text', 'user_click'})
_ROLE_FIELDS = (
    'professional.role', 'professional.discipline', 'registered_professional.role',
    'registered_professional.discipline', 'professional_name', 'responsible_professional', 'professional.name',
)
_SEAL_FIELDS = ('professional.seal', 'professional_seal', 'registered_professional.seal')
_REGISTRATION_FIELDS = (
    'professional.registration_number', 'professional.registration',
    'registered_professional.registration_number', 'apega_number', 'aaa_number',
)
_REJECT_ROLE = frozenset({
    'sales', 'rep', 'supplier', 'manufacturer', 'salesperson', 'vendor',
})


def _applicant_text(case: Case, *fields: str) -> str | None:
    fact = latest_fact(case, *fields)
    if fact is None or fact.status != 'confirmed' or fact.kind == 'proposed':
        return None
    if fact.source.type not in _APPLICANT_SOURCES:
        return None
    if not isinstance(fact.value, str) or not fact.value.strip():
        return None
    return fact.value.strip()


def role_confirmed(value: str) -> bool:
    """Case-insensitive. Punctuation is removed. Engineer and architect variants pass; commercial roles do not."""
    tokens = re.sub(r'[^a-z0-9]+', ' ', value.casefold()).split()
    if any(token in _REJECT_ROLE for token in tokens):
        return False
    if 'peng' in tokens or {'p', 'eng'} <= set(tokens):
        return True
    return 'engineer' in tokens or 'architect' in tokens


def professional_confirmed(case: Case) -> bool:
    """Engineer or architect, plus a seal or registration number, confirmed by the applicant."""
    role = _applicant_text(case, *_ROLE_FIELDS)
    if role is None or not role_confirmed(role):
        return False
    return _applicant_text(case, *_SEAL_FIELDS) is not None or _applicant_text(case, *_REGISTRATION_FIELDS) is not None


class ProfessionalReason(BaseModel):
    code: str
    required: Requirement
    message: str
    citation: str


class ProfessionalResult(BaseModel):
    required: Requirement
    general_required: Requirement
    reasons: list[ProfessionalReason]
    questions: list[str]
    scope_note: str = ('This screens documented professional duties. The responsible professional, regulator '
                       'and authority resolve scope, competence and local conditions.')


# Building area, never gross area summed across floors.
_AREA_LIMITS = {
    'assembly': (300, 150, 100), 'care': (300, 150, 100),
    'treatment': (300, 150, 100), 'detention': (300, 150, 100),
    'hotel': (400, 200, 130),
    'business': (500, 250, 165), 'mercantile': (500, 250, 165), 'industrial': (500, 250, 165),
}


def professional_involvement(facts: ProfessionalFacts | Case, codes: Codes) -> ProfessionalResult:
    if isinstance(facts, Case):
        facts = ProfessionalFacts.from_case(facts)
    reasons: list[ProfessionalReason] = []
    questions: list[str] = []

    def add(code: str, required: Requirement, message: str, pid: str,
            question: str | None = None, division: str = 'C'):
        rec = codes.provision(pid, division)
        if rec is None:
            raise KeyError(f'missing professional-involvement provision: {pid}')
        reasons.append(ProfessionalReason(code=code, required=required, message=message, citation=rec['citation']))
        if question:
            questions.append(question)

    occupancy = facts.occupancy
    general: Requirement = 'depends'
    if occupancy == 'single_family':
        general = 'no'
    elif occupancy == 'multi_family':
        if facts.principal_dwelling_units is not None:
            general = 'yes' if facts.principal_dwelling_units > 4 else 'no'
        else:
            questions.append('How many principal dwelling units are there, excluding confirmed qualifying secondary suites?')
    elif occupancy in _AREA_LIMITS:
        if facts.storeys is not None:
            if facts.storeys > 3:
                general = 'yes'
            elif facts.building_area_m2 is not None:
                general = 'no' if facts.building_area_m2 <= _AREA_LIMITS[occupancy][facts.storeys - 1] else 'yes'
        if general == 'depends':
            questions.append('What are the building height in storeys and building area in square metres (not total floor area)?')
    elif occupancy == 'farm':
        if facts.farm_public_use is False:
            general = 'no'
        else:
            questions.append('Is the farm building for public use, and what occupancy classification applies?')
    elif occupancy == 'relocatable_industrial_camp':
        general = 'no'
    else:
        questions.append('What is the confirmed occupancy/building type, including each use in a mixed-use building?')

    if general == 'yes':
        add('general_building', 'yes',
            'The stated building is outside the general exceptions; appropriate architecture/engineering professionals '
            'must authenticate the drawings and specifications.', '2.4.1.1.(3)')
    elif general == 'no':
        add('general_exception', 'no',
            'The stated building fits a general exception. Component, special-safety and professional-law duties still need checking.',
            '2.4.1.1.(1)')
    else:
        add('general_unresolved', 'depends',
            'The facts do not establish whether a general professional-involvement exception applies.', '2.4.1.1.(1)')
    if occupancy == 'multi_family':
        add('secondary_suites', 'no', 'Qualifying secondary suites need not count for this code exception; '
            'their status and independent professional-law treatment must be confirmed.', '2.4.1.1.(2)')

    if facts.ahj_requires_professional is True:
        add('ahj_direction', 'yes', 'The authority has required professional authentication/field reviews for the identified scope.',
            '2.4.1.1.(4)')
    elif facts.special_safety_concerns is not False or facts.ahj_requires_professional is None:
        add('special_safety', 'depends', 'Size, complexity or an unresolved authority direction may require professionals.',
            '2.4.1.1.(4)', 'Has the authority determined whether size or complexity requires professional involvement, and for which scope?')

    if facts.part4_design is True:
        add('part4', 'yes', 'Part 4 design requires a registered professional skilled in the work concerned.', '2.4.1.2.(1)')
    elif facts.part4_design is None:
        add('part4_unknown', 'depends', 'The structural design route is not confirmed.', '2.4.1.2.(1)',
            'Is any design carried out under Part 4, including beams, connections or foundations?')
    if facts.preserved_wood_foundation_part4 is True:
        add('preserved_wood_foundation', 'yes',
            'A Part 4 preserved wood foundation needs professional retention for installation field reviews before construction.',
            '2.4.1.2.(2)')
    elif facts.preserved_wood_foundation_part4 is None:
        add('foundation_unknown', 'depends', 'The foundation design and field-review trigger are unresolved.', '2.4.1.2.(2)',
            'Does the project include a preserved wood foundation designed under Part 4?')
    if facts.roof_trusses is True:
        add('truss_design', 'yes', 'Wood roof truss design and assembly connections need appropriate engineering responsibility.',
            '9.23.14.11.(2)', division='B')
        add('truss_part4', 'yes', 'The Part 4 connection-design route requires a skilled registered professional.', '2.4.1.2.(1)')
    elif facts.roof_trusses is None:
        add('trusses_unknown', 'depends', 'Roof-truss assembly design responsibility is not confirmed.', '2.4.1.2.(1)',
            'Are wood roof trusses or truss assembly connections included?')

    for field, code, pid, task in (
        ('fire_suppression', 'suppression', '2.4.1.3.(1)', 'testing'),
        ('fire_alarm', 'fire_alarm', '2.4.1.4.(1)', 'verification'),
    ):
        present = getattr(facts, field)
        if general == 'yes' and present is True:
            add(code, 'yes', f'The owner must document professional retention for system design, installation field reviews '
                f'and witnessing {task}, before construction.', pid)
        elif present is None or (present is True and general == 'depends'):
            add(code + '_unknown', 'depends', 'System presence or applicability of the general building requirement is unresolved.',
                pid, f'Is a {field.replace("_", " ")} system being installed, and does the general professional requirement apply?')

    if facts.prescriptive_route_confirmed is not True or facts.professional_judgement_required is not False:
        add('design_scope', 'depends', 'Non-prescriptive work or performance judgements need a competent professional-scope assessment.',
            '2.4.1.1.(3)', 'Which design route applies, and does any proposed analysis require reserved professional judgement?')
    if facts.professional_scope_resolved is not True:
        add('professional_law', 'depends', 'Independent professional-law and local scope requirements are not resolved.',
            '2.4.1.1.(5)', 'Have the applicable professional-law, discipline and local submission requirements been resolved?')

    required: Requirement = 'yes' if any(r.required == 'yes' for r in reasons) else (
        'depends' if any(r.required == 'depends' for r in reasons) else 'no')
    return ProfessionalResult(required=required, general_required=general, reasons=reasons,
                              questions=list(dict.fromkeys(questions)))
