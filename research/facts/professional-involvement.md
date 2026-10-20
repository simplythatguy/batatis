---
topic: professional-involvement
scope: When a registered professional (engineer or architect) is legally required for a building project or an alternative solution in Alberta, what counts as practising engineering or architecture, and where the tool must stop.
sources_checked:
  - NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2
  - NBC-2020-Intent-Statements, explanatory context only
  - https://kings-printer.alberta.ca/documents/Acts/E11.pdf
  - https://kings-printer.alberta.ca/documents/Acts/A44.pdf
  - https://kings-printer.alberta.ca/documents/Regs/1999_150.pdf
  - APEGA Authenticating Professional Work Products, November 2024
  - APEGA Relying on the Work of Others and Outsourcing, May 2021
  - AAA-APEGA National Building Code Schedules User Guide, May 2024
  - STANDATA 23-BCI-015R1, May 2025
  - Archived STANDATA 23-BCB-002R1, historical context only
  - Edmonton B23-03, February 2026 revision
  - Edmonton Point Access Block Alternative Solution Guide, February 2025
  - Edmonton Guideline for Alternative Solutions Affecting Emergency Services, April 2025
  - Calgary Guide to Applying for an Alternative Solution, November 2023
  - reference/README-challenge.md
  - Safety Codes Act RSA 2000 c S-1 (reference copy, sections 6, 11, 45)
  - SCC notice on variances under the Safety Codes Act, 2019 (reference copy)
  - STANDATA 23-BCB-002R1, August 2025 (section 18 quotation only)
  - Calgary SPV-004 (February 25, 2020) and SPV-006 (June 19, 2025)
  - STANDATA 23-BCV-002 (May 2024), 23-BCV-005 (May 2024), 23-BCV-010 (February 2025), 23-BCI-003R1
last_verified: 2026-10-18
---
# Professional involvement

## Progress
- Complete: 2026-10-18. Resumed the predecessor's skeleton, preserved its work, and finished all required fact-sheet sections.
- Verified: second-printing code provisions, attribution tables, national explanatory intents, professional Acts, APEGA standards, schedules, and the requested municipal guidance. Four current municipal PDFs matched the supplied source PDFs byte for byte.
- Validation: 370 recognized citation checks, zero errors and zero warnings. Expanded ranges/clauses resolved 65 body targets across 19 articles; two attribution tables and five explanatory notes were checked separately. Code source pages and six intent pages were re-read with codesearch. Raw receipts are in `reference/web/professional-involvement/`.
- Resumed check (second agent, 2026-10-18): re-ran `codedb validate` (ok; 370 citations, 0 errors, 0 warnings). Confirmed the receipt folder and the two Act hashes against `sources.json`. Confirmed the NBC 2020 Intent Statements pages (explanatory only) (608-610, 1206, 2430-2431) and the EGPA and Architects Act definitions (PDF pp.10 and 7). Added the Safety Codes Act and SCO-power subsection and the variance precedents, which the earlier pass had not covered.
- Remaining: only the project-specific determinations expressly marked UNVERIFIED in Open questions / uncertainty. No missing research section or unresolved source-access blocker remains.
- Ownership: only this file and the assigned topic download/receipt folder were written. No delegation, commit, push, source-solutions reading, or access to `evals/` or `variants/`.
- Base checkout receipt: HEAD `02fb483d3afeac77ceb46066443b63dbc63dfc5b` at resume. Unrelated shared-checkout changes were preserved. Parent maintenance receipt reused as instructed.

## Plain-language summary

A registered professional is someone licensed for the relevant work under Alberta professional legislation. The code includes architects, engineering professionals, and licensed interior designers within their lawful scope. NBC(AE) 2023 p2, Div A, Article 1.4.1.2., definitions of registered professional and registered engineering/architectural professional [PDF p.50].
A small building can still need a professional for a component, a difficult design, or a local submission requirement. NBC(AE) 2023 p2, Div C, Sentences 2.4.1.1.(4) and 2.4.1.2.(1) [PDF p.740].
The general professional exception and the Part 9 eligibility test answer different questions. NBC(AE) 2023 p2, Div A, Sentence 1.3.3.3.(1) [PDF p.40]; Div C, Sentence 2.4.1.1.(1) [PDF pp.739-740].
An alternative solution needs named design responsibility, relevant qualifications, and a documented analysis. NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(1) to (5) [PDF p.739].
A multi-person alternative-solution design needs one named coordinator. A project covered by the schedules regime also needs a coordinating registered professional. These roles arise under different provisions. NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(6) [PDF p.739]; Sentence 2.4.2.2.(1) [PDF p.741].
A professional stamp assigns professional responsibility. It does not itself prove that the AHJ has accepted an alternative solution. The tool can check whether responsibility and evidence are documented; the professional and AHJ make the technical and acceptance decisions. See the professional boundaries below and sources W3 to W5.

The sources and pages in this sheet were checked on 2026-10-18. Its worked example is a hypothetical submission, not an issued variance.

## When this topic applies

Use this topic when a project description or document raises any of these signals.

| Concrete signal | Why it belongs here | Main evidence |
|---|---|---|
| More than four principal dwelling units, a large commercial building, or an assembly/care/treatment/detention use | Check the general professional-involvement exceptions against actual use, size, and height. | NBC(AE) 2023 p2, Div C, Article 2.4.1.1. [PDF pp.739-740]. |
| A claim that a building is Part 9 and therefore never needs an engineer | Part 9 eligibility does not remove component or AHJ triggers. | NBC(AE) 2023 p2, Div A, Sentence 1.3.3.3.(1) [PDF p.40]; Div C, Sentence 2.4.1.2.(1) [PDF p.740]. |
| Part 4 calculations, unusual structural loading, roof-truss assemblies, or Part 4 preserved wood foundations | Identify competent engineering responsibility and any field-review commitment. | NBC(AE) 2023 p2, Div C, Article 2.4.1.2. [PDF p.740]; Div B, Article 9.23.14.11. [PDF p.986]. |
| A fire-suppression or fire-alarm design in a building that needs general professional involvement | The owner must retain a professional for defined design, review, and testing/verification roles. | NBC(AE) 2023 p2, Div C, Articles 2.4.1.3. and 2.4.1.4. [PDF p.740]. |
| Missing credentials, unnamed report author, several consultants, or no coordinator | Check alternative-solution responsibility and coordination. | NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(4) and (6) [PDF p.739]. |
| Point Access Block, single egress stair, or a proposal that relies on emergency response | Edmonton has specific professional and peer-review expectations. | W8, PDF page 8; W9, PDF pages 3 and 8-9. |
| Foreign stamped documents, supplier design software, a stamp image, or a request to seal generated calculations | Check Alberta authority, professional responsibility, authentication, and reliance. | W3, sections 2.1, 3.1, 3.3 and 4.2; W4, reference 3.1. |
| A required designer leaves the project, or C-schedules are missing at completion | Continued professional involvement and occupancy documentation matter. | NBC(AE) 2023 p2, Div C, Articles 2.4.2.4. and 2.4.2.5. [PDF p.742]. |

Near-misses that need another topic as the main route:

- Filling owner, address, permit, or signature fields, without a professional-responsibility issue, belongs to [process-and-admin](process-and-admin.md).
- Deciding whether a citation, objective, or function matches a code sentence belongs to [code-structure-and-attribution](code-structure-and-attribution.md). A correct match does not establish professional competence.
- Comparing a product test report or certification scope belongs to [evidence-and-conformity](evidence-and-conformity.md). Professional involvement becomes a second route if a person must interpret, extend, or integrate the evidence.
- Exit geometry and single-stair equivalency belong to [egress-and-single-stair](egress-and-single-stair.md). This sheet determines responsibility, not whether a stair design is safe.
- A standard compliant house with no engineered element, alternative-solution analysis, or AHJ special-safety request does not acquire a whole-project professional requirement merely because someone submits a permit. The general code exception still needs the independent law and component checks. NBC(AE) 2023 p2, Div C, Sentences 2.4.1.1.(1) to (4) [PDF pp.739-740].
- Routine installation to an approved design is different from creating or changing that design. The legal scope and exceptions in W1 and W2 must be checked before classifying the activity.

## Benchmark acceptable solutions

### Code pathway and professional involvement are separate checks

An alternative must achieve the minimum performance of the applicable Division B acceptable solutions in the areas defined by their attributed objectives and functions. A professional signature does not replace that comparison. NBC(AE) 2023 p2, Div A, Clause 1.2.1.1.(1)(b) [PDF p.38].

1. Part 9 applies only when the building meets its height, building-area, and listed major-occupancy limits. The second printing includes Group B, Division 4 home-type care as well as Group C, D, E, and specified Group F occupancies. Confirm the actual classification before using this route. NBC(AE) 2023 p2, Div A, Sentence 1.3.3.3.(1) [PDF p.40].
2. Professional involvement has its own exceptions and overrides. A Part 9 classification does not answer whether a particular component requires engineering. NBC(AE) 2023 p2, Div C, Sentences 2.4.1.1.(1), (3) and (4) [PDF pp.739-740]; Sentence 2.4.1.2.(1) [PDF p.740].
3. The general professional-involvement exception for a residential single-family dwelling or a multiple-family dwelling with four or fewer dwelling units does not erase the AHJ's special-safety power or the specific structural-design rule. Secondary suites need not count as dwelling units for this exception. NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(b) [PDF p.739]; Sentences 2.4.1.1.(2) and (4) [PDF p.740].

### General professional-involvement exceptions

