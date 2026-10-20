# Sources (Batatis demo cases, backlog #7)

> **Edition caveat.** The cases were checked against the **NBC(AE) 2023 1st printing** (free NRC PDF, mirrored at publications.gc.ca). Page cites are from the NBC(AE) 2023 1st printing. The **2nd printing** (revisions and errata released Aug 17, 2026) is the edition now in force. Its wording and page numbers are **unverified**, because the NRC server failed TLS from the review box. Page numbers below are 1st-printing unless marked "2nd pr. (research, unverified)". Re-check against the 2nd printing before quoting pages.

Every code article, standard and STANDATA cited in the demo cases is listed here with how it was verified. The Data Nerd review (`DATA_NERD_REVIEW.md`, in this folder) is the cross-check behind this revision.
**Verification levels**
- **WEB**: the primary source was fetched on 2026-10-20 (MT) and the cited text read. Snapshots were kept locally by the author and not committed.
- **CODE-1P**: checked directly in the NBC(AE) 2023 1st printing by the Data Nerd review.
- **RESEARCH**: from the Batatis research notes (branch `feat/build-foundations`). Their 2nd-printing page cites are unverified.
- **TO VERIFY**: not confirmed. The cases phrase these generically and flag them.

**Code text:** NBC(AE) 2023 is a **free download** from NRC (1st and 2nd printings): https://nrc-publications.canada.ca/eng/view/object/?id=0316d953-0d55-4311-af69-cad55efec499 (1st-printing mirror: https://publications.gc.ca/collections/collection_2024/cnrc-nrc/NR24-28-7-2023-eng.pdf ; Alberta page: https://www.alberta.ca/building-codes-and-standards). Intent statements come from the *NBC 2020 Intent Statements*, which are national, explanatory, not Alberta law, and were **not re-verified** in the review.

