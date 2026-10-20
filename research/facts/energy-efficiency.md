---
topic: energy-efficiency
scope: Energy efficiency under NBC(AE) 2023 2nd printing (Division B Part 9 Section 9.36 for Part 9 buildings, and the Part 3 and Part 5 provisions that reach larger buildings), the NECB 2020 national energy code and its adopted status in Alberta, STANDATA 23-BCV-003, and the performance path against a variance.
sources_checked:
  - NBC(AE) 2023 2nd printing (reference/codes): Division A 1.3.3.2, 1.3.3.3, 1.5.1.1, 2.1.1.2, 2.2.1.1, 3.2.1.1 and front matter; Division B 1.1.3.1 and Section 9.36 (Tables 9.36.2.6.-A and -B, 9.36.2.7.-A, 9.36.2.8.-A and -B, 9.36.7.2, 9.36.8.2, and attribution rows on PDF pages 1224 to 1228); Division C 2.2.1.2, 2.2.8.1 to 2.2.8.3, 2.3.1.1, 2.4.1.1, 2.4.2.1 to 2.4.2.3
  - NBC 2020 Intent Statements and NECB 2020 Intent Statements (explanatory only); NECB 2020 national text and Users Guide (reference/codes and reference/web/energy-efficiency)
  - Building Code Regulation AR 5/2024 (reference/text and reference/web; King's Printer extract, source p.1, p.3, p.4)
  - STANDATA 23-BCV-003, 23-BCB-001, and 23-BCI-022 (reference/precedents/alberta-standata); precedent index research/precedents/index.json for the historical variances
  - codedb README, sources.py, and validator.py (citation grammar)
  - Web, fetched 2026-10-19: promo.csagroup.org/NECB-online-training; cnrc.canada.ca NECB 2020 page; natural-resources.canada.ca energy-management-training page
last_verified: 2026-10-19
---
# Energy efficiency

## Progress
- Done (2026-10-19): every template section is written in order, with the citation conventions in CONTRACTS.md.
- Done: codedb validate research/facts/energy-efficiency.md exits 0 with 0 errors and 0 warnings (578 citation tokens; 121 distinct provision ids; the Part 3 route is covered in the benchmark section).
- Open for the parent: the 23-BCV-003 index record cites 9.36.2.8.(9) where the STANDATA cites Sentence 9.36.2.8.(1); the Tier 2 point value in Table 9.36.8.2 needs a visual check; NECB article numbers are not cited because codedb does not register the NECB; CSA course details are limited to the fetched pages. See Open questions.

## Plain-language summary
Energy efficiency rules limit the energy a building uses for heating, cooling, ventilation, and hot water. Heat moves through walls, floors, roofs, and windows. Air leaks through gaps. The code controls both.

Houses and small buildings use Division B Section 9.36 of NBC(AE) 2023. Sentence 9.36.1.3.(1) of Division B [PDF p.1069], lists three routes: the prescriptive or trade-off requirements in Subsections 9.36.2 to 9.36.4, the performance requirements in Subsection 9.36.5, or the NECB.

Larger buildings are outside Section 9.36. The National Energy Code of Canada for Buildings 2020 (NECB) covers them. Building Code Regulation AR 5/2024 declares the NECB in force in Alberta from May 1, 2024 (source p.3 and p.4).

The prescriptive path sets a minimum effective thermal resistance (RSI) for each assembly, by heating degree-day zone. In Zone 7A, the wall minimum is RSI 3.08 without a heat-recovery ventilator (Table 9.36.2.6.-A of Division B [PDF p.1073]). The trade-off path lets some above-ground opaque assemblies fall below their minimum if others are raised, within limits (Article 9.36.2.11. of Division B [PDF p.1080]). The performance path models the whole house and requires its annual energy use to stay at or below a reference house target (Sentence 9.36.5.3.(2) of Division B [PDF p.1091]).

Alberta treats Tier 1 as the minimum. The higher tiers in Subsections 9.36.7 and 9.36.8 are optional, and the regulation bars accredited agencies and municipalities from requiring a higher tier (source p.3 and p.4; STANDATA 23-BCB-001, source p.1).

Heated floors on the ground have their own province-wide variance. STANDATA 23-BCV-003 accepts RSI 1.32 (R-7.5) of under-slab insulation, where Table 9.36.2.8.-A requires RSI 2.84 for heated floors in Zone 7A and colder zones (STANDATA 23-BCV-003, source p.1 and p.3; Table 9.36.2.8.-A of Division B [PDF p.1076]).

This sheet treats a variance as the fallback for a case that no compliance route covers. The code does not say that in those words. A variance request goes in writing to the Provincial Building Administrator (Division C, Article 2.2.1.2., [PDF p.729]). A complete file shows which route applies and the documents that route needs. Whether the design performs is a question for the licensed professionals involved.

## When this topic applies
Trigger signals in a project description or application:
- Wording about insulation or thermal resistance: effective thermal resistance, RSI, R-value, continuous insulation, insulation below or around a slab, insulation below a heated floor.
- Heated floors on or in contact with the ground, hydronic or radiant floor heating, and embedded heating pipes or cables (Article 9.36.2.8. of Division B [PDF p.1075]).
- Energy compliance wording: energy model, reference house, house energy target, EnerGuide, energy performance tier, energy conservation points, performance path, percent improvement, percent heat loss reduction.
- Building type: a house or a house with a secondary suite (Sentence 9.36.1.3.(4) of Division B [PDF p.1069]); a Part 9 building with non-residential space above 300 m2 combined, or a medium-hazard industrial occupancy (Sentence 9.36.1.3.(6) of Division B [PDF p.1069]); a building to which Part 3 applies (Sentence 1.3.3.2.(1) of Division A [PDF p.39]).
- HVAC or water-heating equipment that is not one of the prescribed types. Sentence 9.36.3.1.(2) of Division B [PDF p.1081], and Sentence 9.36.4.1.(2) of Division B [PDF p.1087], send that equipment to the NECB.
- Exemption signals: a space that is not a conditioned space (Sentence 9.36.1.3.(7) of Division B [PDF p.1069]); a building not normally occupied, such as an equipment shelter with occasional service visits; a tent or membrane structure (STANDATA 23-BCI-022, source p.1 and p.2).
- Airtightness values in an energy model (Sentence 9.36.5.10.(9) of Division B [PDF p.1095]).

Near-misses that belong to another topic:
- Fire rating, flame spread, or combustibility of insulation or cladding: fire-separations-and-spatial-separation, combustible-construction-and-mass-timber, or building-envelope-insulation-cladding.
- Air barrier and vapour control as moisture protection: building-envelope-insulation-cladding. This sheet cites airtightness only as an input to the energy model.
- Ventilation for air quality, exhaust sizing, and make-up air: hvac-ventilation-plumbing. Sentence 9.36.3.1.(1) of Division B [PDF p.1081], limits Section 9.36.3 to the energy use of HVAC.
- Water supply, drainage, backflow, and pipe sizing: hvac-ventilation-plumbing. Article 9.36.4.1. of Division B [PDF p.1087] limits the energy scope to service water heating.
- Structural capacity of a slab or wall that carries added insulation: structural-and-framing.
- Electrical service, energy storage, and solar equipment: no topic slug covers these, and this sheet does not research them.

## Benchmark acceptable solutions
These are the recipes an applicant compares a proposal against. Each entry paraphrases the requirement.

Routes for Part 9 buildings:
- Sentence 9.36.1.3.(1) of Division B [PDF p.1069]: a building complies with (a) the prescriptive or trade-off requirements in Subsections 9.36.2 to 9.36.4, (b) the performance requirements in Subsection 9.36.5, or (c) the NECB.
- Sentence 9.36.1.3.(2) of Division B [PDF p.1069]: compliance with Subsection 9.36.7 or 9.36.8 is deemed to meet clause (1)(a) or (b).
- Sentences 9.36.1.3.(3) to (5) of Division B [PDF p.1069]: Subsections 9.36.2 to 9.36.4 apply to residential Part 9 buildings and to small business, mercantile, and low-hazard industrial Part 9 buildings. Subsections 9.36.5 and 9.36.7 apply only to houses (with or without a secondary suite) and to buildings with only dwelling units and common spaces of 20 percent or less of floor area. Subsection 9.36.8 applies only to residential Part 9 buildings.
- Sentence 9.36.1.3.(6) of Division B [PDF p.1069]: non-residential buildings above 300 m2 combined, and medium-hazard industrial buildings, comply with the NECB.

Envelope (prescriptive, Subsection 9.36.2):
- Sentence 9.36.2.6.(1) of Division B [PDF p.1073]: above-ground opaque assemblies meet Table 9.36.2.6.-A (no heat-recovery ventilator) or Table 9.36.2.6.-B (with a heat-recovery ventilator that conforms to Article 9.36.3.9.).
- Table 9.36.2.6.-A of Division B [PDF p.1073]: wall minimum RSI by zone, from Zone 4 to Zone 8: 2.78, 3.08, 3.08, 3.08, 3.85, 3.85. Table 9.36.2.6.-B, same page: 2.78, 2.97, 2.97, 2.97, 3.08, 3.08. Zone 4 is below 3000 degree-days, Zone 7A is 5000 to 5999, and Zone 8 is 7000 or more.
- Sentence 9.36.2.6.(4) of Division B [PDF p.1074]: the wall values also apply to skylight shafts, except tubular daylighting devices.
- Article 9.36.2.7. of Division B [PDF p.1074], Table 9.36.2.7.-A: fenestration and doors have a maximum U-value of 1.84 for Zones 4 and 5, 1.61 for Zones 6 and 7A, and 1.44 for Zones 7B and 8, or the energy rating the table lists instead.
- Sentence 9.36.2.8.(1) of Division B [PDF p.1075]: assemblies below grade or in contact with the ground meet Table 9.36.2.8.-A (no heat-recovery ventilator) or Table 9.36.2.8.-B (with one). Table 9.36.2.8.-A of Division B [PDF p.1076]: heated floors need 2.32 for Zones 4 to 6 and 2.84 for Zones 7A to 8.
- Article 9.36.2.8. of Division B [PDF p.1075]: a floor on the ground with embedded heating ducts, cables, or pipes is insulated under its full bottom surface, including the edges (Sentence 9.36.2.8.(5) of Division B [PDF p.1077]). Where only part of the slab is heated, the heated portion is insulated 1.2 m beyond its perimeter (Sentence 9.36.2.8.(6) of Division B [PDF p.1077]). Heated floors on the ground also need vertical perimeter insulation (Sentence 9.36.2.8.(7) of Division B [PDF p.1077]).
- Article 9.36.2.9. of Division B [PDF p.1077], and Article 9.36.2.10. of Division B [PDF p.1078]: airtightness and air barrier construction.
- Sentence 9.36.2.11.(2) of Division B [PDF p.1080]: one or more above-ground opaque assemblies may be below their Article 9.36.2.6. value if the traded areas are equal, other assemblies are raised above their value, and the sum of area divided by RSI does not exceed the all-compliant sum.
- Sentence 9.36.2.11.(6) of Division B [PDF p.1081]: a traded RSI may not fall below 55 percent of the requirement for above-ground walls and joist-type roofs, and below 60 percent for other opaque assemblies.
- Sentences 9.36.2.11.(7) and (8) of Division B [PDF p.1081]: embedded heating assemblies and doors or access hatches cannot be traded.

HVAC and service water heating (Subsections 9.36.3 and 9.36.4):
- Article 9.36.3.9. of Division B [PDF p.1083]: heat recovery from ventilation systems.
- Article 9.36.3.10. of Division B [PDF p.1084]: equipment efficiency, with Table 9.36.3.10. on the same page.
- Article 9.36.4.2. of Division B [PDF p.1088]: service water heaters, boilers, pool heaters, and storage tanks.

Performance path (Subsection 9.36.5, houses and the buildings listed in Sentence 9.36.1.3.(4)):
- Sentence 9.36.5.3.(1) of Division B [PDF p.1091]: performance calculations follow Subsection 9.36.5, or the EnerGuide Rating System version 15 and Sentence 9.36.5.3.(2).
- Sentence 9.36.5.3.(2) of Division B [PDF p.1091]: the proposed house's annual energy consumption may not exceed the house energy target of the reference house.
- Sentence 9.36.5.3.(3) of Division B [PDF p.1091]: the reference house takes its components from the prescriptive requirements for the climate zone.
- Sentence 9.36.5.3.(6) of Division B [PDF p.1091]: both houses use the same climatic data, soil conditions, operating schedules, and temperature set-points.
- Sentence 9.36.5.4.(8) of Division B [PDF p.1092]: if a computer program is used, it is tested to ANSI/ASHRAE 140, and variations from the recommended range are reported.
- Sentence 9.36.5.10.(9) of Division B [PDF p.1095]: the energy model uses 2.5 air changes per hour at 50 Pa, where the air barrier meets Subsection 9.25.3 and Articles 9.36.2.9 and 9.36.2.10, or a measured airtightness under Sentence 9.36.6.3.(1).

Tiered paths (optional above Tier 1):
- Article 9.36.7.2. of Division B [PDF p.1104]: energy performance must meet Table 9.36.7.2. for the percent heat loss reduction, and also for either the percent improvement or the percent house energy target.
- Table 9.36.7.2. of Division B [PDF p.1105]: five tiers. Tier 1 has no heat-loss target. Each higher tier sets stricter targets, and the table has separate blocks of rows for buildings above 300 m3 or of unknown volume, and for buildings at or below 300 m3.
- Article 9.36.8.2. of Division B [PDF p.1106]: compliance uses energy conservation measures from Articles 9.36.8.4 to 9.36.8.10 to accumulate the points that Table 9.36.8.2. sets, and still complies with Subsections 9.36.2 to 9.36.4 except where waived.
- Table 9.36.8.2. of Division B [PDF p.1106]: Tier 1 is the baseline with no points, and Tiers 3 to 5 read "Reserved". The Tier 2 point value is not stated in this sheet because the text layer does not show it cleanly (see Open questions).
- Article 9.36.8.5. of Division B [PDF p.1107]: above-ground wall measures earn points, and Sentence 9.36.8.5.(1) uses the Table 9.36.2.6.-B values as the baseline. Sentence 9.36.8.5.(7) allows wall RSI trading within the measure's target.

Larger buildings (NECB, national text as declared in force):
- NECB 2020 applies to new buildings described in NBC Division A Sentence 1.3.3.2.(1) and to additions (source p.26). Division A Sentence 1.3.3.2.(1) of Division A [PDF p.39], sets the Part 3 application.
- NECB Part 10 tiers (source p.269): Tier 1 allows a percent building energy target of 100 percent or less with 0 percent or more improvement. Tiers 2 to 4 tighten both measures (source p.269). Compliance is modelled under Part 8 (source p.269).
- Alberta's regulation makes Tier 1 the minimum in the NECB (source p.3 and p.4).

Equipment outside the prescribed types:
- Sentence 9.36.3.1.(2) of Division B [PDF p.1081]: HVAC systems, equipment, or techniques not described in Subsection 9.36.3 must meet the NECB.
- Sentence 9.36.4.1.(2) of Division B [PDF p.1087]: service water heating equipment or techniques not described in Subsection 9.36.4 must meet the NECB.

Part 9 or Part 3: which route applies.
- Part 9 covers buildings of three storeys or less and 600 m2 or less, for the listed residential and small occupancies (Sentence 1.3.3.3.(1) of Division A [PDF p.40]). Parts 3 to 6 apply to the buildings beyond those limits and to some other occupancies (Sentence 1.3.3.2.(1) of Division A [PDF p.39]).
- Sections 9.36.2 to 9.36.8 are written for Part 9 buildings (Sentences 9.36.1.3.(3) to (5) of Division B [PDF p.1069]), so a Part 3 building has no Section 9.36 route on the face of the code. This sheet reads the NECB as the energy route for Part 3 buildings. AR 5/2024 section 2(1) declares the NECB in force with respect to buildings (source p.3). The NECB applies to the buildings described in NBC Division A Sentence 1.3.3.2.(1) (source p.26).
- Part 5 governs environmental separation for Part 3 buildings and leaves the loss of heat energy to the NECB. Article 5.4.1.1. of Division B [PDF p.557] sets the air-barrier requirement. Its note on Sentence 5.4.1.1.(3) says that the loss of airborne heat energy is an energy performance issue addressed in the NECB (Note A-5.4.1.1.(3) of Division B [PDF p.581]).
- Part 10 structures, which are existing buildings, are exempt from some Part 9 envelope values (Sentence 9.36.2.1.(7) of Division B [PDF p.1070]). Their insulation is in Article 10.5.1.2. of Division B [PDF p.1505], which this sheet did not research.

## Attributions
Each pair below comes from the NBC(AE) 2023 attribution table (Table 9.38.1.1.) as read through codedb. The page given is the page of that table row.

Objective and functional statements used in this topic (Division A):
- Sentence 2.1.1.2.(6) of Division A [PDF p.67]: objective OE (including OE1 Resources and OE1.1 Excessive Use of Energy) applies only to residential Part 9 buildings, to business, personal services, mercantile, and low-hazard industrial Part 9 buildings up to 300 m2 combined, and to mixes of those. Larger buildings are not covered by the OE objective in this code.
- Article 2.2.1.1. of Division A [PDF p.72]: objective OE, Environment, is that the probability of the environment being affected in an unacceptable manner is limited. Div A [PDF p.73]: OE1 Resources, and OE1.1, "excessive use of energy", are the risks the code addresses.
- Article 3.2.1.1. of Division A [PDF p.81]: functional statements used in this topic. F90 limits uncontrolled air leakage through the building envelope. F91 limits uncontrolled air leakage through system components. F92 limits uncontrolled thermal transfer through the building envelope. F93 limits uncontrolled thermal transfer through system components. F95 limits unnecessary demand or consumption of energy for heating and cooling. F96 limits the same for service water heating. F98 limits equipment inefficiency. F99 limits system inefficiency. F100 limits the unnecessary rejection of reusable waste energy.

Pairs on the Division B provisions (article, pair, table row page):
- Sentence 9.36.2.2.(1) to (4), Div B: [F92-OE1.1] (Table 9.38.1.1., PDF p.1224).
- Sentence 9.36.2.6.(1) to (4), Div B: [F92-OE1.1] (Table 9.38.1.1., PDF p.1225).
- Sentence 9.36.2.8.(1) to (9), Div B: [F92-OE1.1] (Table 9.38.1.1., PDF p.1225). Sentence 9.36.2.8.(10) has no pair row.
- Sentence 9.36.2.11.(2) to (8), Div B: [F92-OE1.1] (Table 9.38.1.1., PDF p.1225).
- Sentence 9.36.5.3.(2) to (5), Div B: [F92,F93,F95,F96,F98,F99,F100-OE1.1] (Table 9.38.1.1., PDF p.1226). Sentence 9.36.5.3.(6), Div B: [F99-OE1.1] (Table 9.38.1.1., PDF p.1226).
- Sentence 9.36.5.10.(1), Div B: [F92,F95,F99-OE1.1] (Table 9.38.1.1., PDF p.1227).
- Sentence 9.36.6.3.(1), Div B: [F90-OE1.1] (Table 9.38.1.1., PDF p.1227).
- Sentence 9.36.7.2.(1), Div B: [F90,F91,F92,F93,F95,F96,F98,F99,F100-OE1.1] (Table 9.38.1.1., PDF p.1227).
- Sentence 9.36.8.2.(1), Div B: [F90,F91,F92,F93,F95,F96,F98,F99,F100-OE1.1] (Table 9.38.1.1., PDF p.1228).
- Sentence 9.36.8.5.(2) to (7), Div B: [F92-OE1.1] (Table 9.38.1.1., PDF p.1228).
- Sentences 9.36.1.3.(1) to (7) of Division B [PDF p.1069]: no attribution row. The compliance-route provision carries intent statements only (see Intent).

Attribution rows are not the same as compliance. A pair shows which objective and functional statement a provision serves. It does not show that a proposed alternative meets the provision. Application notes attached to some rows limit their scope and are not reproduced here.

## Intent
The NBC 2020 and NECB 2020 intent supplements are explanatory only. They are not Alberta law. Each entry paraphrases the supplement's stated purpose.

- NBC 2020 Intent Statements, 9.36.1.3.(1) [PDF p.3128]: the compliance options exist for energy-efficient housing and small buildings, and the NECB is extended to Part 9 buildings.
- NBC 2020 Intent Statements, 9.36.2.2.(1) [PDF p.3130]: thermal characteristics of materials are determined correctly, by calculation or by test, so that inadequate materials are not used.
- NBC 2020 Intent Statements, 9.36.2.6.(1) [PDF p.3136]: the probability of unacceptably low effective thermal resistance in above-ground opaque assemblies is limited. Low resistance would raise heat transfer through the envelope and energy use for heating and cooling.
- NBC 2020 Intent Statements, 9.36.2.8.(1) [PDF p.3140]: the same purpose applies to assemblies below grade or in contact with the ground.
- NBC 2020 Intent Statements, 9.36.2.11.(2) [PDF p.3149]: the trade-off option is an alternative compliance route for above-ground opaque assemblies when stated conditions are met. Its calculation limits keep traded areas from being mis-stated.
- NBC 2020 Intent Statements, 9.36.5.3.(1) [PDF p.3164]: the performance calculations exist to compare the proposed house with the reference house, and the EnerGuide Rating System is an acceptable alternative route under the performance subsection of Division B.
- NBC 2020 Intent Statements, 9.36.5.3.(2) [PDF p.3165]: the proposed building's energy use is kept at or below the reference building's use.
- NBC 2020 Intent Statements, 9.36.6.3.(1) [PDF p.3199]: airtightness used in the energy model is measured by a multi-point depressurization test.
- NBC 2020 Intent Statements, 9.36.7.2.(1) [PDF p.3201]: the basis of compliance for tiered performance, including the total conditioned volume.
- NBC 2020 Intent Statements, 9.36.8.2.(1) [PDF p.3203]: the basis of compliance for points-based tiers, so that the points are not over-counted.
- NBC 2020 Intent Statements, 9.36.8.5.(7) [PDF p.3206]: incorrect RSI values are not used to earn points where walls differ.
- NECB 2020 Intent Statements (explanatory only), source p.168: the tier entries limit the probability that a tier's building energy target exceeds its stated level, or that its percent improvement falls short.

Numbering warning. The NBC 2020 supplement's sentence numbers for 9.36.1.3 do not match the NBC(AE) 2023 sentences. Supplement item (5), which covers NECB use for non-residential space above 300 m2 and F2 occupancies (NBC 2020 Intent Statements, 9.36.1.3.(5) [PDF p.3129]), describes the content of Sentence 9.36.1.3.(6) in the 2023 text. Map supplement items to 2023 sentences by content, not by number.

## Typical alternative solutions
Some of these routes are in the code already, and need no variance. Others have been accepted as variances. Keep the two apart when building an application.

Code routes that applicants use before any variance:
- Envelope trade-off within one building, under Sentence 9.36.2.11.(2) [PDF p.1080] and the limits in Sentence 9.36.2.11.(6) [PDF p.1081]. The trade covers above-ground opaque assemblies only. It does not cover embedded heating assemblies or doors (Sentences 9.36.2.11.(7) and (8) of Division B [PDF p.1081]).
- Performance path for houses and the listed buildings, under Sentence 9.36.5.3.(2) [PDF p.1091]. The model replaces prescribed values with a whole-house comparison.
- Higher tiers. These are optional under Subsections 9.36.7 and 9.36.8, and a builder who chooses one must still meet the Tier 1 baseline (STANDATA 23-BCB-001, source p.1).
- Airtightness measured in place of the 2.5 air-change default, under Sentence 9.36.5.10.(9) of Division B [PDF p.1095], and the test method in Sentence 9.36.6.3.(1) of Division B [PDF p.1103].
- Equipment or techniques outside the prescribed list. These move the building to the NECB (Sentence 9.36.3.1.(2) of Division B [PDF p.1081]; Sentence 9.36.4.1.(2) of Division B [PDF p.1087]).

Variance precedents that deal with energy (index records; the STANDATA text was read for the current one only):
- Heated floor on the ground, current: STANDATA 23-BCV-003 (issued May 2024) accepts RSI 1.32 (R-7.5) under the slab in place of the Table 9.36.2.8.-A value for heated floors (source p.1 to p.3). The index record also lists a condition about not reusing an older frost-depth value. That condition is not in the STANDATA text this sheet read (see Open questions).
- Heated floor on the ground, historical (superseded edition): 14-BCV-019 under ABC 2014 and 19-BCV-005 under NBC(AE) 2019 allowed reduced under-slab values with different values above and below frost depth. Index summaries only. Do not carry these forward.
- EnerGuide route, historical (superseded edition): 14-BCV-017 under ABC 2014 and 19-BCV-004 under NBC(AE) 2019 accepted an EnerGuide version 15 route with added modelling and submission controls. The current text already includes that route in Sentence 9.36.5.3.(1) of Division B [PDF p.1091]. Index summaries only.

The index also records 19-BCV-023 (historical, superseded edition), which set roof insulation values for residential garages. It is not read in full here and is not relied on.

The variance files above show what applicants have asked for in this topic. This sheet does not use practitioner video material. The video synthesis file has an energy section, but its claims are not verified against the code here.

## Usual mitigations and evidence
Documents the code requires for a house modelled under Subsection 9.36.5:
- Sentence 2.2.8.1.(1) of Division C [PDF p.733]: the energy-compliance documents apply to houses, and to buildings with only dwelling units and common spaces of 20 percent or less of floor area, that are modelled under the performance subsection of Division B.
- Sentence 2.2.8.2.(1) of Division C [PDF p.733]: drawings and specifications show (a) the effective thermal resistance values and areas of opaque assemblies, (b) the U-value, solar heat gain coefficient, and areas of fenestration and doors, (c) the ratio of vertical fenestration and door area to gross wall area, (d) equipment ratings, energy sources, and types, (e) the design basis for ventilation rates, (f) measured airtightness where a test was run, and (g) any feature that accounts for a significant difference in house energy performance.
- Sentence 2.2.8.2.(4) of Division C [PDF p.733]: features of the proposed house that differ from the reference house are detailed in the specifications.
- Sentence 2.2.8.3.(1) and (2) of Division C [PDF p.734]: a house performance compliance calculation report is required for each design. It states the project information, the calculation tool and version, the climatic data identifier, the envelope, HVAC, and water-heating summaries, the annual energy consumption against the house energy target, any software adaptations, and a statement that the calculation complies with the performance subsection of Division B.

Test methods the code names:
- Sentence 9.36.2.2.(1) of Division B [PDF p.1070]: thermal characteristics of materials are determined by calculation or testing to the listed product standards, or to ASTM C177 or ASTM C518. Sentence 9.36.2.2.(2) sets the test temperatures.
- Sentence 9.36.2.2.(3) of Division B [PDF p.1070]: windows, doors, and skylights use CSA A440.2/A440.3, or NFRC 100 and NFRC 200.
- Sentence 9.36.2.2.(4) of Division B [PDF p.1070]: opaque assembly RSI comes from the calculation in Article 9.36.2.4., or from a hot-box test to ASTM C1363.
- Sentence 9.36.5.4.(8) of Division B [PDF p.1092]: a computer program used for compliance is tested to ANSI/ASHRAE 140, and variations from the recommended range are reported.
- Sentence 9.36.6.3.(1) of Division B [PDF p.1103]: airtightness used as a model input is measured by a multi-point depressurization test under CAN/CGSB-149.10.
- Article 9.36.5.10. of Division B [PDF p.1095]: model inputs for the proposed house match the proposed construction specifications, and a design airtightness is assigned until the measured value is available (Sentence 9.36.5.10.(10)).

Evidence ladder. This is the sheet's own ordering by how much a reviewer can check from the file. It is not a code ranking. Weakest first:
1. A value with no source.
2. A product rating or listing under a named standard, such as CSA A440.2 for windows (Sentence 9.36.2.2.(3) of Division B [PDF p.1070]).
3. A test of an assembly to a named test method, such as ASTM C1363 (Sentence 9.36.2.2.(4) of Division B [PDF p.1070]).
4. An energy model run by a program tested to ANSI/ASHRAE 140 (Sentence 9.36.5.4.(8) of Division B [PDF p.1092]), with inputs that match the drawings (Article 9.36.5.10. of Division B [PDF p.1095]).
5. A measured airtightness under CAN/CGSB-149.10 in place of the 2.5 air-change default (Sentence 9.36.6.3.(1) of Division B [PDF p.1103]).
6. Commissioning and maintenance information for the installed systems (Sentence 2.3.1.1.(2) of Division C [PDF p.739]).

Points a reviewer tends to test:
- The reference house and the proposed house use the same climate data, schedules, and set-points (Sentence 9.36.5.3.(6) of Division B [PDF p.1091]).
- The energy model's airtightness has a source. The default of 2.5 air changes per hour at 50 Pa applies only where the air barrier meets Subsection 9.25.3 and Articles 9.36.2.9 and 9.36.2.10 (Sentence 9.36.5.10.(9) of Division B [PDF p.1095]).
- Any feature that accounts for a significant difference in house energy performance is listed in the drawings and specifications (Sentence 2.2.8.2.(1), clause (g) of Division C [PDF p.733]).

## Engineering / professional triggers
Division C sets when a registered professional must be involved. The energy provisions do not add their own professional rule, except as noted below.

- Sentence 2.4.1.1.(1) of Division C [PDF p.739]: no registered professional is required for listed small buildings. The list covers a single-family dwelling, a multiple-family dwelling of four dwelling units or fewer, some small hotels and business, mercantile, and industrial buildings (by storey and area limits), farm buildings not for public use, and relocatable industrial camp buildings. Sentence (4) can still require involvement.
- Sentence 2.4.1.1.(3) of Division C [PDF p.739]: for any building outside Sentence (1), the drawings and specifications are authenticated by one or more registered professionals qualified in the appropriate combination of architecture and engineering. Energy-compliance drawings are part of those drawings.
- Sentence 2.4.1.1.(4) of Division C [PDF p.739]: the authority having jurisdiction may require registered professionals to authenticate all or part of the drawings and to do field reviews where the size or complexity of a project may give rise to special safety concerns.
- Sentence 2.4.1.1.(5) of Division C [PDF p.739]: authentication follows the Architects Act or the Engineering and Geoscience Professions Act.
- Article 2.4.2.1. of Division C [PDF p.741]: the coordinating-professional rules apply to a project within Sentence 2.4.1.1.(3). Sentence 2.4.2.2.(1) of Division C [PDF p.741], requires the owner, before applying for a permit, to retain a coordinating registered professional and the registered professionals of record for the design and field reviews.
- Sentence 2.3.1.1.(4) of Division C [PDF p.739]: a Code analysis for an alternative solution includes the qualifications, experience, and background of the person or persons who take responsibility for the design.
- Sentence 2.3.1.1.(6) of Division C [PDF p.739]: where more than one person takes responsibility for different aspects of the design, the applicant names one person to coordinate the design, the Code analysis, and the documentation.
- Sentence 2.2.1.2.(2) of Division C [PDF p.729]: a written variance request conforms to Section 2.3.

Energy-specific gaps:
- Neither the performance subsection of Division B (PDF pages 1090 to 1103) nor Division C Articles 2.2.8.1. to 2.2.8.3. (PDF pages 733 to 734) names who must prepare or sign the energy model or the house performance compliance calculation report. Whether Sentence 2.4.1.1.(3) of Division C [PDF p.739] reaches that report depends on the building. UNVERIFIED: whether that applies to any particular project.
- Whether building an energy model, or doing the trade-off arithmetic in Sentence 9.36.2.11.(2) of Division B [PDF p.1080], is the practice of engineering is a question for the licensing bodies under the Engineering and Geoscience Professions Act. This sheet does not decide it, and no licensing-body guidance was read.
- A file can show that a professional is named and that the stamped drawings exist. It cannot show that the energy design is correct. That judgement belongs to the professional, and the tool should stop at that point.

## Interactions with other topics
- [building-envelope-insulation-cladding](building-envelope-insulation-cladding.md): this sheet owns the energy reading of wall, roof, and slab values (Sentence 9.36.2.6.(1) of Division B [PDF p.1073] and Sentence 9.36.2.8.(1) of Division B [PDF p.1075]) and the energy-model airtightness inputs. The envelope sheet owns the placement, moisture, and fire side of the same assemblies. STANDATA 23-BCV-003 sits in both sheets.
- [hvac-ventilation-plumbing](hvac-ventilation-plumbing.md): a heat-recovery ventilator changes the wall minimum. Sentence 9.36.2.6.(1) of Division B [PDF p.1073], selects Table 9.36.2.6.-B when the ventilation system includes heat recovery under Article 9.36.3.9. In Zone 7A the wall minimum falls from RSI 3.08 to RSI 2.97. Equipment efficiency (Article 9.36.3.10. of Division B [PDF p.1084]) and service water heating (Article 9.36.4.2. of Division B [PDF p.1088]) belong to that sheet for installation questions.
- [housing-secondary-suites-part9](housing-secondary-suites-part9.md): a house with a secondary suite falls under Section 9.36 as a house (Sentence 9.36.1.3.(4) of Division B [PDF p.1069]). For the tiered path, Sentence 9.36.7.1.(2) of Division B [PDF p.1104], defines "house" to include a house with or without a secondary suite whose HVAC and water heating serve only the house, only the suite, or both, and which does not share occupied common spaces with other dwelling units or houses, except the suite. Fire-separation and suite-policy decisions do not appear in Section 9.36 and do not change this classification.
- [professional-involvement](professional-involvement.md): the registered-professional rules in Division C (Sentences 2.4.1.1.(1) to (5) of Division C [PDF p.739]) and the coordinating-professional rules (Article 2.4.2.1. of Division C [PDF p.741]) are cited there in full. This sheet cites them only where an energy document is involved.
- [process-and-admin](process-and-admin.md): the variance route belongs there. Sentence 2.2.1.2.(1) of Division C [PDF p.729], sends a written request to the Provincial Building Administrator, and Sentence 2.2.1.2.(5) of Division C [PDF p.729], makes a variance applicable throughout Alberta. The STANDATA variances and bulletins cited here are province-wide instruments. Transition timing for applications around the 2023 edition's coming-into-force date appears in the City of Calgary advisory B23-001 (index record; source p.1 and p.2). That advisory is non-binding and is not analysed here.
- [evidence-and-conformity](evidence-and-conformity.md): the documentation in Sentences 2.3.1.1.(2) to (5) of Division C [PDF p.739], and the energy-compliance documents in Sentences 2.2.8.2.(1) and 2.2.8.3.(2) of Division C [PDF p.733] and [PDF p.734], are the evidence the file must carry.
- [code-structure-and-attribution](code-structure-and-attribution.md): the OE objective applies only to the listed Part 9 buildings (Sentence 2.1.1.2.(6) of Division A [PDF p.67]). Sentence 1.5.1.1.(2) of Division A [PDF p.54], brings the NECB's objectives into play when a provision references it. Attribution rows are read as in the Attributions section above.
- [occupancy-and-accessibility](occupancy-and-accessibility.md): occupancy decides which energy route applies. Residential and small business occupancies fall under Part 9 (Sentence 9.36.1.3.(3) of Division B [PDF p.1069]). Medium-hazard industrial occupancies and non-residential space above 300 m2 go to the NECB (Sentence 9.36.1.3.(6) of Division B [PDF p.1069]). Part 3 scope comes from Sentence 1.3.3.2.(1) of Division A [PDF p.39], and Sentence 1.3.3.3.(1) of Division A [PDF p.40], sets the Part 9 limits.
- structural-and-framing: any change in wall or floor build-up that adds insulation also changes the structure. This sheet does not assess structural adequacy.

## Common refusal / "more info" causes
- No energy route is named. Sentence 9.36.1.3.(1) of Division B [PDF p.1069], requires a file to rely on one of three routes: prescriptive or trade-off, performance, or the NECB.
- The route does not fit the building. Subsections 9.36.5 and 9.36.7 apply only to houses and to buildings with only dwelling units and common spaces of 20 percent or less of floor area (Sentence 9.36.1.3.(4) of Division B [PDF p.1069]). Subsection 9.36.8 applies only to residential Part 9 buildings (Sentence 9.36.1.3.(5) of Division B [PDF p.1069]). Non-residential space above 300 m2 combined goes to the NECB (Sentence 9.36.1.3.(6) of Division B [PDF p.1069]).
- Trade-off arithmetic is missing. Sentence 9.36.2.11.(2) of Division B [PDF p.1080], needs equal traded areas, raised companion assemblies, and the area-over-RSI sum. Sentence 9.36.2.11.(6) of Division B [PDF p.1081], sets the 55 percent and 60 percent floors.
- Traded values fall below the floors. Traded RSI may not fall below 55 percent of the requirement for above-ground walls and joist-type roofs, or 60 percent for other opaque assemblies (Sentence 9.36.2.11.(6) of Division B [PDF p.1081]).
- Embedded heating or door assemblies are traded. Sentences 9.36.2.11.(7) and (8) of Division B [PDF p.1081], exclude them from the trade.
- The energy report is incomplete. Sentence 2.2.8.3.(2) of Division C [PDF p.734], lists the project information, calculation tool and version, climatic data identifier, envelope and equipment summaries, energy comparison, software adaptations, and compliance statement.
- Software is not shown to be tested. Sentence 9.36.5.4.(8) of Division B [PDF p.1092], requires ANSI/ASHRAE 140 testing for a computer program, and reporting of variations from the recommended range.
- Reference and proposed houses are modelled differently. Sentence 9.36.5.3.(6) of Division B [PDF p.1091], requires the same climate data, soil conditions, operating schedules, and set-points.
- Airtightness is asserted without support. Sentence 9.36.5.10.(9) of Division B [PDF p.1095], allows the 2.5 air-change default only where the air barrier meets Subsection 9.25.3 and Articles 9.36.2.9 and 9.36.2.10. Otherwise a measured value under Sentence 9.36.6.3.(1) of Division B [PDF p.1103], is needed. Sentence 9.36.5.10.(10) assigns a design value until the measured one exists.
- A heated floor on the ground is below the table value without the variance conditions. STANDATA 23-BCV-003 covers Part 9 buildings with a heated floor on the ground, either fully below or above the frost line, and sets RSI 1.32 (R-7.5) as the under-slab minimum (source p.3).
- A higher tier is treated as mandatory. The regulation bars a municipality or accredited agency from requiring one (source p.3 and p.4), and STANDATA 23-BCB-001 says the higher tiers are optional (source p.1).
- Tier 2 is claimed without listed measures. Sentence 9.36.8.2.(1) of Division B [PDF p.1106], requires the energy conservation measures in Articles 9.36.8.4 to 9.36.8.10 to supply the points.
- An earlier edition of the Alberta code or of the NECB is cited as current. Under the edition rule, the citable building code is NBC(AE) 2023, second printing. The NECB 2020 is in force by regulation (AR 5/2024, source p.3) and is cited here from the national text, with the Alberta variations in AR 5/2024 section 2. A file that relies on an earlier edition does not meet the edition rule.
- An exemption is claimed without the required information. Sentence 9.36.1.3.(7) of Division B [PDF p.1069], exempts spaces that are not conditioned spaces. STANDATA 23-BCI-022 (source p.1 and p.2) says the designer gives the authority having jurisdiction enough information to show why the building is exempt, and refers irregular cases to that authority.
- A variance request lacks the documentation that Division C Section 2.3 requires. Sentence 2.2.1.2.(2) of Division C [PDF p.729] requires conformance with Division C Section 2.3, and Sentence 2.3.1.1.(2) of Division C [PDF p.739] requires a Code analysis and the operating and commissioning information.

## Precedents
Current instruments, read at source:
- STANDATA 23-BCV-003, "Insulation below a heated floor", issued May 2024 by the Provincial Building Administrator. Province-wide. It applies to Part 9 buildings where a heating system creates a heated floor in contact with the ground, above or below the frost line. It sets RSI 1.32 (R-7.5) as the minimum under-slab insulation in that case (source p.1 to p.3). URL: https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/3915ba54-96dd-4c54-a9c1-63df5c917836/download/ma-standata-variance-building-23-bcv-003-2024-05.pdf (index record accessed 2026-10-18). Local copy: reference/precedents/alberta-standata/standata-nbc2023-variance-23-bcv-003.pdf. The STANDATA's own code reference is Sentence 9.36.2.8.(1). The index record cites 9.36.2.8.(9). See Open questions.
- STANDATA 23-BCB-001, "Energy efficiency Tier 1 of section 9.36", issued April 2024. It states that Tier 1 is the minimum province-wide standard for housing and small buildings, that the Subsections 9.36.2 to 9.36.4 and 9.36.5 routes are the minimum for Tier 1, and that the higher tiers under Subsections 9.36.7 and 9.36.8 are optional and not enforceable under the Safety Codes Act (source p.1). Page 2 lists the code references, including the airtightness choices in Sentence 9.36.5.10.(9). URL: https://open.alberta.ca/dataset/5cd7e000-4f7c-4188-b26f-11a16bbe43f8/resource/37c27a63-3517-4b03-b4e2-bd2733219caa/download/ma-standata-bulletin-building-23-bcb-001-2024-04.pdf (index record accessed 2026-10-18).
- STANDATA 23-BCI-022, "Energy efficiency exemptions for buildings", issued May 2025. It exempts industrial occupancies not normally occupied by persons, which store or shelter equipment, and tents and air-, cable-, or frame-supported membrane structures (source p.1 and p.2). It says the designer must give the authority having jurisdiction enough information, and that irregular cases go to that authority. URL: https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/f887c64c-068b-4b7d-852e-dfd56531807c/download/ma-standata-interpretation-building-23-bci-022-2025-05.pdf (index record accessed 2026-10-18).
- Building Code Regulation AR 5/2024: filed January 24, 2024, in force May 1, 2024 (King's Printer extract, source p.1; regulation source p.3 and p.4). Recorded URL: https://kings-printer.alberta.ca/documents/Regs/2024_005.pdf. This URL was not fetched on 2026-10-19. UNVERIFIED: its live status and any amendments.

Other energy-tagged records, not read in full:
- STANDATA 23-BCB-006, equipment efficiency metrics (SEER2 and HSPF2). Index summary only. Not relied on.
- STANDATA 23-BCE-001, errata before the second printing. Its source p.24 and p.25 contain energy cross-references to Section 9.36. The index record says the second printing controls. This sheet did not check those pages against the second printing.

Historical variances (superseded editions, index summaries only; do not carry forward):
- 14-BCV-017 (historical, ABC 2014) and 19-BCV-004 (historical, NBC(AE) 2019): EnerGuide version 15 energy-compliance route, with added modelling and submission controls.
- 14-BCV-019 (historical, ABC 2014) and 19-BCV-005 (historical, NBC(AE) 2019): reduced under-slab values for heated floors on the ground, with different values above and below frost depth.
- 19-BCV-023 (historical, NBC(AE) 2019): energy-table roof insulation values for flat or cathedral roofs above qualifying residential garages.

Other categories:
- Calgary and Edmonton policy solutions: none of the ten energy-tagged records in the precedent index is a Calgary SPV or an Edmonton policy. The City of Calgary advisory B23-001 covers transition timing and is noted under Interactions.
- CCMC numbers: the CCMC registry snapshot was not searched for this topic. No energy product number is cited here.

## Worked example
Scenario: a detached house in Zone 7A (5000 to 5999 degree-days, using the climatic values the authority having jurisdiction sets; Article 1.1.3.1. of Division B [PDF p.89]). The house has no heat-recovery ventilator. Above-ground walls total 100 m2. Table 9.36.2.6.-A requires RSI 3.08 for walls in Zone 7A (Div B [PDF p.1073]). The designer's framing layout gives 60 m2 of wall at effective RSI 2.80, which is short by 0.28 RSI, or about 9 percent. The numbers below are illustrative. This sheet does not design the house or run a model.

Route 1, trade-off within the envelope (no variance):
- Sentence 9.36.2.11.(2) of Division B [PDF p.1080], requires equal total traded areas (100 m2 before and after), at least one companion assembly raised above its Article 9.36.2.6. value, and a sum test. Here the companion is 40 m2 of wall at RSI 4.00.
- Sum test: 60 / 2.80 + 40 / 4.00 = 21.43 + 10.00 = 31.43. The all-compliant sum is 100 / 3.08 = 32.47. Since 31.43 is at or below 32.47, the test passes.
- Floor test: Sentence 9.36.2.11.(6), clause (a) of Division B [PDF p.1081]. The traded RSI may not fall below 55 percent of 3.08, which is 1.69. The 2.80 wall clears that floor.
- Result: the trade-off satisfies Sentence 9.36.1.3.(1), clause (a), of Division B [PDF p.1069], without a variance. The drawings must show each wall section's RSI and area, so a reviewer can repeat the sum.

Route 2, performance path (no variance if the model passes):
- The house is within Sentence 9.36.1.3.(4), clause (a) of Division B [PDF p.1069], so Subsection 9.36.5 is available.
- Sentence 9.36.5.3.(2) of Division B [PDF p.1091], requires the proposed house's annual energy use to stay at or below the reference house target. Sentence 9.36.5.10.(1) of Division B [PDF p.1095], models the proposed walls at their proposed RSI, so the 2.80 wall is tested in the whole-house model. The sheet found no per-assembly minimum in Subsection 9.36.5 (pages 1090 to 1103 were checked for minimum wording).
- Whatever the 2.80 wall loses in the model must be made up elsewhere, for example in airtightness, windows, or equipment. The sheet does not show whether that works for this house.
- Documents: the drawings and specifications under Sentence 2.2.8.2.(1) of Division C [PDF p.733], and the compliance report under Sentence 2.2.8.3.(2) of Division C [PDF p.734]. The program must be tested under Sentence 9.36.5.4.(8) of Division B [PDF p.1092]. Airtightness follows Sentence 9.36.5.10.(9) of Division B [PDF p.1095].
- If the model fails, the designer changes the design or moves to Route 3.

Route 3, variance (only if Routes 1 and 2 do not fit):
- A variance is needed here only if the house cannot use Routes 1 and 2. For example, the building is a Part 9 building whose common spaces exceed 20 percent of floor area, so Subsection 9.36.5 does not apply (Sentence 9.36.1.3.(4), clause (b) of Division B [PDF p.1069]), and the trade fails its sum test.
- The request goes in writing to the Provincial Building Administrator (Sentence 2.2.1.2.(1) of Division C [PDF p.729]). It conforms to Section 2.3 (Sentence 2.2.1.2.(2) of Division C [PDF p.729]), which means a Code analysis with the qualifications of the person responsible (Sentence 2.3.1.1.(4) of Division C [PDF p.739]).
- The Administrator may issue the variance with terms (Sentence 2.2.1.2.(4) of Division C [PDF p.729]). A variance issued under this Article applies throughout Alberta (Sentence 2.2.1.2.(5) of Division C [PDF p.729]).
- STANDATA 23-BCV-003 does not apply to this wall. It covers only under-slab insulation for heated floors on the ground.

Section C table for Route 3 (article, objective, function, intent). Each row carries one provision and its attribution pair.

| Article | Objective | Function | Intent |
|---|---|---|---|
| Sentence 9.36.2.6.(1) of Division B [PDF p.1073] | [F92-OE1.1] (Table 9.38.1.1., PDF p.1225): OE1.1, excessive use of energy | F92, uncontrolled thermal transfer through the building envelope (Div A, Article 3.2.1.1., [PDF p.81]) | NBC 2020 Intent Statements, 9.36.2.6.(1) [PDF p.3136]: limits the chance of unacceptably low above-ground RSI (explanatory) |
| Sentence 9.36.2.11.(2) of Division B [PDF p.1080] | [F92-OE1.1] (Table 9.38.1.1., PDF p.1225): OE1.1, excessive use of energy | F92 (Div A, Article 3.2.1.1., [PDF p.81]) | NBC 2020 Intent Statements, 9.36.2.11.(2) [PDF p.3149]: the trade-off is an alternative compliance route when stated conditions are met (explanatory) |
| Sentence 9.36.5.3.(2) of Division B [PDF p.1091] | [F92,F93,F95,F96,F98,F99,F100-OE1.1] (Table 9.38.1.1., PDF p.1226): OE1.1, excessive use of energy | F92, F93, F95, F96, F98, F99, F100 (Div A, Article 3.2.1.1., [PDF p.81]) | NBC 2020 Intent Statements, 9.36.5.3.(2) [PDF p.3165]: the proposed house's energy use is kept at or below the reference house's (explanatory) |
| Sentence 9.36.1.3.(1) of Division B [PDF p.1069] | none (no attribution row for this sentence) | none | NBC 2020 Intent Statements, 9.36.1.3.(1) [PDF p.3128]: the compliance options for energy-efficient housing and small buildings (explanatory) |

Reading the table: Routes 1 and 2 are code compliance paths, so the table is needed only for Route 3. Its rows show how the variance file ties the wall to its benchmark articles. The intent entries are explanatory and cannot establish the variance by themselves.

## Open questions / uncertainty
Source conflicts found while writing this sheet:
- The index record for 23-BCV-003 cites "9.36.2.8.(9)". The STANDATA's own code reference is Sentence 9.36.2.8.(1) (source p.1). This sheet follows the STANDATA. The index record needs correction by its owner (Wave 1c); this sheet did not edit the index.
- The index record for 23-BCV-003 lists a condition not to reuse an older frost-depth value. That condition does not appear in the STANDATA text read (source p.1 to p.3). UNVERIFIED: whether it comes from another instrument.
- Sentence 9.36.8.2.(1) of Division B [PDF p.1106] refers to Tiers 2 to 5, but Table 9.36.8.2. of Division B [PDF p.1106] marks Tiers 3 to 5 as "Reserved". The sheet records the table as printed.
- The NBC 2020 supplement (explanatory only) numbers the sentences under Article 9.36.1.3. of Division B [PDF p.1069] differently from the 2023 text (see Intent). Mapping is by content.
- Division C Article 2.2.1.2., as printed in the 2023 text (PDF p.729), is a written request to the Provincial Building Administrator. The challenge scope PDF paraphrases the same article differently. CONTRACTS already records this. The sheet follows the 2023 text.
- The STANDATA variance wording describes "approximately equivalent or greater safety performance with respect to persons and property". The energy objective OE is an environmental objective. This sheet records both and does not resolve whether an energy variance must show safety performance.
- Division C Article 2.2.1.2. [PDF p.729] places variance decisions with the Provincial Building Administrator. Alternative-solution review under Division A Sentence 1.2.1.1. [PDF p.38] and Division C Article 2.3.1.1. [PDF p.739] is described elsewhere. Which route a local application uses belongs to process-and-admin.

Limits on the extraction:
- No PDF renderer was available (pdftoppm is not installed, and PyMuPDF and pdfplumber are not in the environment). Table values come from the text layer, checked through pypdf coordinates. Table 9.36.2.6.-A (walls) and Table 9.36.2.8.-A (heated floors) match the values the envelope sheet cites from the same pages.
- Table 9.36.8.2. of Division B [PDF p.1106]: the Tier 2 point value is not stated. The raw text reads "21 0" and the layout text reads "210". The coordinates place the tier and points in one text run. A visual check is needed before anyone cites a point value.
- Table A-9.36.1.3. of Division B [PDF p.1455]: the X marks in the matrix come through as merged text runs and are not decoded. Sentence 9.36.1.3.(1) of Division B [PDF p.1069] carries the rules.
- The worked-example numbers are illustrative. No energy model was run. The trade-off sum and floor were checked by hand.
- The performance subsection of Division B (PDF pages 1090 to 1103) was checked for per-assembly minimum wording by text search. The check found none for the envelope. It was not a full article-by-article read.

NECB sources:
- NECB article and table numbers are not cited in this sheet. codedb does not register the NECB, and a bare NECB number would be checked against NBC(AE) articles. Cite the NECB by part and page (source p.N) until codedb registers it.
- The local copy reference/web/energy-efficiency/NECB-2020-from-nrc.pdf carries a 2025 copyright line on its pages, although the NRC page describes the 2020 edition. UNVERIFIED: provenance of the copy, and whether it matches the 2020 text declared in force. Recorded provenance for the local copy is not in the repo.
- Alberta's variations to the NECB are the ones in AR 5/2024 section 2. This sheet does not check the NECB text for other Alberta changes.

Web sources:
- The CSA promo page and the NRC page were fetched through a summarising tool on 2026-10-19. Their claims are summaries, not verbatim text.
- The CSA promo page lists three free courses: contractors (4 hours) and designers (4 hours), both covering Division B Parts 3 to 8, and navigation (20 minutes), which names no parts. A search snippet from another site gave the navigation course as 30 minutes and the parts as 3 to 10. The primary page was taken as the source. The CSA store listing was not fetched, so UNVERIFIED: current availability, access terms, and any 90-day or desktop-only limits.
- NRCan's training page describes NECB 2017 materials and a "Fall 2022" offering. It does not confirm a 2020 course, and UNVERIFIED: its current status.
- AR 5/2024 was read from the local extract. Its live status and any amendments were not checked on 2026-10-19. The local copy's first page shows "(no amdt)".

Other gaps:
- Calgary advisory B23-001 was read through excerpts only. Its transition timing is not analysed here.
- STANDATA 23-BCB-006, 23-BCE-001 (beyond its energy cross-references), and 19-BCV-023 were not read in full, and nothing here rests on them.
- No CCMC or Calgary or Edmonton precedent was searched for energy products.
- The professional question for energy modelling and trade-off arithmetic is open. Sections 2.4.1.1 and 2.4.2 do not answer it for energy reports.
- City-level heating degree-day zones were not checked. The worked example uses Zone 7A as an assumption, and the authority having jurisdiction sets the real values (Article 1.1.3.1. of Division B [PDF p.89]).

## Sources
Code, read at PDF page (local file reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf, text layer through reference/text):
- NBC(AE) 2023, 2nd printing. Front matter, relationship between the NBC(AE) and the NECB: source p.9. Division A: Sentence 1.3.3.2.(1) on PDF pages 39; Article 1.3.3.3. on PDF pages 40; Sentence 1.5.1.1.(2) on PDF pages 54; Sentence 2.1.1.2.(6) on PDF pages 67; Article 2.2.1.1. on PDF pages 68 and 72 to 73; Article 3.2.1.1. on PDF pages 81. Division B: Article 1.1.3.1. on PDF pages 89; Section 9.36 on PDF pages 1068 to 1111, including Sentences 9.36.1.3.(1) to (7) on PDF pages 1069; Articles 9.36.2.2. on PDF pages 1070, 9.36.2.4. on PDF pages 1071, 9.36.2.6. on PDF pages 1073, 9.36.2.7. on PDF pages 1074, 9.36.2.8. on PDF pages 1075 to 1077, 9.36.2.9. on PDF pages 1077, 9.36.2.10. on PDF pages 1078, and 9.36.2.11. on PDF pages 1080 to 1081; Articles 9.36.3.1. on PDF pages 1081, 9.36.3.9. on PDF pages 1083, 9.36.3.10. on PDF pages 1084, 9.36.4.1. on PDF pages 1087, and 9.36.4.2. on PDF pages 1088; Articles 9.36.5.3. and 9.36.5.4. on PDF pages 1091 to 1092, 9.36.5.10. on PDF pages 1095; Article 9.36.6.3. on PDF pages 1103; Article 9.36.7.2. on PDF pages 1104, Table 9.36.7.2. on PDF pages 1105, Article 9.36.7.3. on PDF pages 1105; Article 9.36.8.2. and Table 9.36.8.2. on PDF pages 1106, Article 9.36.8.5. on PDF pages 1107; Table A-9.36.1.3. and its Note on PDF pages 1455; attribution rows on PDF pages 1224 to 1228. Division C: Article 2.2.1.2. on PDF pages 729; Articles 2.2.8.1. to 2.2.8.3. on PDF pages 733 to 734; Articles 2.3.1.1. and 2.4.1.1. on PDF pages 739; Articles 2.4.2.1. to 2.4.2.3. on PDF pages 741.
- NBC 2020 Intent Statements (explanatory only), reference/codes/NBC-2020-Intent-Statements.pdf, PDF pages 3128, 3130, 3136, 3140, 3149, 3164, 3165, 3199, 3201, 3203, 3206 and 3129 (for the numbering note).
- NECB 2020 (national text, local copy reference/web/energy-efficiency/NECB-2020-from-nrc.pdf), source p.4 (table of contents), p.11 (summary of new Part 10), p.26 (Division A application), p.269 (Part 10 tier table and modelling sentence).
- NECB 2020 Intent Statements (explanatory only), reference/codes/NECB-2020-Intent-Statements.pdf, source p.168.
- NECB 2020 Users Guide, reference/codes/NECB-2020-Users-Guide.pdf, source p.7 (parts covered).

Regulation and STANDATA (non-code pages, source p.N):
- Building Code Regulation, Alberta Regulation 5/2024: reference/text/Building-Code-Regulation-AR-5-2024.jsonl and reference/web/process-and-admin/Building-Code-Regulation-AR-5-2024.pdf, source p.3 and p.4 (sections 1, 2, 3, and 6). King's Printer extract reference/web/energy-efficiency/AB-regulation-kings-printer-2024_005.pdf, source p.1 (filed January 24, 2024; in force May 1, 2024). Recorded URL: https://kings-printer.alberta.ca/documents/Regs/2024_005.pdf (not re-fetched on 2026-10-19).
- STANDATA 23-BCV-003, "Insulation below a heated floor", reference/precedents/alberta-standata/standata-nbc2023-variance-23-bcv-003.pdf, source p.1 to p.3. URL: https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/3915ba54-96dd-4c54-a9c1-63df5c917836/download/ma-standata-variance-building-23-bcv-003-2024-05.pdf. Index access date 2026-10-18.
- STANDATA 23-BCB-001, "Energy efficiency Tier 1 of section 9.36", reference/precedents/alberta-standata/standata-nbc2023-bulletin-23-bcb-001.pdf, source p.1 to p.2. URL: https://open.alberta.ca/dataset/5cd7e000-4f7c-4188-b26f-11a16bbe43f8/resource/37c27a63-3517-4b03-b4e2-bd2733219caa/download/ma-standata-bulletin-building-23-bcb-001-2024-04.pdf. Index access date 2026-10-18.
- STANDATA 23-BCI-022, "Energy efficiency exemptions for buildings", reference/precedents/alberta-standata/standata-nbc2023-interpretation-23-bci-022.pdf, source p.1 to p.2. URL: https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/f887c64c-068b-4b7d-852e-dfd56531807c/download/ma-standata-interpretation-building-23-bci-022-2025-05.pdf. Index access date 2026-10-18.
- City of Calgary advisory B23-001 (transition timing), research/precedents/index.json record calgary-building-advisory-b23-001-code-transition, excerpts at source p.1 and p.2 only.
- Precedent index, research/precedents/index.json: records for the STANDATA numbers above and the historical variances listed under Precedents.

Web (fetched 2026-10-19, through a summarising fetch tool, so claims are summaries):
- https://promo.csagroup.org/NECB-online-training: three free NECB 2020 online courses (contractors and designers at 4 hours each, Division B Parts 3 to 8; navigation at 20 minutes); sponsors Natural Resources Canada, the National Research Council, and CSA Group; no dates listed.
- https://cnrc.canada.ca/en/certifications-evaluations-standards/codes-canada/codes-canada-publications/national-energy-code-canada-buildings-2020: free PDF through the NRC Publications Archive (DOI https://doi.org/10.4224/rr3q-hm83); print prices CA$65 (binder) and CA$60 (soft cover); 317 pages; the page does not state amendments or status.
- https://natural-resources.canada.ca/energy-efficiency/building-energy-efficiency/energy-management-training: NRCan training page; describes NECB 2017 online materials and instructor-led materials with a "Fall 2022" offering; does not confirm a 2020 course.
- Search snippet only, not fetched: https://www.hrai.ca/newsletter/free-2020-national-energy-code-for-buildings--necb--training-opportunities-now-available-online- (claims Division B Parts 3 to 10; conflicts with the CSA page; not relied on).

Cross-links read only, claims not copied: research/facts/building-envelope-insulation-cladding.md (front matter and Progress), research/facts/code-structure-and-attribution.md, research/facts/hvac-ventilation-plumbing.md, and research/facts/housing-secondary-suites-part9.md (energy lines only).
