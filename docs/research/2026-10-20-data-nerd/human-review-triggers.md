# Human-review trigger table (Batatis)

Label: **model-checked, not human-verified**. Built 2026-10-20 (MDT). Machine-readable twin: `human-review-triggers.json`.

Code text: National Building Code – 2023 Alberta Edition (NBC(AE) 2023), 2nd printing, © National Research Council of Canada. Excerpts quoted with attribution for research. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499

Every quote below was string-checked. Code quotes were matched against codedb (NBC(AE) 2023, 2nd printing; snapshot sha256 `65e650407516…`). Every other quote was matched against `pdftotext` of the local copy of the cited PDF, with the page found automatically. Page numbers are PDF page numbers. Internal-only appeal decisions are not included in this public variant.

**Type:** `mandatory` means a source sentence requires the human or professional once the condition is met. `strongly-indicated` means the requirement follows from a chain of sources or from an interpretation applied by analogy. `discretionary` means an officer or Administrator may require or decide it, so the app must surface it and must not decide it.

**Detect fields:** these reuse `engine/professional.py` `ProfessionalFacts` names where one exists. `(NEW)` marks a field the engine does not have yet.

## Summary

| ID | Trigger (plain words) | Type | Human | Engine facts | Conf. | Key cite | Verification class | Mandatory (codedb-only) | Verification |
|---|---|---|---|---|---|---|---|---|---|
| HR-01 | Building is outside every general exception in Div C 2.4.1.1.(1), so registered professionals must authenticate the drawings and specifications. | mandatory | Registered architectural and/or engineering professional(s) for the applicable disciplines | `occupancy`, `storeys`, `building_area_m2`, `principal_dwelling_units`, `secondary_suites_count (NEW)`, `farm_public_use`, `relocatable_industrial_camp (NEW; engine uses occupancy value)` | high | Div C Sentence 2.4.1.1.(3) | `codedb-only` | **yes** (P2) | Div C Sentence 2.4.1.1.(3): codedb-checked, 2nd printing, PDF p.740<br>Div C Sentence 2.4.1.1.(1): codedb-checked, 2nd printing, PDF p.739<br>Div C Sentence 2.4.1.1.(2): codedb-checked, 2nd printing, PDF p.740<br>Div C Sentence 2.4.1.1.(5): codedb-checked, 2nd printing, PDF p.740 |
| HR-02 | A 2.4.1.1.(3) project needs a coordinating registered professional (CRP), registered professionals of record (RPRs) and Schedules A and B before the permit application; Schedule C-1 before occupancy; work stops if the CRP or an RPR leaves. | mandatory | Coordinating registered professional + registered professionals of record (architectural, structural, mechanical, electrical, geotechnical as applicable) | `general_required == yes (from HR-01)`, `schedule_a_provided (NEW)`, `schedule_b_provided (NEW)`, `crp_name (NEW)`, `rpr_disciplines (NEW)` | high | Div C Sentence 2.4.2.1.(1) | `mixed` | — | Div C Sentence 2.4.2.1.(1): codedb-checked, 2nd printing, PDF p.741<br>Div C Sentence 2.4.2.2.(1): codedb-checked, 2nd printing, PDF p.741<br>Div C Sentence 2.4.2.2.(1): codedb-checked, 2nd printing, PDF p.741<br>Div C Sentence 2.4.2.4.(1): codedb-checked, 2nd printing, PDF p.742<br>Div C Sentence 2.4.2.5.(1): codedb-checked, 2nd printing, PDF p.742 |
| HR-03 | Any structural design carried out under Part 4 of Div B (including a single engineered beam, connection or foundation in a Part 9 house). | mandatory | Registered professional skilled in the work concerned (structural engineer in practice) | `part4_design`, `part4_elements (NEW: list)` | high | Div C Sentence 2.4.1.2.(1) | `codedb-only` | **yes** (P1) | Div C Sentence 2.4.1.2.(1): codedb-checked, 2nd printing, PDF p.740<br>Div C Sentence 2.2.4.2.(1): codedb-checked, 2nd printing, PDF p.732<br>Div C Sentence 2.2.4.4.(1): codedb-checked, 2nd printing, PDF p.732 |
| HR-04 | Building is not within Part 9 scope (Div A 1.3.3.2.), so Part 4 structural design applies to it → Div C 2.4.1.2.(1) professional, even if the building fits a Div C 2.4.1.1.(1) size exception. | strongly-indicated | Registered professional (structural) for the Part 4 design | `occupancy (incl. Group A, B1-B3, F1, post_disaster NEW)`, `storeys`, `building_area_m2` | medium | Div A Sentence 1.3.3.2.(1) | `codedb-only` | **yes** (P6) | Div A Sentence 1.3.3.2.(1): codedb-checked, 2nd printing, PDF p.39<br>Div A Sentence 1.3.3.3.(1): codedb-checked, 2nd printing, PDF p.40 |
| HR-05 | Part 9 sentence sends the element to Part 4 because of wind or seismic hazard (sheathing fastening, anchorage, lumber roof sheathing). | mandatory | Registered professional (structural) via Div C 2.4.1.2.(1) | `hourly_wind_pressure_1in50_kPa (NEW)`, `Sa_0_2 (NEW)`, `braced_wall_panels_required (NEW)` | high | Div B Sentence 9.23.3.5.(4) | `codedb-only` | **yes** (P5) | Div B Sentence 9.23.3.5.(4): codedb-checked, 2nd printing, PDF p.967<br>Div B Sentence 9.23.6.1.(6): codedb-checked, 2nd printing, PDF p.970<br>Div B Sentence 9.23.16.5.(3): codedb-checked, 2nd printing, PDF p.988 |
| HR-06 | Part 9 sentence sends foundations/footings/spans to Part 4 because of span, load or ground conditions (joist span > 4.9 m, live load > 2.4 kPa, non-residential floor loads, floors-on-ground carrying superstructure loads, permafrost). | mandatory | Registered professional (structural/geotechnical) via Div C 2.4.1.2.(1) | `supported_joist_span_m (NEW)`, `specified_live_load_kPa (NEW)`, `floor_use_non_residential (NEW)`, `slab_supports_superstructure (NEW)`, `permafrost (NEW)` | high | Div B Sentence 9.15.3.3.(2) | `codedb-only` | **yes** (P3) | Div B Sentence 9.15.3.3.(2): codedb-checked, 2nd printing, PDF p.925<br>Div B Sentence 9.15.3.3.(3): codedb-checked, 2nd printing, PDF p.925<br>Div B Sentence 9.23.4.1.(2): codedb-checked, 2nd printing, PDF p.967<br>Div B Sentence 9.16.1.2.(1): codedb-checked, 2nd printing, PDF p.933<br>Div B Sentence 9.15.1.2.(1): codedb-checked, 2nd printing, PDF p.924 |
| HR-07 | Part 9 sentence sends a material/element to Part 4 (reinforced concrete, loadbearing steel studs, non-standard columns, masonry/steel lintels, framing beyond 9.23.1.1.(1) limits, bowstring/arch trusses > 6 m). | mandatory | Registered professional (structural) via Div C 2.4.1.2.(1) | `structural_elements (NEW: list of element types)`, `framing_exceeds_9_23_1_1 (NEW)`, `truss_type/unsupported_span_m (NEW)` | high | Div B Sentence 9.3.1.1.(3) | `codedb-only` | **yes** (P4) | Div B Sentence 9.3.1.1.(3): codedb-checked, 2nd printing, PDF p.831<br>Div B Sentence 9.24.1.1.(2): codedb-checked, 2nd printing, PDF p.991<br>Div B Sentence 9.17.1.1.(2): codedb-checked, 2nd printing, PDF p.935<br>Div B Sentence 9.20.5.2.(3): codedb-checked, 2nd printing, PDF p.944<br>Div B Sentence 9.23.1.1.(2): codedb-checked, 2nd printing, PDF p.962<br>Div B Sentence 9.4.2.2.(3): codedb-checked, 2nd printing, PDF p.838 |
| HR-08 | Wood roof trusses (Part 9): truss design and interconnections need a registered engineering professional. | mandatory | Registered engineering professional (truss designer) | `roof_trusses`, `truss_interconnections (NEW)` | high | Div B Sentence 9.23.14.11.(1) | `mixed` | — | Div B Sentence 9.23.14.11.(1): codedb-checked, 2nd printing, PDF p.986<br>Div B Sentence 9.23.14.11.(2): codedb-checked, 2nd printing, PDF p.986<br>STANDATA 23-BCI-015R1, Interpretation: source-PDF-checked, STANDATA 23-BCI-015R1, p.1; not codedb |
| HR-09 | Design route uses "good engineering practice" (9.4.1.1.(1)(b), 9.23.13.2/3 bracing, 6.2.1.1 HVAC, 7.2.3.16.(2) drainage, 7.2.7.3.(1) water slide flume). | strongly-indicated | Person authorized to practise engineering (registered engineering professional) | `design_route (NEW: prescriptive | good_engineering_practice | part4)`, `prescriptive_route_confirmed` | medium | Div B Sentence 9.4.1.1.(1) | `mixed` | — | Div B Sentence 9.4.1.1.(1): codedb-checked, 2nd printing, PDF p.836<br>Div B Sentence 9.23.13.3.(2): codedb-checked, 2nd printing, PDF p.979<br>Div B Sentence 6.2.1.1.(1): codedb-checked, 2nd printing, PDF p.593<br>Div B Sentence 7.2.3.16.(2): codedb-checked, 2nd printing, PDF p.626<br>STANDATA 23-BCI-015R1, Discussion: source-PDF-checked, STANDATA 23-BCI-015R1, p.1; not codedb |
| HR-10 | Preserved wood foundation designed under Part 4: owner must show a registered professional is retained for installation field reviews. | mandatory | Registered professional (structural) for field reviews | `preserved_wood_foundation_part4` | high | Div C Sentence 2.4.1.2.(2) | `mixed` | — | Div C Sentence 2.4.1.2.(2): codedb-checked, 2nd printing, PDF p.740<br>STANDATA 23-BCV-012R1, Discussion: source-PDF-checked, STANDATA 23-BCV-012R1, p.1; not codedb |
| HR-11 | Automatic fire suppression system or fire alarm system in a 2.4.1.1.(3) building: professional design, field review, witnessed testing/verification; plans authenticated unless the AHJ deems it a minor alteration. | mandatory | Registered professional (fire protection / mechanical / electrical) | `fire_suppression`, `fire_alarm`, `general_required`, `minor_alteration_existing_system (NEW, AHJ decision)` | high | Div C Sentence 2.4.1.3.(1) | `codedb-only` | **yes** (P7) | Div C Sentence 2.4.1.3.(1): codedb-checked, 2nd printing, PDF p.740<br>Div C Sentence 2.4.1.4.(1): codedb-checked, 2nd printing, PDF p.740<br>Div C Sentence 2.2.3.2.(2): codedb-checked, 2nd printing, PDF p.731<br>Div C Sentence 2.2.3.3.(2): codedb-checked, 2nd printing, PDF p.731 |
| HR-12 | Part 10 building (industrial workforce accommodation) with a sprinkler system: designed by a registered professional (applies regardless of 2.4.1.1. exceptions). | mandatory | Registered professional (fire protection) | `part10_building (NEW)`, `fire_suppression` | high | Div B Sentence 10.4.7.2.(1) | `codedb-only` | **yes** (P10) | Div B Sentence 10.4.7.2.(1): codedb-checked, 2nd printing, PDF p.1504<br>Div B Sentence 10.1.1.2.(2): codedb-checked, 2nd printing, PDF p.1499 |
| HR-13 | Swimming pool or water spray park: drawings and specifications authenticated by a registered professional. | mandatory | Registered professional | `aquatic_facility (NEW)` | high | Div C Sentence 2.2.9.2.(1) | `codedb-only` | **yes** (P9) | Div C Sentence 2.2.9.2.(1): codedb-checked, 2nd printing, PDF p.734 |
| HR-14 | Geotechnical work under Part 4: subsurface investigation, geotechnical loads/resistances, deep-foundation load-test interpretation. | mandatory | Registered professional (geotechnical) | `part4_foundation (NEW)`, `deep_foundations (NEW)`, `load_tests (NEW)` | high | Div B Sentence 4.2.2.1.(1) | `codedb-only` | **yes** (P8) | Div B Sentence 4.2.2.1.(1): codedb-checked, 2nd printing, PDF p.505<br>Div B Sentence 4.2.4.1.(3): codedb-checked, 2nd printing, PDF p.507<br>Div B Sentence 4.2.7.2.(2): codedb-checked, 2nd printing, PDF p.510 |
| HR-15 | Temporary structural members during construction (formwork, falsework, hoarding, scaffolding) "when required". | strongly-indicated | Registered professional retained by the constructor | `temporary_works (NEW)` | medium | Div C Sentence 2.2.14.1.(1) | `codedb-only` | no: discretionary | Div C Sentence 2.2.14.1.(1): codedb-checked, 2nd printing, PDF p.737 |
| HR-16 | Structure that is not one of the building types in Div B Articles 3.2.2.20. to 3.2.2.92. (special/unusual structures, e.g. multi-level storage racking): fire protection must follow good fire protection engineering practice. | strongly-indicated | Fire protection engineer (registered engineering professional) | `special_structure (NEW)`, `storage_racking_multilevel (NEW)` | medium | Div B Sentence 3.2.2.2.(1) | `mixed` | — | Div B Sentence 3.2.2.2.(1): codedb-checked, 2nd printing, PDF p.175<br>STANDATA 23-BCV-014: source-PDF-checked, STANDATA 23-BCV-014, p.1; not codedb |
| HR-17 | Alternative solution documentation: the person(s) taking responsibility must be identified with qualifications; if several, a single coordinator; analysis may need testing procedures or engineering studies. | mandatory | Named responsible designer(s); single coordinator (not necessarily registered) | `professional_name`, `professional_qualifications`, `multiple_responsible_persons (NEW)`, `coordinator_name (NEW)`, `supporting_tests_or_studies (NEW)` | high | Div C Sentence 2.3.1.1.(4) | `codedb-only` | no: not-professional-design | Div C Sentence 2.3.1.1.(4): codedb-checked, 2nd printing, PDF p.739<br>Div C Sentence 2.3.1.1.(6): codedb-checked, 2nd printing, PDF p.739<br>Div C Sentence 2.3.1.1.(3): codedb-checked, 2nd printing, PDF p.739 |
| HR-20 | SCO opinion that size or complexity may give rise to safety concerns → SCO may require sealed plans and professional review during construction (and AHJ may require registered professionals under the code). | discretionary | Safety codes officer decides; then registered engineer/architect | `special_safety_concerns`, `ahj_requires_professional`, `complexity_flags (NEW)` | high | Administrative Items Regulation s.18(1) | `mixed` | — | Administrative Items Regulation s.18(1): source-PDF-checked, Administrative Items Regulation AR 16/2004, p.10; not codedb (legislation)<br>Administrative Items Regulation s.18(1)-(2): source-PDF-checked, Administrative Items Regulation AR 16/2004, p.11; not codedb (legislation)<br>Div C Sentence 2.4.1.1.(4): codedb-checked, 2nd printing, PDF p.740 |
| HR-21 | Work is the "practice of engineering" and no EGPA exception applies (exceptions include supervised work, own-property work not involving public safety, and the small-building list in s.2(7), which uses GROSS AREA per floor). | mandatory | Professional engineer / licensee / permit holder | `activity_type (NEW)`, `own_property_sole_use (NEW)`, `occupancy`, `storeys`, `gross_area_per_floor_m2 (NEW)` | high | EGPA s.2(1) | `source-pdf-only` | — | EGPA s.2(1): source-PDF-checked, Engineering and Geoscience Professions Act, p.12; not codedb (legislation)<br>EGPA s.1(q): source-PDF-checked, Engineering and Geoscience Professions Act, p.10; not codedb (legislation)<br>EGPA s.2(4)(e): source-PDF-checked, Engineering and Geoscience Professions Act, p.13; not codedb (legislation)<br>EGPA s.2(7)(a): source-PDF-checked, Engineering and Geoscience Professions Act, p.14; not codedb (legislation) |
| HR-22 | Work is the "practice of architecture" for a building not on the Architects Act s.2(6) list (same small-building list, gross area per floor). | mandatory | Registered architect (or other authorized entity) | `occupancy`, `storeys`, `gross_area_per_floor_m2 (NEW)`, `dwelling_units_total (NEW, incl. suites)` | high | Architects Act s.2(1) | `source-pdf-only` | — | Architects Act s.2(1): source-PDF-checked, Architects Act, p.8; not codedb (legislation)<br>Architects Act s.1(l): source-PDF-checked, Architects Act, p.7; not codedb (legislation)<br>Architects Act s.2(6)(b): source-PDF-checked, Architects Act, p.10; not codedb (legislation) |
| HR-23 | Where the regulations require a stamped/sealed design, no permit may issue unless the design is signed, stamped and sealed. | mandatory | Engineer/architect (seal) and permit issuer (gate) | `seal_required (derived from HR-01/03/20)`, `professional_seal` | high | Safety Codes Act s.45(1) | `source-pdf-only` | — | Safety Codes Act s.45(1): source-PDF-checked, Safety Codes Act, p.35; not codedb (legislation)<br>Safety Codes Act s.11: source-PDF-checked, Safety Codes Act, p.14; not codedb (legislation) |
| HR-24 | Architect applying without an engineer's stamp on final drawings — only if APEGA Council has authorized it. | discretionary | APEGA Council (on Joint Board recommendation) | `applicant_role (NEW)`, `engineer_stamp_present (NEW)` | medium | EGPA s.38 | `source-pdf-only` | — | EGPA s.38: source-PDF-checked, Engineering and Geoscience Professions Act, p.42; not codedb (legislation) |
| HR-30 | Any variance (alternative solution) request: only an SCO or Administrator can decide it; the app must route to them and never state the variance is granted. | mandatory | Safety codes officer (or Administrator); SCO must notify an Administrator and register the variance | `intake_action`, `variance_requested` | high | Safety Codes Act s.38(1) | `source-pdf-only` | — | Safety Codes Act s.38(1): source-PDF-checked, Safety Codes Act, p.31; not codedb (legislation)<br>Safety Codes Act s.38(3): source-PDF-checked, Safety Codes Act, p.31; not codedb (legislation)<br>IB-2025-11-18: source-PDF-checked, SCC Information Bulletin IB-2025-11-18, p.2; not codedb<br>IB-2026-10-01: source-PDF-checked, SCC Information Bulletin IB-2026-10-01, p.3; not codedb<br>IB-2026-10-16: source-PDF-checked, SCC Information Bulletin IB-2026-10-16, p.2; not codedb |
| HR-31 | Province-wide variance or code interpretation (ambiguity/lack of clarity in the code) → Provincial Building Administrator. | discretionary | Provincial Building Administrator | `code_ambiguity (NEW)`, `scope (site vs jurisdiction-wide)` | high | Div C Sentence 2.2.1.2.(1) | `codedb-only` | no: discretionary | Div C Sentence 2.2.1.2.(1): codedb-checked, 2nd printing, PDF p.729<br>Div C Sentence 2.2.1.3.(1): codedb-checked, 2nd printing, PDF p.729 |
| HR-32 | Barrier-free (Div B Section 3.8.) relaxation → Provincial Barrier-Free Administrator or PBA, not the local SCO. | mandatory | Provincial Barrier-Free Administrator / PBA | `provisions_varied (any 3.8.x)` | high | Div C Sentence 2.2.1.4.(1) | `codedb-only` | no: not-professional-design | Div C Sentence 2.2.1.4.(1): codedb-checked, 2nd printing, PDF p.730 |
| HR-33 | Minor dimensional shortfall (≤ 2 %) with no reduction in life safety → AHJ may accept without a variance. | discretionary | Authority having jurisdiction (SCO) | `dimension_required`, `dimension_proposed`, `percent_deviation (derived)` | high | Div C Sentence 2.2.2.3.(1) | `codedb-only` | no: discretionary | Div C Sentence 2.2.2.3.(1): codedb-checked, 2nd printing, PDF p.730 |
| HR-34 | Change of occupancy, alteration, or existing non-compliant construction → AHJ acceptance of the level of safety. | discretionary | Authority having jurisdiction (SCO) | `change_of_occupancy (NEW)`, `alteration_existing (NEW)` | high | Div A Sentence 1.1.1.2.(4) | `codedb-only` | no: discretionary | Div A Sentence 1.1.1.2.(4): codedb-checked, 2nd printing, PDF p.38<br>Div A Sentence 1.1.1.2.(6): codedb-checked, 2nd printing, PDF p.38 |
| HR-35 | Items the code sends to the AHJ for review and acceptance: pool slides/play equipment, supplemental disinfection, water-slide special discharge, Part 10 canopy/hood airflow designs, tents/air-supported structures, temporary buildings. | mandatory | Authority having jurisdiction (SCO) | `aquatic_equipment (NEW)`, `tent_or_air_supported (NEW)`, `temporary_building (NEW)` | high | Div C Sentence 2.2.2.5.(2) | `codedb-only` | no: not-professional-design | Div C Sentence 2.2.2.5.(2): codedb-checked, 2nd printing, PDF p.731<br>Div C Sentence 2.2.11.2.(1): codedb-checked, 2nd printing, PDF p.735<br>Div C Sentence 2.2.11.3.(2): codedb-checked, 2nd printing, PDF p.735<br>Div B Sentence 10.6.4.2.(3): codedb-checked, 2nd printing, PDF p.1508 |
| HR-36 | Incorrect or insufficient information → permit issuer may refuse; may demand further information or records. | discretionary | Permit issuer / SCO | `completeness gaps (engine D-codes)` | high | Permit Regulation s.26(b) | `source-pdf-only` | — | Permit Regulation s.26(b): source-PDF-checked, Permit Regulation AR 204/2007, p.21; not codedb (legislation)<br>Permit Regulation s.20(i): source-PDF-checked, Permit Regulation AR 204/2007, p.18; not codedb (legislation)<br>Safety Codes Act s.35(1): source-PDF-checked, Safety Codes Act, p.30; not codedb (legislation) |
| HR-40 | Fire-resistance rating not from a listed/tabulated source → must come from CAN/ULC-S101 testing (accredited lab). | strongly-indicated | Accredited testing laboratory / certification body | `fire_resistance_rating_source (NEW)` | medium | Div B Sentence 3.1.7.1.(1) | `codedb-only` | no: not-professional-design | Div B Sentence 3.1.7.1.(1): codedb-checked, 2nd printing, PDF p.151 |
| HR-41 | Combustible cladding on a building required to be noncombustible → CAN/ULC-S134 full-scale test results needed. | mandatory | Testing laboratory (CAN/ULC-S134) | `construction_type_required (NEW)`, `cladding_combustible (NEW)` | high | Div B Sentence 3.1.5.5.(1) | `codedb-only` | no: not-professional-design | Div B Sentence 3.1.5.5.(1): codedb-checked, 2nd printing, PDF p.137 |
| HR-42 | Non-flammable medical gas piping → testing agency report accepted by AHJ before use. | mandatory | Testing agency + AHJ | `medical_gas_piping (NEW)` | high | Div C Sentence 2.2.11.4.(2) | `codedb-only` | no: not-professional-design | Div C Sentence 2.2.11.4.(2): codedb-checked, 2nd printing, PDF p.736<br>Div C Sentence 2.2.11.4.(3): codedb-checked, 2nd printing, PDF p.736 |
| HR-43 | Off-site constructed components/buildings: off-site review, CSA A277 certification, or PBA-approved certification for relocatable industrial camps; STANDATA variance route uses registered-professional verification. | mandatory | Certification organization / registered professionals | `off_site_constructed (NEW)`, `csa_a277_certified (NEW)` | high | Div C Sentence 2.5.1.1.(1) | `mixed` | — | Div C Sentence 2.5.1.1.(1): codedb-checked, 2nd printing, PDF p.742<br>Div C Sentence 2.5.1.1.(3): codedb-checked, 2nd printing, PDF p.742<br>STANDATA 23-BCV-002: source-PDF-checked, STANDATA 23-BCV-002, p.2; not codedb |
| HR-44 | Welded construction for Part 4 buildings → evidence of CWB certification if the AHJ requests it. | discretionary | AHJ (request) / Canadian Welding Bureau | `part4_design`, `welded_steel (NEW)` | high | Div C Sentence 2.2.2.4.(1) | `codedb-only` | no: discretionary | Div C Sentence 2.2.2.4.(1): codedb-checked, 2nd printing, PDF p.730 |
| HR-50 | Case relies on a province-wide STANDATA variance whose conditions name a professional (examples: 23-BCV-005 risk assessment; 23-BCV-010R1 APEGA authentication). | mandatory | Registered engineering professional per the variance conditions | `standata_variance_relied_on (NEW)` | high | STANDATA 23-BCV-005, Variance condition 2 | `source-pdf-only` | — | STANDATA 23-BCV-005, Variance condition 2: source-PDF-checked, STANDATA 23-BCV-005, p.2; not codedb<br>STANDATA 23-BCV-010R1, condition 1: source-PDF-checked, STANDATA 23-BCV-010R1, p.2; not codedb |

