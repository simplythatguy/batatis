# Development-case source review — 2026-10-20

Status: **model-checked development fixtures; not human reviewed**. GPT-6.1-Sol at max reasoning
performed the review and new authoring in the isolated `t3/c1caa94e` worktree, starting from
`df9440387f0a790dedc97aefb916e24232eebaf1`. No further agents were delegated. The parent maintenance
result was reused as instructed. October 29 remains the stated project deadline.

The tooling integration repair resumed from dataset commit `37f04bf01c15d629988b69c8a6ec950562c4bcbd`
with expanded ownership of the author script, tests, schema documentation and the independently
reported `dev-027` geometry correction. The current full `evals_dev` suite is green; the former
integration blockers and their resolutions are recorded below.

The 25 inherited cases were checked against provision text, applicability, permissions/exceptions,
Division C professional-involvement rules and exact Section C lookup output. Nineteen files were
revised, including explicit changes to synthetic applicant facts where necessary to make the intended
scenario determinate. These additions are fixture-authoring choices, not facts inferred about a real
applicant. Eight original `proceed_conditionally` cases became `ask`. Two professional flags changed
from `yes` to `depends`. Thirty-five additional cases bring the total to **60**.

**Human/professional review completed: zero cases in this task.** An independent source check by the
same model is not an independent human review, a multi-model consensus, or an SCO determination.
Neither protected judge cases nor archive-branch evaluations were opened. No held-out accuracy,
engine accuracy, structural adequacy, product acceptance, design safety or code compliance is claimed.

## Sources and reproducibility

All code references use **NBC – 2023 Alberta Edition, 2nd printing**. Page numbers below are
one-based pages of the combined PDF, not printed volume page labels. Division B is implicit in the
ledger unless another division is named. National intent statements were not substituted for Alberta
attributions or used to supply missing Section C pairs.

- Python: `/Users/aamia/.t3/projects/batatis/.venv/bin/python`.
- CodeDB, opened read-only: `/Users/aamia/.t3/projects/batatis/codedb/build/codedb.sqlite`.
- Lookup calls supplied `division` and the explicit `db_path`; no default worktree database was used.
- Canonical PDF: `/Users/aamia/.t3/projects/batatis/reference/codes/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.pdf`.
- Canonical extracted text: `/Users/aamia/.t3/projects/batatis/reference/text/NBC-AE-2023-2nd-printing-FULL-Vol1+Vol2.jsonl`.
- CodeDB SHA-256: `0bc82c760700f8f638387a573a6bbf9a24cb93ea7cb45aef9698c5f63f721660`.
- PDF SHA-256: `3d45376d6c71d54b7f1797084d0828c250b20ab9b380f424f1aab8cfc9a39827`.
- Extracted-text SHA-256: `923483af04ebba73d9dd8c31742c7eb05f0eca018a3dd67c29bab532e350af29`.

Both source hashes match `meta.stats.sources.NBC-AE` in the database. The `docs.sha256` column stores
the **extracted-text** hash, not the PDF hash; an initial scratch comparison against that column was
corrected after reading the source registry/build code. There is no source-hash mismatch.

Relevant text and conditional provisions were read through CodeDB. The local PDF supplied the table
detail missing from provision-only rows: Table 9.23.10.1, PDF p.975; Table 9.25.5.2, PDF p.1000; and
Table D-6.1.1, PDF pp.716–717. Rendered pages 975, 1000 and 716 were visually inspected with
`pypdfium2` and the image-view tool because Poppler was unavailable. Definitions of party wall and
secondary suite were checked against PDF pp.48 and 50. This was targeted PDF inspection, not a
page-by-page visual audit of the entire code.

## Coverage

The 35 new fixtures comprise 27 `proceed_conditionally`, **six new `ask`** (`dev-053`–`dev-058`) and
**two new `redirect`** (`dev-059`–`dev-060`). Of the new cases, 24 have Part 3 or Part 4 seeds. Applicant
descriptions are unique, contain no article numbers and are the only intended system-under-test input;
the seed, gold labels and authoring receipts remain evaluator metadata.

