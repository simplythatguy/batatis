# Identify gold v2: high-confidence group for BAT-26

**Label: model-checked, not human-verified.** Generated 2026-10-20 (America/Edmonton, MDT UTC-6) by Data Nerd. Read-only. Codedb NBC(AE) 2023 2nd printing (sha256 `65e650407516…`). v1 (`identify-gold-proposals.*`) is kept unchanged.

**High group: n = 5** (dev-006, dev-009, dev-010, dev-011, dev-015). If Backy adopts it, the scored set grows from 11 to 16. Scoring is at Article level. `must_cite` stays empty on these ask cases (SCHEMA rule 3); the gold goes in `gold.identify_gold`.

**Guardrails.** Golds name the provision at issue; they never say the design complies or fails. Evidence = case description + known_facts + codedb + public sources; case gold/should_cite/seed fields were not used as evidence.

## Summary

| case | result | primary gold (Article) | confidence | missing fact |
|---|---|---|---|---|
| dev-006 | high (adopted in v1) | Div B 9.25.5.2.(1) (9.25.5.2., PDF p.1000) | high | — |
| dev-009 | upgraded: medium -> high (Article level) | Div B 9.27.2.2.(5) (9.27.2.2., PDF p.1014) | high (Article 9.27.2.2.); pinpoint (5) medium | — |
| dev-010 | high (adopted in v1) | Div B 9.10.15.5.(2) (9.10.15.5., PDF p.902) | high | — |
| dev-011 | high (adopted in v1) | Div B 9.23.10.1.(1) (9.23.10.1., PDF p.974) | high | — |
| dev-015 | high (adopted in v1) | Div B 9.9.9.1.(1) (9.9.9.1., PDF p.872) | high | — |
| dev-005 | not upgraded | Div B 9.10.14.5.(1) (9.10.14.5., PDF p.897) | low | building height in storeys; building area; whether any dwelling unit is above another; limiting distance / unprotected-opening % |
| dev-007 | not upgraded | Div B 9.27.3.3.(1) (9.27.3.3., PDF p.1015) | medium | product data sheet / material standard and rigidity classification of the mineral wool board |
| dev-012 | not upgraded (medium; primary flipped to 9.4.1.1. on public CCMC evidence) | Div B 9.4.1.1.(1) (9.4.1.1., PDF p.836) | medium | SIP product and any CCMC evaluation number; structural member (rib/stud/spline) spacing, to test Div B 9.23.1.1.(1)(b); whether the supplier shear values are from a CCMC evaluation or proprietary test data (racking is not in CCMC 13016-R); site address within Cochrane (Table C-2/C-3 give town values) |
| dev-020 | unchanged: no defensible gold | — | None | — |

## Upgraded: dev-009

- **Div B 9.27.2.2.(5)** (Minimum Protection from Precipitation Ingress, PDF p.1014). Role `benchmark`, tier primary, confidence **high (Article 9.27.2.2.); pinpoint (5) medium**. *model-checked, not human-verified*
  - Quote: "… second plane of protection incorporating a capillary break … b) the number of degree-days is 3400 or more, and the moisture index is greater than 1.00."
  - Reasoning: The inspectors' "gap behind the cladding" is the capillary break, and the Sentence that says when one is required is 9.27.2.2.(5). Scoring is at Article level, and every reading of the case (capillary break required or not, the (6) exceptions, what counts as a break under (1)) sits in Article 9.27.2.2., so the Article is high-confidence. Whether (5) is triggered depends on the site climate. The Table C-2 values are recorded below for the officer; the gold does not decide whether the panel complies.
- **Div B 9.27.2.2.(4)** (Minimum Protection from Precipitation Ingress, PDF p.1014). Role `scope`, tier secondary, confidence **high**. *model-checked, not human-verified*
  - Quote: "Exterior walls exposed to precipitation shall be protected against precipitation ingress by an exterior cladding assembly … where such walls enclose spaces of residential occupancy"
  - Reasoning: Houses: the two-plane requirement applies regardless of climate; same Article.
