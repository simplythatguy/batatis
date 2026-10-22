# Standing-package checklists: what a reviewer must check (WP-32)

Status: **not reviewed by a person.** All three checklists carry `reviewed: false`. A model enumerated the
conditions from the source PDFs and the test suite checks every quote word for word against the reference
text. That proves each quote is real and on the cited page. It does not prove that the rows are complete,
correctly split, or fairly put into plain language. Only a person who has read each checklist in full
against its PDF may set `reviewed: true`, with `reviewed_by` and `reviewed_on`.

| Checklist | File | Source PDF (git-excluded) | Rows | Source notes |
|---|---|---|---|---|
| `calgary-spv-001` SPV-001 Zero Lot Line, Rev. 5, 2026-03-05 | `engine/data/jurisdictions/checklists/calgary-spv-001.json` | `reference/precedents/calgary/calgary-spv-001-zero-lot-line-2026-03.pdf` (6 pages) | 53 | 3 |
| `calgary-spv-006` SPV-006 Firewall in a Rowhouse with Secondary Suites, 2025-06-19 | `engine/data/jurisdictions/checklists/calgary-spv-006.json` | `reference/precedents/calgary/calgary-spv-006-firewall-rowhouse-secondary-suites.pdf` (5 pages) | 32 | 3 |
| `edmonton-b23-01` Policy B23-01, 2024-07-30 | `engine/data/jurisdictions/checklists/edmonton-b23-01.json` | `reference/precedents/edmonton/edmonton-policy-b23-01-row-house-fire-separation-more-than-two-secondary-suites.pdf` (2 pages) | 13 | 4 |

Edmonton Policy B14-01 has no checklist. It cites the Alberta Building Code 2014 and is shown only as
historical (`status: historical` in `packs/edmonton.json`, and in the `historical` list of both checklist
routes). The loader refuses a checklist on a historical package.

## For every checklist

1. **Completeness.** Read the PDF from the first page to the last. Every requirement the applicant or the
   project must meet has its own row. Background, reasons, the objective and function statements and
   the "based on" research list are not conditions, and they have no rows (except where "based on" names
   a permit-document requirement).
2. **Splitting.** A row holds one thing to confirm. Where the source joins two requirements with "and",
   or a requirement and a finish detail, they are split. Where the source offers alternatives ("or"),
   each option is a row with the same `one_of` key; the applicant follows one option and marks the others
   "does not apply". Check that no row still hides two requirements, and that no split broke one
   requirement in half.
3. **Plain language.** Each `plain` says what the source says, no more and no less. It must not add a
   number, drop a limit or soften a "shall". It must never say complies, safe, approved or adequate (a
   test enforces the words, not the meaning).
4. **`may_not_apply` and `when`.** `false` means the condition always applies when the package is used,
   and the answer route refuses "does not apply" for it. Check each `false` really is unconditional, and
   each `when` states the trigger the source gives.
5. **Pages, labels and figures.** `source.page` is the PDF page (one-based); `source.label` is the item
   label as printed. `diagram` points to a figure only where the figure shows that condition.
6. **Source notes.** Conflicts and figure-only notes are things the City must answer. Check they are
   real and that none is missing.

## SPV-001 (Calgary), specific checks

- **Both houses.** The package applies "to the exposing building faces on both side walls of both houses
  adjacent to each other" (p.2). Rows with `subject: both_houses` must hold for the neighbouring house
  too. Check that the applicant copy makes this clear enough, since one applicant usually controls one
  lot.
- **Registered agreement.** `l)` on p.4 and the third Authority bullet on p.5 both describe the
  Maintenance Access Right of Way (MARW). Rows `l-marw-on-title`, `l-i` to `l-iv`, `marw-both-titles`,
  `marw-projections` and `marw-0-9-m-apart` cover them. Check that "registered on the title of th parcel
  and the adjacent parcel" (sic, p.5) is read as both titles.
- **Footing conflict.** `l) iii.` (p.4) and the p.6 figure say 0.3 m footing projection into the
  easement; the p.5 Authority bullet says the agreement can allow 0.6 m across the property line. The
  checklist shows both and tells the applicant to ask the City. A reviewer cannot resolve this; the City
  can.
- **Figure-only note.** The p.6 cross-section says unprotected openings serving the same room are at
  least 2.0 m from other unprotected openings. That is not in the written items. The checklist carries it
  as a source note, not a row. Decide whether it should be a row.
- **f) and g).** Each is one long paragraph; the checklist splits it into five or six rows (no openings on
  the 3rd storey; zero side under 1.2 m; zero side 1.2 m or more; easement side at 1.5 m (7%); easement
  side beyond 1.5 m; 3.5% per opening; 3rd-storey area left out). Check that the measurement base (to the
  underside of the 2nd-floor ceiling for three storeys, the uppermost ceiling for one or two) is right in
  each row.
