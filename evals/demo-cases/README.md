# Batatis demo cases: General Applicability (backlog #7)

> **Edition caveat:** the cases were checked against the **NBC(AE) 2023 1st printing**. The 2nd printing (Aug 17, 2026) is in force; its wording and page numbers are unverified. The code is a free NRC download: https://nrc-publications.canada.ca/eng/view/object/?id=0316d953-0d55-4311-af69-cad55efec499

> **EVERYTHING HERE IS EXAMPLE DATA.** All people, companies, addresses, legal descriptions, products, listings, test reports and letters are **fictional**. Only code, STANDATA, standard and process citations are real, and each is traced in [`sources.md`](sources.md).

| Case | Persona | Situation | Route the tool should find |
|---|---|---|---|
| [A: Manufacturer](a-manufacturer-nailbase-sheathing/README.md) | Mira Okafor, Example Panel Works Ltd. | Novel foam + fibre-cement nail-base panel replacing OSB; vinyl siding fastened to the facer; Edmonton pilot house | Departure from **9.27.5.1**; product acceptance via **CCMC/PBA-recognized evaluator** (Div A 1.2.2.1.(2)), plus a project-specific alternative solution; not "Alberta product approval" |
| [B: General contractor](b-contractor-firestop-nonconformance/README.md) | Carlos Mendes, Northgate Example Builders Ltd. | 5-storey sprinklered mixed-use, Calgary; 46 plastic pipe penetrations firestopped with an out-of-scope listed system, found mid-construction | **Remediate to tested CAN/ULC-S115 systems first** (3.1.9.1.(1)), **50 Pa-tested for plastic pipe in this >3-storey building** (3.1.9.4.(4)(b)); variance + IFC-grade EJ only where no tested system exists; sprinkler exception needs NFPA 13 metal escutcheons (3.1.9.1.(4)) |
| [C: Homebuilder](c-homebuilder-infill-house/README.md) | Priya Natarajan, Larkspur Example Homes | 2-storey Edmonton infill: heated slab, unvented low-slope roof, narrow bedroom window | Under-slab **complies via 23-BCV-003** (edges still per 9.36.2.8.(5)/(7)); roof **probably outside 23-BCV-017** as drawn (2% slope, SPF + batt); bedroom window is the departure (**9.9.10.1.(2)**) and needs fall protection (**9.8.8.1.(4)/(5)**, ASTM F2090 WOCD per **23-BCV-001** / Edmonton **B23-02**) |

## Each case contains
- `README.md`: persona, project, compliance split, demo script
- `input/`: what the user uploads (brief as md + **PDF stamped EXAMPLE DATA**, evidence marked EXAMPLE) and `known-gaps.md` (presenter key, don't upload)
- `expected/`: intake summary, article shortlist, Section A–D draft, evidence plan, completeness checklist, SCO review, `must-not.md`

## Tester samples
[`tester-samples/`](tester-samples/README.md): fictional user-testing documents. `01` and `02` are applicant inputs. `03` is the planted-gap SCO submission bundle for the officer timing protocol in `docs/user-testing/` (Round 1b).

`known-gaps.md` and `TESTER-KEY` files are presenter or tester answer keys. Never upload them to the tool.

## Verification legend (used in `sources.md`)
- **WEB:** fetched from the official source on 2026-10-20; snapshot in `_source-snapshots/`
- **CODE-1P:** checked in the NBC(AE) 2023 1st printing (free NRC PDF) by the Data Nerd review
- **RESEARCH:** from the Batatis research notes (`feat/build-foundations`); their 2nd-printing page cites are unverified
- **TO VERIFY:** not confirmed. Phrased generically in the cases.

## Cross-cutting rules applied in every case
- **AHJ** = the accredited organization (the City), acting through its SCOs (SCC IB-2026-10-16).
- From **Dec 1, 2026**, issued variances are registered via the SCC **OVP portal**, with supporting documents and the revised SCC form (IB-2026-10-01; documentation per IB-2025-11-18).
- **Risk assessment and mitigations** are labelled **good practice / SCO expectation**, not Div C 2.3.1.1 requirements. 2.3.1.1 requires code analysis, O&M, assumptions/limiting factors, tests, qualifications and a coordinator.
- Review: [`DATA_NERD_REVIEW.md`](DATA_NERD_REVIEW.md). T-item status is in `sources.md`.

## Re-render a brief
```bash
cd <case-dir> && python3 ../_render_brief.py input/project-brief.md   # needs python-markdown + LibreOffice
```
