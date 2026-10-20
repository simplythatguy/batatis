---
topic: evidence-and-conformity
scope: Evidence for Section D compliance and equivalence, product evaluation, conformity assessment, and limits on approval claims.
sources_checked:
  - NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2
  - NBC-2020-Intent-Statements (national explanatory supplement)
  - SCC-Variance-Form
  - Calgary-Alt-Solution-Guide
  - NRC-Accepting-Alternate-Solutions
  - CWC-Alternative-Solutions-Guide
  - STANDATA 23-BCI-005, 23-BCI-006, 23-BCI-007, 23-BCI-013, 23-BCI-026
  - reference/data/ccmc-registry.json
  - NRC PAS-001 and live CCMC 13016-R
  - Alberta and Calgary official web sources; ASTM scopes/catalogue
  - Official SCC, ICC-ES, SFPE, NFPA, and APEGA indexed excerpts as qualified in Sources
last_verified: 2026-10-18
---
# Evidence and conformity

## Progress

- Done: read the preamble, contracts, Wave 2 brief, topic scope, and research/writing methods; checked source inventory.
- Done: created the full report skeleton before substantive research.
- Done: all template sections, evidence-type and test-standard tables, recognition documents, and worked Section C/D example saved.
- Done: every cited article/table identifier re-searched in the extracted code; page text and key attribution/intent mappings checked.
- Done: database CLI lookups and validator used after the shared CLI became available; zero validation errors, with unbound-page warnings documented below.
- Outstanding: expressly marked source-access, accreditation-status, and technical-judgement limits; no pending drafting work.
- Tool status: the initial CLI attempt failed with missing `codedb.__main__`; the final attempt succeeded. Initial research used `tools/codesearch.py`, followed by CLI verification.

## Plain-language summary

An alternative solution needs a comparison with an applicable code-compliant design, called the benchmark.
The comparison must address the objectives and functions assigned to that benchmark, with at least its minimum performance.
A test report describes the tested specimen and conditions; it does not establish every property of a building.
A product evaluation interprets evidence for a defined use; certification adds assurance under a particular certification scheme.
A certification mark is useful only when the actual product, listing, standard, and installation conditions match.
A variance decision concerns the proposed departure and its conditions; it is not a general product endorsement.
Section D needs a reasoned comparison and traceable supporting documents, including limits and any ongoing maintenance.
The applicant's professionals make technical judgements; an application-completeness tool can identify missing evidence and mismatches.
Sources: NBC(AE) 2023 p2, Div A, Sentence 1.2.1.1.(1) [PDF p.38]; Div C, Article 2.3.1.1. [PDF p.739].

Conformity background: NBC(AE) 2023 p2, Preface [PDF pp.18–19].

Local process: Calgary guide [PDF pp.1–3].

## When this topic applies

### Trigger signals

- A manufacturer supplies a brochure, test report, listing, evaluation number, or certificate as proof of compliance.
- The proposed product differs from a tested assembly in thickness, formulation, substrate, fasteners, joints, orientation, or exposure.
- The product is new, has no directly applicable product standard, or has a report for a different jurisdiction or code edition.
- The application says "equivalent", "fire rated", "noncombustible", "Class A", "engineered", or "approved" without identifying the actual evidence.
- Section D contains attachments but no comparison between their results and the Section C benchmark.
- An applicant wants to sell a product across Alberta using a variance issued for one building.
- A reviewer needs to distinguish laboratory accreditation, product certification, professional authentication, and an authority's decision.

These are routing signals derived from the evidence obligations and conformity distinctions, not statutory trigger language.
Source: NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739].

Conformity background: NBC(AE) 2023 p2, Preface [PDF pp.18–19].

Local process: Calgary guide [PDF pp.1–3].

### Part 3 and Part 9

The evidence framework applies in both streams. Part 9 is not a shortcut around alternative-solution documentation.
Part 9 generally covers buildings no more than three storeys and 600 m² in building area, in the listed occupancy classes.
The Alberta list includes Group B, Division 4 home-type care, as well as Groups C, D, E, F2, and F3.
Parts 3–6 apply according to their separate application provision, including post-disaster buildings and the occupancy/size conditions there.
Confirm classification before choosing the benchmark; product literature rarely supplies enough project information to do this.
Sources: NBC(AE) 2023 p2, Div A, Article 1.3.3.2. [PDF pp.39–40] and Sentence 1.3.3.3.(1) [PDF p.40].

For fire resistance, the Part 3 rating method is different in structure from the Part 9 route that incorporates it and also permits specified tables.
The requirement for a particular duration must come from the project-specific provision; a test-method article alone does not establish the duration.
The benchmark section below identifies the relevant methods without assuming that every assembly needs a one-hour rating.

### Near-misses

- Selecting the required fire separation, exposing building face, or penetration protection is primarily [fire-separations-and-spatial-separation](fire-separations-and-spatial-separation.md).
- Selecting cladding, insulation, air/water/vapour control, or a wall-system benchmark is primarily [building-envelope-insulation-cladding](building-envelope-insulation-cladding.md).
- Determining whether a seal, field review, or professional schedule is legally required is primarily [professional-involvement](professional-involvement.md).
- A report based solely on an older national code belongs first with [code-structure-and-attribution](code-structure-and-attribution.md) for edition and attribution checks.
- Who can issue a variance, what form applies, and whether it carries to another site are primarily [process-and-admin](process-and-admin.md).
- A standard-compliant product used exactly within the applicable acceptable solution may require ordinary compliance evidence, without an alternative solution. The compliance routes are in NBC(AE) 2023 p2, Div A, Sentence 1.2.1.1.(1) [PDF p.38].

## Benchmark acceptable solutions

### Governing evidence provisions

The following are verified against the full Alberta second printing. Administrative provisions belong in the evidence rationale, not in place of the actual Division B benchmark.

| Verified provision | Paraphrased requirement and relevance |
| --- | --- |
| NBC(AE) 2023 p2, Div A, Sentence 1.2.1.1.(1) [PDF p.38] | Compliance uses applicable Division B acceptable solutions or alternatives meeting at least their minimum performance in the attributed areas. |
| NBC(AE) 2023 p2, Div A, Sentence 1.2.1.1.(2) [PDF p.38] | The applicable objectives/functions come from the Division B attribution system. |
| NBC(AE) 2023 p2, Div A, Article 1.2.2.1. [PDF pp.38–39] | Installed materials and systems need characteristics suited to their functions. CCMC reports or reports of an organisation approved by the Provincial Building Administrator may inform compliance. The Administrator can also issue qualifying material/product lists. |
| NBC(AE) 2023 p2, Div A, Article 1.5.1.1. [PDF p.54] | Referenced documents apply within the building and attributed-performance scope; the cross-code condition in Sentence (2) also matters. |
| NBC(AE) 2023 p2, Div A, Sentence 1.5.1.2.(1) [PDF p.54] | The building code prevails over a conflicting referenced document. |
| NBC(AE) 2023 p2, Div A, Sentence 1.5.1.3.(1) [PDF p.54] | Use the editions designated through Division B, not automatically the newest edition advertised by a laboratory. |
| NBC(AE) 2023 p2, Div B, Sentence 1.1.2.1.(1) [PDF p.89] | Each applicable Part's attribution table supplies the objective/function pairs. |
| NBC(AE) 2023 p2, Div B, Sentence 1.3.1.1.(1) [PDF p.90] | Unless otherwise specified, referenced documents include amendments and related updates effective to 15 July 2022. |
| NBC(AE) 2023 p2, Div B, Sentence 1.3.1.2.(1) [PDF p.90] | Table 1.3.1.2. identifies the adopted document editions. The actual second-printing table must be checked. |

