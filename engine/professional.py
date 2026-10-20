"""Conservative, deterministic professional-involvement screening, not a licence determination.

The general building exception and component duties are independent. All code citations are
looked up in the adopted second printing. Missing facts cannot produce an overall ``no``.

``required`` stays ``yes``, ``no``, or ``depends`` for the screen. ``answer`` is the one
sentence a person reads. It names the condition, or ``unknown: needs <fact>``. It does not
repeat the token ``depends``.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, computed_field

from .codes import Codes
from .fact_text import fact_label
from .models import Case
from .process_fields import confirmed_value

Requirement = Literal['yes', 'no', 'depends']
_DEPENDS_WORD = re.compile(r'\bdepends\b', re.I)


def _condition(message: str) -> str:
    """Drop a bare or repeated ``depends`` token and keep the rest of the sentence."""
    text = _DEPENDS_WORD.sub('', message or '')
    text = re.sub(r'\s+', ' ', text).strip(' .;')
    return text


# Same option and help sentences as #26 (`PracticePrompt` / `_HELP` on
# backend/section-d-routing). A Not sure answer is not a yes or a no.
NOT_SURE_OPTION = 'Not sure (the officer decides)'
DEFAULT_HELP = (
    'State the fact if you know it. Yes and No are the two answers when the question is a yes or no. '
    'Not sure: the officer decides.'
)
# #26's Part 4 screening question. This branch asks that fact inside "Do we need an engineer?"
# The Yes and No meanings stay the #26 sentence.
PART4_QUESTION = 'Is any design carried out under Part 4, including beams, connections or foundations?'
PART4_HELP = 'Yes means the project includes Part 4 design. No means it does not. Not sure: the officer decides.'
_HELP = {
    PART4_QUESTION: PART4_HELP,
    'Do we need an engineer? The deciding fact is whether any design is carried out under Part 4.': PART4_HELP,
    'Has the authority determined whether size or complexity requires professional involvement, and for which scope?':
        'Yes means the authority has required a registered professional for a stated scope. '
        'No means it has not. Not sure: the officer decides.',
    'Does the project include a preserved wood foundation designed under Part 4?':
        'Yes means that foundation is in the project. No means it is not. Not sure: the officer decides.',
    'Are wood roof trusses or truss assembly connections included?':
        'Yes means wood roof trusses or those connections are included. No means they are not. '
        'Not sure: the officer decides.',
    'Is a fire suppression system being installed, and does the general professional requirement apply?':
        'Yes means that system is being installed on a building outside the general exceptions. '
        'No means it is not. Not sure: the officer decides.',
    'Is a fire alarm system being installed, and does the general professional requirement apply?':
        'Yes means that system is being installed on a building outside the general exceptions. '
        'No means it is not. Not sure: the officer decides.',
    'Which design route applies, and does any proposed analysis require reserved professional judgement?':
        'Yes means the design uses reserved professional judgement. No means it does not. '
        'Not sure: the officer decides.',
    'Have the applicable professional-law, discipline and local submission requirements been resolved?':
        'Yes means those requirements are resolved. No means they are not. Not sure: the officer decides.',
    'What gross area applies, and does a basement count in that area?':
        'State the gross area if you know it. Yes and No do not settle this. Not sure: the officer decides.',
    'Which part applies to this building, Part 3 or Part 9?':
        'Name Part 3 or Part 9. Not sure: the officer decides.',
    'Is a fire suppression or fire alarm system being installed, and does the general professional requirement apply?':
        'Yes means a fire suppression or fire alarm system is being installed on a building outside the general exceptions. '
        'No means it is not. Not sure: the officer decides.',
    'Does the fire separation stay intact at each penetration, including sprinkler piping?':
        'Yes means the fire separation stays intact at each penetration, including sprinkler piping. '
        'No means it does not. Not sure: the officer decides.',
}


class PracticePrompt(BaseModel):
    """One deciding question, with what Yes and No mean and a Not sure option."""

    model_config = ConfigDict(extra='forbid')
    text: str
    help: str
    not_sure: str = NOT_SURE_OPTION


def prompt_for(text: str) -> PracticePrompt:
    """Help matches #26 when the question is one of its screening questions."""
    return PracticePrompt(text=text, help=_HELP.get(text, DEFAULT_HELP), not_sure=NOT_SURE_OPTION)


def practice_answer(required: str, reasons, needs: list[str]) -> str:
    """One human sentence. The machine token stays on ``required``."""
    if required in ('yes', 'no'):
        for reason in reasons:
            if reason.required == required:
                text = _condition(reason.message)
                if text:
                    return text
        if required == 'yes':
            return 'A registered professional is indicated for the stated scope.'
        return 'The stated facts fit a general exception.'
    fields = list(dict.fromkeys(needs))
    if fields:
        return 'unknown: needs ' + ', '.join(fields)
    for reason in reasons:
        if reason.required == 'depends':
            text = _condition(reason.message)
            if text:
                return text
    return 'unknown: needs a deciding fact'


