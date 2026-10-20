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
from .process_fields import alternative_path, confirmed_value, latest_fact

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
    # Acts measure gross area per floor and a total unit count that does not drop suites.
    # The code screen still uses building area and principal_dwelling_units.
    gross_area_per_floor_m2: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    total_unit_count: Count | None = None
    # Explicit negative. "No engineer" is not an unresolved design route.
    engineer_engaged: bool | None = None
    # Medium confidence. True asks; it does not answer no.
    gross_area_unsettled: bool | None = None
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


Involvement = Literal['professional_involved', 'not_required', 'unresolved']
RouteTarget = Literal['officer', 'professional', 'applicant']

# Applicant-confirmed role. A name or seal copied off a document does not count.
_APPLICANT_SOURCES = frozenset({'user_text', 'user_click'})
# A confirmed status does not move a user_text or user_click fact into this set.
_AUTHORITY_SOURCES = frozenset({'officer', 'professional', 'code'})
_RESERVED_FIELDS = frozenset({
    'ahj_requires_professional', 'special_safety_concerns',
    'professional_scope_resolved', 'professional_judgement_required',
})
_YES_NO_FIELDS = (
    'farm_public_use', 'engineer_engaged', 'gross_area_unsettled',
    'part4_design', 'preserved_wood_foundation_part4', 'roof_trusses',
    'prescriptive_route_confirmed', 'ahj_requires_professional', 'special_safety_concerns',
    'professional_judgement_required', 'professional_scope_resolved',
    'fire_suppression', 'fire_alarm',
)
_NOT_SURE_VALUES = frozenset({
    'not sure', 'not_sure', 'not sure (the officer decides)',
})
NOT_SURE_OPTION = 'Not sure (the officer decides)'
OFFICER_PROFESSIONAL_GAP = 'Routed to the officer: whether a registered professional is required'
PRESCRIPTIVE_CONTRADICTION = (
    'An answer of yes for the prescriptive route contradicts this variance request. That answer clears nothing.'
)
_OFFICER_REASONS = frozenset({'special_safety', 'professional_law', 'design_scope'})
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
_DEPENDS_FIELDS = {
    'special_safety': ('ahj_requires_professional', 'special_safety_concerns'),
    'part4_unknown': ('part4_design',),
    'foundation_unknown': ('preserved_wood_foundation_part4',),
    'trusses_unknown': ('roof_trusses',),
    'suppression_unknown': ('fire_suppression',),
    'fire_alarm_unknown': ('fire_alarm',),
    'systems_unknown': ('fire_suppression', 'fire_alarm'),
    'firestop_scope': ('fire_suppression',),
    'professional_law': ('professional_scope_resolved',),
}

_DECIDER = {
    'officer': 'The officer decides.',
    'applicant': 'The applicant decides.',
    'professional': 'A registered professional decides.',
}
_FIRE_QUESTION = (
    'Does the fire separation stay intact at each penetration, including sprinkler piping?')
_FIRE_MESSAGE = (
    'Whether the fire separation, each penetration and the sprinkler piping are covered is unresolved.')
_SYSTEM_MESSAGE = (
    'System presence or applicability of the general building requirement is unresolved.')
_SYSTEM_QUESTION = (
    'Is a fire suppression or fire alarm system being installed, and does the general professional requirement apply?')
