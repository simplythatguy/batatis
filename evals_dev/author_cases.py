"""Write evals_dev/cases/*.json from the specs below.

Authored from the code database only. Section C rows are filled from `codedb.lookup`, never typed
by hand. Rerun after editing a spec, then run validate_cases.py.

    .venv/bin/python evals_dev/author_cases.py [--db PATH]
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from codedb import lookup  # noqa: E402

DEFAULT_DB = '/Users/aamia/.t3/projects/batatis/codedb/build/codedb.sqlite'
DATE = '2026-10-20'


def B(p, role='benchmark'):
    return {'division': 'B', 'provision': p, 'role': role}


def S(p, why, division='B'):
    return {'division': division, 'provision': p, 'why': why}


def N(p, use, why):
    return {'division': 'B', 'provision': p, 'prohibited_use': use, 'why': why}


def C(p):
    return {'division': 'C', 'provision': p}


ADMIN = [
    {'field': 'owner name and contact', 'why': 'Section A of the variance form', 'priority': 'administrative'},
    {'field': 'civic address and legal description', 'why': 'Section A identifies the property', 'priority': 'administrative'},
]

CASES = [
    # ---------------------------------------------------------------- Part 9, most varied articles
    dict(id='dev-001', applicant_type='homebuilder', topic='part9-spatial-separation', code_part=9, jurisdiction='Calgary',
         seed_provision='9.10.15.5.(8)',
         description=("We're building a new single detached house on a narrow infill lot. The north side wall sits 0.3 m from the "
                      "property line, which is the side yard against the neighbour's lot, not a street or lane. The client wants the "
                      "same 450 mm roof overhang all the way around, including over that north wall. The soffit would be vented "
                      "aluminum. Can we do this as a variance and what would we need to show?"),
         known_facts=['single detached house', 'limiting distance 0.3 m on the north side', 'faces a side property line, not a public way',
                      '450 mm overhang wanted over that wall', 'vented aluminum soffit'],
         missing_info=ADMIN + [{'field': 'soffit construction and protection proposed', 'why': 'mitigation must address fire spread to the neighbour', 'priority': 'administrative'}],
         gold=dict(departure='Roof soffit projects over an exposing building face whose limiting distance is 0.45 m or less.',
                   must_cite=[B('9.10.15.5.(8)')],
                   should_cite=[S('9.10.15.5.(11)', 'protection required for soffits within 1.2 m of the property line'),
                                S('9.10.15.5.(9)', 'projection limit when the limiting distance exceeds 0.45 m')],
                   must_not_cite=[N('9.10.15.5.(10)', 'as the exception permitting the soffit', 'the wall faces a side property line, not a public way')],
                   section_c=['9.10.15.5.(8)'],
                   engineering_required='no',
                   engineering_reason='Single-family dwelling: registered professional involvement not required unless the authority invokes special safety concerns.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(4)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-002', applicant_type='homebuilder', topic='part9-fire-separations', code_part=9, jurisdiction='Edmonton',
         seed_provision='9.10.11.2.(2)',
         description=("We're planning a row of six two-storey townhouses on one lot, and every unit will have a legal basement suite. "
                      "We'd like to build every party wall the same way, as a 1-hour rated double-stud wall running from the footing to "
                      "the underside of the roof deck, instead of making some of them full firewalls. Is there a way to get that approved?"),
         known_facts=['six houses in one row', 'each house has a secondary suite', 'two storeys', '1 h party walls from footing to roof deck proposed for all'],
         missing_info=ADMIN + [{'field': 'tested wall assembly listing for the 1 h party wall', 'why': 'Section D evidence', 'priority': 'administrative'}],
         gold=dict(departure='Party walls between every pair of houses with secondary suites built as 1 h fire separations; no firewalls dividing the row into buildings of not more than 2 houses.',
                   must_cite=[B('9.10.11.2.(2)')],
                   should_cite=[S('9.10.11.2.(1)', 'the 1 h party-wall option the applicant is extending'),
                                S('9.10.11.2.(3)', 'continuity of the party wall')],
                   must_not_cite=[],
                   section_c=['9.10.11.2.(2)'],
                   engineering_required='yes',
                   engineering_reason='Six dwelling units in one building (secondary suites aside) exceeds the four-unit exemption, so authenticated drawings are required.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(2)'), C('2.4.1.1.(3)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-003', applicant_type='contractor', topic='part9-fire-separations', code_part=9, jurisdiction='Red Deer',
         seed_provision='9.10.13.13.(1)',
         description=("Mechanical contractor here. On a three-storey, twelve-unit wood-frame apartment we have supply ducts that pass "
                      "through the rated corridor walls. There's no room above the ceiling for damper access panels, so we'd like to skip "
                      "the fire dampers and instead use 26 gauge steel duct sealed with a listed firestop at each wall. The ducts are about "
                      "150 by 250 mm and serve the suites' heat recovery ventilators."),
         known_facts=['three storeys, twelve dwelling units, wood frame', 'ducts penetrate rated corridor walls', 'no fire dampers proposed',
                      'steel duct with listed firestop instead', 'ducts about 150 x 250 mm serving HRVs'],
         missing_info=ADMIN + [{'field': 'fire-resistance rating of the corridor walls', 'why': 'sets the rating the penetration must maintain', 'priority': 'administrative'}],
         gold=dict(departure='Ducts penetrate rated fire separations without fire dampers; firestopped steel duct proposed instead.',
                   must_cite=[B('9.10.13.13.(1)')],
                   should_cite=[S('9.10.9.6.(1)', 'firestopping of penetrations in fire separations'),
                                S('9.10.13.13.(2)', 'the small branch-duct exemption; the stated duct size exceeds it')],
                   must_not_cite=[N('9.10.13.13.(2)', 'as making dampers unnecessary', 'the stated duct is larger than the exemption allows and does not serve only air-conditioning units')],
                   section_c=['9.10.13.13.(1)'],
                   engineering_required='yes',
                   engineering_reason='Twelve-unit residential building is outside the exemption; registered professionals authenticate the design, including the mechanical changes.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(3)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-004', applicant_type='architect-engineer', topic='part9-spatial-separation', code_part=9, jurisdiction='Canmore',
         seed_provision='9.10.14.2.(2)',
         description=("I'm the architect on a side-by-side duplex with a wall that is angled about 20 degrees to the side property line, "
                      "so it runs from 1.2 m to 3.0 m away. For the window-area calculation we'd like to use the average distance of the "
                      "wall, about 2.1 m, rather than drawing the plane at the closest point. Using the closest point cuts our glazing "
                      "allowance by more than half."),
         known_facts=['duplex', 'skewed wall 1.2 m to 3.0 m from the side property line', 'average distance 2.1 m proposed for unprotected-opening area'],
         missing_info=ADMIN + [{'field': 'sprinklered or not', 'why': 'changes the permitted opening area', 'priority': 'administrative'}],
         gold=dict(departure='Exposing building face location for a skewed wall taken at the average distance instead of the plane with no unprotected openings in front of it.',
                   must_cite=[B('9.10.14.2.(2)')],
                   should_cite=[S('9.10.14.4.(1)', 'maximum aggregate area of unprotected openings'),
                                S('9.10.15.4.(1)', 'glazed openings in houses, if the duplex is treated under the house provisions')],
                   must_not_cite=[],
                   section_c=['9.10.14.2.(2)'],
                   engineering_required='no',
                   engineering_reason='Two-unit residential building is within the exemption; the architect is engaged by choice.',
                   engineering_citations=[C('2.4.1.1.(1)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-005', applicant_type='manufacturer', topic='cladding', code_part=9, jurisdiction='unspecified',
         seed_provision='9.10.14.5.(1)',
         description=("We make a wood-plastic composite siding board. Builders want to use it on walls close to the property line on "
                      "small apartment buildings, where the code calls for noncombustible cladding. We have cone calorimeter results and a "
                      "flame-spread rating of 75 but we have not done the full-scale exterior wall fire test. What do we need to get it "
                      "accepted in Alberta?"),
         known_facts=['wood-plastic composite siding', 'intended where noncombustible cladding is required', 'cone calorimeter data and flame-spread rating 75',
                      'no full-scale exterior wall test'],
         missing_info=[{'field': 'specific building, limiting distance and opening percentage', 'why': 'the required construction depends on the exposing building face', 'priority': 'administrative'},
                       {'field': 'whether a CCMC evaluation exists', 'why': 'product-level acceptance route', 'priority': 'administrative'}],
         gold=dict(departure='Combustible composite cladding on exposing building faces where the table requires noncombustible cladding, without the full-scale wall-assembly test.',
                   must_cite=[B('9.10.14.5.(1)'), B('9.10.14.5.(2)')],
                   should_cite=[S('3.1.5.5.(1)', 'full-scale test acceptance criteria referenced by the Part 9 route')],
                   must_not_cite=[],
                   section_c=['9.10.14.5.(1)', '9.10.14.5.(2)'],
                   engineering_required='depends',
                   engineering_reason='Depends on the building it goes on: buildings outside the Division C exemption need registered professionals.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(3)')],
                   intake_action='proceed_conditionally')),
    # ---------------------------------------------------------------- continuous exterior insulation / sheathing
    dict(id='dev-006', applicant_type='manufacturer', topic='envelope-insulation-sheathing', code_part=9, jurisdiction='Edmonton',
         seed_provision='9.25.5.2.(1)',
         description=("Our product is a 25 mm foil-faced polyiso board meant to go on the outside of 2x6 walls with R-20 batts, as "
                      "continuous insulation under the siding. The foil makes it essentially vapour-impermeable. A builder in Edmonton "
                      "was told the outboard insulation is too thin for that wall. We think the foil is fine because the joints are "
                      "taped. How do we make the case?"),
         known_facts=['25 mm foil-faced polyiso exterior insulation', '2x6 wall with R-20 batts', 'low vapour permeance', 'Edmonton', 'taped joints'],
         missing_info=[{'field': 'whether there is a vented air space outboard of the board', 'why': 'one of the acceptable positions', 'priority': 'administrative'},
                       {'field': 'interior moisture loads (any high-humidity use)', 'why': 'high-moisture uses need design under Part 5', 'priority': 'administrative'}],
         gold=dict(departure='Low-permeance exterior insulation placed where the outboard-to-inboard thermal resistance ratio is below the tabulated minimum.',
                   must_cite=[B('9.25.5.2.(1)')],
                   should_cite=[S('9.25.5.1.(1)', 'which sheet materials the positioning rule applies to'),
                                S('9.25.5.1.(2)', 'Part 5 design for high-moisture interiors')],
                   must_not_cite=[],
                   section_c=['9.25.5.2.(1)'],
                   engineering_required='depends',
                   engineering_reason='Depends on the building type and whether a hygrothermal design under Part 5 is used to justify the assembly.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(4)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-007', applicant_type='contractor', topic='envelope-insulation-sheathing', code_part=9, jurisdiction='Lethbridge',
         seed_provision='9.27.3.4.(2)',
         description=("Renovation contractor. On a bungalow re-side we're adding 50 mm semi-rigid mineral wool boards over the existing "
                      "OSB, strapping and fibre cement siding. We want to leave out the housewrap and let the mineral wool act as the "
                      "drainage layer, with the board joints just butted together, not taped or lapped."),
         known_facts=['single detached bungalow', '50 mm mineral wool exterior boards over OSB', 'no sheathing membrane', 'butted unsealed joints', 'fibre cement on strapping'],
         missing_info=ADMIN,
         gold=dict(departure='Insulating sheathing used in lieu of a sheathing membrane with joints neither sealed nor lapped, over moisture-sensitive OSB.',
                   must_cite=[B('9.27.3.4.(2)')],
                   should_cite=[S('9.27.3.4.(1)', 'when insulating sheathing can replace the membrane'),
                                S('9.27.3.1.(1)', 'second plane of protection')],
                   must_not_cite=[],
                   section_c=['9.27.3.4.(2)'],
                   engineering_required='no',
                   engineering_reason='Single-family dwelling renovation within the exemption.',
                   engineering_citations=[C('2.4.1.1.(1)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-008', applicant_type='homebuilder', topic='envelope-insulation-sheathing', code_part=9, jurisdiction='Airdrie',
         seed_provision='9.23.17.1.(1)',
         description=("For our next phase of single-family homes we want to drop the OSB on exterior walls and put 50 mm rigid foam "
                      "directly on the studs, then large-format fibre cement panels screwed through the foam into the studs. The panels "
                      "need fastening between studs according to the maker. Racking would be handled by let-in steel strap bracing."),
         known_facts=['single-family homes', 'no wood sheathing', '50 mm rigid foam on studs', 'fibre cement panels needing intermediate fastening', 'steel strap bracing'],
         missing_info=ADMIN + [{'field': 'how the bracing is designed (prescriptive or engineered)', 'why': 'decides whether a professional must design the lateral system', 'priority': 'administrative'}],
         gold=dict(departure='Exterior walls left unsheathed although the cladding requires intermediate fastening between supports.',
                   must_cite=[B('9.23.17.1.(1)')],
                   should_cite=[S('9.23.13.1.(2)', 'bracing for lateral loads normally relies on sheathing or panel-type finishes')],
                   must_not_cite=[],
                   section_c=['9.23.17.1.(1)'],
                   engineering_required='depends',
                   engineering_reason='Depends on whether lateral bracing is engineered; Part 4 design must be done by a registered professional.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.2.(1)')],
                   intake_action='proceed_conditionally')),
    # ---------------------------------------------------------------- cladding
    dict(id='dev-009', applicant_type='manufacturer', topic='cladding', code_part=9, jurisdiction='unspecified',
         seed_provision='9.27.2.2.(5)',
         description=("We manufacture an insulated metal panel with factory-sealed joints. It's a face-sealed system: no drainage cavity "
                      "behind it. We'd like to sell it for houses across Alberta, including places that get a lot of rain and snowmelt. "
                      "Some inspectors say they need a gap behind the cladding. Can we get a general acceptance?"),
         known_facts=['insulated metal panel', 'face-sealed, no drained cavity', 'intended for houses across Alberta'],
         missing_info=[{'field': 'climate data for the target locations (degree-days, moisture index)', 'why': 'whether a capillary break is required depends on location', 'priority': 'administrative'},
                       {'field': 'test or field evidence that omitting the capillary break does not harm the assembly', 'why': 'Section D evidence', 'priority': 'administrative'}],
         gold=dict(departure='Face-sealed cladding without a capillary break where the climate requires one.',
                   must_cite=[B('9.27.2.2.(5)')],
                   should_cite=[S('9.27.2.2.(6)', 'conditions under which the capillary break may be omitted'),
                                S('9.27.2.2.(1)', 'what counts as a capillary break')],
                   must_not_cite=[],
                   section_c=['9.27.2.2.(5)'],
                   engineering_required='depends',
                   engineering_reason='Product request without a building; professional involvement depends on the buildings it is used on.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(3)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-010', applicant_type='owner', topic='cladding', code_part=9, jurisdiction='Calgary',
         seed_provision='9.10.15.5.(2)',
         description=("I'm re-siding my house myself. The east wall is only half a metre from the fence on the property line, with my "
                      "neighbour's house beyond it. I want to use vinyl siding on that wall to match the rest. The city says that wall "
                      "needs metal or noncombustible siding. Can I get permission for vinyl?"),
         known_facts=['owner-occupied house', 'east wall 0.5 m from the property line', 'faces neighbour house', 'vinyl siding proposed'],
         missing_info=ADMIN + [{'field': 'current wall construction (gypsum sheathing, rating)', 'why': 'mitigation options', 'priority': 'administrative'}],
         gold=dict(departure='Combustible vinyl cladding on an exposing building face with a limiting distance under 0.6 m.',
                   must_cite=[B('9.10.15.5.(2)')],
                   should_cite=[],
                   must_not_cite=[N('9.10.15.5.(4)', 'as removing the cladding requirement', 'the wall faces a neighbouring house, not a garage or accessory building on the same property')],
                   section_c=['9.10.15.5.(2)'],
                   engineering_required='no',
                   engineering_reason='Single-family dwelling within the exemption.',
                   engineering_citations=[C('2.4.1.1.(1)')],
                   intake_action='proceed_conditionally')),
    # ---------------------------------------------------------------- engineered wall systems
    dict(id='dev-011', applicant_type='manufacturer', topic='engineered-walls', code_part=9, jurisdiction='unspecified',
         seed_provision='9.23.10.1.(1)',
         description=("We build factory panelized wall systems for houses. To save material we want to frame load-bearing exterior walls "
                      "of two-storey homes with 2x4 studs at 600 mm centres supporting the second floor and roof, with a structural "
                      "header system of our own design. Our in-house tables say it works. What does Alberta need from us?"),
         known_facts=['panelized wall system', '2x4 studs at 600 mm on centre, load-bearing', 'two-storey houses', 'proprietary tables'],
         missing_info=[{'field': 'who designed the system and whether it is engineered under Part 4', 'why': 'route choice', 'priority': 'administrative'}],
         gold=dict(departure='Stud size and spacing outside the prescriptive table for the loads carried.',
                   must_cite=[B('9.23.10.1.(1)')],
                   should_cite=[S('9.4.1.1.(1)', 'Part 9 structural members may instead be designed by engineering (acceptable-solution fork)')],
                   must_not_cite=[],
                   section_c=['9.23.10.1.(1)'],
                   engineering_required='yes',
                   engineering_reason='Departing from the span/stud tables needs structural design to Part 4, which must be done by a registered professional.',
                   engineering_citations=[C('2.4.1.2.(1)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-012', applicant_type='architect-engineer', topic='engineered-walls', code_part=9, jurisdiction='Cochrane',
         seed_provision='9.23.13.1.(2)',
         description=("Designer on a custom home built from structural insulated panels. We'd like to rely on the panels themselves for "
                      "resisting wind racking, using the panel supplier's shear values, with no separate braced wall panels laid out. "
                      "No engineer is on the project yet."),
         known_facts=['custom single-family home', 'structural insulated panels', 'supplier shear values for lateral resistance', 'no engineer engaged'],
         missing_info=ADMIN + [{'field': 'site wind and seismic values', 'why': 'whether the low-to-moderate force provisions apply', 'priority': 'administrative'}],
         gold=dict(departure='Lateral bracing provided by proprietary SIP shear values rather than the listed sheathing, panel cladding or engineered design.',
                   must_cite=[B('9.23.13.1.(2)')],
                   should_cite=[S('9.4.1.1.(1)', 'engineering design route for Part 9 structural members'),
                                S('9.23.13.1.(1)', 'applicability limits on wind and seismic forces')],
                   must_not_cite=[],
                   section_c=['9.23.13.1.(2)'],
                   engineering_required='yes',
                   engineering_reason='Lateral design outside the prescriptive options needs Part 4 design by a registered professional.',
                   engineering_citations=[C('2.4.1.2.(1)')],
                   intake_action='proceed_conditionally')),
    # ---------------------------------------------------------------- single exit
    dict(id='dev-013', applicant_type='architect-engineer', topic='single-exit', code_part=3, jurisdiction='Edmonton',
         seed_provision='3.4.2.1.(1)',
         description=("We're designing a four-storey, sprinklered wood-frame apartment with eight units per floor on a mid-block lot. "
                      "To make the floor plate work we want a single exit stair serving every floor, with a pressurized stair and "
                      "a short corridor. Each floor is about 600 m2."),
         known_facts=['four storeys', 'sprinklered', 'residential, eight units per floor', 'single exit stair proposed', 'about 600 m2 per floor'],
         missing_info=ADMIN + [{'field': 'travel distance and occupant load per floor', 'why': 'mitigation and comparison with the single-exit limits', 'priority': 'administrative'}],
         gold=dict(departure='Each floor area served by one exit instead of at least two, in a building above the single-exit height limit.',
                   must_cite=[B('3.4.2.1.(1)')],
                   should_cite=[S('3.4.2.1.(2)', 'single-exit allowance limited to buildings of not more than 2 storeys'),
                                S('3.3.4.4.(5)', 'dwelling unit doors opening into an exit stair')],
                   must_not_cite=[N('9.9.8.2.(2)', 'as the governing single-exit rule', 'a four-storey building is not within Part 9')],
                   section_c=['3.4.2.1.(1)'],
                   engineering_required='yes',
                   engineering_reason='Four-storey apartment is outside the exemption; authenticated architectural and engineering design is required.',
                   engineering_citations=[C('2.4.1.1.(3)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-014', applicant_type='homebuilder', topic='single-exit', code_part=9, jurisdiction='Grande Prairie',
         seed_provision='9.9.8.2.(1)',
         description=("We're putting up a three-storey walk-up with two apartments on each floor, six in total, about 280 m2 per floor. "
                      "We'd like just one interior stair from the top floor down, plus each upper unit gets a balcony. Is one stair "
                      "acceptable if we add something else?"),
         known_facts=['three storeys', 'six apartments', 'about 280 m2 per floor', 'one interior stair', 'balconies on upper units'],
         missing_info=ADMIN + [{'field': 'sprinklered or not', 'why': 'major mitigation and comparison input', 'priority': 'administrative'}],
         gold=dict(departure='Third storey served by a single exit; the single-exit allowance covers only 1- and 2-storey buildings.',
                   must_cite=[B('9.9.8.2.(1)')],
                   should_cite=[S('9.9.8.2.(2)', 'single-exit allowance and its storey limit'),
                                S('9.9.9.1.(3)', 'balcony provision for travel limits within dwelling units')],
                   must_not_cite=[],
                   section_c=['9.9.8.2.(1)'],
                   engineering_required='yes',
                   engineering_reason='Six dwelling units exceeds the four-unit exemption.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(3)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-015', applicant_type='owner', topic='single-exit', code_part=9, jurisdiction='St. Albert',
         seed_provision='9.9.9.1.(1)',
         description=("I'm finishing the attic of my two-storey house as a bedroom and office. The only way out of the attic is down to "
                      "the second floor and then down the main stair to the front door. The attic windows are small skylights. "
                      "I don't want to add a dormer. What are my options?"),
         known_facts=['two-storey single-family house', 'attic converted to a bedroom', 'two storeys of travel to the exit door', 'only small skylights'],
         missing_info=ADMIN + [{'field': 'skylight opening size and height above floor', 'why': 'whether an egress-window route is available', 'priority': 'administrative'}],
         gold=dict(departure='Travel of more than one storey from the attic level to an exit or egress door without the window or balcony alternatives.',
                   must_cite=[B('9.9.9.1.(1)')],
                   should_cite=[S('9.9.9.1.(2)', 'window alternative for units not above or below another suite')],
                   must_not_cite=[],
                   section_c=['9.9.9.1.(1)'],
                   engineering_required='no',
                   engineering_reason='Single-family dwelling within the exemption.',
                   engineering_citations=[C('2.4.1.1.(1)')],
                   intake_action='proceed_conditionally')),
    # ---------------------------------------------------------------- Part 3
    dict(id='dev-016', applicant_type='architect-engineer', topic='part3-fire-protection', code_part=3, jurisdiction='Calgary',
         seed_provision='3.1.5.5.(1)',
         description=("Five-storey sprinklered office building of noncombustible construction. The owner wants a charred-timber rainscreen "
                      "cladding on the street elevation. The supplier has a reaction-to-fire test from Europe but not the Canadian "
                      "full-scale wall test. Can the European test support an alternative solution?"),
         known_facts=['five storeys', 'sprinklered', 'office', 'noncombustible construction required', 'charred timber cladding', 'European test only'],
         missing_info=ADMIN,
         gold=dict(departure='Combustible cladding on a building required to be noncombustible, without the CAN/ULC-S134 test result.',
                   must_cite=[B('3.1.5.5.(1)')],
                   should_cite=[S('3.1.5.5.(2)', 'construction requirements where openings are limited by spatial separation')],
                   must_not_cite=[],
                   section_c=['3.1.5.5.(1)'],
                   engineering_required='yes',
                   engineering_reason='Five-storey office is outside the exemption.',
                   engineering_citations=[C('2.4.1.1.(3)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-017', applicant_type='contractor', topic='part3-fire-protection', code_part=3, jurisdiction='Edmonton',
         seed_provision='3.1.6.4.(1)',
         description=("Design-build contractor on an encapsulated mass timber residential building, eight storeys. In the top-floor suites "
                      "the developer wants the CLT ceilings left fully exposed, about 60% of each suite's ceiling, with a clear "
                      "intumescent coating. Walls would stay covered with gypsum."),
         known_facts=['eight storeys', 'encapsulated mass timber construction', 'residential', 'about 60% of suite ceilings exposed', 'intumescent coating proposed'],
         missing_info=ADMIN + [{'field': 'flame-spread rating of the coated CLT surface', 'why': 'compare with the exposed-ceiling exceptions', 'priority': 'administrative'}],
         gold=dict(departure='Exposed mass timber ceiling area far beyond the permitted percentage, encapsulation replaced by a coating.',
                   must_cite=[B('3.1.6.4.(1)')],
                   should_cite=[S('3.1.6.4.(6)', 'limits on exposed mass timber ceilings within a suite'),
                                S('3.1.6.4.(2)', 'permitted encapsulation materials')],
                   must_not_cite=[N('3.1.6.4.(6)', 'as permitting the proposal', '60% exceeds both limits in that sentence')],
                   section_c=['3.1.6.4.(1)'],
                   engineering_required='yes',
                   engineering_reason='Eight-storey building is outside the exemption.',
                   engineering_citations=[C('2.4.1.1.(3)')],
                   intake_action='proceed_conditionally')),
    # ---------------------------------------------------------------- Part 4
    dict(id='dev-018', applicant_type='architect-engineer', topic='part4-structural', code_part=4, jurisdiction='Leduc',
         seed_provision='4.1.6.2.(3)',
         description=("Structural engineer on a large single-storey warehouse in a suburban industrial park, with other buildings across "
                      "the street. We want to use a reduced wind exposure factor of 0.75 for the roof snow load because the site is "
                      "flat and windy. Normal importance category."),
         known_facts=['single-storey warehouse', 'suburban industrial park', 'neighbouring buildings', 'wind exposure factor 0.75 proposed', 'normal importance'],
         missing_info=ADMIN,
         gold=dict(departure='Reduced wind exposure factor applied outside a rural, fully exposed site.',
                   must_cite=[B('4.1.6.2.(3)'), B('4.1.6.2.(4)')],
                   should_cite=[S('4.1.6.2.(1)', 'snow load formula')],
                   must_not_cite=[],
                   section_c=['4.1.6.2.(3)', '4.1.6.2.(4)'],
                   engineering_required='yes',
                   engineering_reason='Part 4 structural design must be done by a registered professional.',
                   engineering_citations=[C('2.4.1.2.(1)')],
                   intake_action='proceed_conditionally')),
    dict(id='dev-019', applicant_type='manufacturer', topic='part4-structural', code_part=4, jurisdiction='Calgary',
         seed_provision='4.1.7.1.(6)',
         description=("We supply curtain wall and rainscreen cladding for a 20-storey tower. Our engineering team ran computational fluid "
                      "dynamics to get the cladding wind pressures, which come out lower than the code's static method. We'd like to "
                      "design the anchors to the CFD values."),
         known_facts=['cladding for a 20-storey tower', 'CFD-derived wind pressures', 'lower than the static procedure', 'anchor design to CFD values'],
         missing_info=ADMIN + [{'field': 'registered professional responsible for the cladding design', 'why': 'Division C qualifications', 'priority': 'administrative'}],
         gold=dict(departure='Specified wind loads on cladding determined by computational fluid dynamics.',
                   must_cite=[B('4.1.7.1.(6)')],
                   should_cite=[S('4.1.7.1.(5)', 'permitted procedures for cladding wind loads')],
                   must_not_cite=[],
                   section_c=['4.1.7.1.(6)'],
                   engineering_required='yes',
                   engineering_reason='Part 4 design by a registered professional.',
                   engineering_citations=[C('2.4.1.2.(1)'), C('2.4.1.1.(3)')],
                   intake_action='proceed_conditionally')),
    # ---------------------------------------------------------------- key facts deliberately missing (ask)
    dict(id='dev-020', applicant_type='contractor', topic='single-exit', code_part=None, jurisdiction='unspecified',
         seed_provision='3.4.2.1.(1)',
         description=("Our client wants a single staircase in their new building instead of two. What paperwork do we need for that?"),
         known_facts=['new building', 'one stair instead of two'],
         missing_info=[{'field': 'building height in storeys and floor area', 'why': 'decides Part 3 or Part 9 and whether a single exit is already permitted', 'priority': 'critical'},
                       {'field': 'occupancy (residential, office, etc.)', 'why': 'changes the exit rules', 'priority': 'critical'},
                       {'field': 'sprinklered or not', 'why': 'changes single-exit limits', 'priority': 'critical'},
                       {'field': 'municipality', 'why': 'authority having jurisdiction', 'priority': 'administrative'}],
         gold=dict(departure='',
                   must_cite=[],
                   should_cite=[S('3.4.2.1.(1)', 'branch: Part 3 building'), S('9.9.8.2.(1)', 'branch: Part 9 building')],
                   must_not_cite=[],
                   section_c=[],
                   engineering_required='depends',
                   engineering_reason='Depends on building size and occupancy, which are not given.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(3)')],
                   intake_action='ask')),
    dict(id='dev-021', applicant_type='homebuilder', topic='part9-spatial-separation', code_part=9, jurisdiction='Calgary',
         seed_provision='9.10.15.5.(9)',
         description=("The city flagged the eaves on one of our new houses as too close to the property line. We need a variance. "
                      "Can you start the form?"),
         known_facts=['new house', 'eaves flagged as too close to a property line'],
         missing_info=[{'field': 'limiting distance of the wall below the eave', 'why': 'at 0.45 m or less no soffit is allowed; above that the projection limit applies', 'priority': 'critical'},
                       {'field': 'distance from the soffit face to the property line', 'why': 'measures the departure', 'priority': 'critical'},
                       {'field': 'whether that side faces a street or lane', 'why': 'a public-way exception may apply', 'priority': 'critical'}] + ADMIN,
         gold=dict(departure='',
                   must_cite=[],
                   should_cite=[S('9.10.15.5.(8)', 'branch: limiting distance 0.45 m or less'),
                                S('9.10.15.5.(9)', 'branch: limiting distance more than 0.45 m'),
                                S('9.10.15.5.(10)', 'branch: faces a public way')],
                   must_not_cite=[],
                   section_c=[],
                   engineering_required='no',
                   engineering_reason='House within the exemption, unless the authority invokes special safety concerns.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(4)')],
                   intake_action='ask')),
    dict(id='dev-022', applicant_type='manufacturer', topic='envelope-insulation-sheathing', code_part=None, jurisdiction='unspecified',
         seed_provision='9.25.5.2.(1)',
         description=("We have a new exterior insulation board and want it approved for use in Alberta. What do you need from us?"),
         known_facts=['exterior insulation board', 'wants acceptance in Alberta'],
         missing_info=[{'field': 'material type, thickness and vapour permeance', 'why': 'decides which positioning and protection rules apply', 'priority': 'critical'},
                       {'field': 'intended wall assembly and building types', 'why': 'Part 9 or Part 3 rules and fire requirements differ', 'priority': 'critical'},
                       {'field': 'whether a specific project exists', 'why': 'a variance is project-specific; product-wide acceptance is a different route', 'priority': 'critical'},
                       {'field': 'existing evaluations or test reports', 'why': 'Section D evidence', 'priority': 'administrative'}],
         gold=dict(departure='',
                   must_cite=[],
                   should_cite=[S('9.25.5.1.(1)', 'branch: low-permeance sheet or panel material'),
                                S('9.25.5.2.(1)', 'branch: positioning of low-permeance materials'),
                                S('9.27.3.4.(1)', 'branch: insulating sheathing in lieu of membrane'),
                                S('9.10.17.10.(1)', 'branch: foamed plastic protection')],
                   must_not_cite=[],
                   section_c=[],
                   engineering_required='depends',
                   engineering_reason='No project or building is identified.',
                   engineering_citations=[C('2.4.1.1.(1)')],
                   intake_action='ask')),
    dict(id='dev-023', applicant_type='owner', topic='part9-spatial-separation', code_part=9, jurisdiction='Edmonton',
         seed_provision='9.10.15.5.(2)',
         description=("I want to turn my detached garage into a small suite for my mother. The garage is right by the back lane and "
                      "pretty close to the neighbour's fence. Do I need a variance?"),
         known_facts=['detached garage conversion to a suite', 'near the back lane and a side fence'],
         missing_info=[{'field': 'distance from each garage wall to the property line or lane centre line', 'why': 'sets the limiting distance and wall construction', 'priority': 'critical'},
                       {'field': 'window and door openings on each wall', 'why': 'unprotected openings limits', 'priority': 'critical'},
                       {'field': 'existing wall construction and cladding', 'why': 'whether the existing walls can be kept', 'priority': 'critical'}] + ADMIN,
         gold=dict(departure='',
                   must_cite=[],
                   should_cite=[S('9.10.15.4.(1)', 'branch: glazed openings in the suite walls'),
                                S('9.10.15.5.(2)', 'branch: limiting distance under 0.6 m'),
                                S('9.10.15.5.(3)', 'branch: limiting distance 0.6 m to 1.2 m')],
                   must_not_cite=[],
                   section_c=[],
                   engineering_required='no',
                   engineering_reason='Single-family property with a suite stays within the exemption; secondary suites are not counted as dwelling units.',
                   engineering_citations=[C('2.4.1.1.(1)'), C('2.4.1.1.(2)')],
                   intake_action='ask')),
    # ---------------------------------------------------------------- out of scope (redirect)
    dict(id='dev-024', applicant_type='contractor', topic='out-of-scope', code_part=None, jurisdiction='Calgary',
         seed_provision='7.1.2.1.(1)',
         description=("Plumbing contractor. In a basement bathroom we can't tie the new vent into the existing stack, so we want to use "
                      "an air admittance valve under the vanity instead of running a vent through the roof. Can you write up the "
                      "variance for the vent?"),
         known_facts=['basement bathroom', 'air admittance valve instead of a vent through the roof'],
         missing_info=[],
         gold=dict(departure='',
                   must_cite=[],
                   should_cite=[S('7.1.2.1.(1)', 'the building code defers plumbing systems to the Plumbing Code Regulation')],
                   must_not_cite=[],
                   section_c=[],
                   engineering_required='depends',
                   engineering_reason='Decided under the plumbing regime, not by this building-code tool.',
                   engineering_citations=[C('2.4.1.1.(1)')],
                   intake_action='redirect', out_of_scope=True, redirect_to='Plumbing Code Regulation / National Plumbing Code (plumbing permit and plumbing safety codes officer)')),
    dict(id='dev-025', applicant_type='owner', topic='out-of-scope', code_part=None, jurisdiction='Lethbridge',
         seed_provision='9.34.1.1.(1)',
         description=("I'm moving my electrical panel from the basement to the garage and want to run the new feeder through the attic "
                      "in aluminum cable. The electrician says it needs a variance. Can you prepare it?"),
         known_facts=['electrical panel relocation', 'aluminum feeder through the attic'],
         missing_info=[],
         gold=dict(departure='',
                   must_cite=[],
                   should_cite=[S('9.34.1.1.(1)', 'the building code defers electrical installations to the Electrical Code Regulation')],
                   must_not_cite=[],
                   section_c=[],
                   engineering_required='depends',
                   engineering_reason='Decided under the electrical regime (Canadian Electrical Code as adopted in Alberta), not by this tool.',
                   engineering_citations=[C('2.4.1.1.(1)')],
                   intake_action='redirect', out_of_scope=True, redirect_to='Electrical Code Regulation / Canadian Electrical Code (electrical permit and electrical safety codes officer)')),
]


def section_c_row(pid, db):
    r = lookup(pid, division='B', db_path=db)
    if r is None:
        raise SystemExit(f'unknown provision {pid}')
    st = r['attribution_status'] or {}
    pairs = sorted({a['bracket'] for a in r['attributions'] if not a['application_note']})
    cond = sorted({(a['bracket'], a['application_note']) for a in r['attributions'] if a['application_note']})
    return {'provision': r['id'], 'status': st.get('status'), 'root_provision': st.get('root_provision'),
            'pairs': pairs, 'conditional': [{'pair': p, 'when': w} for p, w in cond]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=DEFAULT_DB)
    a = ap.parse_args()
    out = ROOT / 'cases'
    out.mkdir(exist_ok=True)
    for spec in CASES:
        case = dict(spec)
        g = dict(case.pop('gold'))
        g['section_c'] = [section_c_row(p, a.db) for p in g['section_c']]
        g.setdefault('out_of_scope', False)
        g.setdefault('redirect_to', None)
        case['gold'] = g
        case['authoring'] = {'source': 'codedb', 'author': 'Batatis evaluation builder (Claude Opus 5.5)', 'date': DATE,
                             'notes': 'Written from the code database only; held-out judge set not consulted.'}
        (out / f"{case['id']}.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + '\n')
    print(f'wrote {len(CASES)} cases to {out}')


if __name__ == '__main__':
    main()
