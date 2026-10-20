---
topic: structural-and-framing
scope: Structural design and framing under NBC(AE) 2023 - Div B Part 4 (loads, foundations, materials) and Part 9 structural and framing provisions (foundations, permanent wood foundations, wood-frame members, spans, bracing, trusses) - with engineered wall systems, off-site and prefabricated construction, and the point where a registered professional is required.
sources_checked:
  - Repository contracts and briefs: docs/contracts/PREAMBLE, WAVE2-BRIEF, WAVE2-TOPICS (structural-and-framing), CONTRACTS.md, WAVES.md, reference/README-challenge.md
  - Method files read: t3-workflow SKILL.md and references/routes.md, Matt Pocock engineering research SKILL.md, pstack unslop SKILL.md, Codex AGENTS.md, codedb README and PROGRESS
  - NBC(AE) 2023 second printing, Div A 1.2.2.1, 1.3.3.2 and 1.3.3.3, Div B 1.1.3.1 and Part 4 and Part 9 structural articles as cited, Div C 2.3.1.1, 2.4.1.1 to 2.4.1.2 and 2.5.1.1
- Code database (codedb, NBC-AE build 2): lookup, children, the attributions for Div B Table 4.5.1.1 (PDF pp.513 to 524) and Table 9.38.1.1 (PDF pp.1120 to 1192), the definitions table (pages 68 to 81), the intent comparison, and the printed page 1180 checked with tools/codesearch.py page.
  - NBC 2020 Intent Statements (explanatory only), pages cited in Intent
  - STANDATA local copies in reference/text: 23-BCV-002, 23-BCV-007, 23-BCV-010, 23-BCV-010R1, 23-BCV-012R1, 23-BCV-014, 23-BCI-015, 23-BCI-015R1, 23-BCB-002, 23-BCB-002R1, 19-BCV-012, 19-BCV-020, 19-BCV-020-REV1, 19-BCV-021, 19-BCV-025, 14-BCV-002R1, 14-BCV-005
  - Edmonton Policy Bulletin B23-03 local copy in reference/text
  - NRC Canada's objective-based codes, reference/text, explanatory (2005 numbering)
  - CCMC registry snapshot (reference/data/ccmc-registry.json) and research/precedents/index.json
  - Web, accessed 2026-10-19: alberta.ca building STANDATA index, APEGA news item of 2026-02-23, Rocky View County building page, unofficial sips.org copy of CCMC 13016-R (text unreadable, search summary only)
last_verified: 2026-10-19
---
# Structural design and framing

## Progress
- Done and saved (2026-10-19): every template section. Attributions were read from codedb lookup. Intent is paraphrased from the explanatory NBC 2020 Intent Statements, with PDF pages. Precedents, worked example, open questions and sources are written.
- Web checks done (2026-10-19): alberta.ca STANDATA index, APEGA news item, Rocky View County page, and an unofficial CCMC copy. Each result is recorded where it bears on a claim. The Edmonton PDF and the CCMC PDF could not be read as text, so those points rely on the local copy or are marked UNVERIFIED.
- Next: run codedb validate on this file and fix real errors, then give the final report with the Methods used receipt.
- Edition traps found and recorded: the NRC paper's bracing example uses 2005 numbering, and the 2019 STANDATAs cite 2019 numbers. Archived documents are marked as archived where they appear.
- Scope: only this file and reference/web/structural-and-framing/ may be written. No evals, variants, commits, pushes or further delegation.

## Plain-language summary
Structural design asks whether a building and its parts can carry the forces on them without collapse, excessive movement or damage. Those forces are loads. Dead loads are the weight of the building. Live loads are people, furniture and use. Snow, rain, wind, earthquake and ground movement are the environmental loads.

Division B Part 4 is the full structural design method. It sets the loads (Subsections 4.1.4 to 4.1.8), the foundation design basis (Section 4.2) and the materials standards, such as CSA O86 for wood and CSA S16 for steel (Section 4.3). A registered professional must carry out any design done under Part 4 (Division C, Sentence 2.4.1.2.(1) [PDF p.740]).

Part 9 covers houses and small buildings. It offers two routes. One is the prescriptive rules and span tables in Subsection 9.4.2 and Sections 9.15, 9.16 and 9.23. The other is design under Part 4 (Sentence 9.4.1.1.(1) [PDF p.836]).

The prescriptive wood-frame rules in Section 9.23 apply only within stated limits: members spaced 600 mm or less, spans of 12.20 m or less, a floor live load of 2.4 kPa or less, and no use as a foundation (Sentence 9.23.1.1.(1) [PDF p.962]). Outside those limits, the framing and fastening are designed under Part 4 (Sentence 9.23.1.1.(2) [PDF p.962]).

Wood roof trusses are the clearest case of an engineer required in a Part 9 house. Sentence 9.23.14.11.(1) requires good engineering practice [PDF p.986]. Alberta's interpretation 23-BCI-015R1 requires the truss design and its interconnections to be authenticated by a registered engineering professional. The City of Edmonton's Policy Bulletin B23-03 requires authenticated truss drawings with permit applications from 1 March 2026 for single-family, semi-detached and 3 or 4 unit rowhouse projects.

Alberta STANDATA variances add accepted alternatives. They cover Canadian Wood Council Span Book spans (23-BCV-007), mechanically laminated timber permanent wood foundations (23-BCV-012R1) and off-site construction certified to CSA A277 (Division C, Sentence 2.5.1.1.(2) [PDF p.742]). Several predecessors are archived and must not be cited as current, including the 2019 SIP variance.

This sheet records which provisions, evidence and professional triggers apply. It does not decide whether a structure is adequate. It stops where a registered professional must design, authenticate or field-review the work.

## When this topic applies
### Trigger signals
- Any building where footings, foundation walls, floor framing, roof framing, wall framing, lintels or bracing must be sized or selected. Common intake words: joist, rafter, truss, stud, header or lintel, sill plate, bracing, sheathing, footing, bearing pressure, retaining wall.
- Location data needed for loads: ground snow load, 1-in-50 hourly wind pressure, seismic spectral acceleration Sa(0.2) and the climatic values in Appendix C (Sentence 1.1.3.1.(2) [PDF p.89]).
- Part 9 limits exceeded: members spaced more than 600 mm apart, spans over 12.20 m, a floor live load over 2.4 kPa, or a structure that acts as a foundation (Sentence 9.23.1.1.(1) [PDF p.962]).
- Engineered products: I-joists, LVL or LSL, engineered wood trusses, truss plates, structural insulated panels (SIPs), panelized walls, insulated concrete forms (ICF) and precast concrete wall panels.
- Foundations: permanent wood foundations (CSA S406), wood floors on ground, flat-wall ICF foundations (Sentence 9.15.4.1.(1) [PDF p.927]), a high water table, soil with low bearing capacity, sloping ground and retaining walls.
- Off-site or modular buildings and panels, including buildings certified to CSA A277 and steel building modules certified to CSA A660.
- Structural steel or cold-formed steel members, which bring in CSA S16 or CSA S136 (Sentences 4.3.4.1.(1) and 4.3.4.2.(1) [PDF p.512]) and fabricator certification questions.
- Multi-level storage racking and its anchorage, which Part 4 designs for loads (Sentence 4.4.3.1.(1) [PDF p.513]).

### Near-misses that belong to another topic
- Fire-resistance ratings of loadbearing walls, floors or firewalls belong to fire-separations-and-spatial-separation. The attribution tables pair fire resistance with structural functions, but the rating is a fire question.
- Mass timber, CLT, heavy timber and combustible-construction limits belong to combustible-construction-and-mass-timber. Structural design of the timber still runs through CSA O86 here.
- Insulation, air and vapour control, cladding and the exterior environmental separator belong to building-envelope-insulation-cladding. A SIP wall has both a structural and an envelope role, so both topics apply.
- Guards, handrails, stairs and egress routes belong to egress-and-single-stair and occupancy-and-accessibility. Structural loads on guards are cited here only as load inputs.
- Plumbing, HVAC and equipment supports belong to hvac-ventilation-plumbing. Seismic anchorage of non-structural elements (Article 4.1.8.18) stays a structural input.
- Secondary suite layouts, room counts and the routine house permit belong to housing-secondary-suites-part9, unless the question is a span, truss or bracing.
- Who may sign or stamp drawings and the limits of professional practice belong to professional-involvement. This topic flags the trigger and hands off there.
- Variance form mechanics, submission routes and Section C mapping belong to process-and-admin.
- Relocatable industrial camp buildings (Part 10) belong to occupancy-and-accessibility.

## Benchmark acceptable solutions
Read this section as the "recipe" a code-compliant structure follows. Each entry says what the provision requires, in paraphrase. Where a table or standard is named, the sheet cites the provision that names it. Table values are not transcribed here.

### Part 4, the design method for all buildings (including Part 3)
- Loads and effects. Sentence 4.1.2.1.(1) requires dead, live, snow and rain, wind, earthquake and other listed loads to be considered. The other listed effects are temperature change, shrinkage, moisture change, creep and ground settlement (Division B, Sentence 4.1.2.1.(1) [PDF p.424]). Sentence 4.1.2.1.(3) assigns each building an importance category from Table 4.1.2.1, which feeds the snow, wind and earthquake values [PDF p.424].
- Strength and stability. Sentence 4.1.3.2.(1) requires the building and its structural components to have sufficient strength and stability under the specified loads [PDF p.426].
- Serviceability, deflection and vibration. Articles 4.1.3.4 (serviceability), 4.1.3.5 (deflection) and 4.1.3.6 (vibration) control movement, cracking and comfort [PDF p.428 to 429].
- Dead loads. Article 4.1.4.1 sets the specified dead load for a structural member, beginning with the weight of the member itself [PDF p.429].
- Live loads. Sentence 4.1.5.3.(1) requires the uniform live load to be no less than the value in Table 4.1.5.3 [PDF p.430].
- Snow. Article 4.1.6.2 sets the specified snow load S on roofs and other surfaces, with the accumulation factors and related rules in its sentences [PDF p.437].
- Wind. Sentence 4.1.7.3.(1) sets the external wind pressure or suction on building surfaces by the static procedure [PDF p.453].
- Earthquake. Sentence 4.1.8.4.(1) sets the seismic values that depend on site designation [PDF p.479 to 480]. Sentence 4.1.8.5.(1) sets the earthquake importance factor from Table 4.1.8.5.-A [PDF p.482]. Article 4.1.8.9 sets the force modification factors and the general restrictions on the lateral system [PDF p.484].
- Foundations. Sentence 4.2.4.1.(1) requires the design of foundations, excavations and soil- and rock-retaining structures to rest on a subsurface investigation and on one basis: accepted geotechnical and civil engineering principles applied by a registered professional, established local practice with successful experience, or in situ testing of foundation units [PDF p.507]. Sentence 4.2.4.1.(3) requires a registered professional to determine the geotechnical load components and factored geotechnical resistances at ultimate limit states [PDF p.507]. Article 4.2.4.14 sets the structural design of the foundation [PDF p.508]. Article 4.2.6.1 applies Subsection 4.2.4 to shallow foundations [PDF p.509]. Sentence 4.2.7.2.(1) [PDF p.510] applies Subsection 4.2.4 to deep foundations.
- Materials. Wood conforms to CSA O86 (Sentence 4.3.1.1.(1) [PDF p.511]). Plain and reinforced masonry conforms to CSA S304 (Sentence 4.3.2.1.(1) [PDF p.511]). Concrete conforms to CSA A23.3 (Sentence 4.3.3.1.(1) [PDF p.512]). Structural steel conforms to CSA S16 (Sentence 4.3.4.1.(1) [PDF p.512]). Cold-formed steel conforms to CSA S136 (Sentence 4.3.4.2.(1) [PDF p.512]). Aluminum conforms to CSA S157 and S157.1 with limit states design (Sentence 4.3.5.1.(1) [PDF p.512]). Glass conforms to CAN/CGSB-12.20 with a wind-load adjustment factor of at least 0.75, or to ASTM E1300 with a factor of at least 1.0 (Sentence 4.3.6.1.(1) [PDF p.512]).
- Storage racks. Sentence 4.4.3.1.(1) requires storage racks, including their anchorage, to be designed for loads under Part 4 [PDF p.513].

