import json, re, sqlite3, hashlib, sys
from pathlib import Path
DB = '/workspace/batatis/codedb-snapshot/codedb.sqlite'; R = Path('/workspace/batatis/research')
c = sqlite3.connect(DB); ERR = []
n = lambda s: re.sub(r'\s+', ' ', s).strip()
def prov(div, pid):
    r = c.execute('select id,title,article_title,pdf_page,text from provisions where division=? and id=?', (div, pid)).fetchone()
    if not r: ERR.append(f'missing Div {div} {pid}')
    return r
def G(article, sentences, quote, role='benchmark', div='B'):
    a = prov(div, article)
    out = dict(division=div, article=article, title=a[1] if a else None, sentences=[], role=role, pdf_page=a[3] if a else None)
    for s in sentences:
        p = prov(div, s)
        if p: out['sentences'].append(dict(provision=s, pdf_page=p[3]))
    if quote:
        txt = ' '.join(n(prov(div, s)[4]) for s in sentences if prov(div, s))
        if n(quote) not in txt: ERR.append(f'quote mismatch {article}: {quote}')
        out['quote'] = quote
    out['verification'] = f"codedb-checked, NBC(AE) 2023 2nd printing, PDF p.{out['pdf_page']}"
    return out
def X(article, reason, div='B'):
    a = prov(div, article)
    return dict(division=div, article=article, title=a[1] if a else None, pdf_page=a[3] if a else None, reason=reason)
LABEL = 'model-checked, not human-verified'
CASES = []
def case(id, role, description, known_facts, gold, mnr, notes='', source='model-written plain-language applicant phrasing', verbatim_from=None):
    at = {'manufacturer': 'manufacturer', 'general_contractor': 'contractor', 'homebuilder': 'homebuilder'}[role]
    d = dict(id=id, role=role, applicant_type=at, description=description, known_facts=known_facts,
             gold_articles=gold, must_not_return=mnr,
             authoring=dict(source=source, label=LABEL, notes=notes), verification=LABEL)
    if verbatim_from: d['verbatim_from'] = verbatim_from
    if re.search(r'\b\d+\.\d+\.\d+', description): ERR.append(f'{id}: code number in description')
    ga = {g['article'] for g in gold}
    if ga & {m['article'] for m in mnr}: ERR.append(f'{id}: gold/distractor overlap')
    CASES.append(d)

OSBNAILS = X('9.29.9.3.', 'Observed PR #16 @579cd2c failure: nails for OSB/particleboard used as an INTERIOR finish; nothing to do with attaching exterior cladding.')
CLAD = G('9.27.5.1.', ['9.27.5.1.(1)', '9.27.5.1.(2)'], 'cladding shall be fastened to the framing members or furring members, or to blocking between the framing members')
FURR = G('9.27.5.3.', ['9.27.5.3.(1)', '9.27.5.3.(3)'], 'furring for the attachment of cladding shall be not less than 19 mm by 38 mm lumber when applied over sheathing', role='benchmark (acceptable alternative the applicant skipped)')
RIGID = G('9.23.17.3.', ['9.23.17.3.(1)'], 'Gypsum sheathing, rigid insulation and fibreboard shall not be used for the attachment of cladding materials', role='related')
_as = c.execute("select status, root_method from attribution_status where doc='NBC-AE' and provision_id='9.23.17.3.(1)'").fetchone()
RIGID_GOLD = dict(G('9.23.17.3.', ['9.23.17.3.(1)'], 'Gypsum sheathing, rigid insulation and fibreboard shall not be used for the attachment of cladding materials', role='gold (confirmed by Unc; pinned to Sentence 9.23.17.3.(1))'),
  pinned_sentence='9.23.17.3.(1)', confirmed_by='Unc', confirmation='Unc confirmed 9.23.17.3 as gold for idr-001 and idr-002 (Oct 20, 2026, relayed by the parent agent)',
  attribution_status=dict(status=_as[0] if _as else None, root_method=_as[1] if _as else None, note='codedb attribution_status is none for 9.23.17.3.(1): no objective or function is attributed, so a Section C row cannot be looked up for it'))
