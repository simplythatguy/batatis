# Mandatory human-review triggers: sourcing and drop-in tests

Label: **model-checked, not human-verified**. Built 2026-10-20 (America/Edmonton) by `research/src/mtt_build.py`. Machine-readable: `mandatory-triggers-tests.json`.

Purpose: Karen's rubric gap #5 (Recommendations). For triggers HR-02, HR-05, HR-06, HR-07, HR-30 and HR-32 of `human-review-triggers.json`: the exact basis, whether the text makes it mandatory, the facts that fire it and the near-misses that don't, and drop-in tests for Backy's #26/#30.

**Checks:** every code quote is an exact substring of codedb text (NBC(AE) 2023 2nd printing) with its PDF page. Safety Codes Act quotes are checked against page 31 of the Act PDF. Every quote is 25 words or fewer.

**Guardrails in every test:** the expected route is human review by the named professional or officer. No test expects a compliance verdict. No README, expected/ or keys/ content was used.

| Trigger | Call | Test ids |
|---|---|---|
| HR-02 | mandatory (once the project is outside every Div C 2.4.1.1.(1) exception); plus a separate discretionary AHJ power in Div C 2.4.1.1.(4) | mtt-02a, mtt-02b |
| HR-05 | mandatory (when a threshold is met) | mtt-05a, mtt-05b |
| HR-06 | mandatory (when a condition is met) | mtt-06a, mtt-06b |
| HR-07 | mandatory (when the element is present); bowstring/arch trusses medium confidence | mtt-07a, mtt-07b |
| HR-30 | discretionary decision; routing is required (only an Administrator or safety codes officer holds the power) | mtt-30a, mtt-30b |
| HR-32 | discretionary (the Administrator "may grant"); routing to the Provincial Barrier-Free Administrator or Provincial Building Administrator | mtt-32a, mtt-32b |

## HR-02: Coordinating registered professional, registered professionals of record, Schedules A and B

**Call:** mandatory (once the project is outside every Div C 2.4.1.1.(1) exception); plus a separate discretionary AHJ power in Div C 2.4.1.1.(4).

**Why:** Div C 2.4.1.1.(3) and 2.4.2.2.(1) use "shall"; Subsection 2.4.2. applies to every 2.4.1.1.(3) project (Div C 2.4.2.1.(1)). Div C 2.4.1.1.(4) is "may require" (discretionary).

**Basis:**

- Div C 2.4.1.1.(3), PDF p.740: "For buildings other than those described in Sentence (1), the drawings and specifications shall be authenticated by one or more registered professionals"
- Div C 2.4.2.1.(1), PDF p.741: "This Subsection applies to a project that falls within the scope of Sentence 2.4.1.1.(3)."
- Div C 2.4.2.2.(1), PDF p.741: "Before applying for a permit, the owner shall a) retain a coordinating registered professional"
- Div C 2.4.2.2.(1), PDF p.741: "c) provide the authority having jurisdiction with Schedules A and B"
- Div C 2.4.1.1.(1), PDF p.739: "b) classified as a residential occupancy that is i) a single-family dwelling, or ii) a multiple-family dwelling that contains 4 dwelling units or less"
- Div C 2.4.1.1.(4), PDF p.740: "the authority having jurisdiction may require the involvement of one or more registered professionals"

**Fires when:**

- building outside every exception in Div C 2.4.1.1.(1), e.g. residential multiple-family dwelling with more than 4 dwelling units (secondary suites not counted, Div C 2.4.1.1.(2))

**Near-misses (does not fire):**

- single-family dwelling, or multiple-family dwelling with 4 dwelling units or less (exception (1)(b))
- a house with a secondary suite: the suite is not counted as a dwelling unit (Div C 2.4.1.1.(2))
- inside an exception but the AHJ invokes Div C 2.4.1.1.(4): discretionary, the officer decides

**Tests:**

- `mtt-02a` (fires). Input: `{"occupancy": "residential, multiple-family dwelling", "dwelling_units": 64, "storeys": 5, "uses": "retail at grade", "crp_name": null, "schedule_a_provided": false, "schedule_b_provided": false}`. Expected: `{"route": "human_review", "human": "coordinating registered professional and registered professionals of record (owner retains them)", "gap": {"type": "needs_professional", "status": "open"}, "cite": ["Div C 2.4.1.1.(3)", "Div C 2.4.2.2.(1)"], "ask": "Who is the coordinating registered professional, and have Schedules A and B been provided to the authority having jurisdiction?"}`.
- `mtt-02b` (near_miss). Input: `{"occupancy": "residential, single-family dwelling", "dwelling_units": 1, "secondary_suites_count": 1, "storeys": 2}`. Expected: `{"trigger_fires": false, "route": "none from HR-02; other triggers (HR-03 to HR-07) are still checked", "note": "Div C 2.4.1.1.(4): the officer may still require a professional; show this as possible, not as a ruling."}`.