### Part 9, houses and small buildings
Structural design (Subsection 9.4).
- Structural route choice. Sentence 9.4.1.1.(1) lets structural members and connections conform to other Part 9 requirements (a), be designed to good engineering practice such as CWC 2014 "Engineering Guide for Wood Frame Construction" (b), or be designed to Part 4 using the loads and deflection and vibration limits in Part 9 or Part 4 (c) [PDF p.836 to 837].
- Floor live load cap on the prescriptive route. Sentence 9.4.1.1.(2) [PDF p.837] caps the specified floor live load at 2.4 kPa, the value in Table 4.1.5.3, where floor framing uses route (b) or (c) and the supports use route (a).
- Location data. Sentence 9.4.1.1.(3) [PDF p.837] sends location-specific snow, wind and seismic values to Subsection 1.1.3.
- Light-frame scope for Part 9 snow and roof rules. Sentence 9.4.2.1.(1) limits Subsection 9.4.2 to light-frame construction with clad or braced planes on at least one side, members at 600 mm on centre or less, clear spans of 12.2 m or less, roof deflection per Article 9.4.3.1, a total roof area of 4 550 m² or less even where firewalls separate adjoining buildings, and flat-roof obstruction spacing limits [PDF p.837].
- Snow. Sentence 9.4.2.2.(1) gives a specified snow load formula. Sentence 9.4.2.2.(2) sets a floor of 1 kPa. Sentence 9.4.2.2.(3) sends bow-string, arch and semicircular roof trusses over 6 m unsupported span to Subsection 4.1.6. Sentences 9.4.2.2.(4) and (5) cover drift at roof steps [PDF p.837 to 838].
- Platforms and attic loads. Sentence 9.4.2.3.(1) requires exterior platforms subject to snow to carry the roof snow load or 1.9 kPa, whichever is greater [PDF p.838]. Sentence 9.4.2.4.(1) requires limited-access residential attic ceiling joists or truss bottom chords to carry a minimum total specified load [PDF p.838].
- Deflection. Sentence 9.4.3.1.(1) limits member deflection to Table 9.4.3.1. Sentence 9.4.3.1.(2) excludes dead loads from that check [PDF p.838].
- Footings and soil. Sentence 9.4.4.1.(1) sizes shallow footings under Section 9.15 or under Section 4.2 with the bearing pressures in Table 9.4.4.1 [PDF p.839]. Sentence 9.4.4.3.(1) halves the allowable bearing pressure where a footing bears on gravel, sand or silt and the water table is within a footing width below the bearing surface [PDF p.839]. Articles 9.4.4.4 (soil movement), 9.4.4.5 (retaining walls) and 9.4.4.6 (walls supporting drained earth) cover the remaining soil cases [PDF p.839 to 840].

Foundations and floors on ground (Sections 9.15 and 9.16).
- Wood-frame foundations. Sentence 9.15.2.4.(1) requires CSA S406 permanent wood foundation design (a) or Part 4 design (b) [PDF p.925].
- Footing sizes. Sentence 9.15.3.4.(1) requires footing width or area to meet Table 9.15.3.4 [PDF p.926]. Sentence 9.15.3.4.(2) [PDF p.926] sends strip footings under joist spans over 4.9 m in light wood-frame buildings to Section 4.2 or to a formula.
- Flat-wall ICF foundations. Sentence 9.15.4.1.(1) requires flat-wall insulating concrete form units to conform to CAN/ULC-S717.1 [PDF p.927]. Article 9.15.4.2 sets wall thickness and height by table [PDF p.927].
- Wood floors on ground. Sentence 9.16.5.1.(1) requires wood floors-on-ground to conform to CSA S406 [PDF p.934].
- Above-grade flat ICF walls. Sentence 9.20.17.1.(1) requires concrete of at least 140 mm and constant thickness over the wall height for flat insulating concrete form walls not in contact with the ground [PDF p.952].

Wood-frame construction (Section 9.23).
- Scope. Sentence 9.23.1.1.(1) applies Section 9.23 to lumber frames of small repetitive members, or engineered components, that are clad, sheathed or braced on at least one side, spaced 600 mm or less, not serving as foundations, with a floor live load of 2.4 kPa or less and spans of 12.20 m or less. Sentence 9.23.1.1.(2) [PDF p.962] sends wood constructions outside those conditions to Subsection 4.3.1.
- Strength and rigidity. Sentence 9.23.2.1.(1) requires all members to be framed, anchored, fastened, tied and braced for strength and rigidity [PDF p.962].
- Spans. Sentence 9.23.4.1.(1) limits the joist, beam and lintel spans in Article 9.23.4.2 to residential live loads. Sentence 9.23.4.1.(2) [PDF p.967] sends other uses to Subsection 4.1.3. Sentence 9.23.4.2.(1) gives joist and rafter spans from Span Tables 9.23.4.2.-A to -G. Sentence 9.23.4.2.(3) gives built-up and glued-laminated floor beam spans from Tables -H to -K. Sentence 9.23.4.2.(4) gives roof ridge beam spans from Table -L [PDF p.967 to 968].
- Studs. Sentence 9.23.10.1.(1) sets stud size and spacing by Table 9.23.10.1 [PDF p.974]. Sentence 9.23.10.2.(1) [PDF p.975] requires blocking or strapping at mid-height where loadbearing interior walls are not finished under Section 9.29.
- Bracing, low to moderate loads. Article 9.23.13.1 applies where Sa(0.2) is 0.70 or less and the 1-in-50 hourly wind pressure is under 0.80 kPa (body text, PDF p.978). Its Sentence (2) then lets exterior walls qualify by panel cladding under Section 9.27, by sheathing under Subsection 9.23.17 fastened per Table 9.23.3.5.-A, or by an interior panel finish under Section 9.29. Bracing may instead follow Articles 9.23.13.4 to 9.23.13.7, Part 4, or CWC 2014 (Sentence 9.23.13.1.(2) [PDF p.978]).
- Bracing, higher loads. Sentence 9.23.13.2.(1) applies where Sa(0.2) is over 0.70 and up to 1.8, with floor limits, and the wind pressure is under 1.20 kPa. Sentence 9.23.13.2.(2) [PDF p.979] allows Articles 9.23.13.4 to 9.23.13.7, Part 4 or CWC 2014.
- Bracing, extreme loads. Sentence 9.23.13.3.(1) covers Sa(0.2) over 1.8, Sa(0.2) over 0.70 with more floors than the 9.23.13.2 limits, or a wind pressure of 1.20 kPa or more. Sentence 9.23.13.3.(2) requires Part 4 or CWC 2014 [PDF p.979].
- Roof trusses. Sentence 9.23.14.11.(1) requires wood roof trusses to be designed under good engineering practice such as TPIC 2019, "Truss Design Procedures and Specifications for Light Metal Plate Connected Wood Trusses." Sentence 9.23.14.11.(2) requires the joint connections to conform to Subsection 4.3.1. Sentence 9.23.14.11.(3) requires member bracing per the truss design drawings, with continuous lateral bracing anchored to the roof and ceiling diaphragms at 6.10 m on centre or less [PDF p.986].
- Subfloor, roof and wall sheathing. Articles 9.23.15 (subfloor), 9.23.16 (roof sheathing) and 9.23.17 (wall sheathing) set material, thickness and fastening through tables (for example Table 9.23.15.5.-A, Table 9.23.16.7.-A and Table 9.23.17.2.-B). Pages 986 to 990 [codedb article pages; table values not transcribed].

### How Part 3 and Part 9 change the answer
- Scope comes first. Division A, Sentence 1.3.3.3.(1) [PDF p.40] applies Part 9 to buildings of 3 storeys or less and 600 m² or less in building area, in listed occupancies such as Group C residential. Division A, Sentence 1.3.3.2.(1) [PDF p.39 to 40] applies Parts 3 to 6 to buildings outside that scope, including larger buildings in the listed occupancies and Group A, B and F1 uses. Div B, Section 9.23 is not a shortcut for those buildings.
- Part 3 buildings design their members under Part 4. Wood is designed under CSA O86 (Div B, Sentence 4.3.1.1.(1) [PDF p.511]), and the designer must be a registered professional (Div C, Sentence 2.4.1.2.(1) [PDF p.740]). Div B, Sentence 9.23.4.1.(2) [PDF p.967] states the same floor-span rule for Part 9 floors serving other than residential areas.
- In Part 9, the same member may come from a table or from a Part 4 design. The table route is limited to the conditions in Sentence 9.23.1.1.(1). Outside those conditions, a Part 4 design is required, with a registered professional as the designer.
- A Part 9 house can be exempt from registered professional involvement under Division C, Sentence 2.4.1.1.(1) [PDF p.739 to 740], which covers single-family dwellings and multiple-family dwellings of 4 units or fewer, except where Sentence (4) requires involvement. That exemption does not remove the Part 4 designer requirement in Sentence 2.4.1.2.(1). It also does not remove the truss authentication that Alberta's interpretation of Div B, Sentence 9.23.14.11.(1) requires.

