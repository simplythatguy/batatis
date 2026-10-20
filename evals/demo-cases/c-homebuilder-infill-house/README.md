# Case C: Homebuilder with a non-standard infill house

> **EXAMPLE DATA.** The people, companies, address and drawings are fictional. Code and STANDATA citations checked against the NBC(AE) 2023 1st printing. See `../sources.md`.

This is a demo case. No loader reads it yet. Only files in `input/` are ever uploaded to the tool. This README contains the demo script, so it is not uploaded. Answer keys are in [`../keys/c-homebuilder-infill-house/`](../keys/c-homebuilder-infill-house/) and are never uploaded.

## Persona
**Priya Natarajan**, owner of **Larkspur Example Homes (fictional)**, Edmonton. She's a small custom builder doing 6–8 houses a year. She's confident with Part 9, but new to variances. Her client wants an architectural "modern box". Her question: *"Which parts of this house need a variance?"*

## Project summary
A **2-storey single-family infill house** (about 210 m², no secondary suite, **unsprinklered**) at 0000 Example Crescent NW, Edmonton *(fictional)*, permit not yet applied for. Three non-standard features:
1. **Hydronic heated slab-on-grade** (no basement) with **RSI 1.32 (R-7.5)** under-slab insulation
2. **Unvented low-slope roof** with closed-cell spray foam at the deck
3. **Bedroom 3 casement window**, a tall, narrow "slot" with a clear opening of **400 × 780 mm = 0.312 m²**

## Why it needs an alternative solution, or doesn't
| Feature | Route | Basis |
|---|---|---|
| 1. Heated slab, RSI 1.32 | **Under-slab covered by a province-wide variance, so no new request.** Reference it on the permit drawings. **Edges still need detailing.** | STANDATA **23-BCV-003** (W6): minimum RSI 1.32 under a heated floor in contact with the ground, Part 9. Varies only the under-slab value in 9.36.2.8.(1) (Zone 7A table: RSI 2.84). The edge/perimeter rules in **9.36.2.8.(5), (7)** still apply at the Table value. With an integral perimeter footing, **9.36.2.8.(9)** applies instead. Edge insulation isn't shown. |
| 2. Unvented roof | **Probably NOT covered by 23-BCV-017 as drawn** | W7 needs the RDH 32139.000 design requirements, with the report in the permit application. The report (W22) covers low slopes **greater than 2%** (this roof is exactly 2%). SPF + batt fill isn't one of its three assemblies (all-exterior insulation; all required R as SPF at the deck; exterior board + MDSPF). Hybrids are only "can also work" with a ratio check (≥60% air-impermeable R in Zone 7A per the report's IBC excerpt). It also needs interior RH ≤35%, CAN/ULC-S705.1/.2 (or S712.1/.2) install, and a certified installer. SPF thickness is TBD. **Fix:** slope >2% and an all-SPF or exterior-insulated assembly, or a site-specific alternative solution. |
| 3. Bedroom 3 window | **Departure, so it needs a site-specific alternative solution, or a fix** | 9.9.10.1.(2): ≥0.35 m² unobstructed opening, no dimension <380 mm. 0.312 m² fails on area. Both dimensions pass. |
| 3b. Bedroom 3 window, fall protection | **Check, for any window chosen** | 2nd floor, sill 450 mm (< 900 mm): **9.8.8.1.(4)/(5)** needs a guard or an opening limiter (≤100 mm, released only with tools or special knowledge), unless the bottom edge is <1800 mm above the ground outside. Note A-9.8.8.1.(4): **a rotary operator can't be the limiter or guard** (supplier: "standard rotary operator"). A tool-release limiter would conflict with 9.9.10.1.(1). **STANDATA 23-BCV-001** resolves this: an **ASTM F2090** window opening control device (WOCD) satisfies both (not in adaptable or barrier-free units). **Edmonton Policy B23-02** adds inspection criteria (≤102 mm, dual action, visible mechanism on egress windows, auto-reset, owner info at inspection). |

**Routes inside the cited sentences the tool should offer first for #3:** enlarge the opening to ≥0.35 m² (e.g. 450 × 780 mm = 0.351 m², a design-team check); or another bedroom window that meets (2); or the **sprinkler exception in 9.9.10.1.(1)** ("Except where the suite is sprinklered…"). **Whichever window is used still needs an F2090 WOCD (23-BCV-001) or a guard** for 9.8.8.1.

## Demo script (about 6 minutes)
1. **Upload** `input/project-brief.pdf` and `input/drawing-notes.md`. **Type:** *"Which parts of this house need a variance?"*
   → Split: **#1 covered by STANDATA 23-BCV-003, no new request, the officer confirms (but the slab edges need a detail per 9.36.2.8.(5)/(7)), #2 probably doesn't meet 23-BCV-017's conditions as drawn, #3 is a departure and also needs fall protection.** It doesn't propose three variance requests.
2. **Type:** *"Can we drop the under-slab to R-5 since there's a STANDATA?"* → No. 23-BCV-003 sets a **minimum of RSI 1.32 (R-7.5)**.
3. **Type:** *"Is the roof fine?"* → Probably not as drawn: a 2% slope (the report needs >2%), and SPF + batts isn't one of the report's three assemblies. The tool proposes a redesign or a site-specific alternative solution, not "fine".
4. **Type:** *"Draft the variance for the bedroom window."* → First it offers the routes that stay inside the cited sentences, then a Section A–D draft with rows 9.9.10.1.(1)/(2), [F10-OS3.7], and intent cells flagged GAP: intent lookup not available.
5. **Type:** *"Add that the client is OK with the risk."* → The tool explains that owner acceptance isn't equivalence. The risk assessment and mitigations must address the code intent.
6. **Type:** *"Do I need an engineer or architect to sign this?"* → Not by default for a single-family house (Div C 2.4.1.1.(1)), but the AHJ (the City as accredited municipality, through its SCO) may require it (2.4.1.1.(4)).
6b. **Type:** *"Can the window's crank handle count as the opening limiter?"* → No. A rotary operator can't serve as the limiter (Note A-9.8.8.1.(4)). Use an ASTM F2090 WOCD per 23-BCV-001 / Edmonton B23-02.
7. **SCO role:** upload the draft → completeness review.

## Files
- `input/`: the only files uploaded to the tool — `project-brief.md`, `project-brief.html`, `project-brief.pdf`, `drawing-notes.md`, `window-supplier-note-EXAMPLE.md`
- [`../keys/c-homebuilder-infill-house/presenter/known-gaps.md`](../keys/c-homebuilder-infill-house/presenter/known-gaps.md): presenter answer key (never upload)
- [`../keys/c-homebuilder-infill-house/expected/`](../keys/c-homebuilder-infill-house/expected/): intake summary, article shortlist, Section A–D draft, evidence plan, completeness checklist, SCO review, must-not
