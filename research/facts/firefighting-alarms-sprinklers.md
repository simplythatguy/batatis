---
topic: firefighting-alarms-sprinklers
scope: Active fire protection and firefighter interface under NBC(AE) 2023 Division B 3.2.4 to 3.2.7 and Part 9 9.10.18 to 9.10.20, with NFC(AE) 2023 inspection, testing and maintenance (ITM) and fire safety plan provisions, and the alternative-solution route for departing from them.
sources_checked:
  - NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2 (codedb lookup, notes, definitions, attribution and intent tables; codesearch page text)
  - NFC-AE-2023-2nd-printing (codesearch page text only, because codedb does not build the NFC)
  - NBC-2020-Intent-Statements (explanatory only; codedb intent rows)
  - Edmonton-Alt-Solutions-Emergency-Services (Guideline COE-IM-GUIDE-0040 v01, 2025-04-15)
  - edmonton-policy-b19-04-small-building-access (Small Building Access Policy B19-04, 18 May 2023)
  - standata-nbc2023-variance-23-bcv-004 (May 2024)
  - standata-nbc2023-interpretation-23-bci-030 (March 2025)
  - standata-nbc2023-variance-23-bcv-014 (March 2025)
  - STANDATA 14-BCV-018 and 14-BCV-018r1 (2014 edition) and 19-BCV-013 (2019 edition), historical precedents for sprinkler-protected glazing, first page text
  - CWC-Alternative-Solutions-Guide (pages 11, 15, 16, 17, 21, 22)
  - Division A, Sentence 1.3.3.2.(1) (PDF p.39-40), and Division C, Sentences 2.2.1.2.(1) (PDF p.729), 2.3.1.1.(1) to (4) (PDF p.739), 2.4.1.1.(1) to (4) (PDF p.739-740), 2.4.2.1.(1) (PDF p.741) and 2.4.2.2.(1) (PDF p.741), checked through codedb
last_verified: 2026-10-19
---
# Firefighting, alarms and sprinklers

## Progress
- Skeleton saved (2026-10-19). Done: read PREAMBLE, WAVE2-BRIEF, the firefighting-alarms-sprinklers topic section, CONTRACTS.md (the fact-sheet template lives there, not in WAVE2-BRIEF), WAVES.md, README-challenge.md, routes.md, t3-workflow SKILL.md, the matt research and pstack unslop methods, ~/.codex/AGENTS.md. Read the validator source (codedb/validator.py) for the citation grammar. Mapped the structure: Div B 3.2.4 (fire alarm, 23 articles), 3.2.5 (access routes, water supply, standpipes, sprinklers, fire pumps), 3.2.6 (high buildings), 3.2.7 (emergency lighting and power); Part 9 9.10.18 (alarm and detection), 9.10.19 (smoke alarms), 9.10.20 (firefighting).
- Research pass complete (2026-10-19). Verified through codedb: the Part 3 fire alarm, access, water, standpipe, sprinkler, high building and emergency power subsections, the Part 9 alarm and firefighting subsections, their attribution pairs, intent entries and notes. Verified through codesearch: the NFC inspection, testing and maintenance Part and the fire safety plan provisions.
- Status: all sections are written in template order. The validator reports six errors, all unsupported_document for NFC citations in the body, because codedb does not build the NFC. Those six citations were checked by hand with codesearch against their NFC PDF pages. Bounded web checks on 2026-10-19 did not confirm STANDATA 23-BCV-004 or Edmonton policy B19-04, and both are open questions.

## Plain-language summary
Division B of the National Building Code, Alberta Edition 2023, sets the firefighting features that many buildings must have. For Part 3 buildings, these are a fire alarm system, access routes for fire trucks, a water supply, standpipes, automatic sprinklers, fire pumps, elevators for firefighters in high buildings, and emergency power for the fire alarm system and emergency lights. Smaller Part 9 buildings have a shorter list in Subsections 9.10.18 to 9.10.20.

Sprinklers change the rest of the list. A sprinklered building does not need the water supply volume in Article 3.2.5.7, and a low building of a certain size can skip its standpipe if it is sprinklered throughout. Sprinklers also add requirements, such as a fire alarm system under Article 3.2.4.1 and electrical supervision of the sprinkler valves.

Each requirement is linked to functional statements and objectives. For example, F12 means facilitating emergency response, and OS1.5 means that people are delayed in moving to a safe place during a fire. An alternative solution that departs from one of these provisions must show equal or better performance against the statements attributed to it. The code notes that the local fire department should be consulted on access routes. Edmonton's guideline gives four screening questions for deciding when an emergency-services review is needed.

Sprinklers, alarms and firefighting equipment also need ongoing inspection, testing and maintenance under the National Fire Code, Alberta Edition. A design that uses a system the fire code does not regulate needs its own ITM procedures.

Two local documents shape practice. Edmonton's Small Building Access Policy B19-04 sets access standards for small buildings. STANDATA 23-BCV-004 allows sprinkler-protected glazing in some fire-rated walls when its conditions are met.

This sheet explains the code text and the alternative-solution route. It does not judge whether a design is adequate. A registered professional and the local fire department make that judgement.

## When this topic applies
Signals that should trigger this topic:

- A building over 3 storeys in building height or over 600 m² in building area, for a Group C, D, E, or F Division 2 or 3 occupancy. Part 3 applies to that building under NBC(AE) 2023 p2, Div A, Sentence 1.3.3.2.(1) [PDF p.39-40]. Access routes then follow from NBC(AE) 2023 p2, Div B, Sentence 3.2.5.4.(1) [PDF p.228].
- A standpipe question. NBC(AE) 2023 p2, Div B, Sentence 3.2.5.8.(1) [PDF p.231] requires a standpipe for a building more than 3 storeys high or more than 14 m high, and for a smaller building whose area exceeds the limit in that sentence's table. The sprinkler exception applies only to the third case.
- An automatic sprinkler system. NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(1) [PDF p.233] requires NFPA 13 design. NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(2) [PDF p.233] and Sentence 3.2.5.12.(3) [PDF p.233] allow NFPA 13R or NFPA 13D for certain residential buildings.
- A fire alarm question. NBC(AE) 2023 p2, Div B, Sentence 3.2.4.1.(1) [PDF p.218] requires a fire alarm system in a sprinklered building. NBC(AE) 2023 p2, Div B, Sentence 3.2.4.1.(4) [PDF p.218] requires one in a building that is not sprinklered throughout when it has a listed feature, such as more than 3 storeys or an occupant load over 300.
- A fire pump or a private firefighting water supply. NBC(AE) 2023 p2, Div B, Sentence 3.2.5.18.(1) [PDF p.235] covers fire pumps. NBC(AE) 2023 p2, Div B, Sentence 3.2.5.7.(1) [PDF p.229] sets the water supply.
- A high building. NBC(AE) 2023 p2, Div B, Sentence 3.2.6.1.(1) [PDF p.236] applies Subsection 3.2.6 to certain Group A, D, E, and F buildings above 36 m, or above 18 m with a high occupant load measured against the exit stair width. It also reaches some Group B and Group C buildings above 18 m.
- Emergency power for a fire alarm system. NBC(AE) 2023 p2, Div B, Sentence 3.2.7.8.(1) [PDF p.241].
- A Part 9 house or small building. NBC(AE) 2023 p2, Div B, Sentence 9.10.20.3.(1) [PDF p.911] requires fire department access to each building. NBC(AE) 2023 p2, Div B, Sentence 9.10.20.1.(1) [PDF p.911] requires windows or access panels on the second and third storeys when they are not sprinklered. NBC(AE) 2023 p2, Div B, Sentence 9.10.18.2.(1) [PDF p.907-908] requires a fire alarm in a sprinklered building.
- Edmonton's Small Building Access Policy B19-04, which applies to Part 9 buildings and to one-storey Part 3 buildings up to 600 m² (source p.1).
- A sprinkler-protected glazing wall, under STANDATA 23-BCV-004 (source p.1 to p.3).