## Mandatory codedb-only triggers for section-d-routing

Of the 21 `codedb-only` triggers, `mandatory: true` means the quoted code text itself requires professional design or authenticated (sealed) documents once the condition is met. `false` is either `discretionary` (the AHJ or an Administrator may require or decide) or `not-professional-design` (testing, routing or AHJ acceptance, with no registered professional named). JSON filter: `verification_class == "codedb-only" and mandatory`. The order below is the suggested build order (`section_d_routing_priority`): general root rules first, then the Part 9 → Part 4 escalations that come up most often, then rarer building types.

| Priority | ID | Basis (quoted code text) |
|---|---|---|
| 1 | HR-03 | Div C 2.4.1.2.(1): for Part 4 design "the designer shall be a registered professional"; Div C 2.2.4.2.(1) structural drawings "shall be authenticated". |
| 2 | HR-01 | Div C 2.4.1.1.(3): drawings and specifications "shall be authenticated by one or more registered professionals" outside the (1) exceptions. |
| 3 | HR-06 | Div B 9.15.3.3.(2)/(3), Div B 9.23.4.1.(2), Div B 9.16.1.2.(1) "shall be designed in accordance with" Part 4 / Section 4.2 / 4.1.3; Div B 9.15.1.2.(1) permafrost "designed by a designer competent"; Part 4 design then needs a registered professional under Div C 2.4.1.2.(1). |
| 4 | HR-07 | Div B 9.3.1.1.(3), Div B 9.24.1.1.(2), Div B 9.17.1.1.(2), Div B 9.20.5.2.(3), Div B 9.23.1.1.(2), Div B 9.4.2.2.(3) "shall be designed in conformance with" Part 4; Part 4 design needs a registered professional under Div C 2.4.1.2.(1). |
| 5 | HR-05 | Div B 9.23.3.5.(4), Div B 9.23.6.1.(6), Div B 9.23.16.5.(3) "shall conform to Part 4" / "shall be designed according to Part 4" above the wind/Sa(0.2) thresholds; then Div C 2.4.1.2.(1). |
| 6 | HR-04 | Div A 1.3.3.2.(1): Parts 3 to 6 of Div B "apply to all buildings" listed there (e.g. post-disaster, Group A, Group B), i.e. outside Part 9 scope; that Part 4 design needs a registered professional under Div C 2.4.1.2.(1) (quoted under HR-03). Chain of two codedb-checked sentences. |
| 7 | HR-11 | Div C 2.4.1.3.(1)/Div C 2.4.1.4.(1) owner shows it has "retained a registered professional to" design the sprinkler/fire alarm system in a Div C 2.4.1.1.(3) building; plans "shall be authenticated" unless the AHJ deems it a minor alteration (Div C 2.2.3.2.(2), Div C 2.2.3.3.(2)). |
| 8 | HR-14 | Div B 4.2.2.1.(1) subsurface investigation "carried out by or under the direction of a registered professional"; Div B 4.2.4.1.(3), Div B 4.2.7.2.(2) same. |
| 9 | HR-13 | Div C 2.2.9.2.(1) pool / spray park drawings "shall be authenticated by a registered professional". |
| 10 | HR-12 | Div B 10.4.7.2.(1) Part 10 sprinkler system "shall be designed by a registered professional". |