# The facts that decide the screen. The other Division C triggers stay on ``reasons``
# for the machine token. The sentence a person reads names these, not those citations.
_PRIMARY_FACTS = ('occupancy', 'part4_design')
_FACT_PHRASE = {
    'occupancy': 'the building type',
    'part4_design': 'whether any design is carried out under Part 4',
    'storeys': 'the number of storeys',
    'building_area_m2': 'the building area',
    'principal_dwelling_units': 'the number of principal dwelling units',
    'farm_public_use': 'whether the farm building is for public use',
    'span_m': 'the span',
    'preserved_wood_foundation_part4': 'whether there is a preserved wood foundation designed under Part 4',
    'roof_trusses': 'whether wood roof trusses are included',
    'ahj_requires_professional': 'whether the authority requires a professional',
    'special_safety_concerns': 'whether size or complexity requires a professional',
    'fire_suppression': 'whether a fire suppression system is being installed',
    'fire_alarm': 'whether a fire alarm system is being installed',
    'prescriptive_route_confirmed': 'which design route applies',
    'professional_judgement_required': 'whether the work needs reserved professional judgement',
    'professional_scope_resolved': 'whether professional-law scope is resolved',
}


def _field_name(field: str) -> str:
    return field.split('.')[-1]


def deciding_needs(facts: ProfessionalFacts, needs: list[str]) -> list[str]:
    """The missing facts that decide this screen. Not every Division C trigger."""
    def full(name: str) -> str:
        return name if '.' in name else f'professional.{name}'

    def take(chosen: list[str], name: str) -> None:
        item = full(name)
        if item in needs and item not in chosen:
            chosen.append(item)

    chosen: list[str] = []
    for name in _PRIMARY_FACTS:
        take(chosen, name)
    if facts.occupancy == 'multi_family':
        take(chosen, 'principal_dwelling_units')
    if facts.occupancy in _AREA_LIMITS:
        take(chosen, 'storeys')
        take(chosen, 'building_area_m2')
    if facts.occupancy == 'farm':
        take(chosen, 'farm_public_use')
    take(chosen, 'span_m')
    return chosen or list(needs)