## HR-05: Part 9 sends sheathing fastening, anchorage or lumber roof sheathing to Part 4 because of wind or seismic hazard

**Call:** mandatory (when a threshold is met).

**Why:** The Part 9 Sentences say "shall conform to Part 4" / "shall be designed according to Part 4"; Div C 2.4.1.2.(1) then says the Part 4 designer "shall be a registered professional".

**Basis:**

- Div B 9.23.3.5.(4), PDF p.967: "Fastening of sheathing shall conform to Part 4, a) where the 1-in-50 hourly wind pressure is equal to or greater than 1.2 kPa"
- Div B 9.23.6.1.(6), PDF p.970: "Where … Sa(0.2), is greater than 1.8 or … wind pressure is equal to or greater than 1.2 kPa, anchorage shall be designed according to Part 4."
- Div B 9.23.16.5.(3), PDF p.988: "Lumber roof sheathing shall be designed according to Part 4, where a) the seismic spectral acceleration, Sa(0.2), is greater than 1.2"
- Div C 2.4.1.2.(1), PDF p.740: "For design carried out in accordance with Part 4 … the designer shall be a registered professional skilled in the work concerned."

**Fires when:**

- 1-in-50 hourly wind pressure >= 1.2 kPa (sheathing fastening, anchorage; lumber roof sheathing at >= 1.20 kPa)
- Sa(0.2) > 1.8 (anchorage; fastening of required braced wall panels)
- Sa(0.2) > 1.2 (lumber roof sheathing)

**Near-misses (does not fire):**

- wind exactly below 1.2 kPa, e.g. 1.01 kPa (highest 1-in-50 value among the 147 Alberta rows of Div B Appendix C Table C-2, Cowley, page 667 of the PDF)
- Sa(0.2) exactly 1.8 (the test is "greater than")
- Edmonton: 1-in-50 0.45 kPa (Table C-2, page 667 of the PDF), Sa(0.2) 0.103 (Table C-3, page 672 of the PDF)

**Note:** Finding: across the 147 Alberta locations in Table C-2/C-3, the highest 1-in-50 hourly wind pressure is 1.01 kPa (Cowley) and the highest Sa(0.2) is 0.287 (Jasper, page 673 of the PDF). So no listed Alberta location meets an HR-05 threshold; the firing test is a synthetic boundary case. Parsed from the official PDF text by script; model-checked, not human-verified.

**Tests:**

- `mtt-05a` (fires). Input: `{"element": "sheathing fastening", "hourly_wind_pressure_1in50_kPa": 1.2, "Sa_0_2": 0.1, "climate_source": "synthetic boundary value (no Table C-2 Alberta row reaches it)"}`. Expected: `{"route": "human_review", "human": "registered professional (structural) for the Part 4 design", "gap": {"type": "needs_professional", "status": "open"}, "cite": ["Div B 9.23.3.5.(4)", "Div C 2.4.1.2.(1)"]}`.
- `mtt-05b` (near_miss). Input: `{"element": "sheathing fastening and anchorage", "location": "Edmonton", "hourly_wind_pressure_1in50_kPa": 0.45, "Sa_0_2": 0.103}`. Expected: `{"trigger_fires": false, "route": "none from HR-05; show the threshold and the table value as facts", "cite": ["Div B 9.23.3.5.(4)"]}`.

## HR-06: Part 9 sends footings, floor spans, floors-on-ground or permafrost foundations to Part 4

**Call:** mandatory (when a condition is met).

**Why:** "shall be designed in accordance with Section 4.2." / "Subsection 4.1.3." / "Part 4"; Div C 2.4.1.2.(1) then requires a registered professional for design under Part 4 (model-derived chain: Div B Section 4.2. and Div B Subsection 4.1.3. are in Part 4).

**Basis:**

- Div B 9.15.3.3.(2), PDF p.925: "where the span of the supported joists exceeds 4.9 m, footings shall be designed in accordance with Section 4.2."
- Div B 9.15.3.3.(3), PDF p.925: "Where the specified live load exceeds 2.4 kPa, footings shall be designed in accordance with Section 4.2."
- Div B 9.16.1.2.(1), PDF p.933: "Floors-on-ground that support loads from the superstructure shall be designed in conformance with Part 4."
- Div B 9.23.4.1.(2), PDF p.967: "Spans for joists, beams and lintels supporting floors shall be determined according to Subsection 4.1.3. where the supported floors a) serve other than residential areas"
- Div B 9.15.1.2.(1), PDF p.924: "Buildings erected on permafrost shall have foundations designed by a designer competent in this field in accordance with the appropriate requirements of Part 4."
- Div C 2.4.1.2.(1), PDF p.740: "For design carried out in accordance with Part 4 … the designer shall be a registered professional skilled in the work concerned."