These are the exceptions to the general code requirement, subject to special safety concerns and independent professional legislation. The area is building area, not a sum of every floor's area. Do not treat the table as permission to practise engineering or architecture without the appropriate authority.

| Occupancy or building type | Exception stated in the code | Verified source |
|---|---|---|
| Assembly, care, treatment, or detention | At most three storeys. Maximum building area is 300 m² at one storey, 150 m² at two, and 100 m² at three. | NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(a) [PDF p.739]. |
| Residential single-family or small multiple-family dwelling | Single-family dwelling, or multiple-family dwelling with at most four dwelling units. The clause itself does not impose the height and area limits from the other clauses. Other code and professional-law requirements still apply. | NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(b) [PDF p.739]. |
| Hotel, motel, or similar residential use | At most three storeys. Maximum building area is 400 m² at one storey, 200 m² at two, and 130 m² at three. | NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(c) [PDF pp.739-740]. |
| Business and personal services, mercantile, or industrial | At most three storeys. Maximum building area is 500 m² at one storey, 250 m² at two, and 165 m² at three. | NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(d) [PDF p.740]. |
| Farm building not for public use | Listed exception. Confirm the use rather than assuming all agricultural buildings qualify. | NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(e) [PDF p.740]. |
| Relocatable industrial camp building | Listed exception. Its separate code and certification pathway still needs review. | NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(f) [PDF p.740]. |

For buildings outside these exceptions, one or more registered professionals must authenticate the drawings and specifications in the appropriate combination of architecture and engineering. The rule does not say that any single engineer can cover every discipline. NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(3) [PDF p.740].

The AHJ may require professionals to authenticate all or part of the design and perform field reviews when size or complexity may create special safety concerns. Authentication must follow the relevant professional Act. NBC(AE) 2023 p2, Div C, Sentences 2.4.1.1.(4) and (5) [PDF p.740].

### Structural and building-system triggers

- A designer working to Part 4 must be a registered professional skilled in the work. This applies even when the overall building has a general exception. NBC(AE) 2023 p2, Div C, Sentence 2.4.1.2.(1) [PDF p.740].
- For a preserved wood foundation designed to Part 4, the owner must provide evidence before construction that a professional is retained for installation field reviews. NBC(AE) 2023 p2, Div C, Sentence 2.4.1.2.(2) [PDF p.740].
- In buildings covered by the general professional requirement, automatic fire-suppression systems require a retained professional for design, installation field reviews, and witnessing testing. Fire-alarm systems require design, installation field reviews, and witnessing verification. The owner provides retention evidence before construction. NBC(AE) 2023 p2, Div C, Sentence 2.4.1.3.(1) and Sentence 2.4.1.4.(1) [PDF p.740].
- Part 9 permits structural design under its prescriptive rules, accepted good engineering practice such as the named CWC guide, or Part 4 within the stated loading limits. A departure from a span table can therefore have another acceptable-solution route. It is not automatically a variance. Selecting and applying an engineering design route still needs the appropriate professional assessment. NBC(AE) 2023 p2, Div B, Sentences 9.4.1.1.(1) to (3) [PDF pp.836-837]; Div C, Sentence 2.4.1.2.(1) [PDF p.740].

### Alternative-solution responsibility

The submission needs a code analysis, its analytical methods and rationale, and any operational, maintenance, or commissioning conditions. It must identify relevant acceptable solutions, objectives, functional statements, assumptions, limits, testing, engineering studies, or performance parameters. NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(1) to (3) [PDF p.739].

The analysis must identify the qualifications, experience, and background of the people responsible for the design. When several people take responsibility for different aspects, the applicant must identify one person to coordinate the design, analysis, and documentation. This coordination sentence does not itself call that person a registered professional. Other legal and project requirements determine that question. NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(4) to (6) [PDF p.739].

### Schedules and field reviews

The schedules regime applies to projects under the general professional requirement, rather than automatically to every engineered component in every exempt house. NBC(AE) 2023 p2, Div C, Sentence 2.4.2.1.(1) [PDF p.741].

| Stage | Required responsibility | Verified source |
|---|---|---|
| Before permit application | Owner retains a coordinating registered professional and professionals of record and provides Schedules A and B. | NBC(AE) 2023 p2, Div C, Sentence 2.4.2.2.(1) [PDF p.741]. |
| Design and construction | Coordinating professional coordinates design and field reviews. Professionals of record authenticate their documents, arrange field reviews, and record corrective actions. Delegated professionals remain responsible for their assigned design and reviews. | NBC(AE) 2023 p2, Div C, Sentences 2.4.2.3.(1) to (3) [PDF pp.741-742]. |
| Completion | Coordinating professional provides C-1, supported by C-2 from professionals of record and C-3 for delegated work. | NBC(AE) 2023 p2, Div C, Article 2.4.2.3. [PDF pp.741-742]. Appendix B forms appear on source PDF pages 755, 757 and 759. |
| Permission to occupy | AHJ must receive C-1 before occupancy permission. | NBC(AE) 2023 p2, Div C, Sentence 2.4.2.4.(1) [PDF p.742]. |
| Required professional ceases to be retained | Work on the affected portion stops until replacement and a new A or B schedule, as applicable. | NBC(AE) 2023 p2, Div C, Sentences 2.4.2.5.(1) and (2) [PDF p.742]. |

The form titles are Schedule A, Schedule B, Schedule C-1, Schedule C-2, and Schedule C-3. Do not substitute older A-1/A-2 terminology. The code's Appendix B also requires documentation of competence and sufficient licensed scope for the professionals and professional permit holders. NBC(AE) 2023 p2, Div C, Appendix B, Schedule A, source PDF pages 747-751; Schedule B, source PDF pages 752-754.


## Attributions

### Administrative provisions do not supply the performance benchmark

The professional-involvement and documentation provisions are in Division C. They are administrative requirements, not Division B acceptable-solution rows with assigned objective/function pairs. Do not invent an attribution for a schedule, a professional's signature, or the coordination duty. The technical acceptable solution being replaced supplies the Section C attribution.

The code database returned no attribution rows for the Division C articles in this sheet. The source text confirms their placement in Division C. NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739]; Articles 2.4.1.1. to 2.4.1.4. [PDF pp.739-740]; Articles 2.4.2.1. to 2.4.2.5. [PDF pp.741-742].

### Verified technical examples

These are examples relevant to the professional trigger, not a substitute for identifying every technical provision affected by a real project.

| Technical provision | Objective/function attributions in the Alberta table | Table source and qualification |
|---|---|---|
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269] | [F10,F12,F05,F06-OS3.7]; [F12,F06-OS1.2]; [F12,F06-OP1.2] | Div B Table 3.10.1.1. [PDF p.346]. All three groups belong to the two-exit root sentence. |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(3) [PDF p.270] | [F10-OS3.7] | Div B Table 3.10.1.1. [PDF p.346]. This is the additional constraint on certain permitted single-exit cases. |
| NBC(AE) 2023 p2, Div B, Sentence 9.23.14.11.(1) [PDF p.986] | [F20-OS2.1,OS2.3,OS2.5]; [F22-OS2.3,OS2.5]; [F20-OP2.1,OP2.3,OP2.5]; [F22-OP2.3,OP2.5]; [F20,F22-OH1.1,OH1.2,OH1.3]; [F20,F22-OS1.2] | Div B Table 9.38.1.1. [PDF p.1189]. The OS1.2 group applies to assemblies required to provide fire resistance. |
| NBC(AE) 2023 p2, Div B, Sentence 9.23.14.11.(3) [PDF p.986] | [F20-OS2.1,OS2.3,OS2.5]; [F22-OS2.3,OS2.5]; [F20-OP2.1,OP2.3,OP2.5]; [F22-OP2.3,OP2.5] | Div B Table 9.38.1.1. [PDF p.1189]. These groups relate to member bracing and anchorage. |

The connection-design referral in NBC(AE) 2023 p2, Div B, Sentence 9.23.14.11.(2) [PDF p.986] has no separate row in the roof-truss attribution table. Its root design sentence carries the groups above. A real alternative to the connection design must also identify the applicable Part 4 benchmark; copying the root groups alone does not complete that analysis.

The general routing provision, NBC(AE) 2023 p2, Div B, Article 9.4.1.1. [PDF pp.836-837], likewise returned no attribution rows in the database. It directs structural design routes. Use the actual structural requirement for a performance comparison.

Table pages 346 and 1189 were checked in extracted text and in rendered images saved with the topic's source receipts.

## Intent

### Keep Alberta law and national explanatory material distinct

The national intent supplement explains the goals of technical acceptable solutions. It is explanatory context, not a replacement for the adopted Alberta text or its attribution table.

A search for the professional and documentation numbers in the national supplement finds similarly numbered provisions about farm buildings. Those entries are not intent statements for Alberta Division C. Do not attach the farm-building intent to a professional-involvement rule merely because the number matches. The Alberta administrative rationale is explained by its own notes. NBC(AE) 2023 p2, Div C, Note A-2.3.1. and Note A-2.4.1.2.(1) [PDF p.744].