def engineer_question(needs: list[str]) -> str:
    """One question. It names the deciding facts and does not cite Division C."""
    phrases = []
    for field in needs:
        name = _field_name(field)
        phrases.append(_FACT_PHRASE.get(name) or fact_label(field))
    if not phrases:
        return 'Do we need an engineer? A deciding fact is not on the case yet.'
    if len(phrases) == 1:
        return f'Do we need an engineer? The deciding fact is {phrases[0]}.'
    listed = ', '.join(phrases[:-1]) + f', and {phrases[-1]}'
    return f'Do we need an engineer? The deciding facts are {listed}.'


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
    needs: list[str] = []
    scope_note: str = ('This screens documented professional duties. The responsible professional, regulator '
                       'and authority resolve scope, competence and local conditions.')

    @computed_field
    @property
    def answer(self) -> str:
        """The sentence to show. Never ``depends. depends.``"""
        return practice_answer(self.required, self.reasons, self.needs)

    @computed_field
    @property
    def prompts(self) -> list[PracticePrompt]:
        """Help and a Not sure option for the engineer question and for a depends answer."""
        texts: list[str] = []
        for text in self.questions:
            if text and text not in texts:
                texts.append(text)
        if self.required == 'depends':
            sentence = self.answer
            if sentence and sentence not in texts:
                texts.append(sentence)
        return [prompt_for(text) for text in texts]


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
    needs: list[str] = []

    def need(*names: str) -> None:
        for name in names:
            field = name if '.' in name else f'professional.{name}'
            if field not in needs:
                needs.append(field)

    def add(code: str, required: Requirement, message: str, pid: str, division: str = 'C'):
        rec = codes.provision(pid, division)
        if rec is None:
            raise KeyError(f'missing professional-involvement provision: {pid}')
        reasons.append(ProfessionalReason(code=code, required=required, message=message, citation=rec['citation']))

    occupancy = facts.occupancy
    general: Requirement = 'depends'
    if occupancy == 'single_family':
        general = 'no'
    elif occupancy == 'multi_family':
        if facts.principal_dwelling_units is not None:
            general = 'yes' if facts.principal_dwelling_units > 4 else 'no'
    elif occupancy in _AREA_LIMITS:
        if facts.storeys is not None:
            if facts.storeys > 3:
                general = 'yes'
            elif facts.building_area_m2 is not None:
                general = 'no' if facts.building_area_m2 <= _AREA_LIMITS[occupancy][facts.storeys - 1] else 'yes'
    elif occupancy == 'farm':
        if facts.farm_public_use is False:
            general = 'no'
    elif occupancy == 'relocatable_industrial_camp':
        general = 'no'

    if general == 'yes':
        add('general_building', 'yes',
            'The stated building is outside the general exceptions; appropriate architecture/engineering professionals '
            'must authenticate the drawings and specifications.', '2.4.1.1.(3)')
    elif general == 'no':
        add('general_exception', 'no',
            'The stated building fits a general exception. Component, special-safety and professional-law duties still need checking.',
            '2.4.1.1.(1)')
    else:
        if occupancy == 'multi_family':
            need('principal_dwelling_units')
        elif occupancy in _AREA_LIMITS:
            if facts.storeys is None:
                need('storeys')
            if facts.building_area_m2 is None:
                need('building_area_m2')
        elif occupancy == 'farm':
            need('farm_public_use')
        else:
            need('occupancy')
        add('general_unresolved', 'depends',
            'The facts do not establish whether a general professional-involvement exception applies.', '2.4.1.1.(1)')
    if occupancy == 'multi_family':
        add('secondary_suites', 'no', 'Qualifying secondary suites need not count for this code exception; '
            'their status and independent professional-law treatment must be confirmed.', '2.4.1.1.(2)')

    if facts.ahj_requires_professional is True:
        add('ahj_direction', 'yes', 'The authority has required professional authentication/field reviews for the identified scope.',
            '2.4.1.1.(4)')
    elif facts.special_safety_concerns is not False or facts.ahj_requires_professional is None:
        if facts.ahj_requires_professional is None:
            need('ahj_requires_professional')
        if facts.special_safety_concerns is None:
            need('special_safety_concerns')
        add('special_safety', 'depends', 'Size, complexity or an unresolved authority direction may require professionals.',
            '2.4.1.1.(4)')

    if facts.part4_design is True:
        add('part4', 'yes', 'Part 4 design requires a registered professional skilled in the work concerned.', '2.4.1.2.(1)')
    elif facts.part4_design is None:
        need('part4_design')
        add('part4_unknown', 'depends', 'The structural design route is not confirmed.', '2.4.1.2.(1)')
    if facts.preserved_wood_foundation_part4 is True:
        add('preserved_wood_foundation', 'yes',
            'A Part 4 preserved wood foundation needs professional retention for installation field reviews before construction.',
            '2.4.1.2.(2)')
    elif facts.preserved_wood_foundation_part4 is None:
        need('preserved_wood_foundation_part4')
        add('foundation_unknown', 'depends', 'The foundation design and field-review trigger are unresolved.', '2.4.1.2.(2)')
    if facts.roof_trusses is True:
        add('truss_design', 'yes', 'Wood roof truss design and assembly connections need appropriate engineering responsibility.',
            '9.23.14.11.(2)', division='B')
        add('truss_part4', 'yes', 'The Part 4 connection-design route requires a skilled registered professional.', '2.4.1.2.(1)')
    elif facts.roof_trusses is None:
        need('roof_trusses')
        add('trusses_unknown', 'depends', 'Roof-truss assembly design responsibility is not confirmed.', '2.4.1.2.(1)')

    for field, code, pid, task in (
        ('fire_suppression', 'suppression', '2.4.1.3.(1)', 'testing'),
        ('fire_alarm', 'fire_alarm', '2.4.1.4.(1)', 'verification'),
    ):
        present = getattr(facts, field)
        if general == 'yes' and present is True:
            add(code, 'yes', f'The owner must document professional retention for system design, installation field reviews '
                f'and witnessing {task}, before construction.', pid)
        elif present is None or (present is True and general == 'depends'):
            if present is None:
                need(field)
            add(code + '_unknown', 'depends', 'System presence or applicability of the general building requirement is unresolved.',
                pid)

    if facts.prescriptive_route_confirmed is not True or facts.professional_judgement_required is not False:
        if facts.prescriptive_route_confirmed is None:
            need('prescriptive_route_confirmed')
        if facts.professional_judgement_required is None:
            need('professional_judgement_required')
        add('design_scope', 'depends', 'Non-prescriptive work or performance judgements need a competent professional-scope assessment.',
            '2.4.1.1.(3)')
    if facts.professional_scope_resolved is not True:
        need('professional_scope_resolved')
        add('professional_law', 'depends', 'Independent professional-law and local scope requirements are not resolved.',
            '2.4.1.1.(5)')

    required: Requirement = 'yes' if any(r.required == 'yes' for r in reasons) else (
        'depends' if any(r.required == 'depends' for r in reasons) else 'no')
    shown = deciding_needs(facts, needs) if required == 'depends' else []
    asked = [engineer_question(shown)] if required == 'depends' else []
    return ProfessionalResult(required=required, general_required=general, reasons=reasons,
                              questions=asked, needs=shown if required == 'depends' else needs)