## Attributions
Every pair below was read from `codedb lookup` (the attributions field) for the sentence shown. Part 4 pairs come from Table 4.5.1.1 (PDF pp.513 to 524). Part 9 pairs come from Table 9.38.1.1 (PDF pp.1120 to 1192). Division C has no attribution table, so its provisions carry no pairs. Abbreviations follow the table: FS is a functional statement, and OS, OP, OH and OE are the objectives.

The functional statements F20 to F23 are defined in the codedb definitions table at page 80. The objective definitions in the next paragraph come from the same table. "Env sep" marks an application note that limits the row to elements that support or form an environmental separator. Pairs are kept exactly as printed, so a row with no note applies to the whole sentence.

Objective and functional definitions used in this section (codedb definitions table): OS2 Structural Safety (page 68) and its items OS2.1 loads exceeding loadbearing capacity, OS2.2 loads exceeding the supporting medium, OS2.3 damage or deterioration of elements, OS2.4 vibration or deflection, OS2.5 instability, and OS2.6 collapse of an excavation. OP2 Structural Sufficiency (page 72) with OP2.1 to OP2.6 on the same themes, plus OP2.6 instability or movement of the supporting medium. OP4 Protection of Adjacent Buildings from Structural Damage (page 72), with OP4.1 settlement, OP4.2 collapse onto adjacent buildings, OP4.3 impact and OP4.4 collapse of the excavation. OH4 Vibration and Deflection Limitation (page 70). OH1.1 to OH1.3 cover air quality, thermal comfort and contact with moisture (page 70). F80 is "to resist deterioration resulting from expected service conditions" (page 81).

### Part 4, Table 4.5.1.1
| Sentence (Div B) | Pairs as printed | Application note | Page |
|---|---|---|---|
| 4.1.2.1.(1) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4], [F22-OH4] | none | 513 |
| 4.1.2.1.(2) and (3) | [F20-OS2.1] | none | 513 |
| 4.1.3.2.(1) | [F20-OP2.1], [F22-OP2.4], [F20-OS2.1] | none | 513 |
| 4.1.3.2.(2) | [F20-OS2.1], [F22-OS2.4,OS2.5], [F20-OP2.1], [F22-OP2.4,OP2.5] | F22-OS2.4,OS2.5 applies to the stabilizing resistance of dead load | 513 |
| 4.1.3.2.(3) | [F20-OS2.1], [F22-OS2.4,OS2.5], [F20-OP2.1], [F22-OP2.4,OP2.5] | F22-OS2.4,OS2.5 applies to the stabilizing resistance of dead load | 513 |
| 4.1.3.2.(4) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4] | none | 513 |
| 4.1.3.2.(5) | [F20-OS2.1], [F22-OS2.4,OS2.5], [F20-OP2.1], [F22-OP2.4,OP2.5] | none | 513 |
| 4.1.3.2.(8) and (9) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4] | none | 513 |
| 4.1.3.2.(11) | [F20-OS2.1], [F22-OS2.4,OS2.5] | none | 513 |
| 4.1.3.2.(12) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4] | none | 514 |
| 4.1.3.4.(1) to (4) | [F22-OP2.4], [F22-OH4] | none | 514 |
| 4.1.3.4.(5) | [F22-OP2.4], [F22-OH4] | none | 514 |
| 4.1.3.4.(6) | [F21-OS2.5], [F21-OP2.4,OP2.5], [F22-OH4] | none | 514 |
| 4.1.3.5.(1) | [F22-OP2.4], [F22-OH4] | none | 514 |
| 4.1.3.5.(2) | [F22-OS2.3,OS2.4], [F22-OP2.4] | none | 514 |
| 4.1.3.5.(3) | [F22-OP2.4] | none | 514 |
| 4.1.3.5.(5) | [F22-OS2.3,OS2.4], [F22-OP2.3,OP2.4] | none | 514 |
| 4.1.3.6.(2) and (3) | [F20-OS2.1], [F20-OP2.1,OP2.4], [F22-OP2.4], [F22-OH4] | none | 514 |
| 4.1.4.1.(2), (3) and (5) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4] | none | 514 |
| 4.1.4.1.(6) | [F20-OS2.1], [F22-OS2.4,OS2.5] | none | 514 |
| 4.1.5.3.(1) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4], [F22-OH4] | none | 514 |
| 4.1.5.9.(1) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4] | none | 515 |
| 4.1.6.2.(1) to (9) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4] | 4.1.6.2.(8) and its clauses (a) to (f) carry notes on roof shapes that call for a higher accumulation factor | 515 |
| 4.1.7.3.(1) to (10) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4], [F22-OH4] | none | 517 |
| 4.1.8.4.(1), (2), (4) and (6) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4] | none | 519 |
| 4.1.8.5.(1) and (2) | [F20-OS2.1], [F20-OP2.1,OP2.3], [F22-OP2.4] | none | 519 |
| 4.1.8.9.(1) to (4) | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4] | none | 519 |
| 4.2.4.1.(1) | [F20-OS2.2,OS2.6], [F21-OS2.6], [F20-OP2.2], [F21-OP2.5], [F21-OP4.1,OP4.4] | none | 522 |
| 4.2.4.1.(5) | [F21-OS2.5], [F21-OP2.4,OP2.5] | none | 522 |
| 4.2.7.2.(3) | [F20-OS2.1,OS2.2], [F21-OS2.5], [F20-OP2.1,OP2.2], [F21,F22-OP2.4] | none | 523 |
| 4.2.7.2.(5) | [F20-OS2.1], [F20-OP2.1,OP2.4], [F22-OP2.4] | none | 523 |
| 4.2.7.2.(6) | [F20-OP2.1,OP2.4] | none | 523 |

The sentence-level records for Div B 4.2.4.14.(1), 4.2.6.1.(1), 4.3.1.1.(1), 4.3.2.1.(1), 4.3.3.1.(1) and 4.3.4.1.(1) have no pair rows (codedb status none). These are design-basis sentences that point to CSA standards, and the pairs for those standards are not in this database.

### Part 9, Table 9.38.1.1 (structural subsections)
| Sentence (Div B) | Pairs as printed | Application notes | Page |
|---|---|---|---|
| 9.4.2.2.(1) | [F20-OS2.1,OS2.3], [F22-OS2.3], [F20-OP2.1,OP2.3], [F22-OP2.3], [F22-OH1.1,OH1.2,OH1.3] | none | 1120 |
| 9.4.2.2.(2) | [F20-OS2.1], [F20-OP2.1] | none | 1120 |
| 9.4.2.2.(4) | [F20-OS2.1,OS2.3], [F22-OS2.3], [F20-OP2.1,OP2.3], [F22-OP2.3], [F22-OH1.1,OH1.2,OH1.3] | none | 1120 |
| 9.4.2.3.(1) | [F20-OS2.1], [F20-OP2.1] | none | 1120 |
| 9.4.2.4.(1) | [F20-OS2.1], [F20-OP2.1] | none | 1120 |
| 9.4.3.1.(1) | [F22-OS2.3], [F22-OP2.1,OP2.4], [F22-OP2.3], [F22-OH4], [F22-OS3.1], [F22-OS3.7], [F22-OH1.1,OH1.2,OH1.3] | Env sep on OS2.3, OP2.3 and OH1; floors on OS3.1; emergency egress walls on OS3.7 | 1120 |
| 9.4.4.1.(1) | [F20-OS2.2], [F20-OS2.3], [F20-OP2.2,OP2.4], [F20-OP2.3], [F20-OH1.1,OH1.2,OH1.3], [F20-OH4], [F20-OS3.1], [F20-OS3.7] | Env sep on the OS2.3, OP2.3 and OH1 rows; footings supporting floors on OH4 and OS3.1; footings for egress walls on OS3.7 | 1120 |
| 9.4.4.2.(1) | [F20-OS2.2], [F20-OS2.3], [F20-OP2.2,OP2.4], [F20-OP2.3], [F20-OH1.1,OH1.2,OH1.3], [F20-OH4], [F20-OS3.1] | Env sep on OS2.3, OP2.3 and OH1; floors on OH4 and OS3.1 | 1120 |
| 9.4.4.2.(2) | [F20-OS2.2], [F20-OS2.3], [F20-OP2.2,OP2.4], [F20-OP2.3], [F20-OH1.1,OH1.2,OH1.3], [F20-OH4], [F20-OS3.1] | Same notes as 9.4.4.2.(1) | 1121 |
| 9.4.4.3.(1) | [F20-OS2.2], [F20-OS2.3], [F20-OP2.2,OP2.4], [F20-OP2.3], [F20-OH1.1,OH1.2,OH1.3], [F20-OH4], [F20-OS3.1] | Env sep on OS2.3, OP2.3 and OH1; floors on OH4 and OS3.1 | 1121 |
| 9.4.4.4.(1) | [F21-OS2.1], [F21-OS2.3], [F21-OP2.1,OP2.4], [F21-OP2.3], [F21-OH1.1,OH1.2,OH1.3], [F21-OH4], [F21-OS3.1], [F21-OS3.7] | Notes as printed: env sep on OS2.3, OP2.3 and OH1; foundations and footings supporting floors on OH4 and OS3.1; footings for egress walls on OS3.7 | 1121 |
| 9.4.4.5.(1) | [F20-OS2.1,OS2.3], [F20-OP2.1,OP2.3,OP2.4], [F20-OH1.1,OH1.2,OH1.3], [F20-OH4], [F20-OS3.1] | Floors on OH4 and OS3.1 | 1121 |
| 9.4.4.6.(1) and (2) | [F20-OS2.1,OS2.3], [F20-OP2.1,OP2.3,OP2.4], [F20-OH1.1,OH1.2,OH1.3], [F20-OH4], [F20-OS3.1], [F20-OS3.7] | Floors on OH4 and OS3.1; egress walls on OS3.7 | 1121 |
| 9.15.2.4.(1)(a) | [F20-OS2.1,OS2.2], [F20,F80-OS2.3], [F20-OP2.1,OP2.2], [F20,F80-OP2.3], [F20,F80-OH1.1,OH1.2,OH1.3], [F20,F80-OH4], [F20,F80-OS3.1] | Env sep on the F80 rows; floors on OH4 and OS3.1 | 1136 |
| 9.16.5.1.(1) | [F20-OS2.1], [F20-OS2.3], [F20-OS3.1], [F20-OP2.1], [F20-OP2.3], [F20-OH1.1,OH1.2,OH1.3], [F20-OH4] | Wood floors-on-ground serving as an env sep on OS2.3, OP2.3 and OH1 | 1141 |
| 9.23.2.1.(1) | [F20-OS2.1], [F20,F22-OS2.5], [F20,F22-OS2.3], [F20-OP2.1], [F20,F22-OP2.4,OP2.5], [F20,F22-OP2.3], [F22-OH4], [F20,F22-OS1.2], [F22-OS3.1], [F22-OS3.7] | Env sep, floors and fire resistance notes as printed; egress walls on OS3.7 | 1167 |
| 9.23.4.2.(1) and (2) | [F20-OS2.1,OS2.5], [F22-OS2.4,OS2.5], [F20,F22-OS2.3], [F20-OP2.1,OP2.5], [F22-OP2.4,OP2.5], [F20,F22-OP2.3], [F20,F22-OH1.1,OH1.2,OH1.3], [F22-OH4], [F20,F22-OS1.2], [F22-OS3.1], [F22-OS3.7] | Env sep, floors, fire resistance and egress walls as printed | 1171 |
| 9.23.4.2.(3) and (4) | [F20-OS2.1,OS2.3,OS2.5], [F20-OP2.1,OP2.3,OP2.5] | none | 1171 |
| 9.23.10.1.(1) | [F20-OS2.1,OS2.5], [F22-OS2.5], [F20,F22-OS2.3], [F20-OP2.1,OP2.5], [F22-OP2.4,OP2.5], [F20,F22-OP2.3], [F20,F22-OH1.1,OH1.2,OH1.3], [F22-OH4], [F20,F22-OS1.2], [F22-OS3.1], [F22-OS3.7] | Notes refer to elements, floors and egress walls as printed | 1180 |
| 9.23.10.2.(1) | Same pair set as 9.23.10.1.(1) | Notes refer to walls, as printed (for example "walls that support or are part of an environmental separator") | 1180 |
| 9.23.13.1.(2) | [F20-OS2.1,OS2.3,OS2.5], [F22-OS2.3,OS2.4,OS2.5], [F20-OP2.1,OP2.3,OP2.5], [F22-OP2.3,OP2.4,OP2.5], [F20,F22-OH1.1,OH1.2,OH1.3], [F20,F22-OS1.2], [F22-OS3.1], [F22-OS3.7], [F20,F22-OH4] | Fire resistance; walls that support floors; egress walls, as printed | 1186 |
| 9.23.14.11.(1) | [F20-OS2.1,OS2.3,OS2.5], [F22-OS2.3,OS2.5], [F20-OP2.1,OP2.3,OP2.5], [F22-OP2.3,OP2.5], [F20,F22-OH1.1,OH1.2,OH1.3], [F20,F22-OS1.2] | Fire resistance note as printed | 1189 |
| 9.23.14.11.(3) | [F20-OS2.1,OS2.3,OS2.5], [F22-OS2.3,OS2.5], [F20-OP2.1,OP2.3,OP2.5], [F22-OP2.3,OP2.5] | none | 1189 |