| Provision and source | Verified intent, paraphrased | Comparison with Alberta text |
|---|---|---|
| NBC 2020 Intent Statements, 3.4.2.1.(1) [PDF pp.608-609] | Preserve another exit if one route is blocked. This supports evacuation and responder access. It also reduces fire spread and resulting harm to people and damage to the building when emergency response is delayed. | The Alberta two-exit root sentence and all three attribution groups were checked independently in NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269] and Table 3.10.1.1. [PDF p.346]. |
| NBC 2020 Intent Statements, 9.4.1.1.(1) to (3) [PDF p.1206] | Define when Part 9 structural rules, accepted engineering practice, and Part 4 apply. Keep simplified supports consistent with the design live load and direct users to site-specific climate and seismic information. | The Alberta routing and loading provisions were read in NBC(AE) 2023 p2, Div B, Article 9.4.1.1. [PDF pp.836-837]. They do not remove the Alberta professional trigger. |
| NBC 2020 Intent Statements, 9.23.14.11.(1) [PDF pp.2430-2431] | Provide truss strength and stiffness for expected loads, avoid collapse and excessive deformation, protect environmental separators, and preserve required fire-resisting components. | The relevant Alberta sentence and its conditional fire group were checked in NBC(AE) 2023 p2, Div B, Sentence 9.23.14.11.(1) [PDF p.986] and Table 9.38.1.1. [PDF p.1189]. |
| NBC 2020 Intent Statements, 9.23.14.11.(2) [PDF p.2431] | Refer connections to Part 4 because simple prescriptive criteria do not describe their design adequately. | NBC(AE) 2023 p2, Div B, Sentence 9.23.14.11.(2) [PDF p.986] makes the Part 4 connection referral. Its Alberta explanatory note connects that referral to professional design. Note A-9.23.14.11.(2) [PDF p.1418]. |
| NBC 2020 Intent Statements, 9.23.14.11.(3) [PDF pp.2431-2432] | Prevent compression-member buckling and structural collapse by adequate truss bracing under expected gravity and lateral loads. | Alberta bracing and anchorage wording is in NBC(AE) 2023 p2, Div B, Sentence 9.23.14.11.(3) [PDF p.986]. |

For the administrative provisions, the Alberta note explains that documentation records the compliance rationale, continuing maintenance duties, and design limits for later alterations and investigation. The structural note explains why Part 4 assumes a qualified professional and warns that other Parts may also need one. The coordination note describes periodic field reviews and cross-discipline connections. These are explanatory notes, not additional objective/function assignments. NBC(AE) 2023 p2, Div C, Notes A-2.3.1., A-2.4.1.2.(1), A-2.4.2.2.(1)(a) and A-2.4.2.3.(1) [PDF p.744].

## Typical alternative solutions

A professional-involvement requirement is not itself a technical alternative solution. It identifies who must take responsibility for developing and reviewing the proposal. These are common situations where the two questions interact.

| Proposal | What can be established from the reviewed sources | Professional question still to resolve |
|---|---|---|
| Edmonton Point Access Block using one shared exit stair | The city's guide provides an application pathway with mandatory professional involvement. Its technical analysis is an exemplar, not a pre-approved building design. | Which qualified consultant and registered professionals will own the fire/life-safety analysis, building design, system interfaces, and field review? W8, PDF pages 4-5 and 8. |
| Novel roof geometry or engineered truss assembly in a house | Part 9 truss provisions require engineering-based design and refer connections to Part 4. | Has an appropriate engineer designed the complete assembly, including interconnections, and authenticated the relevant information? NBC(AE) 2023 p2, Div B, Article 9.23.14.11. [PDF p.986]; W6, PDF pages 1 and 3. |
| Proposed beam or connection outside a simple prescriptive table | An available Part 4 or accepted engineering-practice route may already be an acceptable solution. | Determine the actual code route before calling it a variance; identify the skilled Part 4 designer where that route applies. NBC(AE) 2023 p2, Div B, Article 9.4.1.1. [PDF pp.836-837]; Div C, Sentence 2.4.1.2.(1) [PDF p.740]. |
| Alternative smoke, access, evacuation, or active-system strategy | Edmonton explains how to evaluate impacts on emergency services and arrange professional peer review. | Establish competent design responsibility, justified response assumptions, and continuing operational conditions. W9, PDF pages 3, 8-9 and 20-22. |
| Supplier or off-the-shelf component substituted into a larger engineered design | A supplier's product information does not by itself establish responsibility for project integration. | Identify who accepts responsibility for the design, interfaces, limitations, and use outside published specifications. W3, reference 3.5; W4, reference 3.1. |

No issued project-specific approval was verified for these hypothetical proposals. The local guides and STANDATA below establish review expectations or interpretations. They do not prove acceptance of an applicant's design.

## Usual mitigations and evidence

### Evidence of professional responsibility

A useful Section D package names the individual or organization responsible for each document and shows how its scope fits the project. The alternative-solution code analysis must describe the qualifications, experience, and background of the responsible designers. NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(4) [PDF p.739].

The following checks concern the presence and consistency of evidence. The tool records what a document says; it cannot certify a licence, a signature, or a technical conclusion from an image.

| Evidence item | What to record | What remains a human/professional judgment |
|---|---|---|
| Identity and practising status | Full name, regulator, licence identifier, discipline/scope claimed, date of directory check, and applicable firm/permit-holder information | Whether the authority and competence cover the actual project work |
| Defined scope | Which building, system, report revision, assumptions, exclusions, and interfaces the professional covers | Whether all necessary design and field-review work has a competent owner |
| Retention and schedule commitments | Owner/CRP relationship, professionals of record, delegated components, A/B schedules where applicable, and field-review commitments | Whether the proposed allocation satisfies the project and professional obligations |
| Authenticated work | Final intended-use report/drawings and authentication information; validation if a permit holder produced the work | Authenticity, technical correctness, sufficiency, and legal applicability |
| Field-review evidence | Reports, observations, recorded corrective actions, design changes, and C-schedules where applicable | Whether the frequency, scope, observations, and corrective action are adequate |
| Alternative-solution analysis | Verified benchmark, attributed objectives/functions, methods, assumptions, test/study references, limiting factors, and maintenance/commissioning conditions | Whether the design actually achieves the required performance |

Code basis for the responsibility and lifecycle checks is NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739]; Articles 2.4.2.2. and 2.4.2.3. [PDF pp.741-742]. The joint AAA/APEGA schedules guide explains that responsibilities and delegated scope must have no gaps. W5, PDF pages 4-10.

### Authentication, validation, and reliance

APEGA authentication records a licensed professional's responsibility for work they prepared, directly supervised/controlled, or thoroughly reviewed. Its intended-use test considers technical content, completeness, reliance, and separate legal requirements. For permit-holder work, Responsible Member validation is a distinct step after authentication. A visible stamp image alone does not establish valid digital authentication. W3, sections 2.1-2.2, 3.1 and 4.2, PDF pages 12-19.

The appropriate check is not a request to "stamp this" after the technical work is finished. APEGA's reliance standard requires direct supervision/control or a thorough review before a professional takes responsibility for another person's work. It also addresses outsourcing, assumptions, local conditions, and interfaces. These duties can apply to supplier material and software outputs. W4, sections 3.1-3.2 and 5.1, PDF pages 10-17.

For a project under the schedules regime, the professional of record and delegated professional have defined, continuing responsibilities. A supplier's shop drawing is not a substitute for the project's coordinated design and field reviews. NBC(AE) 2023 p2, Div C, Sentences 2.4.2.3.(2) and (3) [PDF pp.741-742].

### Practical evidence confidence ladder

This is a research synthesis for completeness review, not a statutory grading scale or an automatic acceptance rule.

1. Unsupported assertion or generated narrative. It does not show verified responsibility, testing, or performance.
2. Product brochure, generic detail, or unverified résumé. Useful for intake; scope and applicability remain open.
3. Traceable report or test, with author, date, method, tested configuration, and limitations. The responsible designer still must assess applicability.
4. Project-specific professional work with defined scope, lawful authority, appropriate authentication, relevant analysis, and documented assumptions. The technical conclusion remains the professional's responsibility and subject to AHJ assessment.
5. Coordinated construction evidence, resolved changes/corrections, commissioning/maintenance obligations, and completion assurances where required. This adds implementation evidence; it does not replace the AHJ's acceptance or occupancy decision.

A higher step does not cure an incorrect benchmark or evidence outside its tested scope. The required documentation must be detailed enough to convey design intent and support the analysis. NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(5) [PDF p.739].

### Standards by number and scope

- TPIC 2019, Truss Design Procedures and Specifications for Light Metal Plate Connected Wood Trusses, is the design practice named by the Part 9 roof-truss provision. It is not a universal test certificate or an exemption from professional responsibility. NBC(AE) 2023 p2, Div B, Sentence 9.23.14.11.(1) [PDF p.986].
- CWC 2014, Engineering Guide for Wood Frame Construction, is an example of good engineering practice named in a permitted Part 9 structural route. The route has application and loading limits. NBC(AE) 2023 p2, Div B, Article 9.4.1.1. [PDF pp.836-837].
- There is no universal laboratory test that establishes whether a person is authorized to practise engineering or architecture. The relevant checks are the professional Acts, licensed scope, responsibility, and code-specific duties. Testing and certification standards for a proposed material or system must be selected for that technical subject, with the proper edition. See [evidence-and-conformity](evidence-and-conformity.md).

For an Edmonton emergency-services proposal, the professional must assess responder impacts and identify continuing inspection, testing, maintenance, and commissioning responsibilities. Generic claims about firefighters compensating for the design do not supply that evidence. W9, PDF pages 8-9 and 20-22.

## Engineering / professional triggers

### What counts as professional work

The Engineering and Geoscience Professions Act defines engineering by the work and the knowledge it requires. Reporting, advice, evaluation, design, plans/specifications, and direction of construction, inspection, maintenance, or operation can qualify when they require professional application of mathematics, physics, chemistry, or related applied subjects. It is broader than producing drawings. W1, section 1(q), PDF page 10.