if not _as or _as[0] != 'none': ERR.append('9.23.17.3.(1) attribution_status changed')

# ---------------- manufacturer
case('idr-001', 'manufacturer', "We make a new insulated sheathing panel and want it approved in Alberta so builders can nail siding straight onto it. What do I need?",
 ['manufacturer', 'insulated sheathing panel', 'siding nailed straight onto the panel', 'wants Alberta-wide approval'],
 [CLAD, FURR, RIGID_GOLD],
 [OSBNAILS, X('9.29.9.2.', 'Thickness of OSB used as an interior finish; wrong face of the wall.'),
  X('9.27.10.1.', 'Material standard for OSB used AS cladding; here OSB is the substrate being replaced.'),
  X('9.23.15.2.', 'Subfloor panel standards; floors, not walls.')],
 notes="Unc's scripted typed phrasing for case A (demo script step 1). 9.23.17.3 is confirmed gold (confirmed by Unc), pinned to Sentence 9.23.17.3.(1), p.990; codedb attribution_status is 'none' (no objective or function).",
 source='verbatim: /workspace/unc-demo-cases/a-manufacturer-nailbase-sheathing/README.md line 24 (demo script step 1, typed text)',
 verbatim_from=dict(file='/workspace/unc-demo-cases/a-manufacturer-nailbase-sheathing/README.md', line=24, kind='scripted demo input; the text Mira actually typed in session 5 is not recorded'))
case('idr-002', 'manufacturer', "Our panel is selling in two other provinces *(claim not verified)*. We want **approval to sell it across Alberta** and a first **pilot house** in Edmonton this spring. Builders love it because vinyl siding nails **straight into the facer**, so there's no OSB and no strapping.",
 ['panel replaces OSB', 'vinyl siding nailed into the panel facer', 'no strapping (furring)', 'pilot house in Edmonton', 'wants Alberta-wide approval'],
 [CLAD, FURR, RIGID_GOLD],
 [OSBNAILS, X('9.29.9.2.', 'Interior OSB finish thickness; "no OSB" refers to wall sheathing, not interior finish.'),
  X('9.27.12.1.', 'Vinyl siding material standard; the question is how it is attached, not the siding product.')],
 notes="Verbatim line from the case A persona brief, markdown kept as written. 9.23.17.3 is confirmed gold (confirmed by Unc), pinned to Sentence 9.23.17.3.(1), p.990; codedb attribution_status is 'none' (no objective or function).",
 source='verbatim: /workspace/unc-demo-cases/a-manufacturer-nailbase-sheathing/input/project-brief.md line 7',
 verbatim_from=dict(file='/workspace/unc-demo-cases/a-manufacturer-nailbase-sheathing/input/project-brief.md', line=7, kind='persona brief text'))
case('idr-003', 'manufacturer', "We make a recycled-plastic rainscreen strapping strip. Builders screw it through the foam board into the studs at 24 inches on centre and hang fibre-cement siding on it. Some framers want to space it at 32 inches to save material. Is our strip OK in place of wood strapping, and does the spacing matter?",
 ['manufacturer of plastic rainscreen strapping', 'installed over foam board, screwed into studs', '24 in. (610 mm) and proposed 32 in. (813 mm) spacing', 'fibre-cement siding'],
 [G('9.27.5.3.', ['9.27.5.3.(1)', '9.27.5.3.(3)'], 'spaced not more than 600 mm o.c.', role='benchmark (pinned: 9.27.5.3.(3)(b) spacing; (1) lumber size)'),
  G('9.27.5.1.', ['9.27.5.1.(1)'], 'cladding shall be fastened to the framing members or furring members')],
 [OSBNAILS, X('9.27.5.2.', 'Blocking between framing members; the product is furring over sheathing, not blocking.'),
  X('9.23.3.5.', 'Fastening of sheathing to framing; the strip is furring for cladding.')],
 notes="Furring case matching the parent's description of case A (pinned to 9.27.5.3.(3)(b)). Note that 24 in. is 610 mm, which is already over 600 mm.")