The code's Preface describes testing, evaluation, qualification, and certification [PDF pp.18–19].
It is explanatory material about conformity assessment; it does not prescribe a universal six-step approval sequence.

### Section D documentation

All six sentences of NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739] matter:

1. The person requesting an alternative supplies the required documentation.
2. It includes the analytical method and rationale, plus special operational, maintenance, and commissioning needs.
3. It identifies acceptable solutions, objectives, functions, assumptions, limitations, tests, studies, and performance parameters.
4. It identifies the qualifications, experience, and background of those responsible for design.
5. Its detail must support assessment of validity, accuracy, relevance, and precision.
6. If several people take responsibility for different aspects, the applicant identifies one coordinator for the design, analysis, and documentation.

The Safety Codes Council form's Section D records the supporting document name and the responsible individual/professional/organisation.
A useful attachment index adds report number, date, revision, specific page, and the claim supported.
Those extra indexing fields are an administrative recommendation; they are not additional printed form fields.
Source: `SCC-Variance-Form` [PDF p.2].

### Fire-performance benchmarks used in this sheet

| Verified provision | Benchmark and boundary |
| --- | --- |
| NBC(AE) 2023 p2, Div B, Sentence 3.1.7.1.(1) [PDF p.151] | Subject to its stated exceptions, a required fire-resistance rating is determined from CAN/ULC-S101 testing. It does not itself say which project assemblies need which duration. |
| NBC(AE) 2023 p2, Div B, Sentence 3.1.7.1.(2) [PDF p.151] | Appendix D is a permitted rating route. A qualifying Appendix D calculation is not automatically an alternative solution. |
| NBC(AE) 2023 p2, Div B, Article 3.1.7.3. [PDF p.151] | Rating exposure matters: floors/roofs/ceilings from below, interior vertical separations/firewalls from either side, and exterior walls from inside. |
| NBC(AE) 2023 p2, Div B, Sentence 9.10.3.1.(1) [PDF p.878] | Part 9 accepts the specified Part 3 tests, Appendix D calculations, or construction specifications in its named wall and floor/ceiling/roof tables. Changing a table assembly needs a defensible basis. |
| NBC(AE) 2023 p2, Div B, Article 9.10.3.2. [PDF p.878] | Part 9 flame-spread ratings use Part 3 methods or Appendix D; the article distinguishes surface ratings from ratings of surfaces exposed by cutting. |
| NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(1) [PDF p.886] | Residential suites generally need a separating assembly with at least 45 minutes of fire resistance, subject to the listed exceptions. |
| NBC(AE) 2023 p2, Div B, Sentences 9.10.9.16.(2)–(4) [PDF p.886] | Boarding/lodging conditions, multi-storey dwelling units, and houses with secondary suites change the answer. In particular, the verified secondary-suite provision permits specified smoke-tight gypsum protection; it must not be mistaken for the general suite rule. |

The standards matrix below gives evidence categories and adopted editions.
It does not replace the envelope, penetration, construction-type, or occupancy provisions that make a particular test relevant.

## Attributions

### Verified pairs

| Benchmark | Exact pair or pairs | Alberta table evidence |
| --- | --- | --- |
| NBC(AE) 2023 p2, Div B, Sentence 3.1.7.1.(1) [PDF p.151] | [F03-OS1.2], [F04-OS1.3], [F03-OP1.2], [F04-OP1.3] | Table 3.10.1.1., PDF p.322. |
| NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(1) [PDF p.886] | [F03-OS1.2], [F03-OP1.2] | Table 9.38.1.1., PDF p.1128. |
| NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(3) [PDF p.886] | [F03-OS1.2] | Table 9.38.1.1., PDF p.1128. Do not append the property-protection pair from Sentence (1). |
| NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(4) [PDF p.886] | [F03-OS1.2], [F03-OP1.2] | Table 9.38.1.1., PDF p.1128. This Alberta exception has its own attribution. |

F03 concerns delaying fire effects beyond the origin; F04 concerns delaying failure or collapse caused by fire.
OS1.2/OS1.3 concern harm to people from fire spread or fire-related structural failure; OP1.2/OP1.3 concern damage to the building from those events.
Sources: NBC(AE) 2023 p2, Div A, Article 2.2.1.1. [PDF pp.68,72] and Article 3.2.1.1. [PDF pp.79–80].

### Provisions without a direct table row

No separate row for the Part 9 rating-method Sentence 9.10.3.1.(1) appears at the relevant transition in Table 9.38.1.1. [PDF p.1126].
It refers to other methods; the project's substantive requirement retains its own attribution.
Where the Part 3 fire-resistance method is the referenced benchmark, show its verified pairs separately, rather than labelling them direct Part 9 table attributions.
Likewise, the Appendix D permission in Sentence 3.1.7.1.(2) has no separate row in Div B Table 3.10.1.1. [PDF p.322].
The parent Sentence 3.1.7.1.(1) supplies the stated fire-resistance performance context.

A test standard, a laboratory accreditation, and Division C paperwork do not acquire objective/function pairs merely because they support a fire-safety claim.
The chain begins with the applicable acceptable solution. The legal attribution link is NBC(AE) 2023 p2, Div B, Sentence 1.1.2.1.(1) [PDF p.89].

## Intent

The following intent material is explanatory national NBC 2020 material, not an Alberta enactment.
Alberta article text and Alberta attribution tables remain the authority for this sheet.

| Provision | Paraphrased intent and verification |
| --- | --- |
| Sentence 3.1.7.1.(1) | Prevent inadequate fire resistance from allowing fire spread or failure/collapse that harms people or damages the building. NBC 2020 Intent Statements, 3.1.7.1.(1) [PDF p.88]. Its four pairs match NBC(AE) 2023 p2, Div B Table 3.10.1.1. [PDF p.322]. |
| Sentence 3.1.7.1.(2) | Permit Appendix D ratings as an alternative to the stated test determination. NBC 2020 Intent Statements, 3.1.7.1.(2) [PDF p.88]. This is an exception explanation, not a separate attributed performance pair. |
| Sentence 9.10.3.1.(1) | Extend the specified Part 3 rating methods to Part 9 and direct users to the permitted tables and Appendix D. NBC 2020 Intent Statements, 9.10.3.1.(1) [PDF p.1344]. |
| Sentence 9.10.3.2.(1) | Extend Part 3 flame-spread methods to Part 9 and permit Appendix D ratings. NBC 2020 Intent Statements, 9.10.3.2.(1) [PDF p.1344]. |
| Sentence 9.10.9.16.(1) | Limit spread between suites or rooms to protect people in the other space and protect the building. NBC 2020 Intent Statements, 9.10.9.16.(1) [PDF pp.1371–1372]. The two pairs match NBC(AE) 2023 p2, Div B Table 9.38.1.1. [PDF p.1128]. |

These selected text/attribution relationships were checked. No claim is made that the complete national intent supplement maps unchanged to Alberta.
In particular, an exception with different Alberta conditions must be checked in the Alberta provision before using the national explanation.

## Typical alternative solutions

### Product within an acceptable solution

A product can have an unfamiliar trade name while meeting the specified product standard and all installation conditions.
The first question is whether the applicable acceptable solution already permits that use.
An evaluation number does not, by itself, mean that a variance is needed.
Source: NBC(AE) 2023 p2, Div A, Sentences 1.2.1.1.(1) and 1.2.2.1.(2) [PDF pp.38–39].

### Innovative material or assembly

Examples include structural insulated panels replacing conventional framing, proprietary protective coatings, or an assembly outside a tested or tabulated configuration.
The supplier's product evidence and the designer's building-specific analysis answer different parts of the question.
CCMC report 13016-R is a real example of a SIP assessment with conditions, plant identification, and separate structural/envelope claims; its older national-code scope is discussed below.
The CWC guide illustrates a coated-wood ceiling proposal with installation and maintenance conditions, using a placeholder Product X.
That guide is an educational example, not proof of an issued Alberta variance or proof that every coating works on every wood species.
Sources: [CCMC 13016-R](https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=13016-R&type=cert), accessed 2026-10-18; `CWC-Alternative-Solutions-Guide` [PDF pp.26–28].

