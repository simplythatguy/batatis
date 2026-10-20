"""Who must see a Section D issue. This is not a compliance determination.

Code citations are copied from a codedb lookup. A provision that does not resolve is omitted.
Statute pinpoints are the cite strings in the human-review research file, and only those.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .codes import Codes
from .models import Case
from .process_fields import alternative_path, confirmed_value
from .professional import ProfessionalFacts, ProfessionalResult, professional_involvement

# (division, provision id). Each id is a codedb-checked sentence in the research table.
REVIEW_PROVISIONS = (
    ('C', '2.4.2.2.(1)'),  # HR-02 Schedules A and B, coordinating registered professional
    ('C', '2.4.2.4.(1)'),  # HR-02 Schedule C-1 before occupancy
    ('C', '2.2.1.4.(1)'),  # HR-32 barrier-free relaxation
    ('C', '2.2.1.3.(1)'),  # HR-31 interpretation
    ('C', '2.2.2.3.(1)'),  # HR-33 minor variation, authority having jurisdiction
    ('C', '2.2.9.2.(1)'),  # HR-13 aquatic facility
    ('B', '4.2.2.1.(1)'),  # HR-14 geotechnical
    ('B', '10.4.7.2.(1)'),  # HR-12 Part 10 sprinklers
    ('C', '2.2.4.4.(1)'),  # guards, named from HR-03's codedb-checked sentence
    ('C', '2.2.11.4.(2)'),  # HR-42 medical gas report
    ('C', '2.5.1.1.(1)'),  # HR-43 off-site construction
    ('B', '3.2.2.2.(1)'),  # HR-16 special structure
)

# Source-PDF-checked pinpoints. Not code citations, and not rewritten.
_ACT_ARCHITECTS = 'Architects Act s.2(6)(b)'
_ACT_ENGINEERING = 'EGPA s.2(7)(a)'
_ACT_VARIANCE = 'Safety Codes Act s.38(1)'

_FLAG_ROWS = {
    'general_building': ('HR-01', 'Registered architectural and/or engineering professional', '2.4.1.1.(3)', 'C'),
    'general_exception': ('HR-01', 'Registered architectural and/or engineering professional', '2.4.1.1.(1)', 'C'),
    'general_unresolved': ('HR-01', 'Registered architectural and/or engineering professional', '2.4.1.1.(1)', 'C'),
    'part4': ('HR-03', 'Registered professional skilled in the work concerned', '2.4.1.2.(1)', 'C'),
    'part4_unknown': ('HR-03', 'Registered professional skilled in the work concerned', '2.4.1.2.(1)', 'C'),
    'preserved_wood_foundation': ('HR-10', 'Registered professional for field reviews', '2.4.1.2.(2)', 'C'),
    'foundation_unknown': ('HR-10', 'Registered professional for field reviews', '2.4.1.2.(2)', 'C'),
    'truss_design': ('HR-08', 'Registered engineering professional', '9.23.14.11.(2)', 'B'),
    'truss_part4': ('HR-03', 'Registered professional skilled in the work concerned', '2.4.1.2.(1)', 'C'),
    'trusses_unknown': ('HR-08', 'Registered engineering professional', '2.4.1.2.(1)', 'C'),
    'suppression': ('HR-11', 'Registered professional for the suppression system', '2.4.1.3.(1)', 'C'),
    'suppression_unknown': ('HR-11', 'Registered professional for the suppression system', '2.4.1.3.(1)', 'C'),
    'fire_alarm': ('HR-11', 'Registered professional for the fire-alarm system', '2.4.1.4.(1)', 'C'),
    'fire_alarm_unknown': ('HR-11', 'Registered professional for the fire-alarm system', '2.4.1.4.(1)', 'C'),
    'ahj_direction': ('HR-20', 'SCO', '2.4.1.1.(4)', 'C'),
    'special_safety': ('HR-20', 'SCO', '2.4.1.1.(4)', 'C'),
}


class HumanReview(BaseModel):
    """One person or authority the issue must be routed to. Not a grant or a determination."""

    model_config = ConfigDict(extra='forbid')
    trigger_id: str
    who: str
    why: str
    cite: str


def _lookup_cite(codes: Codes, provision_id: str, division: str) -> str | None:
    try:
        record = codes.provision(provision_id, division)
    except (ValueError, KeyError):
        return None
    if not record or not str(record.get('citation') or '').strip():
        return None
    return str(record['citation'])


def _add(rows: list[HumanReview], seen: set[tuple[str, str]], trigger_id: str, who: str, why: str, cite: str | None):
    if not cite:
        return
    key = (trigger_id, cite)
    if key in seen:
        return
    seen.add(key)
    rows.append(HumanReview(trigger_id=trigger_id, who=who, why=why, cite=cite))


def _screen(case: Case, codes: Codes) -> tuple[ProfessionalResult, ProfessionalFacts]:
    from .section_d_issues import PART9_MAX_SPAN_M
    span = confirmed_value(case, 'professional.span_m', 'span_m')
    facts = ProfessionalFacts.from_case(case)
    if isinstance(span, (int, float)) and not isinstance(span, bool) and span > PART9_MAX_SPAN_M and facts.part4_design is not True:
        facts = facts.model_copy(update={'part4_design': True})
    return professional_involvement(facts, codes, provisions=tuple(case.provisions)), facts


def _flag_rows(result: ProfessionalResult, codes: Codes, rows: list[HumanReview], seen: set[tuple[str, str]]) -> None:
    chosen = [reason for reason in result.reasons if reason.required == 'yes'] or list(result.reasons)
    for reason in chosen:
        spec = _FLAG_ROWS.get(reason.code)
        if spec is None:
            continue
        trigger_id, who, provision_id, division = spec
        _add(rows, seen, trigger_id, who,
             'The practice flag names this person or authority. This is not a determination.',
             _lookup_cite(codes, provision_id, division))


def _schedules(result: ProfessionalResult, codes: Codes, rows: list[HumanReview], seen: set[tuple[str, str]]) -> None:
    if result.general_required != 'yes':
        return
    _add(rows, seen, 'HR-02', 'Coordinating registered professional',
         'Before the permit application, retain a coordinating registered professional and provide Schedules A and B.',
         _lookup_cite(codes, '2.4.2.2.(1)', 'C'))
    _add(rows, seen, 'HR-02', 'Coordinating registered professional',
         'Schedule C-1 is required from the coordinating registered professional before occupancy.',
         _lookup_cite(codes, '2.4.2.4.(1)', 'C'))


def _acts(result: ProfessionalResult, facts: ProfessionalFacts, rows: list[HumanReview], seen: set[tuple[str, str]]) -> None:
    """The code exception can be no while the Acts still name a professional. No Act area limit is invented."""
    code_exception = result.general_required == 'no'
    units_above_act = (
        facts.occupancy == 'multi_family'
        and facts.principal_dwelling_units is not None
        and facts.principal_dwelling_units <= 4
        and facts.total_unit_count is not None
        and facts.total_unit_count > 4)
    if code_exception and units_above_act:
        _add(rows, seen, 'HR-22', 'Registered architect',
             'Total dwelling units, including suites, are above 4. The code exception can still be no.',
             _ACT_ARCHITECTS)
        _add(rows, seen, 'HR-21', 'Professional engineer',
             'The engineering small-building list does not exclude suites. The code exception can still be no.',
             _ACT_ENGINEERING)
    gross_differs = (
        code_exception
        and facts.gross_area_per_floor_m2 is not None
        and facts.building_area_m2 is not None
        and facts.gross_area_per_floor_m2 > facts.building_area_m2)
    if gross_differs:
        _add(rows, seen, 'HR-21', 'Professional engineer',
             'Gross area per floor is larger than the building area used for the code exception. '
             'No gross-area limit from the Act quote is applied here.',
             _ACT_ENGINEERING)


def _routing(case: Case, codes: Codes, rows: list[HumanReview], seen: set[tuple[str, str]]) -> None:
    if any(provision.startswith('3.8.') for provision in case.provisions):
        _add(rows, seen, 'HR-32', 'Provincial Barrier-Free Administrator or Provincial Building Administrator',
             'A relaxation under Division B Section 3.8 goes to the Provincial Barrier-Free Administrator or the Provincial Building Administrator.',
             _lookup_cite(codes, '2.2.1.4.(1)', 'C'))
    if confirmed_value(case, 'requests_interpretation') is True:
        _add(rows, seen, 'HR-31', 'Provincial Building Administrator',
             'A request for an interpretation goes to the Provincial Building Administrator.',
             _lookup_cite(codes, '2.2.1.3.(1)', 'C'))
    required = confirmed_value(case, 'dimension_required')
    proposed = confirmed_value(case, 'dimension_proposed')
    if isinstance(required, (int, float)) and isinstance(proposed, (int, float)) and not isinstance(required, bool) and not isinstance(proposed, bool) and required > 0:
        if abs(proposed - required) / required <= 0.02:
            _add(rows, seen, 'HR-33', 'Authority having jurisdiction',
                 'A dimensional difference of not more than 2% stays with the authority having jurisdiction. This list does not accept the variation.',
                 _lookup_cite(codes, '2.2.2.3.(1)', 'C'))


_DUTIES = (
    ('aquatic_facility', 'HR-13', 'Registered professional', 'C', '2.2.9.2.(1)',
     'Drawings for an aquatic facility go to a registered professional.'),
    ('geotechnical_part4', 'HR-14', 'Registered professional for geotechnical work', 'B', '4.2.2.1.(1)',
     'Part 4 geotechnical work goes to a registered professional.'),
    ('part10_sprinklers', 'HR-12', 'Registered professional for the sprinkler system', 'B', '10.4.7.2.(1)',
     'A Part 10 sprinkler system goes to a registered professional.'),
    ('guards', 'HR-03', 'Registered professional', 'C', '2.2.4.4.(1)',
     'Structural drawings of guards go to a registered professional.'),
    ('medical_gas_piping', 'HR-42', 'Testing agency and the authority having jurisdiction', 'C', '2.2.11.4.(2)',
     'Medical gas piping needs the testing agency report before use.'),
    ('off_site_constructed', 'HR-43', 'Certification organization or registered professional', 'C', '2.5.1.1.(1)',
     'Off-site construction needs the certification or professional review named for that work.'),
    ('special_structure', 'HR-16', 'Registered professional for fire protection', 'B', '3.2.2.2.(1)',
     'A structure outside Articles 3.2.2.20. to 3.2.2.92. needs fire protection engineering practice.'),
)


def _duties(case: Case, codes: Codes, rows: list[HumanReview], seen: set[tuple[str, str]]) -> None:
    for field, trigger_id, who, division, provision_id, why in _DUTIES:
        if confirmed_value(case, field) is True:
            _add(rows, seen, trigger_id, who, why, _lookup_cite(codes, provision_id, division))


def human_reviews(case: Case, codes: Codes) -> tuple[HumanReview, ...]:
    """Pinpoint rows for this case. A missing lookup is skipped rather than invented."""
    result, facts = _screen(case, codes)
    rows: list[HumanReview] = []
    seen: set[tuple[str, str]] = set()
    _flag_rows(result, codes, rows, seen)
    _schedules(result, codes, rows, seen)
    _acts(result, facts, rows, seen)
    _routing(case, codes, rows, seen)
    _duties(case, codes, rows, seen)
    if alternative_path(case):
        _add(rows, seen, 'HR-30', 'SCO or Administrator',
             'A variance is decided by an SCO or an Administrator. This list does not grant it.',
             _ACT_VARIANCE)
    return tuple(rows)