case('idr-004', 'manufacturer', "We sell stainless ring-shank nails for vinyl siding. On houses with 1-1/2 inch foam outside the OSB, our 2-inch nail only gets about 3/4 inch into the studs. Contractors ask whether that's enough or if they need a longer nail.",
 ['nail manufacturer', 'vinyl siding', '38 mm exterior foam over OSB', 'about 19 mm penetration into studs'],
 [G('9.27.5.7.', ['9.27.5.7.(2)'], 'Fasteners for vinyl cladding, insulated vinyl cladding and polypropylene cladding shall penetrate through the nail-holding base or not less than 32 mm into the framing'),
  G('9.27.5.4.', ['9.27.5.4.(1)'], 'Nail or staple size and spacing for the attachment of cladding and trim', role='related'),
  G('9.27.5.5.', ['9.27.5.5.(1)'], 'shall be corrosion-resistant and shall be compatible with the cladding material', role='related')],
 [OSBNAILS, X('9.23.3.4.', 'Nailing of framing members to each other, not cladding fasteners.'),
  X('9.23.3.5.', 'Fasteners for sheathing or subflooring, not cladding.')])
case('idr-005', 'manufacturer', "Our synthetic housewrap is sold all over the US and tested to ASTM standards, but we've never had it tested to a Canadian standard. Can Alberta builders use it behind siding?",
 ['housewrap manufacturer', 'tested to US ASTM standards only', 'used behind siding'],
 [G('9.27.3.2.', ['9.27.3.2.(1)'], 'Sheathing membranes shall conform to the performance requirements of CAN/CGSB-51.32-M'),
  G('9.27.3.3.', ['9.27.3.3.(1)'], 'at least one layer of sheathing membrane shall be applied beneath cladding', role='scope')],
 [OSBNAILS, X('9.25.4.1.', 'Vapour barrier on the warm side; a housewrap is not the vapour barrier.'),
  X('9.20.13.1.', 'Flashing materials for masonry; housewrap is not flashing.')])
case('idr-006', 'manufacturer', "We make a hemp-fibre batt insulation for walls and attics. There's no Canadian product standard written for hemp. What do inspectors in Alberta need from us before builders can use it?",
 ['insulation manufacturer', 'hemp-fibre batts', 'no Canadian product standard'],
 [G('9.25.2.2.', ['9.25.2.2.(1)'], 'thermal insulation shall conform to the requirements of')],
 [OSBNAILS, X('9.25.2.3.', 'How insulation is installed, not which material standard it meets.'),
  X('9.36.2.6.', 'Required thermal values for assemblies; does not qualify an insulation material.'),
  X('9.10.17.10.', 'Protection of foamed plastics; hemp batts are not foamed plastic.')])
case('idr-007', 'manufacturer', "We make a frameless glass railing for decks and balconies. Homeowners like the clean look at 36 inches high. Can we sell it at that height for house decks that are about 8 feet above the yard?",
 ['glass railing manufacturer', '36 in. (914 mm) guard height', 'house decks about 8 ft (2.4 m) above ground'],
 [G('9.8.8.3.', ['9.8.8.3.(1)', '9.8.8.3.(3)'], 'all guards shall be not less than 1 070 mm high'),
  G('9.8.8.2.', ['9.8.8.2.(1)'], 'guards shall be designed to resist the specified loads prescribed in Table 9.8.8.2.', role='related')],
 [OSBNAILS, X('9.8.7.4.', 'Handrail height, not guard height.'),
  X('9.8.8.6.', 'Anti-climbing rule applies only above 4.2 m; the deck is about 2.4 m.')])
case('idr-008', 'manufacturer', "We make insulating concrete form blocks for basements. Our new thin-core block pours a 140 mm concrete core to save concrete. Can builders use it for basement walls on houses?",
 ['ICF manufacturer', '140 mm concrete core', 'house basement walls'],
 [G('9.15.4.2.', ['9.15.4.2.(1)', '9.15.4.2.(2)'], 'shall be not less than the greater of'),
  G('9.15.4.1.', ['9.15.4.1.(1)'], 'Flat wall insulating concrete form units shall conform to CAN/ULC-S717.1', role='related')],
 [OSBNAILS, X('9.15.3.4.', 'Footing widths, not foundation wall thickness.'),
  X('9.27.5.1.', 'Its Sentence (5) covers screwing cladding to ICF web strips; the question is the wall core.')])