Only sentence (1) has a pair set for 9.23.10.2. In Table 9.38.1.1, the printed block for that article on PDF p.1180 has no sentence (3). See the edition note below.

### Unattributed sentences and roots
Codedb status is taken from the sentence records. "None" means the sentence has no row in the attribution table. The root suggestion is codedb's own label and is not an attribution.
- Div B 9.4.1.1.(1) to (3): none, no root. These sentences choose the design route. The Part 4 pairs above apply when Part 4 is used.
- Div B 9.4.2.1.(1): none. Codedb's heuristic root is 9.4.3.1.(1), which is a suggestion only. The scope test is applied to the whole Subsection.
- Div B 9.23.1.1.(1) and (2): none. Scope sentences carry no pairs.
- Div B 9.23.13.1.(1) and 9.23.13.2.(1): none. These are applicability sentences. Their bracing options are attributed through the sentences that follow.
- Div B 9.23.14.11.(2): none. Codedb root is 9.23.14.11.(1) as a referenced article. The joint connection rules are in Subsection 4.3.1, so the pairs come from Part 4 and not from this row.
- Div B 9.23.10.3.(2): none. Codedb root is 9.23.10.1.(1) as a referenced article.
- Div B 9.15.2.4.(1): clause-level attribution sits on clause (a). Clause (b), which refers to Part 4, is not a separate row.

### Edition note on the NRC paper
The NRC paper "NRC-Canadas-Objective-Based-Codes" (reference/text) reproduces a bracing example from an older numbering. Its pairs for that bracing sentence do not match the 2023 printed rows above. Its intent statement and application statement are also from the older edition. The bracing sentence numbered in that paper does not exist in NBC(AE) 2023, where the article has only sentence (1). Codedb returns no record for it, and the printed table on PDF p.1180 has only sentence (1). Treat the paper as an explanation of how attributions work, not as a source of 2023 pairs.

## Intent
The intent statements come from the NBC 2020 Intent Statements supplement. They explain why a provision exists. They are explanatory only and are not Alberta law. Codedb's intent comparison returns "match" for every provision below, which means the supplement lists the same objective and functional pairs as the 2023 printed table. That comparison covers pair sets only. It does not compare wording or Alberta amendments. Each paraphrase below states what the provision aims to limit.

### Part 4
- Div B, Sentence 4.1.2.1.(1). NBC 2020 Intent Statements, 4.1.2.1.(1) [PDF p.771]. Limits the chance that the listed loads are left out of the design, which could lead to structural failure (OS2), excessive deformation or stress that damages the building (OP2), or excessive vibration or deflection (OH4).
- Div B, Sentence 4.1.3.2.(1). NBC 2020 Intent Statements, 4.1.3.2.(1) [PDF p.773]. Limits the chance that member capacity and building stability fall short of the maximum expected loads, which could lead to failure (OS2) or to excessive deformation and stress (OP2).
- Div B, Sentence 4.1.3.5.(2). NBC 2020 Intent Statements, 4.1.3.5.(2) [PDF p.783]. Limits the chance that wind and gravity loads cause excessive lateral deflection, which could displace non-structural elements that then fall (OS2) or damage the building (OP2).
- Div B, Sentence 4.1.5.3.(1). NBC 2020 Intent Statements, 4.1.5.3.(1) [PDF p.791]. Limits the chance that live load ignores the expected accumulation and distribution of people and objects, including dynamic effects, or falls below the prescribed value (OS2, OP2, OH4).
- Div B, Sentence 4.1.6.2.(1). NBC 2020 Intent Statements, 4.1.6.2.(1) [PDF p.808]. Limits the chance that a snow load calculation misses the factors that govern snow accumulation and distribution (OS2, OP2).
- Div B, Sentence 4.1.8.5.(1). NBC 2020 Intent Statements, 4.1.8.5.(1) [PDF p.887]. Limits the chance that earthquake loads are calculated without the reliability level suited to the use and occupancy (OS2, OP2).
- Div B, Sentence 4.2.4.1.(1). NBC 2020 Intent Statements, 4.2.4.1.(1) [PDF p.964]. Limits the chance that foundation, excavation or retaining design is not based on a subsurface investigation and an accepted basis (OS2, OP2, OP4).

### Part 9
- Div B, Sentence 9.4.1.1.(1). NBC 2020 Intent Statements, 9.4.1.1.(1) [PDF p.1206]. States three things. Part 9 structural requirements apply. Accepted good engineering practice applies where construction does not comply with the Part 9 requirements. Part 4 is extended to cover those cases. This sentence has no pair rows in either the intent supplement or the 2023 table (codedb status none_both).
- Div B, Sentence 9.4.2.1.(1). NBC 2020 Intent Statements, 9.4.2.1.(1) [PDF p.1206]. States that the Part 9 snow and roof-load subsection applies to the stated light-frame constructions.
- Div B, Sentence 9.4.2.2.(1). NBC 2020 Intent Statements, 9.4.2.2.(1) [PDF p.1207]. Limits the chance that inaccurate snow load assumptions stop roofs and walls from resisting gravity, snow and rain loads, which could cause structural failure (OS2, OP2) or excessive movement and damage to roofing (OH1).
- Div B, Sentence 9.4.3.1.(1). NBC 2020 Intent Statements, 9.4.3.1.(1) [PDF p.1211 to 1212]. Limits excessive deflection of structural members. The stated harms include rainwater ingress at roof framing, damage to ceilings and to air or vapour barriers carried by the framing (OS2, OP2), springy or noticeably deformed floors (OH4), and falls from floors that deflect or vibrate (OS3).
- Div B, Sentence 9.4.4.1.(1). NBC 2020 Intent Statements, 9.4.4.1.(1) [PDF p.1213 to 1215]. Limits the chance that an inadequate footing design overloads the footings, causing soil subsidence that cracks foundations or the structure above (OS2, OP2, OH1, OH4, OS3).
- Div B, Sentence 9.15.2.4.(1). NBC 2020 Intent Statements, 9.15.2.4.(1) [PDF p.1564]. Limits the chance that wood-frame foundations perform well below expectations. That could leave them unable to carry vertical building loads or lateral earth loads and could damage the foundation and the structure above (OS2, OP2, OH1, OH4, OS3).
- Div B, Sentence 9.16.5.1.(1). NBC 2020 Intent Statements, 9.16.5.1.(1) [PDF p.1658 to 1660]. Limits the chance that floors-on-ground perform well below expectations and cannot resist gravity or lateral soil loads, which could damage the floors or foundation walls (OS2, OS3, OP2, OH1, OH4).
- Div B, Sentence 9.23.4.2.(1). NBC 2020 Intent Statements, 9.23.4.2.(1) [PDF p.2139 to 2141]. Limits the chance of excessively long spans, which could leave the members unable to resist lateral, gravity or wind uplift loads. The stated harms are collapse of wood-frame construction, failure of environmental separators, loss of fire resistance and floor problems (OS2, OP2, OH1, OH4, OS1, OS3).
- Div B, Sentence 9.23.13.1.(2). NBC 2020 Intent Statements, 9.23.13.1.(2) [PDF p.2352 to 2354]. Limits the chance that the framing cannot resist gravity and lateral loads, which could cause excessive racking, collapse of wood-frame construction, displacement or failure of environmental separation elements, and loss of fire resistance (OS2, OP2, OH1, OS1, OS3, OH4).
- Div B, Sentence 9.23.14.11.(1). NBC 2020 Intent Statements, 9.23.14.11.(1) [PDF p.2430 to 2431]. Limits the chance that truss design falls short of the specified strength and deflection criteria, which could leave the truss unable to resist gravity loads and could cause excessive roof deflection and collapse (OS2, OP2), and damage to fire-resistance assemblies (OS1).

### How to use an intent statement in review
An intent statement tells a reviewer why a provision exists. It does not replace the attributed pairs, and it does not show that a proposal meets them. The pairs in the Attributions section decide which objectives and functional statements a proposal must address. The intent explains what the reviewer should look for in the supporting analysis.