**Fires when:**

- supported joist span > 4.9 m (footings)
- specified live load > 2.4 kPa (footings)
- floor-on-ground carries superstructure loads
- floors serving other than residential areas (spans)
- permafrost

**Near-misses (does not fire):**

- joist span exactly 4.9 m ("exceeds")
- live load exactly 2.4 kPa ("exceeds")
- the exception in Div B 9.15.3.4.(2) referred to by 9.15.3.3.(2) (not assessed here)
- slab-on-ground that carries no superstructure load

**Tests:**

- `mtt-06a` (fires). Input: `{"supported_joist_span_m": 5.2, "specified_live_load_kPa": 1.9, "occupancy": "residential, single-family dwelling"}`. Expected: `{"route": "human_review", "human": "registered professional (structural/geotechnical) for the Section 4.2 footing design", "gap": {"type": "needs_professional", "status": "open"}, "cite": ["Div B 9.15.3.3.(2)", "Div C 2.4.1.2.(1)"]}`.
- `mtt-06b` (near_miss). Input: `{"supported_joist_span_m": 4.9, "specified_live_load_kPa": 2.4, "occupancy": "residential, single-family dwelling"}`. Expected: `{"trigger_fires": false, "route": "none from HR-06 on these facts"}`.

## HR-07: Part 9 sends a material or element to Part 4

**Call:** mandatory (when the element is present); bowstring/arch trusses medium confidence.

**Why:** "shall be designed to conform to the requirements of Part 4" / "in conformance with Part 4" / "Subsection 4.3.1."; Div C 2.4.1.2.(1). For Div B 9.4.2.2.(3) the text sends only the snow-load requirements of Subsection 4.1.6.; whether that is "design carried out in accordance with Part 4" is a model judgement.

**Basis:**

- Div B 9.3.1.1.(3), PDF p.831: "Except as provided in Sentence (4), reinforced concrete shall be designed to conform to the requirements of Part 4."
- Div B 9.3.1.1.(4), PDF p.831: "For flat insulating concrete form walls not exceeding 2 storeys in building height and having a maximum floor to floor height of 3 m"
- Div B 9.24.1.1.(2), PDF p.991: "Where loadbearing steel studs are used, they shall be designed in conformance with Part 4."
- Div B 9.17.1.1.(2), PDF p.935: "Columns for applications other than as described in Sentence (1) shall be designed in accordance with Part 4."
- Div B 9.23.1.1.(2), PDF p.962: "Where the conditions in Sentence (1) are exceeded for wood constructions, the design of the framing and fastening shall conform to Subsection 4.3.1."
- Div B 9.4.2.2.(3), PDF p.838: "Bow string, arch or semi-circular roof trusses having an unsupported span greater than 6 m shall be designed in conformance with the snow load requirements"
- Div C 2.4.1.2.(1), PDF p.740: "For design carried out in accordance with Part 4 … the designer shall be a registered professional skilled in the work concerned."

**Fires when:**

- reinforced concrete outside the flat-ICF permission
- loadbearing steel studs
- columns outside Div B 9.17.1.1.(1)
- wood framing beyond Div B 9.23.1.1.(1) (e.g. a member span over 12.20 m)
- bowstring/arch/semi-circular truss with unsupported span > 6 m

**Near-misses (does not fire):**

- flat ICF walls of 2 storeys or less with floor-to-floor 3 m or less (Div B 9.3.1.1.(4) gives a prescriptive route)
- truss unsupported span exactly 6 m ("greater than")
- non-loadbearing steel studs

**Tests:**

- `mtt-07a` (fires). Input: `{"structural_elements": ["loadbearing steel studs"], "occupancy": "residential, single-family dwelling", "storeys": 2}`. Expected: `{"route": "human_review", "human": "registered professional (structural) for the Part 4 design", "gap": {"type": "needs_professional", "status": "open"}, "cite": ["Div B 9.24.1.1.(2)", "Div C 2.4.1.2.(1)"]}`.
- `mtt-07b` (near_miss). Input: `{"structural_elements": ["flat ICF foundation walls"], "storeys": 2, "floor_to_floor_m": 3.0, "truss_type": "bowstring", "truss_unsupported_span_m": 6.0}`. Expected: `{"trigger_fires": false, "route": "none from HR-07 on these facts; the Div B 9.3.1.1.(4) prescriptive route is shown with its conditions"}`.

## HR-30: Any variance (alternative solution) request goes to a safety codes officer or Administrator

**Call:** discretionary decision; routing is required (only an Administrator or safety codes officer holds the power).

**Why:** SCA s.38(1) "may issue" and "is of the opinion": the grant is discretionary. The power is given only to "An Administrator or a safety codes officer", so the app can only route. s.38(3) "shall notify" binds the officer after issuing, not the applicant. This is officer routing, not professional design.