# ---------------- general contractor
case('idr-009', 'general_contractor', "On a duplex we're finishing, the siding sub nailed the vinyl siding straight into the rigid foam boards on two walls instead of into strapping or studs. The inspector flagged it. Can we leave it with some kind of approval?",
 ['general contractor', 'vinyl siding nailed into rigid foam boards', 'no strapping, not into studs', 'flagged by inspector'],
 [G('9.27.5.1.', ['9.27.5.1.(1)'], 'cladding shall be fastened to the framing members or furring members, or to blocking between the framing members'),
  G('9.23.17.3.', ['9.23.17.3.(1)'], 'rigid insulation and fibreboard shall not be used for the attachment of cladding materials')],
 [OSBNAILS, X('9.27.12.1.', 'Vinyl siding material standard; the defect is attachment.'),
  X('9.25.2.3.', 'Installation of the insulation itself.')])
case('idr-010', 'general_contractor', "Our framer put up 1x3 strapping over the sheathing at about 32 inches apart so the cedar siding has a rain gap. Is that spacing a problem?",
 ['general contractor', '1x3 (19 x 64 mm) strapping over sheathing', 'about 32 in. (813 mm) spacing', 'cedar siding'],
 [G('9.27.5.3.', ['9.27.5.3.(3)'], 'spaced not more than 600 mm o.c.')],
 [OSBNAILS, X('9.27.5.2.', 'Blocking between framing members, not furring strips.'),
  X('9.27.6.1.', 'Lumber siding material; spacing of the strapping is the question.')])
case('idr-011', 'general_contractor', "Crew nailed the OSB wall sheathing at 12 inches on the panel edges and 24 in the field because the nail gun was set wrong. What's the actual requirement and do we have to renail?",
 ['general contractor', 'OSB wall sheathing', 'nails at 12 in. (305 mm) on edges, 24 in. (610 mm) in the field'],
 [G('9.23.3.5.', ['9.23.3.5.(1)'], 'fastening of sheathing and subflooring shall conform to Table 9.23.3.5.-A')],
 [OSBNAILS, X('9.27.5.4.', 'Nails for cladding and trim, not sheathing.'),
  X('9.23.3.4.', 'Nailing framing members together.')],
 notes='Closest neighbour of the observed failure: 9.29.9.3.(2) cross-references 9.23.3.5.(2) only when OSB is an interior finish providing bracing.')
case('idr-012', 'general_contractor', "Building a small two-storey office. The stair between floors came out with 210 mm risers because the floor got thicker. Do we have to rebuild it?",
 ['general contractor', 'two-storey office', 'stair risers 210 mm'],
 [G('9.8.4.1.', ['9.8.4.1.(1)'], 'the rise, which is measured as the vertical nosing-to-nosing distance, shall comply with Table 9.8.4.1.')],
 [OSBNAILS, X('9.8.4.3.', 'Tapered treads; this stair is straight.'),
  X('9.8.7.4.', 'Handrail height, not riser height.')])
case('idr-013', 'general_contractor', "We want to use 190 mm plain concrete block for a basement wall with about 2.4 m of backfill against it, no rebar. Is that thick enough?",
 ['general contractor', 'unreinforced 190 mm concrete block basement wall', 'about 2.4 m backfill'],
 [G('9.15.4.2.', ['9.15.4.2.(1)'], 'the thickness of foundation walls made of unreinforced concrete block')],
 [OSBNAILS, X('9.15.3.4.', 'Footing widths, not wall thickness.'),
  X('9.15.4.1.', 'ICF material standard; the wall is concrete block.')])
case('idr-014', 'general_contractor', "On a three-storey walk-up, the architect drew horizontal cable railings on the top-floor balconies, about 5 m above the ground. The owner likes the look. Any issue?",
 ['general contractor', 'three-storey walk-up', 'horizontal cable guards', 'balconies about 5 m above grade'],
 [G('9.8.8.6.', ['9.8.8.6.(1)'], 'shall be designed so that no member, attachment or opening located between 140 mm and 900 mm above the level protected by the guard facilitates climbing'),
  G('9.8.8.5.', ['9.8.8.5.(1)'], 'prevents the passage of a spherical object having a diameter of 100 mm', role='related')],
 [OSBNAILS, X('9.8.8.3.', 'Guard height is not in question.'),
  X('9.8.7.4.', 'Handrail height, not guard design.')])