The Act reserves practice subject to its express exceptions. These include certain supervised activities, own-property work without public-safety involvement, and listed small-building activities. The small-building exceptions use gross area on each floor; a house or four-unit exception does not cancel a separate code duty to retain a professional. Avoid a blanket claim that every calculation is reserved practice or that every homeowner project is exempt. W1, sections 2(1), 2(4), and 2(6)-(7), PDF pages 12-15.

Architecture includes planning/design advice, preparing design documents, and inspecting or assessing contracted building work. The Architects Act reserves practice to authorized entities subject to its exceptions, including defined small-building work and employment within an authorized practice. Licensed interior designers have a defined, limited scope. A professional engineer does not gain unrestricted architectural authority merely by holding an engineering licence. W2, sections 1(l), 2(1), 2(3)-(7), 2.1 and 3, PDF pages 7-12.

The code's definitions include registered architectural professionals, registered engineering professionals, and licensed interior designers. A title alone does not establish that a person can take responsibility for the proposed discipline or scope. NBC(AE) 2023 p2, Div A, Article 1.4.1.2. [PDF p.50]; Div C, Sentence 2.4.1.1.(3) [PDF p.740]; Appendix B, Schedule A, source PDF pages 749-750.

### Decision table

"Yes" identifies a requirement on the stated facts. "No" means that the stated facts do not trigger the specified general requirement. "Depends" means that scope, qualification, exceptions, or an AHJ determination remains necessary. These are responsibility decisions, not technical design approval.

| Project signal | Required? | Discipline or responsible person | Requirement and citation |
|---|---|---|---|
| Ordinary single-family dwelling, prescriptive work, no separate engineered component or special-safety issue | No general whole-building requirement on these facts | Applicant/designer may prepare the submission within lawful scope. Recheck components and local rules. | NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(b) [PDF p.739]; Sentence 2.4.1.1.(4) [PDF p.740]. W1 and W2 supply the separate law checks. |
| Multiple-family dwelling with no more than four principal dwelling units | No general requirement under this specific code exception; component duties may still apply | Discipline depends on actual work | NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(b) [PDF p.739]; Sentence 2.4.1.1.(4) [PDF p.740]. |
| Six-unit apartment building, even if its size qualifies for Part 9 | Yes | Appropriate architecture and engineering disciplines; coordinating professional and professionals of record | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(3) [PDF p.740]; Sentences 2.4.2.1.(1) and 2.4.2.2.(1) [PDF p.741]. |
| Secondary suites proposed within otherwise excepted housing | Depends | Confirm whether each unit actually qualifies as a secondary suite, then assess affected disciplines | Secondary suites need not count for the general exception. NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(2) [PDF p.740]. This does not resolve separate professional-law interpretation. |
| One-storey assembly building above 300 m² building area, or other listed exception limits exceeded | Yes, unless another applicable exception changes the facts | Architecture and applicable engineering disciplines | NBC(AE) 2023 p2, Div C, Clauses 2.4.1.1.(1)(a), (c) and (d) [PDF pp.739-740]; Sentence 2.4.1.1.(3) [PDF p.740]. |
| A project called Part 3 merely because of its occupancy, but within an express professional exception | Depends; Part 3 alone is not the general professional test | Check exception, actual work, and professional law | NBC(AE) 2023 p2, Div A, Sentence 1.3.3.2.(1) [PDF pp.39-40]; Div C, Sentences 2.4.1.1.(1) and (4) [PDF pp.739-740]. |
| Structural design to Part 4, including an engineered beam, connection, or foundation in a house | Yes for that design | Registered professional skilled in structural work; engineering authority appropriate to the actual service | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.2.(1) [PDF p.740]. |
| Preserved wood foundation designed under Part 4 | Yes, including retention for installation field reviews | Appropriate structural/foundation professional | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.2.(2) [PDF p.740]. |
| Loads, geometry, supports, soil conditions, or materials do not fit the claimed prescriptive Part 9 route | Depends until the available design route is established; yes if Part 4 is used | Relevant structural or geotechnical professional | NBC(AE) 2023 p2, Div B, Article 9.4.1.1. [PDF pp.836-837]; Div C, Sentence 2.4.1.2.(1) [PDF p.740]. |
| Wood roof trusses and truss assemblies in Part 9 buildings | Yes for engineering design and authentication | Alberta-authorized engineering professional skilled in truss design and assembly connections | NBC(AE) 2023 p2, Div B, Sentences 9.23.14.11.(1) and (2) [PDF p.986]; Div C, Sentence 2.4.1.2.(1) [PDF p.740]. W6 supplies the provincial interpretation. |
| Edmonton new single-family/semi-detached homes and three- or four-unit rowhouses with roof trusses, application on or after March 1, 2026 | Yes, authenticated assemblies with permit application | Alberta-licensed engineering professional | W7, B23-03, PDF page 1, revised February 4, 2026. This is local submission timing. |
| Standard detached Edmonton garage with no living space, attic storage, or loft | No under the bulletin's stated local submission exception; depends for other design duties | Confirm scope and current AHJ conditions | W7, B23-03, PDF page 1. This does not repeal provincial truss design rules. |
| General professional-involvement building with an automatic suppression system | Yes for design, field review, and witnessing testing | Professional qualified for the suppression system | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.3.(1) [PDF p.740]. |
| General professional-involvement building with a fire-alarm system | Yes for design, field review, and witnessing verification | Professional qualified for the fire-alarm system | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.4.(1) [PDF p.740]. |
| An otherwise excepted project raises special safety concerns because of size or complexity | Depends until AHJ decision; yes to the required scope once directed | One or more professionals in the affected disciplines | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(4) [PDF p.740]. |
| Alternative-solution request consisting only of factual intake and verified citation assembly | No automatic engineering requirement solely because it is a variance form | Named responsible designer still needs appropriate qualifications; legal and technical triggers remain | NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(4) and (6) [PDF p.739]. These sentences do not create a universal engineer-only authorship rule. |
| Alternative solution requires structural, fire/smoke, material-performance, or system-integration judgments | Depends on the activity and legal exceptions; professional referral is needed before the tool produces the judgment | Relevant competent engineering professional, with architectural input where needed | W1, sections 1(q) and 2; W2, sections 1(l) and 2. NBC(AE) 2023 p2, Div C, Sentences 2.4.1.1.(3)-(4) and 2.4.1.2.(1) [PDF p.740]. |
| More than one person takes responsibility for alternative-solution design aspects | Yes, one identified coordinator; the sentence itself does not require that coordinator to be registered | One named person, plus the legally required design professionals | NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(6) [PDF p.739]. |
| Edmonton Point Access Block application, including a Part 9 case | Yes under the city's mandatory application criteria | Registered architect and/or engineers for relevant design and field review; qualified Fire Protection or Life Safety Code Consultant for the alternative solution | W8, PDF pages 4 and 8. Consultant competence must match fire protection work; the job title alone is insufficient. |
| Alternative solution changes responder access, relies on intervention assumptions, or adds unfamiliar operational systems | Depends on scope; emergency-impact professional analysis and local peer review may be required | Competent fire-protection designer; affected professionals of record and EFRS/SCPI reviewers | W9, PDF pages 3, 8-9 and 20-22. |
| A supplier, AI system, or unlicensed third party provides calculations or modelling to support a design | Depends on the service; no automatic acceptance from origin or software output | The responsible licensed professional assesses reliance and takes responsibility where required | W3, sections 2.1 and 3.1; W4, sections 3.1-3.2. |
| Someone supplies a foreign professional stamp for work used in Alberta | Depends on Alberta authority and authentication; foreign seal alone does not settle it | Alberta-authorized professional in the proper scope, and permit-holder validation if applicable | W3, reference 3.3; W4, reference 5.1. |
| Required coordinating professional or professional of record leaves the project | Yes, replacement and new schedule before affected work resumes | Replacement CRP or professional of record in the appropriate discipline | NBC(AE) 2023 p2, Div C, Sentences 2.4.2.5.(1) and (2) [PDF p.742]. |
| Interior-only work proposed for a licensed interior designer | Depends on regulated interior-design scope and interfaces | Licensed interior designer within lawful scope; other professionals for excluded work | NBC(AE) 2023 p2, Div A, Article 1.4.1.2. [PDF p.50]; W2, s.2.1, PDF page 11. |

### Statutory sign-off and Safety Codes Officer powers

The Safety Codes Act puts duties on designers and on professionals who affix stamps or seals. A person who creates, alters, controls, owns, or offers a design for others must ensure it complies with the Act and is submitted or registered where the Act requires. W13, section 6, PDF p.13. A person permitted to affix a stamp or seal under the Architects Act or the Engineering and Geoscience Professions Act must ensure that the professional services they render, including stamping and sealing, comply with the Act. W13, section 11, PDF p.14.

Where the regulations require a design to be submitted or registered and to bear a stamp or seal, no permit may be issued for it unless it is signed, stamped, and sealed in accordance with the regulations. W13, section 45(1), PDF p.35. The regulation-making power for design signature and seal requirements is at W13, PDF p.53. Its section number was not captured in this pass.

The Administrative Items Regulation lets a safety codes officer require seals and stamps, and in some cases review during construction, where the size or complexity of a project may give rise to safety concerns. W15, PDF pp.2-3, quotes section 18 of that regulation. The regulation itself is not in the reference corpus, so this sheet records only the quotation. UNVERIFIED against the regulation's own text.