Not mandatory (codedb-only):

| ID | Class | Basis |
|---|---|---|
| HR-15 | discretionary | Div C 2.2.14.1.(1) constructor retains a registered professional "when required"; the text does not say when, so it is a conditional/AHJ-or-contract call, not automatic. |
| HR-17 | not-professional-design | Div C 2.3.1.1.(4)/(6) must state the "qualifications, experience and background" of the responsible person and name "a single person" to co-ordinate; does not require a registered professional. |
| HR-31 | discretionary | Div C 2.2.1.2.(1)/Div C 2.2.1.3.(1) a request "may be submitted" to the PBA; routing, not professional design. |
| HR-32 | not-professional-design | Div C 2.2.1.4.(1) only the PBFA/PBA "may grant relaxation" of Div B Section 3.8.; routing to an administrator, not professional design. |
| HR-33 | discretionary | Div C 2.2.2.3.(1) the AHJ "may accept a minor variation"; no professional required. |
| HR-34 | discretionary | Div A 1.1.1.2.(4)/(6) acceptance by the AHJ ("acceptable to", "may accept"); no professional required by the text. |
| HR-35 | not-professional-design | Div C 2.2.2.5.(2), Div C 2.2.11.2.(1), Div C 2.2.11.3.(2), Div B 10.6.4.2.(3): submitted to / permitted by the AHJ; AHJ acceptance, no professional named. |
| HR-40 | not-professional-design | Div B 3.1.7.1.(1) rating "determined on the basis of the results of tests" (CAN/ULC-S101); a test lab, not a professional. |
| HR-41 | not-professional-design | Div B 3.1.5.5.(1) cladding performance "when tested in accordance with CAN/ULC-S134"; a test, not a professional. |
| HR-42 | not-professional-design | Div C 2.2.11.4.(2)/(3) a "testing agency" report accepted by the AHJ; not a professional. |
| HR-44 | discretionary | Div C 2.2.2.4.(1) "If requested by the authority having jurisdiction": CWB evidence, not professional design. |

## A. Professional involvement (code)

### HR-01: Building is outside every general exception in Div C 2.4.1.1.(1), so registered professionals must authenticate the drawings and specifications.

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P2). Div C 2.4.1.1.(3): drawings and specifications "shall be authenticated by one or more registered professionals" outside the (1) exceptions.
- **Type:** mandatory. **Confidence:** high. **Human:** Registered architectural and/or engineering professional(s) for the applicable disciplines.
- **Case facts:** `occupancy`, `storeys`, `building_area_m2`, `principal_dwelling_units`, `secondary_suites_count (NEW)`, `farm_public_use`, `relocatable_industrial_camp (NEW; engine uses occupancy value)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.1.1.(3), PDF p.740 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.740. © National Research Council of Canada.
  > For buildings other than those described in Sentence (1), the drawings and specifications shall be authenticated by one or more registered professionals …
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.1.1.(1), PDF p.739 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.739. © National Research Council of Canada.
  > involvement of a registered professional is not required for a building a) 3 storeys or less in building height, classified as an assembly, care, treatment …
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.1.1.(2), PDF p.740 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.740. © National Research Council of Canada.
  > For the purposes of Sentence (1), secondary suites need not be considered as dwelling units.
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.1.1.(5), PDF p.740 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.740. © National Research Council of Canada.
  > Drawings and specifications required to be authenticated by a registered professional shall be authenticated … Architects Act or the Engineering and Geoscience Professions Act.
- **Notes:** Exception thresholds (Div C 2.4.1.1.(1), p739): assembly/care/treatment/detention ≤3 storeys: 300/150/100 m² building area for 1/2/3 storeys; residential: single-family, or multi-family with ≤4 dwelling units (secondary suites not counted, 2.4.1.1.(2)); hotel/motel ≤3 storeys: 400/200/130 m²; business & personal services/mercantile/industrial ≤3 storeys: 500/250/165 m²; farm building not for public use; relocatable industrial camp building. "Except as required by Sentence (4)" — see HR-20.
- **Engine today:** Covered: professional.py general_building / general_exception / general_unresolved; same thresholds in _AREA_LIMITS.

### HR-02: A 2.4.1.1.(3) project needs a coordinating registered professional (CRP), registered professionals of record (RPRs) and Schedules A and B before the permit application; Schedule C-1 before occupancy; work stops if the CRP or an RPR leaves.

- **Verification class:** `mixed`
- **Type:** mandatory. **Confidence:** high. **Human:** Coordinating registered professional + registered professionals of record (architectural, structural, mechanical, electrical, geotechnical as applicable).
- **Case facts:** `general_required == yes (from HR-01)`, `schedule_a_provided (NEW)`, `schedule_b_provided (NEW)`, `crp_name (NEW)`, `rpr_disciplines (NEW)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.2.1.(1), PDF p.741 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.741. © National Research Council of Canada.
  > This Subsection applies to a project that falls within the scope of Sentence 2.4.1.1.(3).
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.2.2.(1), PDF p.741 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.741. © National Research Council of Canada.
  > Before applying for a permit, the owner shall a) retain a coordinating registered professional to coordinate the design and field reviews of the registered professionals …
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.2.2.(1), PDF p.741 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.741. © National Research Council of Canada.
  > c) provide the authority having jurisdiction with Schedules A and B
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.2.4.(1), PDF p.742 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.742. © National Research Council of Canada.
  > Before issuing an occupancy permit or giving permission to occupy, the authority having jurisdiction shall receive Schedule C-1 from the coordinating registered professional.
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.2.5.(1), PDF p.742 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.742. © National Research Council of Canada.
  > work on the portion … shall stop until a replacement is retained and a new Schedule A is submitted to the authority having jurisdiction.
