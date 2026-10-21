"""Who must see a Section D issue. This is not a compliance determination.

Code citations are copied from a codedb lookup. A provision that does not resolve is omitted.
Only codedb-only triggers marked mandatory are returned as codedb rows, in routing order.
Those rows can push the practice flag toward yes. The other codedb-only triggers are
discretionary or an authority-having-jurisdiction acceptance. They set routed_to officer
and do not push yes. Statute rows stay for a pinpoint confirmed from the Act text.
Mixed triggers stay off this list.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .codes import Codes
from .models import Case
from .process_fields import alternative_path, confirmed_value
from .professional import (PART9_MAX_SPAN_M, ProfessionalFacts, ProfessionalResult, Requirement,
                           _screen_involvement, professional_involvement)

# (division, provision id). Each id is a codedb-checked sentence the mandatory rows look up.
REVIEW_PROVISIONS = (
    ('C', '2.4.1.2.(1)'),  # HR-03 Part 4 designer
    ('C', '2.4.1.1.(3)'),  # HR-01 authentication outside the general exceptions
    ('B', '9.15.3.3.(2)'),  # HR-06 joist span
    ('B', '9.15.3.3.(3)'),  # HR-06 live load
    ('B', '9.23.4.1.(2)'),  # HR-06 non-residential floors
    ('B', '9.16.1.2.(1)'),  # HR-06 floor-on-ground
    ('B', '9.15.1.2.(1)'),  # HR-06 permafrost
    ('B', '9.3.1.1.(3)'),  # HR-07 reinforced concrete
    ('B', '9.24.1.1.(2)'),  # HR-07 loadbearing steel studs
    ('B', '9.17.1.1.(2)'),  # HR-07 columns
    ('B', '9.20.5.2.(3)'),  # HR-07 lintels
    ('B', '9.23.1.1.(2)'),  # HR-07 framing past the Part 9 wood limits
    ('B', '9.4.2.2.(3)'),  # HR-07 bowstring / arch truss span
    ('B', '9.23.3.5.(4)'),  # HR-05 sheathing fastening
    ('B', '9.23.6.1.(6)'),  # HR-05 anchorage
    ('B', '9.23.16.5.(3)'),  # HR-05 lumber roof sheathing
    ('A', '1.3.3.2.(1)'),  # HR-04 Parts 3 to 6 apply
    ('A', '1.3.3.3.(1)'),  # HR-04 Part 9 scope, checked with the sentence above
    ('C', '2.4.1.3.(1)'),  # HR-11 suppression
    ('C', '2.4.1.4.(1)'),  # HR-11 fire alarm
    ('B', '4.2.2.1.(1)'),  # HR-14 subsurface investigation
    ('B', '4.2.4.1.(3)'),  # HR-14 geotechnical resistance
    ('B', '4.2.7.2.(2)'),  # HR-14 load tests
    ('C', '2.2.9.2.(1)'),  # HR-13 aquatic facility
    ('B', '10.4.7.2.(1)'),  # HR-12 Part 10 sprinklers
    ('B', '10.1.1.2.(2)'),  # HR-12 Part 10 applies to workforce accommodation
)

# verification_class == codedb-only. 21 of 36. Mandatory routing uses the ten below.
CODEDB_ONLY_TRIGGERS = frozenset({
    'HR-01', 'HR-03', 'HR-04', 'HR-05', 'HR-06', 'HR-07', 'HR-11', 'HR-12', 'HR-13', 'HR-14',
    'HR-15', 'HR-17', 'HR-31', 'HR-32', 'HR-33', 'HR-34', 'HR-35', 'HR-40', 'HR-41', 'HR-42', 'HR-44',
})
# routing_priority from the research file. Discretionary codedb-only ids are the rest.
MANDATORY_ORDER = (
    'HR-03', 'HR-01', 'HR-06', 'HR-07', 'HR-05', 'HR-04', 'HR-11', 'HR-14', 'HR-13', 'HR-12',
)
MANDATORY_TRIGGERS = frozenset(MANDATORY_ORDER)
DISCRETIONARY_TRIGGERS = CODEDB_ONLY_TRIGGERS - MANDATORY_TRIGGERS

# Pinpoints confirmed from the King's Printer office consolidations Karen checked.
# Architects Act, RSA 2000 c A-44, current as of November 16, 2022, s.2(6)(b)(ii).
# Engineering and Geoscience Professions Act, RSA 2000 c E-11, current as of December 7, 2023:
# s.2(7)(b)(ii) counts dwelling units; s.2(7)(a) is assembly or institutional gross area.
# Other occupancies get no Act gross-area row. Safety Codes Act s.38(1) is unchanged.
_ACT_ARCHITECTS = 'Architects Act, RSA 2000 c A-44 (current as of Nov 16, 2022)'
_ACT_ENGINEERING = 'Engineering and Geoscience Professions Act, RSA 2000 c E-11 (current as of Dec 7, 2023)'
_ACT_VARIANCE_NAME = 'Safety Codes Act, RSA 2000 c S-1 (current as of Dec 1, 2025)'
_CITE_ARCH_UNITS = 'Architects Act s.2(6)(b)(ii)'
_CITE_EGPA_UNITS = 'EGPA s.2(7)(b)(ii)'
_CITE_EGPA_GROSS = 'EGPA s.2(7)(a)'
_CITE_VARIANCE = 'Safety Codes Act s.38(1)'
_QUOTE_ARCH_UNITS = (
    'a building for residential occupancy that (i) is a single family dwelling, or '
    '(ii) is a multiple family dwelling containing 4 dwelling units or less;'
)
_QUOTE_EGPA_UNITS = (
    'a building for residential occupancy that (i) is a single family dwelling, or '
    '(ii) is a multiple family dwelling, containing 4 dwelling units or less;'
)
_QUOTE_EGPA_GROSS = (
    'a building, 3 storeys or less in height, for assembly occupancy or institutional occupancy that, '
    '(i) in the case of a single storey building, has a gross area of 300 square metres or less, '
    '(ii) in the case of a 2 storey building, has a gross area of 150 square metres or less on each floor, or '
    '(iii) in the case of a 3 storey building, has a gross area of 100 square metres or less on each floor;'
)
_QUOTE_VARIANCE = (
    'An Administrator or a safety codes officer may issue a written variance with respect to any thing, '
    'process or activity to which this Act applies if the Administrator or officer is of the opinion that '
    'the variance provides approximately equivalent or greater safety performance with respect to persons '
    'and property as that provided for by this Act.'
)
_UNITS_WHY = 'counts dwelling units (4 or less); whether a suite counts is for the officer'
_ASSEMBLY_OR_INSTITUTIONAL = frozenset({'assembly', 'care', 'treatment', 'detention'})
_OUTSIDE_PART9_OCCUPANCY = _ASSEMBLY_OR_INSTITUTIONAL
_JOIST_SPAN_M = 4.9
_LIVE_LOAD_KPA = 2.4
_WIND_KPA = 1.2
_SA_FASTENING = 1.8
_SA_LUMBER_ROOF = 1.2
_PART9_STOREYS = 3
_PART9_AREA_M2 = 600
_ARCH_TRUSS_SPAN_M = 6
_ARCH_TRUSS_TYPES = frozenset({
    'bowstring', 'bow_string', 'arch', 'semi_circular', 'semicircular',
})
_ELEMENT_PROVISIONS = (
    ('reinforced_concrete', 'B', '9.3.1.1.(3)',
     'Reinforced concrete is stated, so that design is Part 4 work for a registered professional.'),
    ('loadbearing_steel_studs', 'B', '9.24.1.1.(2)',
     'Loadbearing steel studs are stated, so that design is Part 4 work for a registered professional.'),
    ('steel_studs', 'B', '9.24.1.1.(2)',
     'Loadbearing steel studs are stated, so that design is Part 4 work for a registered professional.'),
    ('nonstandard_columns', 'B', '9.17.1.1.(2)',
     'Columns outside the Part 9 cases are stated, so that design is Part 4 work for a registered professional.'),
    ('non_standard_columns', 'B', '9.17.1.1.(2)',
     'Columns outside the Part 9 cases are stated, so that design is Part 4 work for a registered professional.'),
    ('masonry_or_steel_lintel', 'B', '9.20.5.2.(3)',
     'A masonry or steel lintel is stated, so that design is Part 4 work for a registered professional.'),
    ('masonry_lintel', 'B', '9.20.5.2.(3)',
     'A masonry or steel lintel is stated, so that design is Part 4 work for a registered professional.'),
    ('steel_lintel', 'B', '9.20.5.2.(3)',
     'A masonry or steel lintel is stated, so that design is Part 4 work for a registered professional.'),
    ('framing_exceeds_9_23_1_1', 'B', '9.23.1.1.(2)',
     'Framing is past the Part 9 wood-construction limits, so that design is Part 4 work for a registered professional.'),
)
_ELEMENT_FIELDS = (
    ('reinforced_concrete', 'reinforced_concrete'),
    ('loadbearing_steel_studs', 'loadbearing_steel_studs'),
    ('nonstandard_columns', 'nonstandard_columns'),
    ('masonry_or_steel_lintel', 'masonry_or_steel_lintel'),
    ('framing_exceeds_9_23_1_1', 'framing_exceeds_9_23_1_1'),
)


class HumanReview(BaseModel):
    """One person or authority the issue must be routed to. Not a grant or a determination."""

    model_config = ConfigDict(extra='forbid')
    trigger_id: str
    who: str
    why: str
    cite: str
    source: Literal['codedb', 'statute'] = 'codedb'
    act: str | None = None
    quote: str | None = None


@dataclass(frozen=True)
class MandatoryHit:
    """One mandatory codedb-only row whose cite was copied from a lookup."""

    trigger_id: str
    who: str
    why: str
    cite: str
    division: Literal['A', 'B', 'C']
    provision_id: str


def _lookup_cite(codes: Codes, provision_id: str, division: str) -> str | None:
    try:
        record = codes.provision(provision_id, division)
    except (ValueError, KeyError):
        return None
    if not record or not str(record.get('citation') or '').strip():
        return None
    return str(record['citation'])


def _add(rows: list[HumanReview], seen: set[tuple[str, str]], trigger_id: str, who: str, why: str,
         cite: str | None, *, source: Literal['codedb', 'statute'] = 'codedb',
         act: str | None = None, quote: str | None = None):
    if not cite:
        return
    if source == 'statute' and not (act and quote):
        return
    key = (trigger_id, cite)
    if key in seen:
        return
    seen.add(key)
    rows.append(HumanReview(trigger_id=trigger_id, who=who, why=why, cite=cite,
                            source=source, act=act, quote=quote))


def _number(case: Case, name: str) -> float | None:
    value = confirmed_value(case, f'professional.{name}', name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _yes(case: Case, name: str) -> bool:
    return confirmed_value(case, f'professional.{name}', name) is True


def _text(case: Case, name: str) -> str | None:
    value = confirmed_value(case, f'professional.{name}', name)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _tokens(case: Case, name: str) -> set[str]:
    value = confirmed_value(case, f'professional.{name}', name)
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return set()
    tokens = set()
    for item in value:
        token = str(item).strip().lower().replace('-', '_').replace(' ', '_')
        if not token or token.startswith('non_loadbearing') or token.startswith('nonloadbearing'):
            continue
        tokens.add(token)
    return tokens


def _remember(hits: list[MandatoryHit], seen: set[tuple[str, str]], codes: Codes,
              trigger_id: str, who: str, why: str, division: Literal['A', 'B', 'C'],
              provision_id: str) -> None:
    key = (trigger_id, provision_id)
    if key in seen:
        return
    cite = _lookup_cite(codes, provision_id, division)
    if not cite:
        return
    seen.add(key)
    hits.append(MandatoryHit(trigger_id=trigger_id, who=who, why=why, cite=cite,
                             division=division, provision_id=provision_id))


def _part4_chain_resolves(codes: Codes) -> bool:
    """HR-04, HR-05, HR-06 and HR-07 name a Part 4 duty. Both sentences have to resolve."""
    return _lookup_cite(codes, '2.4.1.2.(1)', 'C') is not None


def _hr03(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]]) -> None:
    span = _number(case, 'span_m')
    elements = _tokens(case, 'part4_elements')
    if not (_yes(case, 'part4_design') or elements or (span is not None and span > PART9_MAX_SPAN_M)):
        return
    _remember(hits, seen, codes, 'HR-03', 'Registered professional skilled in the work concerned',
              'Part 4 design is stated. Recommend a registered professional skilled in that work.',
              'C', '2.4.1.2.(1)')


def _hr01(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]],
          general_required: Requirement) -> None:
    if general_required != 'yes':
        return
    _remember(hits, seen, codes, 'HR-01', 'Registered architectural and/or engineering professional',
              'The stated building is outside the general exceptions. Recommend that a registered '
              'professional authenticate the applicable drawings and specifications.',
              'C', '2.4.1.1.(3)')


def _hr06(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]]) -> None:
    if not _part4_chain_resolves(codes):
        return
    who = 'Registered professional for the structural or geotechnical work'
    span = _number(case, 'supported_joist_span_m')
    live = _number(case, 'specified_live_load_kPa')
    if span is not None and span > _JOIST_SPAN_M:
        _remember(hits, seen, codes, 'HR-06', who,
                  'Supported joist span is above 4.9 m, so the footing design is Part 4 work for a registered professional.',
                  'B', '9.15.3.3.(2)')
    if live is not None and live > _LIVE_LOAD_KPA:
        _remember(hits, seen, codes, 'HR-06', who,
                  'Specified live load is above 2.4 kPa, so the footing design is Part 4 work for a registered professional.',
                  'B', '9.15.3.3.(3)')
    if _yes(case, 'floor_use_non_residential'):
        _remember(hits, seen, codes, 'HR-06', who,
                  'The supported floor is other than residential, so the spans are Part 4 work for a registered professional.',
                  'B', '9.23.4.1.(2)')
    if _yes(case, 'slab_supports_superstructure'):
        _remember(hits, seen, codes, 'HR-06', who,
                  'A floor-on-ground supports the superstructure, so that design is Part 4 work for a registered professional.',
                  'B', '9.16.1.2.(1)')
    if _yes(case, 'permafrost'):
        _remember(hits, seen, codes, 'HR-06', who,
                  'The building is on permafrost, so the foundation design is Part 4 work for a registered professional.',
                  'B', '9.15.1.2.(1)')


def _hr07(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]]) -> None:
    if not _part4_chain_resolves(codes):
        return
    who = 'Registered professional for the structural work'
    tokens = _tokens(case, 'structural_elements')
    for token, field in _ELEMENT_FIELDS:
        if _yes(case, field):
            tokens.add(token)
    emitted: set[str] = set()
    for token, division, provision_id, why in _ELEMENT_PROVISIONS:
        if token in tokens and provision_id not in emitted:
            emitted.add(provision_id)
            _remember(hits, seen, codes, 'HR-07', who, why, division, provision_id)
    truss = _text(case, 'truss_type')
    truss_span = _number(case, 'unsupported_span_m')
    if truss and truss_span is not None and truss_span > _ARCH_TRUSS_SPAN_M:
        normalized = truss.lower().replace('-', '_').replace(' ', '_')
        if normalized in _ARCH_TRUSS_TYPES:
            _remember(hits, seen, codes, 'HR-07', who,
                      'A bowstring, arch, or semi-circular truss spans more than 6 m, so that design is Part 4 work for a registered professional.',
                      'B', '9.4.2.2.(3)')


def _hr05(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]]) -> None:
    if not _part4_chain_resolves(codes):
        return
    who = 'Registered professional for the structural work'
    wind = _number(case, 'hourly_wind_pressure_1in50_kPa')
    sa = _number(case, 'Sa_0_2')
    if sa is None:
        sa = _number(case, 'sa_0_2')
    lumber = _yes(case, 'lumber_roof_sheathing')
    braced = _yes(case, 'braced_wall_panels_required')
    wind_hit = wind is not None and wind >= _WIND_KPA
    sa_fastening = sa is not None and sa > _SA_FASTENING
    if wind_hit or (braced and sa_fastening):
        _remember(hits, seen, codes, 'HR-05', who,
                  'Wind or seismic demand sends sheathing fastening to Part 4, so a registered professional is named for that work.',
                  'B', '9.23.3.5.(4)')
    if wind_hit or sa_fastening:
        _remember(hits, seen, codes, 'HR-05', who,
                  'Wind or seismic demand sends anchorage to Part 4, so a registered professional is named for that work.',
                  'B', '9.23.6.1.(6)')
    if lumber and ((sa is not None and sa > _SA_LUMBER_ROOF) or wind_hit):
        _remember(hits, seen, codes, 'HR-05', who,
                  'Lumber roof sheathing is stated with the wind or seismic demand, so that design is Part 4 work for a registered professional.',
                  'B', '9.23.16.5.(3)')


def _outside_part9(case: Case, facts: ProfessionalFacts) -> bool:
    storeys = facts.storeys
    area = facts.building_area_m2
    if storeys is not None and storeys > _PART9_STOREYS:
        return True
    if area is not None and area > _PART9_AREA_M2:
        return True
    if facts.occupancy in _OUTSIDE_PART9_OCCUPANCY:
        return True
    if _yes(case, 'post_disaster') or _yes(case, 'high_hazard_industrial') or _yes(case, 'group_f1'):
        return True
    return False


def _hr04(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]]) -> None:
    facts = ProfessionalFacts.from_case(case)
    if not _outside_part9(case, facts):
        return
    if not _part4_chain_resolves(codes) or _lookup_cite(codes, '1.3.3.3.(1)', 'A') is None:
        return
    _remember(hits, seen, codes, 'HR-04', 'Registered professional for the Part 4 design',
              'This building is outside Part 9 scope, so Part 4 design applies and a registered professional is named for that design.',
              'A', '1.3.3.2.(1)')


def _hr11(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]],
          general_required: Requirement) -> None:
    if _yes(case, 'minor_alteration_existing_system'):
        return
    if general_required != 'yes':
        return
    if _yes(case, 'fire_suppression'):
        _remember(hits, seen, codes, 'HR-11',
                  'Registered professional for fire protection, mechanical, or electrical',
                  'A fire-suppression system is stated for a building outside the general exceptions. '
                  'Recommend documenting professional retention for design, field review and witnessing of testing.',
                  'C', '2.4.1.3.(1)')
    if _yes(case, 'fire_alarm'):
        _remember(hits, seen, codes, 'HR-11',
                  'Registered professional for fire protection, mechanical, or electrical',
                  'A fire-alarm system is stated for a building outside the general exceptions. '
                  'Recommend documenting professional retention for design, field review and witnessing of verification.',
                  'C', '2.4.1.4.(1)')


def _hr14(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]]) -> None:
    who = 'Registered professional for geotechnical work'
    if _yes(case, 'geotechnical_part4') or _yes(case, 'part4_foundation'):
        _remember(hits, seen, codes, 'HR-14', who,
                  'Part 4 geotechnical work goes to a registered professional.',
                  'B', '4.2.2.1.(1)')
    if _yes(case, 'deep_foundations'):
        _remember(hits, seen, codes, 'HR-14', who,
                  'Geotechnical loads and resistances go to a registered professional.',
                  'B', '4.2.4.1.(3)')
    if _yes(case, 'load_tests'):
        _remember(hits, seen, codes, 'HR-14', who,
                  'Deep-foundation load-test interpretation goes to a registered professional.',
                  'B', '4.2.7.2.(2)')


def _hr13(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]]) -> None:
    if not _yes(case, 'aquatic_facility'):
        return
    _remember(hits, seen, codes, 'HR-13', 'Registered professional',
              'Drawings for an aquatic facility go to a registered professional.',
              'C', '2.2.9.2.(1)')


def _hr12(case: Case, codes: Codes, hits: list[MandatoryHit], seen: set[tuple[str, str]]) -> None:
    sprinklers = _yes(case, 'part10_sprinklers') or (
        _yes(case, 'part10_building') and _yes(case, 'fire_suppression'))
    if not sprinklers:
        return
    if _yes(case, 'part10_building') and _lookup_cite(codes, '10.1.1.2.(2)', 'B') is None:
        return
    _remember(hits, seen, codes, 'HR-12', 'Registered professional for the sprinkler system',
              'A Part 10 sprinkler system goes to a registered professional.',
              'B', '10.4.7.2.(1)')


def mandatory_hits(case: Case, codes: Codes, *, general_required: Requirement | None = None) -> tuple[MandatoryHit, ...]:
    """Mandatory codedb-only triggers whose cites resolved, in routing order."""
    if general_required is None:
        general_required = _screen_involvement(case, codes).general_required
    hits: list[MandatoryHit] = []
    seen: set[tuple[str, str]] = set()
    _hr03(case, codes, hits, seen)
    _hr01(case, codes, hits, seen, general_required)
    _hr06(case, codes, hits, seen)
    _hr07(case, codes, hits, seen)
    _hr05(case, codes, hits, seen)
    _hr04(case, codes, hits, seen)
    _hr11(case, codes, hits, seen, general_required)
    _hr14(case, codes, hits, seen)
    _hr13(case, codes, hits, seen)
    _hr12(case, codes, hits, seen)
    order = {trigger_id: index for index, trigger_id in enumerate(MANDATORY_ORDER)}
    hits.sort(key=lambda hit: order[hit.trigger_id])
    return tuple(hits)


def discretionary_review(case: Case) -> bool:
    """True when a discretionary or authority-acceptance trigger is present. This does not push yes."""
    if any(provision.startswith('3.8.') for provision in case.provisions):
        return True
    if confirmed_value(case, 'requests_interpretation') is True:
        return True
    required = _number(case, 'dimension_required')
    proposed = _number(case, 'dimension_proposed')
    if required is not None and proposed is not None and required > 0 and abs(proposed - required) / required <= 0.02:
        return True
    flags = (
        'temporary_works', 'multiple_responsible_persons', 'supporting_tests_or_studies',
        'change_of_occupancy', 'alteration_existing', 'aquatic_equipment', 'tent_or_air_supported',
        'temporary_building', 'fire_resistance_rating_by_test', 'cladding_combustible',
        'medical_gas_piping', 'welded_steel', 'minor_alteration_existing_system',
    )
    if any(_yes(case, name) for name in flags):
        return True
    if _text(case, 'coordinator_name'):
        return True
    source = _text(case, 'fire_resistance_rating_source')
    if source and source.casefold() in {'test', 'can/ulc-s101', 's101'}:
        return True
    return False


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
        _add(rows, seen, 'HR-22', 'Registered architect', _UNITS_WHY, _CITE_ARCH_UNITS,
             source='statute', act=_ACT_ARCHITECTS, quote=_QUOTE_ARCH_UNITS)
        _add(rows, seen, 'HR-21', 'Professional engineer', _UNITS_WHY, _CITE_EGPA_UNITS,
             source='statute', act=_ACT_ENGINEERING, quote=_QUOTE_EGPA_UNITS)
    gross_differs = (
        code_exception
        and facts.occupancy in _ASSEMBLY_OR_INSTITUTIONAL
        and facts.gross_area_per_floor_m2 is not None
        and facts.building_area_m2 is not None
        and facts.gross_area_per_floor_m2 > facts.building_area_m2)
    if gross_differs:
        _add(rows, seen, 'HR-21', 'Professional engineer',
             'The Act lists gross area for assembly or institutional occupancy. This row does not apply a limit.',
             _CITE_EGPA_GROSS, source='statute', act=_ACT_ENGINEERING, quote=_QUOTE_EGPA_GROSS)


def human_reviews(case: Case, codes: Codes) -> tuple[HumanReview, ...]:
    """Mandatory codedb rows, then confirmed statute rows. A missing lookup is skipped."""
    rows = [HumanReview(trigger_id=hit.trigger_id, who=hit.who, why=hit.why, cite=hit.cite)
            for hit in mandatory_hits(case, codes)]
    seen = {(row.trigger_id, row.cite) for row in rows}
    result = professional_involvement(case, codes)
    _acts(result, ProfessionalFacts.from_case(case), rows, seen)
    if alternative_path(case):
        _add(rows, seen, 'HR-30', 'SCO or Administrator',
             'A variance is decided by an SCO or an Administrator. This list does not grant it.',
             _CITE_VARIANCE, source='statute', act=_ACT_VARIANCE_NAME, quote=_QUOTE_VARIANCE)
    return tuple(row for row in rows if row.source == 'statute' or row.trigger_id in MANDATORY_TRIGGERS)