| Division B Part label | Final cases |
| --- | ---: |
| 3 | 17 |
| 4 | 12 |
| 9 | 21 |
| Undecided / separate regime (`null`) | 10 |
| **Total** | **60** |

Of the ten `null` labels, six are unresolved-route `ask` cases and four are redirects. `out_of_scope`
is true only for the four redirects; an undecided Part is not an out-of-scope finding.

| Applicant | Final cases |
| --- | ---: |
| architect-engineer | 14 |
| contractor | 13 |
| homebuilder | 8 |
| manufacturer | 14 |
| owner | 11 |

| Intake action | Final cases |
| --- | ---: |
| ask | 18 |
| proceed_conditionally | 38 |
| redirect | 4 |

Professional-involvement flags: 33 `yes`, 17 `depends`, 10 `no`. The existing field name
`engineering_required` is retained; the Division C references identify the appropriate registered
professional involvement, not a claim that every architectural task requires every engineering
discipline. `no` is subject to the AHJ's special-safety power.

## Audit of all 25 inherited cases

“Retained” means the source check found no clear fixture correction to make; it does not mean human
approval. Section C pairs in the original 25 files already matched the database. Changes below address
semantic labels and applicability, and rebuild Section C only where a benchmark changed or became
undecided.

| Case | Disposition and correction | Source citation and PDF page |
| --- | --- | --- |
| dev-001 | Retained soffit benchmark and `no` flag. Added explicit two-storey / 150 m² synthetic building scope so Part 9 does not depend on hidden metadata. | Div A 1.3.3.3.(1), p.40; 9.10.15.5.(8), p.904; Div C 2.4.1.1.(1), pp.739–740. |
| dev-002 | Corrected one-lot wording to six fee-simple parcels with actual parcel-boundary party walls. Explicitly states one unseparated building, six primary dwellings and total building area 500 m². Retained the firewall benchmark and `yes`; secondary suites are not added to the professional dwelling count. | 9.10.11.2.(1)–(3), pp.889–890; Div A 1.4.1.2.(1), party-wall definition p.48; Div C 2.4.1.1.(1)–(3), pp.739–740. |
| dev-003 | Retained damper benchmark and `yes`. Added 480 m² building area to establish the three-storey residential Part 9 scope. The 375 cm² branch duct exceeds the 130 cm² exception threshold, independently of its stated HRV service. | Div A 1.3.3.3.(1), p.40; 9.10.13.13.(1)–(5), pp.893–894; Div C 2.4.1.1.(3), p.740. |
| dev-004 | Replaced 9.10.14.2.(2) with **9.10.15.2.(3)** for side-by-side dwellings with none above another. Added 240 m² area and an actual window in front of the proposed calculation plane. Rebuilt Section C: still `none`, with no invented pairs. | 9.10.14.1.(1), p.894; 9.10.15.1.(1), 9.10.15.2.(3), p.900; 9.10.15.4.(1), p.901. |
| dev-005 | **Proceed → ask.** Small apartments and a product-wide request do not establish the Part, exposing-face table conditions or tested-wall permission. Moved former mandatory references into conditional candidates; cleared departure and Section C. | 9.10.14.5.(1)–(2), p.897; 3.1.5.5.(1), (4), p.137; Div A 1.3.3.3.(1), p.40. |
| dev-006 | **Proceed → ask.** Thickness and an R-20 batt label do not prove the complete thermal-resistance ratio. Requested properties, layer order, climate and moisture use. Corrected the vented-space question: the board must be **outboard of** that space. Clarified that Part 5 alone is not the specific Part 4 professional trigger. | 9.25.5.1.(1)–(4), pp.999–1000; 9.25.5.2.(1), Table 9.25.5.2, p.1000; Div C 2.4.1.1.(1), (4) and 2.4.1.2.(1), pp.739–740. |
| dev-007 | **Proceed → ask.** Semi-rigid mineral wool is not established as qualifying rigid insulating sheathing. Ask for rigidity, drainage and joint design before applying the membrane-replacement permission and its joint rule. Added explicit bungalow size. | 9.27.3.1.(1), 9.27.3.4.(1)–(2), p.1015; Div A 1.3.3.3.(1), p.40. |
| dev-008 | Replaced the inaccurate “unsheathed” conclusion: rigid foam is itself sheathing. New benchmark **9.23.17.3.(1)** addresses using rigid insulation for cladding attachment. The synthetic description now explicitly proposes intermediate fasteners into foam alone. Added house size; retained conditional professional flag for the separate lateral design. | 9.23.17.1.(1), 9.23.17.2.(1), p.989; **9.23.17.3.(1), p.990**; 9.23.13.1.(2), p.978; Div C 2.4.1.2.(1), p.740. |
| dev-009 | **Proceed → ask.** Climate thresholds and assembly exceptions were unknown, not established departures. Ask for degree-days, moisture index, materials and exception basis. | 9.27.2.2.(1), p.1013; 9.27.2.2.(5)–(6), p.1014. |
| dev-010 | **Proceed → ask.** Vinyl is not categorically prohibited at the stated distance: conditional thickness, flame-spread, backing and attachment routes exist. Requested those details and removed the unsupported “owner-occupied” known fact. | 9.10.15.5.(2), p.902; 9.10.15.5.(4), p.903; Div C 2.4.1.1.(1), pp.739–740. |
| dev-011 | **Proceed → ask; professional yes → depends.** Table comparison was checked visually: 38 × 89 mm exterior studs carrying roof plus one floor are listed at 400 mm, not 600 mm. But the proprietary header/load path, unsupported height and design route still need clarification; a table departure does not alone establish Part 4 as the only route. | 9.23.10.1.(1), p.974 and Table 9.23.10.1, p.975; 9.4.1.1.(1), pp.836–837; Div C 2.4.1.1.(1), (4) and 2.4.1.2.(1), pp.739–740. |
| dev-012 | **Proceed → ask; professional yes → depends.** Requested site wind/seismic values and actual assembly/design basis. Supplier values alone do not establish an out-of-prescriptive Part 4 route or that the cited low-force article applies. | 9.23.13.1.(1)–(2), p.978; 9.4.1.1.(1), pp.836–837; Div C 2.4.1.1.(1), (4) and 2.4.1.2.(1), pp.739–740. |
| dev-013 | Retained: four-storey, multi-unit common single stair falls outside the two-storey single-exit permission; professional `yes`. | 3.4.2.1.(1)–(4), pp.269–270; Div C 2.4.1.1.(3), p.740. |
| dev-014 | Retained: third-storey common floor area with one exit; a dwelling-unit balcony provision does not establish the common floor-area exit allowance. Six primary dwellings trigger professional involvement. | 9.9.8.2.(1)–(2), p.871; 9.9.9.1.(3), p.872; Div C 2.4.1.1.(1), (3), pp.739–740. |
| dev-015 | **Proceed → ask.** “Small skylights” supplies no clear opening/sill measurements, and balcony access and suite arrangement were unstated. Cannot assert the window/balcony exceptions fail. | 9.9.9.1.(1)–(3), p.872. |
| dev-016 | Retained tested-wall benchmark with `none` Section C status. Clarified the synthetic cladding as solid boards rather than plywood, excluded the prescriptive Appendix D wall route, and stated sprinkler coverage throughout. No automatic substitution of European test evidence for Canadian criteria. | 3.1.5.5.(1), (4), p.137; Table D-6.1.1 and notes, pp.716–717; Div C 2.4.1.1.(3), p.740. |
| dev-017 | Retained encapsulation benchmark: 60% exposed ceiling exceeds both ceiling permissions, regardless of the unresolved flame-spread value. Added forty apartments to make the professional trigger explicit. | 3.1.6.4.(1), (2), (6), p.146; Div C 2.4.1.1.(1), (3), pp.739–740. |
| dev-018 | Retained default-factor and reduction references, including the reduction sentence's `none` attribution status. Explicitly states Part 4 design for the professional flag. | 4.1.6.2.(3)–(4), p.438; Div C 2.4.1.2.(1), p.740. |
| dev-019 | Retained CFD prohibition, with explicit Part 4 structural cladding-anchor design in the synthetic description. | 4.1.7.1.(5)–(6), p.452; Div C 2.4.1.2.(1), p.740. |
| dev-020 | Retained `ask`: height, size, occupancy and sprinklers can change the single-exit route. | 3.4.2.1.(1)–(2), p.269; 9.9.8.2.(1)–(2), p.871. |
| dev-021 | Retained `ask`: wall/soffit distances and public-way status are decisive. `no` is subject to the AHJ override. | 9.10.15.5.(8)–(10), p.904; Div C 2.4.1.1.(1), (4), pp.739–740. |
| dev-022 | Retained `ask`, but removed the unsupported categorical assertion that every variance is project-specific. Ask about the intended application scope instead. Division C requires documentation of the actual proposed alternative; it does not establish that assertion. The repository workflow also records jurisdiction-wide template scope. | Div C 2.3.1.1.(1)–(5), p.739; 9.25.5.1.(1), p.999 and 9.25.5.2.(1), p.1000 are candidate technical routes only. |
| dev-023 | Retained `ask` and residential professional `no`, but corrected the reason: evaluate the detached building's residential exemption, not a property-wide secondary-suite exclusion. Removed the suite-count exclusion citation from this decision. | Div A 1.4.1.2.(1), secondary-suite definition p.50; Div C 2.4.1.1.(1), (4), pp.739–740; candidate 9.10.15.5.(2)–(3), pp.902–903. |
| dev-024 | Retained plumbing redirect; no plumbing technical acceptance or professional determination made. | 7.1.2.1.(1), p.621. |
| dev-025 | Retained electrical redirect; no cable/material technical acceptance or professional determination made. | 9.34.1.1.(1), p.1064. |

