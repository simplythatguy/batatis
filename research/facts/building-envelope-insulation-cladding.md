---
topic: building-envelope-insulation-cladding
scope: Exterior insulation and cladding assemblies, environmental separation (heat, air, vapour and moisture), exterior wall fire performance, and a continuous-insulation sheathing worked example under NBC(AE) 2023 Part 9 and Part 3.
sources_checked:
  - NBC(AE) 2023 2nd printing, Division A 1.2.2.1, 1.3.3.2, 1.3.3.3; Division B Part 3 (3.1.5, 3.2.3), Part 5 (5.1 to 5.9), Part 9 (9.10.14.5, 9.10.17.10, 9.19.1.1, 9.23.13.1, 9.25, 9.27, 9.36.2.6); Division B Appendix A (Table A-9.25.5.1.(1)); Appendix C (Tables C-2 and C-3); Division C 2.2.1.2, 2.3.1.1, 2.4.1.1 to 2.4.2.3; attribution tables for Parts 3, 5 and 9
  - NBC 2020 Intent Statements (explanatory only), read by PDF page
  - Code database (codedb/build/codedb.sqlite), read-only
  - STANDATA 23-BCV-003, 23-BCV-017, 23-BCV-018 (reference/precedents/alberta-standata/), and archived 19-BCV-017 and 19-BCV-022 (reference/web/building-envelope-insulation-cladding/)
  - research/precedents/index.json; reference/data/ccmc-registry.json (snapshot)
  - reference/web/building-envelope-insulation-cladding/gohba-btrboard.html (company description)
  - Two standard web searches on BTRboard (2026-10-19); open.alberta.ca publication page, fetch failed (HTTP 520)
  - Practitioner transcripts 6XtuUn_icQU, 5xQeFj0bfLA, yv3QUPZAmVw, gKhBTL0wALc, t8KcQIypnYE, LlGM_yBP9Ko (explanatory only)
last_verified: 2026-10-19
---
# Building envelope, insulation and cladding

## Progress
- Done: all template sections are written, from Plain-language summary through Sources. The worked example includes a Section C table.
- Done: attribution pairs were checked against the code database rows and against raw page text (Part 9 PDF p.1200, Part 5 PDF p.572, Part 3 PDF p.336). The Zone 7A value of RSI 2.84 is confirmed in the code table on PDF p.1076.
- Done (web, 2026-10-19): two standard searches for a BTRboard evaluation found none. The open.alberta.ca publication page returned HTTP 520 on two WebFetch attempts, so STANDATA currency is confirmed only from the local PDFs' issue dates.
- Validation (codedb validate, 2026-10-19): every remaining error is a known false positive named in the brief. They are lettered-table suffixes in the Part 9 wall and fixing tables, and Section C attribution rows that sit under an Intent header. The remaining warnings are pages with no linked provision, such as Appendix C, Division A and definition pages.
- Open items for the parent, recorded in Open questions: the challenge scope PDF quotes a professional-design sentence and a variance sentence whose wording does not match the 2023 text; the precedent index records a frost-depth condition for 23-BCV-003 that is not in the PDF text; BTRboard's substrate, membrane, permeance and air-leakage data are not on file.

## Plain-language summary
The envelope is the set of walls, roofs and floors that separates heated space from outside air or the ground. Heat, air, water vapour and liquid water all move through it. The code controls those movements through insulation, air barriers, vapour barriers, and the order in which materials are layered. Part 9 covers houses and small buildings. Part 5 covers larger buildings and can also be used for houses. Div B, Article 9.25.1.1. [PDF p.994] and Div B, Article 5.1.1.1. [PDF p.553].

A wall in a Part 9 house needs thermal insulation, a continuous air barrier and a vapour barrier. Each material must also sit in the right position relative to the others. Div B, Article 9.25.1.1. [PDF p.994] and Div B, Article 9.25.5.2. [PDF p.1000].

Cladding sheds most rain. Behind the cladding, a second plane of protection catches any water that gets past it. In most walls that plane is a sheathing membrane. Div B, Article 9.27.2.3. [PDF p.1014] and Div B, Article 9.27.3.3. [PDF p.1015].

A drained, vented air space behind the cladding is a capillary break. Some walls must have one, and the trigger depends on degree-days and a moisture index. Calgary and Edmonton fall below the trigger, though residential walls still need both planes of protection. Div B, Article 9.27.2.2. [PDF pp.1013 to 1014] sets the triggers.

NBC(AE) 2023 Appendix C, Table C-2 gives the moisture index for each listed Alberta location, including Calgary and Edmonton [PDF p.667].

Rigid, non-wood insulating sheathing can replace the separate sheathing membrane when its joints are sealed or detailed to drain. Div B, Article 9.27.3.4. [PDF p.1015].

An exterior insulation finish system is covered by Part 9 only when it meets CAN/ULC-S716.1 and has a drainage cavity of at least 10 mm with at least 13 percent open area. Otherwise Part 5 applies. Div B, Article 9.27.14.1. [PDF p.1025].

Foamed plastic insulation has fire rules. Part 9 requires interior protection from the adjacent space. Part 3 buildings have their own rules for combustible cladding and insulation on exterior walls. Div B, Article 9.10.17.10. [PDF p.907]. Div B, Article 3.1.5.5. [PDF p.137] and Article 3.1.5.15. [PDF pp.141 to 142].

For a variance application, the envelope work is mostly a documentation exercise. The applicant must state the material properties the code asks for, name the degree-day and moisture-index values for the location, and show which article each deviation touches. Whether the wall performs is a professional judgement. Div C, Article 2.3.1.1. [PDF p.739].

## When this topic applies
Route a project here when any of the following signals appears in the description.

Trigger signals, grouped by what the user is describing:

- Insulation in or on the wall: "continuous insulation", "exterior insulation", "insulated sheathing", "rigid board", "XPS", "EPS", "polyiso", "wood fibre board", "spray foam", "insulation below a heated floor", "under-slab insulation".

- Air and vapour control: "air barrier", "vapour barrier" or "vapor retarder", "permeance", "perm rating", "house wrap", "WRB", "sealed joints", "tape", "polyethylene".

- Cladding and moisture: "cladding", "siding", "vinyl", "insulated vinyl", "fibre cement", "metal siding", "stucco", "masonry veneer", "rainscreen", "drained cavity", "drainage mat", "capillary break", "second plane", "drainage plane", "clearance from grade".

- EIFS and similar finish systems: "EIFS", "exterior insulation and finish system", "synthetic stucco", "CAN/ULC-S716".

- Roof and soffit envelope items: "unvented roof", "spray foam roof", "vented soffit", "soffit protection", "roof venting", "ice dams".

- Climate and location: "degree-days", "heating degree-days", "moisture index", "Table 9.25.5.2", "Table C-2".

- Named products and evidence: "CCMC", "evaluation report", "CAN/ULC-S134", "CAN/ULC-S124", "ASTM E96", "dry cup permeance", and product names listed in the CCMC registry such as Legerclad, AiRclad, Thermax Sheathing Insulation, ZIP System R-Sheathing, Wrapsulate, or BTRboard.

- Documents: an existing variance or STANDATA number in 23-BCV-003, 23-BCV-017, 23-BCV-018, or any 19-BCV number used for a 2023 project (see Precedents for the edition warning).

Near-misses that belong to another topic slug:

- Fire spread across a property line, openings in a wall near a lot line, limiting distance, or exposing-face area calculations. Route to fire-separations-and-spatial-separation. This sheet covers only the cladding material on an exposing face.

- Combustibility of the building as a whole, mass timber, encapsulation, or height and area limits. Route to combustible-construction-and-mass-timber.

- Bracing, shear walls, sheathing used as lateral bracing, span tables, trusses, or wall-framing design. Route to structural-and-framing. This sheet notes only the sheathing question.

- Heating, ventilation, heat-recovery ventilators, duct insulation, or plumbing in a wall. Route to hvac-ventilation-plumbing.

- Wall R-value targets, energy modelling, or the performance path. Route to energy-efficiency. This sheet cites the wall requirement only so the reader can see why insulation is needed.

- Two-storey or three-storey row houses and secondary suites, including suite separations. Route to housing-secondary-suites-part9.

- Major occupancy classification, or whether Part 9 or Part 3 applies at all. Route to occupancy-and-accessibility and code-structure-and-attribution. The scope rule is summarized below.

- Evidence and test-report quality beyond naming the standard. Route to evidence-and-conformity.

- Whether a registered professional must sign off. Route to professional-involvement. This sheet lists the envelope triggers only.

Scope rule. Part 9 applies to buildings of three storeys or less in building height, with a building area not more than 600 m², used for residential, business, mercantile, or the listed industrial and home-type care occupancies. Div A, Article 1.3.3.3. [PDF p.40]. Parts 3, 4, 5 and 6 apply to other buildings, including any building over 600 m² or over three storeys used for those occupancies. Div A, Article 1.3.3.2. [PDF pp.39 to 40]. Part 5 can also serve as an alternative route for Part 9 cladding. Div B, Article 9.27.1.1. [PDF pp.1012 to 1013].

## Benchmark acceptable solutions
These are the articles that set the recipe for an envelope assembly. Each row paraphrases what the article requires. Read the full sentence before relying on a row. All paragraphs are NBC(AE) 2023, 2nd printing, Division B.

Part 9 houses and small buildings:

| Article | What it requires (paraphrase) | Cite |
|---|---|---|
| 9.25.1.1.(2) | Walls, ceilings and floors that separate conditioned space from unconditioned space, outside air or the ground need thermal insulation, an air barrier, a vapour barrier, and materials positioned as the material-position rules require. | [PDF p.994] |
| 9.25.2.1.(1) | Enough insulation to prevent room-side condensation and to keep the occupants comfortable. Batt or loose-fill insulation must fill the cavity (Sentence 9.25.2.1.(4)). | [PDF p.994] and [PDF p.995] |
| 9.25.2.2.(1) and (2) | Thermal insulation conforms to the standards listed in Sentence (1), such as CAN/ULC-S701.1, S702.1, S704.1, S705.1 and S706.1. The flame-spread ratings in those standards do not apply in Part 9. | [PDF p.995] |
| 9.25.3.1.(1) | A continuous air barrier system in every wall, floor and ceiling separating conditioned from unconditioned space or the ground. | [PDF p.997] |
| 9.25.3.2.(1) and (2) | Air barrier systems resist air pressure from stack effect, mechanical systems and wind. Polyethylene used as an air barrier conforms to CAN/CGSB-51.34. | [PDF p.997] |
| 9.25.4.1.(1) | Insulated wall, ceiling and floor assemblies need a vapour barrier against diffusion from the interior. | [PDF p.998] |
| 9.25.4.2.(1) | A vapour barrier has a permeance of 60 ng/(Pa·s·m²) or less, by the ASTM E96 dry-cup method. | [PDF p.998] |
| 9.25.5.1.(1) | Sheet or panel materials that have both air leakage under 0.1 L/(s·m²) at 75 Pa and permeance under 60 ng/(Pa·s·m²) must follow Article 9.25.5.2, unless the interior use produces high moisture. | [PDF p.999] |
| 9.25.5.1.(3) [PDF p.1000] | Wood-based sheathing of 12.5 mm or less that complies with Article 9.23.17.2 [PDF p.989] need not comply with Sentence (1). | Exemption |
| 9.25.5.1.(4) | No need to comply with Sentence (1) where permeance is at least 30 ng/(Pa·s·m²), thermal resistance is at least RSI 0.7, and the heating degree-days are below 6000. | [PDF p.1000] |
| 9.25.5.2.(1) and (2) [PDF p.1000] | Low-permeance sheet materials sit on the warm face, or meet the ratio in Table 9.25.5.2 [PDF p.1000], or sit outboard of a vented air space. For walls, that air space meets Clause 9.27.2.2.(1)(a) [PDF p.1013]. | Position rule |
| Table 9.25.5.2 | Minimum outboard-to-inboard resistance ratio by heating degree-days: 0.20 below 5000, 0.30 for 5000 to 5999, 0.35 for 6000 to 6999, rising to 0.75 at 12 000 or more. | [PDF p.1000] |
| 9.27.1.1.(1), (2), (4) and (5) | Cladding on wood-frame walls follows Subsections 9.27.2 to 9.27.13, or Part 5. Stucco and masonry have their own routes. Exterior insulation finish systems follow 9.25.5, 9.27.2 to 9.27.4 and 9.27.14, or Part 5. | [PDF pp.1012 to 1013] |
| 9.27.2.2.(1) | A deemed capillary break exists where a drained and vented air space is at least 9.5 mm deep, or an open drainage material is at least 10 mm thick and at least 80 percent open, or the cladding is loosely fastened with a clear air space behind it, or the wall is masonry cavity or masonry veneer, or the cladding is EIFS under 9.27.14. | [PDF pp.1013 to 1014] |
| 9.27.2.2.(4) | Residential exterior walls exposed to precipitation need both a first and a second plane of protection. | [PDF p.1014] |
| 9.27.2.2.(5) and (6) | A capillary break is required where degree-days are under 3400 and the moisture index is over 0.90, or where degree-days are 3400 or more and the moisture index is over 1.00. Some walls are exempt. | [PDF p.1014] |
| 9.27.2.4.(1) | A clearance of at least 200 mm from finished ground for cladding that moisture harms, such as untreated wood, plywood, OSB, waferboard and hardboard. | [PDF pp.1014 to 1015] |
| 9.27.3.1.(1) | The second plane is a drainage plane with an appropriate inner boundary and flashing that drains water to the exterior. | [PDF p.1015] |
| 9.27.3.3.(1) to (3) | At least one layer of sheathing membrane beneath the cladding, unless 9.27.3.4 to 9.27.3.6 apply. Laps are at least 100 mm. | [PDF p.1015] |
| 9.27.3.4.(1) and (2) | Non-wood-based rigid exterior insulating sheathing, or insulating sheathing with an integral membrane, needs no separate membrane. Moisture-sensitive panels have sealed joints. Other panels have sealed joints, or lapped or tongue-and-groove joints that drain to the exterior. | [PDF p.1015] |
| 9.27.3.5.(1) | With no sheathing, at least two layers of sheathing membrane. | [PDF pp.1015 to 1016] |
| 9.27.3.6.(1) to (3) | Membrane may be omitted where sheathing or cladding joints are sealed or battened, or where metal siding has locked seams. | [PDF p.1016] |
| 9.27.14.1.(1) and (2) | EIFS that meet CAN/ULC-S716.1 and have a drainage cavity of at least 10 mm with at least 13 percent open area are covered here. Other EIFS follow Part 5. | [PDF p.1025] |
| 9.27.14.2.(1) and (2) [PDF p.1025] | EIFS materials conform to CAN/ULC-S716.1. The substrate is compatible with the system and meets the sheathing structure rules of Section 9.23 [PDF pp.962 to 990]. | Materials |
| 9.27.14.3.(1) | EIFS design and installation follow CAN/ULC-S716.2 (installation and water-resistive barrier) and CAN/ULC-S716.3 (design application). | [PDF p.1025] |
| 9.10.17.10.(1) | Foamed plastic in a wall or ceiling is protected from the adjacent space in the building, except concealed spaces inside wall or ceiling assemblies. Protection is an interior finish, sheet metal (not in Group C), or a thermal barrier that meets Sentence 3.1.5.15.(2). | [PDF p.907] |
| 9.19.1.1.(1) | Where insulation sits between the ceiling and the roof sheathing, a ventilated space is needed between the insulation and the sheathing, unless the assembly is shown to need no venting. | [PDF p.939] |