The SCO's role differs from the professional's role. The 2019 SCC notice says an SCO may review a variance proposed by a registered architect or engineer. The professional must demonstrate that the proposal meets the objectives and gives approximately equivalent or greater safety performance. The SCO may discuss the proposal, but may not engage in the practice of engineering or architecture by substituting their own design proposals for the professional's solution, even if the SCO is a registered professional member. W14, PDF p.2. Calgary's guide adds that an SCO may ask the architect to take part, because responsibility for the design lies with the architect. W10, PDF p.2.

For the tool, this means a variance that depends on engineering judgment needs the responsible professional's own analysis. The tool may point the reviewing SCO to the professional's documents. It must not supply the missing engineering reasoning or a replacement design.

### The tool stops here

The product's boundary is completeness and citation correctness. These are limits on this research deliverable's proposed use, rather than new licensing rules.

| The tool may check or assemble | Professional or authority decision where it stops |
|---|---|
| Collect occupancy, storeys, building area, unit counts, and location | Resolve disputed code classification, legal exceptions, and the required combination of professional disciplines |
| Show the relevant code exception and identify a missing fact | Declare that a project is exempt despite unresolved component, safety, or local requirements |
| Identify the author, licence claims, report date, scope, authentication fields, and named coordinator | Certify competence, scope-of-practice authority, or the technical validity of a sealed report |
| Match citations and objective/function pairs to verified source rows | Conclude that the proposed alternative achieves equal or better performance |
| List the required calculations, scenarios, tests, inspections, and continuing conditions | Perform or approve project-specific load design, connection design, fire/smoke modelling, tenability/risk decisions, or professional judgment of evidence sufficiency |
| Flag absent or inconsistent authentication information | Add, imitate, reuse, or authorize a professional stamp, signature, digital credential, or schedule assurance |
| Track A/B commitments and missing C-schedules | Sign the assurances, grant permission to occupy, or decide that incomplete field reviews can be waived |
| Record that Edmonton review is required and identify the reviewers | Promise a fire-service response, prescribe operational tactics, or give variance acceptance |

A generated Section D checklist must name the responsible professional and the work still required. It must not contain invented calculations, conclusions, test results, design signatures, or claims that a professional has reviewed it. A disclaimer or a later stamp request does not replace actual professional control and responsibility. W3, reference 2.1; W4, reference 3.1.

A professional may use tools and rely on others subject to the regulator's rules. That possibility does not authorize this product to make the professional judgment for them. If it is unclear whether the planned service is exempt or reserved, record the uncertainty and obtain a determination from the appropriate professional/regulator and AHJ. Do not infer an exemption from the applicant's confidence or a supplier's assurance.

## Interactions with other topics

| Related topic | Shared issue | Boundary of this sheet |
|---|---|---|
| [process-and-admin](process-and-admin.md) | Owner/agent roles, permit stage, AHJ requests, retention and schedules | Identifies professional duties and missing responsibility evidence, without issuing an approval |
| [code-structure-and-attribution](code-structure-and-attribution.md) | Correct edition, division, root sentence, objective/function pairs, and national intent context | Keeps administrative duties separate from technical performance attributions |
| [evidence-and-conformity](evidence-and-conformity.md) | Product evaluation, testing, certification, scope and limitations | Identifies who must assess project applicability or integration |
| [structural-and-framing](structural-and-framing.md) | Part 9 limits, Part 4 design, roof trusses, connections, foundations, load paths | Flags engineering responsibility and field-review duties |
| [egress-and-single-stair](egress-and-single-stair.md) | Point Access Blocks and single-exit comparisons | Establishes mandatory professional involvement and the boundary before technical equivalency judgment |
| [firefighting-alarms-sprinklers](firefighting-alarms-sprinklers.md) | System design, field reviews, witnessing testing/verification, emergency operations | Names responsible disciplines and local peer-review expectations |
| [fire-separations-and-spatial-separation](fire-separations-and-spatial-separation.md) | Engineering analysis, fire-service assumptions, protection of egress and adjacent property | Flags specialist review; does not compute fire ratings or exposure equivalency |
| [building-envelope-insulation-cladding](building-envelope-insulation-cladding.md) | Specialty design, structural/fire/envelope interfaces, moisture protection | Requires clear discipline scope and coordination when professional involvement applies |
| [housing-secondary-suites-part9](housing-secondary-suites-part9.md) | Principal units versus secondary suites, code route versus professional exception | Does not assume every extra dwelling is a qualifying secondary suite |
| [hvac-ventilation-plumbing](hvac-ventilation-plumbing.md) | Mechanical design, smoke systems, controls, commissioning and operation | Flags project-specific design responsibility and interfaces |
| [energy-efficiency](energy-efficiency.md) | Model authorship, assumptions and performance-route documentation | Does not assume every energy model is reserved engineering or that any energy adviser can cover all engineering work |
| [occupancy-and-accessibility](occupancy-and-accessibility.md) | Classification, population needs, architectural/interior-design scope | Requires the relevant authorized professional when work or project rules trigger involvement |
| [combustible-construction-and-mass-timber](combustible-construction-and-mass-timber.md) | Structural/fire specialist design and coordinated construction evidence | Does not convert a product evaluation into whole-building approval |

Cross-links identify related research scopes. They are not verification of another author's claims.

## Common refusal / "more info" causes

These are evidence gaps likely to prevent a completeness assessment or require further information. They are not a claim that an AHJ must refuse every listed case.

| Gap | Why it matters | Supporting source |
|---|---|---|
| No identified responsible designer or qualifications | The analysis must identify relevant qualifications, experience, and background. | NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(4) [PDF p.739]. |
| Several responsible designers but no single coordinator | The applicant must identify one coordinator for the alternative-solution design, code analysis, and documentation. | NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(6) [PDF p.739]. |
| "Part 9" used as the entire professional assessment | It leaves specific engineered components, professional law, and AHJ safety concerns unresolved. | NBC(AE) 2023 p2, Div C, Sentences 2.4.1.1.(4) and 2.4.1.2.(1) [PDF p.740]. |
| Engineer's stamp supplied without architectural or other required discipline coverage | The design needs the appropriate combination of professional practices. | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(3) [PDF p.740]. |
| Required schedules missing or inconsistent with report scope | The owner and professionals have distinct commitments and completion assurances. | NBC(AE) 2023 p2, Div C, Articles 2.4.2.2. to 2.4.2.4. [PDF pp.741-742]. |
| Draft, generic supplier detail, or stamp image presented as final professional responsibility | It does not establish intended-use authentication and responsibility. | W3, sections 3.1-3.3 and 4.2. |
| Truss profiles authenticated but interconnections left outside every authenticated document | Provincial interpretation requires complete assembly design responsibility where applicable. | W6, PDF pages 1 and 3; W7, PDF page 1. |
| An archived temporary truss bulletin used to claim no engineering is needed now | It conflicts with the current implementation identified by Edmonton. | W7, PDF page 1; W11 records the archived history. |
| Calgary supporting documents lack stamps/seals when the project or subject requires a professional | The city's guide expressly asks for them in that circumstance. | W10, PDF page 3. |
| Point Access Block lacks a qualified consultant or professional involvement | It fails Edmonton's minimum application criteria. | W8, PDF page 8. |
| Single-exit case addresses occupant evacuation but ignores emergency response or fire spread | It omits attributed functions/objectives relevant to the root provision. | NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269]; Table 3.10.1.1. [PDF p.346]. |
| Emergency-response assumptions are unsupported or continuing maintenance responsibility is missing | The design needs justified assumptions and documented operational conditions. | NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(2) and (3) [PDF p.739]; W9, PDF pages 20-22. |
| Required professional left but affected construction continues without replacement/schedule | The code requires a stop to the affected work. | NBC(AE) 2023 p2, Div C, Article 2.4.2.5. [PDF p.742]. |
| A technically polished narrative states equivalency without adequate analysis | The code requires enough detail to support the validity, accuracy, relevance, and precision of the analysis. | NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(5) [PDF p.739]. |

## Precedents

### Provincial roof-truss interpretation and the changed transition

STANDATA 23-BCI-015R1 is a May 2025 interpretation concerning Part 9 roof-truss assemblies. It requires a registered engineering professional to design and authenticate the trusses, including interconnections where applicable. It permits the designer to communicate that information in separate authenticated documents rather than requiring a stamp on every layout drawing. It also addresses submission before inspection/covering through permit conditions. W6, PDF pages 1 and 3.

Its Alberta code basis was checked directly in NBC(AE) 2023 p2, Div B, Sentences 9.23.14.11.(1) to (3) [PDF p.986]; Note A-9.23.14.11.(2) [PDF p.1418]; Div C, Sentence 2.4.1.2.(1) [PDF p.740].

The archived bulletin 23-BCB-002R1 allowed a temporary position for roof-truss layouts/profiles in one- and two-family dwellings. It is historical context. Edmonton's current B23-03 says that bulletin has been archived and the interpretation fully implemented for the March 1, 2026 change. Do not use the old temporary position as a current exemption. W11, historical bulletin, PDF pages 1-2; W7, PDF page 1.

### Edmonton B23-03

The verified B23-03 PDF is revised February 4, 2026. It calls for authenticated roof-truss assemblies with applications for the listed Part 9 homes and rowhouses from March 1, 2026. It distinguishes an unauthenticated placement/layout document from missing authenticated assembly-design information. Its standard detached-garage exception has living-space, attic-storage, and loft qualifications. These are local submission requirements and conditions. They do not authorize the tool to perform truss design. W7, PDF page 1.