## Typical alternative solutions
Each route below is one that innovators bring to this topic, with the precedent or evaluation that already exists. The routes differ in how much proof they need. The next section sets that out.

1. Structural insulated panels (SIPs) and other engineered wall systems. A SIP is a sandwich panel with a rigid insulating core between two structural facings. STANDATA 19-BCV-020(REV1) (October 2021, marked archived, 2019 edition) accepted SIPs in Part 9 buildings in two ways: a CCMC evaluation used within its conditions, or an alternative solution prepared by a registered professional (STANDATA 19-BCV-020(REV1), conditions section). The CCMC snapshot in this repository lists Plasti-Fab's Insulspan Structural Insulated Panel (SIP) System as evaluation 13016-R, status Active (reference/data/ccmc-registry.json). A web search summary of an unofficial copy of the report reports it as keyed to the 2015 National Building Code (UNVERIFIED; see open questions 1 and 17). Other wall systems in the snapshot include precast insulated concrete wall panels (Superior Walls Xi, 13628-R). Flat-wall ICF units conform to CAN/ULC-S717.1 (Sentence 9.15.4.1.(1) [PDF p.927]), and above-grade flat ICF walls need at least 140 mm of concrete (Sentence 9.20.17.1.(1) [PDF p.952]). Whether a SIP wall falls inside the Section 9.23 wood-frame scope is a judgment that this sheet does not make. Sentence 9.23.1.1.(1) speaks of lumber frames of small repetitive members or engineered components at 600 mm or less, and a panel without repetitive studs does not obviously fit that description.
2. Engineered floor and roof components. I-joists, laminated veneer lumber (LVL), laminated strand lumber (LSL) and engineered trusses appear in the CCMC snapshot. Examples are Nordic I-Joist Series (13032-R), Pinkwood I-Joists (14001-R), AcuJoist (14508-R), Weyerhaeuser Microllam LVL (08675-R), Boise VERSA-LAM LVL (12472-R), Weyerhaeuser TimberStrand LSL (12627-R), West Fraser LVL (12904-R) and Tolko T-TEC LSL (14476-R). Truss plates are listed too, for example Alpine HS18 (13124-L) and Simpson AS-20 (13326-L). Each evaluation sets its own conditions, which must be checked against the project.
3. Span Book configurations beyond the Part 9 span tables. STANDATA 23-BCV-007 (May 2024) recognizes the Canadian Wood Council Span Book (2020 edition) values for joists, rafters and beams referenced in Article 9.23.4.2 (STANDATA 23-BCV-007, Variance section). The archived 19-BCV-012 (December 2019) did the same for the 2019 edition.
4. Permanent wood foundations with mechanically laminated timber panels. STANDATA 23-BCV-012R1 (May 2025) allows these foundations under Clause 9.15.2.4.(1)(a) when the design follows the document "Permanent Wood Foundations with Mechanically Laminated Timber Panels for Part 9 Residential Buildings in Alberta" (December 2024), and the building permit drawings include the project-specific details (STANDATA 23-BCV-012R1, Variance section). That document is not in this repository, so its content is UNVERIFIED here. Projects outside it fall back to Part 4 under Clause 9.15.2.4.(1)(b).
5. Authenticated truss assemblies. The usual Part 9 truss route is now a truss design, with its interconnections, authenticated by a registered engineering professional (STANDATA 23-BCI-015R1, May 2025). The innovation sits in the layout and the connection design, which must be authenticated.
6. Off-site and modular construction. Buildings and panels constructed after 1 May 2024 and certified to CSA A277 by an organization accredited by the Standards Council of Canada are considered to comply (Division C, Sentence 2.5.1.1.(2) [PDF p.742]). STANDATA 23-BCV-002 (May 2024) also accepts CSA A660 certification for completed steel building modules, registered professional verification with seals, or AHJ inspection at the site (STANDATA 23-BCV-002, Variance section). The archived 19-BCV-021 described the 2019 version of these rules and cites 2019 section numbers, so do not cite it.
7. Welding and fabrication outside the usual certification. STANDATA 23-BCV-010R1 (April 2025) is a variance for skids that mount mechanical equipment and for proprietary structural components. It uses engineering quality controls in place of CSA W47.1 certification for the welding (STANDATA 23-BCV-010R1, Purpose section). The fabricator-qualification variances 23-BCV-010 (February 2025) and 19-BCV-025 (December 2022) are archived.
8. Multi-level storage racking. STANDATA 23-BCV-014 (March 2025) treats these systems as special and unusual structures under Div B, Article 3.2.2.2, with fire, egress and emergency conditions attached. Their structural design still runs through Div B, Article 4.4.3.1 [PDF p.513]. The fire and egress side belongs to other topics.
9. Taller walls. STANDATA 14-BCV-002R1 (tall wall generic engineered details, September 2017) was written for the Alberta Building Code 2014 and is archived. Do not cite it. Taller walls are a Part 4 design question now.
10. Practitioner context. Two transcripts in reference/youtube/ (a column base plate case, 6UEYhsqLu9g, and a steel frame grid layout case, ssM4E9uVtTY) show that base plate and grid decisions depend on the engineer's design. They are not code sources and are not cited for code claims. The transcripts for tNNQKiGer4k (1950s house framing) and IwfbxQQtYMo (exterior wall studs and steel superstructure) contain no transcript text in the repository, so they are not used.

## Usual mitigations and evidence
### What the submission must establish, by route
- Prescriptive Part 9 wood frame (Section 9.23). Show that every condition in Sentence 9.23.1.1.(1) is met, name the span table or Span Book configuration used, and name the bracing option from Article 9.23.13.1, 9.23.13.2 or 9.23.13.3 with the Sa(0.2) and 1-in-50 wind values that place the building there.
- Part 4 design. Provide the design by a registered professional (Division C, Sentence 2.4.1.2.(1) [PDF p.740]). The load inputs are the Part 4 loads in Subsections 4.1.4 to 4.1.8, with the location values from Appendix C and Div B, Subsection 1.1.3 (Div B, Sentence 1.1.3.1.(2) [PDF p.89]). Field review is part of the professional scope where the code or the AHJ requires it.
- CCMC evaluation. Provide the current evaluation report and show that the product is used within its conditions and limitations. Division A, Sentence 1.2.2.1.(2) [PDF p.38 to 39] lets an evaluation report from CCMC determine compliance. The archived SIP STANDATA asked for the report to go to the AHJ, with field inspections, as a condition of acceptance.
- Alternative solution. Provide the Code analysis required by Division C, Section 2.3.1.1. Sentence 2.3.1.1.(2) requires a Code analysis and information on special maintenance and commissioning. Sentence 2.3.1.1.(3) requires the analysis to identify the objectives, functional statements and acceptable solutions, and the assumptions, limits, testing procedures, engineering studies and performance parameters. Sentence 2.3.1.1.(4) requires the qualifications of the person taking responsibility for the design [PDF p.739].
- Off-site construction. Provide the CSA A277 certificate from an accredited organization for buildings constructed after 1 May 2024 (Sentence 2.5.1.1.(2) [PDF p.742]). Otherwise provide registered professional seals or AHJ inspections (STANDATA 23-BCV-002).
- Trusses. Provide the authenticated truss design, the interconnection design and the joint connection design under Div B, Subsection 4.3.1, and provide the authenticated drawings to the AHJ before the scheduled inspection (STANDATA 23-BCI-015R1, Interpretation section, items 1 to 4).

### Evidence confidence ladder for structural claims (strongest proof last)
1. A Part 9 table or a Span Book configuration recognized by 23-BCV-007. Conditions are fixed, and the reviewer checks the stated conditions.
2. A current CCMC evaluation report used within its conditions. The report is the evidence, and the reviewer checks conditions and limitations.
3. A registered professional's design under Part 4, with calculations, drawings, load inputs from the site's location values, and field review where required.
4. Certification by an accredited body for off-site construction (CSA A277 for buildings, CSA A660 for steel modules).
5. An alternative solution backed by testing or engineering studies, reviewed by a registered professional. This is the most work and the weakest standing with an SCO.

### Standards named in the code and in the variances (verified by reading the text)
CSA O86 (wood, Sentence 4.3.1.1.(1)); CSA S304 (masonry, Sentence 4.3.2.1.(1)); CSA A23.3 (concrete, Sentence 4.3.3.1.(1)); CSA S16 (structural steel, Sentence 4.3.4.1.(1)); CSA S136 (cold-formed steel, Sentence 4.3.4.2.(1)); CSA S157 and S157.1 (aluminum, Sentence 4.3.5.1.(1)); CAN/CGSB-12.20 and ASTM E1300 (glass, Sentence 4.3.6.1.(1)); CSA S406 (permanent wood foundations, Sentences 9.15.2.4.(1) and 9.16.5.1.(1)); CAN/ULC-S717.1 (flat-wall ICF units, Sentence 9.15.4.1.(1)); TPIC 2019 (trusses, Sentence 9.23.14.11.(1)); CWC 2014 Engineering Guide for Wood Frame Construction (Sentences 9.4.1.1.(1)(b) and 9.23.13.1.(2)); CSA A277 (Sentence 2.5.1.1.(2)); CSA W47.1 (cited in STANDATA 23-BCV-010 and 010R1). CSA A660 appears in STANDATA 23-BCV-002. I did not verify test-standard numbers for SIP or panel products in this corpus. The CCMC evaluation for each product lists the tests it relied on, and that list must be read from the report.

### Inspection and record expectations
- Permit Regulation section 22, as quoted in STANDATA 23-BCI-015R1, lets a permit issuer make a permit subject to conditions, including approval by a safety codes officer before any part of the building or system is covered or concealed (STANDATA 23-BCI-015R1, Permit Regulation section 22 as quoted). The STANDATA applies that condition to truss assemblies, where authenticated truss drawings may follow the permit application and must reach the AHJ before the framing inspection.
- Edmonton's Policy Bulletin B23-03 treats authenticated truss drawings as part of the permit application, with a transition period for some building types that the bulletin says will be published separately (first published 20 June 2025, last revised 4 February 2026).

## Engineering / professional triggers
The decision table lists project signals, whether a registered professional is required, the discipline, and the citation. "Depends" means the answer turns on a fact the tool must ask for. Division C, Sentence 2.4.1.1 is the general rule, and the other rows are specific to structure.

