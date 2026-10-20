# Carlos S1 backing: variance vs redesign, sprinkler "exempt", fact-extraction regression cases

**Label: model-checked, not human-verified.** Generated 2026-10-20 (America/Edmonton, MDT UTC-6) by Data Nerd. Public sources only. Codedb: NBC(AE) 2023 2nd printing, sha256 `65e650407516…`. Builder: `research/src/carlos_s1_build.py` (every quote is string-matched against codedb or pdftotext; the build fails on a mismatch). Report: `/workspace/unc-reports/session3-carlos-gc.md (S1 issues 1-3 at lines 8-10)`.

## 1. Variance vs redesign: decision rule

**App answer:** Two routes; the officer decides. (1) Replace or repair with a tested, listed firestop system for the actual pipe and gap — the code's acceptable-solution route (Div A 1.2.1.1.(1)(a)); the inspector or safety codes officer confirms it. (2) If no tested system fits, propose an alternative solution with the documents in Div C 2.3.1.1 and request a variance; the safety codes officer decides (SCA s.38(1)), and installed work stays at risk until then. Batatis can't tell you either route will be accepted.

*Wording: Karen review, /workspace/karen/pr-reviews.md "Carlos S1 backing" (Oct 20, 2026 ~2:31 PM MDT), verbatim.*

- Step 1 (route 1): Show the Division B acceptable solution that governs the item. For Carlos that is a tested, listed CAN/ULC-S115 firestop system for the actual pipe and gap. Replacing or repairing to it is the acceptable-solution route (Div A 1.2.1.1.(1)(a)). The inspector or safety codes officer confirms it; the app never states that the work complies.
- Step 2: Only where the acceptable solution cannot be met (no tested system fits the field condition) is an alternative solution the route, under Div A 1.2.1.1.(1)(b). It must reach at least the performance required "in the areas defined by the objectives and functional statements attributed to the applicable acceptable solutions".
- Step 3: The attributed objectives and functions are the ones the code lists for that sentence (Div A 1.2.1.1.(2), Div B 1.1.2.1.(1), and for Part 3 Table 3.10.1.1 via Div B 3.10.1.1.(1)). The app looks them up and never invents them. Where codedb attribution_status is "none" (for example Div B 3.1.9.4.(4)), the app shows "lookup not available".
- Step 4: The applicant provides the documentation in Div C 2.3.1.1: a code analysis showing at least the required performance, plus any maintenance or operational requirements.
- Step 5: A safety codes officer may issue a variance only if, in the officer's opinion, it gives "approximately equivalent or greater safety performance" (Safety Codes Act s.38(1)). A refusal is served in writing and can be appealed to the Council within 30 days (s.38(6)-(7)). The app never says a variance will be granted, and never says installed work can be kept.
- Step 6 (Carlos S1 issue 1): for an "EJ", the app lists evidence and does not judge it. The IFC EJ guidelines (industry guidance, not code) say EJs are not used in lieu of available tested systems, are issued only by the manufacturer's qualified technical personnel or a knowledgeable registered PE/FPE or listing agency, and carry the authorization signature, the tested system relied on, and the job name and location. The app marks the email evidence_listed (not reviewed), lists which of these items it cannot find, and routes: ask for an EJ from a qualified issuer; the officer decides acceptance.

**Citations (verbatim):**