- **Div B 9.27.2.2.(1)** (Minimum Protection from Precipitation Ingress, PDF p.1013). Role `definition`, tier secondary, confidence **high**. *model-checked, not human-verified*
  - Quote: "a cladding assembly is deemed to have a capillary break … a) there is a drained and vented air space not less than 9.5 mm deep"
  - Reasoning: What counts as a capillary break; same Article.
- **Div B 9.27.2.2.(6)** (Minimum Protection from Precipitation Ingress, PDF p.1014). Role `exception`, tier secondary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "the first and second planes of protection need not incorporate a capillary break … will not adversely affect the performance of the building assemblies"
  - Reasoning: The route the manufacturer's evidence would target if (5) applies; same Article.
- Note A-9.27.2. (on PDF page 1429): "Part 5 and Part 9 of the NBC(AE) recognize that mass walls and face-sealed, concealed barrier and rainscreen assemblies have their place …"
- Climate facts: Table C-2 (PDF pages 667-670): 147 Alberta locations parsed. Lowest degree-days 4460 (so every listed location is in branch (5)(b), "3400 or more"); highest moisture index 0.6 (the (5)(b) threshold is "greater than 1.00"). These are recorded facts for the officer and are not a compliance finding. A site not listed in Table C-2 needs its own values.
- Still to confirm (does not change the Article): site location (if not in Table C-2), backing materials (for 9.27.2.2.(6)(c)).
- Evidence basis: case description + known_facts + codedb + Appendix C of the official PDF; the case gold/should_cite fields were not used as evidence.

## Not upgraded: dev-005 (low)

- **Div B 9.10.14.5.(1)** (Construction of Exposing Building Face and Walls above Exposing Building Face, PDF p.897). Role `benchmark`, tier primary, confidence **low**. *model-checked, not human-verified*
  - Quote: "each exposing building face and any exterior wall located above an exposing building face … shall be constructed in conformance with Table 9.10.14.5.-A"
  - Reasoning: Part 9 branch.
- **Div B 3.2.3.7.(1)** (Construction of Exposing Building Face, PDF p.212). Role `candidate`, tier secondary, confidence **low**. *model-checked, not human-verified*
  - Quote: "the fire-resistance rating, construction and cladding for exposing building faces … of Group A, B, C, D … shall comply with Table 3.2.3.7."
  - Reasoning: Part 3 branch.
- **Div B 9.10.15.1.(1)** (Application, PDF p.900). Role `scope`, tier secondary, confidence **low**. *model-checked, not human-verified*
  - Quote: "buildings that contain only dwelling units and have no dwelling unit above another dwelling unit"
  - Reasoning: If no dwelling unit is above another, 9.10.15. (not 9.10.14.) governs.
- **Div A 1.3.3.3.(1)** (Application of Parts 9, 10 and 11, PDF p.40). Role `scope`, tier scope, confidence **n/a**. *model-checked, not human-verified*
  - Quote: "of 3 storeys or less in building height, having a building area not exceeding 600 m²"
  - Reasoning: Part 9 limits