### A project-specific performance proposal

A professional may compare a proposed configuration with a code-compliant one using calculations, tests, studies, and a documented set of assumptions.
The method must establish the relevant comparison rather than simply assert a desirable overall outcome.
NBC(AE) 2023 p2, Div A, Sentence 1.2.1.1.(1) [PDF p.38] and Div C, Article 2.3.1.1. [PDF p.739] supply that framework.
The NRC paper *Accepting alternate solutions under objective-based codes* explains third-party evaluation as advice to the official and stresses comparison with acceptable-solution performance.
It is a 2001 explanatory paper, not current Alberta legal authority.

Source: `NRC-Accepting-Alternate-Solutions` [PDF pp.3–4].

### Calgary's product-approval boundary

Calgary's current linked guide says variances are not intended for product/equipment approval or approval of new or untested products.
This is consistent with using product evidence within a site-specific proposal: an assessment can support the application without the variance becoming a general permission to market a product.
The guide ties requests to the permit/site and calls for a discussion with the SCO about the appropriate route.
Source: [Calgary guide, 23 November 2023](https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf), accessed 2026-10-18, PDF pp.1–3.

For a product intended for repeated sale, the relevant evaluation/certification pathway and project acceptance must both be considered.
For a one-off building proposal, a product report is one part of the evidence package, with the report's restrictions carried into the design.

## Usual mitigations and evidence

### Evidence types and the proposed confidence ladder

The topic brief names this sequence: manufacturer literature, STANDATA, ISO/IEC 17025 testing, evaluation, qualification, ISO/IEC 17065 certification.
It is useful as an introduction to independent assessment, but it is not a statutory ranking or an obligatory sequence.
STANDATA supplies regulatory interpretation or a variance, rather than a generic level of laboratory assurance.
A narrowly applicable test is stronger evidence for its measured property than a broad certificate that excludes the proposed use.
Several evidence types can be needed together.
The separate "pathway map" referred to by the topic brief was not present among the located reference files; the sequence itself is brief-supplied, with the qualifications below independently sourced.

In the table, "acceptance use" means the role evidence can play in an SCO's assessment, not a guarantee of acceptance.
Cost/time entries without a published figure are planning considerations inferred from the work involved; they are not market quotations.
Conformity categories: NBC(AE) 2023 p2, Preface [PDF pp.18–19].

Governing sources: NBC(AE) 2023 p2, Div A, Article 1.2.2.1. [PDF pp.38–39]; Div C, Article 2.3.1.1. [PDF p.739].

| Evidence type and issuer | What it establishes and its limits | Cost/time information | Acceptance use and missing checks |
| --- | --- | --- | --- |
| Manufacturer literature, drawings, declarations, or mill certificates | Identifies the product and asserted characteristics. Commercial assertions need underlying evidence when they carry the compliance case. | Existing documents may be immediately obtainable; no universal fee or turnaround verified. | Useful for identification, installation, and stated properties. Check revision, manufacturer, and the report behind each relevant assertion. |
| Applicable STANDATA, Provincial Building Administrator | Establishes the scope and conditions of that interpretation or provincewide variance. It may recognise an organisation or a defined alternative. | Published documents are accessible without a testing commission. Obtaining a new variance has no verified universal schedule here. | Check type, edition, revision, applicability, and every condition. A general information bulletin is not a product test or blanket approval. |
| Test report, laboratory accredited for the relevant method under ISO/IEC 17025 | Reports performance of identified specimens under stated conditions. Accreditation concerns competence for a defined scope, not approval of the whole building. | Existing report retrieval differs from commissioning a new test. Request a laboratory quote for specimen construction, conditioning, capacity, and repeats. | Match method/edition, scope of accreditation, specimen, loading, mounting, exposure, and result to the claim. |
| Independent evaluation, e.g. CCMC or an Alberta-recognised organisation | Gives a technical opinion/assessment for defined uses based on supporting evidence. The report may include restrictions and surveillance. | Depends on innovation and available criteria; see the CCMC snapshot below. | Read the full report, including limitations and code editions. Recognition of the issuer does not expand report scope. |
| Product qualification, an organisation operating a qualification scheme | Verifies required performance against a standard; the code Preface says it normally includes some plant follow-up. | Scheme-specific testing and inspection quote needed. | Confirm which standard, facility, product, and follow-up activities the qualification covers. |
| Product certification, independent certification body accredited under ISO/IEC 17065 | Formal conformity assurance within the certification scheme. A mark/certificate must be linked to the listing and product. | Initial assessment, testing, and ongoing activities have scheme-specific costs. No universal cost or duration verified. | Check accredited scope, Canadian/code applicability, listing status, manufacturing location, marking, and installation conditions. |
| Authenticated project analysis, appropriate registered professional | Assigns professional responsibility for a defined design/analysis. It can address differences between tests and the proposed installation. | Depends on project complexity and available supporting data; obtain a scoped proposal. | Check author, discipline, authentication, scope, assumptions, calculations, and conclusions. A seal is neither certification nor the variance decision. |
| Field review, commissioning, or inspection record, competent responsible party | Records what was built, installed, or tested on site. It can verify specified conditions. | Depends on access, inspection stages, and retesting; cost/time not quantified here. | Link findings to drawings and the evidence conditions. Inspection cannot retrospectively turn an untested material into a certified one. |