- Div A 1.2.1.1.(1) (PDF p.38): "Compliance with this Code shall be achieved by a) complying with the applicable acceptable solutions in Division B". *(compliance option (a): acceptable solutions)*
- Div A 1.2.1.1.(1) (PDF p.38): "b) using alternative solutions that will achieve at least the minimum level of performance required by Division B … attributed to the applicable acceptable solutions". *(compliance option (b): alternative solutions)*
- Div A 1.2.1.1.(2) (PDF p.38): "the objectives and functional statements attributed to the acceptable solutions in Division B shall be … referred to in Subsection 1.1.2. of Division B". *(which objectives/functions count)*
- Div A 2.1.1.2.(1) (PDF p.67): "only to the extent that they relate to compliance with this Code as required in Article 1.2.1.1.". *(objectives (Div A Part 2) apply only via Div A 1.2.1.1)*
- Div A 2.2.1.1.(1) (PDF p.68): "OS1 Fire Safety An objective of this Code is to limit the probability that". *(objective OS1 (fire safety))*
- Div A 3.2.1.1.(1) (PDF p.79): "F03 To retard the effects of fire on areas beyond its point of origin.". *(functional statement F03 (Div A Part 3))*
- Div A 3.2.1.1.(1) (PDF p.79): "F04 To retard failure or collapse due to the effects of fire.". *(functional statement F04)*
- Div B 1.1.2.1.(1) (PDF p.89): "… acceptable solutions in Division B shall be the objectives and functional statements identified in Sections 3.10., 4.5., 5.10., 6.10., 7.3., 8.3., 9.38., 10.8. and 11.3.". *(attribution (Div B 1.1.2))*
- Div B 3.10.1.1.(1) (PDF p.321): "shall be the objectives and functional statements listed in Table 3.10.1.1.". *(Part 3 attribution table)*
- Div C 2.3.1.1.(1) (PDF p.739): "Documentation … shall be provided by the person requesting the use of an alternative solution to demonstrate that the proposed alternative solution complies with this Code.". *(documentation duty)*
- Div C 2.3.1.1.(2) (PDF p.739): "a Code analysis … rationales … that a proposed alternative solution will achieve at least the level of performance required by Clause 1.2.1.1.(1)(b) of Division A". *(required code analysis)*
- Safety Codes Act, RSA 2000, c S-1 (King's Printer, current as of December 1, 2025) (https://kings-printer.alberta.ca/documents/Acts/S01.pdf), page 31 of the PDF: "An Administrator or a safety codes officer may issue a written variance … of the opinion that the variance provides approximately equivalent or greater safety performance". *(SCA s.38(1) variance basis)*
- Safety Codes Act, RSA 2000, c S-1 (King's Printer, current as of December 1, 2025) (https://kings-printer.alberta.ca/documents/Acts/S01.pdf), page 32 of the PDF: "An applicant who receives a notice referred to in subsection (6) may, within 30 days … appeal the refusal to the Council". *(SCA s.38(7) appeal of refusal)*
- International Firestop Council, IFC EJ Guidelines (Rev. Feb 2024) - industry guidance, not code (https://firestop.org/wp-content/uploads/2024/03/Guidelines_Firestop_Engineering_Judgments_Rev2024-02.pdf), page 2 of the PDF: "Not be used in lieu of tested systems when available". *(IFC EJ guideline 1)*
- International Firestop Council, IFC EJ Guidelines (Rev. Feb 2024) - industry guidance, not code (https://firestop.org/wp-content/uploads/2024/03/Guidelines_Firestop_Engineering_Judgments_Rev2024-02.pdf), page 2 of the PDF: "… issued only by a firestop manufacturer’s qualified technical personnel or in concert with the manufacturer … registered Professional Engineer … or an independent testing agency". *(IFC EJ guideline 2 (who may issue))*
- International Firestop Council, IFC EJ Guidelines (Rev. Feb 2024) - industry guidance, not code (https://firestop.org/wp-content/uploads/2024/03/Guidelines_Firestop_Engineering_Judgments_Rev2024-02.pdf), page 3 of the PDF: "Include dates of issue and authorization signature as well as the issuer’s name, address and telephone number". *(IFC EJ content item)*
- International Firestop Council, IFC EJ Guidelines (Rev. Feb 2024) - industry guidance, not code (https://firestop.org/wp-content/uploads/2024/03/Guidelines_Firestop_Engineering_Judgments_Rev2024-02.pdf), page 3 of the PDF: "Reference tested system(s) upon which design (EJ or TE) is based on". *(IFC EJ content item)*
- International Firestop Council, IFC EJ Guidelines (Rev. Feb 2024) - industry guidance, not code (https://firestop.org/wp-content/uploads/2024/03/Guidelines_Firestop_Engineering_Judgments_Rev2024-02.pdf), page 3 of the PDF: "Identify the job name, project location and firm EJ (TE) is issued to". *(IFC EJ content item)*

**Attribution lookups (Carlos case):**

- Div B 3.1.9.1.(1) [F03-OS1.2] [F04-OS1.3] [F03-OP1.2] [F04-OP1.3] (from Table 3.10.1.1., PDF p.323); attribution_status `direct`
- Div B 3.1.9.1.(4) ; attribution_status `none`; no rows, so show "lookup not available"
- Div B 3.1.9.4.(4) ; attribution_status `none`; no rows, so show "lookup not available"

**Case B evidence:**

- `evals/demo-cases/b-contractor-firestop-nonconformance/input/manufacturer-ej-draft-EXAMPLE.md @ simplythatguy/batatis@914b8ec` line 6: `"Hi Carlos, FireSeal 200 performs great on plastic pipe too, we've seen it in lots of jobs. Treat this as our engineering judgment that it'll hold the rating. Thanks!"`
- `evals/demo-cases/b-contractor-firestop-nonconformance/input/architect-email-EXAMPLE.md @ simplythatguy/batatis@914b8ec` line 4: `we can't accept the rep's email as an EJ`
- `evals/demo-cases/b-contractor-firestop-nonconformance/input/ncr-firestop-EXAMPLE.md @ simplythatguy/batatis@914b8ec` line 15: `Recommendation: "Replace with listed systems for plastic pipe, or obtain an engineering judgment acceptable to the AHJ."`

## 2. The sprinkler 'exempt' claim

Report: `/workspace/unc-reports/session3-carlos-gc.md` line 9: `2. The sprinkler "exempt" claim isn't challenged; 3.1.9.4.(1) and 9.10.9.9.(3) show in search but aren't connected to the claim or to the sealant around the sprinkler pipes. (Backy)`

- `evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.md @ simplythatguy/batatis@914b8ec` line 20: `The sprinkler fitter used the same sealant around the sprinkler branch lines. The sub says sprinklers are "exempt".`
- `evals/demo-cases/b-contractor-firestop-nonconformance/input/ncr-firestop-EXAMPLE.md @ simplythatguy/batatis@914b8ec` line 13: `| L3–L4 | Sprinkler branch lines (steel) | 22 | Rated floor | Same sealant | **Not assessed:** inspector asks the design team to confirm treatment |`

**Scope note.** In case B, the "exempt" claim is about firestopping the sprinkler PIPE penetrations (Div B 3.1.9.1.(4)), not about whether the building needs sprinklers. The brief says the building is sprinklered. Both questions are covered: (A) does the building need sprinklers, and (B) is the sprinkler penetration exempt from firestopping.

### 2A. Does the building need sprinklers? Decision table

| condition | result | next |
|---|---|---|
| Group A, B or F1, or a post-disaster building, or Group C/D/E/F2/F3 over 3 storeys or over 600 m² | Part 3 applies (Div A 1.3.3.2.(1)) | Part 3 size Articles Div B 3.2.2.20-3.2.2.92 |
| Group B4/C/D/E/F2/F3, 3 storeys or less, and 600 m² or less | Part 9 applies (Div A 1.3.3.3.(1)) | No general Part 9 sprinkler mandate was found in a codedb sentence search except home-type care (Div B 9.10.2.2.(2)). If sprinklers are installed: Div B 9.10.1.3.(8). (model reading) |
| Part 3, Group C, 5 storeys (Carlos) | The Group C Articles that allow 5 storeys are Div B 3.2.2.47, Div B 3.2.2.48 (≤12 storeys, ≤42 m, ≤6 000 m²), Div B 3.2.2.49 (noncombustible, ≤7 200 m² at 5 storeys) and Div B 3.2.2.51 (≤6 storeys, ≤18 m, ≤1 800 m² at 5 storeys). All are listed in Div B 3.2.2.18.(1), so the building is required to be sprinklered if it falls under one of these Articles (officer confirms); the brief states it is sprinklered (applicant-stated). Div B 3.2.2.52 (≤4 storeys) and Div B 3.2.2.55 (≤3) do not cover 5 storeys. | Need building area and height (m) to pick the Article. |
| Retail (Group E) at grade under Group C | Allowed within Div B 3.2.2.48 or Div B 3.2.2.51 if the Group E occupancy is below the third storey (Div B 3.2.2.48.(4)(b), Div B 3.2.2.51.(5)(a)). Otherwise use Div B 3.2.2.6 or Div B 3.2.2.7. Div B 3.2.2.8 applies if the retail is ≤10% of the storey floor area. | Need the retail floor area and storey. |
| Any storey required to be sprinklered | All lower storeys are sprinklered too (Div B 3.2.2.18.(2)) | — |
| Sprinkler standard | NFPA 13 by default (Div B 3.2.5.12.(1)); NFPA 13R is limited to a residential-occupancy-throughout building of ≤4 storeys under the listed Articles (Div B 3.2.5.12.(2)(a)(i)). The app shows these limits; the officer confirms which standard applies. | Ask for the sprinkler design standard. |

### 2B. Sprinkler penetration 'exempt' claim: what the app does

The app never rules on the exemption; each row asks for evidence or opens an officer gap.

| item | provisions | App action |
|---|---|---|
| Sprinkler (head) through a fire separation or membrane, with a metal escutcheon plate per NFPA 13 | Firestop requirements of Div B 3.1.9.1.(1)-(3) do not apply (Div B 3.1.9.1.(4); Part 9: Div B 9.10.9.9.(4)) | ask for escutcheon evidence → officer gap "exemption claimed under 3.1.9.1.(4), evidence needed" |
| Steel sprinkler branch line through a rated floor (case B: 22 lines, NCR L13) | Service penetration: firestop conforming to Div B 3.1.9.1.(1) (CAN/ULC-S115 F rating ≥ the required rating) or cast-in-place for steel (Div B 3.1.9.2.(1), Div B 3.1.9.1.(1)(b)) | needs-evidence question: which listed system or provision covers this penetration? → officer gap "applicant claim not supported by a citation" |
| Combustible (e.g. CPVC) sprinkler piping | Permitted to penetrate a fire separation if the fire compartments on both sides are sprinklered (Div B 3.1.9.4.(1); Part 9: Div B 9.10.9.9.(3)). The sentence does not itself say the firestop is waived, so the app should not infer that (model reading). | needs-evidence question: which listed system or provision covers this penetration? → officer gap "applicant claim not supported by a citation" |
| Same sealant as the failed DWV/PEX penetrations, listing covers metallic pipe only | The NCR marks the sprinkler lines "Not assessed"; the listing must cover the actual penetrant and annular space | needs-evidence question: which listed system or provision covers this penetration? → officer gap "applicant claim not supported by a citation" |

### Evidence the app must have before it accepts 'exempt'

| field | ask | basis |
|---|---|---|
| `major_occupancies` | Major occupancy of each part, with its storey (Table 3.1.2.1 Group/Division) | Div B 3.1.2.1.(1); Div B 3.2.2.6-3.2.2.8 |
| `building_area_m2` | Building area (greatest horizontal area above grade, to the outside of exterior walls / centre line of firewalls) | Div A 1.4.1.2.(1) "Building area"; Div A 1.3.3.2/Div A 1.3.3.3; Div B 3.2.2.x |
| `building_height_storeys` | Building height in storeys (per the Div A definition, counted from the floor of the first storey to the roof) | Div A 1.4.1.2.(1) "Building height", "First storey"; Div B 3.2.2.x; Div B 3.2.1.1.(1) rooftop enclosures not counted |
| `height_m` | Height from the floor of the first storey to the uppermost floor level (excluding rooftop enclosures) | Div B 3.2.2.48.(1)(c), Div B 3.2.2.51.(1)(c) |
| `construction_type` | Combustible / noncombustible / encapsulated mass timber | Div B 3.2.2.49 vs Div B 3.2.2.51 (titles and (2)) |
| `dwelling_units_and_suites` | Number of dwelling units / suites and where they are | Div B 3.2.5.12.(2)-(3) (13R/13D eligibility); case brief "64 dwelling units" |
| `retail_area_m2` | Group E floor area per storey, and its storey | Div B 3.2.2.8.(1); Div B 3.2.2.48.(4); Div B 3.2.2.51.(5) |
| `firewalls` | Are any firewalls subdividing the building? (They change the building area.) | Div A 1.4.1.2.(1) "Building area", "Firewall" |
| `sprinkler_standard_and_extent` | NFPA 13 / 13R / 13D, and is it installed throughout (all storeys)? | Div B 3.2.2.18.(1)-(2); Div B 3.2.5.12.(1)-(3) |
| `penetrant_type` | At each sprinkler penetration: sprinkler head with a metal escutcheon per NFPA 13, or branch-line pipe? Pipe material (steel, CPVC)? | Div B 3.1.9.1.(4); Div B 3.1.9.2.(1); Div B 3.1.9.4.(1) |
| `compartments_both_sides_sprinklered` | Are the fire compartments on both sides sprinklered? (Needed for combustible sprinkler piping.) | Div B 3.1.9.4.(1) |
| `fire_separation_rating` | Required fire-resistance rating of the separation (from the architect's code analysis, as project data) | Div B 3.1.9.1.(1); case brief L15 ("1 h") |
| `firestop_listing` | Listed CAN/ULC-S115 system number for that penetrant and annular space | Div B 3.1.9.1.(1)(a) |

### Alberta-specific

Alberta-specific (historical context, previous Alberta Edition): the SCC NBC(AE) 2023 Part 3 update document says that the two Alberta-specific Sentences, (3) and (4), of the "Automatic Sprinkler System Required" Article were deleted and the Article was harmonized with the NBC. A text search of that document found no other Alberta-specific sprinkler-requirement change. Its numbering notes (for example Div B 3.2.2.50 "Reserved") were not interpreted. Not checked: a search snippet (SCC Summit 2023 slides) about NFPA 13D being extended to row houses; it is not used here.


**Part 9 vs Part 3 scope, classification:**

- Div A 1.3.3.2.(1) (PDF p.39): "c) exceeding 600 m² in building area or exceeding 3 storeys in building height used for major occupancies classified as i) Group C, residential occupancies" *(Part 3 scope)*
- Div A 1.3.3.3.(1) (PDF p.40): "applies to all buildings described in Article 1.1.1.1. of 3 storeys or less in building height, having a building area not exceeding 600 m²" *(Part 9 scope (the Sentence opens "Part 9 of Division B"))*
- Div B 3.1.2.1.(1) (PDF p.129): "every building or part thereof shall be classified according to its major occupancy as belonging to one of the Groups or Divisions … Table 3.1.2.1." *(occupancy classification)*

**Definitions (Div A 1.4.1.2.(1)):**

- Div A 1.4.1.2.(1) (PDF p.43): "Building area means the greatest horizontal area of a building above grade within the outside surface of exterior walls … and the centre line of firewalls." *(term located on PDF p.43 by string-match against the code text (definitions list, Sentence Div A 1.4.1.2.(1), PDF p.42-53))*
- Div A 1.4.1.2.(1) (PDF p.43): "Building height (in storeys) means the number of storeys contained between the roof and the floor of the first storey." *(term located on PDF p.43 by string-match against the code text (definitions list, Sentence Div A 1.4.1.2.(1), PDF p.42-53))*
- Div A 1.4.1.2.(1) (PDF p.45): "Firewall means a type of fire separation of noncombustible construction that subdivides a building … structural stability to remain intact under fire conditions" *(term located on PDF p.45 by string-match against the code text (definitions list, Sentence Div A 1.4.1.2.(1), PDF p.42-53))*
- Div A 1.4.1.2.(1) (PDF p.45): "First storey means the uppermost storey having its floor level not more than 2 m above grade." *(term located on PDF p.45 by string-match against the code text (definitions list, Sentence Div A 1.4.1.2.(1), PDF p.42-53))*
- Div A 1.4.1.2.(1) (PDF p.51): "Sprinklered (as applying to a building or part thereof) means that the building or part thereof is equipped with a system of automatic sprinklers." *(term located on PDF p.51 by string-match against the code text (definitions list, Sentence Div A 1.4.1.2.(1), PDF p.42-53))*

**Part 3 building size and sprinkler Articles:**

- Div B 3.2.2.5.(1) (PDF p.176): "the building height and building area of the entire building shall be used" *(whole-building height/area)*
- Div B 3.2.2.6.(1) (PDF p.176): "the requirements of this Subsection for the most restricted major occupancy contained shall apply to the whole building" *(multiple occupancies)*
- Div B 3.2.2.7.(1) (PDF p.176): "… one major occupancy is located entirely above another major occupancy … shall apply to that portion as if the entire building were of that major occupancy" *(superimposed occupancies (retail below residential))*
- Div B 3.2.2.8.(1) (PDF p.176): "these major occupancies need not be considered as major occupancies for the purposes of this Subsection" *(10% exception)*
- Div B 3.2.2.18.(1) (PDF p.178): "an automatic sprinkler system conforming to the requirements of Articles … shall be installed throughout a building regulated by one or more of Articles" *(sprinklers required for listed Articles (includes Div B 3.2.2.47.-3.2.2.49., Div B 3.2.2.51., Div B 3.2.2.52., Div B 3.2.2.55., Div B 3.2.2.66., Div B 3.2.2.67., Div B 3.2.2.69.))*
- Div B 3.2.2.18.(2) (PDF p.179): "the automatic sprinkler system shall also be installed throughout all lower storeys in the building" *(lower storeys)*
- Div B 3.2.2.47.(1) (PDF p.187): "Except as permitted by Articles 3.2.2.48. to 3.2.2.55., a building classified as Group C shall conform to Sentence (2)." *(Group C any height/area, sprinklered)*
- Div B 3.2.2.48.(1) (PDF p.188): "it is not more than 12 storeys in building height, c) it has a height not more than 42 m" *(Group C up to 12 storeys, sprinklered)*
- Div B 3.2.2.48.(4) (PDF p.188): "b) the Group E major occupancy is located below the third storey" *(Group E inside a Div B 3.2.2.48 building)*
- Div B 3.2.2.49.(1) (PDF p.188): "iv) not more than 7 200 m² if 5 storeys in building height" *(Group C up to 6 storeys, noncombustible, sprinklered)*
- Div B 3.2.2.51.(1) (PDF p.189): "b) it is not more than 6 storeys in building height, c) it has a height not more than 18 m" *(Group C up to 6 storeys, sprinklered)*
- Div B 3.2.2.51.(1) (PDF p.189): "v) 1 800 m² if 5 storeys in building height" *(Div B 3.2.2.51 area at 5 storeys)*
- Div B 3.2.2.51.(5) (PDF p.189): "a) the Group A, Division 2 major occupancy and Group E major occupancy are located below the third storey" *(Group E inside a Div B 3.2.2.51 building)*
- Div B 3.2.2.52.(1) (PDF p.189): "b) it is not more than 4 storeys in building height" *(Group C up to 4 storeys: excludes 5 storeys)*
- Div B 3.2.2.55.(1) (PDF p.190): "b) it is not more than 3 storeys in building height" *(Group C up to 3 storeys: excludes 5 storeys)*
- Div B 3.2.2.67.(1) (PDF p.195): "b) it is not more than 4 storeys in building height, and c) it has a building area not more than 1 800 m²" *(Group E up to 4 storeys)*
- Div B 3.2.5.12.(1) (PDF p.233): "an automatic sprinkler system shall be designed, constructed, installed and tested in conformance with NFPA 13" *(sprinkler standard)*
- Div B 3.2.5.12.(2) (PDF p.233): "i) is not more than 4 storeys in building height and conforms to Article 3.2.2.47., 3.2.2.49., 3.2.2.51., 3.2.2.52. or 3.2.2.55." *(NFPA 13R limits)*

**Part 9:**

- Div B 9.10.1.3.(8) (PDF p.876): "Sprinkler systems shall be designed, constructed and installed in conformance with Articles 3.2.5.12. to 3.2.5.15. and 3.2.5.17." *(Part 9 sprinkler design)*
- Div B 9.10.2.2.(2) (PDF p.877): "be i) sprinklered in conformance with NFPA 13D" *(Part 9 sprinkler mandate found: home-type care)*
- Div B 9.10.9.9.(3) (PDF p.885): "Sprinkler piping is permitted to penetrate a fire separation, provided the fire compartments on each side of the fire separation are sprinklered." *(Part 9 sprinkler piping penetration)*
- Div B 9.10.9.9.(4) (PDF p.885): "provided the annular space created by the penetration of a fire sprinkler is covered by a metal escutcheon plate in accordance with NFPA 13" *(Part 9 sprinkler escutcheon exception)*

**Penetrations:**

- Div B 3.1.9.1.(1) (PDF p.159): "sealed by a firestop that … CAN/ULC-S115 … has an F rating not less than the required fire-resistance rating of the fire separation … b) cast in place" *(general firestop rule)*
- Div B 3.1.9.1.(4) (PDF p.159): "Sprinklers are permitted to penetrate … without having to meet the firestop requirements … provided … covered by a metal escutcheon plate in accordance with NFPA 13" *(the only sprinkler "exemption" (sprinklers, with escutcheon))*
- Div B 3.1.9.2.(1) (PDF p.159): "pipes, totally enclosed raceways" *(service penetrations)*
- Div B 3.1.9.2.(1) (PDF p.159): "provided they are protected at the penetration with a firestop conforming to Sentence 3.1.9.1.(1)" *(service penetrations need a Div B 3.1.9.1.(1) firestop)*
- Div B 3.1.9.4.(1) (PDF p.160): "Combustible sprinkler piping is permitted to penetrate a fire separation provided the fire compartments on each side of the fire separation are sprinklered." *(combustible sprinkler piping)*
- Div B 3.1.9.4.(4)(b) (PDF p.160): "in buildings more than 3 storeys in building height, the piping is sealed at the penetration by a firestop" *(DWV in >3 storeys)*
- Div B 3.1.9.4.(4)(b) (PDF p.160): "with a pressure differential of 50 Pa between the exposed and unexposed sides" *(50 Pa)*

**Alberta-specific:**

- Safety Codes Council, "National Building Code - 2023 Alberta Edition, Part 3 - Code update information" (https://ebs.safetycodes.ab.ca/documents/webdocs/PI/National%20Building%20Code%20-%202023%20Alberta%20Edition_Part%203.pdf), page 12 of the PDF: "AB specific Sentences (3) and (4) deleted; harmonized with NBC." *(historical context: entry for the "Automatic Sprinkler System Required" Article, previous Alberta Edition to 2023; the Alberta-specific sprinkler sentences were removed)*

## 3. Fact-extraction regression cases (Carlos style)

### cfx-001: Project table paste (owner, address, legal, permit)
Source: `evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.md @ simplythatguy/batatis@914b8ec` lines 8-15. session3 L3: "Pasted owner, address, legal description and permit were not read". *model-checked, not human-verified*

```text
| Name | Example Commons *(fictional)* |
| Address | 0000 Example Avenue SW, Calgary, AB *(fictional)* |
| Legal | Lot 0, Block 0, Plan 0000000 *(fictional placeholder)* |
| Owner | Example Commons Holdings Inc. *(fictional)* |
| Building permit | BP-0000-00000 *(fictional)*, issued |
| Building | 5 storeys, sprinklered, retail at grade, 64 dwelling units above |
| Design team | Example Architecture Inc. *(fictional)*, coordinating registered professional; Example MEP Engineering *(fictional)* |
| Floor assemblies | Rated fire separations. *Rating per the architect's code analysis: "1 h"* |
```

Expected fields:
```json
{
 "project_name": "Example Commons",
 "address": "0000 Example Avenue SW, Calgary, AB",
 "legal_description": "Lot 0, Block 0, Plan 0000000",
 "owner": "Example Commons Holdings Inc.",
 "building_permit": {
  "number": "BP-0000-00000",
  "status": "issued"
 },
 "storeys": 5,
 "sprinklered": {
  "value": true,
  "status": "applicant-stated"
 },
 "uses": "retail at grade, 64 dwelling units above",
 "dwelling_units": 64,
 "design_team": [
  "Example Architecture Inc. (coordinating registered professional)",
  "Example MEP Engineering"
 ],
 "floor_fire_separation_rating": {
  "value": "1 h",
  "status": "project data, per the architect's code analysis; not derived"
 },
 "jurisdiction": {
  "value": "Calgary",
  "status": "proposed (from address)"
 }
}
```
Must not: put the paste into "Proposed alternative"; re-ask owner, address, legal description or permit; derive the 1 h rating or an occupancy Group as a confirmed fact.
Still missing (ask): building_area_m2, height_m, major_occupancies (Group C + Group E to be confirmed), construction_type, firewalls.

### cfx-002: What happened (sealant, listing, penetrants)
Source: `evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.md @ simplythatguy/batatis@914b8ec` lines 18, 20. *model-checked, not human-verified*

```text
Our firestop sub sealed the plumbing penetrations on L3 and L4 with **Example FireSeal 200** *(fictional)* and handed in listing **EX-FS-1234** *(fictional)*. The third-party firestop inspector says that listing only covers **metal pipes**. Ours are mostly **PVC drain pipe and bundles of PEX**, and some holes are bigger than the listing allows. L2 (copper) passed.

The sprinkler fitter used the same sealant around the sprinkler branch lines. The sub says sprinklers are "exempt".
```

Expected fields:
```json
{
 "levels": [
  "L3",
  "L4"
 ],
 "sealant": "Example FireSeal 200",
 "listing": "EX-FS-1234",
 "listing_scope": "metal pipes only (per third-party inspector)",
 "penetrants": [
  "PVC drain pipe",
  "PEX bundles"
 ],
 "annular_space_issue": "some holes bigger than the listing allows",
 "passed": {
  "level": "L2",
  "penetrant": "copper"
 },
 "sprinkler_branch_lines": {
  "sealed_with": "same sealant"
 },
 "claims": [
  {
   "text": "sprinklers are \"exempt\"",
   "by": "firestop sub",
   "status": "unverified claim; check against 3.1.9.1.(4)"
  }
 ]
}
```
Must not: record "sprinklers exempt" as a fact; treat the listing as covering plastic pipe.

### cfx-003: What we need (schedule, desired outcome, evidence)
Source: `evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.md @ simplythatguy/batatis@914b8ec` lines 22-25. *model-checked, not human-verified*

```text
## What we need
- Keep the **drywall close-in on 2026-10-24**
- Ideally "a variance so we don't have to rip it out"
- We have a **draft EJ email** from the sealant rep
```

Expected fields:
```json
{
 "close_in_date": "2026-10-24",
 "desired_outcome": "\"a variance so we don't have to rip it out\" (applicant wish, not a route decision)",
 "evidence_offered": [
  {
   "type": "email",
   "from_": "sealant rep",
   "described_as": "draft EJ",
   "status": "not yet assessed"
  }
 ]
}
```
Must not: promise a variance; classify the rep email as an engineering judgment.

### cfx-004: Sales-rep "EJ" email
Source: `evals/demo-cases/b-contractor-firestop-nonconformance/input/manufacturer-ej-draft-EXAMPLE.md @ simplythatguy/batatis@914b8ec` lines 4-6. *model-checked, not human-verified*

Note: repo file ends at line 6; missing items are derived from what the email does not contain.

```text
From: sales rep, Example Sealants Co. *(fictional)*. Sent 2026-10-15 4:52 pm.

"Hi Carlos, FireSeal 200 performs great on plastic pipe too, we've seen it in lots of jobs. Treat this as our engineering judgment that it'll hold the rating. Thanks!"
```

Expected fields:
```json
{
 "issuer_role": "sales rep",
 "issuer_company": "Example Sealants Co.",
 "sent": "2026-10-15 4:52 pm",
 "product": "FireSeal 200",
 "claim": {
  "text": "performs on plastic pipe; \"Treat this as our engineering judgment\"",
  "status": "claim"
 },
 "ej_status": "evidence_listed (not reviewed)",
 "missing_items": [
  "signature/authorization",
  "tested system referenced",
  "job name/location",
  "issuer qualifications"
 ],
 "route": "ask for an EJ from a qualified issuer (IFC guidance); the officer decides acceptance"
}
```
Must not: accept as an EJ; write or complete the EJ; rule on whether it is an EJ.

### cfx-005: Sprinkler "exempt" question plus NCR row
Source: `evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.md @ simplythatguy/batatis@914b8ec line 20; evals/demo-cases/b-contractor-firestop-nonconformance/input/ncr-firestop-EXAMPLE.md @ simplythatguy/batatis@914b8ec line 13`. *model-checked, not human-verified*

Note: input files only; no README, expected/ or keys/ content.

```text
The sprinkler fitter used the same sealant around the sprinkler branch lines. The sub says sprinklers are "exempt".
| L3–L4 | Sprinkler branch lines (steel) | 22 | Rated floor | Same sealant | **Not assessed:** inspector asks the design team to confirm treatment |
```

Expected fields:
```json
{
 "claim": {
  "text": "sprinklers are \"exempt\"",
  "by": "firestop sub",
  "status": "claim (unverified)"
 },
 "sealant_on_sprinkler_lines": "same sealant (brief L20)",
 "penetrant": "sprinkler branch lines",
 "material": "steel",
 "quantity": 22,
 "levels": "L3-L4",
 "assembly": "rated floor",
 "installed_system": "same sealant",
 "ncr_finding": "Not assessed: inspector asks the design team to confirm treatment",
 "needs_evidence_question": "Which listed system or provision covers each sprinkler penetration (heads with a metal escutcheon per NFPA 13, or branch pipe through the floor)?",
 "officer_gap": "applicant claim not supported by a citation"
}
```
Must not: answer yes or no.
Must: create a needs-evidence question plus an officer gap.