## Legislation and provincial process
| ID | Source | Used for | Level | URL |
|---|---|---|---|---|
| W1 | Safety Codes Act, RSA 2000 c S-1, s.10 (use of variances) and s.38 (variances, notice, refusal) | Who may issue a variance; the "approximately equivalent or greater safety performance" test; compliance with a variance is deemed compliance; written refusal | WEB | https://kings-printer.alberta.ca/documents/Acts/S01.pdf |
| W2 | Building Code Regulation, AR 5/2024, s.1 and s.6 | NBC(AE) 2023 declared in force; in force May 1, 2024 | WEB | https://kings-printer.alberta.ca/documents/Regs/2024_005.pdf |
| W3 | Safety Codes Council, Variances page | Owner requests the variance; refusal appeal within 30 days with a $500 fee; only SCO refusals are appealable (live page re-checked). **Its registration statement is superseded by W15/W16.** | WEB | https://www.safetycodes.ab.ca/permits-inspections/variances/ |
| W4 | SCC Variance Form for Proposed Alternative Solution | Part 1 Sections A (applicant), B (details/legal description/ATS), C (Code or Standard; Article, Objective, Function, Intent), D (supporting docs and responsible person); Parts 2(a)/(b) are SCO-only | WEB | https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf |
| W5 | SCC, Where to get a Permit (accredited organization search) | Confirm the AHJ for a site; accredited municipality vs agency | WEB | https://www.safetycodes.ab.ca/permits-inspections/where-to-get-a-permit/ |
| W6 | **STANDATA 23-BCV-003**, Insulation below a heated floor (May 2024) | Province-wide variance: min. RSI 1.32 (R-7.5) under a heated floor in contact with the ground, Part 9; varies Sentence 9.36.2.8.(1) [F92-OE1.1]. Its full text contains **no** frost-depth condition, which resolves an open question in the research notes. | WEB | https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/3915ba54-96dd-4c54-a9c1-63df5c917836/download/ma-standata-variance-building-23-bcv-003-2024-05.pdf |
| W7 | **STANDATA 23-BCV-017**, Unvented roof assembly (Sept 2025) | Part 9 residential roofs may be unvented when using the design requirements of RDH report 32139.000, which must be provided with the permit application; varies Sentence 9.19.1.1.(1) | WEB | https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/2aa7678c-c476-4523-b0c3-36e71256e11b/download/ma-standata-variance-building-23-bcv-017-2025-09.pdf |
| W8 | STANDATA variance index, NBC(AE) 2023 | Lists current 23-BCV documents | WEB | https://open.alberta.ca/publications/standata-variance-building-national-building-code-2023-alberta-edition |
| W15 | SCC Information Bulletin **IB-2026-10-01**, Orders and Variances Registration Changes | From **Dec 1, 2026**, variances are registered only via the **OVP portal**, with supporting documentation included at registration and the **revised SCC Variance Form** completed; each variance registered individually per location | WEB | https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf |
| W16 | SCC Information Bulletin **IB-2025-11-18**, Mandatory Documentation of Variances | Building/fire/plumbing variances documented per Div C 2.3.1; copy to the Council within 10 days of issue; supporting documents retained | WEB | https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf |
| W17 | SCC Information Bulletin **IB-2026-10-16**, Clarifying AHJ | The **AHJ is the accredited organization** (or the Alberta Safety Codes Authority); SCOs exercise delegated powers on its behalf | WEB | https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf |
| W18 | NBC(AE) 2023, NRC record + Alberta 2nd-printing notice (Aug 2026) | Free download; 2nd printing in force | WEB | https://nrc-publications.canada.ca/eng/view/object/?id=0316d953-0d55-4311-af69-cad55efec499 ; https://www.alberta.ca/building-codes-and-standards |
| W19 | **STANDATA 23-BCV-001** (Apr 2024), Window opening control devices | An **ASTM F2090** WOCD satisfies both 9.8.8.1.(4) and 9.9.10.1.(1); not in adaptable or barrier-free units | WEB | https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/01b622f0-f4a1-426d-b15f-ffc25e725949/download/ma-standata-variance-building-23-bcv-001-2024-04.pdf |
| W24 | **STANDATAs 23-BCI-005** QAI (May 2024), **-006** UL Solutions (May 2024), **-007** Intertek (May 2024), **-013** ICC-ES (Feb 2025), **-040** APA (May 2025) | Each organization approved by the PBA under Div A 1.2.2.1.(2), on condition that it keeps its SCC accreditation and notifies the PBA of changes. (23-BCI-018 is "ON HOLD – UNDER REVIEW", so it isn't cited.) | WEB (CKAN API, metadata as of 2026-10-15) | https://open.alberta.ca/api/3/action/package_show?id=cb3d1662-1354-45c8-aab8-29b91f2a6c35 |

## Municipal process (Calgary)
| ID | Source | Used for | Level | URL |
|---|---|---|---|---|
| W9 | City of Calgary, *Guide to Applying for an Alternative Solution (Variance)*, Nov 23, 2023 | Start by talking to the SCO; **construction underway → contact the inspector or plans examiner**; separate request per issue/site/permit; a variance is **not** product or equipment approval; stamped and sealed docs where a professional is required | WEB | https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf |
| W10 | Calgary *Request for Specific Variance* form (R2014-06) | Local form fields; declaration that the owner keeps responsibility for safety under the variance | WEB | https://www.calgary.ca/content/dam/www/pda/pd/documents/building/variances/request-for-specific-variance.pdf |
| W11 | Calgary Building Advisory **B23-014**, *New Products, Materials and Systems used in Building Construction* (Sept 17, 2026) | Quotes Div A 1.2.1.1 and 1.2.2.1 and Div C 2.3.1.1; CCMC and PBA-recognized evaluators; for innovative products with no standard, an alternative solution is submitted **as part of a building permit application** and is site- and project-specific | WEB | https://www.calgary.ca/content/dam/www/pda/pd/documents/building/advisories/b23-014-new-products-materials-and-systems-in-building-construction.pdf |

## Municipal process (Edmonton)
| ID | Source | Used for | Level | URL |
|---|---|---|---|---|
| W20 | City of Edmonton, *Application requirements: house permits*, "Variance Requests for Alternative Solutions" | Request made with the house permit application; links to SCC Variances; no City-specific variance form; policy solutions offered first | WEB | https://www.edmonton.ca/residential_neighbourhoods/application-requirements-house-permits |
| W21 | City of Edmonton **Policy B23-02**, Window Opening Control Devices (Dec 23, 2024) | WOCD criteria: ≤102 mm, dual action, visible mechanism on egress windows, auto-reset, owner info at inspection | WEB | https://www.edmonton.ca/sites/default/files/public-files/Policy-B23-02-Window-Opening-Control-Devices.pdf |

## Product evaluation, standards and industry guidance
| ID | Source | Used for | Level | URL |
|---|---|---|---|---|
| W12 | NRC, Canadian Construction Materials Centre (CCMC) | National code-compliance assessment and registry | WEB | https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre |
| W23 | NRC CCMC **PAS-001** | Planning estimates read 2026-10-20: $4,000 non-refundable application; standardized products 2–6 months (CCMC) / 4–12 months (third party); **mature innovative** 6–12 months, $4,000 + $5,000 + $2,500/plant, annual $5,000 + $1,850/plant; **highly innovative** 8–18 months, $14,000+ at application (technical guide $10k–$250k+); FAQ "18+ months" for complex innovative products. **Fee changes effective Sept 1, 2026**, so confirm current rates. | WEB (Data Nerd live read) | https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=PAS-001&type=policy |
| W13 | CAN/ULC-S115, *Standard Method of Fire Tests of Firestop Systems* (SCC standards database entry) | Scope: penetration and joint firestop systems. **Adopted edition per Div B Table 1.3.1.2 of the printing in force:** 1st printing lists **CAN/ULC-S115-11** (CODE-1P, PDF p.111); the research notes said S115:2018 for the 2nd printing, which is **unverified**. Never silently substitute the current ULC edition (S115:2023). | WEB + CODE-1P | https://scc-ccn.ca/standardsdb/standards/4029527 |
| W14 | International Firestop Council, *Recommended IFC Guidelines for Evaluating Firestop System Engineering Judgments* (Rev. 2024-02) | EJs aren't used in place of tested systems when those are available; issued by the manufacturer's qualified staff or a qualified PE/FPE/listing agency; valid for a single job and location; required content | WEB (official PDF, indexed excerpt) | https://firestop.org/wp-content/uploads/2024/03/Guidelines_Firestop_Engineering_Judgments_Rev2024-02.pdf |

| W22 | RDH Building Science, *32139.000 Alberta Unvented Roofs, Evaluation Report* (Sept 10, 2025), published by the Spray Foam Coalition | The report named in 23-BCV-017: low-slope type "greater than 2%"; three assemblies (all exterior insulation / all required R as SPF at the deck / exterior board + MDSPF); hybrids with fibrous insulation only with a ratio check (≥60% air-impermeable R in Zone 7A per its IBC excerpt); interior RH ≤35%; CAN/ULC-S705.1/.2 or S712.1/.2; certified installer | WEB | https://sprayfoamcoalition.org/wp-content/uploads/32139_000-2025-09-10-RDH-Alberta-Unvented-Roofs-Report.pdf |

## NBC(AE) 2023 provisions cited
Pages are **1st printing** (CODE-1P) unless marked. "2nd pr." pages come from the research notes and are unverified.

| Provision | What it's used for | Verification |
|---|---|---|
| Div A 1.2.1.1.(1)(a)/(b), (2) | Acceptable solution vs alternative solution; attributed objectives/functions | CODE-1P; quoted in W11 |
| Div A 1.2.2.1.(1)–(3) | Fitness for purpose; CCMC or PBA-approved evaluation reports may be used in determining compliance | CODE-1P; quoted in W11 |
| Div A 1.3.3.2.(1) | Part 3/4/5/6 application | RESEARCH |
| Div A 1.3.3.3.(1) | Part 9 application (≤3 storeys, ≤600 m², listed occupancies) | CODE-1P |
| Div A 1.4.1.2 ("authority having jurisdiction") | Read per W17: the accredited organization, acting through SCOs | W17 |
| Div B 1.1.2.1.(1) | Points to the attribution tables. Objective/function pairs come from those tables. | RESEARCH (2nd pr. p.89) |
| Div B Table 1.3.1.2 | Adopted standard editions: **CAN/ULC-S115-11** in the 1st printing; 2nd printing unverified | CODE-1P (PDF p.111) |
| Div C 2.2.1.2 and Note A-2.2.1.2 | Province-wide variance by written request to the PBA; must show a province-wide issue | CODE-1P |
| Div C 2.3.1.1.(1)–(6) | Code analysis; O&M/commissioning; objectives, functions, acceptable solutions, assumptions, limiting factors, test procedures, engineering studies, performance parameters; qualifications; single coordinator. **Doesn't use the terms "risk assessment" or "mitigating measures"**, so the cases label those as good practice / SCO expectation. | CODE-1P (PDF p.733, C 2-10/2-11) |
| Div C 2.4.1.1.(1), (3), (4), (5) | Professional-involvement exemptions; AHJ may require; authentication under the professional Acts | CODE-1P |
| Div C 2.4.2.2.(1), 2.4.2.3.(1) | Coordinating registered professional; field review; change records ((1)(c)) | CODE-1P |
| Div B 3.1.7.1.(1), (2) | Fire-resistance rating from CAN/ULC-S101 tests, or Appendix D | CODE-1P |
| Div B 3.1.8.1.(1), (2) | (1)(a) continuous [F03-OS1.2]/[F03-OP1.2], clause (a) only; (2) openings protected with closures, shafts or other means [F03-OS1.2]/[F03-OP1.2] | CODE-1P (Table 3.10.1.1, PDF p.316, B 3-194) |
| Div B 3.1.8.3.(3), (4) | Joint firestops: FT rating, CAN/ULC-S115; perimeter joints, ASTM E2307 | CODE-1P |
| Div B 3.1.9.1.(1) | Penetrations sealed by an S115-tested firestop; "See also Article 3.1.9.4." [F03-OS1.2][F04-OS1.3]/[F03-OP1.2][F04-OP1.3] | CODE-1P (text PDF p.153; Table 3.10.1.1 PDF p.317) |
| Div B 3.1.9.1.(4) | Sprinklers exempt from (1)–(3) **only if** the annular space is covered by a metal escutcheon plate per NFPA 13 | CODE-1P (PDF p.153, B 3-31) |
| Div B 3.1.9.2 | Service penetrations → 3.1.9.1 | CODE-1P |
| Div B 3.1.9.4.(1)–(4) | Combustible piping: (1) sprinkler pipe if both sides sprinklered; (2) PEX only per (4)(a)/(b); (3) DWV only per (4), (5), (7), (8); (4)(b) >3 storeys: F rating ≥ FRR, S115 test **with 50 Pa** pressure differential; (4)(c) not in a vertical service space. 3.1.9.4.(3): [F03-OS1.2][F02,F04-OS1.3]/[F03-OP1.2][F02,F04-OP1.3] | CODE-1P (text PDF pp.153–154, B 3-31/32; Table 3.10.1.1 PDF p.318, B 3-196) |
| Div B 3.2.2.51.(2)(a), 3.2.2.49.(2)(a) | Floors as fire separations ≥1 h (if the Article governs; the architect's call) | CODE-1P (B 3-60/61) |
| Div B 5.4.1.2.(2)(b) | CAN/ULC-S741 for air-barrier materials (Part 5 only; mentioned as an example only) | CODE-1P (B 5-6/5-7) |
| Div B 9.8.8.1.(4), (5) and Note A-9.8.8.1.(4) | Window fall protection: guard or a ≤100 mm limiter (tools or special knowledge) for sills <900 mm, unless the bottom edge is <1800 mm above the outside ground; rotary operators can't serve as the limiter or guard. [F30-OS3.1] | CODE-1P; also quoted in W19 and W21 |
| Div B 9.9.10.1.(1), (2) | "Except where the suite is sprinklered…" bedroom outside opening without keys, tools or special knowledge; ≥0.35 m², no dimension <380 mm, stays open. [F10-OS3.7] | CODE-1P (text PDF p.865, B 9-43; Table 9.38.1.1 PDF p.1117, B 9-295) |
| Div B 9.10.17.10.(1) | Foam protected from adjacent space in the building, other than concealed spaces within walls. [F01,F02,F05-OS1.5] | CODE-1P (PDF p.899, B 9-77; Table 9.38.1.1 PDF p.1122) |
| Div B 9.23.13.1.(2) | Bracing: (a)(ii) listed sheathings; (a)(iii) interior panel-type finish per 9.29; (b) 9.23.13.4–7, Part 4, CWC 2014. (a) only where Sa(0.2) ≤0.70 and 1-in-50 wind <0.80 kPa. | CODE-1P (PDF p.970, B 9-147/148) |
| Div B 9.25.2.2.(1) | Insulation to listed standards (S701.1, S704.1, …) | CODE-1P |
| Div B 9.25.5.1.(1), (3), (4); Note A-9.25.5.1.(1); 9.25.5.2.(1) + Table | Low-permeance materials; permeance test ASTM E96/E96M desiccant method ((1)(a)(ii)); permeance inversely proportional to thickness (Note); (4) exemption; ratio 0.30 at 5000–5999 HDD | CODE-1P (B 9-169, 9-594) |
| Div B 9.27.3.3.(1); 9.27.3.4.(1), (2) | Sheathing membrane; insulating sheathing in lieu; joints | CODE-1P |
| Div B 9.27.5.1.(1), (2); 9.27.5.3.(1), (3) | Cladding fastening; sheathing that may hold vertical vinyl; furring. 9.27.5.1.(1): [F20-OS2.1,OS2.3], [F20-OH1.1,OH1.2,OH1.3]; other pairs apply only to panel-type bracing cladding | CODE-1P (Table 9.38.1.1 PDF p.1193, B 9-371) |
| Div B 9.36.2.6 | Zone 7A wall RSI 3.08 (no HRV) / 2.97 (HRV) | CODE-1P |
| Div B 9.36.2.8.(1), (5), (7), (9) | Heated floor RSI 2.84 (Zone 7A); (5) full bottom surface including edges; (7) in addition, perimeter/foundation wall to the bottom of the floor; (9) integral-footing slab (RSI 3.72 / 2.84 + skirt; Part 4 per 9.16.1.2) | CODE-1P (B 9-245 to 9-247); (1) also quoted in W6 |
| Div B 9.19.1.1.(1) | Roof venting "except where it can be shown to be unnecessary" | WEB (quoted in W7) |
| Div B App. C Table C-2 | Edmonton 5120 HDD (Zone 7A); 1-in-50 wind 0.45 kPa | CODE-1P (PDF p.661) |

## Explicitly not used
- No CCMC number, test report, lab, WOCD product or engineering letter in these cases is real. All of them are fictional EXAMPLE inputs.
- STANDATA "19-BCB-012" and article "9.10.9.9." are known fakes from `evals/battle-prompts/`. They appear only as traps in must-not lists.
- STANDATA **23-BCI-018** (guards for glazing in a window) is "ON HOLD – UNDER REVIEW", so it's not cited.

## T-list status (after the Data Nerd review)
| # | Item | Case | Status | Now says |
|---|---|---|---|---|
| T1 | Interior-finish bracing route | A | **Resolved** | 9.23.13.1.(2)(a)(iii), interior panel-type finish per 9.29, within the Sa(0.2)/wind limits. Edmonton Sa(0.2) is still for the designer to confirm. |
| T2 | 9.10.17.10.(1) and exterior foam | A | **Resolved on the text; AHJ still confirms** | Outdoors isn't "space in the building"; stud cavity excluded |
| T3 | Air-leakage test method | A | **Open (confirmed gap)** | No method named; S741 only as a Part 5 example |
| T4 | 23-BCI-005/-006/-007/-013/-040 texts | A | **Resolved** | W24 |
| T5 | CCMC fees and timelines | A | **Resolved** | W23 innovative-product rows; Sept 1, 2026 fee change |
| T6 | 3.1.9.1.(4) conditions | B | **Resolved** | Metal escutcheon per NFPA 13; branch pipe not covered |
| T7 | Intent for 3.1.9.1.(1), 3.1.8.1.(2), 3.1.9.4.(3) | B | **Open** | Section C cells stay flagged blank |
| T8 | Required floor rating "1 h" | B | **Partial** | Consistent with 3.2.2.51.(2)(a)/3.2.2.49.(2)(a); which governs is the architect's call |
| T9 | Roof vs RDH 32139.000 | C | **Resolved: probably doesn't match as drawn** | W22 |
| T10 | 9.9.10.1.(1) sprinkler exception wording | C | **Resolved** | "Except where the suite is sprinklered…" |
| T11 | Edmonton AHJ and route | C | **Partial** | Route verified (W20); accreditation still to look up (W5) |
| T12 | NBC(AE) source URL | all | **Resolved** | Free NRC download (W18) |
| T13 | 2nd-printing wording, page numbers and S115 edition | all | **Open** | See the edition caveat at the top |
| T14 | NBC 2020 Intent Statements (I1/I2 and IS pages) | A, C | **Open** | Intent cells are flagged GAP in cases A and C. Labelled national and not re-verified |