- **Notes:** The brief/plan reference to "Tables 2.4.2.1.A/B" has no match in NBC(AE) 2023 2nd printing (codedb: 0 provisions mention "Table 2.4.2"). The equivalents are Schedules A, B, C-1, C-2, C-3 named in Div C 2.4.2.2-2.4.2.4 (Note A-2.4.2.2.(1)(c), p744). The challenge-brief quote attributed to 2.4.2.1.(1) ("Where required, the design and field review shall be carried out by a registered professional skilled in the appropriate discipline.") does NOT appear in the code; 2.4.2.1.(1) is the application sentence quoted here.
- **Engine today:** NOT covered: professional.py never mentions Schedules, CRP or 2.4.2.x.

### HR-03: Any structural design carried out under Part 4 of Div B (including a single engineered beam, connection or foundation in a Part 9 house).

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P1). Div C 2.4.1.2.(1): for Part 4 design "the designer shall be a registered professional"; Div C 2.2.4.2.(1) structural drawings "shall be authenticated".
- **Type:** mandatory. **Confidence:** high. **Human:** Registered professional skilled in the work concerned (structural engineer in practice).
- **Case facts:** `part4_design`, `part4_elements (NEW: list)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.1.2.(1), PDF p.740 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.740. © National Research Council of Canada.
  > For design carried out in accordance with Part 4 of Division B, the designer shall be a registered professional skilled in the work concerned.
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.4.2.(1), PDF p.732 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.732. © National Research Council of Canada.
  > Structural drawings and related documents submitted with the application to build shall be authenticated by a registered professional as required by Sentence 2.4.1.2.(1).
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.4.4.(1), PDF p.732 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.732. © National Research Council of Canada.
  > Structural drawings of parts or components including guards shall be authenticated by a registered professional.
- **Notes:** Div C Note A-2.4.1.2.(1) (p744): "Part 4 … is written on the assumption that structural design will be carried out by a registered professional who is qualified to perform such design." Div C Subsection 2.2.4. (incl. Div C Article 2.2.4.4., guards) applies only where Div C Subsection 2.4.1. requires a registered professional (Div C 2.2.4.1.(1)).
- **Engine today:** Covered as a boolean (part4_design). Not derived from facts — see HR-05..HR-08 for the Part 9→Part 4 triggers the engine could detect.

### HR-04: Building is not within Part 9 scope (Div A 1.3.3.2.), so Part 4 structural design applies to it → Div C 2.4.1.2.(1) professional, even if the building fits a Div C 2.4.1.1.(1) size exception.

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P6). Div A 1.3.3.2.(1): Parts 3 to 6 of Div B "apply to all buildings" listed there (e.g. post-disaster, Group A, Group B), i.e. outside Part 9 scope; that Part 4 design needs a registered professional under Div C 2.4.1.2.(1) (quoted under HR-03). Chain of two codedb-checked sentences.
- **Type:** strongly-indicated. **Confidence:** medium. **Human:** Registered professional (structural) for the Part 4 design.
- **Case facts:** `occupancy (incl. Group A, B1-B3, F1, post_disaster NEW)`, `storeys`, `building_area_m2`
- NBC(AE) 2023, 2nd printing, Div A Sentence 1.3.3.2.(1), PDF p.39 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.39. © National Research Council of Canada.
  > Parts 3, 4, 5, and 6 of Division B apply … c) exceeding 600 m² in building area or exceeding 3 storeys in building height
- NBC(AE) 2023, 2nd printing, Div A Sentence 1.3.3.3.(1), PDF p.40 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.40. © National Research Council of Canada.
  > Part 9 of Division B applies to all buildings … of 3 storeys or less in building height, having a building area not exceeding 600 m²
- **Notes:** Model-derived chain (Div A 1.3.3.2.(1) → Part 4 applies → Div C 2.4.1.2.(1)); not stated in one sentence. The repo research sheet treats "Part 3 merely because of occupancy" as "Depends". Keep as strongly-indicated pending human confirmation.
- **Engine today:** NOT covered: engine does not link Part 3/4 applicability to 2.4.1.2.(1).

### HR-05: Part 9 sentence sends the element to Part 4 because of wind or seismic hazard (sheathing fastening, anchorage, lumber roof sheathing).

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P5). Div B 9.23.3.5.(4), Div B 9.23.6.1.(6), Div B 9.23.16.5.(3) "shall conform to Part 4" / "shall be designed according to Part 4" above the wind/Sa(0.2) thresholds; then Div C 2.4.1.2.(1).
- **Type:** mandatory. **Confidence:** high. **Human:** Registered professional (structural) via Div C 2.4.1.2.(1).
- **Case facts:** `hourly_wind_pressure_1in50_kPa (NEW)`, `Sa_0_2 (NEW)`, `braced_wall_panels_required (NEW)`
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.23.3.5.(4), PDF p.967 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.967. © National Research Council of Canada.
  > Fastening of sheathing shall conform to Part 4 … wind pressure is equal to or greater than 1.2 kPa … Sa(0.2), is greater than 1.8.
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.23.6.1.(6), PDF p.970 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.970. © National Research Council of Canada.
  > Where … Sa(0.2), is greater than 1.8 or … wind pressure is equal to or greater than 1.2 kPa, anchorage shall be designed according to Part 4.
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.23.16.5.(3), PDF p.988 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.988. © National Research Council of Canada.
  > … roof sheathing shall be designed according to Part 4 … Sa(0.2), is greater than 1.2, or … wind pressure is equal to or greater than 1.20 kPa.
- **Notes:** Climatic values come from Div B Appendix C per location; not looked up here.
- **Engine today:** NOT covered (no climate facts in ProfessionalFacts).

### HR-06: Part 9 sentence sends foundations/footings/spans to Part 4 because of span, load or ground conditions (joist span > 4.9 m, live load > 2.4 kPa, non-residential floor loads, floors-on-ground carrying superstructure loads, permafrost).

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P3). Div B 9.15.3.3.(2)/(3), Div B 9.23.4.1.(2), Div B 9.16.1.2.(1) "shall be designed in accordance with" Part 4 / Section 4.2 / 4.1.3; Div B 9.15.1.2.(1) permafrost "designed by a designer competent"; Part 4 design then needs a registered professional under Div C 2.4.1.2.(1).
- **Type:** mandatory. **Confidence:** high. **Human:** Registered professional (structural/geotechnical) via Div C 2.4.1.2.(1).
- **Case facts:** `supported_joist_span_m (NEW)`, `specified_live_load_kPa (NEW)`, `floor_use_non_residential (NEW)`, `slab_supports_superstructure (NEW)`, `permafrost (NEW)`
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.15.3.3.(2), PDF p.925 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.925. © National Research Council of Canada.
  > Except as provided in Sentence 9.15.3.4.(2), where the span of the supported joists exceeds 4.9 m, footings shall be designed in accordance with Section 4.2.
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.15.3.3.(3), PDF p.925 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.925. © National Research Council of Canada.
  > Where the specified live load exceeds 2.4 kPa, footings shall be designed in accordance with Section 4.2.
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.23.4.1.(2), PDF p.967 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.967. © National Research Council of Canada.
  > Spans for joists, beams and lintels supporting floors shall be determined according to Subsection 4.1.3. where the supported floors a) serve other than residential areas …
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.16.1.2.(1), PDF p.933 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.933. © National Research Council of Canada.
  > Floors-on-ground that support loads from the superstructure shall be designed in conformance with Part 4.
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.15.1.2.(1), PDF p.924 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.924. © National Research Council of Canada.
  > Buildings erected on permafrost shall have foundations designed by a designer competent in this field in accordance with the appropriate requirements of Part 4.
- **Engine today:** NOT covered as facts; only via part4_design boolean.

### HR-07: Part 9 sentence sends a material/element to Part 4 (reinforced concrete, loadbearing steel studs, non-standard columns, masonry/steel lintels, framing beyond 9.23.1.1.(1) limits, bowstring/arch trusses > 6 m).

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P4). Div B 9.3.1.1.(3), Div B 9.24.1.1.(2), Div B 9.17.1.1.(2), Div B 9.20.5.2.(3), Div B 9.23.1.1.(2), Div B 9.4.2.2.(3) "shall be designed in conformance with" Part 4; Part 4 design needs a registered professional under Div C 2.4.1.2.(1).
- **Type:** mandatory. **Confidence:** high. **Human:** Registered professional (structural) via Div C 2.4.1.2.(1).
- **Case facts:** `structural_elements (NEW: list of element types)`, `framing_exceeds_9_23_1_1 (NEW)`, `truss_type/unsupported_span_m (NEW)`
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.3.1.1.(3), PDF p.831 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.831. © National Research Council of Canada.
  > Except as provided in Sentence (4), reinforced concrete shall be designed to conform to the requirements of Part 4.
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.24.1.1.(2), PDF p.991 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.991. © National Research Council of Canada.
  > Where loadbearing steel studs are used, they shall be designed in conformance with Part 4.
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.17.1.1.(2), PDF p.935 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.935. © National Research Council of Canada.
  > Columns for applications other than as described in Sentence (1) shall be designed in accordance with Part 4.
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.20.5.2.(3), PDF p.944 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.944. © National Research Council of Canada.
  > Steel angle lintels supporting masonry other than veneer, masonry and reinforced concrete lintels, and masonry arches shall be designed in accordance with Part 4 …
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.23.1.1.(2), PDF p.962 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.962. © National Research Council of Canada.
  > Where the conditions in Sentence (1) are exceeded for wood constructions, the design of the framing and fastening shall conform to Subsection 4.3.1.
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.4.2.2.(3), PDF p.838 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.838. © National Research Council of Canada.
  > Bow string, arch or semi-circular roof trusses having an unsupported span greater than 6 m shall be designed in conformance with the snow load requirements …
- **Notes:** Full list of Part 9 sentences pointing to Part 4/Section 4.x found by SQL LIKE (33 hits) is not included in this pack.
- **Engine today:** NOT covered as facts.

### HR-08: Wood roof trusses (Part 9): truss design and interconnections need a registered engineering professional.

- **Verification class:** `mixed`
- **Type:** mandatory. **Confidence:** high. **Human:** Registered engineering professional (truss designer).
- **Case facts:** `roof_trusses`, `truss_interconnections (NEW)`
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.23.14.11.(1), PDF p.986 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.986. © National Research Council of Canada.
  > Wood roof trusses shall be designed in accordance with good engineering practice such as that described in TPIC 2019
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.23.14.11.(2), PDF p.986 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.986. © National Research Council of Canada.
  > The joint connections used in trusses described in Sentence (1) shall be designed in conformance with the requirements in Subsection 4.3.1.
- STANDATA 23-BCI-015R1 (May 2025), wood roof trusses, STANDATA 23-BCI-015R1, Interpretation, source PDF page 1 (https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/750b7bd6-7a6a-47b8-8acf-bd58298f672b/download/ma-standata-interpretation-building-23-bci-015r1-2025-05.pdf). Verification: source-PDF-checked, STANDATA 23-BCI-015R1, p.1; not codedb.
  > Based on the requirements of Article 9.23.14.11., a truss assembly constructed using wood trusses must be designed by a registered engineering professional … — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Notes:** Interpretation also allows the authenticated truss design to be a permit condition before framing inspection.
- **Engine today:** Covered: roof_trusses → truss_design / truss_part4 (yes).

### HR-09: Design route uses "good engineering practice" (9.4.1.1.(1)(b), 9.23.13.2/3 bracing, 6.2.1.1 HVAC, 7.2.3.16.(2) drainage, 7.2.7.3.(1) water slide flume).

- **Verification class:** `mixed`
- **Type:** strongly-indicated. **Confidence:** medium. **Human:** Person authorized to practise engineering (registered engineering professional).
- **Case facts:** `design_route (NEW: prescriptive | good_engineering_practice | part4)`, `prescriptive_route_confirmed`
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.4.1.1.(1), PDF p.836 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.836. © National Research Council of Canada.
  > b) be designed according to good engineering practice such as that provided in CWC 2014 … or c) be designed according to Part 4
- NBC(AE) 2023, 2nd printing, Div B Sentence 9.23.13.3.(2), PDF p.979 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.979. © National Research Council of Canada.
  > Bracing to resist lateral loads shall be designed and constructed in accordance with a) Part 4, or b) good engineering practice
- NBC(AE) 2023, 2nd printing, Div B Sentence 6.2.1.1.(1), PDF p.593 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.593. © National Research Council of Canada.
  > Heating, ventilating and air-conditioning systems, including mechanical refrigeration equipment, shall be designed, constructed and installed in conformance with good engineering practice
- NBC(AE) 2023, 2nd printing, Div B Sentence 7.2.3.16.(2), PDF p.626 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.626. © National Research Council of Canada.
  > A drainage system shall be designed in accordance with good engineering practice.
- STANDATA 23-BCI-015R1 (May 2025), wood roof trusses, STANDATA 23-BCI-015R1, Discussion, source PDF page 1 (https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/750b7bd6-7a6a-47b8-8acf-bd58298f672b/download/ma-standata-interpretation-building-23-bci-015r1-2025-05.pdf). Verification: source-PDF-checked, STANDATA 23-BCI-015R1, p.1; not codedb.
  > The term “good engineering practice” requires the involvement of an individual who is authorized to engage in the practice of engineering … — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Notes:** The STANDATA sentence is written about Article 9.23.14.11.; applying it to other "good engineering practice" sentences is an extrapolation (hence strongly-indicated, medium).
- **Engine today:** Partly: design_scope "depends" fires whenever prescriptive_route_confirmed is not True; no route-specific trigger.

### HR-10: Preserved wood foundation designed under Part 4: owner must show a registered professional is retained for installation field reviews.

- **Verification class:** `mixed`
- **Type:** mandatory. **Confidence:** high. **Human:** Registered professional (structural) for field reviews.
- **Case facts:** `preserved_wood_foundation_part4`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.1.2.(2), PDF p.740 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.740. © National Research Council of Canada.
  > If a preserved wood foundation designed in accordance with Part 4 … retained a registered professional to perform field reviews of the foundation system during installation.
- STANDATA 23-BCV-012R1 (May 2025), PWF with MLTP, STANDATA 23-BCV-012R1, Discussion, source PDF page 1 (https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/f0256837-d2a2-4038-bb0c-cb19aacfeb43/download/ma-standata-variance-building-23-bcv-012r1-2025-05.pdf). Verification: source-PDF-checked, STANDATA 23-BCV-012R1, p.1; not codedb.
  > Sentence 2.4.1.2.(2) of Division C requires a registered professional to perform field reviews of preserved wood foundations designed in accordance to Part 4. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Engine today:** Covered: preserved_wood_foundation (yes).

### HR-11: Automatic fire suppression system or fire alarm system in a 2.4.1.1.(3) building: professional design, field review, witnessed testing/verification; plans authenticated unless the AHJ deems it a minor alteration.

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P7). Div C 2.4.1.3.(1)/Div C 2.4.1.4.(1) owner shows it has "retained a registered professional to" design the sprinkler/fire alarm system in a Div C 2.4.1.1.(3) building; plans "shall be authenticated" unless the AHJ deems it a minor alteration (Div C 2.2.3.2.(2), Div C 2.2.3.3.(2)).
- **Type:** mandatory. **Confidence:** high. **Human:** Registered professional (fire protection / mechanical / electrical).
- **Case facts:** `fire_suppression`, `fire_alarm`, `general_required`, `minor_alteration_existing_system (NEW, AHJ decision)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.1.3.(1), PDF p.740 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.740. © National Research Council of Canada.
  > If an automatic fire suppression system is to be installed … the owner shall submit evidence … retained a registered professional to a) design the system …
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.1.4.(1), PDF p.740 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.740. © National Research Council of Canada.
  > If a fire alarm system is to be installed … the owner shall submit evidence … retained a registered professional to a) design the system …
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.3.2.(2), PDF p.731 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.731. © National Research Council of Canada.
  > Unless deemed by the authority having jurisdiction … minor alteration … all plans … for an automatic fire suppression system … shall be authenticated by a registered professional.
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.3.3.(2), PDF p.731 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.731. © National Research Council of Canada.
  > Unless deemed by the authority having jurisdiction … minor alteration … all plans for a fire alarm system … shall be authenticated by a registered professional.