Part 5 environmental separation (larger buildings, or an alternative route for Part 9 cladding):

| Article | What it requires (paraphrase) | Cite |
|---|---|---|
| 5.1.4.2.(1) | Materials in a separator or exterior assembly are compatible with their neighbours and resist expected deterioration. | [PDF p.555] |
| 5.3.1.1.(1) and 5.3.1.2.(1) | Materials that resist heat transfer are sized for the intended temperature difference. They minimize condensation on the warm side and within the assembly, and ice damming on sloped roofs. | [PDF p.557] |
| 5.4.1.1.(1) to (4) | Air leakage is controlled by materials and positions. An air barrier system is continuous across joints, junctions and penetrations. | [PDF pp.557 to 558] |
| 5.4.1.2.(1) and (2) | Air barrier assemblies conform to CAN/ULC-S742 and meet the performance class in Table 5.4.1.1. Assemblies not evaluated to S742 need at least one air barrier material to CAN/ULC-S741. | [PDF pp.558 to 559] |
| 5.5.1.1.(1) and (2) and 5.5.1.2.(1) | Vapour diffusion is controlled. A vapour barrier provides the principal resistance, unless its absence is shown to cause no harm. | [PDF p.559] |
| 5.6.1.1.(1) and 5.6.2.1.(1) | Precipitation is kept out of assemblies. Exposed joints are sealed, or drained to the exterior. | [PDF p.560] |
| 5.9.1.1.(1) [PDF p.565] | Materials in environmental separators and exposed assemblies conform to the standards listed in the Part 5 standards table. | Standards |
| 5.9.4.1.(1) | EIFS meet Subsections 5.1.4 and 5.3 to 5.6, and CAN/ULC-S716.1 where covered by that standard. | [PDF p.570] |

Part 3 buildings (combustible cladding, foam insulation and exposing faces):

| Article | What it requires (paraphrase) | Cite |
|---|---|---|
| 3.1.5.1.(1) [PDF p.135] | Defines noncombustible construction. The exceptions in Part 3 point back to this sentence. | Definition |
| 3.1.5.5.(1) and (2) [PDF p.137] | Combustible cladding is allowed on a noncombustible-construction exterior wall in a building of three storeys or less, or a sprinklered one, if a CAN/ULC-S134 test shows flaming not above 5 m over the opening and a heat flux not above 35 kW/m² at 3.5 m. Where unprotected openings are 10 percent or less, the exposing-face construction of Article 3.2.3.7 applies [PDF p.212]. | Limits |
| 3.1.5.5.(3) | Fire-retardant-treated wood cladding must be weathered under ASTM D2898 before the fire test. | [PDF p.137] |
| 3.1.5.6.(1) | Other combustible wall components are allowed under the same conditions, or behind 25 mm of masonry or concrete cladding. | [PDF p.137] |
| 3.1.5.14.(2) and (4) | Combustible insulation with flame-spread rating 25 or less is allowed in noncombustible construction. Ratings from 25 to 500 need a thermal barrier. | [PDF pp.140 to 141] |
| 3.1.5.15.(2) and (3) | Foamed plastic with flame-spread rating 500 or less is allowed behind a thermal barrier of 12.7 mm gypsum, lath and plaster, masonry, concrete, or a CAN/ULC-S124 Class B coating. Non-sprinklered buildings over 18 m high have a separate rule for exterior walls. | [PDF pp.141 to 142] |
| 3.2.3.7.(1) | Exposing building faces follow Table 3.2.3.7 for fire-resistance rating, construction and cladding. | [PDF p.212] |
| 3.2.3.8.(1) to (3) [PDF p.214] | Foamed plastic in an exterior wall of a building over three storeys, with more than 10 percent unprotected openings, is protected on the outside by 25 mm of concrete or masonry, or by a noncombustible material tested to CAN/ULC-S101. This does not apply to walls that comply with Article 3.1.5.5 [PDF p.137]. | Protection |
| 3.2.3.16.(1) | Soffits over a common attic serving more than two suites are protected where they project past the exterior wall, within 2500 mm of an opening. | [PDF p.216] |
| 9.10.14.5.(2) [PDF p.897] | Combustible cladding on an exposing face above 10 percent unprotected openings may remain combustible if the wall meets the S134 criteria in Clause 3.1.5.5.(1)(b) [PDF p.137]. | Exposing face |

Part 9 and Part 3 change the answer in four ways. The first is which article set applies. A single-family house uses the Part 9 sections on environmental separation and cladding. A Part 3 building uses Part 5 in full, through Div A, Article 1.3.3.2. [PDF pp.39 to 40]. The second is the flame-spread rule for insulation. Div B, Sentence 9.25.2.2.(2) [PDF p.995] exempts insulation from the flame-spread ratings of the listed standards. Div B, Sentence 5.9.1.1.(2) [PDF p.565] applies those ratings where Part 3 itself requires them. The third is foam protection. The Part 3 exterior-wall rule for foam, Div B, Article 3.2.3.8 [PDF p.214], has no direct Part 9 counterpart. Part 9 protects foam under Div B, Sentence 9.10.17.10.(1) [PDF p.907]. The fourth is cladding fire tests. Both Parts use CAN/ULC-S134 for combustible cladding on exposing faces. Part 9 reaches that test through Div B, Sentence 9.10.14.5.(2) [PDF p.897], and Part 3 through Div B, Sentence 3.1.5.5.(1) [PDF p.137].

## Attributions
The envelope pairs come from three attribution tables in NBC(AE) 2023, 2nd printing. Part 9 pairs are in Table 9.38.1.1 (PDF pp.1194 to 1204, with the 9.10 and 9.19 rows on PDF pp.1129, 1130 and 1144). Part 5 pairs are in Table 5.10.1.1 (PDF pp.571 to 573). Part 3 pairs are in Table 3.10.1.1 (PDF pp.321 and 336). Each pair is shown as printed. The F-codes are functional statements. The OS, OH, OP and OE codes are objectives.

Functional statements used below, paraphrased from Div A, Part 3 (PDF pp.79 to 81):

| Code | What it requires (paraphrase) | PDF page |
|---|---|---|
| F01 | minimize the risk of accidental ignition | p.79 |
| F02 | limit the severity and effects of fire or explosions | p.79 |
| F03 | retard the effects of fire beyond its point of origin | p.79 |
| F05 | retard the effects of fire on emergency egress facilities | p.80 |
| F20 | support and withstand expected loads and forces | p.80 |
| F22 | limit movement under expected loads and forces | p.80 |
| F40 | limit the level of contaminants | p.80 |
| F44 | limit the spread of hazardous substances beyond their point of release | p.80 |
| F51 | maintain appropriate air and surface temperatures | p.80 |
| F52 | maintain appropriate relative humidity | p.80 |
| F54 | limit drafts | p.80 |
| F55 | resist the transfer of air through environmental separators | p.80 |
| F61 | resist ingress of precipitation, water or moisture from the exterior or the ground | p.80 |
| F62 | facilitate dissipation of water and moisture from the building | p.81 |
| F63 | limit moisture condensation | p.81 |
| F80 | resist deterioration from expected service conditions | p.81 |
| F92 | limit uncontrolled thermal transfer through the building envelope | p.81 |

Objectives used below, from Div A, Part 2 (PDF pp.68 to 73):

| Code | Objective (paraphrase) | PDF page |
|---|---|---|
| OS1.1 | fire or explosion occurring | p.68 |
| OS1.2 | fire or explosion impacting areas beyond its point of origin | p.68 |
| OS1.4 | fire safety systems failing to function as expected | p.68 |
| OS1.5 | persons delayed or impeded from moving to a safe place in a fire emergency | p.68 |
| OS2.3 | damage to or deterioration of building elements (structural safety group) | p.68 |
| OS3.1 | tripping, slipping, falling, contact, drowning or collision | p.69 |
| OS3.4 | exposure to hazardous substances | p.69 |
| OH1.1 | inadequate indoor air quality (indoor conditions group) | p.70 |
| OH1.2 | inadequate thermal comfort | p.70 |
| OH1.3 | contact with moisture | p.70 |
| OH2.5 | contact with vermin and insects | p.70 |
| OP1.2 | fire or explosion impacting areas beyond its point of origin | p.72 |
| OP2.1 | loads exceeding the loadbearing capacity of elements | p.72 |
| OP2.3 | damage to or deterioration of building elements | p.72 |
| OP3.1 | fire or explosion impacting areas beyond the building of origin | p.72 |
| OE1.1 | excessive use of energy | p.73 |

Pairs for the envelope sentences, as printed in each table:

| Sentence | Pairs as printed | Table page |
|---|---|---|
| 3.1.5.1.(1) noncombustible materials | [F02-OS1.2] [F02-OP1.2] | p.321 |
| 3.1.5.5.(2) construction where the limiting distance allows 10 percent or less unprotected openings | [F03,F02-OP3.1] | p.321 |
| 3.2.3.7.(1) construction of exposing building face | [F03,F02-OP3.1] | p.336 |
| 3.2.3.8.(1) protection of exterior building face (foamed plastic) | [F03,F02-OP3.1] | p.336 |
| 3.2.3.16.(1) protection of soffits | [F03-OS1.2] [F03-OP1.2] | p.336 |
| 5.3.1.1.(1) required resistance to heat transfer | [F63-OH1.1] [F51,F63-OH1.2] [F63-OS2.3] [F51,F63-OS1.4] | p.571 |
| 5.4.1.1.(1)(a) required resistance to air leakage | [F51,F52,F54,F55-OH1.2] [F40,F55-OH1.1] | p.572 |
| 5.4.1.1.(1)(b) | [F51,F52,F54,F55-OH1.2] [F40,F55-OH1.1] | p.572 |
| 5.4.1.1.(1)(c) | [F40,F55-OH1.1] [F55,F61,F63-OH1.3] [F61,F62,F63,F55-OS2.3] | p.572 |
| 5.4.1.1.(1)(d) | [F61,F62,F63,F55-OS2.3] [F55,F62-OS3.1] | p.572 |
| 5.4.1.1.(1)(e) | [F40,F55-OH1.1] | p.572 |
| 5.4.1.1.(1)(f) | [F51,F52,F54,F55-OH1.2] [F55,F62-OS1.4] | p.572 |
| 5.4.1.2.(1) air barrier assemblies (CAN/ULC-S742 and performance class) | [F55-OH1.1,OH1.2,OH1.3] [F55-OS2.3] [F55-OS1.4] | p.572 |
| 5.4.1.2.(2) air barrier assemblies not evaluated to CAN/ULC-S742 | [F55-OH1.1,OH1.2,OH1.3] [F55-OS2.3] [F55-OS1.4] | p.572 |
| 5.5.1.1.(1) and (2) vapour diffusion control and vapour barrier | [F63-OH1.1,OH1.2] [F63-OS2.3] | p.572 |
| 5.5.1.2.(1) vapour barrier properties and installation | [F63-OH1.1,OH1.2] [F63-OS2.3] | p.572 |
| 5.6.1.1.(1) required protection from precipitation | [F61-OH1.1,OH1.2,OH1.3] [F61-OS2.3] | p.572 |
| 5.6.2.1.(1) sealing and drainage | [F61,F62-OH1.1,OH1.2,OH1.3] [F61,F62-OS2.3] | p.572 |
| 5.9.1.1.(1) (materials conform to the standards in Part 5's standards table) | [F20,F22,F51,F54,F55,F61,F63,F80-OH1.1,OH1.2] [F20,F22,F51,F61,F63,F80-OS2.3] [F55,F61,F80-OH1.3] and others | p.573 |
| 5.9.4.1.(1)(b) EIFS covered by CAN/ULC-S716.1 | [F61,F62-OH1.1,OH1.2,OH1.3] [F61,F62-OS2.3] | p.573 |
| 9.10.14.5.(2) cladding on exposing faces above 10 percent openings | [F03-OP3.1] | p.1129 |
| 9.10.17.10.(1) protection of foamed plastics from adjacent space | [F01,F02,F05-OS1.5] | p.1130 |
| 9.19.1.1.(1) required venting above insulation at the roof sheathing | [F51,F62-OH1.1,OH1.2] [F51-OH1.3] [F62,F51-OS2.3] | p.1144 |
| 9.25.1.1.(2) walls, ceilings and floors need insulation, air barrier, vapour barrier and material position | [F51,F63-OH1.1,OH1.2] [F55-OH1.1,OH1.2,OH1.3] [F55,F63-OS2.3] | p.1194 |
| 9.25.2.1.(1) sufficient thermal insulation to prevent room-side condensation | [F51,F63-OH1.1,OH1.2] [F63-OS2.3] | p.1194 |
| 9.25.2.2.(1) insulation materials conform to listed standards | [F51,F63,F80-OH1.1,OH1.2] [F63,F80-OS2.3] | p.1194 |
| 9.25.3.1.(1) required air barrier system | [F55-OH1.1,OH1.2,OH1.3] [F40-OH1.1] [F55-OS2.3] [F44-OS1.1] and [F44-OS3.4] (garage note) | p.1195 |
| 9.25.3.2.(1) air barrier system properties | [F20,F55-OH1.1,OH1.2,OH1.3] [F40-OH1.1] [F20,F55-OS2.3] and garage rows | p.1195 |
| 9.25.3.2.(2) polyethylene air barrier | [F20,F80,F55-OH1.1,OH1.2,OH1.3] | p.1195 |
| 9.25.4.1.(1) required vapour barrier | [F63-OH1.1,OH1.2] [F63-OS2.3] | p.1196 |
| 9.25.4.2.(1) vapour barrier permeance limit | [F63-OS2.3] [F63-OH1.1,OH1.2] | p.1196 |
| 9.25.4.2.(3) high moisture generation uses Part 5 | [F62,F63-OS2.3] [F62,F63-OH1.1,OH1.2,OH1.3] | p.1196 |
| 9.25.5.1.(2) high moisture generation uses Part 5 | [F62,F63-OS2.3] [F62,F63-OH1.1,OH1.2,OH1.3] | p.1196 |
| 9.25.5.2.(1) position of low-permeance sheet materials | [F62,F63-OS2.3] [F62,F63-OH1.1,OH1.2] | p.1196 |
| 9.27.2.2.(4) two planes of protection for residential walls | [F61,F62-OS2.3] [F61,F62-OH1.1,OH1.2,OH1.3] | p.1200 |
| 9.27.2.2.(5) capillary break thresholds | [F61,F62-OS2.3] [F61,F62-OH1.1,OH1.2,OH1.3] | p.1200 |
| 9.27.2.3.(1) first and second planes | [F61,F62-OS2.3] [F61,F62-OH1.1,OH1.2,OH1.3] | p.1200 |
| 9.27.3.1.(1) second plane is a drainage plane | [F61,F62-OS2.3] [F61,F62-OH1.1,OH1.2,OH1.3] | p.1200 |
| 9.27.3.3.(1) sheathing membrane beneath cladding | [F61,F55-OS2.3] [F61,F55-OH1.1,OH1.2,OH1.3] | p.1200 |
| 9.27.3.4.(2) insulating sheathing joints | [F61,F55-OS2.3] [F61,F55-OH1.1,OH1.2,OH1.3] | p.1200 |
| 9.27.5.3.(1) furring anchorage | [F20-OH1.1,OH1.2,OH1.3] [F20-OS2.1,OS2.3] [F20-OS2.1,OS2.3,OS2.4] [F22-OS2.3,OS2.4,OS2.5] | p.1201 |
| 9.27.14.2.(1) EIFS materials | [F20,F61,F62-OH1.1,OH1.2,OH1.3] [F20,F61,F62-OS2.3] | p.1204 |
| 9.27.14.3.(1) EIFS design and installation | [F20,F61,F62-OH1.1,OH1.2,OH1.3] [F20,F61,F62-OS2.3] | p.1204 |

Several envelope sentences have no attribution row. Each of these is a permission or an exception. The intent statement for each one names the sentence it limits or exempts, so the root can be identified from the intent text rather than from a heuristic.

| Sentence without a row | Sentence the intent names | Basis in the intent text |
|---|---|---|
| 3.1.5.5.(1) combustible cladding permitted | 3.1.5.1.(1) noncombustible materials | Exempts certain combustible materials from 3.1.5.1.(1) |
| 3.1.5.6.(1), 3.1.5.14.(2) and (4), 3.1.5.15.(2) and (3) | 3.1.5.1.(1) | Same exemption wording as 3.1.5.5.(1) |
| 9.25.2.2.(2) flame-spread exemption for insulation | 9.25.2.2.(1) | Exempts insulation from the flame-spread requirements of the referenced standards |
| 9.25.5.1.(1) low-permeance sheet materials | 9.25.5.2 | States, in part, the application of 9.25.5.2 |
| 9.25.5.1.(3) thin wood-based sheathing | 9.25.5.1.(1) | Exempts sheathing that shows acceptable moisture dissipation despite low air and vapour permeance; the intent cites Clause 9.25.5.1.(1)(b), while the sentence text cites all of Sentence (1) |
| 9.27.1.1.(1) and (5) cladding scope | 9.27.2 to 9.27.13, and 9.27.14 for EIFS | States the application of those subsections |
| 9.27.2.2.(1) deemed capillary break | 9.27.2.2.(5) and (6) | Defines the assemblies deemed to provide a capillary break |
| 9.27.3.4.(1) insulating sheathing in lieu of membrane | 9.27.3.3.(1) | Limits the application of 9.27.3.3.(1) where insulating sheathing provides the same protection |
| 9.27.14.1.(1) EIFS scope | 9.27.14 | States the application of 9.27.14 |

Intent-only rows have no attribution pairs on either side of the national 2020 comparison. The code database reports status `none_both` for these sentences. The attribution pairs of the root sentence, where the root has a row, are the pairs a reviewer would check first. This sheet does not treat the root pairs as attributions of the exception itself.

## Intent
The NBC 2020 Intent Statements are national explanatory text. They are not Alberta law and are cited here only to explain why an article exists. The paraphrases below are mine. Each key article exists in NBC(AE) 2023 with the same number, so the intent can be matched to the article it explains.

| Sentence | What the intent says (paraphrase) | Citation |
|---|---|---|
| 9.25.1.1.(2) | Limit the chance that walls, floors and ceilings are built badly for heat transfer, air leakage and condensation. The sentence points to the insulation, air barrier, vapour barrier and material-position subsections. | NBC 2020 Intent Statements, 9.25.1.1.(2) [PDF pp.2511 to 2512] |
| 9.25.2.1.(1) | Limit the chance that heat transfer cannot be controlled through an assembly, leading to cold interior surfaces or condensation. | NBC 2020 Intent Statements, 9.25.2.1.(1) [PDF pp.2512 to 2513] |
| 9.25.2.2.(1) | Limit the chance that the thermal performance of required insulation falls well below expectations. | NBC 2020 Intent Statements, 9.25.2.2.(1) [PDF pp.2513 to 2514] |
| 9.25.2.2.(2) | Exempts insulation from the flame-spread requirements of the standards listed in Sentence (1). | NBC 2020 Intent Statements, 9.25.2.2.(2) [PDF p.2514] |
| 9.25.3.1.(1) | Limit excessive heat loss or gain from air movement, air infiltration and exfiltration, airborne vapour transfer, and precipitation drawn in by pressure differences. | NBC 2020 Intent Statements, 9.25.3.1.(1) [PDF pp.2531 to 2532] |
| 9.25.3.2.(1) | Limit the chance that air barrier components fail under air pressure loads, through rupture, tearing or puncture at fasteners. | NBC 2020 Intent Statements, 9.25.3.2.(1) [PDF pp.2532 to 2534] |
| 9.25.4.1.(1) | Limit uncontrolled diffusion of water vapour from heated-space air into insulated wall, ceiling and floor assemblies. | NBC 2020 Intent Statements, 9.25.4.1.(1) [PDF p.2544] |
| 9.25.4.2.(1) | Limit excessive vapour diffusion through vapour barriers that could lead to condensation, where the interior use does not produce high moisture. | NBC 2020 Intent Statements, 9.25.4.2.(1) [PDF p.2545] |
| 9.25.5.1.(1) | States, in part, the application of the position article that follows it. | NBC 2020 Intent Statements, 9.25.5.1.(1) [PDF p.2554] |
| 9.25.5.1.(3) | Exempts sheathing that shows acceptable moisture dissipation despite lower air and vapour permeances. The intent names Clause 9.25.5.1.(1)(b). The sentence text exempts from all of Sentence 9.25.5.1.(1). | NBC 2020 Intent Statements, 9.25.5.1.(3) [PDF p.2555] |
| 9.25.5.2.(1) | Limit inadequate moisture diffusion, venting or drainage to the exterior under normal interior conditions, which could lead to condensation. | NBC 2020 Intent Statements, 9.25.5.2.(1) [PDF p.2556] |
| 9.27.1.1.(5) | States the application of Subsections 9.25.5., 9.27.2. to 9.27.4. and 9.27.14. to exterior insulation finish systems, and extends Part 5 to them. | NBC 2020 Intent Statements, 9.27.1.1.(5) [PDF p.2665] |
| 9.27.2.2.(1) | Defines the assemblies that are deemed to have a capillary break between the cladding and the backing. | NBC 2020 Intent Statements, 9.27.2.2.(1) [PDF p.2667] |
| 9.27.2.2.(4) and (5) | Limit precipitation or meltwater ingress, and limit inadequate drying of moisture from behind the cladding. | NBC 2020 Intent Statements, 9.27.2.2.(5) [PDF pp.2668 to 2669] |
| 9.27.2.3.(1) | Limit precipitation ingress through the first and second planes of protection, and at penetrations and interfaces. | NBC 2020 Intent Statements, 9.27.2.3.(1) [PDF pp.2669 to 2670] |
| 9.27.3.1.(1) | Limit precipitation ingress through the second plane and inadequate drainage to the exterior. | NBC 2020 Intent Statements, 9.27.3.1.(1) [PDF pp.2672 to 2673] |
| 9.27.3.3.(1) | Limit excessive air infiltration, which causes wind-washing and condensation, and limit precipitation ingress. This is the reason for the sheathing membrane. | NBC 2020 Intent Statements, 9.27.3.3.(1) [PDF pp.2675 to 2676] |
| 9.27.3.4.(1) | Limits the application of 9.27.3.3.(1) where insulating sheathing can provide the air and precipitation protection that a sheathing membrane normally provides. States the application of 9.27.3.4.(2). | NBC 2020 Intent Statements, 9.27.3.4.(1) [PDF p.2678] |
| 9.27.3.4.(2) | Limit inadequate joint sealing or detailing, which could let in moisture or air and lead to deterioration of the exterior wall. | NBC 2020 Intent Statements, 9.27.3.4.(2) [PDF pp.2678 to 2679] |
| 9.27.14.1.(1) | States the application of the EIFS subsection. | NBC 2020 Intent Statements, 9.27.14.1.(1) [PDF p.2778] |
| 9.27.14.2.(1) | Limit the chance that EIFS performance falls well below expectations, leading to early failure or an inability to shed water. | NBC 2020 Intent Statements, 9.27.14.2.(1) [PDF pp.2778 to 2779] |
| 9.27.14.3.(1) | Limit inadequate design and installation of EIFS, which could cause component failure. | NBC 2020 Intent Statements, 9.27.14.3.(1) [PDF pp.2780 to 2781] |
| 5.3.1.1.(1) | Limit inadequate control of heat transfer through environmental separators under expected loads. | NBC 2020 Intent Statements, 5.3.1.1.(1) [PDF pp.1016 to 1017] |
| 5.4.1.1.(1) | Limit inadequate control of air leakage or venting, which could cause deterioration, ice dams and loss of thermal control. | NBC 2020 Intent Statements, 5.4.1.1.(1) [PDF pp.1020 to 1021] |
| 5.4.1.2.(1) and (2) | Limit the chance that installed assemblies are not airtight enough for thermal, moisture and life-safety control, with separate wording for assemblies evaluated and not evaluated to CAN/ULC-S742. | NBC 2020 Intent Statements, 5.4.1.2.(1) [PDF pp.1026 to 1027] and 5.4.1.2.(2) [PDF pp.1027 to 1028] |
| 5.5.1.1.(1) and (2) | Limit inadequate control of vapour diffusion through environmental separators, except moisture from the ground. | NBC 2020 Intent Statements, 5.5.1.1.(1) [PDF p.1029] and 5.5.1.1.(2) [PDF pp.1029 to 1030] |
| 5.5.1.2.(1) | Limit the chance that installed materials cannot adequately control vapour diffusion. | NBC 2020 Intent Statements, 5.5.1.2.(1) [PDF pp.1030 to 1031] |
| 5.6.1.1.(1) | Limit inadequate protection from precipitation ingress and excessive moisture loading. | NBC 2020 Intent Statements, 5.6.1.1.(1) [PDF pp.1032 to 1033] |
| 5.6.2.1.(1) | Limit inadequate control of precipitation ingress and inadequate provision for drainage. | NBC 2020 Intent Statements, 5.6.2.1.(1) [PDF p.1035] |
| 5.9.4.1.(1) | Directs users to the Part 5 requirements that apply to EIFS, and limits EIFS performance falling below expectations. | NBC 2020 Intent Statements, 5.9.4.1.(1) [PDF p.1060] |
| 3.1.5.5.(1) | Exempts certain combustible materials from 3.1.5.1.(1) when the stated conditions are met, because protected materials are deemed to contribute insignificantly to fire growth and spread. States the application of the S134 clause and the 10 percent sentence. | NBC 2020 Intent Statements, 3.1.5.5.(1) [PDF p.67] |
| 3.1.5.5.(2) | Limit the chance that an exposing building face has too little fire resistance, which could spread fire to an adjacent building. | NBC 2020 Intent Statements, 3.1.5.5.(2) [PDF pp.67 to 68] |
| 3.2.3.7.(1) and 3.2.3.8.(1) | Limit the chance that an exposing building face has insufficient fire resistance, which could spread fire to adjacent buildings. | NBC 2020 Intent Statements, 3.2.3.7.(1) [PDF p.393] and 3.2.3.8.(1) [PDF p.395] |
| 3.2.3.16.(1) | Limit the spread of fire from a suite through openings in the soffit area. | NBC 2020 Intent Statements, 3.2.3.16.(1) [PDF p.401] |
| 9.10.14.5.(2) | Limit the chance that fire spreads from the building to an adjacent building through its exposing face. | NBC 2020 Intent Statements, 9.10.14.5.(2) [PDF pp.1408 to 1409] |
| 9.10.17.10.(1) | Limit the chance that foamed plastic insulation is exposed to fire or high heat, which could lead to ignition. | NBC 2020 Intent Statements, 9.10.17.10.(1) [PDF pp.1427 to 1428] |
| 9.19.1.1.(1) | Limit inadequate venting, which could cause condensation, moisture accumulation or ice dams. | NBC 2020 Intent Statements, 9.19.1.1.(1) [PDF pp.1710 to 1711] |

Comparison with NBC(AE) 2023. The code database holds 311 sentence and clause rows under the section prefixes this sheet uses (9.25, 9.27, 5.3 to 5.9, 3.1.5, 3.2.3, 9.10.14, 9.10.17 and 9.19.1.1). Of these, 206 have the same objective and functional pairs in the 2020 intent and in the 2023 table. 99 have no pairs on either side. Six differ. The comparison checks pair sets only. It does not check whether the wording or the Alberta amendments are the same.

The six rows that differ are these. Three matter for this topic. For 9.25.3.2.(1), the 2023 table attributes objectives OH1.1 to OH1.3 with functions F20 and F55. The 2020 intent block lists no such pairs. For 9.27.3.2.(1), the 2023 table adds OS2.3 pairs for F20, F55, F61 and F62. For 9.27.5.4.(1), the 2023 table adds OH1.1 to OH1.3 with F22. The other three differing rows are 5.9.2.2.(1), 9.25.2.4.(4) and 9.27.12.1.(3), and sit outside this sheet's scope.

## Typical alternative solutions
The list below comes from the products and variances on file. Product names and CCMC numbers are as printed in the supplied CCMC registry snapshot (462 records). The snapshot could not be refreshed live on 2026-10-18, so the numbers are not confirmed against the live registry. Whether a product reaches the code through an article or through a variance is not stated in the registry, so each case is marked UNVERIFIED where that matters.

1. Continuous insulated sheathing in place of OSB or plywood. The snapshot lists:

   - Thermax Sheathing Insulation (CCMC 08433-L), listed to CAN/ULC-S704.1, Type 3, Class 1. That standard covers faced polyurethane and polyisocyanurate boards.

   - Styrobar rigid insulation board (CCMC 13217-L), listed to CAN/ULC-S701.1, the polystyrene board standard.

   - BP Sheathing (CCMC 12044-L), listed to CAN/ULC-S706-09, the insulating wood fibre board standard.

   - Legerclad, a composite EPS board with a sheathing membrane (CCMC 13510-R), and AiRclad, a sheathing membrane and insulation board (CCMC 13488-R). Both carry an integral membrane.

   - Wrapsulate Foam Jacket insulating sheathing (CCMC 14049-R) and ZIP System R-Sheathing (CCMC 14075-R).
   What each must show: the permeance and air leakage of the board (9.25.5.1), the joint treatment (9.27.3.4.(2)), whether the board is wood-based (9.27.3.4.(1)), and the bracing route (9.23.13.1.(2)). The registry does not say which route each product uses. UNVERIFIED per product.

2. Air barrier systems that include insulation. The snapshot lists the FOAMULAR NGX CodeBord Air Barrier System (CCMC 12935-R), Insulthane Extreme Air Barrier System (CCMC 14030-R), Wrapsulate Foam Jacket Air Barrier System (CCMC 14096-R), and Boreal Nature Elite Air Barrier System (CCMC 14241-R). Each is recorded as an air barrier system. Whether an evaluation covers the assembly the code's air barrier article (5.4.1.2, CAN/ULC-S742) requires is a question for the report. UNVERIFIED for each product.

3. Insulated siding. Haven Insulated Siding (CCMC 13544-R) is in the snapshot. Insulated vinyl is named in Sentence 9.27.1.1.(1), so this cladding follows 9.27.2 to 9.27.13 or Part 5.

4. Drainage products. The snapshot lists Form-A-Drain (CCMC 13492-R), Fiodrain (13517-R), Hydrostar AG (13674-R), SOPRADRAIN DMB (14410-R), DELTA-DRAIN (13209-R) and SUPERSEAL Dimpled Membrane (13098-R). Most are filed under MasterFormat 33 46, the subdrainage section, so they are most likely foundation products. Whether any is evaluated for a wall drained air space is UNVERIFIED. Sentence 9.27.2.2.(1)(b) needs an open drainage material at least 10 mm thick and at least 80 percent open. Whether any one product meets that test is UNVERIFIED.

5. Exterior insulation finish systems. DuROCK PUCC-ROCK and InsulROCK (CCMC 12969-R) appear in the snapshot with CAN/ULC-S716.1 and CCMC-TG-072413.05-20A as reference documents. Under 9.27.14.1.(1), an EIFS is covered by Part 9 only when it is within the scope of CAN/ULC-S716.1 and has the drainage cavity described there.

6. Unvented roof assemblies. STANDATA 23-BCV-017 (issued September 2025) accepts unvented Part 9 residential roof assemblies designed to the RDH evaluation report 32139.000, and requires that report with the permit application. This is a roof variance, not a wall variance.

7. Intumescent-coated vented soffits. STANDATA 23-BCV-018 (issued September 2025) accepts a tested intumescent-coated vented substrate in place of the solid soffits required by Sentences 9.10.14.5.(12), 9.10.15.5.(11) and 9.10.12.4.(2) and (3). The conditions are testing by a Standards Council of Canada accredited laboratory, performance at least equal to 11 mm plywood under a 50 kW/m² radiant heat flux for 15 minutes (Appendix A), and installation to the manufacturer's instructions or the test documentation.

8. Under-slab insulation below a heated floor. STANDATA 23-BCV-003 (issued May 2024) accepts a minimum RSI 1.32 (R-7.5) under a heated floor in contact with the ground, in place of the values in Table 9.36.2.8.-A and -B. For Edmonton, which is in Zone 7A, the table value is RSI 2.84 [PDF p.1076]. The variance applies to Part 9 buildings. It does not remove Section 9.36.

9. Combustible cladding on exposing faces. Innovators propose cladding that is combustible but tested to CAN/ULC-S134. Part 9 reaches that test through Sentence 9.10.14.5.(2), and Part 3 through Sentence 3.1.5.5.(1). Calgary SPV-003 is a specified encapsulated wood-frame exposed wall for single-storey F3 buildings facing dwellings. It is listed, not a project variance. Its details belong to fire-separations-and-spatial-separation.

10. Structural insulated panels. STANDATA 19-BCV-020 covers structural insulated panels. It is archived for the 2019 edition and no 2023 counterpart was found in the precedent index. UNVERIFIED for 2023.

Practitioner notes, not code. The outside-insulation video (DCArchTech, "Outside Insulation and its Vapour Permeance", transcript 6XtuUn_icQU) warns against placing two vapour barriers in one wall, and the presenter uses permeance bands of 0 to 6, 6 to 60, and 60 to 600 ng/(Pa·s·m²) to describe materials. Those bands are the presenter's own shorthand. The code thresholds that matter are the 60 limit for vapour barriers (9.25.4.2.(1)), the 60 and 30 limits in 9.25.5.1, and the Table 9.25.5.2 ratios. The video cites the 2019 edition, and this sheet does not use any number from it.

## Usual mitigations and evidence
Evidence type, and what each type can and cannot establish for this topic:

| Evidence type | Where the code uses it | What it cannot establish |
|---|---|---|
| Manufacturer technical data | Permeance, air leakage and resistance values for the product itself. The code gives generic values in Table A-9.25.5.1.(1) and says that proprietary products may differ. [PDF pp.1424 to 1425] and Note A-9.25.5.1 | Compliance on its own. Generic and manufacturer values are inputs, not evidence of the assembly as built. |
| Accredited laboratory test report | ASTM E96 permeance (9.25.4.2.(1)); CAN/ULC-S134 wall fire test (3.1.5.5.(1)(b) and 9.10.14.5.(2)); CAN/ULC-S101 and CAN/ULC-S124 fire tests (3.1.5.15.(2) and (3), 3.2.3.8.(2)); CAN/ULC-S742 air barrier assembly (5.4.1.2.(1)); STANDATA 23-BCV-018 requires an SCC-accredited laboratory | Performance of an assembly that differs from the one tested. The test must describe the assembly as built. |
| CCMC or approved-body evaluation report | May be used to show compliance (Division A, Sentence 1.2.2.1.(2)). | Coverage beyond the report's scope and edition. The registry snapshot could not be checked live, so a current report must be obtained directly. |
| Provincial STANDATA variance | Accepted alternative for the scope and conditions it states (23-BCV-003, 23-BCV-017, 23-BCV-018). | Anything outside its scope, or any other article. |
| Engineering or other analysis by a named person | Code analysis under Division C, Sentence 2.3.1.1.(3), with the qualifications of the responsible person under Sentence 2.3.1.1.(4). [PDF p.739] | Judgement of performance by the tool. The analysis belongs to the responsible person. |

Test standards by number, and the code sentence that calls each one:

| Standard | What it measures or governs | Code location |
|---|---|---|
| ASTM E96/E96M, dry cup | Water vapour permeance of vapour barriers and sheet materials | 9.25.4.2.(1), 9.25.5.1.(1)(a)(ii) [PDF pp.998 to 999] |
| ASTM E96/E96M, wet cup | Permeance of variable-permeance foundation vapour barriers | 9.25.4.2.(2) [PDF p.998] |
| CAN/CGSB-1.501-M | Permeance of coated gypsum board used as a vapour barrier | 9.25.4.2.(7) [PDF p.999] |
| CAN/CGSB-51.33-M | Membrane-type vapour barrier sheet, other than polyethylene | 9.25.4.2.(5) [PDF p.999] |
| CAN/CGSB-51.34 | Polyethylene sheet used as an air or vapour barrier | 9.25.3.2.(2) [PDF p.997]; 9.25.4.2.(4) [PDF p.999] |
| CAN/ULC-S742 and CAN/ULC-S741 | Air barrier assemblies, and air barrier materials used where an assembly is not evaluated to S742 | 5.4.1.2.(1) and (2) [PDF pp.558 to 559] |
| CAN/ULC-S134 | Fire test of exterior wall assemblies, with flame spread and heat flux limits | 3.1.5.5.(1)(b) [PDF p.137]; 9.10.14.5.(2) [PDF p.897] |
| CAN/ULC-S101 | Fire endurance tests of building construction, used for protected exterior foam | 3.1.5.15.(3)(d) [PDF pp.141 to 142]; 3.2.3.8.(1)(b) and (2) [PDF p.214] |
| CAN/ULC-S124 | Protective coverings for foamed plastic, Class B | 3.1.5.15.(2)(e) [PDF p.141] |
| ASTM D2898 | Accelerated weathering of fire-retardant-treated wood before a fire test | 3.1.5.5.(3) [PDF p.137] |
| CAN/ULC-S701.1, S702.1, S703, S704.1, S705.1, S706.1 | Insulation product standards for boards, fibre, cellulose, polyurethane and wood fibre | 9.25.2.2.(1) [PDF p.995] |
| CAN/ULC-S716.1, S716.2, S716.3 | EIFS materials, installation with water-resistive barrier, and design application | 9.27.14.1.(1), 9.27.14.2.(1), 9.27.14.3.(1) [PDF p.1025]; 5.9.4.1.(1)(b) [PDF p.570] |

Test standards that the code text read here does not name: the air leakage limit of 0.1 L/(s·m²) at 75 Pa in 9.25.5.1.(1)(a)(i) has no named test method in the sentence. The method is UNVERIFIED in this sheet. The 50 kW/m² radiant heat flux in STANDATA 23-BCV-018, Appendix A, is a test condition described in that variance, not a code standard.

Mitigations reviewers look for, grouped by assembly part. Each is a code requirement, with the sentence that sets it.

- Air barrier. The air barrier must be continuous across joints, junctions and penetrations (5.4.1.1.(4), [PDF pp.557 to 558]). In Part 9, the air barrier must be continuous and comply with Subsection 9.25.3 (9.25.3.1.(1), [PDF p.997]).

- Vapour barrier and position. The vapour barrier is set on the warm side (9.25.4.3.(1), [PDF p.999]). Low-permeance sheet materials sit on the warm face, or meet the ratio in Table 9.25.5.2, or sit outboard of a vented air space (9.25.5.2.(1), [PDF p.1000]). In Edmonton, which has 5120 degree-days, the minimum ratio is 0.30 (Table 9.25.5.2, [PDF p.1000]).

- Drained cavity and second plane. The vented air space behind cladding is at least 9.5 mm deep and runs the full height and width of the wall (9.27.2.2.(1)(a), [PDF p.1013]). Penetrations, flashing and furring can interrupt it, provided furring makes up no more than 20 percent of the furred area (9.27.2.2.(2), [PDF p.1013]). Residential walls exposed to precipitation need both planes of protection (9.27.2.2.(4), [PDF p.1014]).

- Clearance. Cladding that moisture harms, such as untreated wood, plywood, OSB, waferboard and hardboard, needs 200 mm clearance from finished ground and 50 mm from a roof surface (9.27.2.4.(1) and (2), [PDF pp.1014 to 1015]).

- Insulating sheathing joints. Joints are sealed, or lapped or tongue-and-groove and detailed to drain (9.27.3.4.(2), [PDF p.1015]). Panels that moisture harms have sealed joints at every edge (9.27.3.4.(2)(a), [PDF p.1015]).

- Cladding attachment. Cladding is fastened to framing or furring, or to blocking (9.27.5.1.(1), [PDF p.1017]). Vertically applied vinyl or insulated vinyl siding, and polypropylene siding, may be attached to sheathing only where the sheathing is at least 14.3 mm lumber, 12.5 mm plywood or waferboard, or 11 mm OSB (9.27.5.1.(2), [PDF p.1017]). Non-wood insulating boards are not on that list. Furring over sheathing is at least 19 by 38 mm lumber (9.27.5.3.(1), [PDF p.1018]) and is spaced at most 600 mm on centre (9.27.5.3.(3), [PDF p.1018]).

- Foamed plastic inside the wall. Foam that forms part of a wall is protected from the adjacent space in the building, unless the space is a concealed space inside the wall (9.10.17.10.(1), [PDF p.907]). For Part 3 walls, a thermal barrier of 12.7 mm gypsum, lath and plaster, masonry, concrete, or a Class B S124 coating applies (3.1.5.15.(2), [PDF p.141]).

- Combustible cladding. In Part 3, combustible cladding on a noncombustible building must meet the S134 limits: flaming not more than 5 m above the opening, and heat flux not more than 35 kW/m² at 3.5 m (3.1.5.5.(1)(b), [PDF p.137]). In Part 9, combustible cladding on an exposing face with more than 10 percent unprotected openings needs an S134 wall (9.10.14.5.(2), [PDF p.897]).

- EIFS. The EIFS must be covered by CAN/ULC-S716.1 with the drainage cavity described in 9.27.14.1.(1) (at least 10 mm deep with at least 13 percent open area), and its design and installation follow S716.2 and S716.3 (9.27.14.3.(1), [PDF p.1025]).

- Roof and soffit venting. Where insulation sits between a ceiling and the roof sheathing, a ventilated space is required unless the assembly is shown to need none (9.19.1.1.(1), [PDF p.939]). Soffits over more than two suites' common attic are protected (3.2.3.16.(1), [PDF p.216]). STANDATA 23-BCV-017 and 23-BCV-018 give the accepted alternatives for unvented roofs and intumescent-coated vented soffits.

Hygrothermal modelling, such as a condensation or moisture-flow model, does not appear as a code requirement in the text read for this sheet. It can serve as an engineering study under 2.3.1.1.(3) if an applicant chooses to use one. UNVERIFIED whether any Alberta SCO expects one for a Part 9 wall.

Practitioner detail, not code. The brick detail videos (transcripts 5xQeFj0bfLA, yv3QUPZAmVw and gKhBTL0wALc) describe an air cavity behind brick with weep holes at the base to let water out. The drip edge video (t8KcQIypnYE) explains why water must be carried past the edge of a cladding or overhang. The THERM video (LlGM_yBP9Ko) shows a two-dimensional heat-flow calculation for a temperature gradient through an assembly. The code text read here does not require THERM for a Part 9 wall. The masonry cavity itself is covered by Sentence 9.27.2.2.(1)(d) [PDF p.1013], and flashing materials by Article 9.27.3.7 [PDF p.1016].

## Engineering / professional triggers
The rules below set when a registered professional is required. They are summarized here only as far as this topic needs them. The full decision table is in professional-involvement.

- Single-family dwellings and small multiple-family dwellings are exempt from the registered-professional requirement, unless the authority having jurisdiction requires involvement. Div C, Sentence 2.4.1.1.(1), which covers single-family dwellings and multiple-family dwellings of four units or fewer. [PDF p.739]

- The authority having jurisdiction may require one or more registered professionals to authenticate drawings and specifications and to carry out field reviews, where the size or complexity of a project may raise special safety concerns. Div C, Sentence 2.4.1.1.(4). [PDF p.740]

- Buildings outside that exemption must have their drawings and specifications authenticated by registered professionals. Div C, Sentence 2.4.1.1.(3). [PDF p.740] For such projects the owner must retain a coordinating registered professional before applying for the permit. Div C, Sentences 2.4.2.2.(1) and 2.4.2.3.(1). [PDF p.741]

- An alternative solution for any envelope article needs the documentation in Div C, Sentence 2.3.1.1.(2) to (4). That documentation names the person responsible for the design, with that person's qualifications. Div C, Article 2.3.1.1. [PDF p.739]. Whether the named person must be a registered professional depends on the Safety Codes Act and the Division C registered-professional rules. This sheet does not verify that point.

- Structural bracing that depends on sheathing: Div B, Sentence 9.23.13.1.(2)(a) lists the bracing options for an exterior wall. A wall braced by other sheathing may still be braced under Part 4 or by good engineering practice, such as the CWC 2014 guide. Div B, Sentence 9.23.13.1.(2)(b) [PDF p.978] says so. Div B, Sentence 9.4.1.1.(1) [PDF pp.836 to 837] lets Part 9 structural members be designed under Part 4 or the CWC guide.

- The challenge scope PDF quotes a professional-design sentence and numbers it in the 2.4.2 series. That sentence does not appear in the NBC(AE) 2023 text indexed here. Div C, Article 2.4.2.1 is the application article, and Div C, Sentences 2.4.2.2.(1) and 2.4.2.3.(1) carry the coordinating-professional duties [PDF p.741]. The quotation is not used as a code citation in this sheet, and its wording is UNVERIFIED against the 2023 edition.

Decision table for envelope signals. The table gives the code answer, not a project decision.

| Project signal | Required? | Discipline | Citation |
|---|---|---|---|
| Single-family house, prescriptive envelope | No, unless the authority requires it | None set by code | Div C 2.4.1.1.(1) and (4) [PDF pp.739 to 740] |
| Multiple-family building of four units or fewer | No, unless the authority requires it | None set by code | Div C 2.4.1.1.(1)(b)(ii) and (4) [PDF pp.739 to 740] |
| Residential building outside the exemption, such as five or more units | Yes, drawings and specifications authenticated | Architecture and engineering as applicable | Div C 2.4.1.1.(3) [PDF p.740]; 2.4.2.2.(1) [PDF p.741] |
| Authority requires professionals for a complex envelope | Yes, if required | As the authority specifies | Div C 2.4.1.1.(4) [PDF p.740] |
| Bracing relies on a sheathing not listed in Div B, Sentence 9.23.13.1.(2)(a) | Depends on the chosen route | Engineer under Part 4, or good engineering practice | Div B 9.23.13.1.(2)(b) [PDF p.978] |
| Alternative solution for an envelope article | Documentation required; the responsible person is named | Depends on the Safety Codes Act and Division C 2.4. UNVERIFIED | Div C 2.3.1.1.(2) to (4) [PDF p.739] |
| EIFS design application | UNVERIFIED | UNVERIFIED | CAN/ULC-S716.3, cited in Div B, Sentence 9.27.14.3.(1) [PDF p.1025] |
| Hygrothermal or condensation model | Not required by the text read here | Optional engineering study | Div C 2.3.1.1.(3) [PDF p.739] |

Where the tool stops. The tool does not decide any of the following. It flags each one and sends the question to a named professional, to the test report, or to the authority having jurisdiction.

- Whether a measured permeance or air leakage value is acceptable for a particular product. That needs the test report and the product's scope.

- Whether bracing or cladding fastening through continuous insulation is adequate. That needs a structural design under Part 4 or the CWC guide.

- Whether the condensation risk or thermal performance is acceptable for a given wall. The code gives prescriptive values and the tool cites them, but it does not judge the wall.

- Whether a CCMC report, an EIFS system or an insulated sheathing assembly performs as the report claims.

- Whether a fire test result applies to a different wall assembly, or whether a foam protection detail is equivalent.

## Interactions with other topics
A change to the envelope usually touches one or more of these topics. Each entry says what the link is.

- fire-separations-and-spatial-separation. Exposing faces and their cladding (Div B 9.10.14.5 and 9.10.15.5), soffit protection (9.10.12.4), and intumescent soffits (STANDATA 23-BCV-018). Limiting distance and the openings percentage are set by that topic, and this sheet only reads the cladding limit that follows from them. Calgary SPV-003 is also indexed under that topic.

- combustible-construction-and-mass-timber. Part 3 combustible cladding (3.1.5.5), combustible components in exterior walls (3.1.5.6), combustible insulation and foamed plastic (3.1.5.14 and 3.1.5.15), and encapsulated mass timber cladding (3.1.6.9). This sheet carries the same articles for Part 9 and Part 5 comparisons only.

- structural-and-framing. Bracing by sheathing (9.23.13.1), wood sheathing grade and thickness (9.23.17), the design routes for Part 9 structure (9.4.1.1), and cladding anchorage (9.27.5). A foam panel that replaces OSB changes the bracing route and the fixing of cladding. The structural check belongs to that topic.

- energy-efficiency. Effective wall resistance in Table 9.36.2.6-A and -B. For Edmonton (Zone 7A) the wall minimum is RSI 3.08 without a heat-recovery ventilator and RSI 2.97 with one. Under-slab insulation (9.36.2.8 and STANDATA 23-BCV-003) is also in that topic.

- hvac-ventilation-plumbing. Ventilation changes which wall table applies (9.36.2.6-A or -B), duct insulation and sealing (9.25.1.1.(3)), and interior condensation control (5.3.1.2). Attic and roof venting (9.19.1.1) is shared with this topic.

- evidence-and-conformity. CCMC evaluation reports (Division A, Sentence 1.2.2.1.(2)), the test standards in the table above, and the limits of a product listing as evidence for an assembly.

- professional-involvement. Division C, Articles 2.4.1.1 to 2.4.2.3 and the qualifications rule in 2.3.1.1.(4). This sheet gives only the envelope triggers.

- process-and-admin. The variance route, its written request to the Provincial Building Administrator (Division C, Article 2.2.1.2), and STANDATA variances. The administrative steps belong to that topic.

- housing-secondary-suites-part9. Row houses and secondary suites put exterior walls next to each other or close to property lines. Unvented roof assemblies (STANDATA 23-BCV-017) are also used on houses with suites.

- firefighting-alarms-sprinklers. Div B, Sentence 3.1.5.5.(1) allows combustible cladding where a building is three storeys or less or sprinklered throughout. Div B, Sentence 3.2.3.16.(4) allows the soffit protection to be omitted where the compartments are sprinklered. The sprinkler design belongs to that topic.

- occupancy-and-accessibility. The major occupancy decides whether Part 9 or Parts 3 to 6 apply (Division A, Articles 1.3.3.2 and 1.3.3.3).

- code-structure-and-attribution. How to read an attribution row, and how to find the root sentence of an exception, both of which the Attributions and Intent sections of this sheet use.

## Common refusal / "more info" causes
Each item below is an omission that a reviewer can check against a verified sentence. The number after each item is the sentence that would be checked.

1. Permeance and air leakage not stated for an insulating sheathing or panel. Without them, Sentence 9.25.5.1.(1) cannot be applied. [PDF p.999]

2. Permeance measured for one thickness, and the application uses another. Table A-9.25.5.1.(1) says permeance depends on thickness and that product values can differ from the generic table. [PDF pp.1424 to 1425]

3. No statement of where the innermost impermeable surface lies. The ratio in Table 9.25.5.2 cannot be computed without it. [PDF p.1000]

4. The sheathing is not described as non-wood-based, or as having an integral sheathing membrane. That description decides whether a separate membrane is needed. Sentence 9.27.3.4.(1). [PDF p.1015]

5. No joint detail for insulating sheathing, or joints left unsealed where the panel is moisture-sensitive. Sentence 9.27.3.4.(2). [PDF p.1015]

6. No statement of the drained air space or capillary break for a residential wall. Sentences 9.27.2.2.(1) and (4). [PDF pp.1013 to 1014]

7. Degree-days or moisture index not given for the location. Table 9.25.5.2 [PDF p.1000] and Sentence 9.27.2.2.(5) [PDF p.1014] both depend on them.

Table C-2 lists selected Alberta locations only [PDF p.667].

8. Combustible cladding on an exposing face above 10 percent openings, without an S134 test of the assembly as built. Sentence 9.10.14.5.(2). [PDF p.897]

9. Foamed plastic in a Part 3 wall without a thermal barrier or a Class B S124 coating. Sentence 3.1.5.15.(2). [PDF p.141]

10. Foamed plastic in a Part 9 wall with no interior protection and no concealed-space argument. Sentence 9.10.17.10.(1). [PDF p.907]

11. EIFS without CAN/ULC-S716.1 coverage, or without the drainage cavity of at least 10 mm and 13 percent open area. Those EIFS fall to Part 5. Sentence 9.27.14.1.(1). [PDF p.1025]

12. Vertically applied vinyl or insulated vinyl siding fixed to an insulating board that is not on the sheathing list. Sentence 9.27.5.1.(2). [PDF p.1017]

13. Bracing shown to come from a sheathing not on the list, with no Part 4 or CWC design, and no interior panel finish. Sentence 9.23.13.1.(2). [PDF p.978]

14. A STANDATA from the 2019 edition cited for a 2023 project. The precedent index marks 19-BCV-017, 19-BCV-022 and 19-BCV-020 as archived, with the note "Do not use unchanged for a new 2023-edition project". Precedent index record, not a code sentence.

15. The 2020 national intent statements or the 2019 edition cited as Alberta law. The intent statements are explanatory only. Example intent: NBC 2020 Intent Statements, 9.27.3.4.(1) [PDF p.2678].

16. Registered-professional authentication missing where Division C requires it, or where the authority of jurisdiction has asked for it. Sentences 2.4.1.1.(3) and (4). [PDF p.740]

17. An alternative solution submitted without the Section C attributions, or without the responsible person's qualifications. Sentences 2.3.1.1.(2) to (4). [PDF p.739]

Items 14 and 15 are about the reference sources, not about the building. A reviewer checks them first because they change the test the applicant must pass.

## Precedents
These are the precedents on file for the topic, with the status each one carries. Issue dates come from the local PDFs. Live status could not be confirmed, because the open.alberta.ca publication page returned HTTP 520 on both fetch attempts on 2026-10-19.

Current Alberta variances in the 2023 edition:

- STANDATA 23-BCV-003, Insulation below a heated floor. Issued May 2024. Applies to Part 9 buildings with a heated floor in contact with the ground. A minimum RSI 1.32 (R-7.5) under-slab insulation complies. Local copy: reference/precedents/alberta-standata/standata-nbc2023-variance-23-bcv-003.pdf. The precedent index also lists a condition about frost depth, and that condition does not appear in the PDF text read for this sheet. The discrepancy is recorded in Open questions.

- STANDATA 23-BCV-017, Unvented roof assembly. Issued September 2025. Applies to Part 9 residential roof assemblies within the scope of the RDH evaluation report 32139.000, which must accompany the permit application. Local copy: reference/precedents/alberta-standata/standata-nbc2023-variance-23-bcv-017.pdf.

- STANDATA 23-BCV-018, Vented soffit protection. Issued September 2025. Accepts a tested intumescent-coated vented substrate in place of the solid soffits required by 9.10.14.5.(12), 9.10.15.5.(11) and 9.10.12.4.(2) and (3). Conditions: SCC-accredited laboratory testing, performance at least that of 11 mm plywood (Appendix A), and installation to the manufacturer's instructions or the test documentation. Local copy: reference/precedents/alberta-standata/standata-nbc2023-variance-23-bcv-018.pdf.

Archived 2019-edition variances, not to be used unchanged for a 2023 project:

- STANDATA 19-BCV-017, vented soffit protection (issued 2020). The 2023 version is 23-BCV-018. Local copy: reference/web/building-envelope-insulation-cladding/standata-19-bcv-017.pdf, the same size as the index copy in reference/precedents/alberta-standata/.

- STANDATA 19-BCV-022, unvented roof assembly (issued April 2022). The 2023 version is 23-BCV-017. Local copy: reference/web/building-envelope-insulation-cladding/standata-19-bcv-022.pdf. The precedent index holds its own copy.

- STANDATA 19-BCV-020 (and REV1), structural insulated panels. Archived. The 2023 counterpart was not found in the precedent index. UNVERIFIED.

- STANDATA 19-BCV-018 (and revisions), adhered masonry veneer, generic engineered details for Part 9 residential buildings. Archived. No 2023 counterpart found in the index. UNVERIFIED.

Related precedents from other topics:

- Calgary SPV-003, Construction of Exposed Building Face (revision 3, 2025-02-12). Accepts a specified encapsulated wood-frame exposed-wall assembly for qualifying single-storey F3 Part 9 buildings that face dwellings they do not serve. Listed in the precedent index. Its details are in fire-separations-and-spatial-separation.

- Calgary and Edmonton policy solutions. The precedent index has no envelope-specific Edmonton policy. The one Edmonton interpretation that matched a keyword search (B23-05, Application of 9.9.4.4) concerns egress and is not an envelope precedent.

CCMC registry (supplied snapshot, 462 product assessments, not refreshed live). Products that appear in the snapshot and bear on this topic are listed in Typical alternative solutions. The snapshot has no entry named BTRboard. Two standard web searches on 2026-10-19 for "BTRboard CCMC evaluation report insulated sheathing" and related wording found no BTRboard evaluation either. The only BTRboard source on file is a GOHBA member directory page, which describes the company and its product. That page is company description, not evaluation. Reference: reference/web/building-envelope-insulation-cladding/gohba-btrboard.html.

## Worked example
The case is a continuous-insulation sheathing panel in a Part 9 house. The topic scope names a product called BTRboard for this example. The sheet cannot say whether BTRboard meets the code, because the product's data are not on file. The example therefore shows which sentences decide the answer and which values must be supplied.

### The case
A single-family house in Edmonton, classed as Part 9 under Division A, Sentence 1.3.3.3.(1). The site data come from NBC(AE) 2023:

- Heating degree-days 5120, which falls in Zone 7A (Table C-2, PDF p.667).

The Part 9 wall table in Article 9.36.2.6 [PDF p.1073] sets the Zone 7A minimum.

- Moisture index 0.5 (Table C-2, PDF p.667).

- 1-in-50 hourly wind pressure 0.45 kPa (Table C-2, PDF p.667).

- Seismic spectral acceleration Sa(0.2) 0.103 (Table C-3, PDF p.672).

The capillary-break trigger in Sentence 9.27.2.2.(5) is not met, because the moisture index is not over 1.00 at 5000 degree-days or more [PDF p.1014].

The wall, from inside out, is 12.7 mm gypsum board, 2 by 6 studs with cavity batt insulation, 11 mm OSB, and vertically applied insulated vinyl siding. The proposal replaces the OSB with a 50 mm rigid insulating sheathing panel. The sheathing is not an exposing building face. The panel's substrate, permeance, air leakage, joint system and CCMC status are not on file. The GOHBA member page describes the panel as combining a "certified sheathing substrate" with a Class A fire-rated polyurethane foam core, and it describes "vapour permeability". Those are the company's claims, not verified data.

### Step 1. Establish the product's properties
The answer depends on the values in this table. None is on file for BTRboard.

| Item | Why it matters | Cite | Status |
|---|---|---|---|
| Substrate wood-based or not | Decides whether a separate membrane is needed | Div B, Sentence 9.27.3.4.(1) [PDF p.1015] | UNVERIFIED |
| Integral sheathing membrane | The second route in the same sentence | Div B, Sentence 9.27.3.4.(1) [PDF p.1015] | UNVERIFIED |
| Air leakage at 75 Pa | Half of the test for a low-permeance sheet material | Div B, Clause 9.25.5.1.(1)(a)(i) [PDF p.999] | UNVERIFIED |
| Water vapour permeance, dry cup | The other half of that test, and the exemption threshold of 30 | Div B, Clause 9.25.5.1.(1)(a)(ii) and Sentence 9.25.5.1.(4) [PDF pp.999 to 1000] | UNVERIFIED |
| Thermal resistance and the location of the innermost impermeable surface | Needed for the ratio in Table 9.25.5.2 | Div B, Sentence 9.25.5.2.(1) [PDF p.1000] | UNVERIFIED |
| Joint system | Joints must be sealed or detailed to drain | Div B, Sentence 9.27.3.4.(2) [PDF p.1015] | UNVERIFIED |
| Foam type and flame-spread rating | Interior protection and Part 3 limits | Div B, Sentence 9.10.17.10.(1) [PDF p.907] | UNVERIFIED |
| Evaluation report and its scope | A CCMC report can be used to show compliance | Div A, Sentence 1.2.2.1.(2) [PDF p.38] | No report found |

Generic values give a starting point only. Table A-9.25.5.1.(1) lists values for common materials, and its note says that proprietary products may differ [PDF pp.1424 to 1425]. The table gives these generic figures. A 27 mm foil-faced polyisocyanurate has negligible air leakage and a permeance of 4.3 ng/(Pa·s·m²). A 27 mm paper-faced polyisocyanurate has 61.1. A 25 mm extruded polystyrene has 23 to 92. A 25 mm expanded polystyrene (Type 2) has air leakage of 0.0214 and a permeance of 86 to 160. An 11 mm OSB has air leakage of 0.0108 and a permeance of 44. The table notes that the values are for the listed thickness and that permeance depends on thickness.

### Step 2. Decide whether a separate membrane is needed
If the panel is non-wood-based rigid exterior insulating sheathing, or insulating sheathing with an integral membrane, no separate sheathing membrane is required [PDF p.1015, Sentence 9.27.3.4.(1)]. If the panel is wood-based and has no integral membrane, Sentence 9.27.3.3.(1) applies and at least one sheathing membrane must go beneath the cladding [PDF p.1015]. The answer depends on the substrate and membrane questions in Step 1, both UNVERIFIED.

### Step 3. Check the joints
Sheathing panels subject to moisture deterioration need sealed joints at all joints. Other panels need sealed joints, or lapped or tongue-and-groove joints detailed to drain water to the exterior [PDF p.1015, Sentence 9.27.3.4.(2)].

### Step 4. Decide whether the vapour and position rules apply
The OSB was exempt from Sentence 9.25.5.1.(1). Sentence 9.25.5.1.(3) [PDF p.1000] exempts wood-based sheathing of 12.5 mm or less that complies with Article 9.23.17.2 [PDF p.989]. Replacing the OSB with a non-wood panel removes that exemption. The panel must then be tested against Sentence 9.25.5.1.(1). If it has air leakage under 0.1 L/(s·m²) at 75 Pa and permeance under 60 ng/(Pa·s·m²), it is a low-permeance sheet material and must follow Article 9.25.5.2 [PDF p.1000].

Sentence 9.25.5.1.(4) [PDF p.1000] gives an exemption where permeance is at least 30 ng/(Pa·s·m²), thermal resistance is at least RSI 0.7, and the degree-days are under 6000. Edmonton's 5120 degree-days pass that test. The generic figures show how the result depends on the product. A foil-faced polyisocyanurate at 4.3 falls under 30, so it gets no exemption. An expanded polystyrene at 86 to 160 is above 60, so Sentence 9.25.5.1.(1) does not apply to it at all.

Berwyn, at 6100 degree-days (Table C-2, PDF p.667), is above 6000, so the exemption would not be available there.

Article 9.25.5.2 allows low-permeance sheet materials to sit on the warm face, or to meet the ratio in Table 9.25.5.2, or to sit outboard of a vented air space [PDF p.1000]. Edmonton's minimum ratio is 0.30 [PDF p.1000, Table 9.25.5.2]. The ratio uses the resistance outboard of the material's inner surface over the resistance inboard of it. The applicant must state where that inner surface lies.

The arithmetic below uses hypothetical values to show how the ratio works. The values are not product data. Assume the inboard resistance (cavity insulation and gypsum) is RSI 3.6. The ratio needs at least 0.30 times 3.6, which is RSI 1.08 outboard. A 50 mm board of RSI 1.0 gives 1.0 divided by 3.6, which is 0.28, and fails. The designer would need more outboard resistance, or the vented air space route in Sentence 9.25.5.2.(1)(c). For walls, that air space must also meet Clause 9.27.2.2.(1)(a) [PDF p.1013], as Sentence 9.25.5.2.(2) requires [PDF p.1000].

### Step 5. Check cladding fastening
Cladding must be fastened to framing or furring, or to blocking [Sentence 9.27.5.1.(1), PDF p.1017]. Vertically applied vinyl or insulated vinyl siding may be attached to sheathing only if the sheathing is at least 14.3 mm lumber, 12.5 mm plywood or waferboard, or 11 mm OSB [PDF pp.1017 to 1018, Sentence 9.27.5.1.(2)]. The 11 mm OSB in the current wall meets that list. A non-wood panel does not. The siding must therefore fasten to the framing or to furring through the panel. Furring over sheathing is at least 19 by 38 mm lumber, secured to the framing, and spaced at most 600 mm on centre [PDF p.1018, Sentences 9.27.5.3.(1) and (3)]. The code text read here does not give a fastener length for fixing through 50 mm of panel. That length, in Table 9.27.5.4.-A, is not reproduced in this sheet. UNVERIFIED.

### Step 6. Check bracing
Sentence 9.23.13.1.(1) [PDF p.978] covers this wall, because Sa(0.2) is not more than 0.70 and the 1-in-50 hourly wind pressure is under 0.80 kPa. Under Sentence 9.23.13.1.(2)(a), exterior walls may be braced by panel-type cladding under Section 9.27, by sheathing of plywood, OSB, waferboard, fibreboard, gypsum board or diagonal lumber that complies with Subsection 9.23.17 and is fastened to Table 9.23.3.5.-A, or by a panel-type interior finish under Section 9.29. Sentence 9.23.13.1.(2)(b) [PDF p.978] also allows Part 4 and good engineering practice.

The original OSB was a listed bracing sheathing. The panel is not on that list. Bracing must therefore come from another route. The interior gypsum board can provide bracing under the interior-finish route, if it meets Section 9.29. That section is not read in this sheet, so the point is UNVERIFIED. The intent of 9.27.5.3 refers to panel-type siding used as bracing. Whether vinyl lap siding is panel-type siding is also UNVERIFIED. The sheathing change alone does not remove bracing, but the bracing route must be stated.

### Step 7. Check fire
Sentence 9.10.17.10.(1) protects foam forming part of a wall from the adjacent space in the building. The protection is an interior finish, sheet metal in a non-Group C building, or a thermal barrier that meets Sentence 3.1.5.15.(2). Concealed spaces inside wall assemblies are excluded [PDF p.907]. Here the board's inner face bears on the stud bays. Those bays are concealed spaces within the wall assembly, so the reading that interior protection is not required for the board is possible. The reading is UNVERIFIED with the authority having jurisdiction.

If the wall were an exposing building face above 10 percent unprotected openings, Sentence 9.10.14.5.(2) [PDF p.897] would apply. Combustible cladding is then permitted only where the wall assembly complies with Clause 3.1.5.5.(1)(b) [PDF p.137] when tested to CAN/ULC-S134. A new sheathing changes the tested assembly. The code text read here does not state how closely a test must match the assembly as built. UNVERIFIED.

### Step 8. Check energy
The wall minimum in Zone 7A is RSI 3.08 without a heat-recovery ventilator [PDF p.1073, Table 9.36.2.6.-A]. It is RSI 2.97 with one [PDF p.1073, Table 9.36.2.6.-B]. The continuous insulation adds effective resistance, and that calculation belongs to energy-efficiency.

### Step 9. Check professional involvement
A single-family dwelling is exempt from the registered-professional requirement, unless the authority having jurisdiction requires involvement [PDF p.739, Sentence 2.4.1.1.(1), and PDF p.740, Sentence 2.4.1.1.(4)]. A variance request needs the documentation in Sentences 2.3.1.1.(2) to (4), which names the person responsible for the design and that person's qualifications [PDF p.739]. Choosing bracing under Part 4 or the CWC guide may require a designer. The tool does not decide that.

### Step 10. CCMC or variance
The decision follows the order below. The code text supports each route. The product data decide which route applies, and those data are not on file.

1. If the panel's data meet Sentence 9.27.3.4.(1), the joints meet Sentence 9.27.3.4.(2), and the panel meets Sentence 9.25.5.1.(4) or the ratio in Article 9.25.5.2, the wall follows the articles. No variance is needed. The test data then serve as evidence of the product's properties.

2. If the panel is wood-based and has no integral membrane, a membrane is required under Sentence 9.27.3.3.(1). A non-wood panel alone does not reach the articles in that case.

3. A CCMC evaluation report can be used to determine compliance [PDF p.38, Sentence 1.2.2.1.(2)]. It is not a variance. If a report exists for BTRboard, it must be obtained directly, checked for scope and edition, and read for its wall conditions. No report was found. UNVERIFIED.

4. If the wall cannot meet Article 9.25.5.2 and has no exemption, the choices are a vented air space outboard of the panel, which is an article route, or a variance. A variance is a written request to the Provincial Building Administrator under Div C, Sentence 2.2.1.2.(1) [PDF p.729], with the alternative-solution documentation in Div C, Sentence 2.3.1.1.(2) [PDF p.739].

Where a variance is needed, the Section C table below lists the articles that the request would name. The rows are verified against the attribution tables and the NBC 2020 intent statements.

### Section C table for the variance route
Pairs are shown as printed. Objective and function definitions are in the Attributions section above.

| Article | Objective codes, as printed | Function codes, as printed | Intent (NBC 2020 Intent Statements, paraphrase) |
|---|---|---|---|
| 9.27.3.3.(1) sheathing membrane beneath cladding. Pairs [F61,F55-OS2.3] and [F61,F55-OH1.1,OH1.2,OH1.3] (Part 9 attribution table, PDF p.1200) | OS2.3; OH1.1, OH1.2, OH1.3 | F61; F55 | Limit excessive air infiltration, which causes wind-washing and condensation, and limit precipitation ingress. NBC 2020 Intent Statements, 9.27.3.3.(1) [PDF pp.2675 to 2676]. |
| 9.27.3.4.(1) insulating sheathing in lieu of membrane. No printed pairs. The intent names 9.27.3.3.(1). | None printed | None printed | Limits the application of 9.27.3.3.(1) where insulating sheathing gives the air and precipitation protection a membrane normally gives. States 9.27.3.4.(2). NBC 2020 Intent Statements, 9.27.3.4.(1) [PDF p.2678]. |
| 9.27.3.4.(2) joints of insulating sheathing. Pairs [F61,F55-OS2.3] and [F61,F55-OH1.1,OH1.2,OH1.3] (Part 9 attribution table, PDF p.1200) | OS2.3; OH1.1, OH1.2, OH1.3 | F61; F55 | Limit inadequate joint sealing or detailing that lets in moisture or air and causes deterioration. NBC 2020 Intent Statements, 9.27.3.4.(2) [PDF pp.2678 to 2679]. |
| 9.25.5.1.(1) low-permeance sheet materials. No printed pairs. The intent names the position article that follows. | None printed | None printed | States, in part, the application of the position article that follows. NBC 2020 Intent Statements, 9.25.5.1.(1) [PDF p.2554]. |
| 9.25.5.2.(1) position of low-permeance sheet materials. Pairs [F62,F63-OS2.3] and [F62,F63-OH1.1,OH1.2] (Part 9 attribution table, PDF p.1196) | OS2.3; OH1.1, OH1.2 | F62; F63 | Limit inadequate moisture diffusion, venting or drainage to the exterior, which could lead to condensation. NBC 2020 Intent Statements, 9.25.5.2.(1) [PDF p.2556]. |
| 9.25.2.2.(1) insulation materials conform to listed standards. Pairs [F51,F63,F80-OH1.1,OH1.2] and [F63,F80-OS2.3] (Part 9 attribution table, PDF p.1194) | OH1.1, OH1.2; OS2.3 | F51, F63, F80 | Limit the probability that the thermal performance of required insulation falls well below expectations. NBC 2020 Intent Statements, 9.25.2.2.(1) [PDF pp.2513 to 2514]. |
| 9.25.3.1.(1) required air barrier system. Pairs [F55-OH1.1,OH1.2,OH1.3], [F40-OH1.1] and [F55-OS2.3] (Part 9 attribution table, PDF p.1195) | OH1.1, OH1.2, OH1.3; OS2.3 | F55; F40 | Limit excessive heat loss or gain from air movement, air infiltration and exfiltration, and airborne vapour transfer. NBC 2020 Intent Statements, 9.25.3.1.(1) [PDF pp.2531 to 2532]. |
| 9.27.5.1.(1) fastening cladding to framing, furring or blocking. Several printed pairs, including [F20-OS2.1,OS2.3] and [F22-OS2.3,OS2.4,OS2.5] (Part 9 attribution table, PDF p.1201) | OS2.1, OS2.3, OS2.4, OS2.5, OP2.1, OP2.3, OP2.4, OP2.5, OH1.1 to OH1.3, OH4, OS3.1, OS3.7 | F20, F22 | Limit the probability of fastening cladding to an inappropriate substrate, which could leave the cladding without enough resistance to gravity and wind loads. NBC 2020 Intent Statements, 9.27.5.1.(1) [PDF pp.2694 to 2697]. |
| 9.27.5.1.(2) cladding that may fasten to sheathing. Pairs [F20-OH1.1,OH1.2,OH1.3] and [F20-OS2.1,OS2.3] (Part 9 attribution table, PDF p.1201) | OH1.1 to OH1.3; OS2.1, OS2.3 | F20 | Supersedes the fastening requirement of 9.27.5.1.(1) for some cladding materials, allowing fastening to sheathing that gives enough support. NBC 2020 Intent Statements, 9.27.5.1.(2) [PDF pp.2697 to 2698]. |
| 9.23.13.1.(2) bracing of exterior walls. Printed pairs include [F20-OS2.1,OS2.3,OS2.5], [F22-OS2.3,OS2.4,OS2.5] and [F20,F22-OH1.1,OH1.2,OH1.3] (Part 9 attribution table, PDF p.1186) | OS2.1, OS2.3, OS2.5, OP2.1, OP2.3, OH1.1 to OH1.3 and others in the row | F20, F22 | Limit the inability to resist expected gravity and lateral loads, which could cause excessive racking. NBC 2020 Intent Statements, 9.23.13.1.(2) [PDF p.2352]. |
| 9.10.17.10.(1) protection of foamed plastics. Pairs [F01,F02,F05-OS1.5] (Part 9 attribution table, PDF p.1130) | OS1.5 | F01, F02, F05 | Limit the probability that foamed plastic insulation is exposed to fire or high temperatures and ignites. NBC 2020 Intent Statements, 9.10.17.10.(1) [PDF pp.1427 to 1428]. |

Rows 8 to 10 are the wall-fixing, bracing and fire rows. The row for 9.10.14.5.(2) is omitted because this case is not an exposing building face. If it were, its pair [F03-OP3.1] (Part 9 attribution table, PDF p.1129) would be added with the intent in NBC 2020 Intent Statements, 9.10.14.5.(2) [PDF pp.1408 to 1409].

### What the case decides, and what it does not
The code text decides which articles apply, which values the applicant must supply, and which routes exist. The case does not decide whether BTRboard meets those articles. That depends on the product's substrate, permeance, air leakage, joints and position, none of which is on file. It also does not decide the bracing or fastening adequacy, which needs a designer, or the fire reading, which needs the authority having jurisdiction.

## Open questions / uncertainty
These points could not be settled from the sources read.

1. BTRboard. No CCMC or other evaluation report was found in the registry snapshot or in two standard web searches on 2026-10-19. The product's substrate, membrane, permeance, air leakage, joint system and foam type are not on file. The GOHBA page is a company description, and its claims of a "certified sheathing substrate" and "vapour permeability" are unverified.

2. CCMC suffixes. The registry records 250 "-R" numbers and 212 "-L" numbers. This sheet uses the numbers as printed and does not state what each suffix means. UNVERIFIED.

3. CCMC snapshot. The live registry could not be reached on 2026-10-18 (DNS failure). The snapshot has no date of publication. Every CCMC number in this sheet needs a live check before use.

4. STANDATA 23-BCV-003. The precedent index records a second condition about frost depth, which says not to reuse the lower historical value. That condition does not appear in the PDF text read for this sheet. Check the source PDF on open.alberta.ca.

5. STANDATA currency. The open.alberta.ca publication page returned HTTP 520 on two WebFetch attempts on 2026-10-19. Whether 23-BCV-003, 23-BCV-017 or 23-BCV-018 has been withdrawn or replaced is not confirmed live. The issue dates come from the local PDFs (May 2024; September 2025).

6. Sentence 9.25.5.1.(3). The intent statement cites clause (b) of Sentence 9.25.5.1.(1), but the sentence text exempts the sheathing from all of Sentence 9.25.5.1.(1). This sheet treats the sentence text as controlling. The authority having jurisdiction's reading is UNVERIFIED.

7. Air leakage test. Sentence 9.25.5.1.(1)(a)(i) gives the 0.1 L/(s·m²) limit at 75 Pa, but names no test method. Note A-9.25.5.1 was not read in full, so the method may be there. UNVERIFIED.

8. Foamed plastic behind the stud bay. Whether a sheathing panel whose inner face bears on a concealed stud bay falls outside Sentence 9.10.17.10.(1) is an interpretation, UNVERIFIED with the authority having jurisdiction.

9. Test matching. The code text read here does not say how closely a fire or air-barrier test must match the assembly as built. UNVERIFIED.

10. Other Alberta communities. Table C-2 lists selected locations only. The moisture index and degree-days for any other community must come from the full table or from the Appendix C map, which was not read in full.

11. Bracing by cladding. Sentence 9.23.13.1.(2)(a)(i) refers to panel-type cladding. The intent of 9.27.5.3 refers to panel-type siding. Whether vinyl lap siding counts as panel-type is UNVERIFIED. The interior-finish route depends on Section 9.29, which was not read in this sheet.

12. Fastener length. Table 9.27.5.4.-A, which sets nail and screw sizes and spacing, is not reproduced here. The length needed to fix cladding through insulation is UNVERIFIED.

13. Challenge scope PDF. The challenge scope PDF quotes "2.4.2.1.(1)" as a professional-design sentence, and the same quotation does not appear in the NBC(AE) 2023 text indexed here. The 2023 text places coordinating-professional duties in Sentences 2.4.2.2.(1) and 2.4.2.3.(1). This discrepancy is reported to the parent, and the quotation is not used as a citation.

14. Challenge scope PDF, variance wording. The challenge scope PDF quotes "2.2.1.2.(1)" as a variance sentence in words that differ from the 2023 text indexed here. The 2023 text reads as a written request to the Provincial Building Administrator. This discrepancy is also reported to the parent.

15. EIFS design. Whether CAN/ULC-S716.3 must be applied by a registered professional is UNVERIFIED.

16. Generic permeance values. Table A-9.25.5.1.(1) draws on older studies listed in its notes, including a 1988 CMHC report and a 2002 IRC report. Current products may differ, and the table says so.

17. Practitioner videos. The outside-insulation video (6XtuUn_icQU) gives permeance bands that are the presenter's own shorthand. The videos cite the 2019 edition. None of their numbers is used in this sheet as code.

18. Calgary SPV-003. The sheet records only its index entry. Its details are for the fire topic and were not read in full here.

## Sources
Every source below was read or queried for this sheet. Access dates are 2026-10-18 for local files and the code database, and 2026-10-19 for the web queries. Article numbers and pages are in the body.

NBC(AE) 2023, 2nd printing, read from reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf through tools/codesearch.py and the code database. PDF pages are as cited.

- Division A, compliance and materials: Sentence 1.2.2.1.(1) and (2) [PDF p.38].

- Application of Parts 3 to 6 [PDF pp.39 to 40].

- Application of Part 9 [PDF p.40].

- Division A, Part 2 objectives [PDF pp.68 to 73] and Part 3 functional statements [PDF pp.79 to 81].

- Division B, Part 3 combustibility, cladding and insulation articles [PDF pp.135 to 216], including the exterior cladding article [PDF p.148].

- Division B, Part 5 environmental separation [PDF pp.553 to 573], including the applicable-standards table [PDF p.565].

- Division B, Part 9 structural design, foamed plastic, exposing faces, venting, environmental separation, cladding and the wall tables [PDF pp.836 to 1074].

- Table 9.25.5.2 [PDF p.1000].

- Attribution tables: Part 3 Table 3.10.1.1 [PDF pp.321 and 336]; Part 5 Table 5.10.1.1 [PDF pp.571 to 573]; Part 9 Table 9.38.1.1 [PDF pp.1129 to 1130, 1144, 1186 and 1194 to 1204].

- Division C, variance and professional rules: Sentences 2.2.1.2.(1) and (3) [PDF p.729]; Article 2.3.1.1 [PDF p.739]; Article 2.4.1.1 [PDF pp.739 to 740]; Articles 2.4.2.1 to 2.4.2.3 [PDF p.741].

- Appendix A: Note A-9.25.5.1 and Table A-9.25.5.1.(1) [PDF pp.1424 to 1425].

- Appendix C: Table C-2 climatic data [PDF p.667] and Table C-3 seismic values [PDF p.672].

NBC 2020 Intent Statements, codesearch document NBC-2020-Intent-Statements, cited by PDF page for explanatory intent only. Pages used: [PDF pp.67 to 68, 393, 395, 401, 1408 to 1409, 1427 to 1428, 1710 to 1711, 2352, 2513 to 2556, 2665 to 2698, 2702 to 2703, 2778 to 2781].

Code database, codedb/build/codedb.sqlite, read-only queries on 2026-10-18 and 2026-10-19. Used for provision text, attribution rows, intent blocks, intent comparison and definitions.

Alberta STANDATA variances, local copies in reference/precedents/alberta-standata/: 23-BCV-003 (issued May 2024), 23-BCV-017 (September 2025) and 23-BCV-018 (September 2025). Publication page https://open.alberta.ca/publications/standata-variance-building-national-building-code-2023-alberta-edition. Two fetch attempts on 2026-10-19 returned HTTP 520.

Archived 2019-edition variances, read for status only: reference/web/building-envelope-insulation-cladding/standata-19-bcv-017.pdf and standata-19-bcv-022.pdf, and the index records for 19-BCV-018 and 19-BCV-020.

Precedent index, research/precedents/index.json, records accessed 2026-10-18. Includes the 2023 variance records, the archived 2019 records, the Calgary SPV-003 record and ccmc-registry-summary.

Calgary SPV-003, revised 2025-02-12, index record only.

CCMC registry snapshot, reference/data/ccmc-registry.json (462 records). Entries cited by CCMC number: 08433-L, 13217-L, 12044-L, 13510-R, 13488-R, 14049-R, 14075-R, 12935-R, 14030-R, 14096-R, 14241-R, 13544-R, 13492-R, 13517-R, 13674-R, 14410-R, 13209-R, 13098-R and 12969-R. A live refresh was not reached on 2026-10-18.

BTRboard company description, reference/web/building-envelope-insulation-cladding/gohba-btrboard.html, from https://members.gohba.ca/active-member-directory/Details/btrboard-inc-4368662. The page gives a product description and no evaluation.

Web searches, 2026-10-19, standard mode: "BTRboard CCMC evaluation report insulated sheathing" and "BTRboard Inc. wall panel polyurethane foam core sheathing substrate evaluation Canada". Neither returned a BTRboard evaluation. No claim in this sheet relies on the search results.

Practitioner transcripts, explanatory only and not code, in reference/youtube/: 6XtuUn_icQU ("Outside Insulation and its Vapour Permeance", DCArchTech, uploaded 2025-12-17); LlGM_yBP9Ko ("Calculating a Temperature Gradient Through an Assembly Using THERM", 2023-04-03); t8KcQIypnYE ("The Drip Edge", 2023-11-19); 5xQeFj0bfLA ("Brick at Foundation Detail", 2021-11-16); yv3QUPZAmVw ("Brick at Floor Detail", 2021-11-21); gKhBTL0wALc ("Brick at Roof Detail", 2021-11-30). The sloped flat roof transcript (4yWcKRaxIKk) was checked and not used.