_PART_QUESTION = 'Which part applies to this building, Part 3 or Part 9?'
_PART_MESSAGE = 'Whether Part 3 or Part 9 applies is unresolved.'
# Div A 1.3.3.3 keeps Part 9 to three storeys and 600 m2. Assembly and institutional occupancies are outside it.
_PART3_OCCUPANCY = frozenset({'assembly', 'care', 'treatment', 'detention'})
_PART9_OCCUPANCY = frozenset({
    'single_family', 'multi_family', 'farm', 'hotel', 'business', 'mercantile',
    'industrial', 'relocatable_industrial_camp',
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


def commercial_party(*parts: str) -> bool:
    """Sales, vendor, and manufacturer wording. An unsigned note from one of these is not a professional."""
    tokens = re.sub(r'[^a-z0-9]+', ' ', ' '.join(parts).casefold()).split()
    return any(token in _REJECT_ROLE for token in tokens)


def role_confirmed(value: str) -> bool:
    """Case-insensitive. Punctuation is removed. Engineer and architect variants pass; commercial roles do not."""
    tokens = re.sub(r'[^a-z0-9]+', ' ', value.casefold()).split()
    if commercial_party(value):
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


class PracticePrompt(BaseModel):
    """One deciding question, with what Yes and No mean and a Not sure option."""

    model_config = ConfigDict(extra='forbid')
    text: str
    help: str
    not_sure: str = NOT_SURE_OPTION


_HELP = {
    'Has the authority determined whether size or complexity requires professional involvement, and for which scope?':
        'Yes means the authority has required a registered professional for a stated scope. '
        'No means it has not. Not sure: the officer decides.',
    'Is any design carried out under Part 4, including beams, connections or foundations?':
        'Yes means the project includes Part 4 design. No means it does not. Not sure: the officer decides.',
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
}


def _prompt_for(text: str) -> PracticePrompt:
    return PracticePrompt(
        text=text,
        help=_HELP.get(text, 'State the fact if you know it. Yes and No are the two answers when the question is a yes or no. Not sure: the officer decides.'),
    )


def _not_sure_value(value: object) -> bool:
    return isinstance(value, str) and ' '.join(value.split()).casefold() in _NOT_SURE_VALUES


def _apply_case_sources(case: Case, facts: ProfessionalFacts):
    """Applicant Yes/No answers, including a confirmed user fact, cannot clear the screen."""
    contradiction = None
    if alternative_path(case) and facts.prescriptive_route_confirmed is True:
        facts = facts.model_copy(update={'prescriptive_route_confirmed': False})
        contradiction = PRESCRIPTIVE_CONTRADICTION
    applicant: list[str] = []
    not_sure: list[str] = []
    withheld: dict[str, None] = {}
    for name in _YES_NO_FIELDS:
        fact = latest_fact(case, f'professional.{name}', name)
        if fact is None or fact.status != 'confirmed' or fact.kind == 'proposed':
            continue
        if _not_sure_value(fact.value):
            not_sure.append(name)
            withheld[name] = None
            continue
        if fact.source.type not in _AUTHORITY_SOURCES:
            applicant.append(name)
            if name in _RESERVED_FIELDS:
                withheld[name] = None
    if withheld:
        facts = facts.model_copy(update=withheld)
    return facts, tuple(applicant), tuple(not_sure), contradiction


class ProfessionalResult(BaseModel):
    required: Requirement
    general_required: Requirement
    # Sentences for an unresolved screen. Empty when that token is not unresolved.
    # Show these. The tokens above stay for the machine.
    decision: str = ''
    general_decision: str = ''
    reasons: list[ProfessionalReason]
    questions: list[str]
    prompts: list[PracticePrompt] = []
    involvement: Involvement = 'unresolved'
    missing_facts: tuple[str, ...] = ()
    routed_to: RouteTarget | None = None
    applicant_sourced: bool = False
    not_sure_fields: tuple[str, ...] = ()
    prescriptive_contradiction: str | None = None
    scope_note: str = ('This screens documented professional duties. The responsible professional, regulator '
                       'and authority resolve scope, competence and local conditions.')


# Building area, never gross area summed across floors.
_AREA_LIMITS = {
    'assembly': (300, 150, 100), 'care': (300, 150, 100),
    'treatment': (300, 150, 100), 'detention': (300, 150, 100),
    'hotel': (400, 200, 130),
    'business': (500, 250, 165), 'mercantile': (500, 250, 165), 'industrial': (500, 250, 165),
}


def _listed(provisions: tuple[str, ...], prefix: str) -> bool:
    return any(provision.startswith(prefix) for provision in provisions)


def unresolved_item(what: str, routed_to: str | None) -> str:
    """User-facing line for an open screen. Names the deciding fact and who decides it."""
    body = ' '.join(what.split()).strip().rstrip('.')
    if not body or body.casefold() in {'depends', 'depend'}:
        body = 'Whether a registered professional is required'
    who = _DECIDER.get(routed_to or '', _DECIDER['officer'])
    if who.casefold() in body.casefold():
        return body if body.endswith('.') else f'{body}.'
    return f'{body}. {who}'


def _provision_part(provision: str) -> str | None:
    head = provision.split('.', 1)[0]
    if head in {'3', '9'}:
        return head
    return None


def _building_part(facts: ProfessionalFacts, provisions: tuple[str, ...]) -> str:
    """Part 3, Part 9, or unknown, from storeys, area, occupancy, and cited prefixes."""
    cited = {part for part in (_provision_part(provision) for provision in provisions) if part}
    if ((facts.storeys is not None and facts.storeys > 3)
            or (facts.building_area_m2 is not None and facts.building_area_m2 > 600)
            or facts.occupancy in _PART3_OCCUPANCY
            or '3' in cited):
        return '3'
    if (facts.occupancy in _PART9_OCCUPANCY
            and (facts.storeys is None or facts.storeys <= 3)
            and (facts.building_area_m2 is None or facts.building_area_m2 <= 600)):
        return '9'
    if cited == {'9'}:
        return '9'
    return 'unknown'


def _screen_scope(case: Case | None, provisions: tuple[str, ...]) -> str:
    """Fire-separation work asks about the penetration. Structural provisions keep their own questions."""
    if case is None:
        return 'any'
    parts = [case.title or '']
    for field in ('topic', 'description', 'alternative_description', 'alternative'):
        value = confirmed_value(case, field)
        if isinstance(value, str):
            parts.append(value)
    text = ' '.join(parts).casefold()
    fire = any(provision.startswith(('3.1.8', '3.1.9')) for provision in provisions) or any(
        phrase in text for phrase in ('firestop', 'fire separation', 'fire-separation', 'penetration'))
    structural = any(provision.startswith(('9.15', '9.23', '9.4', '4.')) for provision in provisions)
    if fire and not structural:
        return 'fire'
    return 'any'


def _missing_facts(facts: ProfessionalFacts, reasons: list[ProfessionalReason], *, confirmed: bool) -> tuple[str, ...]:
    """Fact names still needed. An alternative case is not asked to set the prescriptive route to yes."""
    names: list[str] = []
    for reason in reasons:
        if reason.required != 'depends':
            continue
        if reason.code == 'design_scope':
            if facts.professional_judgement_required is not True:
                names.append('professional_judgement_required')
            if not confirmed:
                names.append('professional.role')
                names.append('professional.registration_number or professional.seal')
            continue
        if reason.code == 'general_unresolved':
            if facts.occupancy is None:
                names.append('occupancy')
            elif facts.occupancy == 'multi_family' and facts.principal_dwelling_units is None:
                names.append('principal_dwelling_units')
            elif facts.occupancy in _AREA_LIMITS:
                if facts.storeys is None:
                    names.append('storeys')
                if facts.building_area_m2 is None:
                    names.append('building_area_m2')
            elif facts.occupancy == 'farm' and facts.farm_public_use is None:
                names.append('farm_public_use')
            else:
                names.append('occupancy')
            continue
        for name in _DEPENDS_FIELDS.get(reason.code, ()):
            if getattr(facts, name) is None:
                names.append(name)
    return tuple(dict.fromkeys(names))


def professional_involvement(facts: ProfessionalFacts | Case, codes: Codes, *,
                             provisions: tuple[str, ...] = (), span_handoff: bool = False) -> ProfessionalResult:
    case = facts if isinstance(facts, Case) else None
    applicant: tuple[str, ...] = ()
    not_sure: tuple[str, ...] = ()
    contradiction = None
    if isinstance(facts, Case):
        provisions = tuple(facts.provisions)
        loaded = ProfessionalFacts.from_case(facts)
        loaded, applicant, not_sure, contradiction = _apply_case_sources(facts, loaded)
        facts = loaded
    if span_handoff and facts.part4_design is not True:
        facts = facts.model_copy(update={'part4_design': True})
    scope = _screen_scope(case, provisions)
    # Facts-only calls keep the existing questions so the flag eval does not move.
    part = _building_part(facts, provisions) if case is not None else '9'
    ask_part9 = part == '9'
    reasons: list[ProfessionalReason] = []
    questions: list[str] = []
    asked: dict[str, str] = {}

    def add(code: str, required: Requirement, message: str, pid: str,
            question: str | None = None, division: str = 'C'):
        rec = codes.provision(pid, division)
        if rec is None:
            raise KeyError(f'missing professional-involvement provision: {pid}')
        reasons.append(ProfessionalReason(code=code, required=required, message=message, citation=rec['citation']))
        if question:
            questions.append(question)
            asked[code] = question

    occupancy = facts.occupancy
    general: Requirement = 'depends'
    general_question = None
    if occupancy == 'single_family':
        general = 'no'
    elif occupancy == 'multi_family':
        if facts.principal_dwelling_units is not None:
            general = 'yes' if facts.principal_dwelling_units > 4 else 'no'
        else:
            general_question = 'How many principal dwelling units are there, excluding confirmed qualifying secondary suites?'
            questions.append(general_question)
    elif occupancy in _AREA_LIMITS:
        if facts.storeys is not None:
            if facts.storeys > 3:
                general = 'yes'
            elif facts.building_area_m2 is not None:
                general = 'no' if facts.building_area_m2 <= _AREA_LIMITS[occupancy][facts.storeys - 1] else 'yes'
        if general == 'depends':
            general_question = 'What are the building height in storeys and building area in square metres (not total floor area)?'
            questions.append(general_question)
    elif occupancy == 'farm':
        if facts.farm_public_use is False:
            general = 'no'
        elif ask_part9 and scope != 'fire':
            general_question = 'Is the farm building for public use, and what occupancy classification applies?'
            questions.append(general_question)
    elif occupancy == 'relocatable_industrial_camp':
        general = 'no'
    else:
        general_question = 'What is the confirmed occupancy/building type, including each use in a mixed-use building?'
        questions.append(general_question)

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
            'The facts do not establish whether a general professional-involvement exception applies.', '2.4.1.1.(1)',
            general_question)
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
    elif facts.part4_design is None and scope != 'fire':
        add('part4_unknown', 'depends', 'The structural design route is not confirmed.', '2.4.1.2.(1)',
            'Is any design carried out under Part 4, including beams, connections or foundations?')
    # Unanswered component questions are in scope only. A preserved-wood foundation
    # question is Part 9 work or a 9.15.2 provision. A truss question is Part 9 work
    # or a 9.23.14 provision. Part 3, including a 5-storey building or a Part 3
    # citation, does not ask those. An unknown part asks which part applies instead.
    # Absence alone does not make the screen depend.
    if facts.preserved_wood_foundation_part4 is True:
        add('preserved_wood_foundation', 'yes',
            'A Part 4 preserved wood foundation needs professional retention for installation field reviews before construction.',
            '2.4.1.2.(2)')
    elif ask_part9 and scope != 'fire' and facts.preserved_wood_foundation_part4 is None and (
            facts.part4_design is True or _listed(provisions, '9.15.2')):
        add('foundation_unknown', 'depends', 'The foundation design and field-review trigger are unresolved.', '2.4.1.2.(2)',
            'Does the project include a preserved wood foundation designed under Part 4?')
    if facts.roof_trusses is True:
        add('truss_design', 'yes', 'Wood roof truss design and assembly connections need appropriate engineering responsibility.',
            '9.23.14.11.(2)', division='B')
        add('truss_part4', 'yes', 'The Part 4 connection-design route requires a skilled registered professional.', '2.4.1.2.(1)')
    elif ask_part9 and scope != 'fire' and facts.roof_trusses is None and (
            facts.part4_design is True or _listed(provisions, '9.23.14')):
        add('trusses_unknown', 'depends', 'Roof-truss assembly design responsibility is not confirmed.', '2.4.1.2.(1)',
            'Are wood roof trusses or truss assembly connections included?')

    pending_systems: list[tuple[str, str, str]] = []
    for field, code, pid, task in (
        ('fire_suppression', 'suppression', '2.4.1.3.(1)', 'testing'),
        ('fire_alarm', 'fire_alarm', '2.4.1.4.(1)', 'verification'),
    ):
        present = getattr(facts, field)
        if general == 'yes' and present is True:
            add(code, 'yes', f'The owner must document professional retention for system design, installation field reviews '
                f'and witnessing {task}, before construction.', pid)
        elif scope != 'fire' and general != 'no' and (present is None or (present is True and general == 'depends')):
            # Div C 2.4.1.3 and 2.4.1.4 apply to a 2.4.1.1.(3) building. A resolved
            # general exception is out of scope, so an unanswered system does not ask.
            pending_systems.append((field, code, pid))
    if len(pending_systems) >= 2:
        for _field, _code, pid in pending_systems:
            if codes.provision(pid, 'C') is None:
                raise KeyError(f'missing professional-involvement provision: {pid}')
        add('systems_unknown', 'depends', _SYSTEM_MESSAGE, pending_systems[0][2], _SYSTEM_QUESTION)
    elif len(pending_systems) == 1:
        field, code, pid = pending_systems[0]
        add(code + '_unknown', 'depends', _SYSTEM_MESSAGE, pid,
            f'Is a {field.replace("_", " ")} system being installed, and does the general professional requirement apply?')
    if scope == 'fire':
        add('firestop_scope', 'depends', _FIRE_MESSAGE, '2.4.1.3.(1)', _FIRE_QUESTION)
    if case is not None and part == 'unknown' and _PART_QUESTION not in questions:
        record = codes.provision('1.3.3.3.(1)', 'A')
        if record is None:
            questions.append(_PART_QUESTION)
        else:
            add('part_scope', 'depends', _PART_MESSAGE, '1.3.3.3.(1)', _PART_QUESTION, division='A')

    # The Acts count suites. Div C 2.4.1.1.(2) does not. Above 4 is a yes even when the code exception is no.
    # The cite is the codedb authentication sentence. The Act pinpoint is source-pdf and is not a routing cite.
    if facts.total_unit_count is not None and facts.total_unit_count > 4 and (
            facts.principal_dwelling_units is None or facts.principal_dwelling_units <= 4):
        add('acts_units', 'yes',
            'Dwelling units counted with suites are above 4. Div C 2.4.1.1.(5) is the authentication '
            'sentence that follows the professional Acts.',
            '2.4.1.1.(5)')
    if facts.gross_area_unsettled is True:
        add('gross_area_acts', 'depends',
            'Gross area can be read more than one way. This screen does not answer no from building area alone.',
            '2.4.1.1.(5)',
            'What gross area applies, and does a basement count in that area?')

    if facts.prescriptive_route_confirmed is not True or facts.professional_judgement_required is not False:
        add('design_scope', 'depends', 'Non-prescriptive work or performance judgements need a competent professional-scope assessment.',
            '2.4.1.1.(3)', 'Which design route applies, and does any proposed analysis require reserved professional judgement?')
    if facts.professional_scope_resolved is not True:
        add('professional_law', 'depends', 'Independent professional-law and local scope requirements are not resolved.',
            '2.4.1.1.(5)', 'Have the applicable professional-law, discipline and local submission requirements been resolved?')

    required: Requirement = 'yes' if any(r.required == 'yes' for r in reasons) else (
        'depends' if any(r.required == 'depends' for r in reasons) else 'no')
    # Facts-only calls have no applicant source, so the eval can still answer no.
    blocked = bool(applicant or not_sure)
    if blocked and required == 'no':
        required = 'depends'
    confirmed = professional_confirmed(case) if case is not None else False
    alternative = case is not None and alternative_path(case)
    other_depends = [reason for reason in reasons if reason.required == 'depends' and reason.code != 'design_scope']
    if (not blocked and alternative and facts.professional_judgement_required is True
            and confirmed and not other_depends):
        involvement: Involvement = 'professional_involved'
        missing: tuple[str, ...] = ()
    elif required == 'no' and not alternative:
        involvement = 'not_required'
        missing = ()
    else:
        # An alternative case does not become not_required by answering the prescriptive route as yes.
        involvement = 'unresolved'
        missing = _missing_facts(facts, reasons, confirmed=confirmed)
    if blocked and required != 'yes':
        routed: RouteTarget | None = 'officer'
    elif any(reason.required == 'depends' and reason.code in _OFFICER_REASONS for reason in reasons):
        routed = 'officer'
    elif required == 'yes':
        routed = 'professional'
    elif required == 'depends':
        routed = 'applicant'
    else:
        routed = None
    if not ask_part9:
        part9_items = ('preserved wood', 'roof truss', 'farm building')
        questions = [text for text in questions if not any(phrase in text.casefold() for phrase in part9_items)]
    if scope == 'fire':
        questions = [text for text in questions if 'beams, connections or foundations' not in text.casefold()]
    unique_questions = list(dict.fromkeys(questions))
    for reason in reasons:
        if reason.required != 'depends':
            continue
        detail = reason.message
        question = asked.get(reason.code)
        if question and question not in detail:
            detail = f'{detail.rstrip(".")}. {question}'
        reason.message = unresolved_item(detail, routed)
    decision = unresolved_item(
        unique_questions[0] if unique_questions else 'Whether a registered professional is required', routed,
    ) if required == 'depends' else ''
    general_decision = unresolved_item(
        'Whether a general professional-involvement exception applies', routed,
    ) if general == 'depends' else ''
    prompts = []
    decider = _DECIDER.get(routed or '', '')
    for text in unique_questions:
        prompt = _prompt_for(text)
        if decider and decider.casefold() not in prompt.help.casefold():
            prompt = prompt.model_copy(update={'help': f'{prompt.help} {decider}'})
        prompts.append(prompt)
    return ProfessionalResult(required=required, general_required=general, decision=decision,
                              general_decision=general_decision, reasons=reasons,
                              questions=unique_questions, prompts=prompts,
                              involvement=involvement, missing_facts=missing, routed_to=routed,
                              applicant_sourced=bool(applicant), not_sure_fields=not_sure,
                              prescriptive_contradiction=contradiction)