- Settling fact: **building height in storeys and building area**, which settles Part 9 vs Part 3: Div A 1.3.3.3.(1) (3 storeys or less, 600 m² or less); above either limit, Div B 3.2.3.7..
- Settling fact: **whether any dwelling unit is above another dwelling unit**, which settles Div B 9.10.15. (no unit above another, Div B 9.10.15.1.(1)) vs Div B 9.10.14..
- Settling fact: **limiting distance and the permitted unprotected-opening %**, which settles which row of Table 9.10.14.5.-A (or Div B 9.10.15.5.(2)/(3)) applies, and whether a waiver Sentence such as Div B 9.10.14.5.(3) is in play.
- Settling fact: **complete wall assembly and any CAN/ULC-S134 test of it**, which settles whether the tested-assembly routes (Clause 3.1.5.5.(1)(b) via Div B 9.10.14.5.(2) or Div B 9.10.15.5.(2)(c)/(3)(d)) are available; the stated flame-spread rating of 75 is a fact to compare with the 25 limits in those Sentences, not a finding.
- Public-source check: None settles it. The four facts are project facts and the request is product-wide, so no public source can supply them. NRC CCMC Registry search (2026-10-20) found wood-plastic composite evaluations for decking only (for example CCMC 14114-R, 14154-R, 14342-R), none for siding and none with a CAN/ULC-S134 result. Stays low.
- **Why not high:** Three different Articles are possible, depending on facts the description does not give: Part 3 Div B 3.2.3.7. if the building is over 3 storeys or over 600 m² (Div A 1.3.3.3.(1)); Div B 9.10.15.5. if no dwelling unit is above another (Div B 9.10.15.1.(1)); otherwise Div B 9.10.14.5. "Small apartment buildings" fixes none of these.
- **Missing fact(s):** building height in storeys; building area; whether any dwelling unit is above another; limiting distance / unprotected-opening %.

## Not upgraded: dev-007 (medium)

- **Div B 9.27.3.3.(1)** (Required Sheathing Membrane and Installation, PDF p.1015). Role `benchmark`, tier primary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "Except as provided in Articles 9.27.3.4. to 9.27.3.6., at least one layer of sheathing membrane shall be applied beneath cladding."
  - Reasoning: Omitting the housewrap departs from this Sentence unless an exception Article applies.
- **Div B 9.27.3.4.(1)** (Insulating Sheathing in lieu of Sheathing Membrane, PDF p.1015). Role `candidate`, tier secondary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "Where non-wood-based rigid exterior insulating sheathing, or exterior insulating sheathing with an integral sheathing membrane is installed, a separate sheathing membrane is not required."
  - Reasoning: If the board qualifies, no membrane is required and the departure moves to the joints in 9.27.3.4.(2) (butted, unsealed).
- **Div B 9.27.3.4.(2)** (Insulating Sheathing in lieu of Sheathing Membrane, PDF p.1015). Role `candidate`, tier secondary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "the joints of sheathing panels not subject to moisture deterioration shall be i) sealed at all joints, or ii) lapped or tongue and groove …"
  - Reasoning: Joint rule if 9.27.3.4.(1) applies.
- Note A-9.27.3.4.(2) (PDF p.1432): "Butt joints can drain to either side and so should not be used unless they are sealed."
- **Why not high:** The scored Article flips between 9.27.3.3. and 9.27.3.4. depending on whether the specified board is "non-wood-based rigid exterior insulating sheathing" (9.27.3.4.(1)). The applicant calls it "semi-rigid". The code does not define "rigid", and codedb has no Note on 9.27.3.4.(1) (only A-9.27.3.4.(2) on joints). No public Alberta guidance was found in this pass that classifies semi-rigid mineral wool board.
- **Missing fact(s):** product data sheet / material standard and rigidity classification of the mineral wool board.

## Not upgraded: dev-012 (medium)

- **Div B 9.4.1.1.(1)** (General, PDF p.836). Role `benchmark`, tier primary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "structural members and their connections shall a) conform to requirements provided elsewhere in this Part, b) be designed according to good engineering practice"
  - Reasoning: Route Article for structural members outside the Section 9.23. prescriptive scope. CCMC 13016-R (below) frames SIP framing as an alternative solution to 9.4.1.1.(1)(c) and Section 9.23.
- **Div B 9.23.13.1.(2)** (Requirements for Low to Moderate Wind and Seismic Forces, PDF p.978). Role `candidate`, tier secondary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "Bracing to resist lateral loads shall be designed and constructed as follows"
  - Reasoning: Applies only if the SIP system is inside Section 9.23. (members at 600 mm o.c. or less); its Clause (b) also allows Part 4 or good engineering practice.