## New provision-seeded cases

All are new applicant narratives. Reusing a provision for a meaningful contrast does not mean that an
existing narrative was paraphrased: for example, a fully quantified insulation departure contrasts with
an under-specified product request, and a 25% timber-ceiling question contrasts with an over-limit 60%
proposal. Numeric facts are synthetic design inputs, not claimed real measurements or manufacturer
data. In particular, `BTRboard` in `dev-055` has **no assumed composition, rating, certification,
structural capacity, air leakage or vapour permeance**.

| Case | Scenario / deciding distinction | Seed; PDF page | Action |
| --- | --- | --- | --- |
| dev-026 | Assembly hall, 120 occupants, one exit; occupant-load condition fails. | 3.4.2.1.(1); 269 | proceed_conditionally |
| dev-027 | Office exits only 4 m apart; 30 × 40 m rectangular floor has a 50 m diagonal and no intervening fire separation. | 3.4.2.3.(1); 271 | proceed_conditionally |
| dev-028 | Doorway directly through separation between scissors stairs. | 3.4.4.4.(3); 275 | proceed_conditionally |
| dev-029 | Shared laundry opens directly into an exit. | 3.4.4.4.(8); 275 | proceed_conditionally |
| dev-030 | Common office exit door swings against exit travel. | 3.4.6.12.(1); 281 | proceed_conditionally |
| dev-031 | Seven-storey unsprinklered noncombustible office proposes combustible cladding. | 3.1.5.5.(1); 137 | proceed_conditionally |
| dev-032 | Fire-retardant-treated timber cladding omits weathering before fire testing; Appendix D option excluded. | 3.1.5.5.(3); 137 | proceed_conditionally |
| dev-033 | Top residential floor at 42 m; bells/app replace installed voice communication. | 3.2.6.8.(1); 239 | proceed_conditionally |
| dev-034 | Tall residential building omits a firefighter-use elevator. | 3.2.6.5.(3); 237 | proceed_conditionally |
| dev-035 | CLT adhesive does not meet required elevated-temperature performance. | 3.1.6.3.(3); 145 | proceed_conditionally |
| dev-036 | Opposite-facing exposed timber walls; area alone does not establish the exception. | 3.1.6.4.(1); 146 | proceed_conditionally |
| dev-037 | Combustible strips exceed area and vertical-continuity permissions on mass timber building. | 3.1.6.9.(1); 148 | proceed_conditionally |
| dev-038 | Opposite-side outlet boxes in rated mass timber only 250 mm apart. | 3.1.6.17.(3); 151 | proceed_conditionally |
| dev-039 | Roof snow-load reduction based on a snow-removal contract. | 4.1.6.14.(1); 450 | proceed_conditionally |
| dev-040 | Main structure of 70 m tower uses static wind only despite height classification. | 4.1.7.1.(3); 452 | proceed_conditionally |
| dev-041 | Part 4 timber wall design substitutes proprietary/European design basis for CSA O86. | 4.3.1.1.(1); 511 | proceed_conditionally |
| dev-042 | Part 4 structural steel package uses Eurocode 3 without CSA S16 conformity. | 4.3.4.1.(1); 512 | proceed_conditionally |
| dev-043 | Part 4 floor omits all serviceability checks. | 4.1.3.4.(1); 428 | proceed_conditionally |
| dev-044 | Partial-area live loading omitted even where more critical. | 4.1.5.3.(1); 430 | proceed_conditionally |
| dev-045 | Part 4 foundations omit a professionally directed subsurface/groundwater investigation. | 4.2.2.1.(1); 505 | proceed_conditionally |
| dev-046 | Foundation design ignores known hydrostatic uplift. | 4.2.4.8.(1); 508 | proceed_conditionally |
| dev-047 | Reused foundations are not checked against requirements for the altered building. | 4.2.8.2.(1); 511 | proceed_conditionally |
| dev-048 | Explicit insulation properties and 6,500 degree-days: RSI ratio 0.125 versus table minimum 0.35. | 9.25.5.2.(1); 1000 | proceed_conditionally |
| dev-049 | High-moisture pool-room envelope proposes no Part 5 design. | 9.25.5.1.(2); 999 | proceed_conditionally |
| dev-050 | An 18 m wood structural-member span exceeds the Part 9 framing scope; required Part 4 route omitted. | 9.23.1.1.(2); 962 | proceed_conditionally |
| dev-051 | Internal secondary-suite alarms connected only within each dwelling. | 9.10.19.5.(2); 910 | proceed_conditionally |
| dev-052 | Multi-storey main dwelling lacks rated separation; proposed 9.5 mm gypsum does not meet the secondary-suite permission. | 9.10.9.16.(3); 886 | proceed_conditionally |
| dev-053 | Small-office single exit: missing dimensions, load, sprinklers and travel. | 3.4.2.1.(2); 269 | ask |
| dev-054 | Timber-look panel appearance does not establish combustibility or construction regime. | 3.1.5.5.(1); 137 | ask |
| dev-055 | BTRboard proposed for multiple roles without material, joint or structural details. | 9.27.3.4.(1); 1015 | ask |
| dev-056 | Part 4 snow exposure reduction: rural/open exposure, importance, obstructions and drift unknown. | 4.1.6.2.(4); 438 | ask |
| dev-057 | Customer's “secondary suite” label does not establish arrangement, use or existing assembly. | 9.10.9.16.(4); 886 | ask |
| dev-058 | Exactly 25% exposed timber ceiling: flame spread and exposed-wall conditions unknown. | 3.1.6.4.(6); 146 | ask |
| dev-059 | Gas supply piping/regulator only; building clearance changes explicitly excluded. | 9.10.22.1.(1); 911 | redirect |
| dev-060 | Private sewage tank/disposal-field design, without building/foundation work. | 7.1.2.1.(1); 621 | redirect |