- **Engine today:** Covered: suppression / fire_alarm. NOT covered: the 2.2.3.2.(2)/2.2.3.3.(2) "minor alteration" AHJ carve-out.

### HR-12: Part 10 building (industrial workforce accommodation) with a sprinkler system: designed by a registered professional (applies regardless of 2.4.1.1. exceptions).

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P10). Div B 10.4.7.2.(1) Part 10 sprinkler system "shall be designed by a registered professional".
- **Type:** mandatory. **Confidence:** high. **Human:** Registered professional (fire protection).
- **Case facts:** `part10_building (NEW)`, `fire_suppression`
- NBC(AE) 2023, 2nd printing, Div B Sentence 10.4.7.2.(1), PDF p.1504 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.1504. © National Research Council of Canada.
  > If a sprinkler system is installed, it shall be designed by a registered professional in conformance with NFPA 13
- NBC(AE) 2023, 2nd printing, Div B Sentence 10.1.1.2.(2), PDF p.1499 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.1499. © National Research Council of Canada.
  > this Part applies to a building providing accommodation for an industrial workforce living and working in a temporary location
- **Engine today:** NOT covered (engine treats relocatable_industrial_camp as a general "no").

### HR-13: Swimming pool or water spray park: drawings and specifications authenticated by a registered professional.

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P9). Div C 2.2.9.2.(1) pool / spray park drawings "shall be authenticated by a registered professional".
- **Type:** mandatory. **Confidence:** high. **Human:** Registered professional.
- **Case facts:** `aquatic_facility (NEW)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.9.2.(1), PDF p.734 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.734. © National Research Council of Canada.
  > … the drawings and specifications for a swimming pool or water spray park shall be authenticated by a registered professional.
- **Engine today:** NOT covered.

### HR-14: Geotechnical work under Part 4: subsurface investigation, geotechnical loads/resistances, deep-foundation load-test interpretation.

- **Verification class:** `codedb-only`. **Mandatory:** **yes** (P8). Div B 4.2.2.1.(1) subsurface investigation "carried out by or under the direction of a registered professional"; Div B 4.2.4.1.(3), Div B 4.2.7.2.(2) same.
- **Type:** mandatory. **Confidence:** high. **Human:** Registered professional (geotechnical).
- **Case facts:** `part4_foundation (NEW)`, `deep_foundations (NEW)`, `load_tests (NEW)`
- NBC(AE) 2023, 2nd printing, Div B Sentence 4.2.2.1.(1), PDF p.505 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.505. © National Research Council of Canada.
  > A subsurface investigation, including groundwater conditions, shall be carried out by or under the direction of a registered professional having knowledge and experience …
- NBC(AE) 2023, 2nd printing, Div B Sentence 4.2.4.1.(3), PDF p.507 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.507. © National Research Council of Canada.
  > the geotechnical components of loads and the factored geotechnical resistances at ULS shall be determined by a suitably qualified and experienced registered professional.
- NBC(AE) 2023, 2nd printing, Div B Sentence 4.2.7.2.(2), PDF p.510 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.510. © National Research Council of Canada.
  > the determination of the number and type of load test and the interpretation of the results shall be carried out by a registered professional …
- **Engine today:** NOT covered.

### HR-15: Temporary structural members during construction (formwork, falsework, hoarding, scaffolding) "when required".

- **Verification class:** `codedb-only`. **Mandatory:** no: discretionary. Div C 2.2.14.1.(1) constructor retains a registered professional "when required"; the text does not say when, so it is a conditional/AHJ-or-contract call, not automatic.
- **Type:** strongly-indicated. **Confidence:** medium. **Human:** Registered professional retained by the constructor.
- **Case facts:** `temporary_works (NEW)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.14.1.(1), PDF p.737 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.737. © National Research Council of Canada.
  > The constructor … when required, shall retain a registered professional to design temporary structural members such as formwork, falsework, hoarding and scaffolding.
- **Notes:** "when required" is not defined in the sentence (UNSOURCED which conditions trigger it).
- **Engine today:** NOT covered.

### HR-16: Structure that is not one of the building types in Div B Articles 3.2.2.20. to 3.2.2.92. (special/unusual structures, e.g. multi-level storage racking): fire protection must follow good fire protection engineering practice.

- **Verification class:** `mixed`
- **Type:** strongly-indicated. **Confidence:** medium. **Human:** Fire protection engineer (registered engineering professional).
- **Case facts:** `special_structure (NEW)`, `storage_racking_multilevel (NEW)`
- NBC(AE) 2023, 2nd printing, Div B Sentence 3.2.2.2.(1), PDF p.175 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.175. © National Research Council of Canada.
  > A structure that cannot be identified with the characteristics of a building in Articles 3.2.2.20. to 3.2.2.92. … good fire protection engineering practice.
- STANDATA 23-BCV-014 (Mar 2025), multi-level storage racking, STANDATA 23-BCV-014, source PDF page 1 (https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/8246dd4b-20e7-4e37-b5f7-5e554accd3c5/download/ma-standata-variance-building-23-bcv-014-2025-03.pdf). Verification: source-PDF-checked, STANDATA 23-BCV-014, p.1; not codedb.
  > they be considered as special and unusual structures according to Article 3.2.2.2. and be designed according to good fire protection engineering practice. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Engine today:** NOT covered.

### HR-17: Alternative solution documentation: the person(s) taking responsibility must be identified with qualifications; if several, a single coordinator; analysis may need testing procedures or engineering studies.