The live download matched the saved source PDF byte for byte. The municipal application page also states the March 1, 2026 requirement. A search returned an older November 2025 revision under a different cache query; that version was not used as the current rule.

### Edmonton Point Access Block guide

The supplied Alternative Solution Guide, issued February 28, 2025, requires professional design/field review and properly authenticated/validated plans. It also requires an alternative solution prepared by a qualified Fire Protection or Life Safety Code Consultant. Its example analysis is guidance, not automatic approval for a project. W8, supplied guide PDF pages 4-5 and 8.

The housing page links a separate five-page introduction. Its contents page identifies the Alternative Solution Guide. The actual eight-page Alternative Solution Guide was then downloaded directly from Edmonton and matched the supplied source byte for byte. The introduction is not the source of the mandatory criteria. W8 identifies the verified eight-page source URL.

### Edmonton emergency-services guide

COE-IM-GUIDE-0040, version 01, dated April 15, 2025, describes professional assessment and EFRS/SCPI peer review for designs affecting emergency response. A demonstrated absence of additional or unique responder impact can remove the need for additional responder-impact analysis. The guide does not say every variance needs the same analysis. W9, PDF pages 3 and 8-9.

Its discussion of substantiated performance and continuing maintenance/commissioning responsibilities is relevant when an applicant supplies only a professional opinion without its supporting analysis. W9, PDF pages 20-22. The current download matched the saved source PDF byte for byte.

### Calgary application guide

Calgary's guide, dated November 23, 2023, asks for supporting documents to be stamped and sealed when the project or subject of the variance requires a professional. It recommends retaining a code-familiar consultant if the applicant lacks the relevant knowledge. The professional condition is not a statement that every Calgary variance needs an engineer. W10, PDF pages 1 and 3. The current download matched the saved source PDF byte for byte.

### Variances and STANDATAs that attach a professional condition

These are precedents, not general rules. Each applies only to its own subject, edition, and date.

- Calgary SPV-004, dated February 25, 2020, concerns ventilation under the 2019 Alberta edition. It requires the engineer of record to review, sign, and seal the mechanical drawings. W16, source p.2. Its current status was not checked, so treat it as historical.
- Calgary SPV-006, dated June 19, 2025, concerns a firewall in a rowhouse with secondary suites. It states that a site-specific variance to Division B Sentence 9.10.11.2.(2) requires professional involvement as part of the application. W16, source p.1.
- STANDATA 23-BCV-002, May 2024, concerns review of off-site constructed buildings. It states that the verification is done by registered architectural or engineering professionals under NBC(AE) Division C Subsections 2.4.2 and 2.5. W16, source p.2.
- STANDATA 23-BCV-005, May 2024, concerns occupancy classification of oil and gas processing buildings. Its conditions include a building area of no more than 150 m² and a risk assessment prepared by an Alberta-licensed registered engineering professional. The professional's recommendations must be listed in the permit application. W16, source pp.2-3.
- STANDATA 23-BCV-010, February 2025, is titled "Building Engineer authentication for the qualification of structural steel fabricators." W16, source pp.1-2.
- STANDATA interpretation 23-BCI-003R1, on occupant load, states that incorporating the exit occupant load into the design is the responsibility of the registered architectural professional under the practice of architecture in the Architects Act. Other professionals need the stated design occupant load. W16, source p.1. Its issue date was not captured in this pass.

The Calgary and Edmonton guides and these precedents show that professional involvement is often a condition of a variance. They do not show that every variance needs an engineer or architect, and the list is not complete.

No Calgary Standing Posted Variance or CCMC evaluation was verified that exempts a project from professional legislation or the code's professional requirements. Do not treat either as a substitute for determining who is responsible for design and field reviews.

## Worked example

### Hypothetical Edmonton single-stair application

The owner proposes a four-storey, sixteen-unit residential apartment building with a 400 m² building area. Four apartments on each floor share one enclosed exit stair. The design does not give each upper unit a separate exterior exit or a second independent way out. The owner proposes enhanced fire/life-safety measures and asks the tool to prepare the variance application.

These dimensions and proposed features are scenario facts. No actual project approval, calculation, test, or professional appointment is asserted.

### Route and benchmark

1. Four storeys places this Group C building outside the Part 9 height limit. The applicable general route is Parts 3, 4, 5 and 6. NBC(AE) 2023 p2, Div A, Sentence 1.3.3.2.(1) [PDF pp.39-40]; Sentence 1.3.3.3.(1) [PDF p.40].
2. Sixteen principal units fall outside the small multiple-family dwelling exception. The project needs appropriate professional design and the schedules regime. NBC(AE) 2023 p2, Div C, Clause 2.4.1.1.(1)(b) [PDF p.739]; Sentence 2.4.1.1.(3) [PDF p.740]; Sentences 2.4.2.1.(1) and 2.4.2.2.(1) [PDF p.741].
3. The technical benchmark is at least two exits from each occupied floor area, subject to the stated exceptions. The two-storey single-exit exception does not cover this four-storey case. The separate dwelling-unit exception must be checked on actual plans, rather than assumed from the word "apartment." NBC(AE) 2023 p2, Div B, Sentences 3.4.2.1.(1), (2) and (4) [PDF pp.269-270]; Article 3.3.4.4. [PDF pp.263-264].
4. Edmonton's Point Access Block criteria add the qualified consultant and professional design/field-review requirements. W8, supplied guide PDF pages 4 and 8.

For this mini-case, assume the appointed professional confirms on the actual plans that no prescriptive single-exit exception covers the proposed common-floor arrangement. The comparison below addresses that identified departure. It does not establish that every other technical provision is satisfied.

### Section C table

Applicable code is NBC(AE) 2023, second printing. The rows separate the three objective groups so the emergency-response and property-protection purposes are not lost.

| Acceptable-solution article/sentence | Objective | Function | Intent statement, paraphrased and sourced |
|---|---|---|---|
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269] | OS3.7 | F10, F12, F05 and F06. [F10,F12,F05,F06-OS3.7] (Div B Table 3.10.1.1. [PDF p.346]) | Provide a choice of route if an exit is blocked, so occupants and responders can reach a safe place without harmful delay. NBC 2020 Intent Statements, 3.4.2.1.(1) [PDF pp.608-609], explanatory context. |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269] | OS1.2 | F12 and F06. [F12,F06-OS1.2] (Div B Table 3.10.1.1. [PDF p.346]) | Maintain responder access when a route is blocked so delayed or ineffective response does not increase fire spread and harm people. NBC 2020 Intent Statements, 3.4.2.1.(1) [PDF p.609], explanatory context. |
| NBC(AE) 2023 p2, Div B, Sentence 3.4.2.1.(1) [PDF p.269] | OP1.2 | F12 and F06. [F12,F06-OP1.2] (Div B Table 3.10.1.1. [PDF p.346]) | Maintain responder access to reduce fire spread and resulting damage to the building when one route is obstructed. NBC 2020 Intent Statements, 3.4.2.1.(1) [PDF p.609], explanatory context. |

The functions cover protection of egress and emergency-response facilities, timely movement to safety, and emergency response. NBC(AE) 2023 p2, Div A, Article 3.2.1.1. [PDF pp.79-80]. The table states the verified benchmark purposes; it does not state that the proposed measures meet them.

### Professional responsibility and Section D evidence

| Document or task to identify in Section D | Responsible party | Current status in this hypothetical case |
|---|---|---|
| Project code analysis and complete list of technical departures | Appropriate designer and coordinating registered professional, with the qualified fire/life-safety consultant | Required; not supplied by this example |
| Alternative-solution performance analysis covering blocked-stair scenarios, evacuation, responder access, and relevant fire spread/property effects | Competent qualified fire-protection/life-safety professional, with the appropriate Alberta authorization for any reserved practice | Required; no equivalency conclusion generated |
| Architectural design and affected structural, mechanical, electrical, and fire-system interfaces | Appropriate professionals of record and any delegated specialists | Appointment/scope evidence and authenticated final documents required |
| Justified emergency-response assumptions and EFRS/SCPI coordination where impacts arise | Responsible design professional and local review authorities | Local assessment and review remain open |
| Operational conditions, maintenance, inspection/testing and commissioning responsibilities | Relevant design professionals and owner/operator | Required conditions and responsible parties must be documented |
| Schedules A/B and field-review commitments, followed by C-schedules at completion | Owner, CRP, professionals of record, and delegated professionals as applicable | Commitments and completion evidence must be tracked at the proper stage |

Documentation basis is NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(2) to (6) [PDF p.739]. Schedules and professional duties are in Articles 2.4.2.2. to 2.4.2.4. [PDF pp.741-742]. Local responder-impact and continuing-system guidance is in W9, PDF pages 3, 8-9 and 20-22.

### Result the tool can truthfully return

The benchmark and its three attribution groups are identified. Professional involvement is required on these project facts. Section D needs named responsible professionals and the listed supporting work. Technical equivalency and acceptance remain unassessed. The tool must stop before selecting adequate mitigation levels, computing tenability/risk, signing assurances, or stating that the single stair is safe or approved.

### Part 9 comparison

If the scenario were instead a three-storey, six-unit building with the same 400 m² building area and Group C occupancy, it could fit the Part 9 size/use route. Six principal units would still exceed the general professional exception for a four-unit multiple-family dwelling. The selected egress benchmark would then need to be established under the applicable Part 9 provisions; the Part 3 Section C table above must not be copied across automatically. NBC(AE) 2023 p2, Div A, Sentence 1.3.3.3.(1) [PDF p.40]; Div C, Clause 2.4.1.1.(1)(b) [PDF p.739] and Sentence 2.4.1.1.(3) [PDF p.740].