# ---------------- homebuilder
case('idr-015', 'homebuilder', "We're putting 2 inches of foil-faced foam board on the outside of our houses with taped seams. Can we skip the housewrap behind the vinyl siding?",
 ['homebuilder', '50 mm foil-faced rigid foam outside', 'taped seams', 'vinyl siding'],
 [G('9.27.3.4.', ['9.27.3.4.(1)', '9.27.3.4.(2)'], 'a separate sheathing membrane is not required'),
  G('9.27.3.3.', ['9.27.3.3.(1)'], 'at least one layer of sheathing membrane shall be applied beneath cladding', role='scope')],
 [OSBNAILS, X('9.25.5.1.', 'Low-permeance placement of the foam; a different question from the sheathing membrane.'),
  X('9.25.4.1.', 'Interior vapour barrier.')])
case('idr-016', 'homebuilder', "Our back-deck stairs have 8-inch risers and 9-inch treads to fit the yard. Will that pass?",
 ['homebuilder', 'exterior deck stair', 'risers 8 in. (203 mm)', 'treads 9 in. (229 mm)'],
 [G('9.8.4.1.', ['9.8.4.1.(1)'], 'shall comply with Table 9.8.4.1.'),
  G('9.8.4.2.', ['9.8.4.2.(1)'], 'the run shall comply with Table 9.8.4.2.')],
 [OSBNAILS, X('9.8.4.3.', 'Tapered treads; the stair is straight.'),
  X('9.8.8.3.', 'Guard height, not stair geometry.')])
case('idr-017', 'homebuilder', "For a modern look we want horizontal wood slats on the open side of the basement stairs, with about 4-1/2 inch gaps between slats. Is that allowed in a house?",
 ['homebuilder', 'interior stair guard of horizontal slats', 'gaps about 4.5 in. (114 mm)', 'house'],
 [G('9.8.8.5.', ['9.8.8.5.(1)'], 'prevents the passage of a spherical object having a diameter of 100 mm')],
 [OSBNAILS, X('9.8.8.6.', 'Anti-climbing applies only where the guard protects a level more than 4.2 m above the adjacent level.'),
  X('9.8.8.3.', 'Guard height is not in question.')])
case('idr-018', 'homebuilder', "To save money we only insulate the basement walls down to about 2 feet below grade. Is full-height basement insulation actually required?",
 ['homebuilder', 'basement wall insulation to about 600 mm below grade'],
 [G('9.25.2.3.', ['9.25.2.3.(4)'], 'Insulation shall be installed over the full height of foundation walls enclosing a basement or heated crawl space')],
 [OSBNAILS, X('9.36.2.6.', 'Thermal values for above-ground assemblies, not basement coverage.'),
  X('9.25.2.2.', 'Insulation material standards.')])
case('idr-019', 'homebuilder', "The lot is silty and the geotech says the water table is about 300 mm below where the footings will sit. We sized the strip footings from the normal house table at 400 mm wide. OK?",
 ['homebuilder', 'silt soil', 'water table about 300 mm below footing base', '400 mm strip footings from table'],
 [G('9.15.3.4.', ['9.15.3.4.(3)'], 'the footing width for walls shall be not less than twice the width required')],
 [OSBNAILS, X('9.15.4.2.', 'Foundation wall thickness, not footing width.'),
  X('9.13.2.1.', 'Dampproofing; the question is bearing width.')])
case('idr-020', 'homebuilder', "We're switching to 3/8-inch OSB wall sheathing to cut costs and nailing vertical vinyl siding straight to it, no strapping. Any problem?",
 ['homebuilder', '9.5 mm (3/8 in.) OSB wall sheathing', 'vertical vinyl siding nailed to sheathing', 'no strapping'],
 [G('9.27.5.1.', ['9.27.5.1.(2)'], 'vertically applied vinyl siding'),
  G('9.23.17.2.', ['9.23.17.2.(1)'], 'it shall conform to either Table 9.23.17.2.-A or 9.23.17.2.-B', role='related')],
 [OSBNAILS, X('9.29.9.2.', 'Thickness of OSB as an INTERIOR finish; the classic near-miss for OSB thickness.'),
  X('9.27.10.1.', 'OSB used as cladding; here OSB is sheathing behind vinyl.')])