- **Verification class:** `codedb-only`. **Mandatory:** no: not-professional-design. Div C 2.3.1.1.(4)/(6) must state the "qualifications, experience and background" of the responsible person and name "a single person" to co-ordinate; does not require a registered professional.
- **Type:** mandatory. **Confidence:** high. **Human:** Named responsible designer(s); single coordinator (not necessarily registered).
- **Case facts:** `professional_name`, `professional_qualifications`, `multiple_responsible_persons (NEW)`, `coordinator_name (NEW)`, `supporting_tests_or_studies (NEW)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.3.1.1.(4), PDF p.739 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.739. © National Research Council of Canada.
  > The Code analysis … shall include information about the qualifications, experience and background of the person or persons taking responsibility for the design.
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.3.1.1.(6), PDF p.739 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.739. © National Research Council of Canada.
  > the applicant for the permit shall identify a single person to co-ordinate the preparation of the design, Code analysis and documentation …
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.3.1.1.(3), PDF p.739 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.739. © National Research Council of Canada.
  > any assumptions, limiting or restricting factors, testing procedures, engineering studies or building performance parameters that will support a Code compliance assessment.
- **Notes:** 2.3.1.1 does not by itself require a registered professional; it requires a named, qualified responsible person.
- **Engine today:** Partly: completeness.py D12 gaps (professional_name/qualifications/seal) fire only when professional.required == yes; 2.3.1.1.(4) used for evidence-author gaps. Single-coordinator rule (2.3.1.1.(6)) NOT covered.


## B. Professional law (Acts/Regulations)

### HR-20: SCO opinion that size or complexity may give rise to safety concerns → SCO may require sealed plans and professional review during construction (and AHJ may require registered professionals under the code).

- **Verification class:** `mixed`
- **Type:** discretionary. **Confidence:** high. **Human:** Safety codes officer decides; then registered engineer/architect.
- **Case facts:** `special_safety_concerns`, `ahj_requires_professional`, `complexity_flags (NEW)`
- Administrative Items Regulation, AR 16/2004 (consolidation current as of Mar 15, 2021), Administrative Items Regulation s.18(1), source PDF page 10 (https://kings-printer.alberta.ca/documents/Regs/2004_016.pdf). Verification: source-PDF-checked, Administrative Items Regulation AR 16/2004, p.10; not codedb (legislation).
  > … the size or complexity of a project may give rise to safety concerns, the safety codes officer may require that all plans and specifications … — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Administrative Items Regulation, AR 16/2004 (consolidation current as of Mar 15, 2021), Administrative Items Regulation s.18(1)-(2), source PDF page 11 (https://kings-printer.alberta.ca/documents/Regs/2004_016.pdf). Verification: source-PDF-checked, Administrative Items Regulation AR 16/2004, p.11; not codedb (legislation).
  > be imprinted with a seal or stamp … be reviewed during construction in accordance with the Engineering and Geoscience Professions Act or the Architects Act. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.4.1.1.(4), PDF p.740 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.740. © National Research Council of Canada.
  > If the size or complexity of a project may give rise to special safety concerns … may require the involvement of one or more registered professionals …
- **Notes:** AR 16/2004 consolidation is "current as of March 15, 2021"; amendments after that date were not checked.
- **Engine today:** Covered: ahj_direction (yes) / special_safety (depends) cite 2.4.1.1.(4). Admin Items Reg s.18 not cited.

### HR-21: Work is the "practice of engineering" and no EGPA exception applies (exceptions include supervised work, own-property work not involving public safety, and the small-building list in s.2(7), which uses GROSS AREA per floor).

- **Verification class:** `source-pdf-only`
- **Type:** mandatory. **Confidence:** high. **Human:** Professional engineer / licensee / permit holder.
- **Case facts:** `activity_type (NEW)`, `own_property_sole_use (NEW)`, `occupancy`, `storeys`, `gross_area_per_floor_m2 (NEW)`
- Engineering and Geoscience Professions Act, RSA 2000 c E-11 (current as of Dec 7, 2023), EGPA s.2(1), source PDF page 12 (https://kings-printer.alberta.ca/documents/Acts/E11.pdf). Verification: source-PDF-checked, Engineering and Geoscience Professions Act, p.12; not codedb (legislation).
  > Except as otherwise provided in this Act, no individual, corporation, partnership or other entity … except a professional engineer … shall engage in the practice of engineering. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Engineering and Geoscience Professions Act, RSA 2000 c E-11 (current as of Dec 7, 2023), EGPA s.1(q), source PDF page 10 (https://kings-printer.alberta.ca/documents/Acts/E11.pdf). Verification: source-PDF-checked, Engineering and Geoscience Professions Act, p.10; not codedb (legislation).
  > “practice of engineering” means (i) reporting on, advising on, evaluating, designing, preparing plans and specifications for or directing … of any structure, work or process — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Engineering and Geoscience Professions Act, RSA 2000 c E-11 (current as of Dec 7, 2023), EGPA s.2(4)(e), source PDF page 13 (https://kings-printer.alberta.ca/documents/Acts/E11.pdf). Verification: source-PDF-checked, Engineering and Geoscience Professions Act, p.13; not codedb (legislation).
  > (e) a person who, on the person’s own property … carries out any work that does not involve the safety of the public; — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Engineering and Geoscience Professions Act, RSA 2000 c E-11 (current as of Dec 7, 2023), EGPA s.2(7)(a), source PDF page 14 (https://kings-printer.alberta.ca/documents/Acts/E11.pdf). Verification: source-PDF-checked, Engineering and Geoscience Professions Act, p.14; not codedb (legislation).
  > The buildings referred to in subsection (6) are the following: (a) a building, 3 storeys or less in height, for assembly occupancy or institutional occupancy … — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Notes:** EGPA s.2(7) list mirrors Div C 2.4.1.1.(1) but measures "gross area" (per floor for 2-3 storeys), not "building area", and has no secondary-suite carve-out. A case can pass the code exception yet need legal review. s.38: Council may authorize a registered architect to apply for a permit without an engineer's stamp (see HR-24).
- **Engine today:** Partly: professional_law "depends" whenever professional_scope_resolved is not True; no EGPA thresholds or gross-area check.

### HR-22: Work is the "practice of architecture" for a building not on the Architects Act s.2(6) list (same small-building list, gross area per floor).

- **Verification class:** `source-pdf-only`
- **Type:** mandatory. **Confidence:** high. **Human:** Registered architect (or other authorized entity).
- **Case facts:** `occupancy`, `storeys`, `gross_area_per_floor_m2 (NEW)`, `dwelling_units_total (NEW, incl. suites)`
- Architects Act, RSA 2000 c A-44 (current as of Nov 16, 2022), Architects Act s.2(1), source PDF page 8 (https://kings-printer.alberta.ca/documents/Acts/A44.pdf). Verification: source-PDF-checked, Architects Act, p.8; not codedb (legislation).
  > 2(1) Except as otherwise provided in this Act, no person except an authorized entity shall engage in the practice of architecture. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Architects Act, RSA 2000 c A-44 (current as of Nov 16, 2022), Architects Act s.1(l), source PDF page 7 (https://kings-printer.alberta.ca/documents/Acts/A44.pdf). Verification: source-PDF-checked, Architects Act, p.7; not codedb (legislation).
  > “practice of architecture” means (i) planning, designing or giving advice on the design of … erection, construction or alteration of or addition to a building, — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Architects Act, RSA 2000 c A-44 (current as of Nov 16, 2022), Architects Act s.2(6)(b), source PDF page 10 (https://kings-printer.alberta.ca/documents/Acts/A44.pdf). Verification: source-PDF-checked, Architects Act, p.10; not codedb (legislation).
  > … a building for residential occupancy that (i) is a single family dwelling, or (ii) is a multiple family dwelling containing 4 dwelling units or less; — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Notes:** Same gross-area vs building-area and secondary-suite caveats as HR-21. Whether the Architects regulations count secondary suites: UNSOURCED (regulations not read).
- **Engine today:** Partly: secondary_suites reason flags "independent professional-law treatment must be confirmed"; no Act thresholds.

### HR-23: Where the regulations require a stamped/sealed design, no permit may issue unless the design is signed, stamped and sealed.

- **Verification class:** `source-pdf-only`
- **Type:** mandatory. **Confidence:** high. **Human:** Engineer/architect (seal) and permit issuer (gate).
- **Case facts:** `seal_required (derived from HR-01/03/20)`, `professional_seal`
- Safety Codes Act, RSA 2000 c S-1 (consolidation current as of Dec 1, 2025), Safety Codes Act s.45(1), source PDF page 35 (https://kings-printer.alberta.ca/documents/Acts/S01.pdf). Verification: source-PDF-checked, Safety Codes Act, p.35; not codedb (legislation).
  > no permit may be issued … unless the design is submitted for review or registered and is signed, stamped and sealed in accordance with the regulations. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Safety Codes Act, RSA 2000 c S-1 (consolidation current as of Dec 1, 2025), Safety Codes Act s.11, source PDF page 14 (https://kings-printer.alberta.ca/documents/Acts/S01.pdf). Verification: source-PDF-checked, Safety Codes Act, p.14; not codedb (legislation).
  > A person permitted to affix stamps or seals … shall ensure that any professional service the person renders … complies with this Act. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Engine today:** Partly: completeness.py D12 professional_authentication gap when required == yes.

### HR-24: Architect applying without an engineer's stamp on final drawings — only if APEGA Council has authorized it.

- **Verification class:** `source-pdf-only`
- **Type:** discretionary. **Confidence:** medium. **Human:** APEGA Council (on Joint Board recommendation).
- **Case facts:** `applicant_role (NEW)`, `engineer_stamp_present (NEW)`
- Engineering and Geoscience Professions Act, RSA 2000 c E-11 (current as of Dec 7, 2023), EGPA s.38, source PDF page 42 (https://kings-printer.alberta.ca/documents/Acts/E11.pdf). Verification: source-PDF-checked, Engineering and Geoscience Professions Act, p.42; not codedb (legislation).
  > … Council may authorize … a registered architect … to apply for a permit … without the final design drawings … having the stamp or seal of a professional engineer. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Engine today:** NOT covered.


## C. Officer / Administrator discretion

### HR-30: Any variance (alternative solution) request: only an SCO or Administrator can decide it; the app must route to them and never state the variance is granted.

- **Verification class:** `source-pdf-only`
- **Type:** mandatory. **Confidence:** high. **Human:** Safety codes officer (or Administrator); SCO must notify an Administrator and register the variance.
- **Case facts:** `intake_action`, `variance_requested`
- Safety Codes Act, RSA 2000 c S-1 (consolidation current as of Dec 1, 2025), Safety Codes Act s.38(1), source PDF page 31 (https://kings-printer.alberta.ca/documents/Acts/S01.pdf). Verification: source-PDF-checked, Safety Codes Act, p.31; not codedb (legislation).
  > if the Administrator or officer is of the opinion that the variance provides approximately equivalent or greater safety performance with respect to persons and property … — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Safety Codes Act, RSA 2000 c S-1 (consolidation current as of Dec 1, 2025), Safety Codes Act s.38(3), source PDF page 31 (https://kings-printer.alberta.ca/documents/Acts/S01.pdf). Verification: source-PDF-checked, Safety Codes Act, p.31; not codedb (legislation).
  > A safety codes officer on issuing a variance shall notify an Administrator. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- SCC Information Bulletin IB-2025-11-18, IB-2025-11-18, source PDF page 2 (https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf). Verification: source-PDF-checked, SCC Information Bulletin IB-2025-11-18, p.2; not codedb.
  > Submit a copy of each variance to the Safety Codes Council within 10 days of issuance. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- SCC Information Bulletin IB-2026-10-01, IB-2026-10-01, source PDF page 3 (https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf). Verification: source-PDF-checked, SCC Information Bulletin IB-2026-10-01, p.3; not codedb.
  > Applicable professional involvement; and — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- SCC Information Bulletin IB-2026-10-16, IB-2026-10-16, source PDF page 2 (https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf). Verification: source-PDF-checked, SCC Information Bulletin IB-2026-10-16, p.2; not codedb.
  > Undue influence … would be a person directing an SCO to issue a variance based on anything other than an administratively compliant alternative solution. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Notes:** IB-2026-10-01 lists "Applicable professional involvement" as a component of the revised variance form (OVP sole method from Dec 1, 2026).
- **Engine today:** UNSOURCED in engine: no explicit SCO hand-off object; intake_action exists in evals gold schema only.

### HR-31: Province-wide variance or code interpretation (ambiguity/lack of clarity in the code) → Provincial Building Administrator.

- **Verification class:** `codedb-only`. **Mandatory:** no: discretionary. Div C 2.2.1.2.(1)/Div C 2.2.1.3.(1) a request "may be submitted" to the PBA; routing, not professional design.
- **Type:** discretionary. **Confidence:** high. **Human:** Provincial Building Administrator.
- **Case facts:** `code_ambiguity (NEW)`, `scope (site vs jurisdiction-wide)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.1.2.(1), PDF p.729 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.729. © National Research Council of Canada.
  > A written request for a variance may be submitted to the Provincial Building Administrator.
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.1.3.(1), PDF p.729 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.729. © National Research Council of Canada.
  > A written request for an interpretation may be submitted to the Provincial Building Administrator … a) specific Code references, and b) a statement identifying the ambiguity …