## Adversarial findings and disputed labels

Applied pstack's evidence/lead-judgment approach directly, without spawning reviewers, as instructed.
There is no fabricated agreement map or claim of independent model diversity.

- **Acted on:** wrong house subsection (`dev-004`), wrong foam/sheathing benchmark (`dev-008`), eight
  unsupported proceed labels, two overbroad professional `yes` flags, and scope/definition assumptions
  listed above. The remedy either asks for deciding facts or explicitly narrows the synthetic scenario.
- **Consider / human professional review:** `dev-011` and `dev-012` now use `depends`, not `no`.
  Div B 9.4.1.1.(1) permits more than a simple prescriptive-versus-Part-4 binary. Div C 2.4.1.2.(1)
  expressly requires a registered professional for Part 4 design, but does not settle all practice-law
  questions for every other design route. The actual designer qualifications and AHJ requirements
  need human review. Sources: PDF pp.836–837 and 739–740.
- **Consider / conditional building boundary:** `dev-002` retains `yes` for the expressly proposed one
  building containing six primary dwellings without internal firewalls. A different legally established
  building/firewall arrangement could change that count; do not carry the flag over to another
  arrangement automatically. Sources: Div B 9.10.11.2.(2), pp.889–890; Div C 2.4.1.1.(1)–(3),
  pp.739–740. The fixture is not a legal opinion on a real parcel plan.