case('idr-021', 'general_contractor', "Fibre-cement lap siding went up with regular bright (uncoated) nails because the coated ones were back-ordered. Do we need to pull it?",
 ['general contractor', 'fibre-cement lap siding', 'uncoated steel nails'],
 [G('9.27.5.5.', ['9.27.5.5.(1)'], 'Nails or staples for the attachment of cladding and wood trim shall be corrosion-resistant')],
 [OSBNAILS, X('9.20.16.1.', 'Corrosion resistance of masonry connectors, not cladding nails.'),
  X('9.23.3.4.', 'Framing nails.')])

# ---------------- Part 3 (non-Part 9) GC cases, Carlos style (added Oct 20, 2026 ~2:45 PM MDT)
P3 = "Part 3 case: the building is outside Part 9 scope (Div A 1.3.3.2./1.3.3.3.); Part 9 analogues are listed as must_not_return. Gold names the provision at issue only; it is not a compliance verdict."
case('idr-022', 'general_contractor', "We're the GC on a six-storey wood-frame apartment, all rental units, sprinklered throughout. The developer now wants to add a seventh floor of units on top, still wood. Is that a problem, or can we just keep framing?",
 ['general contractor', 'residential apartment, sprinklered', 'wood frame (combustible)', 'six storeys, proposed seventh'],
 [G('3.2.2.51.', ['3.2.2.51.(1)'], 'b) it is not more than 6 storeys in building height'),
  G('3.2.2.48.', ['3.2.2.48.(1)'], 'b) it is not more than 12 storeys in building height', role='related (taller Group C Article; its construction requirements are in Sentence (2))')],
 [OSBNAILS, X('9.10.8.1.', 'Part 9 floor and roof fire-resistance ratings; a 6-7 storey apartment is outside Part 9.'),
  X('9.10.4.1.', 'Part 9 rule on mezzanines not counted as storeys; tempting on "storeys" but Part 9 only.')], notes=P3)
case('idr-023', 'general_contractor', "Four storeys: shops on the street level, apartments on the three floors above, sprinklered. The drawings show the floor over the shops as the same 1-hour floor as every other level. The owner asks if that's enough between the stores and the apartments.",
 ['general contractor', 'mixed use: retail at grade, residential above', 'four storeys, sprinklered', 'floor over retail drawn at 1 h'],
 [G('3.1.3.1.', ['3.1.3.1.(1)'], 'major occupancies shall be separated from adjoining major occupancies by fire separations having fire-resistance ratings conforming to Table 3.1.3.1.'),
  G('3.2.2.7.', ['3.2.2.7.(1)'], 'in a building in which one major occupancy is located entirely above another major occupancy', role='related (superimposed occupancies)')],
 [OSBNAILS, X('9.10.9.13.', 'Part 9 separation of residential occupancies from other occupancies (1 h); the classic Part 9 near-miss for a 4-storey Part 3 building.'),
  X('9.10.8.1.', 'Part 9 floor ratings; not the occupancy-separation rule.')], notes=P3)
case('idr-024', 'general_contractor', "Fit-out of a banquet hall on the second floor of an existing two-storey building, about 400 seats. The owner wants only one exit stair from the hall so the kitchen can go where the second stair is drawn. Can we do that?",
 ['general contractor', 'assembly use: banquet hall about 400 seats', 'second floor of a two-storey building', 'one exit stair proposed'],
 [G('3.4.2.1.', ['3.4.2.1.(1)', '3.4.2.1.(2)'], 'every floor area intended for occupancy shall be served by at least 2 exits'),
  G('3.3.1.5.', ['3.3.1.5.(1)'], 'b) intended for an occupant load more than 60', role='related (two egress doorways from the room)')],
 [OSBNAILS, X('9.9.8.2.', 'Part 9 number of required exits; assembly occupancies are outside Part 9 (Div A 1.3.3.2.(1)(b)).'),
  X('9.9.9.1.', 'Part 9 travel limit within dwelling units; wrong occupancy and Part.')], notes=P3)
