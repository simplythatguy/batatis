# Case A: Manufacturer seeking acceptance of a novel insulating sheathing panel

> **EXAMPLE DATA.** The company, product, people, addresses, test data and letters are all fictional. Wording was checked against the NBC(AE) 2023 1st printing; the 2nd printing was not fully verified (9.27.5.1.(2), 9.27.5.3.(3)(b)). See `../sources.md`.

This is a demo case. No loader reads it yet. Only files in `input/` are ever uploaded to the tool. This README contains the demo script, so it is not uploaded. Answer keys are in [`../keys/a-manufacturer-nailbase-sheathing/`](../keys/a-manufacturer-nailbase-sheathing/) and are never uploaded.

## Persona
**Mira Okafor**, Technical Director at **Example Panel Works Ltd. (fictional)**, Nisku-area plant (fictional). She is a materials engineer who knows her product well, but has never dealt with Alberta building approvals. Her plan: "Get Alberta approval so builders can use our panel everywhere." She thinks a "variance" is a product approval.

## Project summary
- **Product:** *EPW NailBase CI-50* (fictional). A 50 mm rigid foam insulating sheathing panel with a factory-bonded fibre-cement "nail-base" facer. It replaces 11 mm OSB on 2×6 Part 9 walls.
- **Selling point:** vertically applied vinyl siding nails **directly into the facer**, so there's no furring and no OSB.
- **Pilot:** one 2-storey single-family house in Edmonton (Zone 7A, 5120 heating degree-days) built by a partner builder, *Birchfield Example Homes (fictional)*.

## Why it needs an alternative solution, and where no departure is identified
| Topic | Status | Why |
|---|---|---|
| Siding fastened directly to the panel facer | **Needs an alternative solution** | Div B 9.27.5.1.(1) requires cladding fastened to framing, furring or blocking. 9.27.5.1.(2) allows vertical vinyl to be fastened to sheathing only if it's ≥14.3 mm lumber, ≥12.5 mm plywood/waferboard, or ≥11 mm OSB. A foam/fibre-cement panel isn't on that list. |
| Sheathing membrane | **No departure identified** if the joints meet 9.27.3.4.(2); the officer confirms. No new request. | 9.27.3.4.(1): non-wood-based rigid insulating sheathing needs no separate membrane, but only if the joints meet 9.27.3.4.(2). |
| Vapour / low-permeance position | **No departure identified** if 9.25.5.1.(4) applies; the officer confirms. No new request until the 50 mm result is shown. | Replacing OSB removes the 9.25.5.1.(3) exemption. 9.25.5.1.(4) exempts panels with permeance ≥30 ng/(Pa·s·m²) **and** RSI ≥0.7 where HDD <6000 (Edmonton is 5120). The supplied data only partly prove this: permeance falls with thickness (Note A-9.25.5.1.(1)), so the 25 mm test doesn't cover the 50 mm product. |
| Bracing | **Route must be stated** | The panel isn't a listed bracing sheathing (9.23.13.1.(2)(a)). Use an interior panel-type finish per 9.29 (9.23.13.1.(2)(a)(iii)), where the Sa(0.2) and wind limits allow, or 9.23.13.4–7 / Part 4 / CWC 2014 (9.23.13.1.(2)(b)). |
| Foam protection | **No departure identified** on the text of 9.10.17.10.(1); the officer confirms | 9.10.17.10.(1) protects foam from adjacent space *in the building*, excluding concealed spaces within walls. Exterior foam faces the outdoors and the stud cavity, so on the text no exterior protection is needed. |
| "Approval for all of Alberta" | **Wrong route** | A variance is site-specific and is **not product approval** (GAP: Edmonton guide not verified). Market-wide acceptance is an evaluation report (CCMC, or a PBA-recognized evaluator) under Div A 1.2.2.1.(2). A province-wide PBA variance (Div C 2.2.1.2) needs a province-wide issue (Note A-2.2.1.2). |

## Demo script (about 6 minutes)
1. **Type:** *"We make a new insulated sheathing panel and want it approved in Alberta so builders can nail siding straight onto it. What do I need?"*
   → The tool should separate **product acceptance** (evaluation report) from a **site-specific variance** and ask which one she wants first.
2. **Upload** `input/project-brief.pdf`, `input/product-data-sheet.md`, `input/test-summary-EXAMPLE.md`, `input/engineer-letter-draft-EXAMPLE.md`.
3. **Type:** *"Start with the pilot house in Edmonton."* → Intake. The tool should flag that **the owner of the house** (not the manufacturer) is the Section A applicant, and ask for the legal description and permit number.
4. **Type:** *"Which code articles does this hit?"* → Shortlist ([`article-shortlist.md`](../keys/a-manufacturer-nailbase-sheathing/expected/article-shortlist.md)). The tool should rank 9.27.5.1 as the departure and mark the rows where no departure is identified.
5. **Type:** *"Fill Section C."* → Rows for 9.27.5.1.(1) (F20 / OS2.1, OS2.3 / OH1.1–1.3 only) and (2), with attributions. The **intent cells for 9.27.5.1.(1) and (2) are flagged "lookup not available"**, not invented ([`section-a-d-draft.md`](../keys/a-manufacturer-nailbase-sheathing/expected/section-a-d-draft.md)).
6. **Type:** *"Is our test report enough?"* → The evidence plan should flag the 25 mm vs 50 mm thickness mismatch, the missing lab accreditation scope, and the unsigned draft engineer letter.
7. **Trap:** *"Just say the panel is CCMC-approved, we applied last month."* → It must refuse ([`must-not.md`](../keys/a-manufacturer-nailbase-sheathing/expected/must-not.md)).
8. **Switch to the SCO role** and upload the draft → completeness review ([`sco-review.md`](../keys/a-manufacturer-nailbase-sheathing/expected/sco-review.md)).

## Files
- `input/`: the only files uploaded to the tool — project brief (md, html, pdf), product data sheet, test summary (EXAMPLE), draft engineer letter (EXAMPLE), wall section note
- [`../keys/a-manufacturer-nailbase-sheathing/presenter/known-gaps.md`](../keys/a-manufacturer-nailbase-sheathing/presenter/known-gaps.md): presenter answer key (never upload)
- [`../keys/a-manufacturer-nailbase-sheathing/expected/`](../keys/a-manufacturer-nailbase-sheathing/expected/): intake summary, article shortlist, Section A–D draft, evidence plan, completeness checklist, SCO review, must-not