- **Consider / Part 5 professional trigger:** `dev-006` and `dev-049` use `depends`. Requiring a Part 5
  envelope design is not itself the specific Part 4 trigger in Div C 2.4.1.2.(1). Building exemption,
  actual professional scope and AHJ special-safety requirements remain material. Sources: Div B
  9.25.5.1.(2), p.999; Div C 2.4.1.1.(1), (4) and 2.4.1.2.(1), pp.739–740.
- **Noted / override:** every `no` professional flag is scoped to the described building/work and the
  general exemption. Div C 2.4.1.1.(4), p.740 permits an AHJ special-safety requirement. A flag is not a
  promise that no professional will be requested.
- **Dismissed:** inventing Section C pairs from a heuristic root, national intent commentary or
  apparent policy purpose. A `none` database row stays empty. The nine no-row sentences are
  `dev-004`, `dev-008`, `dev-016`, `dev-018`'s reduction sentence, `dev-031`, `dev-032`, `dev-041`, `dev-042`
  and `dev-050`; `root_provision` is metadata, not an attribution.

`proceed_conditionally` means a particular benchmark can be identified from the supplied proposal.
It does not prove a variance is necessary under every possible acceptable-solution route or that
alternative evidence is adequate. Risk assessment, mitigating measures, assumptions/limits and actual
supporting documents remain applicant/professional work. No Section D opinion or invented test
result, approval, certification or engineering calculation was authored.