| Project signal | Registered professional required? | Discipline | Citation |
|---|---|---|---|
| Any design carried out under Part 4 of Division B | Yes. The designer must be a registered professional skilled in the work | Engineering (structural) | Div C, Sentence 2.4.1.2.(1) [PDF p.740] |
| Geotechnical load components and factored geotechnical resistances at ultimate limit states | Yes. A registered professional determines them | Engineering (geotechnical) | Div B, Sentence 4.2.4.1.(3) [PDF p.507] |
| Permanent wood foundation designed under Part 4, installed in a building | Yes for field review. The owner must show before construction that a registered professional is retained for field review | Engineering | Div C, Sentence 2.4.1.2.(2) [PDF p.740] |
| Permanent wood foundation to CSA S406 (Div B, Clause 9.15.2.4.(1)(a)) | Depends on the permit authority and the drawings. The sentence does not itself require a professional | Depends | Div B, Clause 9.15.2.4.(1)(a) [PDF p.925] |
| Mechanically laminated timber permanent wood foundation under 23-BCV-012R1 | Depends. Inside the document, the STANDATA treats the foundation as Clause 9.15.2.4.(1)(a) work with project-specific drawings. Outside it, Part 4 applies, which needs a registered professional designer and field review (Div C, Sentences 2.4.1.2.(1) and (2)) | Engineering where Part 4 applies | 23-BCV-012R1, Variance section |
| Wood roof trusses in a Part 9 building (23-BCI-015R1 scope) | Yes. Trusses and truss assemblies must be designed and authenticated by a registered engineering professional, including interconnections. The STANDATA's Application line covers Part 9 buildings that do not require professional involvement under Division C, Section 2.4 (STANDATA 23-BCI-015R1, Application section). Rocky View County reads the requirement as applying to all Part 9 buildings from 1 March 2026, while Edmonton's permit requirement covers the listed building types (open question 16) | Engineering (registered engineering professional) | Div B, Sentence 9.23.14.11.(1) [PDF p.986]; 23-BCI-015R1, Interpretation section; Rocky View County building page, accessed 2026-10-19 |
| Wood roof trusses for single-family, semi-detached, and 3 or 4 unit rowhouse permits from 1 March 2026 (Edmonton) | Yes. Authenticated roof truss assemblies must accompany the permit application. Detached garages are excluded unless they have living space, attic storage or a loft | Engineering (Alberta-licensed) | Edmonton Policy Bulletin B23-03, first published 20 June 2025, last revised 4 February 2026 |
| Part 9 single-family dwelling or multiple-family dwelling of 4 units or fewer, within Div C, Sentence 2.4.1.1.(1) | No, under the general rule, except where Div C, Sentence 2.4.1.1.(4) applies | Depends on the AHJ | Div C, Sentences 2.4.1.1.(1) and (4) [PDF p.739 to 740] |
| Building outside the Sentence 2.4.1.1.(1) exemptions | Yes. Drawings and specifications must be authenticated by registered professionals qualified in the applicable architecture and engineering | Architecture and engineering as applicable | Div C, Sentence 2.4.1.1.(3) [PDF p.740] |
| Project size or complexity raises special safety concerns | The AHJ may require registered professionals to authenticate all or part of the drawings and perform field reviews | As required | Div C, Sentence 2.4.1.1.(4) [PDF p.740] |
| Authentication itself | Under the Architects Act or the Engineering and Geoscience Professions Act | As applicable | Div C, Sentence 2.4.1.1.(5) [PDF p.740] |
| Off-site building constructed after 1 May 2024 with a CSA A277 certificate from an SCC-accredited organization | Not separately required for compliance. The sentence treats such buildings as complying | CSA A277 accredited certifier | Div C, Sentence 2.5.1.1.(2) [PDF p.742] |
| Off-site building without the A277 route (STANDATA 23-BCV-002) | Depends on route. Verification by registered professionals needs drawings and letters bearing their seals or stamps. The AHJ inspection route needs no professional | Engineering or architecture, or the AHJ | 23-BCV-002, Variance section |
| Steel building modules certified to CSA A660 | The variance's first route is a Certificate of Design and Manufacturing Conformance from an accredited organization. The variance adds no separate professional step on that route | Accredited certifier | 23-BCV-002, Variance section |
| SIP walls, CCMC route | The archived 2019 STANDATA requires the CCMC report to be given to the AHJ and the installation to be field inspected. It notes that a registered professional's evaluation may be needed to show the CCMC conditions were met. The 2023 position is UNVERIFIED | Engineering | 19-BCV-020(REV1), conditions section (archived) |
| SIP walls, alternative solution route | Yes. The 2019 STANDATA required the alternative solution to be submitted by a registered professional | Engineering | 19-BCV-020(REV1), conditions section (archived) |
| Welded structural components outside the usual CSA W47.1 certification route (23-BCV-010R1) | Yes in the variance. Engineer authentication of the welding procedures and quality controls is part of the route | Engineering | 23-BCV-010R1, Purpose section |

### Where this tool stops
- It can say whether a registered professional is required, which discipline applies and which provision is the trigger.
- It cannot size a member, a footing, a connection, a bracing panel or a truss. Those are the registered professional's work under Part 4, and the code says so in Sentence 2.4.1.2.(1).
- It cannot decide that a SIP, I-joist, LVL or truss layout is adequate. It can check whether the CCMC report, the authenticated design or the certificate is present and matches the project.
- It cannot choose the snow, wind or seismic values for a site. Those come from Appendix C and Subsection 1.1.3 for the location, and the tool should ask for them.
- It cannot judge whether the practice of engineering is involved in a particular proposal. That question belongs to professional-involvement.

## Interactions with other topics
- professional-involvement: registered professional triggers for Part 4, stamps, field reviews and authentication. This sheet gives the structural triggers and the stopping points, and that sheet gives the general rule.
- evidence-and-conformity: CCMC reports, CSA A277 and A660 certificates, and the weight of each evidence type. The confidence ladder above is a structural view of that topic.
- process-and-admin: the variance form, Section C mapping and the permit conditions. Permit terms in STANDATA 23-BCI-015R1 are relevant there.
- code-structure-and-attribution: how Table 4.5.1.1 and Table 9.38.1.1 are read, the root-sentence rule for unattributed sentences, and the edition traps listed in this sheet.
- housing-secondary-suites-part9: single-family and small row houses and their structure, including the truss and span rules, which are the most common Part 9 structural questions.
- building-envelope-insulation-cladding: the environmental separator notes in the attribution rows, sheathing under Subsection 9.23.17, and the insulation role of SIP and ICF walls.
- fire-separations-and-spatial-separation: fire-resistance ratings of loadbearing assemblies, which the attribution rows reference through F20 and F22 with OS1.2. The ratings themselves are a fire question.
- combustible-construction-and-mass-timber: timber structures beyond Part 9 scope, mass timber systems, and combustible construction limits. Structural timber design under CSA O86 still runs through Subsection 4.3.1 here.
- egress-and-single-stair: walls and floors that carry egress openings and guard loads, which appear as separate rows in the attribution tables.
- occupancy-and-accessibility: multi-level storage racking treated as special and unusual structures (23-BCV-014), and relocatable industrial camp buildings in Part 10.
- hvac-ventilation-plumbing: equipment supports and the seismic anchorage of non-structural elements under Article 4.1.8.18.

## Common refusal / "more info" causes
- No location values. The ground snow load, 1-in-50 wind pressure and seismic values for the site are missing. Sentence 9.4.1.1.(3) sends these values to Subsection 1.1.3, and Sentence 1.1.3.1.(2) refers to Appendix C [PDF p.89].
- Part 9 table route used outside its conditions. Members spaced more than 600 mm apart, spans over 12.20 m, a floor live load over 2.4 kPa, or a structure that acts as a foundation (Sentence 9.23.1.1.(1) [PDF p.962]) without a Part 4 design by a registered professional.
- Bracing thresholds not checked. The Sa(0.2) and wind pressure decide between Article 9.23.13.1, 9.23.13.2 and 9.23.13.3. A project on a threshold without both values cannot be checked.
- Archived or superseded documents cited as current. Examples are 19-BCV-020 and 19-BCV-020(REV1) for SIPs, 19-BCV-021 for off-site review, 19-BCV-025 and the original 23-BCV-010 for fabricators, 23-BCB-002 for trusses, 19-BCV-012 for spans, and 14-BCV-002R1 and 14-BCV-005 from the 2014 code.
- Wrong edition numbering. The archived 2019 SIP STANDATA cites two Division C sentences by their 2019 numbers. Codedb finds no 2023 sentence with either number, so the 2019 numbers must not be carried forward. The NRC paper's bracing example uses sentence numbering that does not exist in the 2023 edition.
- Trusses without the full authenticated package. The truss layout, the individual truss designs and the interconnection design must each be authenticated, or the layout must be stamped (STANDATA 23-BCI-015R1, interpretation items 1 to 4). Edmonton requires the package from 1 March 2026 for the listed building types.
- Permanent wood foundations without the field review commitment. Division C, Sentence 2.4.1.2.(2) requires evidence before construction that a registered professional is retained for field review, where the foundation is designed under Part 4.
- MLTP foundations without project-specific drawings. 23-BCV-012R1 requires the permit drawings to show the project-specific details.
- SIP walls without a current CCMC report or without its conditions shown as met. The archived STANDATA asked for the report and field inspections as a condition, and the 2023 requirement needs checking.
- Off-site buildings without a route. A CSA A277 certificate from an accredited body is needed for the presumption in Sentence 2.5.1.1.(2), which applies to buildings constructed after 1 May 2024. Otherwise the registered professional seal route or the AHJ inspection route in 23-BCV-002 must be shown.
- Missing field review for Part 4 design. The file does not show who will field review the design where the code or the AHJ requires it (Division C, Sentences 2.4.1.2.(2) and 2.4.1.1.(4) [PDF p.740]).
- Bow-string, arch or semicircular roof trusses over 6 m. Div B, Sentence 9.4.2.2.(3) [PDF p.838] requires their snow loads to follow Div B, Subsection 4.1.6, not the Part 9 snow formula alone.

## Precedents
Status is taken from the local copy. "Marked archived" means the archive footer appears on the pages in reference/text/. Live status must be checked before a precedent is cited as current (see open questions).