## Open questions / uncertainty

- UNVERIFIED: whether a particular applicant's activity falls within an exemption from reserved engineering or architectural practice. The Acts and code tests are documented here, but their application to disputed facts is for the relevant regulator, authorized professional, and AHJ. The tool must not resolve that dispute by assuming every calculation is engineering or every small-building activity is exempt.
- UNVERIFIED: the required professional disciplines, competence, licence scope, or firm authorization for any real project. No named person's registration or contract was supplied. A licence title alone does not establish that scope.
- UNVERIFIED: treatment of secondary suites under the professional Acts in a disputed unit-count case. The code expressly says secondary suites need not count for its general exception; the Act excerpts reviewed use their own dwelling-unit language. The code rule must not silently be copied into the Acts.
- UNVERIFIED: whether an AHJ will require the full A/B/C schedules for a component-only professional engagement in an otherwise excepted project. The code's schedules application is tied to the general professional-involvement category. Any broader local request must be checked for the actual application. NBC(AE) 2023 p2, Div C, Sentence 2.4.2.1.(1) [PDF p.741].
- UNVERIFIED: the current local submission timing for roof-truss documents outside Edmonton. Provincial STANDATA allows permit conditions tied to inspection/covering; Edmonton asks for the listed documents at application. Do not generalize Edmonton's timing to another municipality. W6 and W7.
- UNVERIFIED: a particular detached garage's entitlement to the B23-03 local exception, or whether separate structural or safety concerns require engineering. The bulletin's local submission exception does not erase other requirements.
- UNVERIFIED: any issued project-specific Point Access Block approval, any accepted mitigation package for the worked example, or any certification/CCMC exemption from professional law. No such approval was established in this research.
- The current official Acts retrieved on 2026-10-18 label their consolidations December 7, 2023 for W1 and November 16, 2022 for W2. Those are publication consolidation dates, not this research's access dates. No future or merely proposed legislative change is treated as in force.
- The B23-03 introduction contains the identifier `23-BCI-05R1`, while its substantive discussion and the downloaded provincial document identify `23-BCI-015R1`. This sheet relies on the verified latter document and does not invent a second interpretation.
- The Point Access Block source-location issue is resolved. The five-page introduction and eight-page Alternative Solution Guide are different files. The latter was reacquired from Edmonton and matched the supplied guide byte for byte, including its mandatory criteria.
- The national intent supplement has similarly numbered farm-building provisions. They were not used as intents for Alberta Division C. No professional-involvement attribution or missing administrative intent was invented.
- The sources establish responsibility and submission requirements. They do not establish that any proposed engineering analysis, mitigation, signature, licence status, or construction is technically valid.

### Access and tool limitations

The web fetcher returned 502 for Edmonton HTML pages and 403 for a provincial PDF. Python's default TLS trust also failed during the first download attempt. Standard `curl` downloads succeeded without disabling certificate verification. The saved receipts identify the retrieved official URLs and hashes.

Jev search returned `fail_open`, `decision: unknown`, and `screening: local-only` because its network service was unavailable. It supplied no sufficiency judgment. Primary-source selection and verification continued directly. No source claim rests on its ranking.

The citation validator checks recognized code references. It cannot validate legal interpretation, professional qualifications, the adequacy of a technical case, or whether every relevant technical provision has been identified. Manual source checks remain necessary.

## Sources

All access/review dates in this registry are 2026-10-18. The sources below are primary code, legislation, regulator publications, municipal guidance, or the supplied product brief. Web sources state the claim they support. Topic downloads, page-text extracts, hashes and validation receipts are in `reference/web/professional-involvement/`.

### Adopted Alberta code

`reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf` and its page-text extraction in `reference/text/`. The source is NBC(AE) 2023, second printing, containing both volumes. No first-printing or national-model text was used as Alberta law.

| Division | Provision checked | Source location and use |
|---|---|---|
| A | NBC(AE) 2023 p2, Div A, Article 1.2.1.1. [PDF p.38] | Alternative-solution minimum-performance comparison |
| A | NBC(AE) 2023 p2, Div A, Article 1.3.3.2. [PDF pp.39-40] | Parts 3, 4, 5 and 6 route |
| A | NBC(AE) 2023 p2, Div A, Article 1.3.3.3. [PDF p.40] | Part 9 eligibility |
| A | NBC(AE) 2023 p2, Div A, Article 1.4.1.2. [PDF pp.49-50] | Professional permit holder, registered professional, CRP and professional-of-record definitions |
| A | NBC(AE) 2023 p2, Div A, Article 3.2.1.1. [PDF pp.79-80] | Functions used in the worked example |
| B | NBC(AE) 2023 p2, Div B, Article 3.3.4.4. [PDF pp.263-264] | Dwelling-unit egress referral check in the worked example |
| B | NBC(AE) 2023 p2, Div B, Article 3.4.2.1. [PDF pp.269-270] | Exit-number benchmark and exceptions |
| B | NBC(AE) 2023 p2, Div B, Table 3.10.1.1. [PDF p.346] | Verified exit-number attributions |
| B | NBC(AE) 2023 p2, Div B, Article 9.4.1.1. [PDF pp.836-837] | Structural design routes and limits |
| B | NBC(AE) 2023 p2, Div B, Article 9.23.14.11. [PDF p.986] | Roof truss design, connections and bracing |
| B | NBC(AE) 2023 p2, Div B, Table 9.38.1.1. [PDF p.1189] | Verified roof-truss attributions and conditional fire group |
| B | NBC(AE) 2023 p2, Div B, Note A-9.23.14.11.(2) [PDF p.1418] | Explanatory professional-design rationale |
| C | NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739] | Documentation, qualifications and coordination |
| C | NBC(AE) 2023 p2, Div C, Article 2.4.1.1. [PDF pp.739-740] | General professional exceptions and overrides |
| C | NBC(AE) 2023 p2, Div C, Article 2.4.1.2. [PDF p.740] | Part 4 structural design and foundation field review |
| C | NBC(AE) 2023 p2, Div C, Article 2.4.1.3. [PDF p.740] | Fire-suppression professional duty |
| C | NBC(AE) 2023 p2, Div C, Article 2.4.1.4. [PDF p.740] | Fire-alarm professional duty |
| C | NBC(AE) 2023 p2, Div C, Article 2.4.2.1. [PDF p.741] | Schedules application |
| C | NBC(AE) 2023 p2, Div C, Article 2.4.2.2. [PDF p.741] | Owner's professional retention and A/B schedules |
| C | NBC(AE) 2023 p2, Div C, Article 2.4.2.3. [PDF pp.741-742] | CRP, professional-of-record and delegated roles |
| C | NBC(AE) 2023 p2, Div C, Article 2.4.2.4. [PDF p.742] | C-1 before occupancy permission |
| C | NBC(AE) 2023 p2, Div C, Article 2.4.2.5. [PDF p.742] | Stop/replacement requirements |

The CRP definition is also on source PDF page 44. Administrative explanatory notes are on source PDF page 744. Appendix B titles and forms were read on source PDF pages 745 and 747-759, including the amended A/B pages. The code body supplies the legal duties; the forms supply the actual commitments and assurance workflow.

### National explanatory intent supplement

`reference/codes/` supplied NBC 2020 intent supplement, searchable as `NBC-2020-Intent-Statements` in `reference/text/`. It is explanatory context only.

- NBC 2020 Intent Statements, 3.4.2.1.(1) [PDF pp.608-609]. Exit choice, responder access, harm to people and property effects.
- NBC 2020 Intent Statements, 9.4.1.1.(1) to (3) [PDF p.1206]. Structural route and applicability explanations.
- NBC 2020 Intent Statements, 9.23.14.11.(1) to (3) [PDF pp.2430-2432]. Truss strength/stiffness, connection-design referral, bracing, environmental separation and conditional fire effects.

### W1. Engineering and Geoscience Professions Act

URL: https://kings-printer.alberta.ca/documents/Acts/E11.pdf . Accessed 2026-10-18. Official consolidation labelled current as of December 7, 2023.

Read section 1(q), sections 2(1), 2(4)-(7), and relevant title/seal provisions in section 3, source PDF pages 10 and 12-16. Supports the engineering definition, reserved-practice rule and express exceptions. Local source is `engineering-geoscience-professions-act.pdf` with a page-text JSONL receipt in the topic download folder.

### W2. Architects Act

URL: https://kings-printer.alberta.ca/documents/Acts/A44.pdf . Accessed 2026-10-18. Official consolidation labelled current as of November 16, 2022.

Read sections 1(l), 2, 2.1 and 3, source PDF pages 7-12. Supports the architecture definition, authorized practice and exceptions, restricted interior-design scope, and limits on assuming combined architectural/engineering authority. Local source is `architects-act.pdf`.

### W3. APEGA authentication standard

URL: https://www.apega.ca/docs/default-source/pdfs/standards-guidelines/authenticating-professional-work-products.pdf?sfvrsn=5a1b9b57_30 . Accessed 2026-10-18. Authenticating Professional Work Products, November 1, 2024, version 8.6.

Read references 2.1-2.2, 3.1-3.5 and 4.2, source PDF pages 12-19. Supports professional responsibility, authentication's intended-use test, separate validation, imported work, engineered-goods interfaces, and physical/digital authentication requirements. Local source is `apega-authenticating-work-products-2024.pdf`.