Near misses that belong to other topic slugs:

- Exit count, travel distance, dead-end corridors, and exit width belong to egress-and-single-stair. Access openings for firefighting belong here.
- Fire-resistance ratings, firewalls, fire dampers, and spatial separation distances belong to fire-separations-and-spatial-separation. The sprinkler-protected glazing criteria belong here.
- Construction type and combustible construction belong to combustible-construction-and-mass-timber. The sprinkler duties for combustible spaces belong here, as in NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(11) [PDF p.234].
- Cladding and exterior wall assemblies belong to building-envelope-insulation-cladding.
- Smoke control, ventilation, and general plumbing belong to hvac-ventilation-plumbing. Freeze protection of fire protection equipment belongs here, as in NBC(AE) 2023 p2, Div B, Sentence 9.10.20.5.(1) [PDF p.911].
- Barrier-free routes belong to occupancy-and-accessibility. Firefighter elevators belong here.
- Suite-level rules for secondary suites belong to housing-secondary-suites-part9. The Part 9 access and alarm articles belong here.
- Registered professional duties belong to professional-involvement. This sheet cross-links only the triggers.

## Benchmark acceptable solutions
The paraphrases below follow the Part 3 and Part 9 text. Article titles in this section were checked with codedb. Where a sentence refers to a standard such as NFPA 13, the standard text itself is not in the repository, so only the code's reference is described.

Fire alarm systems

- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.1.(1) [PDF p.218]. A fire alarm system is required in a building with an automatic sprinkler system. Sentences (2) and (3) of the same article exempt a building with an NFPA 13D system, or with fewer than 9 sprinklers under Sentence 3.2.5.12.(4).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.1.(4) [PDF p.218]. A building that is not sprinklered throughout needs a fire alarm system when it has a contained use area, an impeded egress zone, more than 3 storeys, an occupant load over 300, or one of the other listed features. Sentences (5) and (6) give exemptions.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.5.(1) [PDF p.220]. Fire alarm systems, including voice communication where provided, are installed to CAN/ULC-S524, except as Article 3.2.4.19 permits.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.7.(1) [PDF p.220]. A single stage fire alarm system in an assembly building with an occupant load over 300 notifies the fire department. Sentence 3.2.4.7.(2) [PDF p.220] requires the same for a system with waterflow-indicating devices, and Sentence 3.2.4.7.(4) [PDF p.220] requires the notification to follow CAN/ULC-S561.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.8.(1) [PDF p.220]. An annunciator sits near a building entrance that faces a street or an access route complying with Sentence 3.2.5.5.(1). Sentence 3.2.4.8.(7) [PDF p.221] accepts a fire alarm control unit in that location instead.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.9.(3) [PDF p.221]. Sprinkler system valves are electrically supervised, and their signals show on the building alarm annunciator.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.9.(4) [PDF p.221]. A fire pump is electrically supervised as NFPA 20 requires.

Access for firefighting and access routes

- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.1.(1) [PDF p.228]. Direct outdoor access for firefighting is required to each storey that is not sprinklered throughout and whose floor is less than 25 m above grade. It takes at least one unobstructed window or access panel for each 15 m of wall facing a street.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.1.(2) [PDF p.228]. Those openings have a sill no higher than 900 mm, and measure at least 1 100 mm high by 550 mm wide, or 750 mm wide for a building designed for the storage or use of dangerous goods.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.4.(1) [PDF p.228]. A building over 3 storeys in building height, or over 600 m² in building area, needs an access route for fire department vehicles to its principal entrance face. It also needs one to each face with firefighting access openings. A sprinklered throughout building needs no storey openings under Sentence 3.2.5.1.(1), so the route then reaches only the principal entrance face, unless basement openings under Article 3.2.5.2 apply.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.5.(1) [PDF p.229]. The principal entrance and each access opening sit at least 3 m and no more than 15 m from the nearest part of the access route, measured horizontally from the building face.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.5.(2) [PDF p.229]. A pumper must reach a position that depends on the fire department connection. With a connection, the pumper stands next to the hydrants in Article 3.2.5.15. Without a connection, the hydrant-to-pumper length plus the firefighter path is no more than 90 m. In either case, the firefighter path from the vehicle to the building is no more than 45 m.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.6.(1) [PDF p.229]. A required access route has a clear width of at least 6 m, unless lesser widths are shown to be satisfactory. The route also needs a centre-line radius of at least 12 m, an overhead clearance of at least 5 m, a gradient change of no more than 1 in 12.5 over at least 15 m, a surface that carries firefighting loads, a turnaround for any dead end over 90 m long, and a connection to a public thoroughfare.
- NBC(AE) 2023 p2, Div B, Note A-3.2.5.6.(1) [PDF p.375]. The note lists the design variables for access routes and says the local fire department should be consulted before design and construction.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.6.(2) [PDF p.229]. For buildings under Articles 3.2.2.51 or 3.2.2.60, no part of the route described in Sentence 3.2.2.10.(3) may be more than 20 m below the uppermost floor level.

Water supply, standpipes and hose stations

- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.7.(1) [PDF p.229-231]. Firefighting water comes from a piped municipal supply that delivers at least 3 800 L/min at a residual pressure of at least 140 kPa. A private supply must meet the formula in the sentence. A building that is no more than 3 storeys and no more than 600 m² is exempt.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.7.(2) [PDF p.230]. A private supply delivers at least 2 700 L/min for a building that needs less than 75 000 L, and at least 3 800 L/min for a larger building. It has a dry hydrant under NFPA 1142 or a pressurized hydrant under NFPA 24.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.7.(4) [PDF p.230]. The capacity requirement does not apply to a building sprinklered under NFPA 13, NFPA 13D, or NFPA 13R.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.8.(1) [PDF p.231]. A standpipe is required for a building more than 3 storeys high, a building more than 14 m high, or a smaller building whose area exceeds the table limit in that sentence. The sprinkler exception attaches only to the last case.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.8.(2) [PDF p.231]. A standpipe is not required in a storage garage that meets Article 3.2.2.92 and is no more than 15 m high.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.9.(1) [PDF p.231]. Standpipe design, construction, installation, and testing follow NFPA 14, except where Sentences (2) to (5) and the hose connection and hose station articles provide otherwise.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.9.(2) [PDF p.232]. A dry standpipe that is not connected to a water supply does not meet the article.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.9.(4) [PDF p.232]. The residual pressure at the topmost hose connection may be below 690 kPa if three conditions hold. The building is sprinklered throughout, the sprinkler water supply meets demand without a fire pump, and the fire department connection can deliver 690 kPa at the topmost hose connection.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.9.(5) [PDF p.232]. Every standpipe system has a fire department connection.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.10.(1) [PDF p.232]. Hose connections are placed in exits under NFPA 14.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.11.(1) [PDF p.232]. 38 mm hose stations are installed for a standpipe system in a building that is not sprinklered throughout. Sentence 3.2.5.11.(2) [PDF p.232] applies the same rule to each floor area that is not sprinklered throughout.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.11.(3) [PDF p.232]. Hose stations sit within 5 m of exits and at other points that cover the whole floor area.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.11.(5) [PDF p.232]. An open hose cabinet door must not block the required width of a means of egress.

Automatic sprinklers

- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(1) [PDF p.233]. Sprinkler systems are designed, built, installed, and tested to NFPA 13, except where Sentences (2) to (4) and (9) allow otherwise.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(2) [PDF p.233]. NFPA 13R may be used for certain residential buildings of no more than 4 storeys that meet the listed articles, or of no more than 3 storeys that meet the Part 9 article the sentence names. It also covers some care buildings with 10 or fewer occupants.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(3) [PDF p.233]. NFPA 13D may be used in a residential building with no more than two dwelling units, in some care buildings with two or fewer suites, and in some larger residential buildings that meet separation conditions between suites.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(4) [PDF p.233]. A building with fewer than 9 sprinklers may take its sprinkler water from the domestic water system if that system meets the required flow.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(6) [PDF p.234]. Sprinklers are not omitted from any room or closet on the storey directly below a roof assembly.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(10) [PDF p.234]. Where the sprinkler water comes from a source other than a piped municipal system, provision must be made for the fire department to use that supply.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(11) [PDF p.234]. Buildings of combustible construction need sprinklers in porches and balconies, public corridors, open attached stairs, and other listed spaces, except buildings built under Article 3.2.2.51.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.13.(1) [PDF p.234]. Combustible sprinkler piping is limited to residential and other light-hazard occupancies.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.13.(2) [PDF p.234]. Combustible sprinkler piping meets ULC/ORD-C199P.

Fire department connections and fire pumps

- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.15.(1) [PDF p.235]. The fire department connection for a standpipe is no more than 45 m from a hydrant and is unobstructed.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.18.(1) [PDF p.235]. A fire pump is installed to NFPA 20.

High buildings

- NBC(AE) 2023 p2, Div B, Sentence 3.2.6.5.(1) [PDF p.237]. Every elevator can operate on emergency power.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.6.5.(3) [PDF p.237]. At least one elevator is provided for firefighters. Sentence 3.2.6.5.(4) [PDF p.237] sets its platform area at no less than 2.2 m² and its load capacity at 900 kg.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.6.7.(1) [PDF p.238]. A central alarm and control facility sits on the storey that holds the firefighter access entrance, in a location that is readily accessible.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.6.8.(1) [PDF p.239]. A voice communication system conforming to Article 3.2.4.22 is required under listed conditions, including a top storey floor more than 36 m above grade.

Emergency lighting and emergency power

- NBC(AE) 2023 p2, Div B, Sentence 3.2.7.3.(1) [PDF p.239]. Emergency lighting gives an average illumination of at least 10 lx at floor or tread level in exits, principal routes and other listed spaces.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.7.5.(1) [PDF p.240]. An emergency power supply system follows CSA C282, except where Articles 3.2.7.6 and 3.2.7.7 apply.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.7.8.(1) [PDF p.241]. Fire alarm systems, including those with voice communication, have an emergency power supply.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.7.8.(3) [PDF p.241]. The emergency supply gives supervisory power for at least 24 h, then full emergency power under load.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.7.8.(4) [PDF p.241]. The supply transfers to emergency power automatically when the normal source fails.

Part 9 houses and small buildings

- NBC(AE) 2023 p2, Div B, Sentence 9.10.18.2.(1) [PDF p.907]. A fire alarm system is installed in a sprinklered building, except as Sentences (3) and (4) allow for NFPA 13D systems and buildings with fewer than 9 sprinklers.
- NBC(AE) 2023 p2, Div B, Sentence 9.10.18.2.(2) [PDF p.908]. A fire alarm system is also required in a building of more than 3 storeys, a building with an occupant load over 300, or in the other listed cases. Sentence 9.10.18.2.(5) [PDF p.908] exempts some residential occupancies.
- NBC(AE) 2023 p2, Div B, Sentence 9.10.18.3.(2) [PDF p.908]. Several Part 3 fire alarm articles do not apply to Part 9 buildings, including the article that requires a fire alarm in a sprinklered building. Part 9 buildings follow the Part 3 fire alarm rules that remain.
- NBC(AE) 2023 p2, Div B, Sentence 9.10.19.1.(1) [PDF p.909]. Smoke alarms to CAN/ULC-S531 are installed in each dwelling unit, each sleeping room outside a dwelling unit, and the ancillary and common spaces of a house with a secondary suite.
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.1.(1) [PDF p.911]. A window or access panel of at least 1 100 mm high by 550 mm wide, with a sill no higher than 900 mm, is required on the second and third storeys of every building, in at least one wall facing a street, unless those storeys are sprinklered.
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.2.(1) [PDF p.911]. An unsprinklered basement more than 25 m long or wide needs direct access to the outdoors, except in a house with a secondary suite or a basement that serves one dwelling unit.
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.2.(2) [PDF p.911]. That access may be a window or door at least 1 100 mm high by 550 mm wide, with a sill no higher than 900 mm.
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.3.(1) [PDF p.911]. Fire department equipment reaches each building by a street, a private roadway, or a yard.
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.3.(2) [PDF p.911]. A roadway or yard used for access is designed for its connection to public thoroughfares, the weight of firefighting equipment, its width, the radius of curves, its overhead clearance, and the location of fire hydrants.
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.4.(1) [PDF p.911]. Portable extinguishers are installed in all buildings except dwelling units, in conformance with the National Fire Code, Alberta Edition. The fire code requirements are outside this sheet, because codedb does not build that code.

- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.5.(1) [PDF p.911]. Fire protection equipment in an unheated area is protected from freezing.

## Attributions
An attribution pair links a functional statement to an objective for the provision beside it. For example, F12 paired with OS1.2 means the table attributes emergency response support to the injury objective OS1.2. Part 3 pairs in this sheet come from Table 3.10.1.1. (PDF p.337-341). Part 9 pairs come from Table 9.38.1.1. (PDF p.1130-1131). Every pair below was read from the codedb attribution rows for the provision cited.

Objective meanings, paraphrased from NBC(AE) 2023 p2, Div A, Article 2.2.1.1., PDF p.68-72:

- OS1.1, fire or explosion occurring.
- OS1.2, fire or explosion impacting areas beyond its point of origin. This is the injury form of the objective.
- OS1.3, collapse of physical elements due to fire or explosion.
- OS1.4, fire safety systems failing to function as expected.
- OS1.5, persons being delayed in or impeded from moving to a safe place during a fire emergency.
- OS3.1, injury from tripping, slipping, falling, contact, drowning or collision.
- OS3.7, persons being delayed in or impeded from moving to a safe place during an emergency.
- OP1.2, fire or explosion impacting areas beyond its point of origin. This is the property form of the objective.
- OP3.1, fire or explosion impacting areas beyond the building of origin, also a property form.

Functional statement meanings, paraphrased from NBC(AE) 2023 p2, Div A, Article 3.2.1.1., PDF p.79-81:

- F01, minimize the risk of accidental ignition.
- F02, limit the severity and effects of fire or explosions.
- F03, retard the effects of fire on areas beyond its point of origin.
- F05, retard the effects of fire on emergency egress facilities.
- F06, retard the effects of fire on facilities for notification, suppression and emergency response.
- F10, facilitate the timely movement of persons to a safe place in an emergency.
- F11, notify persons in a timely manner of the need to take action in an emergency.
- F12, facilitate emergency response.
- F13, notify emergency responders in a timely manner of the need to take action in an emergency.
- F30, minimize the risk of injury from tripping, slipping, falling, contact, drowning or collision.
- F81, minimize the risk of malfunction, interference, damage, tampering, lack of use or misuse.
- F82, minimize the risk of inadequate performance from improper or lacking maintenance.

Part 3 pairs by provision:

- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.1.(1) [PDF p.218]: [F11-OS1.5], [F13-OS1.5,OS1.2], [F13-OP1.2] (Div B Table 3.10.1.1., PDF p.337).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.1.(4) [PDF p.218]: [F11-OS1.5] (Div B Table 3.10.1.1., PDF p.337).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.7.(1) [PDF p.220]: [F13-OS1.5,OS1.2], [F13-OP1.2] (Div B Table 3.10.1.1., PDF p.337).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.7.(4) [PDF p.220]: [F81,F13-OS1.5,OS1.2], [F81,F13-OP1.2] (Div B Table 3.10.1.1., PDF p.337).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.4.8.(1) [PDF p.220]: [F12-OS1.5,OS1.2] (Div B Table 3.10.1.1., PDF p.337).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.4.(1) [PDF p.228]: [F12-OS1.5,OS1.2], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.5.(1) [PDF p.229]: [F12-OS1.5,OS1.2], [F06-OS1.1], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.5.(2) [PDF p.229]: [F12-OS1.2], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.6.(1) [PDF p.229]: [F12-OS1.2], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.6.(2) [PDF p.229]: [F02,F12-OS1.2], [F02,F12,F03-OP1.2], [F02,F12,F03-OP3.1] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.7.(1) [PDF p.229]: [F02,F03,F12-OS1.2,OS1.3] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.8.(1) [PDF p.231]: [F02-OS1.2], [F02-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.9.(1) [PDF p.231]: [F02-OS1.2], [F02-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.10.(1) [PDF p.232]: [F03-OS1.2], [F05,F06-OS1.5,OS1.2], [F03,F06-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.11.(1) [PDF p.232]: [F02-OS1.2], [F02-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(1) [PDF p.233]: [F02,F81,F82-OS1.2], [F02,F81,F82-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(2) [PDF p.233]: [F02,F81-OS1.2], [F02,F81-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(3) [PDF p.233]: [F02,F81-OS1.2], [F02,F81-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(4) [PDF p.233]: [F02-OS1.2], [F02-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(10) [PDF p.234]: [F12-OS1.2], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.339).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.15.(1) [PDF p.235]: [F12-OS1.2], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.340).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.18.(1) [PDF p.235]: [F02,F81-OS1.2], [F81-OS1.4], [F02,F81-OP1.2], [F81-OP1.4] (Div B Table 3.10.1.1., PDF p.340).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.6.5.(1) [PDF p.237]: [F12-OS1.2,OS1.5], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.340).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.6.5.(3) [PDF p.237]: [F12,F06-OS1.2,OS1.5], [F12,F06-OP1.2] (Div B Table 3.10.1.1., PDF p.340).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.6.7.(1) [PDF p.238]: [F12-OS1.2,OS1.5], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.340).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.6.7.(2) [PDF p.238]: [F12-OS1.2,OS1.5], [F11-OS1.5], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.341).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.6.8.(1) [PDF p.239]: [F12,F11-OS3.7] (Div B Table 3.10.1.1., PDF p.341).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.7.3.(1) [PDF p.239]: [F30-OS3.1], [F10-OS3.7] (Div B Table 3.10.1.1., PDF p.341).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.7.5.(1) [PDF p.240]: [F81,F06,F11,F02,F03,F10,F12-OS1.2,OS1.5], [F81,F06,F02,F03-OP1.2], [F81,F06,F02-OP3.1], [F81,F30-OS3.1], [F81,F11,F10,F12-OS3.7] (Div B Table 3.10.1.1., PDF p.341).
- NBC(AE) 2023 p2, Div B, Sentence 3.2.7.8.(1) [PDF p.241]: [F11-OS1.5], [F13-OS1.5,OS1.2], [F13-OP1.2] (Div B Table 3.10.1.1., PDF p.341). The table's application note for this sentence says the pairs cover the emergency power supply for fire alarm systems, including those with voice communication.

Part 9 pairs by provision:

- NBC(AE) 2023 p2, Div B, Sentence 9.10.18.2.(1) [PDF p.907]: [F11-OS1.5], [F13-OS1.2,OS1.5], [F03-OS1.2], [F13-OP1.2] (Div B Table 9.38.1.1., PDF p.1130).
- NBC(AE) 2023 p2, Div B, Sentence 9.10.18.2.(2) [PDF p.908]: [F11-OS1.5] (Div B Table 9.38.1.1., PDF p.1130).
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.1.(1) [PDF p.911]: [F12-OS1.2,OS1.5], [F12-OP1.2] (Div B Table 9.38.1.1., PDF p.1131).
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.2.(1) [PDF p.911]: [F12-OS1.2,OS1.5], [F12-OP1.2] (Div B Table 9.38.1.1., PDF p.1131).
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.3.(1) [PDF p.911]: [F12-OS1.2,OS1.5], [F12-OP1.2] (Div B Table 9.38.1.1., PDF p.1131).
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.4.(1) [PDF p.911]: [F81,F02,F12-OS1.2], [F81,F02,F12-OP1.2] (Div B Table 9.38.1.1., PDF p.1131).
- NBC(AE) 2023 p2, Div B, Sentence 9.10.20.5.(1) [PDF p.911]: [F81,F02-OS1.2], [F81,F02-OP1.2] (Div B Table 9.38.1.1., PDF p.1131).

Pairs in the table are not a complete list of what a provision addresses. They say which objective and function the code attributes to the acceptable solution. A pair that is absent from this list may still exist in the table for another sentence of the same article, so check codedb for each provision before relying on it.

## Intent
The entries below come from the NBC 2020 Intent Statements. They are explanatory only. They are national material, not Alberta law, and they do not replace the 2023 Alberta text or its attribution tables. The wording is paraphrased.

- NBC 2020 Intent Statements, 3.2.4.1.(1) [PDF p.409-410]. The intent is to limit the chance that occupants and emergency responders are not told of a fire promptly, which could delay evacuation or fire response.
- NBC 2020 Intent Statements, 3.2.4.1.(2) [PDF p.410]. The intent is to exempt certain small sprinklered buildings from the alarm requirement, on the basis of their limited size and a sprinkler system built to the referenced standard.
- NBC 2020 Intent Statements, 3.2.4.1.(4) [PDF p.410]. The intent is to limit the chance that occupants of an unsprinklered building with the listed features are not promptly notified of a fire, which could delay evacuation.
- NBC 2020 Intent Statements, 3.2.5.4.(1) [PDF p.448]. The intent is to limit the chance that fire emergency response will be delayed or ineffective, which could delay evacuation and let fire spread to other parts of the building.
- NBC 2020 Intent Statements, 3.2.5.5.(1) [PDF p.448-449]. The intent is the same emergency response concern, applied to the position of access routes relative to principal entrances and access openings.
- NBC 2020 Intent Statements, 3.2.5.5.(2) [PDF p.449]. The intent is to limit the chance that fire emergency response will be delayed or ineffective, which could let fire spread to other parts of the building.
- NBC 2020 Intent Statements, 3.2.5.5.(3) [PDF p.449]. The intent is to clarify how the unobstructed path of travel is measured.
- NBC 2020 Intent Statements, 3.2.5.6.(1) [PDF p.450]. The intent is to limit the chance that fire emergency response will be delayed or ineffective, which could let fire spread to other parts of the building.
- NBC 2020 Intent Statements, 3.2.5.6.(2) [PDF p.450-451]. The intent is to limit the chance that a firefighter's hose stream cannot reach the roof, which could make firefighting less effective and let fire spread beyond its point of origin or to an adjacent building.
- NBC 2020 Intent Statements, 3.2.5.7.(1) [PDF p.451]. The intent is to limit the chance that firefighting operations are ineffective, so that a fire is not suppressed or controlled and spreads.
- NBC 2020 Intent Statements, 3.2.5.8.(1) [PDF p.451-452]. The intent is to limit the chance that manual firefighting operations are delayed or ineffective, so that a fire is not controlled.
- NBC 2020 Intent Statements, 3.2.5.8.(2) [PDF p.452]. The intent exempts open-air storage garages from the standpipe rule, on the basis that there are no other occupancies, the construction is noncombustible, and the storeys are open to the air.

Comparison with the 2023 Alberta tables. The codedb comparison finds that the 2020 intent entries match the 2023 attribution pairs for Sentences 3.2.4.1.(1), 3.2.5.4.(1), 3.2.5.5.(2), 3.2.5.6.(1), 3.2.5.8.(1), 3.2.5.11.(1), 3.2.5.12.(1), and 3.2.7.8.(1). For Sentence 3.2.5.7.(1), the comparison differs. The 2023 table has nine pairs that the 2020 supplement does not list. An alternative solution must use the 2023 Alberta table, not the 2020 entries, for that sentence.

Intent entries for the Part 9 articles in this sheet were not read, so this section does not describe their intent.

## Typical alternative solutions
The sources below show request types from Alberta variances and interpretations, and from related guidance. They come from variances, interpretations, policies and guides, so they show the kinds of request, not how often each kind is made.

- Sprinkler-protected glazing in fire-rated walls. The variance removes the test requirement in NBC(AE) 2023 p2, Div B, Sentence 3.1.7.1.(1) [PDF p.151] for glazing in fire-rated assemblies. It applies when a fixed automatic sprinkler system protects the glazing and the listed criteria are met (source p.2 and source p.3). The same subject appears in STANDATA 14-BCV-018 and 14-BCV-018r1 for the 2014 edition, and in STANDATA 19-BCV-013 for the 2019 edition (source p.1 of each).
- Narrower access routes. Sentence 3.2.5.6.(1) allows a clear width under 6 m when lesser widths are shown to be satisfactory (NBC(AE) 2023 p2, Div B, Sentence 3.2.5.6.(1) [PDF p.229]). Edmonton's policy B19-04 treats a side-yard path with a clear width from 0.6 m to 0.9 m as obstructed, and names an automatic sprinkler system as an example of the alternative that may then be needed (source p.2).
- Sprinklers to offset excess area or height. The CWC Alternative Solutions Guide lists enhanced sprinkler protection, meaning more design area and a more reliable water supply, as a way to offset excess area or height (source p.16). It also lists additional fire protection systems such as sprinkler protection (source p.15), and sidewall sprinkler protection at the intersection of cross-laminated timber floor and wall panels (source p.11).
- Fire department access points. The CWC guide lists fire department access to the building (source p.21), and targeted fire department access points and access routes serving the building (source p.22), among the measures it discusses.
- Sprinkler protection for storage racking. STANDATA 23-BCV-014 requires sprinkler protection under all platforms and access levels of multi-level storage racking, despite the standard that its Item 5.3.1 names (source p.4).
- Construction and demolition sites. STANDATA 23-BCI-030 is an interpretation, not a variance. It restates the expectations for unobstructed fire department access to hydrants, extinguishers and fire department connections, and for water supply during construction and demolition (source p.7 and source p.9). It does not change the permanent building requirements.

## Usual mitigations and evidence
The items below are the ones that the code, guidance and variance texts in this sheet point to. Reviewer expectations beyond those texts were not sourced. The confidence ladder after the list shows how much weight each source can carry.

- Sprinklers designed to NFPA 13 under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(1) [PDF p.233]. The application should state its design basis, which a reviewer may question (see the refusal section).
- Fire department notification from the fire alarm system where the code requires it, under NBC(AE) 2023 p2, Div B, Sentence 3.2.4.7.(1) [PDF p.220], with installation to CAN/ULC-S524 under NBC(AE) 2023 p2, Div B, Sentence 3.2.4.5.(1) [PDF p.220].
- Emergency power for the fire alarm system under NBC(AE) 2023 p2, Div B, Sentence 3.2.7.8.(1) [PDF p.241].
- Hose stations within 5 m of exits under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.11.(3) [PDF p.232].
- Written consultation with the local fire department on access routes, as NBC(AE) 2023 p2, Div B, Note A-3.2.5.6.(1) [PDF p.375] recommends.
- Ongoing inspection, testing and maintenance of sprinklers under NFC(AE) 2023 p2, Div B, Sentence 6.4.1.1.(1) [NFC PDF p.314], which refers to NFPA 25.
- Maintenance of fire protection installations in working order under NFC(AE) 2023 p2, Div B, Sentence 6.1.1.2.(1) [NFC PDF p.313].
- Inspection, testing and maintenance of emergency power under NFC(AE) 2023 p2, Div B, Sentence 6.5.1.1.(1) [NFC PDF p.315], which refers to CSA C282.
- A fire safety plan prepared with the fire department, under NFC(AE) 2023 p2, Div B, Sentence 2.8.2.1.(1) [NFC PDF p.96], and reviewed at intervals of no more than 12 months under NFC(AE) 2023 p2, Div B, Sentence 2.8.2.1.(2) [NFC PDF p.96].

Response time evidence comes from the Edmonton guideline (source p.15). Its service targets are dispatch and turnout each within 90 seconds for 90 percent of calls, first pump travel within 4 minutes for 90 percent, and a first alarm of at least 16 firefighters within 8 minutes travel for 90 percent. These are city targets, not code requirements. The guideline also notes that the code generally assumes intervention on a timescale of about 10 minutes (source p.8).

Evidence confidence ladder, from strongest to weakest:

1. Code text and Alberta attribution pairs, checked line by line in codedb. These bind the Alberta requirement.
2. Variances issued under the Provincial Building Administrator, such as STANDATA 23-BCV-004. These bind only the matters and conditions they state.
3. Municipal policies and guidelines, such as Edmonton's B19-04 and its emergency services guideline. These guide practice and bind only where the city adopts them.
4. Analysis and test reports by a competent designer, such as the code analysis that Sentence 2.3.1.1.(2) requires (NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(2) [PDF p.739]).
5. National intent statements. These explain the purpose of a sentence and are not Alberta law.

Test and listed standards named in the sources read here:

- CAN/ULC-S101, fire endurance tests, under NBC(AE) 2023 p2, Div B, Sentence 3.1.7.1.(1) [PDF p.151].
- CAN/ULC-S136, sprinkler-protected window systems, named as criterion 1 in STANDATA 23-BCV-004 (source p.2).
- CAN/ULC-S524, fire alarm installation, under NBC(AE) 2023 p2, Div B, Sentence 3.2.4.5.(1) [PDF p.220].
- CAN/ULC-S561, fire department notification equipment, under NBC(AE) 2023 p2, Div B, Sentence 3.2.4.7.(4) [PDF p.220].
- CAN/ULC-S531, smoke alarms, under NBC(AE) 2023 p2, Div B, Sentence 9.10.19.1.(1) [PDF p.909].
- ULC/ORD-C199P, combustible sprinkler piping, under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.13.(2) [PDF p.234].
- NFPA 13, 13R and 13D, sprinkler systems, under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(1) [PDF p.233], Sentence 3.2.5.12.(2) [PDF p.233] and Sentence 3.2.5.12.(3) [PDF p.233].
- NFPA 14, standpipes, under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.9.(1) [PDF p.231].
- NFPA 20, fire pumps, under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.18.(1) [PDF p.235].
- NFPA 24 and NFPA 1142, private water supplies, under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.7.(2) [PDF p.230].
- CSA C282, emergency power, under NBC(AE) 2023 p2, Div B, Sentence 3.2.7.5.(1) [PDF p.240].

The text of these standards is not in the repository. This sheet records only what the code and STANDATA say about them.

## Engineering / professional triggers
Registered professional involvement follows the Division C rules on project size and type. The main sentences are these:

- NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(1) [PDF p.739-740]. A registered professional is not required for listed small buildings, such as a single-family dwelling or a multiple-family dwelling with 4 dwelling units or fewer, and for some small assembly, care, and residential buildings.
- NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(3) [PDF p.740]. For buildings outside that list, the drawings and specifications are authenticated by one or more registered professionals who are qualified in the relevant part of architecture and engineering.
- NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(4) [PDF p.740]. The authority having jurisdiction may require registered professionals for a project whose size or complexity raises special safety concerns.
- NBC(AE) 2023 p2, Div C, Sentence 2.4.2.1.(1) [PDF p.741]. The coordinating professional subsection applies to a project within Sentence 2.4.1.1.(3). Sentence 2.4.2.1.(1) is a scope sentence, not a design duty.
- NBC(AE) 2023 p2, Div C, Article 2.4.2.2. [PDF p.741]. Before applying for a permit, the owner retains a coordinating registered professional and registered professionals of record for the design and field reviews.

Alternative solutions carry their own professional duties. NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(2) [PDF p.739] requires a code analysis and information on special maintenance and operating requirements. NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(4) [PDF p.739] requires the code analysis to state the qualifications, experience and background of the person who takes responsibility for the design. The Edmonton guideline says the effect of an alternative solution on emergency services must be judged by a competent designer using good fire protection engineering practice (source p.8).

Triggers in this topic, as stated in the sources read:

- A sprinkler departure from NFPA 13 is a design question for the designer of record. Whether Alberta requires a certified sprinkler or fire alarm designer is UNVERIFIED. The Safety Codes Act and the regulations in the repository were not searched for that point in this pass.
- An access route or water supply departure should carry a fire protection engineering analysis and the local fire department's view. The Edmonton guideline calls for an evaluation by a competent designer (source p.8). Note A-3.2.5.6.(1) says the local fire department should be consulted (NBC(AE) 2023 p2, Div B, Note A-3.2.5.6.(1) [PDF p.375]).
- A fire pump, a standpipe, or a private water supply needs a designer who can meet NFPA 20, NFPA 14, NFPA 24 or NFPA 1142 as the code requires. The text of those standards is not in the repository, so their design requirements are UNVERIFIED here.

The challenge scope appendix quotes professional design wording under a Division C sentence numbered 2.4.2.1.(1) (source p.11). The 2023 text places Sentence 2.4.2.1.(1) [PDF p.741] in the scope rules (see the open questions). This sheet cites the code text, not the appendix.

## Interactions with other topics
- Egress and single stair. Access openings and access routes are measured to the building face and to the principal entrance. Exits, travel distance and dead ends belong to egress-and-single-stair. Hose stations sit within 5 m of exits and at other points for floor coverage (NBC(AE) 2023 p2, Div B, Sentence 3.2.5.11.(3) [PDF p.232]).
- Fire separations and spatial separation. Continuity of the fire alarm through a firewall is covered by NBC(AE) 2023 p2, Div B, Sentence 3.2.4.2.(1) [PDF p.219]. The rating test for sprinkler-protected glazing is the fire separations question, and this sheet covers only the sprinkler criteria in STANDATA 23-BCV-004 (source p.2 and source p.3).
- Combustible construction and mass timber. Sprinklers are required in combustible spaces under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(11) [PDF p.234], and combustible sprinkler piping is limited by NBC(AE) 2023 p2, Div B, Sentence 3.2.5.13.(1) [PDF p.234]. The CWC guide's mass timber examples are cited in the alternative solutions section (source p.11 and source p.15).
- Building envelope, insulation and cladding. Access openings under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.1.(1) [PDF p.228] are unobstructed windows or access panels in exterior walls, so the cladding design must keep them unobstructed. The envelope rules are in building-envelope-insulation-cladding.
- Secondary suites in Part 9 houses. A house with a secondary suite is exempt from the access panel rule under NBC(AE) 2023 p2, Div B, Sentence 9.10.20.1.(3) [PDF p.911], and needs smoke alarms in its ancillary and common spaces under NBC(AE) 2023 p2, Div B, Sentence 9.10.19.1.(1) [PDF p.909]. Suite rules sit in housing-secondary-suites-part9.
- Structural and framing. Water tanks, fire pumps and elevator machine rooms raise structural and service-space questions. This sheet does not check their loads. Those questions belong to structural-and-framing.
- HVAC, ventilation and plumbing. A domestic water supply can serve a sprinkler system with fewer than 9 sprinklers under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(4) [PDF p.233]. Fire protection equipment in unheated areas needs freeze protection under NBC(AE) 2023 p2, Div B, Sentence 9.10.20.5.(1) [PDF p.911]. Smoke control belongs to hvac-ventilation-plumbing.
- Professional involvement. The triggers above cross-link to professional-involvement, where the registered professional rules belong.
- Evidence and conformity. The general evidence rules for variances belong to evidence-and-conformity. The test standards above appear here only for this topic's own claims.
- Process and administration. A written variance request may go to the Provincial Building Administrator under NBC(AE) 2023 p2, Div C, Sentence 2.2.1.2.(1) [PDF p.729]. The documentation rules are in NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(1) [PDF p.739]. Process steps belong to process-and-admin.
- Occupancy and accessibility. Emergency lighting on principal routes (NBC(AE) 2023 p2, Div B, Sentence 3.2.7.3.(1) [PDF p.239]) and firefighter elevators (NBC(AE) 2023 p2, Div B, Sentence 3.2.6.5.(3) [PDF p.237]) touch occupancy-and-accessibility.
- Code structure and attribution. The structure of the attribution tables is a code-structure-and-attribution question.

## Common refusal / "more info" causes
The first group below is written in the sources. The second group follows from the code text and is a likely reviewer question, not a documented refusal.

Written in the sources:

- The access route fails a dimension in NBC(AE) 2023 p2, Div B, Sentence 3.2.5.6.(1) [PDF p.229] (6 m clear width, 12 m centre-line radius, 5 m overhead clearance, gradient, load-bearing surface, turnaround for a dead end over 90 m).
- The firefighter path is over 45 m, or the principal entrance is outside the 3 m to 15 m band from the route, under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.5.(1) [PDF p.229] and Sentence 3.2.5.5.(2) [PDF p.229].
- The fire department connection is more than 45 m from a hydrant under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.15.(1) [PDF p.235].
- The alternative solution uses functional statements F06, F12 or F13 without an impact statement for emergency services. The Edmonton guideline calls such a variance likely to affect emergency services (source p.8, screening question 1.2).
- The design relies on fire service action for protection, and no time basis is stated. The guideline's screening question 2 asks whether life safety or property protection depends on timely intervention, and item 2.1 notes that the code generally assumes intervention in about 10 minutes (source p.8).
- The design introduces equipment or technology that is new to the fire service, or special occupant plans that affect response (source p.8, screening questions 3 and 4).
- The documentation omits assumptions about emergency responders (source p.20).
- A Part 9 proposal cites the B19-04 policy for a building over 600 m² or over 3 storeys, which is Part 3 under NBC(AE) 2023 p2, Div A, Sentence 1.3.3.2.(1) [PDF p.39-40]. The policy applies to Part 9 buildings and one-storey Part 3 buildings up to 600 m² (source p.1).
- A side-yard access path measures less than 0.9 m clear, and no alternative is offered (source p.2).

Likely reviewer questions from the code text:

- The alternative solution does not give the qualifications of the person responsible for the design, which NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(4) [PDF p.739] requires.
- The alternative solution does not state its special maintenance or operating requirements, which NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(2) [PDF p.739] requires.
- The sprinkler design does not identify NFPA 13 as the design basis, under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(1) [PDF p.233].
- The fire alarm requirement that comes with sprinklers is not addressed, under NBC(AE) 2023 p2, Div B, Sentence 3.2.4.1.(1) [PDF p.218]. STANDATA 23-BCV-004 Note 4 says the same for sprinkler-protected glazing (source p.3).
- The inspection, testing and maintenance plan for a system that the fire code does not regulate is missing. The Edmonton guideline notes that such systems may have gaps in their ITM procedures (source p.22).
- The application cites a superseded code edition, such as the 2019 Alberta edition. Edmonton's B19-04 does this in its code references, so its section numbers must be checked against the 2023 text (source p.1 and source p.3).

## Precedents
- STANDATA 23-BCV-004, sprinkler-protected glazing in fire-resistant wall assemblies. Issued May 2024 by the Provincial Building Administrator. It lists 11 criteria. Criteria 1 to 8 are on source p.2, and criteria 9 to 11 with four notes are on source p.3. Note 4 requires a fire alarm system for the building under NBC(AE) 2023 p2, Div B, Sentence 3.2.4.1.(1) [PDF p.218].
- STANDATA 14-BCV-018 and 14-BCV-018r1 (2014 edition), and STANDATA 19-BCV-013 (2019 edition). Earlier variances on sprinkler-protected glazing, with the same opening statement (source p.1 of each).
- STANDATA 23-BCV-014 (March 2025). Multi-level storage racking, with sprinkler protection under all platforms and access levels (source p.4).
- STANDATA 23-BCI-030 (March 2025). An interpretation on measures to mitigate fire spread to adjacent buildings, water supply, and access for firefighting, aimed at construction and demolition sites (source p.1, source p.7 and source p.9).
- Edmonton Small Building Access Policy B19-04 (18 May 2023). Applies to Part 9 buildings and one-storey Part 3 buildings up to 600 m² (source p.1). It sets a 45 m stop distance for fire trucks from the principal entrance (source p.1), side-yard path widths of 0.9 m and 0.6 m (source p.2), and examples (source p.3).
- Edmonton guideline COE-IM-GUIDE-0040 v01 (15 April 2025), Guideline for Alternative Solutions Affecting Emergency Services. It gives the screening questions (source p.8), the 10-minute assumption (source p.8), the service targets (source p.15), documentation guidance (source p.20), and inspection, testing and maintenance for systems the NFC does not regulate (source p.22).
- CWC Alternative Solutions Guide. Examples of sprinkler, access point and access route measures in alternative solutions (source p.11, source p.15, source p.16, source p.21 and source p.22).

Not reviewed for this sheet: Calgary alternative solution guide (no sprinkler mentions in the text search), Calgary SPV-006 (sprinkler mentions on two pages), and the Edmonton design guide and technical report (sprinkler mentions on one page and on four pages). These are listed as open questions.

## Worked example
This is an invented case. It is not an approved project, a professional design, or a decision by any authority.

### Intake and classification
The applicant proposes a four-storey apartment building in Edmonton with 24 dwelling units and a building area of 1 150 m². It is a Group C building over 3 storeys, so Part 3 applies under NBC(AE) 2023 p2, Div A, Sentence 1.3.3.2.(1) [PDF p.39-40]. The building is sprinklered throughout and uses the sprinklered four-storey Group C article, which allows up to 1 800 m² at four storeys under NBC(AE) 2023 p2, Div B, Sentence 3.2.2.52.(1) [PDF p.189-190]. Assuming the floor of the top storey is below 18 m above grade, Subsection 3.2.6 does not apply (NBC(AE) 2023 p2, Div B, Sentence 3.2.6.1.(1) [PDF p.236]).

The baseline firefighting requirements are these. A fire alarm system is required because the building is sprinklered (NBC(AE) 2023 p2, Div B, Sentence 3.2.4.1.(1) [PDF p.218]). A standpipe is required because the building is more than 3 storeys high (NBC(AE) 2023 p2, Div B, Sentence 3.2.5.8.(1) [PDF p.231]). The sprinkler exception in that sentence does not apply to this case. The water supply capacity rule does not apply because the building is sprinklered under NFPA 13 (NBC(AE) 2023 p2, Div B, Sentence 3.2.5.7.(4) [PDF p.230]). An access route must reach the principal entrance face (NBC(AE) 2023 p2, Div B, Sentence 3.2.5.4.(1) [PDF p.228]). Because the building is sprinklered throughout, no storey access openings are required under NBC(AE) 2023 p2, Div B, Sentence 3.2.5.1.(1) [PDF p.228]. The example has no basement, so Article 3.2.5.2 is not engaged.

The site has a private lane about 35 m long from a public street to the principal entrance. The applicant states that the lane is 4.5 m clear, with a 12 m centre-line radius, a 5 m overhead clearance, and a surface that carries fire apparatus. These are assumptions to be measured on a survey.

### Define the requested departure
The applicant asks that the 4.5 m clear width be accepted in place of the 6 m width in NBC(AE) 2023 p2, Div B, Sentence 3.2.5.6.(1) [PDF p.229]. The request changes the route width only. It does not change the principal entrance distance, the firefighter path, the hydrant distance, or the sprinkler and alarm requirements. Those stay as baseline. The sprinklers are a required baseline, not extra compensation for the narrower lane, so the example does not count them as offsetting the departure. Pumper placement must still meet NBC(AE) 2023 p2, Div B, Sentence 3.2.5.5.(2) [PDF p.229]. The building has a fire department connection, so the pumper must stand beside the hydrants that Article 3.2.5.15 covers. The firefighter path from the pumper to the entrance is assumed to be 30 m, within the 45 m limit.

### Emergency services screening
The Edmonton guideline asks four screening questions (source p.8).

- Question 1 asks whether the alternative solution modifies a firefighting requirement, including Division B Subsection 3.2.5. It does. Question 1.1 says the designer must state the operational impact of any variance of a prescriptive firefighting measure, and Question 1.2 says a variance that refers to F06, F12 or F13 is likely to affect emergency services. The Section C table in this example cites F12 (see below), so review is required.
- Question 2 asks whether life safety or property protection relies on timely fire service action. The applicant must state whether it does. The example assumes that the sprinklers, rated walls and separation protect the building without fire service action, so the answer is no, but the applicant must show it. If exposure protection for a neighbouring building depends on intervention, Question 2.1 applies, and the 10-minute assumption must be checked against the design.
- Question 3 asks whether the design introduces equipment or technology that is new to Edmonton Fire Rescue Services. The example has none, but the apparatus check in the next section applies.
- Question 4 asks whether the design needs special occupant plans that affect response. The example has none. A fire safety plan under NFC(AE) 2023 p2, Div B, Sentence 2.8.2.1.(1) [NFC PDF p.96] still applies where it is required.

### Impact evaluation
The evaluation has four steps. First, check whether the parcel is inside the City's 10-minute response boundary. The guideline says that projects outside the boundary need careful review of spatial separation and delayed response (source p.15). Second, obtain the response times for the station that serves the address. The guideline targets are 4 minutes for first pump travel and 8 minutes for a first alarm of 16 firefighters, each for 90 percent of calls (source p.15). Third, check the apparatus. The guideline lists pumping apparatus, including aerial platforms, with onboard pumps that generally discharge 7,000 L/min (source p.17). A swept-path check with the apparatus that the fire service uses shows whether the 4.5 m lane works for that apparatus. The code and the guideline do not set the method for that check, so the method is an open point. Fourth, get the written view of the fire department on the departure, which Note A-3.2.5.6.(1) recommends (NBC(AE) 2023 p2, Div B, Note A-3.2.5.6.(1) [PDF p.375]).

### Section C table
The rows below are the provisions the departure touches. Each row gives the attributed pairs and the 2020 intent entry.

| Article | Objective and function | Intent |
|---|---|---|
| NBC(AE) 2023 p2, Div B, Sentence 3.2.5.6.(1) [PDF p.229] | [F12-OS1.2], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.339). F12 means facilitate emergency response. | NBC 2020 Intent Statements, 3.2.5.6.(1) [PDF p.450] |
| NBC(AE) 2023 p2, Div B, Sentence 3.2.5.5.(2) [PDF p.229] | [F12-OS1.2], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.339). The pumper location and firefighter path are covered here. | NBC 2020 Intent Statements, 3.2.5.5.(2) [PDF p.449] |
| NBC(AE) 2023 p2, Div B, Sentence 3.2.5.4.(1) [PDF p.228] | [F12-OS1.5,OS1.2], [F12-OP1.2] (Div B Table 3.10.1.1., PDF p.339). OS1.5 means delay or impediment in moving to a safe place during a fire emergency. | NBC 2020 Intent Statements, 3.2.5.4.(1) [PDF p.448] |
| NBC(AE) 2023 p2, Div B, Sentence 3.2.5.12.(1) [PDF p.233] (baseline, unchanged) | [F02,F81,F82-OS1.2], [F02,F81,F82-OP1.2] (Div B Table 3.10.1.1., PDF p.339). Sprinklers are the baseline and are not changed by the departure. | Not checked for this row. |

### What the example does not show
The example does not show that a 4.5 m lane is acceptable. That depends on the fire service's view, the apparatus check and the response times, none of which this sheet can verify. The intent entries are explanatory only.

## Open questions / uncertainty
- The brief says sprinklers are the most common compensating feature. This is UNVERIFIED. A text search of the 170 non-code reference documents found the word "sprinkl" in 42 of them. The search did not code each use as a compensating measure, so the claim cannot be confirmed. Sprinkler conditions do recur, as in STANDATA 14-BCV-018, 19-BCV-013, 23-BCV-004, 23-BCV-014, and an exemption from an alternate floor recall feature in STANDATA 23-BCI-038 for a floor area that is sprinklered throughout (source p.2).
- The NFPA standards (13, 13R, 13D, 14, 20, 24, 25 and 1142) are not in the repository. The sheet records only what the code says about them.
- CAN/ULC-S136, CAN/ULC-S524, CAN/ULC-S561 and CSA C282 were not read as standards. Their use is taken from the code and STANDATA text.
- Whether Alberta requires a certified designer or installer for sprinklers, fire alarms, or fire pumps is UNVERIFIED. The Safety Codes Act and the regulations in the repository were not searched for that point in this pass.
- The challenge scope appendix quotes professional wording under a Division C sentence numbered 2.4.2.1.(1) (source p.11). In the 2023 text, Sentence 2.4.2.1.(1) [PDF p.741] is a scope rule. CONTRACTS.md records the same discrepancy. The appendix's article numbers are not used here.
- Edmonton B19-04 cites the 2019 Alberta edition. Its references to Division B Sentence 3.2.5.5.(2) [PDF p.229] (the 45 m distance), Division B Article 3.2.5.6 [PDF p.229] and Division B Article 9.10.20.3 [PDF p.911] were compared with the 2023 text. A bounded web search on 2026-10-19 did not return the policy. The repository copy dated 18 May 2023 is therefore the only source for its figures, and whether it is the current version is UNVERIFIED.
- The Edmonton 10-minute boundary map and the service targets are City materials, not code text. The boundary map was not checked.
- The NFC attribution table for Part 6 is on NFC PDF page 317. This sheet does not transcribe it, because codedb does not build the NFC.
- NBC(AE) 2023 p2, Div B, Sentence 3.2.5.7.(1) [PDF p.229]: the 2020 intent entries differ from the 2023 pairs. The 2023 table has nine pairs that the 2020 supplement does not list.
- Part 9 sprinkler and alarm provisions beyond the articles cited here were not searched.
- Calgary SPV-006, the Calgary alternative solution guide, the Edmonton design guide and the Edmonton technical report were not reviewed for this sheet. A text search found sprinkler mentions in Calgary SPV-006, the Edmonton design guide and the Edmonton technical report, and none in the Calgary alternative solution guide.
- STANDATA 23-BCV-004 is dated May 2024 in the repository. A bounded web search on 2026-10-19 did not return it, and no page was opened, so whether it is still in force or has been replaced is UNVERIFIED.
- The validator reports six errors, all unsupported_document, for six NFC citations in the body, which are five distinct NFC sentences. Codedb does not build the NFC, so the validator cannot check them. Each one was checked by hand with codesearch against the NFC PDF page it cites. They are not citation mismatches, and no NFC citation was removed to clear the validator.

## Sources
NBC and NFC code text (codedb and codesearch):

- NBC(AE) 2023 p2, Division A, Sentence 1.3.3.2.(1), PDF p.39-40. Division B, Subsections 3.2.4 to 3.2.7, PDF pages 218 to 242, with the attribution table at Table 3.10.1.1., PDF p.337-341. Division B, Subsection 9.10.18 to 9.10.20, PDF p.907 to 911, with the attribution table at Table 9.38.1.1., PDF p.1130-1131. Division C, Sentences 2.2.1.2.(1) (PDF p.729), 2.3.1.1.(1) to (4) (PDF p.739), 2.4.1.1.(1) to (4) (PDF p.739-740), 2.4.2.1.(1) (PDF p.741) and Article 2.4.2.2. (PDF p.741). Division B, Sentence 3.1.7.1.(1) (PDF p.151), Sentence 3.2.2.52.(1) (PDF p.189-190), and Note A-3.2.5.6.(1) and related notes (PDF p.375).
- Objective definitions, NBC(AE) 2023 p2, Div A, Article 2.2.1.1., PDF p.68-72. Functional statement definitions, Div A, Article 3.2.1.1., PDF p.79-81.
- Division A Note A-2.2.1.1.(1), PDF p.75, on emergency responders as persons under objective OS1.
- NBC 2020 Intent Statements, explanatory only. Entries cover Sentences 3.2.4.1.(1) to (4), on PDF pages 409 to 410, and Sentences 3.2.5.4.(1) to 3.2.5.8.(2), on PDF pages 448 to 452.
- NFC(AE) 2023 p2, Division B, the Part 6 inspection, testing and maintenance provisions and the Part 2 fire safety plan provisions, cited by sentence in the body, on NFC PDF pages 96, 313, 314 and 315. The NFC attribution table on NFC PDF page 317 is not transcribed.

Guides, policies and STANDATA (source pages):

- Edmonton Guideline for Alternative Solutions Affecting Emergency Services, COE-IM-GUIDE-0040 v01, 2025-04-15 (reference/guides, text id Edmonton-Alt-Solutions-Emergency-Services). Pages read: 2, 6, 8, 9, 11, 15, 17, 20 and 22. Pages cited in this sheet: 8, 15, 17, 20 and 22.
- Edmonton Small Building Access Policy B19-04, 18 May 2023 (text id edmonton-policy-b19-04-small-building-access). Pages 1, 2 and 3.
- STANDATA variance 23-BCV-004, Sprinkler-protected glazing in fire-resistant wall assemblies, May 2024 (text id standata-nbc2023-variance-23-bcv-004). Pages 1, 2 and 3.
- STANDATA variance 23-BCV-014, Multi-level storage racking systems, March 2025 (text id standata-nbc2023-variance-23-bcv-014). Page 4.
- STANDATA interpretation 23-BCI-030, Measures to mitigate fire spread to adjacent buildings, March 2025 (text id standata-nbc2023-interpretation-23-bci-030). Pages 1, 7 and 9.
- STANDATA 14-BCV-018 and 14-BCV-018r1 (2014 edition), and STANDATA 19-BCV-013 (2019 edition). Historical precedents, first page of each.
- CWC Alternative Solutions Guide (text id CWC-Alternative-Solutions-Guide). Pages read: 11, 15, 16, 17, 21 and 22. Pages cited in this sheet: 11, 15, 16, 21 and 22.
- Challenge scope appendix (text id Challenge-Scope), source p.11, read only to note its discrepancy with Sentence 2.4.2.1.(1) [PDF p.741].