**Basis:**

- Safety Codes Act s.38(1), page 31 of the Act PDF: "An Administrator or a safety codes officer may issue a written variance"
- Safety Codes Act s.38(1), page 31 of the Act PDF: "if the Administrator or officer is of the opinion that the variance provides approximately equivalent or greater safety performance"
- Safety Codes Act s.38(3), page 31 of the Act PDF: "A safety codes officer on issuing a variance shall notify an Administrator."
- Div A 1.2.1.1.(1), PDF p.38: "b) using alternative solutions that will achieve at least the minimum level of performance required by Division B"
- Div C 2.2.1.2.(1), PDF p.729: "A written request for a variance may be submitted to the Provincial Building Administrator."

**Fires when:**

- the applicant asks to depart from an acceptable solution (alternative solution / variance request), site-specific

**Near-misses (does not fire):**

- the design follows the acceptable solution as written (no variance requested)
- a province-wide request: written request to the Provincial Building Administrator (Div C 2.2.1.2.(1)), a different route
- a Div B Section 3.8. barrier-free relaxation: HR-32 route

**Note:** The HRT json had mandatory=null for HR-30 (not codedb-only). This file classifies it as discretionary (decision) with required routing.

**Tests:**

- `mtt-30a` (fires). Input: `{"intake_action": "variance_request", "variance_requested": true, "scope": "one site", "jurisdiction": "Calgary (confirmed)"}`. Expected: `{"route": "human_review", "human": "safety codes officer of the reviewing authority (or an Administrator)", "gap": {"type": "officer_decision", "status": "open"}, "cite": ["Safety Codes Act s.38(1)"], "say": "The officer decides; Batatis prepares the request and cannot say it will be accepted."}`.
- `mtt-30b` (near_miss). Input: `{"intake_action": "variance_request", "variance_requested": true, "scope": "province-wide"}`. Expected: `{"trigger_fires": "different route", "route": "human_review", "human": "Provincial Building Administrator (written request)", "cite": ["Div C 2.2.1.2.(1)"]}`.

## HR-32: Barrier-free (Div B Section 3.8.) relaxation

**Call:** discretionary (the Administrator "may grant"); routing to the Provincial Barrier-Free Administrator or Provincial Building Administrator.

**Why:** Div C 2.2.1.4.(1) "may grant relaxation" and only "if an owner can demonstrate" one of two grounds. Whether a local safety codes officer may also vary Div B Section 3.8. under SCA s.38 is not settled by this text (UNSOURCED).

**Basis:**

- Div C 2.2.1.4.(1), PDF p.730: "The Provincial Barrier-Free Administrator or Provincial Building Administrator may grant relaxation of one or more of the requirements of Section 3.8. of Division B"
- Div C 2.2.1.4.(1), PDF p.730: "a) the specific requirements are unnecessary, or b) extraordinary circumstances prevent conformance."
- Div B 3.8.1.1.(1), PDF p.301: "This Section is concerned with the barrier-free design of buildings."

**Fires when:**

- the applicant asks to relax a requirement in Div B Section 3.8. (barrier-free design)

**Near-misses (does not fire):**

- the departure is from a requirement outside Section 3.8.: HR-30 route (safety codes officer)
- barrier-free requirement met as written: no relaxation requested

**Note:** The HRT json typed HR-32 as "mandatory" (routing rule) with mandatory=false; the text supports discretionary.

**Tests:**

- `mtt-32a` (fires). Input: `{"provisions_varied": ["Div B Section 3.8. requirement (barrier-free path of travel)"], "request": "relaxation", "owner_grounds": "extraordinary circumstances (applicant-stated)"}`. Expected: `{"route": "human_review", "human": "Provincial Barrier-Free Administrator or Provincial Building Administrator", "gap": {"type": "administrator_decision", "status": "open"}, "cite": ["Div C 2.2.1.4.(1)"], "ask": "Which ground does the owner rely on (unnecessary, or extraordinary circumstances), and what shows it?"}`.
- `mtt-32b` (near_miss). Input: `{"provisions_varied": ["Div B 3.1.9.1.(1)"], "request": "variance"}`. Expected: `{"trigger_fires": false, "route": "HR-30 (safety codes officer)", "cite": ["Safety Codes Act s.38(1)"]}`.

## must_not (every test)

- state that the design complies, is compliant, or is approved
- state as a final ruling that a professional is or is not required (route instead)
- close needs_professional without the applicant confirming an engineer/architect role plus a seal or registration number (#26)
- close the gap because a document names a person or a seal (#26)
- state that a variance or relaxation is granted, will be granted, or is not needed
- answer yes or no on the officer's behalf

Near-miss tests also add: never say "no professional/engineer needed" as a ruling.