case('idr-025', 'general_contractor', "Two-storey office building, about 1,400 m2 on each floor, wood frame, no sprinklers. The floor between the levels is drawn as plain joists and drywall with no rating. The owner says it's just an office so it doesn't need anything special.",
 ['general contractor', 'business and personal services (office)', 'two storeys, about 1,400 m2 per floor', 'combustible, not sprinklered', 'floor assembly drawn unrated'],
 [G('3.2.2.64.', ['3.2.2.64.(2)'], 'floor assemblies shall be fire separations and, if of combustible construction, shall have a fire-resistance rating not less than 45 min'),
  G('3.2.2.62.', ['3.2.2.62.(2)'], 'floor assemblies shall be fire separations and, if of combustible construction, shall have a fire-resistance rating not less than 45 min', role='benchmark (alternative Group D Article; which one applies depends on building area against Tables 3.2.2.62. and 3.2.2.64.)')],
 [OSBNAILS, X('9.10.8.1.', 'Part 9 floor ratings; 1,400 m2 exceeds the 600 m2 Part 9 limit (Div A 1.3.3.3.(1)).'),
  X('9.10.18.2.', 'Part 9 fire alarm requirement; not the floor-rating question and the wrong Part.')], notes=P3)
case('idr-026', 'general_contractor', "Six-storey hotel. The electrician ran bundles of cable through the rated corridor walls and the drywallers packed the holes with mineral wool and regular caulk. There are also plastic electrical boxes back-to-back in the suite walls. The inspector wants a listed system for each one. Can we leave them?",
 ['general contractor', 'hotel (residential), six storeys', 'cable bundles through rated corridor walls', 'mineral wool and non-listed caulk', 'combustible outlet boxes in rated walls'],
 [G('3.1.9.1.', ['3.1.9.1.(1)'], 'has an F rating not less than the required fire-resistance rating of the fire separation'),
  G('3.1.9.2.', ['3.1.9.2.(1)'], 'electrical wires and cables, and other similar service equipment are permitted to penetrate a fire separation', role='benchmark (service penetrations)'),
  G('3.1.9.3.', ['3.1.9.3.(2)'], 'Combustible outlet boxes are permitted to penetrate the membrane of an assembly required to have a fire-resistance rating, provided they are sealed at the penetration by a firestop', role='benchmark (outlet boxes)')],
 [OSBNAILS, X('9.10.9.6.', 'Part 9 general penetration rule (allows "sealed to maintain the integrity"); a 6-storey hotel is Part 3.'),
  X('9.10.9.7.', 'Part 9 piping penetrations; these are cables and boxes, and the wrong Part.')], notes=P3)

if ERR:
    print('\n'.join(ERR)); sys.exit(1)
from collections import Counter
meta = dict(title='Identify regression set: plain-language applicant descriptions (manufacturer / general contractor / homebuilder)',
  generated='2026-10-20 (America/Edmonton)', label=LABEL,
  trigger='Unc session 5 (cold manufacturer run, PR #16 @579cd2c): identify missed case A provisions 9.27.5.1/9.27.5.3 and returned 9.29.9.3.(2).',
  codedb_snapshot=dict(path=DB, sha256=hashlib.sha256(open(DB, 'rb').read()).hexdigest(), edition='NBC(AE) 2023 2nd printing'),
  scoring_note='Score at Article level (as engine/identify/benchmark.py _article()). gold_articles uses the identify_gold shape {division, provision->article, role}; sentences[] give the pinpoints. must_not_return: any of these in the top-k is a regression.',
  quote_check='every quote is an exact substring of the codedb sentence text (whitespace-normalised)',
  counts=dict(Counter(x['role'] for x in CASES)), total=len(CASES))
json.dump(dict(meta=meta, cases=CASES), open(R/'identify-regression.json', 'w'), ensure_ascii=False, indent=2)
print('OK', len(CASES), meta['counts'])
