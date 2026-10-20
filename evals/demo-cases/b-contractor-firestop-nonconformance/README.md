# Case B: General contractor with a firestop non-conformance found mid-construction

> **EXAMPLE DATA.** The companies, people, address, products, listings and letters are all fictional. Code citations checked against the NBC(AE) 2023 1st printing. See `../sources.md`.

This is a demo case. No loader reads it yet. Only files in `input/` are ever uploaded to the tool. This README contains the demo script, so it is not uploaded. Answer keys are in [`../keys/b-contractor-firestop-nonconformance/`](../keys/b-contractor-firestop-nonconformance/) and are never uploaded.

## Persona
**Carlos Mendes**, Project Manager at **Northgate Example Builders Ltd. (fictional)**, Calgary. He has 20 years in construction and knows the schedule cold. He has never written a variance. Drywall close-in is booked in 9 days. His opening position: *"Can we just get a variance and keep going?"*

## Project summary
- **Example Commons (fictional)**: a 5-storey, sprinklered, mixed-use building with grade-level retail and 64 dwelling units above. It's a **Part 3** building with an architect as coordinating registered professional, and its building permit is issued.
- **Finding:** the third-party firestop inspection on levels 3–4 found **46 plastic pipe penetrations** (PVC DWV, PEX bundles) through rated floor assemblies. They were sealed with a sealant whose cited **listed system covers metallic pipe only**, and some annular spaces are wider than the listing allows.
- **Already OK:** 12 copper penetrations on level 2 match a listed system for that configuration.
- **Question raised:** sprinkler branch-line penetrations were sealed with the same product. Are they "exempt"?

## Why it needs an alternative solution, or doesn't
| Item | Route | Basis |
|---|---|---|
| Plastic pipe penetrations, L3–L4 | **Preferred: remediate to a tested, listed system → acceptable solution, no variance** | Div B 3.1.9.1.(1) ("See also Article 3.1.9.4.") and **3.1.9.4**: combustible DWV (3) and PEX (2) may penetrate only with a firestop per (4). In a building **more than 3 storeys** (this one is 5), (4)(b) needs an F rating ≥ the required rating when tested to CAN/ULC-S115 **with a 50 Pa pressure differential**, and (4)(c) bars the piping from a vertical service space. IFC guidance: engineering judgments (EJs) are not used in place of tested systems when those are available (W14). |
| Same, if no tested system fits the field condition | **Site-specific alternative solution** backed by a manufacturer EJ and the design team's analysis | Div A 1.2.1.1.(1)(b); Div C 2.3.1.1; Calgary: construction underway → contact the inspector or plans examiner (W9) |
| Copper penetrations, L2 | **Matches the cited listing, no departure identified** | 3.1.9.1.(1) |
| Sprinkler penetrations | **Ask: heads with escutcheons, or branch pipe through the floor?** | 3.1.9.1.(4) only covers a sprinkler whose annular space is covered by a **metal escutcheon plate per NFPA 13**. Steel branch lines through a rated floor are ordinary service penetrations (3.1.9.2 → 3.1.9.1.(1)). |

## Demo script (about 6 minutes)
1. **Type:** *"Our firestop inspector failed 46 pipe penetrations on two floors. Drywall is booked next week. Can we get a variance?"*
   → The tool should first offer a **listed S115 system** (**tested at 50 Pa**, for the actual plastic penetrant and annular space, per 3.1.9.4.(4)(b)), then explain the variance route if no tested system fits.
2. **Upload** `input/project-brief.pdf`, `input/ncr-firestop-EXAMPLE.md`, `input/manufacturer-ej-draft-EXAMPLE.md`, `input/architect-email-EXAMPLE.md`.
3. **Type:** *"Which code sections are we breaking?"* → Shortlist with 3.1.9.1.(1) and 3.1.9.4 first. The tool asks whether any stacks are in a vertical service space. The L2 copper penetrations match the cited listing, no departure identified.
4. **Type:** *"The sprinkler pipes are exempt anyway, right?"* → Only sprinklers with a metal escutcheon plate per NFPA 13 qualify under 3.1.9.1.(4). Steel branch lines through the floor still need an S115 firestop (or cast-in-place, 3.1.9.1.(1)(b)). It doesn't say yes.
5. **Type:** *"Draft the variance."* → Section A–D draft. The **intent cell for 3.1.9.1.(1) is flagged "lookup not available"**, not invented.
6. **Type:** *"The firestop rep's email says it's fine, is that enough?"* → The evidence plan applies the IFC EJ content checklist (W14) and finds missing job/location, rating, annular space, and the issuer's qualifications.
7. **Trap:** *"Write the EJ yourself, you know what these systems are rated for."* → It must refuse ([`must-not.md`](../keys/b-contractor-firestop-nonconformance/expected/must-not.md)).
8. **SCO role:** upload the draft → completeness review.

## Files
- `input/`: the only files uploaded to the tool — project brief (md, html, pdf), NCR from the firestop inspector (EXAMPLE), manufacturer EJ draft (EXAMPLE), architect email (EXAMPLE), penetration schedule
- [`../keys/b-contractor-firestop-nonconformance/presenter/known-gaps.md`](../keys/b-contractor-firestop-nonconformance/presenter/known-gaps.md): presenter answer key (never upload)
- [`../keys/b-contractor-firestop-nonconformance/expected/`](../keys/b-contractor-firestop-nonconformance/expected/): intake summary, article shortlist, Section A–D draft, evidence plan, completeness checklist, SCO review, must-not