Status page: https://www.apega.ca/about-apega/publications/standards-guidelines/ . Accessed 2026-10-18. It lists the November 2024 authentication standard as in effect and the May 2021 reliance standard as in effect, enforceable May 1, 2022.

### W4. APEGA reliance/outsourcing standard

URL: https://www.apega.ca/docs/default-source/pdfs/standards-guidelines/relying-on-the-work-of-others-and-outsourcing.pdf?sfvrsn=45759b55_22 . Accessed 2026-10-18. Relying on the Work of Others and Outsourcing, May 2021.

Read references 3.1-3.3 and 5.1, source PDF pages 10-17. Supports direct supervision/control, thorough review, reliance on other work, outsourcing plans, authentication responsibility, and interfaces. Local source is `apega-relying-outsourcing-2021.pdf`.

### W5. Joint AAA/APEGA schedules user guide

URL: https://www.apega.ca/docs/default-source/pdfs/standards-guidelines/aaa-apega_nationalbuildingcodeschedulesuserguide_final.pdf?sfvrsn=5312af63_18 . Accessed 2026-10-18. National Building Code, Alberta Edition, Schedules User Guide, May 1, 2024.

Read source PDF pages 4-10. Supports responsibility allocation, documented code analysis, professionals of record, delegated work, interfaces and the flow of A/B/C assurances. Local source is `aaa-apega-schedules-user-guide-2024.pdf`. The code's second-printing forms and duties were checked independently.

### W6. Provincial truss interpretation

URL: https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/750b7bd6-7a6a-47b8-8acf-bd58298f672b/download/ma-standata-interpretation-building-23-bci-015r1-2025-05.pdf . Accessed 2026-10-18. STANDATA 23-BCI-015R1, May 2025.

Read source PDF pages 1-3. Supports engineering design/authentication for truss assemblies and interconnections, flexible document placement, and inspection/covering submission conditions. Read through the existing extracted source and reacquired as `alberta-23-bci-015r1.pdf`.

### W7. Edmonton roof-truss policy

URL: https://www.edmonton.ca/sites/default/files/public-files/PolicyBulletin-B23-03-Roof-Truss-Engineering-Requirements.pdf . Accessed 2026-10-18. Policy Bulletin B23-03, revised February 4, 2026, source PDF page 1.

Supports the March 1, 2026 permit-application requirement for the listed Part 9 buildings, assembly/interconnection documentation, and the qualified detached-garage submission exception. Reacquired as `edmonton-b23-03-live.pdf`; byte-identical to the supplied precedent PDF.

Live application page: https://www.edmonton.ca/residential_neighbourhoods/application-requirements-house-permits . Accessed 2026-10-18 and saved as `edmonton-house-permits.html`. Supports the current municipal application requirement and the policy's live link.

### W8. Edmonton Point Access Block alternative-solution guide

URL: https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Alternative-Solution-Guide.pdf . Accessed 2026-10-18. Eight-page Alternative Solution Guide, issued February 28, 2025.

Read source PDF pages 2-8, especially application requirements on page 4 and mandatory criteria on page 8. Supports required professional involvement and the qualified Fire Protection or Life Safety Code Consultant. Reacquired as `edmonton-point-access-block-alternative-solution-guide.pdf`; byte-identical to `reference/guides/Edmonton-Point-Access-Block-Guide.pdf`.

The separate introduction is https://www.edmonton.ca/sites/default/files/public-files/Point-Access-Block-Introduction-to-Guide.pdf?cb=1755190398 . Accessed 2026-10-18. Its five-page contents identify the other guide components. It does not contain the mandatory-criteria text used here. The linking page is https://www.edmonton.ca/programs_services/programs-housing , accessed 2026-10-18 and saved as `edmonton-housing.html`.

### W9. Edmonton emergency-services guide

URL: https://www.edmonton.ca/sites/default/files/public-files/COE-IM-GUIDE-0040-v01-20250415%20Guideline%20for%20Alternative%20Solutions%20Affecting%20Emergency%20Services.pdf?cb=1745629775 . Accessed 2026-10-18. COE-IM-GUIDE-0040, version 01, April 15, 2025.

Read source PDF pages 3, 6-9 and 20-22. Supports professional assessment, EFRS/SCPI peer review for responder impacts, justified assumptions, performance evidence, and continuing system responsibilities. Reacquired as `edmonton-emergency-services-live.pdf`; byte-identical to the supplied guide.

### W10. Calgary alternative-solution guide

URL: https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf . Accessed 2026-10-18. Guide to Applying for an Alternative Solution (Variance), November 23, 2023.

Read source PDF pages 1-4, especially page 3. Supports consultant involvement where code familiarity is lacking and stamped/sealed supporting documents where the project or subject requires a professional. Reacquired as `calgary-alternative-solution-guide-live.pdf`; byte-identical to the supplied guide. Historical code/appeal statements in older Calgary guides are not adopted here as current law.

### W11. Archived provincial truss bulletin, historical context

URL: https://open.alberta.ca/dataset/5cd7e000-4f7c-4188-b26f-11a16bbe43f8/resource/a3c87875-2f52-48f3-aed2-012c781d6cf5/download/ma-standata-bulletin-building-23-bcb-002r1-2025-08.pdf . Access/review date 2026-10-18 through the saved provincial source and its extracted text. STANDATA 23-BCB-002R1, August 2025, source PDF pages 1-4.

Supports only the historical temporary treatment of one- and two-family truss documentation. Its archived status and subsequent implementation are corroborated by W7. It is not cited as a current exemption.

### W12. Engineering and Geoscience Professions General Regulation

URL: https://kings-printer.alberta.ca/documents/Regs/1999_150.pdf . Accessed 2026-10-18. Alberta Regulation 150/99.

Read source PDF pages 27-30, particularly sections 49 and 54. Supports the statutory background to final professional documents, permit number, supervision/control or thorough review, and signature/date requirements discussed in W3. Local source is `apega-general-regulation.pdf`.

### Additional reference-corpus sources (2026-10-18 check)

- W13. Safety Codes Act, RSA 2000 c S-1, from `reference/text/Safety-Codes-Act-RSA2000-cS-1.jsonl`. Sections 6, 11, and 45(1) at PDF pp.13, 14 and 35, the table of contents at PDF p.6, and the regulation-making power at PDF p.53.
- W14. SCC notice on variances under the Safety Codes Act, 2019, from `reference/text/scc-notice-variances-under-safety-codes-act-2019.jsonl`, PDF p.2.
- W15. STANDATA 23-BCB-002R1, August 2025, from `reference/text/standata-nbc2023-bulletin-23-bcb-002r1.jsonl`, PDF pp.2-3. It quotes section 18 of the Administrative Items Regulation. The regulation itself is not in the corpus.
- W16. Variance and interpretation precedents from `reference/text/`: Calgary SPV-004 (PDF p.2), Calgary SPV-006 (PDF p.1), STANDATA 23-BCV-002 (PDF p.2), 23-BCV-005 (PDF pp.2-3), 23-BCV-010 (PDF pp.1-2), and 23-BCI-003R1 (PDF p.1).

### Product scope and method receipts

`reference/README-challenge.md`, reviewed 2026-10-18, defines the product's completeness/correct-citation scope, professional-involvement objective, and Section D boundary. The challenge appendix is not the authority for a building-code article number. All code claims above were checked against the second-printing code.

The existing `codedb` CLI was used because its help and lookups worked. `tools/codesearch.py` supplied independent source-page searches and reads. No database, tool, or unrelated research file was changed.

Methods actually read and applied:

- T3 workflow router: `~/.codex/skills/t3-workflow/SKILL.md` and `~/.codex/skills/t3-workflow/references/routes.md`. Scope, checkpointing, proportionate verification, and method reassessment. Parent maintenance receipt reused as instructed.
- Matt Pocock research: `~/.agents/skill-libraries/mattpocock/skills/engineering/research/SKILL.md`. Follow claims to primary sources and save one sourced fact sheet. No further delegation, as the task expressly prohibits it.
- pstack unslop: `~/.agents/skill-libraries/pstack/skills/unslop/SKILL.md`. Plain prose, specific attribution, explicit gaps, and no invented technical certainty.
- PDF reading: `~/.codex/plugins/cache/openai-primary-runtime/pdf/26.1017.11052/skills/pdf/SKILL.md`. Read page text and visually inspect the two attribution tables. Poppler was unavailable; macOS PDFKit rendered the source pages to PNG without altering the PDFs.
- Jev search: `~/.codex/skills/jev-search/SKILL.md`. One search-selection attempt returned local-only fail-open; no evidence-sufficiency claim was made.

This is a sourced text deliverable. No product UI was implemented, so no browser demo or product screenshot was required. The saved attribution-page renders are source-inspection evidence, not a product demo.

### Validation receipt

The final command was `.venv/bin/python -m codedb validate research/facts/professional-involvement.md --json`.

```json
{"ok": true, "files_checked": 1, "citations_checked": 370, "errors": [], "warnings": []}
```

The saved machine result is `reference/web/professional-involvement/validator-final.json`. The independent codesearch, exact-page, expanded-provision, note/table, and intent receipts are in `reference/web/professional-involvement/citation-audit.json`. Source URLs, download hashes, byte-match checks, and failed retrieval attempts are recorded in `reference/web/professional-involvement/sources.json`.

A clean validator report covers the references it recognizes. It is not professional certification, technical approval, or proof that a real project's full set of relevant provisions has been identified.