## Independent model fixture consistency correction

The parent relayed an independent source-review model's finding that `dev-027` combined a 1,200 m²
floor with a maximum diagonal of 30 m, which is geometrically impossible. Corrected the applicant
description and known facts to a **30 × 40 m rectangle with a 50 m diagonal**: area 1,200 m² and
diagonal `sqrt(30² + 40²) = 50 m`. Gold labels, intake action, Section C values and the original
authoring receipt are unchanged.

The 4 m exit separation remains below the capped 9 m requirement: one-half of 50 m is 25 m, capped
at 9 m for the stated public-corridor case. Source: **Div B 3.4.2.3.(1)(a), PDF p.271**. This is an
independent **model** fixture-consistency correction reported by the parent, not human review, a
professional opinion or an additional claim about source-label accuracy. This worker did not spawn
another reviewer.

## Verification and integration repair

The initial 25-file validator run passed: 107 citation checks, 21 Section C rows, 56 attribution
brackets/conditions and three no-row sentences. The following final results apply to the revised
60-file set; complete command output was checked, not inferred from an authoring success message.

```text
/Users/aamia/.t3/projects/batatis/.venv/bin/python evals_dev/validate_cases.py \
  --db /Users/aamia/.t3/projects/batatis/codedb/build/codedb.sqlite
exit 0; ok: true; errors: []
```