| Precedent | Subject | Issued | Status in local copy | Use here |
|---|---|---|---|---|
| STANDATA 23-BCV-007 | Maximum span values for joists, rafters and beams | May 2024 | No archive mark | Recognizes the Canadian Wood Council Span Book (2020) configurations under Article 9.23.4.2 |
| STANDATA 23-BCV-012R1 | Permanent wood foundations with mechanically laminated timber panels | May 2025 | No archive mark | Allows MLTP foundations under Clause 9.15.2.4.(1)(a) when the Dec 2024 document is followed |
| STANDATA 23-BCV-002 | Review of off-site constructed buildings | May 2024 | No archive mark | CSA A277 presumption, CSA A660 route, professional verification route, AHJ inspection route |
| STANDATA 19-BCV-021 | Off-site review of buildings (2019 edition) | Jan 2022 | Marked archived | Superseded by 23-BCV-002. Uses 2019 numbering for its Division C off-site provisions. Do not cite as current |
| STANDATA 19-BCV-020 and 19-BCV-020(REV1) | Structural insulated panels in Part 9 (2019 edition) | Oct 2021 (REV1) | Marked archived | Historical CCMC and alternative solution conditions for SIPs. The 2023 position is UNVERIFIED |
| STANDATA 23-BCI-015R1 | Design of wood trusses for roof assemblies in Part 9 buildings | May 2025 | No archive mark | Effective 1 March 2026 according to Rocky View County and APEGA (both 2026, accessed 2026-10-19). Truss design and interconnections authenticated by a registered engineering professional |
| STANDATA 23-BCI-015 | Wood roof truss systems in Part 9 buildings | Feb 2025 | No archive mark | Earlier version of the same number. The R1 revision is the later version |
| STANDATA 23-BCB-002 | Roof truss layout for one- and two-family dwellings | Aug 2024 | Marked archived | Superseded. Do not cite |
| STANDATA 23-BCB-002R1 | Roof trusses for one- and two-family dwellings | Aug 2025 | No mark in the local copy | Archived as of 28 Feb 2026 according to Rocky View County (accessed 2026-10-19) and Edmonton's B23-03 (last revised 4 Feb 2026). The Alberta index page does not list individual documents, so the primary record is unconfirmed |
| Edmonton Policy Bulletin B23-03 | Roof truss engineering requirements for new construction building permits | First published 20 June 2025; last revised 4 Feb 2026 | Current (local copy) | Authenticated truss assemblies with permit applications from 1 March 2026 for single-family, semi-detached and 3 or 4 unit rowhouse projects. The bulletin names the STANDATA as "23-BCI-05R1". The STANDATA is 23-BCI-015R1, so treat the bulletin's reference as a typo |
| STANDATA 23-BCV-010 | Engineer authentication for the qualification of structural steel fabricators (CSA W47.1 alternative) | Feb 2025 | Marked archived on all five pages | Do not cite as current |
| STANDATA 23-BCV-010R1 | Engineer's authentication for welding procedures (skids and proprietary structural components) | Apr 2025 | No mark | Current scope in the local copy |
| STANDATA 19-BCV-025 | Engineer authentication for structural steel fabricators (2019 edition) | Dec 2022 | Marked archived | Superseded by 23-BCV-010 |
| STANDATA 23-BCV-014 | Multi-level storage racking systems | Mar 2025 | No mark | Treats these racks as special and unusual structures under Div B, Article 3.2.2.2. Fire and egress topic, with structural design under Div B, Article 4.4.3.1 |
| STANDATA 14-BCV-002R1 | Tall wall generic engineered details (2014 code) | Sep 2017 | Marked archived | Do not cite |
| STANDATA 14-BCV-005 | CSA-A277-16 procedure for prefabricated buildings (2014 code) | May 2017 | Marked archived | Do not cite. Use 23-BCV-002 |
| STANDATA 19-BCV-012 | Spans for joists, rafters and beams (2019 edition) | Dec 2019 | Marked archived | Superseded by 23-BCV-007 |
| CCMC registry snapshot | 462 product records (reference/data/ccmc-registry.json) | Snapshot | Snapshot, not a live query | Structural records cited in Typical alternative solutions. Verify each number live before use |

No Calgary structural precedent was found in research/precedents/index.json. Calgary SPV-001 concerns zero lot line setbacks, which belong to fire-separations-and-spatial-separation. In Edmonton, B23-03 is the only structural policy in the index. B19-03 (area separation walls) and B23-05 (Sentence 9.9.4.4) are not structural.

## Worked example
This is a hypothetical case, not a real project. A manufacturer, called Northwind Panels here, proposes a factory-built SIP wall system for two-storey single-family houses in Edmonton. The houses have a concrete basement, engineered floor joists and engineered wood trusses. The wall system is the only non-standard element.

### Intake and classification
- Building. A two-storey single-family dwelling is a Part 9 building. Division A, Sentence 1.3.3.3.(1) applies Part 9 to buildings of 3 storeys or less and 600 m² or less in residential occupancies [PDF p.40].
- Location. The ground snow load, 1-in-50 wind pressure and seismic Sa(0.2) for Edmonton come from Appendix C and Div B, Subsection 1.1.3 (Div B, Sentence 1.1.3.1.(2) [PDF p.89]). They are not supplied in this sheet, and the tool should request them rather than infer them.
- Wall system. The SIP is the exterior wall. It also carries the floor and roof loads, so it is structural as well as an envelope element.
- Roof. Engineered wood trusses, so the Part 9 truss rules apply.
- Foundation. A concrete basement. The wall system does not change the foundation route.

### Route decision
1. Is the SIP wall inside Section 9.23? Not clearly. Sentence 9.23.1.1.(1) describes lumber frames of small repetitive members, or engineered components, spaced 600 mm or less [PDF p.962]. A SIP is neither described nor clearly covered, so the tool should flag the question and not decide it. The conservative path is outside Section 9.23. That means Part 4 design (Sentence 9.23.1.1.(2) [PDF p.962], and Sentence 9.4.1.1.(1)(c) [PDF p.836 to 837]).
2. Is there a current CCMC evaluation? The snapshot lists Insulspan Structural Insulated Panel (SIP) System, 13016-R, as Active. Its conditions and limitations must be read from the live evaluation before any use. That check is UNVERIFIED in this sheet. Division A, Sentence 1.2.2.1.(2) [PDF p.38 to 39] allows an evaluation report to be used in determining compliance. A web search summary of an unofficial copy of the report says it was first issued in October 2001, last re-evaluated in September 2018, and keyed to the 2015 National Building Code. That copy's text could not be read in this session. Whether a 2015-keyed evaluation supports compliance with NBC(AE) 2023 is not settled by the sources read here, so it must be checked on the official CCMC listing (open question 17).
3. If the CCMC route applies, the archived 2019 SIP STANDATA shows what the AHJ asked for: the report, field inspections of the installation, and a registered professional's letters where needed. The 2023 version of that expectation must be checked.
4. If the CCMC route does not apply or its conditions are not met, the path is an alternative solution under Division C, Section 2.3.1.1 [PDF p.739]. The submission needs a Code analysis (Sentences 2.3.1.1.(2) and (3)), special maintenance and commissioning information (Sentence 2.3.1.1.(2)(b)), and the qualifications of the person taking responsibility (Sentence 2.3.1.1.(4)). A registered professional prepares it, and Part 4 design requires a registered professional designer (Sentence 2.4.1.2.(1) [PDF p.740]).

### Section C table for the case
Pairs are read from the attribution tables. The "why" column paraphrases the NBC 2020 supplement and is explanatory only. The facings of the SIP are wood or steel. Their design is governed by Sentence 4.3.1.1.(1) (CSA O86) or Sentence 4.3.4.1.(1) (CSA S16). Those design-basis sentences have no pair rows.

| Article | Pairs (function and objective, as printed) | Why (paraphrased from the 2020 supplement) |
|---|---|---|
| Div B, Sentence 9.4.1.1.(1) [PDF p.836 to 837] | none in the table (codedb status none) | Route statement. Chooses between Part 9 rules, good engineering practice and Part 4 design. Cite it for the route, not for a pair |
| Div B, Sentence 4.1.2.1.(1) [PDF p.424] | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4], [F22-OH4] (Div B Table attribution, PDF p.513) | Listed loads must be taken into account, or the structure may fail, deform or vibrate |
| Div B, Sentence 4.1.3.2.(1) [PDF p.426] | [F20-OP2.1], [F22-OP2.4], [F20-OS2.1] (Div B Table attribution, PDF p.513) | Member capacity and stability must resist the maximum expected loads |
| Div B, Sentence 4.1.3.5.(2) [PDF p.429] | [F22-OS2.3,OS2.4], [F22-OP2.4] (Div B Table attribution, PDF p.514) | Wind and gravity loads must not cause excessive lateral deflection that damages or drops elements |
| Div B, Sentence 4.1.6.2.(1) [PDF p.437] | [F20-OS2.1], [F20-OP2.1], [F22-OP2.4] (Div B Table attribution, PDF p.515) | The snow calculation must capture the factors that drive accumulation and distribution |
| Div B, Sentence 4.1.8.5.(1) [PDF p.482] | [F20-OS2.1], [F20-OP2.1,OP2.3], [F22-OP2.4] (Div B Table attribution, PDF p.519) | The importance factor sets the reliability level for the use and occupancy |
| Div B, Sentence 4.2.4.1.(1) [PDF p.507] | [F20-OS2.2,OS2.6], [F21-OS2.6], [F20-OP2.2], [F21-OP2.5], [F21-OP4.1,OP4.4] (Div B Table attribution, PDF p.522) | Foundation design rests on a subsurface investigation and an accepted basis |
| Div B, Sentence 9.4.2.2.(1) [PDF p.837] | [F20-OS2.1,OS2.3], [F22-OS2.3], [F20-OP2.1,OP2.3], [F22-OP2.3], [F22-OH1.1,OH1.2,OH1.3] (Div B Table attribution, PDF p.1120) | Snow load assumptions must not stop roofs and walls carrying gravity, snow and rain. Use only where the Part 9 snow rules apply, not for a Part 4 design |
| Div B, Sentence 9.4.3.1.(1) [PDF p.838] | [F22-OS2.3], [F22-OP2.1,OP2.4], [F22-OP2.3], [F22-OH4], [F22-OS3.1], [F22-OS3.7], [F22-OH1.1,OH1.2,OH1.3] (Div B Table attribution, PDF p.1120) | Deflection limits protect ceilings and barriers, floor comfort and against falls |

Scope gate. Div B, Sentence 9.23.1.1.(1) [PDF p.962] decides whether Section 9.23 applies at all. The SIP wall needs a route statement here, not a pair, because the scope sentence has no pair row.

Intent citations for the rows above (the Why column paraphrases them; explanatory only): NBC 2020 Intent Statements, 4.1.2.1.(1) [PDF p.771]; NBC 2020 Intent Statements, 4.1.3.2.(1) [PDF p.773]; NBC 2020 Intent Statements, 4.1.3.5.(2) [PDF p.783]; NBC 2020 Intent Statements, 4.1.6.2.(1) [PDF p.808]; NBC 2020 Intent Statements, 4.1.8.5.(1) [PDF p.887]; NBC 2020 Intent Statements, 4.2.4.1.(1) [PDF p.964–965]; NBC 2020 Intent Statements, 9.4.2.2.(1) [PDF p.1207]; NBC 2020 Intent Statements, 9.4.3.1.(1) [PDF p.1211–1212].