The ISO distinctions above are supported by the Standards Council of Canada's laboratory and product-certification programme documents.
The direct PDFs were inaccessible to the browser; only official indexed excerpts were available. No individual body's current accreditation scope is certified by this sheet.
Sources: [SCC laboratory requirements](https://scc-ccn.ca/system/files/2024-01/scc-rg_lap_en.pdf) and [SCC product-certification requirements](https://scc-ccn.ca/system/files/2024-03/asb_rg_cbap_v5_2021-09-21.pdf), official search excerpts accessed 2026-10-18.

### CCMC process and cost/time snapshot

CCMC's current PAS distinguishes standard-based listings from innovative-product reports.
It uses Type 5 assessment with ongoing surveillance; the older Preface description of evaluations without normal plant follow-up does not describe every current programme.
PAS-001 says general alignment with ISO/IEC 17065; this does not establish a claim of SCC accreditation for every CCMC service.
Published estimates separate CCMC work from third-party work.
For standard products relying on third-party certification, the listed CCMC application fee is CAD 4,000 and qualification fee CAD 0, with CAD 2,500 annual maintenance; existing third-party costs remain separate.
The table estimates 2–6 months for that CCMC service and 4–12 months for third-party services.
Highly innovative multi-function products may take 18+ months.
These are programme estimates, not a project quote or guaranteed combined duration.
Source: [NRC PAS-001, modified 9 September 2026](https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=PAS-001&type=policy), accessed 2026-10-18, process, fee table, and FAQ.

### Common fire-test standards

Adopted editions below come from NBC(AE) 2023 p2, Div B, Table 1.3.1.2., beginning at PDF p.90.

The specific entries were read on its continuation pages [PDF pp.96,115–116].
The descriptions identify the measured property at a high level; licensed full standards and the actual reports are needed for detailed procedures and acceptance criteria.
A standard's presence in the reference table does not make it applicable to every project.

| Test standard | Evidence it concerns | Edition/status and common misuse |
| --- | --- | --- |
| CAN/ULC-S101 | Fire endurance of a construction assembly/material/member used to determine required fire resistance. | Adopted S101-14, PDF p.115. A surface-burning rating does not supply an S101 fire-resistance duration. |
| CAN/ULC-S102 | Surface-burning characteristics of building materials/assemblies. | Adopted S102:2018, PDF p.115. It does not by its title or result establish an assembly fire-resistance rating. |
| CAN/ULC-S102.2 | Surface-burning characteristics for flooring, floor coverings, and other materials/assemblies in its scope. | Adopted S102.2:2018, PDF p.115. The relevant mounting/material category must be checked; S102 and S102.2 are not interchangeable labels. |
| CAN/ULC-S114 | Determination of noncombustibility of building materials. | Adopted S114:2018, PDF p.116. A low flame-spread value alone is not this determination. |
| CAN/ULC-S115 | Fire tests of firestop systems. | Adopted S115:2018, PDF p.116. Match the system configuration and required classification; a container of sealant is not the entire tested assembly. |
| CAN/ULC-S134 | Fire behaviour of exterior wall assemblies. | Adopted S134-13, PDF p.116. Small-specimen surface-burning evidence cannot be represented as this exterior-wall assembly test. |
| CAN/ULC-S124 | Evaluation of coverings that protect foamed plastic. | Adopted S124-06, PDF p.116. A protective-covering result is not an unrestricted fire-resistance rating for the wall. |
| ASTM E84 | Comparative surface flame spread and smoke-developed measurements; the published scope describes a 10-minute test. | ASTM E84-20 scope consulted for explanation, not claimed as an adopted replacement for S102. ASTM states the index alone does not establish noncombustibility. [ASTM scope](https://store.astm.org/e0084-20.html), accessed 2026-10-18. |
| ASTM E2768 | Extended-duration surface-burning test, identified by ASTM as a 30-minute tunnel test. | ASTM E2768-25 catalogue consulted for identification, not an Alberta adopted edition or a 30-minute assembly rating. [ASTM catalogue](https://store.astm.org/e2768-25.html), accessed 2026-10-18. |
| ASTM E2307 | Performance of the perimeter fire barrier between a floor and exterior wall under the specified fire and deformation exposure. | Adopted E2307-20, PDF p.96. ASTM's scope distinguishes this from separate component properties and cautions about changed end-use conditions. [ASTM scope](https://store.astm.org/e2307-20.html), accessed 2026-10-18. |

The distinction between surface burning, noncombustibility, fire endurance, and firestop/perimeter performance is an evidence-matching distinction.
No numerical conversion between S102 and E84, or between E2768 duration and S101 rating, was verified.
No claim that ASTM E84 or E2768 universally replaces a referenced Canadian method is supported here.

### Matching evidence to objectives and functional statements

The following is an administrative evidence matrix, derived from the documentation requirement, not an engineering calculation method.
Source: NBC(AE) 2023 p2, Div C, Sentences 2.3.1.1.(2)–(5) [PDF p.739].

1. Identify the exact acceptable-solution sentence that controls the proposed departure.
2. Record its minimum performance and conditions, using the Alberta second printing.
3. Copy the exact objective/function pairs from the applicable attribution table, retaining qualifiers.
4. Explain the corresponding physical concern, using national intent only as labelled explanatory support.
5. Identify which report, test result, calculation, or operational measure addresses each concern.
6. Record the differences between the tested/evaluated system and the proposed installation.
7. Identify who takes responsibility for analysing those differences and any residual uncertainty.
8. Carry necessary installation, maintenance, commissioning, and inspection conditions into the application.

For NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(1), [F03-OS1.2] and [F03-OP1.2] require the comparison to address spread to another space. Attribution table evidence: PDF p.1128.
For NBC(AE) 2023 p2, Div B, Sentence 3.1.7.1.(1), [F04-OS1.3] and [F04-OP1.3] address fire-related failure/collapse. Attribution table evidence: PDF p.322.
It is an overreach to mark the whole comparison complete because one test supplies a favourable surface flame-spread number.
The verified benchmark and attribution sources are in the tables above.

### What a traceable report package contains

These are recommended completeness fields derived from the same Division C requirements and the conformity categories, rather than a claim that every test standard prescribes an identical report form.

- Issuer, complete report identifier, issue/revision date, and all relevant pages.
- Product name, model, formulation, manufacturing source, and evidence tying the delivered product to the assessed one.
- Standard number and edition, referenced acceptance criteria, and any deviations from the procedure.
- Specimen geometry, thickness, density where relevant, substrate, joints, fastening, conditioning, and mounting.
- Loading, exposure direction, and the measured results/classifications needed for the stated benchmark.
- Accreditation body and current scope relevant to the performed test or certification activity.
- Report limitations, exclusions, validity/status, and permitted installation conditions.
- A building-specific comparison identifying matches, differences, the responsible analyst, and unresolved questions.
- Drawings, site verification records, and ongoing conditions needed to reproduce the assessed performance.

A missing datum can be flagged as missing. Whether a changed specimen or procedure remains technically representative needs competent judgement.
The tool's permitted outcome is an evidence gap or scope mismatch, not a calculated declaration of equivalent safety.

### Performance-based methods

SFPE's published guide describes project scope, goals, objectives, performance criteria, fire scenarios, trial designs, evaluation, and documentation.
That structure can organise a professional comparison, while Alberta's attributed acceptable solution remains the benchmark.
Source: [SFPE performance-based design course outline](https://www.sfpe.org/events-education/liveeducation/coursecatalog/seminars-pbd), accessed 2026-10-18; [SFPE 2007 engineering guide description](https://www.sfpe.org/publications/guides/pbfp2nd), accessed 2026-10-18.

NFPA's published committee material identifies Chapter 5 of NFPA 101 as a scenario-based performance approach.
This is background only; the committee document is not an adopted Alberta provision.
The NFPA 101:2024 LiNK page returned no usable text, so detailed current requirements and scenario lists were not verified.
Source: [NFPA committee material](https://docinfofiles.nfpa.org/files/AboutTheCodes/1/1_2024_FCC_FUN_Log1736_tiaballot.pdf), accessed 2026-10-18, official indexed excerpt.

A modelling submission should disclose the model, version, inputs, assumptions, validation basis for its use, scenarios, uncertainty, and comparison criteria.
This is an evidence-completeness recommendation under NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739].
Selecting credible design fires, accepting a model's applicability, or judging tenability is professional work, not an automated completeness finding.

## Engineering / professional triggers

### Code requirements that change the evidence package

| Verified trigger | Required involvement or evidence |
| --- | --- |
| Buildings outside the exceptions in NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(1) [PDF pp.739–740] | Sentence 2.4.1.1.(3) [PDF p.740] requires drawings/specifications authenticated by professionals qualified in the applicable architecture/engineering disciplines. The exceptions depend on occupancy, size, height, and dwelling-unit count; do not reduce them to a Part 9/Part 3 label. |
| Size or complexity raising special safety concerns | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(4) [PDF p.740] permits the authority to require professional authentication and field reviews. This can apply despite a general building-size exception. |
| Documents required to be professionally authenticated | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.1.(5) [PDF p.740] links authentication to the Architects Act or Engineering and Geoscience Professions Act. |
| Structural design under Part 4 | NBC(AE) 2023 p2, Div C, Sentence 2.4.1.2.(1) [PDF p.740] requires a registered professional skilled in the work. |
| Structural component drawings, including guards | NBC(AE) 2023 p2, Div C, Sentence 2.2.4.4.(1) [PDF p.732] requires professional authentication. |
| Structural calculations and analysis | NBC(AE) 2023 p2, Div C, Sentence 2.2.4.5.(1) [PDF p.732] requires them to be available for inspection on request. A summary conclusion does not replace the underlying analysis. |
| Automatic suppression or fire-alarm design in a building covered by the general professional requirement | NBC(AE) 2023 p2, Div C, Sentences 2.4.1.3.(1) and 2.4.1.4.(1) [PDF p.740] require evidence of professional retention before construction for design, field review, and the specified testing/verification witnessing. |
| Several alternative-solution design authors | NBC(AE) 2023 p2, Div C, Sentence 2.3.1.1.(6) [PDF p.739] requires an identified coordinator. Coordination alone does not certify every contributing discipline. |

Alternative-solution documentation requires designer qualifications and experience, but it does not impose a single universal "every variance needs an engineer" rule.
The applicable building-design triggers and professional practice law must still be checked.
Alberta's single-egress-stair interpretation makes the same distinction in its professional-involvement discussion.
Source: `standata-nbc2023-interpretation-23-bci-026` [PDF p.2], October 2026; use its discussion as topic-specific guidance, not an exemption from other laws.

### What an authenticated engineering analysis means

APEGA says authentication records professional responsibility for work prepared, thoroughly reviewed, or directly supervised and controlled by the professional.
A project-specific analysis should make its scope clear, including the evidence relied on, assumptions, restrictions, and conclusions.
An image of a seal detached from its document is inadequate for checking authentication and document identity.
Source: [APEGA authentication standard](https://www.apega.ca/about-apega/publications/standards-guidelines/authenticating-professional-work-products), accessed 2026-10-18; current page identifies the 1 November 2024 revision.

Signals for professional assessment include extrapolation beyond tested configurations, structural capacity or fire-resistance calculations, fire/smoke modelling, and safety-system trade-offs.
These signals identify work whose professional scope must be resolved; they are not new statutory thresholds invented by this sheet.
The completeness tool can request the responsible professional and authenticated work product.
It must not invent a seal, declare that a model proves equivalence, or treat a stamped opinion as an authority's variance approval.
Source for scope: [APEGA guidance on hiring an engineer](https://www.apega.ca/government), accessed 2026-10-18; code triggers above.

For a product manufactured repeatedly, a project engineer's letter does not establish that every future factory output meets a certification scheme.
Conversely, a certified product does not resolve the engineering of a project outside the listing's conditions.
This distinction follows from the different scopes of certification, design responsibility, and project documentation in the sources above.

## Interactions with other topics

The following links identify neighbouring fact sheets, not additional sources for unverified claims.

| Topic | Interaction with evidence and conformity |
| --- | --- |
| [process-and-admin](process-and-admin.md) | Correct applicant, authority, permit/site scope, form, decision, and any ongoing conditions. |
| [code-structure-and-attribution](code-structure-and-attribution.md) | Applicable edition, Division A/B/C roles, cross-references, exact attribution pairs, and national-intent limits. |
| [professional-involvement](professional-involvement.md) | Professional scope, authenticated work products, field review, schedules, and coordination. |
| [fire-separations-and-spatial-separation](fire-separations-and-spatial-separation.md) | Which assembly needs a rating, its exposure, openings, joints, penetrations, and spread between buildings. |
| [building-envelope-insulation-cladding](building-envelope-insulation-cladding.md) | Product/assembly fire evidence alongside moisture, durability, air leakage, installation, and climate limitations. |
| [combustible-construction-and-mass-timber](combustible-construction-and-mass-timber.md) | Distinguish surface flame spread, noncombustibility, protection/encapsulation, and structural fire resistance. |
| [housing-secondary-suites-part9](housing-secondary-suites-part9.md) | Part 9 rating routes and the specific secondary-suite exception; do not apply general suite assumptions blindly. |
| [structural-and-framing](structural-and-framing.md) | Proprietary design values, loads, connections, authenticated component designs, and construction matching the analysis. |
| [egress-and-single-stair](egress-and-single-stair.md) | Project-level comparative fire/evacuation evidence, assumptions, and professional responsibility. |
| [firefighting-alarms-sprinklers](firefighting-alarms-sprinklers.md) | Reliance on active systems needs corresponding design, installation, commissioning, and operational evidence. |
| [energy-efficiency](energy-efficiency.md) | A thermal product value does not establish whole-building compliance; report conditions and model inputs matter. |
| [hvac-ventilation-plumbing](hvac-ventilation-plumbing.md) | Equipment ratings, installation conditions, service performance, and commissioning must be matched. |
| [occupancy-and-accessibility](occupancy-and-accessibility.md) | Occupancy affects benchmark selection and professional triggers; product dimensions alone do not prove access performance. |

The general requirement to identify assumptions, limits, affected performance, and ongoing conditions is NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739].
The links are routing guidance; each project's extra provisions require separate source verification.

## Common refusal / "more info" causes

Alberta's single-egress-stair interpretation identifies incomplete information, incorrect assumptions/inputs, failure to demonstrate the alternative's safety intent, and impractical or unclear recommendations as possible refusal reasons.
That list is published for single-egress-stair applications; it is not a provincewide statistical ranking of rejection causes.
Source: `standata-nbc2023-interpretation-23-bci-026` [PDF pp.1–2].

The following broader evidence patterns are a completeness checklist derived from NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739] and the scope distinctions in this sheet.
They are not assertions that an SCO must refuse every case with one of these findings.

| Pattern | Appropriate completeness finding |
| --- | --- |
| Brochure says "approved" without a report number or issuer | Missing traceable basis for the compliance claim. |
| Active evaluation addresses a different code edition | Missing comparison to the applicable Alberta requirements. |
| Laboratory is accredited, but the particular test is outside the stated scope | Accreditation does not establish competence for this report as presented; request the relevant scope and explanation. |
| Only a report cover, certificate logo, or favourable excerpt is attached | Missing results, specimen detail, conditions, or limitations needed to assess relevance. |
| S102/E84/E2768 result offered as proof of a 45- or 60-minute fire-resistance rating | Evidence measures a different property; request a technically justified rating basis. |
| Noncombustibility claimed solely from a low surface flame-spread number | Evidence does not establish the stated classification. |
| Test uses different substrate, fasteners, joints, loading, thickness, or orientation | Unresolved difference between evidence and proposed construction. |
| Certificate/listing is expired, withdrawn, for another plant, or for another model | Current product identity/status is unverified. |
| Single product-component report is used to claim whole-wall or whole-building compliance | Scope of evidence is narrower than the conclusion. |
| National, American, or previous-Alberta approval is presented as current Alberta permission | Jurisdiction/edition mapping and local acceptance remain unresolved. |
| Analysis has no benchmark or only broad statements about safety | Missing acceptable-solution comparison and attributed performance areas. |
| Multiple reports use inconsistent drawing revisions | The submitted design and tested/evaluated configuration cannot be traced. |
| Proposed mitigation relies on maintenance with no responsibility or schedule | Missing ongoing compliance condition. |
| Stamp appears on an unrelated drawing but not the relied-on analysis | Authentication scope is unclear. |
| Factory certificate covers the module but site joints and services are excluded | Missing evidence for the installed interfaces. |
| A prior site's variance is used for general marketing | The cited decision's scope does not establish general product approval. |

A numerical inconsistency can be flagged for review without deciding what the correct engineering result should be.
A reviewer can identify missing evidence without making a technical refusal determination on the authority's behalf.

## Precedents

### Alberta-recognised evaluation organisations

The governing permission is NBC(AE) 2023 p2, Div A, Sentence 1.2.2.1.(2) [PDF pp.38–39].
The following issued interpretations were read in the repository's source copies.
Each requires maintained Standards Council of Canada accreditation and notice to the Provincial Building Administrator when accreditation changes or lapses.
Here "SCC accreditation" means the Standards Council of Canada, not the Safety Codes Council that supplies the variance form.

| Organisation | Recognition document | Verified scope |
| --- | --- | --- |
| QAI Laboratories | 23-BCI-005, May 2024, PDF pp.1–2 | Approved organisation whose evaluation reports may be used to determine NBC(AE) compliance, subject to the accreditation conditions. |
| Underwriters Laboratories of Canada Inc./UL Solutions | 23-BCI-006, May 2024, PDF pp.1–2 | Same evaluation-organisation recognition and conditions. |
| Intertek | 23-BCI-007, May 2024, PDF pp.1–2 | Same evaluation-organisation recognition and conditions. |
| ICC Evaluation Service | 23-BCI-013, February 2025, PDF pp.1–2 | Same evaluation-organisation recognition and conditions. |
| CCMC, National Research Council | Named directly in the verified Division A sentence | Reports may be used in determining compliance. The sentence does not say every proposed use of an evaluated product complies. |

The province's [STANDATA index](https://www.alberta.ca/building-standata), accessed 2026-10-18, distinguishes variances, interpretations, and bulletins and warns that earlier-code STANDATA is edition-specific.
The linked 2023 interpretation collection returned HTTP 403 during this check.
Recognition language is verified from the local issued PDFs; a live accreditation-register check for each legal entity and technical scope remains necessary for an actual application.
This table does not establish that each organisation's current accreditation is unchanged.

ICC-ES's Canadian service describes Canadian evaluations supported by testing and/or engineering analysis.
Its recognition in Alberta does not make a US-only ESR or an unrelated acceptance criterion sufficient for an Alberta proposal.
The report must address the relevant use and applicable requirements.
Source: [ICC-ES Canada](https://icc-es.org/es-global/canada/), official indexed text accessed 2026-10-18; direct page exposed only an empty input element.

### CCMC registry example and its limits

The local `reference/data/ccmc-registry.json` contains 462 records as inspected on 2026-10-18.
It is an index snapshot, not the full reports or a guarantee that every status is current.
Record 423 identifies CCMC 13016-R, *Insulspan Structural Insulated Panel (SIP) System*, with status Active and two CCMC technical-guide references.
The live report also showed Active, modified 21 October 2025, but its compliance headings were the historical editions NBC 2010 and NBC 2015.
Its conditions limit the described use to single-family houses and state that fire/sound ratings for other occupancies are not supplied.
This is a real product-assessment example, not an Alberta 2023 second-printing approval precedent.
A designer would need to address the edition and proposed-use gaps before relying on it for a different project.
Source: [CCMC 13016-R](https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=13016-R&type=cert), accessed 2026-10-18, header, compliance opinion, and conditions/limitations.

The local registry also includes standard-based entries, such as 12018-L for ROCKWOOL Comfortbatt with CAN/ULC-S702.1-21, Type 1.
That observation establishes only what the local index says; the full listing and live status of that product were not verified.
An -L or -R suffix is a discovery aid, not a substitute for reading the assessment's scope.

### Guides and policy examples

- Calgary's 23 November 2023 guide distinguishes a project variance from product approval. The currently linked guide, not its older 2014 predecessor, was consulted. Source: Calgary guide, PDF pp.1–3, URL in Sources.
- NRC's 2001 paper describes manufacturer evidence, certification labels, third-party evaluation, and professional review as different ways of supporting an official's assessment. Its historical examples are explanatory, not current Alberta recognition decisions. Source: `NRC-Accepting-Alternate-Solutions`, PDF pp.3–4.
- CWC's guide uses an illustrative coated-wood ceiling case. It shows the need to discuss installation, damaged/cut surfaces, maintenance, and supporting test evidence. It is not an issued variance and its engineering inference about Product X is not independently validated here. Source: `CWC-Alternative-Solutions-Guide`, PDF pp.26–28.
- SFPE's guide description provides a structured method for performance comparisons; it supplies no automatic Alberta approval. URLs appear in Sources.

No identified Calgary SPV or Edmonton policy solution was independently established here as a general product-approval precedent.
The absence of such a precedent is not evidence that a product cannot be proposed; it means this sheet supplies no blanket prior approval.

## Worked example

### Hypothetical intake and issue

A new two-storey, 400 m² Group C building contains four single-level apartments.
It is not a house with a secondary suite, a boarding house, a hotel, or a Part 10 building.
The proposed change affects one nonloadbearing wall between two apartments on the same storey.
The applicant wants to replace the lining of a conventional rated suite-separation assembly with a proprietary mineral-composite board.
Only an S102 report for a sample of that board is provided, described by the applicant as "fire rated".
These are invented case facts, not a real approval or a product-performance claim.

The stated height, area, and occupancy meet the Part 9 application description in NBC(AE) 2023 p2, Div A, Sentence 1.3.3.3.(1) [PDF p.40].
On the stated facts, the relevant suite-separation benchmark is NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(1) [PDF p.886], with at least 45 minutes of fire resistance.
Its exceptions have been considered against the stated case, including the multi-storey dwelling-unit and secondary-suite conditions on the same page.
Other building requirements still need their own review; this example completes the evidence issue for the proposed wall change, not every issue in the building.

### Section C attribution table for this issue

| Applicable article/sentence and role | Objective | Function | Intent and source | Why included |
| --- | --- | --- | --- | --- |
| NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(1) [PDF p.886]. Primary acceptable-solution benchmark. | OS1.2 and OP1.2 | F03, paired exactly as [F03-OS1.2] and [F03-OP1.2]. Div B Table 9.38.1.1. [PDF p.1128]. | Limit spread between rooms/suites that could harm people in the other space or damage the building. NBC 2020 Intent Statements, 9.10.9.16.(1) [PDF pp.1371–1372]. National explanatory source. | Sets the minimum separation performance that the changed assembly must achieve. |
| NBC(AE) 2023 p2, Div B, Sentence 9.10.3.1.(1) [PDF p.878]. Supporting rating-method cross-reference. | No direct row at the relevant Div B Table 9.38.1.1. transition [PDF p.1126]; do not invent a pair. | No separate direct attribution identified. Keep the primary row above; record the referenced method below. | Directs Part 9 users to Part 3 methods, the specified tables, and Appendix D. NBC 2020 Intent Statements, 9.10.3.1.(1) [PDF p.1344]. | Identifies how the required rating can be substantiated. |
| NBC(AE) 2023 p2, Div B, Sentence 3.1.7.1.(1) [PDF p.151]. Referenced fire-resistance test method, if that route is used. | OS1.2, OS1.3, OP1.2, OP1.3 | [F03-OS1.2], [F04-OS1.3], [F03-OP1.2], [F04-OP1.3]. Div B Table 3.10.1.1. [PDF p.322]. | Address inadequate fire resistance leading to spread or fire-related failure/collapse. NBC 2020 Intent Statements, 3.1.7.1.(1) [PDF p.88]. | Identifies the S101 evidence route and its actual attributed pairs. These are Part 3 method attributions, not invented direct attributions to the Part 9 cross-reference. |

The table retains the full verified method pairs. The responsible designer must explain which physical aspects of the nonloadbearing wall and its stability support those performance areas.
A completeness tool should not silently delete table pairs or fabricate a structural calculation to fill them.

### Section D attachment index to be completed

The entries below describe required evidence for the proposed case. They are not claims that these documents already exist.

| Proposed supporting document | Responsible party | What the reviewer needs to see |
| --- | --- | --- |
| D1, code and benchmark analysis | Applicant's designer/code professional, with professional authentication where required | Part 9 classification, wall location, exact proposed departure, verified Section C rows, and comparison criteria. |
| D2, proposed wall detail and installation specification | Responsible designer with manufacturer information | Layers, board identity/thickness, stud system, fasteners, joints, height, interfaces, and revisions. |
| D3, fire-resistance basis | Laboratory/evaluation issuer and responsible analyst | Applicable S101 report for a representative assembly, a permitted Appendix D/table basis where actually applicable, or a professionally justified alternative comparison. |
| D4, existing S102 report | Laboratory/manufacturer | Product identity and surface-burning result, with an explicit statement that this report does not establish the wall's 45-minute resistance. |
| D5, report-to-installation comparison | Responsible professional where technical judgement is involved | All differences between assessed and proposed assembly, evidence for their treatment, and outstanding limits. |
| D6, construction verification and ongoing conditions | Designer/constructor and owner as applicable | Inspection points, evidence of installed product identity, treatment of damaged boards/joints, and any necessary maintenance. |
| D7, qualifications and responsibility record | Applicant/design team | Author qualifications, professional scope where required, and coordinator if several people own parts of the analysis. |

NBC(AE) 2023 p2, Div C, Article 2.3.1.1. [PDF p.739] supports the analysis, evidence, responsibility, and ongoing-condition requirements.
The specific report choice and technical validity remain with the responsible designers and reviewing authority.

### Evidence-completeness result

The submitted S102 report does not address the required fire-resistance property.
The record lacks a verified basis for the proposed wall's rating and lacks a comparison of the installed assembly with an assessed assembly.
The appropriate result is "supporting evidence incomplete; request the rating basis and responsible analysis", not "the wall fails" or "the alternative is equivalent".
If a valid acceptable-solution route already covers the exact assembly, the issue may be ordinary compliance rather than a variance.
If the proposal remains outside that route, its technical comparison and acceptance decision remain outstanding.

Professional involvement is screened separately using the verified Division C triggers above.
The stated four-unit count does not by itself trigger the greater-than-four-unit condition; complexity or engineering work can still require professional involvement.
No fictitious test result, report number, professional seal, or approval has been supplied.

## Open questions / uncertainty

- UNVERIFIED: the standalone "pathway map" cited by the topic brief was not located. The named sequence is recorded as brief-supplied; the code Preface and programme sources support the distinctions, not a universal ranking.
- UNVERIFIED: current accreditation status and exact technical scope of each recognised organisation. The STANDATA recognition documents were read; individual live accreditation certificates/scopes were not obtained.
- UNVERIFIED: complete current text of the SCC laboratory and product-certification programme PDFs. Browser opens returned HTTP 402; only official search-index excerpts were available. The basic distinctions also appear in the code Preface.
- UNVERIFIED: detailed current NFPA 101 performance-based requirements. The NFPA 101:2024 LiNK endpoint exposed no text. A committee excerpt supports only the background reference to a scenario-based chapter; no scenario list or acceptance threshold is imported.
- UNVERIFIED: full paid test-standard procedures or universal conversion between Canadian and ASTM fire tests. Standard titles, adopted editions, code use, and the accessible ASTM scope statements were checked; detailed test execution requires the actual standard and competent assessment.
- UNVERIFIED: fixed cost or turnaround for laboratory tests, non-CCMC certification, professional review, or authority approval. Published CCMC figures are dated programme estimates with third-party work separate, not market-wide estimates.
- UNVERIFIED: Alberta 2023 suitability of the example CCMC SIP product for a proposed building. Its active report is expressly based on older national editions and restrictive use conditions.
- UNVERIFIED: live status and full listing conditions of the ROCKWOOL registry example. Only its local index record was inspected.
- UNVERIFIED: whether any proposed coating, board substitution, model, or operational mitigation actually achieves the required performance. This sheet supplies evidence requirements and examples, not engineering validation.
- The 2023 STANDATA collection returned HTTP 403 through the browser. Issued local PDFs were available; the UL recognition PDF was also located in official indexed results. This is a source-access limitation, not proof of withdrawal or continued accreditation.
- The challenge appendix contains illustrative code-reference text. This sheet does not use it as authority where it differs from the verified Alberta second printing.
- No issued approval was obtained for the hypothetical worked example. It deliberately stops at a documented evidence gap.
- Database validation availability is recorded in the verification receipt below. Manual source verification remains necessary even if a database recognises an article identifier.

## Sources

### Local sources actually read

PDF pages are one-based physical PDF pages, not the printed page labels.
Code excerpts were located and checked with `.venv/bin/python -I tools/codesearch.py`; prose above is paraphrased.

| Source | Pages/data inspected and claims supported |
| --- | --- |
| `reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf` | Preface pp.18–19, conformity categories; pp.38–40, compliance/product reports and Part application; p.54, referenced documents; pp.68,72,79–80, objectives/functions; pp.89–90, attribution and standard-edition rules; pp.96,115–116, test-standard editions; p.151, fire-resistance methods/exposure; p.322, Part 3 attributions; p.732, structural documentation; pp.739–740, alternative documentation and professional triggers; p.878, Part 9 methods; p.886, residential suite separation; pp.1126,1128, Part 9 attributions. |
| `reference/text/NBC-2020-Intent-Statements.jsonl` | PDF p.88, Part 3 rating method/exception; p.1344, Part 9 rating/flame-spread references; pp.1371–1372, residential-suite separation. Explanatory national material only. |
| `reference/guides/SCC-Variance-Form.pdf` | PDF p.2, actual Section D attachment/responsibility fields. |
| `reference/guides/Calgary-Alt-Solution-Guide.pdf` | PDF pp.1–4, local procedure, product-approval boundary, site scope, and supporting evidence. The current linked web PDF was also opened. |
| `reference/guides/NRC-Accepting-Alternate-Solutions.pdf` | PDF pp.1–5, publication provenance and historical explanation of third-party evidence and benchmark equivalence. |
| `reference/guides/CWC-Alternative-Solutions-Guide.pdf` | PDF pp.26–28, illustrative coating case and evidence/maintenance considerations. Guide inference not independently adopted as a technical result. |
| `reference/text/standata-nbc2023-interpretation-23-bci-005.jsonl` | PDF pp.1–2, QAI recognition and accreditation conditions. |
| `reference/text/standata-nbc2023-interpretation-23-bci-006.jsonl` | PDF pp.1–2, UL recognition and accreditation conditions. |
| `reference/text/standata-nbc2023-interpretation-23-bci-007.jsonl` | PDF pp.1–2, Intertek recognition and accreditation conditions. |
| `reference/text/standata-nbc2023-interpretation-23-bci-013.jsonl` | PDF pp.1–2, ICC-ES recognition and accreditation conditions. |
| `reference/text/standata-nbc2023-interpretation-23-bci-026.jsonl` | PDF pp.1–2, topic-specific refusal reasons and professional-involvement explanation. |
| `reference/data/ccmc-registry.json` | Local index of 462 records; inspected records 423/13016-R and 163/12018-L. Full live 13016-R report separately checked. |

### Primary web sources and exact uses

All dates below are access dates, 2026-10-18. A search excerpt is explicitly distinguished from a retrieved full page.

| Source and full URL | Claim supported / access boundary |
| --- | --- |
| Alberta STANDATA index, https://www.alberta.ca/building-standata | Full page read. Distinguishes document types and earlier-edition scope; links current interpretation collection. |
| Alberta 2023 interpretation collection, https://open.alberta.ca/publications/standata-interpretation-building-national-building-code-2023-alberta-edition | Link resolved, retrieval returned HTTP 403. Not counted as a full source read. Local issued interpretations supply the cited details. |
| 23-BCI-006 official PDF, https://open.alberta.ca/dataset/cb3d1662-1354-45c8-aab8-29b91f2a6c35/resource/8fc9ac5c-ff9d-46a1-8d5b-c657e5c9d6a8/download/ma-23-bci-006-approved-organization-underwriters-laboratories-of-canada-inc-ul-solutions.pdf | Official indexed text corroborates UL recognition. Full two-page local copy read. |
| Calgary current guide, https://www.calgary.ca/content/dam/www/tools-and-resources/guide-to-applying-for-an-alternative-solution.pdf | Retrieved PDF; pp.1–3 support the product-approval boundary, project/site scope, evidence, and professional-document requirements. |
| Calgary advisories index, https://www.calgary.ca/development/permits/building-regulation-advisories.html | Official indexed entry identifies the guide dated 2023/11/23, distinguishing it from the older 2014 guide returned by search. |
| NRC PAS-001, https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=PAS-001&type=policy | Relevant process/fees/FAQ passages read from the live page. Supports current assessment terminology, surveillance, ISO wording, and dated fee/time snapshot. |
| CCMC 13016-R, https://nrc.canada.ca/en/certifications-evaluations-standards/canadian-construction-materials-centre/ccmc-publications/document.html?id=13016-R&type=cert | Relevant live report passages read. Active status, historical NBC 2010/2015 headings, plant and use limitations; illustrates why status alone is insufficient. |
| SCC laboratory programme, https://scc-ccn.ca/system/files/2024-01/scc-rg_lap_en.pdf | Official indexed excerpt supports ISO/IEC 17025 programme basis; full browser retrieval returned HTTP 402. |
| SCC product-certification programme, https://scc-ccn.ca/system/files/2024-03/asb_rg_cbap_v5_2021-09-21.pdf | Official indexed excerpt supports ISO/IEC 17065 and Canadian accreditation requirements; full browser retrieval returned HTTP 402. |
| ICC-ES Canada, https://icc-es.org/es-global/canada/ | Official indexed excerpt supports its Canadian report service and claimed product-certification accreditation. Direct page yielded no usable body; current scope not independently checked. |
| ASTM E84-20, https://store.astm.org/e0084-20.html | Official scope text read in indexed result: surface-burning indices, 10-minute test, and inability to establish noncombustibility from the index alone. Historical explanatory edition, not claimed as Alberta adoption. |
| ASTM E2768-25, https://store.astm.org/e2768-25.html | Catalogue retrieved; supports title and 30-minute extended-duration surface-burning identity. No detailed procedure or Alberta adoption inferred. |
| ASTM E2307-20, https://store.astm.org/e2307-20.html | Official scope text read in indexed result: perimeter-barrier performance and limits of extrapolation. Adopted edition independently checked in Alberta table. |
| SFPE guide description, https://www.sfpe.org/publications/guides/pbfp2nd | Official indexed description supports the 2007 guide's scope and design-process topics; full paid book not read. |
| SFPE performance-based design outline, https://www.sfpe.org/events-education/liveeducation/coursecatalog/seminars-pbd | Official indexed text supplies scope, criteria, scenarios, evaluation, and documentation structure; no claim of Alberta legal adoption. |
| NFPA committee material, https://docinfofiles.nfpa.org/files/AboutTheCodes/1/1_2024_FCC_FUN_Log1736_tiaballot.pdf | Official indexed excerpt identifies NFPA 101 Chapter 5 as a scenario-based method. Committee context only, not final code requirements. |
| NFPA 101:2024 access attempt, https://link.nfpa.org/all-publications/101/2024 | Opened but no usable text returned. No detailed requirements verified. |
| APEGA authentication guidance, https://www.apega.ca/about-apega/publications/standards-guidelines/authenticating-professional-work-products | Official indexed text supplies current revision date and authentication purpose. |
| APEGA authentication standard, https://www.apega.ca/docs/default-source/pdfs/standards-guidelines/authenticating-professional-work-products.pdf | Official indexed passages support professional responsibility and authentication scope. Full standard not represented as read. |
| APEGA hiring guidance, https://www.apega.ca/government | Official indexed text supports the licensed-professional boundary for full-scope engineering services. |

### Verification receipt

The code corpus was checked by exact identifier search and actual page reads, not by relying on the challenge appendix's sample citations.
There are 24 distinct cited code articles, plus three named tables. The standard-edition table shares an identifier with its parent article, giving 26 distinct article/table identifiers.

| Division | Cited articles, counted once regardless of sentence references |
| --- | --- |
| Div A, nine articles | 1.2.1.1.; 1.2.2.1.; 1.3.3.2.; 1.3.3.3.; 1.5.1.1.; 1.5.1.2.; 1.5.1.3.; 2.2.1.1.; 3.2.1.1. |
| Div B, eight articles | 1.1.2.1.; 1.3.1.1.; 1.3.1.2.; 3.1.7.1.; 3.1.7.3.; 9.10.3.1.; 9.10.3.2.; 9.10.9.16. |
| Div C, seven articles | 2.2.4.4.; 2.2.4.5.; 2.3.1.1.; 2.4.1.1.; 2.4.1.2.; 2.4.1.3.; 2.4.1.4. |
| Div B, three tables | Table 1.3.1.2.; Table 3.10.1.1.; Table 9.38.1.1. |

The raw verification commands included:

```text
.venv/bin/python -I tools/codesearch.py find '<escaped identifier>' --doc NBC-AE --max 100 --context 25
.venv/bin/python -I tools/codesearch.py page NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2 322
.venv/bin/python -I tools/codesearch.py page NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2 1128
.venv/bin/python -I tools/codesearch.py page NBC-2020-Intent-Statements 88 # national explanatory supplement
.venv/bin/python -I tools/codesearch.py page NBC-2020-Intent-Statements 1371 # national explanatory supplement
.venv/bin/python -I tools/codesearch.py page NBC-2020-Intent-Statements 1372 # national explanatory supplement
.venv/bin/python -m codedb lookup '3.1.7.1.(1)' --doc NBC-AE --division B --json
.venv/bin/python -m codedb lookup '9.10.9.16.(1)' --doc NBC-AE --division B --json
.venv/bin/python -m codedb validate research/facts/evidence-and-conformity.md
```

All 26 distinct identifiers returned matches in the code search.
The fire-resistance lookup returned `pdf_page: 151`, four attribution records with `pdf_page: 322`, and national explanatory intent records with `pdf_page: 88`.
The residential-suite lookup returned `pdf_page: 886`, two attribution records with `pdf_page: 1128`, and national explanatory intent pages 1371–1372.
The raw pages also confirm the single safety pair for the multi-storey-dwelling exception and both pairs for the Alberta secondary-suite exception.

Validator result: `1 files; 251 citation tokens; 0 errors; 38 warnings`, exit status 0.
The remaining warnings are all `unbound_page`, covering source-page references without a machine-linked provision, including guides, STANDATA, the Preface, the source list, and reference-table continuations.
Those pages were manually read; a warning-free technical or legal review is not claimed.
The validator's first run also bound some neighbouring sources to the wrong provision. Explicit source separation and same-line historical-edition labels resolved those errors without changing the verified source facts.
A passing identifier scan is not proof of equivalence or regulatory acceptance.

Scope checks: only this deliverable was authored; no held-out eval or variant files were read; no commits, pushes, or code changes were made.
This is a nonvisual research deliverable. No application feature, screenshot, or working-demo claim applies.
The workflow maintenance check reported model-preference drift; source methods were readable, live T3 identity/capabilities were checked, and no workflow files were changed.

Methods used, with actual source files read:

- T3 workflow router: `/Users/aamia/.codex/skills/t3-workflow/SKILL.md`.
- T3 method routing: `/Users/aamia/.codex/skills/t3-workflow/references/routes.md`.
- Matt Pocock primary-source research: `/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/research/SKILL.md`.
- pstack unslop prose review: `/Users/aamia/.agents/skill-libraries/pstack/skills/unslop/SKILL.md`.
- Workflow drift-handling instructions: `/Users/aamia/.agents/t3-workflow/UPDATE-SAFETY.md`.

The brief's no-further-delegation and no-commit rules governed this research. The source research method's background-agent instruction did not override those rules.