- **Engine today:** NOT covered (completeness.py collects "scope" only).

### HR-32: Barrier-free (Div B Section 3.8.) relaxation → Provincial Barrier-Free Administrator or PBA, not the local SCO.

- **Verification class:** `codedb-only`. **Mandatory:** no: not-professional-design. Div C 2.2.1.4.(1) only the PBFA/PBA "may grant relaxation" of Div B Section 3.8.; routing to an administrator, not professional design.
- **Type:** mandatory. **Confidence:** high. **Human:** Provincial Barrier-Free Administrator / PBA.
- **Case facts:** `provisions_varied (any 3.8.x)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.1.4.(1), PDF p.730 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.730. © National Research Council of Canada.
  > The Provincial Barrier-Free Administrator or Provincial Building Administrator may grant relaxation of one or more of the requirements of Section 3.8. of Division B
- **Notes:** Typed mandatory as a routing rule (the relaxation power sits with these Administrators); whether a local SCO may also vary Div B Section 3.8. under SCA s.38 is not settled here (UNSOURCED).
- **Engine today:** NOT covered.

### HR-33: Minor dimensional shortfall (≤ 2 %) with no reduction in life safety → AHJ may accept without a variance.

- **Verification class:** `codedb-only`. **Mandatory:** no: discretionary. Div C 2.2.2.3.(1) the AHJ "may accept a minor variation"; no professional required.
- **Type:** discretionary. **Confidence:** high. **Human:** Authority having jurisdiction (SCO).
- **Case facts:** `dimension_required`, `dimension_proposed`, `percent_deviation (derived)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.2.3.(1), PDF p.730 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.730. © National Research Council of Canada.
  > If life safety will not be reduced, the authority having jurisdiction may accept a minor variation, not more than 2%, of a dimension …
- **Engine today:** NOT covered.

### HR-34: Change of occupancy, alteration, or existing non-compliant construction → AHJ acceptance of the level of safety.

- **Verification class:** `codedb-only`. **Mandatory:** no: discretionary. Div A 1.1.1.2.(4)/(6) acceptance by the AHJ ("acceptable to", "may accept"); no professional required by the text.
- **Type:** discretionary. **Confidence:** high. **Human:** Authority having jurisdiction (SCO).
- **Case facts:** `change_of_occupancy (NEW)`, `alteration_existing (NEW)`
- NBC(AE) 2023, 2nd printing, Div A Sentence 1.1.1.2.(4), PDF p.38 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.38. © National Research Council of Canada.
  > A change in occupancy or alteration … shall be permitted if the level of safety and building performance proposed are acceptable to the authority having jurisdiction.
- NBC(AE) 2023, 2nd printing, Div A Sentence 1.1.1.2.(6), PDF p.38 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.38. © National Research Council of Canada.
  > The authority having jurisdiction may accept existing construction not in complete compliance with this Code and may place conditions on the existing construction.
- **Engine today:** NOT covered.

### HR-35: Items the code sends to the AHJ for review and acceptance: pool slides/play equipment, supplemental disinfection, water-slide special discharge, Part 10 canopy/hood airflow designs, tents/air-supported structures, temporary buildings.

- **Verification class:** `codedb-only`. **Mandatory:** no: not-professional-design. Div C 2.2.2.5.(2), Div C 2.2.11.2.(1), Div C 2.2.11.3.(2), Div B 10.6.4.2.(3): submitted to / permitted by the AHJ; AHJ acceptance, no professional named.
- **Type:** mandatory. **Confidence:** high. **Human:** Authority having jurisdiction (SCO).
- **Case facts:** `aquatic_equipment (NEW)`, `tent_or_air_supported (NEW)`, `temporary_building (NEW)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.2.5.(2), PDF p.731 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.731. © National Research Council of Canada.
  > The design of a water treatment system using ozone, ultraviolet light … shall be submitted for review and acceptance by the authority having jurisdiction.
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.11.2.(1), PDF p.735 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.735. © National Research Council of Canada.
  > A tent or air-supported structure shall not be erected unless written permission has been obtained from the authority having jurisdiction.
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.11.3.(2), PDF p.735 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.735. © National Research Council of Canada.
  > The authority having jurisdiction may permit selective compliance with this Code for a temporary building referred to in Sentence (1).
- NBC(AE) 2023, 2nd printing, Div B Sentence 10.6.4.2.(3), PDF p.1508 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.1508. © National Research Council of Canada.
  > each design shall be submitted to the authority having jurisdiction for review.
- **Engine today:** NOT covered.

### HR-36: Incorrect or insufficient information → permit issuer may refuse; may demand further information or records.

- **Verification class:** `source-pdf-only`
- **Type:** discretionary. **Confidence:** high. **Human:** Permit issuer / SCO.
- **Case facts:** `completeness gaps (engine D-codes)`
- Permit Regulation, AR 204/2007 (consolidation current as of Nov 20, 2024), Permit Regulation s.26(b), source PDF page 21 (https://kings-printer.alberta.ca/documents/Regs/2007_204.pdf). Verification: source-PDF-checked, Permit Regulation AR 204/2007, p.21; not codedb (legislation).
  > (b) incorrect or insufficient information is submitted with respect to the permit or the undertaking to be governed by the permit, — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Permit Regulation, AR 204/2007 (consolidation current as of Nov 20, 2024), Permit Regulation s.20(i), source PDF page 18 (https://kings-printer.alberta.ca/documents/Regs/2007_204.pdf). Verification: source-PDF-checked, Permit Regulation AR 204/2007, p.18; not codedb (legislation).
  > (i) include any further information that the permit issuer considers necessary — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- Safety Codes Act, RSA 2000 c S-1 (consolidation current as of Dec 1, 2025), Safety Codes Act s.35(1), source PDF page 30 (https://kings-printer.alberta.ca/documents/Acts/S01.pdf). Verification: source-PDF-checked, Safety Codes Act, p.30; not codedb (legislation).
  > any record or document pertaining in any manner to compliance with this Act — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Notes:** Supports routing incomplete cases to the SCO as "more information required" rather than auto-refusal.
- **Engine today:** Covered in spirit: completeness.py emits gaps; no explicit refusal-risk flag.


## D. Specialist testing / certification

### HR-40: Fire-resistance rating not from a listed/tabulated source → must come from CAN/ULC-S101 testing (accredited lab).

- **Verification class:** `codedb-only`. **Mandatory:** no: not-professional-design. Div B 3.1.7.1.(1) rating "determined on the basis of the results of tests" (CAN/ULC-S101); a test lab, not a professional.
- **Type:** strongly-indicated. **Confidence:** medium. **Human:** Accredited testing laboratory / certification body.
- **Case facts:** `fire_resistance_rating_source (NEW)`
- NBC(AE) 2023, 2nd printing, Div B Sentence 3.1.7.1.(1), PDF p.151 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.151. © National Research Council of Canada.
  > shall be determined on the basis of the results of tests conducted in conformance with CAN/ULC-S101
- **Notes:** Exceptions in 3.1.7.1.(2), 3.1.7.2. and 3.6.3.5. (and Part 9 Appendix-based ratings) not expanded here.
- **Engine today:** NOT covered.

### HR-41: Combustible cladding on a building required to be noncombustible → CAN/ULC-S134 full-scale test results needed.

- **Verification class:** `codedb-only`. **Mandatory:** no: not-professional-design. Div B 3.1.5.5.(1) cladding performance "when tested in accordance with CAN/ULC-S134"; a test, not a professional.
- **Type:** mandatory. **Confidence:** high. **Human:** Testing laboratory (CAN/ULC-S134).
- **Case facts:** `construction_type_required (NEW)`, `cladding_combustible (NEW)`
- NBC(AE) 2023, 2nd printing, Div B Sentence 3.1.5.5.(1), PDF p.137 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.137. © National Research Council of Canada.
  > when tested in accordance with CAN/ULC-S134, “Standard Method of Fire Test of Exterior Wall Assemblies,”
- **Engine today:** NOT covered.

### HR-42: Non-flammable medical gas piping → testing agency report accepted by AHJ before use.

- **Verification class:** `codedb-only`. **Mandatory:** no: not-professional-design. Div C 2.2.11.4.(2)/(3) a "testing agency" report accepted by the AHJ; not a professional.
- **Type:** mandatory. **Confidence:** high. **Human:** Testing agency + AHJ.
- **Case facts:** `medical_gas_piping (NEW)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.11.4.(2), PDF p.736 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.736. © National Research Council of Canada.
  > The testing agency that does the inspection and testing required by Sentence (1) shall provide a report
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.11.4.(3), PDF p.736 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.736. © National Research Council of Canada.
  > A non-flammable medical gas piping system shall not be used until the report required by Sentence (1) has been accepted by the authority having jurisdiction.
- **Engine today:** NOT covered.

### HR-43: Off-site constructed components/buildings: off-site review, CSA A277 certification, or PBA-approved certification for relocatable industrial camps; STANDATA variance route uses registered-professional verification.