### Evidence checklist for the case
- CCMC report: number, status, conditions and limitations, and the test standards it relies on. Read live. Not verified here.
- Drawings and details: panel sizes, facings, core, connections and fastening. The archived STANDATA's Appendix A lists these items and is a useful checklist even though it is archived.
- Code analysis: the sections affected. The archived STANDATA's Appendix A lists Part 3 Sections 3.1.5 (noncombustible construction) and 3.1.7 (fire-resistance ratings), and Part 9 Sections 9.4 (structural), 9.10 (fire protection) and 9.25 (heat transfer, air leakage and condensation).
- Professional documents: stamped drawings, a field review plan and a statement of the registered professional's responsibility (Sentence 2.4.1.2.(1) [PDF p.740]). Sentence 2.4.1.1.(3) does not apply to this exempt single-family house, so it is not cited here.
- Location values for Edmonton from Appendix C.
- Trusses: the authenticated truss design and interconnection design (STANDATA 23-BCI-015R1), and the authenticated drawings for the Edmonton permit package (Bulletin B23-03).

### What the tool does and does not do in this case
- It classifies the house as Part 9, states the route decision, lists the Section C rows above, requests the location values and the CCMC report, and marks the professional triggers.
- It does not confirm the SIP's structural or fire performance, size the panels, or decide that the CCMC conditions are met.

## Open questions / uncertainty
1. Current SIP position for NBC(AE) 2023. The 2019 variance is archived. Neither the repository nor a web search found a 2023 SIP STANDATA. The Alberta STANDATA index page, as summarized on fetch (accessed 2026-10-19), says that once a new code takes effect, existing STANDATA are deemed obsolete and cannot be used for new construction. Read with the archive footers, that points to the 2019 variance being unusable for new construction. The index does not list documents individually, so the status of the SIP routes under the 2023 edition remains UNVERIFIED.
2. Archive status of 23-BCB-002R1. The local copy has no archive mark. Edmonton's B23-03 (local copy, last revised 4 February 2026) and Rocky View County's building page (accessed 2026-10-19) both say it is archived as of 28 February 2026. The Alberta index page does not list individual documents, so the primary Alberta record remains unconfirmed.
3. Edmonton's bulletin reference. B23-03 names the STANDATA "23-BCI-05R1". The STANDATA in the repository is 23-BCI-015R1. The City should confirm the intended reference.
4. Span Book values. STANDATA 23-BCV-007 recognizes the Span Book (2020). The Span Book itself is a paid publication and its tables are not in this repository, so no Span Book values are stated here.
5. MLTP foundation document. The University of Alberta document of December 2024, which 23-BCV-012R1 requires, is not in the repository. Its content is UNVERIFIED.
6. Standards not in the repository. CSA O86, S16, S136, S157, S304, A23.3, S406, A277, A660, W47.1, W59 and TPIC 2019, and the CWC 2014 Engineering Guide, were checked only as far as the code and STANDATA text names them. Their contents are UNVERIFIED.
7. CCMC snapshot. The records are from reference/data/ccmc-registry.json. Live verification was not possible in the precedent index, so each number needs a live check.
8. Climatic values. The Appendix C values for Edmonton and other Alberta locations are not transcribed. Any load calculation needs them.
9. Table values. The span tables (Article 9.23.4.2), the bracing tables (Article 9.23.13.5 and 9.23.13.6 and Table 9.23.3.5.-A), Table 4.1.5.3, Table 9.4.3.1, Table 9.4.4.1 and the footing and wall tables are not transcribed. This sheet cites each table only through the sentence that names it.
10. SIP and Section 9.23 scope. Whether a SIP wall falls within Sentence 9.23.1.1.(1) is a judgment for the registered professional and the AHJ. This sheet does not make it.
11. NRC paper numbering. The NRC paper's bracing example is from an older numbering and is not a source for 2023 pairs. Its intent and application statements are not used.
12. Intent comparison scope. Codedb's "match" status compares pair sets. It does not compare wording or Alberta amendments.
13. Practitioner transcripts. 6UEYhsqLu9g and ssM4E9uVtTY have transcript text but are not code sources. tNNQKiGer4k and IwfbxQQtYMo have metadata only.
14. Fabricator qualification. The current route for qualifying structural steel fabricators is unclear. 23-BCV-010R1 addresses welding procedures for skids and proprietary components, and its archived predecessors covered fabricator qualification.
15. Calgary. No Calgary structural policy or SPV was found in the precedent index, so Calgary's structural practice is not covered here.
16. Truss scope. The STANDATA's Application line limits 23-BCI-015R1 to Part 9 buildings that do not require professional involvement under Division C, Section 2.4 (STANDATA 23-BCI-015R1, Application section). Rocky View County reads the requirement as covering all Part 9 buildings from 1 March 2026, and Edmonton's B23-03 limits its permit requirement to single-family, semi-detached and 3 or 4 unit rowhouse projects. The Alberta position should be confirmed with Municipal Affairs before the truss row is relied on for a particular building type.
17. CCMC 13016-R basis. A web search summary of an unofficial copy of the report says it was first issued in October 2001, last re-evaluated in September 2018, and keyed to the 2015 National Building Code. The copy's PDF could not be read in this session, and no official NRC or CCMC listing was found in the search results. These points are UNVERIFIED. Whether an evaluation keyed to an earlier national edition supports NBC(AE) 2023 compliance must be checked on the official CCMC listing before the SIP route is used.
## Sources
Repository documents read in this session. Page numbers are PDF pages.
- docs/contracts/briefs/PREAMBLE.md, docs/contracts/WAVE2-BRIEF.md, docs/contracts/briefs/WAVE2-TOPICS.md (section structural-and-framing), docs/contracts/CONTRACTS.md, WAVES.md, reference/README-challenge.md. The challenge scope PDF text in the README was read for the judging context.
- Method files: /Users/aamia/.codex/skills/t3-workflow/SKILL.md and references/routes.md; /Users/aamia/.codex/AGENTS.md; /Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/research/SKILL.md; /Users/aamia/.agents/skill-libraries/pstack/skills/unslop/SKILL.md.
- codedb/README.md and codedb/PROGRESS.md, for the CLI, the validator scope and the known false positives.
- Code database (codedb, NBC-AE build 2): lookup, children, the attributions for Div B Table 4.5.1.1 (PDF pp.513 to 524) and Table 9.38.1.1 (PDF pp.1120 to 1192), the definitions table (pages 68 to 81), the intent comparison, and the printed page 1180 checked with tools/codesearch.py page.
- NBC(AE) 2023 second printing (reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf; text in reference/text/). Division A Part 1 (PDF pages 38 to 40), Division B Part 1 climatic values (PDF page 89), Division B Part 4 (PDF pages 424 to 524), Division B Part 9 structural articles (PDF pages 831 to 1192 as cited), and Division C Sections 2.3, 2.4 and 2.5 (PDF pages 739 to 742).
- NBC 2020 Intent Statements (explanatory only), read through the codedb intents at the PDF pages cited in Intent.
- STANDATA local copies in reference/text/ (Alberta Municipal Affairs). Read in full: 23-BCV-002 (pp.1 to 2), 23-BCV-007 (pp.1 to 2), 23-BCV-012R1 (pp.1 to 2), 23-BCI-015R1 (pp.1 to 3), 19-BCV-020(REV1) (pp.1 to 6, archive footer), 19-BCV-021 (pp.1 to 2, archive footer), 23-BCB-002R1 (first pages, purpose and discussion). Header and purpose read, with archive footers counted: 23-BCV-010 (archive footer on all five pages), 23-BCV-010R1 (p.1), 23-BCV-014 (p.1), 23-BCI-015 (p.1), 23-BCB-002 (archive footer), 19-BCV-025 (p.1, archive footer), 19-BCV-012, 14-BCV-002R1 and 14-BCV-005 (headers and archive footers).
- Edmonton Policy Bulletin B23-03, local copy at reference/text/edmonton-policy-bulletin-b23-03-roof-truss-engineering.jsonl. The local copy is the text used; the online PDF could not be read by the web fetch tool.
- NRC Canada's objective-based codes, reference/text/NRC-Canadas-Objective-Based-Codes.jsonl, pages 9 to 11 (explanatory, 2005 numbering).
- CCMC registry snapshot, reference/data/ccmc-registry.json (462 records). Records cited: 13016-R (status Active in the snapshot), 13628-R, 13032-R, 14001-R, 14508-R, 08675-R, 12472-R, 12627-R, 12904-R, 14476-R, 13124-L, 12182-L, 13326-L and 13418-L.
- research/precedents/index.json, for titles and statuses. No structural Calgary SPV is in it.
- Practitioner transcripts used for context only: reference/youtube/6UEYhsqLu9g/transcript.txt and reference/youtube/ssM4E9uVtTY/transcript.txt. Metadata only, no transcript: reference/youtube/tNNQKiGer4k/meta.json and reference/youtube/IwfbxQQtYMo/meta.json.
- Other fact sheets in research/facts/ were read for format and headings only. Their claims were not used. The evals/ and variants/ folders were not read.

Web sources, all accessed 2026-10-19:
- https://www.alberta.ca/building-standata.aspx. The Alberta Building STANDATA index is grouped by year and lists no document numbers or status labels. The fetch summary reports this wording: "Once a new code comes into effect, all existing STANDATA are deemed to be obsolete and cannot be used for new construction." Verify the exact wording on the page.
- https://www.apega.ca/news/2026/02/23/clarified-standards-support-safety-in-truss-design. An article dated 23 February 2026 states that the guidance takes effect 1 March 2026 and ends a one-year grace period that began with a 2025 announcement. It names no archived document.
- https://www.rockyview.ca/build-plan-and-develop/building-and-renovating. Rocky View County building page, a municipal source and not an Alberta primary source. It states that STANDATA 23-BCI-015R1 applies to all Part 9 buildings from 1 March 2026, including one- and two-family dwellings, and that STANDATA 23-BCB-002R1 will be archived as of 28 February 2026.
- https://www.edmonton.ca/sites/default/files/public-files/PolicyBulletin-B23-03-Roof-Truss-Engineering-Requirements.pdf. The web fetch tool could not read the PDF text. The sheet relies on the local copy listed above.
- https://www.sips.org:443/documents/Insulspan-Evaluation-Report-CCMC-13016-R.pdf. An unofficial copy of CCMC report 13016-R, hosted by an industry association. The fetch tool could not read the text. A search summary reports first issue in October 2001, re-evaluation in September 2018 and a 2015 national code basis. These points are UNVERIFIED.
- Official CCMC or NRC listing for 13016-R. Searched; not located.
