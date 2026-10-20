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
| dev-012 | not upgraded (raised low -> medium) | Div B 9.23.13.1.(2) (9.23.13.1., PDF p.978) | medium | SIP product and any CCMC evaluation number; whether the panel system is framed (studs/splines) or stressed-skin only; site address within Cochrane (Table C-2/C-3 give town values) |
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

- **Div B 9.23.13.1.(2)** (Requirements for Low to Moderate Wind and Seismic Forces, PDF p.978). Role `benchmark`, tier primary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "Bracing to resist lateral loads shall be designed and constructed as follows"
  - Reasoning: Low-to-moderate-force bracing rule; the site values now fall in this Article's scope.
- **Div B 9.23.13.1.(1)** (Requirements for Low to Moderate Wind and Seismic Forces, PDF p.978). Role `scope`, tier primary, confidence **high (for the climate branch)**. *model-checked, not human-verified*
  - Quote: "This Article applies in locations where … Sa(0.2), is not more than 0.70 and the 1-in-50 hourly wind pressure is less than 0.80 kPa."
  - Reasoning: Cochrane values below.
- **Div B 9.23.1.1.(1)** (Limitations, PDF p.962). Role `scope`, tier secondary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "This Section applies to constructions where wall, floor and roof planes are generally comprised of lumber frames of small repetitive structural members, or engineered components"
  - Reasoning: Whether a SIP house is inside Section 9.23. at all.
- **Div B 9.4.1.1.(1)** (General, PDF p.836). Role `candidate`, tier secondary, confidence **medium**. *model-checked, not human-verified*
  - Quote: "be designed according to Part 4 using the loads and deflection and vibration limits specified in i) Part 9, or ii) Part 4."
  - Reasoning: Engineering-design route if Section 9.23. does not apply to the SIP system.
- Note A-9.23.1.1. (PDF p.1405): "The prescriptive requirements in Section 9.23. apply only to standard light wood-frame construction."
- Resolved: Cochrane: Table C-3 Sa(0.2) = 0.236 (PDF page 672); Table C-2 1-in-50 hourly wind pressure = 0.48 kPa (PDF page 667). Both are within the 9.23.13.1.(1) limits, so the high-force branch 9.23.13.2. is not the scoped Article for this town.
- **Why not high:** The climate fact is resolved, but the scope fact is not. If the SIP system counts as standard light wood-frame construction, 9.23.13.1. is the benchmark; if not, Note A-9.23.1.1. sends design to Part 4 (9.4.1.1.(1)(c)). The description gives no product evaluation. Public SIP documents found (an Ontario Minister's ruling cited by a manufacturer; CCMC listings) are not Alberta and not for this product, so they were not used.
- **Missing fact(s):** SIP product and any CCMC evaluation number; whether the panel system is framed (studs/splines) or stressed-skin only; site address within Cochrane (Table C-2/C-3 give town values).

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