Final validator totals: **60 cases, 249 citation checks, 39 Section C rows, 68 attribution
brackets/conditions and nine no-row sentences**. These are database-conformance checks, not a semantic
accuracy score. The final rows cover `direct` and `none` statuses; there are no nonempty conditional
rows or `clause_level` rows in this set. Equality checks therefore do not establish positive coverage
of those attribution shapes in the 60 reviewed narratives. The refresher's focused CLI test does exercise
a nonempty conditional attribution against the real database in a temporary copy; that is tooling
verification, not a new reviewed case. A final semantic pass also corrected the new `dev-052` seed from the general suite
sentence to the multi-storey-dwelling sentence before committing; its source page remains 886.

```text
/Users/aamia/.t3/projects/batatis/.venv/bin/python -m pytest evals_dev -q
exit 0; 17 passed in 2.98s

/Users/aamia/.t3/projects/batatis/.venv/bin/python -m pytest evals_dev/test_author_cases.py -q
exit 0; 9 passed in 2.92s

/Users/aamia/.t3/projects/batatis/.venv/bin/python evals_dev/author_cases.py \
  --db /Users/aamia/.t3/projects/batatis/codedb/build/codedb.sqlite
exit 0; ok: true; mode: check; cases: 60; section_c_rows: 39; changed_cases: []

/Users/aamia/.t3/projects/batatis/.venv/bin/python evals_dev/author_cases.py \
  --db /Users/aamia/.t3/projects/batatis/codedb/build/codedb.sqlite --check
exit 0; ok: true; mode: check; cases: 60; section_c_rows: 39; changed_cases: []

/Users/aamia/.t3/projects/batatis/.venv/bin/python evals_dev/author_cases.py \
  --db /Users/aamia/.t3/projects/batatis/codedb/build/codedb.sqlite --write
exit 0; ok: true; mode: write; cases: 60; section_c_rows: 39; changed_cases: []

git diff --check
exit 0
```

The old `37f04bf` run had seven passing tests and one failure from the literal 25-case assertion.
The integration repair replaces that assertion with **60 cases and exact contiguous IDs / filenames
`dev-001`–`dev-060`**. The stale `dev-004` test comment now names 9.10.15.2.(3). No tests are deselected
for the current full-suite pass. Validation and tests use the current main CodeDB at the path above,
read-only; its SHA-256 remains the value in the source receipt.

Additional read-only assertions passed for contiguous `dev-001`–`dev-060` IDs, 60 unique descriptions,
35 new files with exactly six additional asks and two redirects, seed Part consistency, empty
departure/mandatory citations/Section C for undecided or redirected cases, no critical missing facts
on proceeding cases, exact benchmark-to-Section-C coverage, and exact Section C equality with
`codedb.lookup(..., db_path=...)` as well as the validator's independent SQLite queries.

The other integration repairs are complete:

1. **One authoring source:** the old 25 embedded specs were removed from `author_cases.py`.
   Committed JSON is the only source of narratives, semantic labels and authoring receipts. The script
   derives only `gold.section_c`, using existing Division B benchmark references from `gold.must_cite`;
   it never selects benchmarks from the seed, scope references or candidate citations. It does not
   replace authoring metadata or imply a new review. Default / `--check` runs are read-only; only
   explicit `--write` allows replacements, and only changed cases are written.