- **Verification class:** `mixed`
- **Type:** mandatory. **Confidence:** high. **Human:** Certification organization / registered professionals.
- **Case facts:** `off_site_constructed (NEW)`, `csa_a277_certified (NEW)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.5.1.1.(1), PDF p.742 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.742. © National Research Council of Canada.
  > Where a component of a building is assembled off the building site … cannot be reviewed on site, off-site reviews shall be carried out …
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.5.1.1.(3), PDF p.742 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.742. © National Research Council of Canada.
  > Every relocatable industrial camp building that is constructed after 01 May 2024 shall be certified by an organization approved … by the Provincial Building Administrator
- STANDATA 23-BCV-002 (May 2024), off-site constructed buildings, STANDATA 23-BCV-002, source PDF page 2 (https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/c10bed94-08f0-41f0-93eb-90a039f89529/download/ma-standata-variance-building-23-bcv-002-2024-05.pdf). Verification: source-PDF-checked, STANDATA 23-BCV-002, p.2; not codedb.
  > Verified by registered architectural/engineering professionals in accordance with Division C, Subsections 2.4.2. and Section 2.5. of the NBC(AE). — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Engine today:** NOT covered.

### HR-44: Welded construction for Part 4 buildings → evidence of CWB certification if the AHJ requests it.

- **Verification class:** `codedb-only`. **Mandatory:** no: discretionary. Div C 2.2.2.4.(1) "If requested by the authority having jurisdiction": CWB evidence, not professional design.
- **Type:** discretionary. **Confidence:** high. **Human:** AHJ (request) / Canadian Welding Bureau.
- **Case facts:** `part4_design`, `welded_steel (NEW)`
- NBC(AE) 2023, 2nd printing, Div C Sentence 2.2.2.4.(1), PDF p.730 (https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en). Verification: codedb-checked, 2nd printing, PDF p.730. © National Research Council of Canada.
  > If requested by the authority having jurisdiction, the owner shall submit evidence … fabricators and erectors of welded construction … are certified by the Canadian Welding Bureau.
- **Engine today:** NOT covered.


## E. STANDATA variances that carry a professional condition

### HR-50: Case relies on a province-wide STANDATA variance whose conditions name a professional (examples: 23-BCV-005 risk assessment; 23-BCV-010R1 APEGA authentication).

- **Verification class:** `source-pdf-only`
- **Type:** mandatory. **Confidence:** high. **Human:** Registered engineering professional per the variance conditions.
- **Case facts:** `standata_variance_relied_on (NEW)`
- STANDATA 23-BCV-005 (May 2024), oil and gas processing buildings, STANDATA 23-BCV-005, Variance condition 2, source PDF page 2 (https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/bda7efc6-de1f-480f-b81b-1ecc8f66eea0/download/ma-standata-variance-building-23-bcv-005-2024-05.pdf). Verification: source-PDF-checked, STANDATA 23-BCV-005, p.2; not codedb.
  > A risk assessment has been prepared by a Registered Engineering Professional, licensed to practice in the province of Alberta — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- STANDATA 23-BCV-010R1 (Apr 2025), engineer's authentication for welding procedures, STANDATA 23-BCV-010R1, condition 1, source PDF page 2 (https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/e18fadda-66e8-40e2-950b-79f990724912/download/ma-23-bcv-010r1-engineers-authentication-welding-procedures.pdf). Verification: source-PDF-checked, STANDATA 23-BCV-010R1, p.2; not codedb.
  > All documentation … must be authenticated in accordance with APEGA’s authentication standards and must be submitted to the authority having jurisdiction. — © National Research Council of Canada. Source: https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499
- **Notes:** Precedent conditions; each applies only to its own subject. Also see 23-BCV-002 (HR-43), 23-BCV-012R1 (HR-10), 23-BCV-014 (HR-16).
- **Engine today:** NOT covered.

## What the repo engine covers today, and the gaps

This section was read read-only via cursor-github from `simplythatguy/batatis`, branch `dev`, on 2026-10-20. Files: `engine/professional.py` (blob `bb8b8775b3`) and `engine/completeness.py` (blob `a44bbd1e6c`). I also skimmed `research/facts/professional-involvement.md` for consistency. A GitHub code search for `escalate OR human` under `engine/` returned 0 hits; the index covers the default branch only and reported incomplete results.

**What exists**

- `professional_involvement()` gives a yes/no/depends answer with reasons and questions. The questions are the facts it is missing.
  - It covers Div C 2.4.1.1.(1)–(5), Div C 2.4.1.2.(1)–(2), Div C 2.4.1.3.(1), Div C 2.4.1.4.(1) and Div B 9.23.14.11.(2).
  - Missing facts never produce `no`. This is conservative and good.
  - The thresholds in `_AREA_LIMITS` match Div C 2.4.1.1.(1) exactly.
- `completeness.py`:
  - When `required == yes` (or `engineering_required` is yes), it emits D12 gaps for the responsible professional's name, qualifications and authentication.
  - When `required == depends`, it emits a `professional_requirement` gap containing the questions.
  - Its docstring says that "engineering adequacy and licence authenticity require human judgement". That boundary is right, but nothing in the code routes a case to a human: there is no hand-off object.

**Gaps against this table, in priority order**

1. **No explicit human-review route (HR-30).** Every variance is an SCO/Administrator decision under SCA s.38. The engine needs one output such as `human_review: [{trigger_id, who, why, cite}]` and should never imply approval. Today only gaps and questions come out.
2. **Schedules and the coordinating professional are missing (HR-02).** If `general_required == yes`, the engine should require Schedules A and B, a CRP and the RPR disciplines (2.4.2.2.(1)), and should flag C-1 before occupancy (2.4.2.4.(1)).
3. **Part 9→Part 4 triggers are not derived (HR-05/06/07).** `part4_design` is a user-supplied boolean. The thresholds are cheap to compute from facts:
   - wind ≥ 1.2 kPa, Sa(0.2) > 1.8 or > 1.2;
   - joist span > 4.9 m;
   - live load > 2.4 kPa;
   - reinforced concrete, steel studs, permafrost, slab carrying superstructure loads.
4. **Part 3/4 applicability is not linked to 2.4.1.2.(1) (HR-04).** A small Group A building can meet the 2.4.1.1.(1) size exception and still need a structural professional, because Part 4 applies.
5. **Professional-law thresholds are not checked (HR-21/22).** EGPA s.2(7) and Architects Act s.2(6) measure *gross area per floor* and do not exclude secondary suites, whereas the code uses *building area* and excludes suites. The engine collapses this into one `professional_law: depends`. Add `gross_area_per_floor_m2` and a total unit count so it can say *why* the law check is open.
6. **Other mandatory professional or testing duties are missing:**
   - aquatic facilities (2.2.9.2.(1));
   - geotechnical (4.2.2.1.(1), 4.2.4.1.(3), 4.2.7.2.(2));
   - Part 10 sprinklers (10.4.7.2.(1)). The engine currently treats relocatable camps as a plain `no`;
   - guards and structural components (2.2.4.4.(1));
   - medical gas (2.2.11.4);
   - CAN/ULC-S134 / S101 testing (HR-40/41);
   - off-site certification (2.5.1.1);
   - special structures (3.2.2.2.(1));
   - "good engineering practice" routes (HR-09, via 23-BCI-015R1).
7. **Routing to someone other than the local SCO is missing:**
   - barrier-free 3.8 relaxations go to the PBFA/PBA (2.2.1.4.(1));
   - province-wide variances and interpretations go to the PBA (2.2.1.2/2.2.1.3);
   - the ≤2 % dimensional tolerance (2.2.2.3.(1)) and change-of-occupancy acceptance (Div A 1.1.1.2.(4)/(6)) are AHJ decisions.
8. **Citation gaps:** the engine does not cite the Administrative Items Regulation s.18 (SCO may require seals or field review for size or complexity) or SCA s.45(1) (no permit without required seals). The engine cites only 2.4.1.1.(4).
9. **Single-coordinator rule is missing:** Div C 2.3.1.1.(6) requires one coordinator when several people take design responsibility.

**Possible over-trigger to review:** `roof_trusses is True` returns `yes`. That matches 23-BCI-015R1. However, `roof_trusses is None` adds a `depends` reason to every case, so `required` can be `depends` for cases with no structure at all, such as a pure exit-signage variance. Consider making the truss, PWF and suppression questions conditional on scope.

## Feature spec

This section is a product feature spec, not a judging criterion. The challenge brief's rubric (challenge PDF section 3, "Judging Criteria and Weighting", PDF p.4) has nine criteria, named exactly: 1 Intake (20%), 2 Code Identification (20%), 3 Recommendations (10%), 4 Review (10%), 5 General Applicability (5%), 6 Implementation Plan (10%), 7 Business Plan (10%), 8 Usability and Portability (10%), 9 The X Factor (5%). None of them is a separate "human review" criterion. Each point below maps to the criterion it supports, quoting that criterion's own wording.

| # | Feature | Supports criterion (exact name, PDF p.4) | Triggers |
|---|---|---|---|
| 1 | Every variance case is routed to the safety codes officer, or to an Administrator where applicable. The app never states or implies that a variance is granted. | **Recommendations** ("knowing where to stop rather than generating professional judgment itself") | HR-30, HR-31, HR-32 |
| 2 | Mandatory professional-involvement triggers are detected from case facts, and unknown facts become questions rather than a "no". | **Intake** ("prompt for what's missing or incomplete, and signal its own confidence rather than filling boxes regardless") | HR-01 to HR-14, HR-17, HR-21 to HR-23 |
| 3 | Discretionary triggers are surfaced to the officer as points to decide, not decided by the app. | **Review** ("Does the reviewer-facing view actually save an SCO time") | HR-20, HR-33 to HR-37, HR-44 |
| 4 | The responsible person is named: discipline, PBA/PBFA, testing laboratory or certification body. | **Recommendations** ("correctly flag where engineering or another licensed professional is required") | all; see the Human column |
| 5 | Each flag carries a plain-language reason and a pinpoint citation that resolves in codedb (NBC(AE) 2023, 2nd printing), so the reason is traceable to the code text. | **Code Identification** ("do all citations resolve to real articles in the correct edition"); traceable citations | all |

## UNSOURCED / not verified

- The conditions under which 2.2.14.1.(1) "when required" applies to temporary works.
- Whether a local SCO may vary Section 3.8 under SCA s.38, as opposed to the PBFA/PBA relaxation route.
- Whether the Architects or Engineering regulations treat secondary suites differently from the Acts. I did not read the regulations.
- Amendments to AR 16/2004 after its Mar 15, 2021 consolidation.
- Building Code Regulation AR 5/2024 adopts NBC(AE) 2023 (s.1) and has no professional-involvement provisions (s.1–6 read; the King's Printer copy is an "Extract").
- Permit Regulation AR 204/2007 contains no professional, seal, stamp, architect or engineer wording. Its levers are s.20 (application contents, "further information") and s.26 (refusal).
- "Tables 2.4.2.1.A/B" do not exist in the 2nd printing. The equivalents are Schedules A, B, C-1, C-2 and C-3.

## Citation check

`python -m codedb validate human-review-triggers.md` (public variant): 0 errors, 2 warnings (unbound source-PDF pages for non-code documents). Internal-only appeal quotes are not included in this variant.

All remaining quotes were string-checked: code quotes against codedb, and everything else against pdftotext of the source PDF.