- **j) i. and k) i.** "Must not cover more than 2% ... or Must not extend more than 0.6 meters". The
  checklist reads this as either limit being enough. Check that reading.
- **j) ii. and k) ii.** The source permits combustible cladding at 2.4 m (zero side) or 0.9 m beyond the
  easement line (easement side), on the 1st and 2nd storey. The rows turn the permission into "used only
  where ...". Check that this reading is fair.
- **h).** The row covers the zero-side outlet boxes; the source's statement that 1.5 m-side boxes need no
  protection is a relief, kept in the plain text, not a row.
- **Scope rows** "same layout on the block" and "up to three storeys" come from the Reason section (p.1),
  not the Accepted method. Check that they are fair scope conditions.

## SPV-006 (Calgary), specific checks

- **Items 1 and 2.** Each is printed as a), b), c) where b) and c) are alternatives (45 min rating, or
  none if sprinklered). The checklist has a) as an always-row for suites (item 2) and a conditional row for
  exits (item 1, "where an exit is located in a house with a secondary suite"), and b)/c) as a `one_of`.
  Check this reading.
- **Item 3.** a) Article 9.10.3.1. or b) the deemed construction (i to iv), then c) loadbearing elements.
  b) is split into its four parts plus footnote (1) (CAN/ULC-S702.1, 1.22 kg/m2) and footnote (2) (edge
  support). Check that the footnotes are operative conditions and not only explanations. Row 3c is marked
  conditional on a rating being required; check that.
- **Item 4.** Read as: where a unit's egress door opens onto a shared egress facility and the unit has one
  exit, no second means of egress is needed if (sprinklered) or (direct access to a balcony) or (direct
  access to an openable window to 9.9.9.1.(2)(a) and (b)). Three options, one `one_of`. Figure 2 words this
  differently ("2 means of egress when only shared egress is provided or building isn't sprinklered"); the
  difference is a source note.
- **Item 5 a).** Split into "noncombustible, melting point at least 760 C" and "openings serve only one
  fire compartment". The degree sign is outside the verified quote (PDF text layer). Check the cross-
  reference to Clause 9.33.1.1.(3) in the plain text.
- **Item 5 b).** Split into two drawing contents rows. Check that it is a permit-document requirement for
  every SPV-006 project (marked always-applies).
- **Permit rows.** "Reference to Variance SPV-006 and compliance with the construction requirements is
  included in the permit documents" is its own row (`permit-shows-construction`), separate from naming the
  SPV.

## B23-01 (Edmonton), specific checks

- **Scope line.** The policy opens "For a row house being constructed per NBC2023(AE):B:9.10.15.", while
  the body is about the firewall in 9.10.11.2.(2). Kept as a source note; check whether it should be a
  scope row instead.
- **Party wall.** Split into "party wall on a property line, separating each pair of adjacent houses with a
  suite from the rest of the building" and "fire separation with at least 1 h rating".
- **Letter of Construction Intention.** Each bullet the signer affirms is a row (owner or agent; read the
  policy; built to the policy instead of an alternative solution; enough detail for Div C 2.2.5.2.;
  notify the City of changes). The fourth bullet holds two statements and is split. Check the wording,
  and that "print, read, sign and submit" is fairly one row.
- **Refusal and offence.** "In exceptional circumstances" refusal, the offence sentence and "content
  subject to periodic update" are source notes, not rows.

## What the tests check, and what they cannot

`engine/tests/test_checklists.py`:

- every file validates against the schema (unknown keys fail), and links both ways to its package;
- a historical package can never name a checklist; B14-01 has none;
- every source item label the reviewer of this PR listed is cited by at least one row (the list is in the
  test as `EXPECTED_LABELS`; a reviewer who finds a missing item adds its label there and a row here);
- no row repeats another row's quote; no row says "see source", "etc." or "all conditions";
- no plain-language copy says complies, safe, approved or adequate;
- every quote and lead-in is on its cited page of `reference/text/<stem>.jsonl` (skips when the
  git-excluded reference folder is absent), and the local PDF hash equals the recorded hash;
- every checklist is still `reviewed: false` and listed in this file.

They cannot check meaning. A wrong `plain`, a wrong split or a missed condition that the reviewer of this
PR did not list in `EXPECTED_LABELS` passes the tests. That is what this review is for.

When the review is done: set `reviewed: true`, `reviewed_by` (name and role, e.g. "Safety codes officer,
building") and `reviewed_on`, and update `test_every_checklist_waits_for_a_human_reviewer` to accept it.