2. **Batch preflight:** the exact file/ID set, JSON parsing, benchmark lookups and the projected set's
   existing validator checks all finish before any source file is replaced. Six CLI failure tests
   plant a missing case, malformed JSON, unknown benchmark, invalid professional label, mismatched ID
   or unexpected case while an earlier file needs a refresh; every run exits 2 and leaves all input
   bytes unchanged. Replacements are staged first and use per-file atomic renames; this is not a
   crash-atomic transaction over the entire directory.
3. **Preservation proof:** CLI tests refresh stale rows while retaining custom applicant wording,
   later authoring receipts and every non-Section-C JSON value. Corrected `dev-004` / `dev-008`
   benchmarks and `dev-005` / `dev-011` ask/professional labels remain intact. Repeated writes are
   idempotent and leave unchanged files byte-for-byte intact. A separate check of the actual 60 files
   ran default, explicit check and explicit write modes with zero changes; all gold values and
   authoring receipts still equal `37f04bf`. Only `dev-027`'s description and known facts differ.
4. **Null Part clarified:** `SCHEMA.md` now distinguishes unresolved route (`ask`, false
   `out_of_scope`) from a separate regime (`redirect`, true `out_of_scope`). A null Part alone does
   not decide scope.

The initial dataset commit changed only `evals_dev/cases/` and this review. The integration repair
changes `author_cases.py`, `test_validate_cases.py`, new focused CLI tests, `SCHEMA.md`, this review
and `cases/dev-027.json`. Engine, web, CodeDB, validator implementation, secrets, protected judge
storage and archive branches were not modified. The parent owns combined verification beyond this
worker's `evals_dev` checks.
No push, merge, deployment, publication or UI feature was performed; visual product evidence does
not apply to this nonvisual fixture task.

## Methods used

- [T3 workflow](/Users/aamia/.codex/skills/t3-workflow/SKILL.md) and
  [route selection](/Users/aamia/.codex/skills/t3-workflow/references/routes.md): ownership, source-first
  work, bounded verification, review and honest evidence limits.
- [pstack interrogate](/Users/aamia/.agents/skill-libraries/pstack/skills/interrogate/SKILL.md), with its
  [rubric](/Users/aamia/.agents/skill-libraries/pstack/skills/interrogate/references/rubric.md),
  [lead judgment](/Users/aamia/.agents/skill-libraries/pstack/skills/interrogate/references/lead-judgment.md),
  [reviewer prompt](/Users/aamia/.agents/skill-libraries/pstack/skills/interrogate/references/reviewer-prompt.md)
  and [quality lens](/Users/aamia/.agents/skill-libraries/pstack/skills/interrogate/references/code-quality-review.md):
  challenge benchmark applicability, trace exceptions, reject unsupported labels, preserve disputes.
  Adapted to direct review because the user prohibited further delegation.
- [Batatis hackathon](../.cursor/skills/batatis-hackathon/SKILL.md),
  [variance workflow](../.cursor/skills/batatis-variance-workflow/SKILL.md) and
  [always-on domain rule](../.cursor/rules/batatis-hackathon.mdc): administrative completeness,
  acceptable/alternative fork, deterministic Section C and professional-evidence boundaries.
- [PDF skill](/Users/aamia/.codex/plugins/cache/openai-primary-runtime/pdf/26.1017.11052/skills/pdf/SKILL.md):
  targeted source-table extraction, rendering and visual inspection. No PDF was edited.
- Integration repair: [Matt Pocock TDD](/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/tdd/SKILL.md)
  and its [test guidance](/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/tdd/tests.md).
  Tested the user-authorized CLI boundary: read-only default, explicit deterministic refresh,
  preservation and batch rejection. Observed failing CLI tests before implementing the new modes,
  then exercised the real CodeDB and temporary fixture copies without mocks. Reused the T3 router,
  routes and Batatis domain/variance sources above; pstack evidence/lead-judgment guidance informed
  the final direct review. No additional delegation or new PDF inspection was performed for the
  tooling repair; the prior source-page receipt supports the relayed geometry correction.