- **Div B 9.23.13.1.(1)** (Requirements for Low to Moderate Wind and Seismic Forces, PDF p.978). Role `scope`, tier secondary, confidence **high (for the climate branch)**. *model-checked, not human-verified*
  - Quote: "This Article applies in locations where … Sa(0.2), is not more than 0.70 and the 1-in-50 hourly wind pressure is less than 0.80 kPa."
  - Reasoning: Cochrane values below.
- **Div B 9.23.1.1.(1)** (Limitations, PDF p.962). Role `scope`, tier secondary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "the small repetitive structural members are spaced not more than 600 mm o.c."
  - Reasoning: The scope test that decides between the two Articles. The one public CCMC SIP evaluation read has ribs at 1.2 m o.c.
- Note A-9.23.1.1. (PDF p.1405): "The prescriptive requirements in Section 9.23. apply only to standard light wood-frame construction."
- Resolved: Cochrane: Table C-3 Sa(0.2) = 0.236 (PDF page 672); Table C-2 1-in-50 hourly wind pressure = 0.48 kPa (PDF page 667). Both are within the 9.23.13.1.(1) limits, so the high-force branch 9.23.13.2. is not the scoped Article for this town.
- Public source: NRC CCMC Registry, CCMC 13016-R, Insulspan Structural Insulated Panel (SIP) System (Plasti-Fab Ltd.), status Active, modified 2025-10-21; compliance NBC 2010 and NBC 2015 (historical context: not the NBC(AE) 2023, and not shown to be the case product). <https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=13016-R&type=cert>. Verification: quotes checked against the WebFetch rendering of the public page on 2026-10-20; a direct curl from the box failed (HTTP 000). *model-checked, not human-verified*
  - "an alternative solution to Clause 9.4.1.1.(1)(c), General (Structural Design Requirements and Application Limitations), and Section 9.23., Wood-Frame Construction"
  - "Note that only the Insulspan System with a structural stud or joist at 1.2 m (4 ft.) o.c. is CCMC-evaluated"
  - "Any other panel installations, in particular loadbearing applications without structural members, are not CCMC-evaluated"
  - "pre-engineered wall and roof Insulspan panel resistance values for LSD design, for the specified gravity loads"
  - "With no hold-downs, the Insulspan SIP System is limited for use in geographical locations where the q1/50 wind load is less than 0.6 kPa"
  - Reading: The evaluation covers gravity loads only; racking resistance is not in its compliance table, so it does not evaluate "panels resist wind racking with supplier shear values". Its compliance edition is NBC 2015 (historical context).
- Public source: Alberta STANDATA 19-BCV-020 Structural Insulated Panels, May 2021, issued under the NBC(AE) 2019 (historical context: Open Alberta states STANDATA are obsolete for new construction once a new Code comes into effect). <https://open.alberta.ca/dataset/5a1e414d-6639-467d-b5a4-6d68454f1340/resource/4e9bae1e-bb8a-460e-9ae0-e105e7f8255b/download/ma-standata-building-code-variance-19-bcv-020.pdf>. Verification: quotes checked against pdftotext of the public PDF fetched 2026-10-20 (local copy kept in /tmp only, not committed). *model-checked, not human-verified*
  - "Currently SIPs are not a referenced product or system in the NBC(AE)"
  - "CCMC evaluations that state materials, products and systems for SIPs are in compliance with the NBC are recognized in Alberta"
  - Reading: Shows how Alberta handled SIPs under the previous edition (CCMC evaluation, or an alternative solution by a registered professional). Not current; the routing decision stays with the SCO.
- **Why not high:** The public evidence now favours 9.4.1.1. as the Article at issue for SIPs generally: codedb Note A-9.23.1.1. limits Section 9.23. to standard light wood-frame construction; 9.23.1.1.(1)(b) requires members at 600 mm o.c. or less; and the one public CCMC SIP evaluation found (13016-R) has ribs at 1.2 m o.c. and treats SIP framing as an alternative to 9.4.1.1.(1)(c) and Section 9.23. It is still not high because the case names no product, so neither its member spacing nor any CCMC evaluation can be checked. A SIP with studs at 600 mm o.c. or less would put the case back inside Section 9.23. (9.23.13.1.(2)). CCMC 13016-R covers gravity loads, not racking, and its compliance edition is NBC 2015 (historical context, previous national edition).
- **Missing fact(s):** SIP product and any CCMC evaluation number; structural member (rib/stud/spline) spacing, to test Div B 9.23.1.1.(1)(b); whether the supplier shear values are from a CCMC evaluation or proprietary test data (racking is not in CCMC 13016-R); site address within Cochrane (Table C-2/C-3 give town values).

## Kept from v1 (high)

- dev-006: **Div B 9.25.5.2.(1)** (Position of Low Permeance Materials, PDF p.1000). Role `benchmark`, tier primary, confidence **high**. *model-checked, not human-verified*
  - Quote: "… the ratio between the total thermal resistance of all materials outboard … inboard of that surface is not less than that required by Table 9.25.5.2."
  - Reasoning: 'Outboard insulation is too thin for that wall' is exactly the outboard-to-inboard thermal-resistance ratio in Clause (1)(b); the foil-faced (essentially impermeable) board is a low-permeance sheet material. Whether the design actually fails the ratio is an intake question, but the provision at issue is this one.
- dev-010: **Div B 9.10.15.5.(2)** (Construction of Exposing Building Face of Houses, PDF p.902). Role `benchmark`, tier primary, confidence **high**. *model-checked, not human-verified*
  - Quote: "where the limiting distance is less than 0.6 m, the exposing building face … shall have a fire-resistance rating of not less than 45 min"
  - Reasoning: A house (9.10.15. applies per 9.10.15.1.(1)) with the east wall 0.5 m from the property line: limiting distance < 0.6 m. The city's 'metal or noncombustible siding' matches Clause (2)(a). Clause (2)(b) is a conditional vinyl route (9.27.12., gypsum backing, FSR ≤ 25, ≤ 2 mm), so whether a variance is needed is an intake question, but the provision is this one.
- dev-011: **Div B 9.23.10.1.(1)** (Stud Size and Spacing, PDF p.974). Role `benchmark`, tier primary, confidence **high**. *model-checked, not human-verified*
  - Quote: "The size and spacing of studs shall conform to Table 9.23.10.1."
  - Reasoning: Table 9.23.10.1. (PDF p.975, checked visually): exterior walls carrying 'roof with or without attic storage plus one floor' allow 38 × 89 at max 400 mm (or 38 × 140 at 600 mm). 2x4 at 600 mm supporting the second floor and roof departs from the table.
- dev-015: **Div B 9.9.9.1.(1)** (Travel Limit to Exits or Egress Doors, PDF p.872). Role `benchmark`, tier primary, confidence **high**. *model-checked, not human-verified*
  - Quote: "… dwelling unit containing more than 1 storey shall have exits or egress doors … not be necessary to travel up or down more than 1 storey"
  - Reasoning: Attic bedroom in a two-storey house: from the attic the occupant travels down two storeys to the front door. The window exception (2) needs a ≥1 m × 0.55 m opening with a sill ≤1 m above the floor; 'small skylights' is not a measurement, so the case stays 'ask', but this is the provision.

## Climate data used

NBC(AE) 2023 2nd printing, Division B Appendix C, Table C-2 "Climatic Design Data for Selected Locations in Alberta" and Table C-3 "Seismic Design Data for Selected Locations in Alberta for Part 9 Design". Table C-2 on PDF pages 667–670; Table C-3 on PDF pages 671–674. Method: pdftotext -layout row parse (16 numeric columns; HDD = col 6, moisture index = col 10, 1/50 hourly wind pressure = last); model-checked, not human-verified.

## Patches

See `patches` in the json: `identify_gold` for the 5 high cases and `identify_gold_candidates` for 005/007/012.
