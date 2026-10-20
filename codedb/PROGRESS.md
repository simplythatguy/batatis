# W1b progress — complete

## Done
- Read preamble, contracts, brief, source documents and assigned workflow methods.
- Audited resumed build against codesearch page output; fixed systematic sentence/table/figure text pollution and strict ID parsing.
- Delivered tested CLI and importable lookup/search/children/validate APIs; validator gate checkpoint made available early.
- Preserved attributions and application notes, explicitly heuristic exception roots, objective/functional definitions, and explanatory intent comparisons.
- Rebuilt source-fingerprinted SQLite plus nine JSONL exports; final repeated rebuild is byte-identical across SQLite/stats/exports.
- Final test result: 47 passed in 0.61s. SQLite integrity ok; no orphan children or invalid provision page ranges.
- Stratified random 30-provision source audit: 0/30 mismatches, all divisions and Div B parts represented.
- README and REPORT document scope, commands, coverage, proof, limitations and methods actually used.

## Gate

`.venv/bin/python -m codedb validate <paths...> --json`

Exit 0 clean, 1 citation/file errors, 2 setup errors. Warnings identify unbound pairs/pages. NFC explicitly unsupported.

## Remaining / limits

No required W1b implementation remains. NFC was stretch-only and was not attempted. Two unmatched targets in the printed Part 4 attribution table are preserved as source discrepancies. Roots remain heuristic, table cells/formulas/diagrams are not reconstructed, and citation checks do not prove technical correctness. See REPORT.md and README.md.

## Ownership / throughput

All task writes stayed under codedb/. No commits, pushes, subagents or eval access. Sequential source audit → validator checkpoint → final rebuild/verification avoided shared writes outside the owned folder.

## Parent review backlog (2026-10-18)
- Validator false positives seen on research/facts: (1) `PDF p.N` belonging to a non-code document (STANDATA, Calgary SPV,
  "W16, PDF p.1") is bound to the nearest NBC provision → page_mismatch; bind pages to the document named in the same
  citation span. (2) NFC-AE citations hard-error as unsupported_document; downgrade to warning until NFC is built.
  (3) national_edition_as_law fires on explicitly labelled explanatory uses of the NBC 2020 intent supplement.
- From combustible-construction sheet (2026-10-18): (4) heuristic exception root for 3.1.5.5.(1) points the wrong way
  (text says root is 3.1.5.1.(1)); (5) validator treats every row of a markdown table whose header contains "Intent" as
  intent context, producing false errors; (6) precedents/index.json crosswalk mapping greenhouse-film variances
  (23-BCV-011 / 19-BCV-014) to 3.1.6.5 is unsupported (owner: research/precedents). (7) code tables (e.g. Table 3.1.6.3,
  3.2.2.58, 3.2.2.62) are not parsed; consider a table extractor.
- (8) Validator drops lettered table suffixes: "Table 9.10.14.4.-A", "Table 3.2.3.1.-B" are parsed as "Table 9.10.14.4."
  and reported nonexistent_table (false positive; verified in code text PDF pp.894–896, 204–207). Seen in
  research/facts/fire-separations-and-spatial-separation.md lines 135, 368.
- From video notes (2026-10-19): (9) when no division is written, the validator resolves bare ids like 3.2.2.10. against
  Div A and reports nonexistent_provision; infer Div B for Part 3–11 ids (Div A only has Parts 1–3 with distinct ids;
  report ambiguity only on real collisions). (10) superseded_edition fires inside an explicit "2019 → 2023" mapping
  table/row; allow edition-labelled historical mappings (e.g. a row containing both "2019" and a verified 2023 id).
  These two account for ~78 of 119 errors in research/youtube/notes.

## Status 2026-10-19 (validator fixes, parent)
- DONE (8): the citation regex now reads the letter after a table id, so `Table 9.23.3.5.-A` resolves to its own row
  (regression tests in `tests/test_validator.py`).
- DONE (5): each markdown table row is its own scope, so a row's header or earlier row cannot make its citations intent.
- DONE (intent source): a citation's intent status follows the latest document or intent mention before that citation,
  not later text on the same line. Intent citations therefore need the label before the citation, as in CONTRACTS.md
  (`NBC 2020 Intent Statements, 9.9.10.1.(1) [PDF p.N]`).
- PARTLY DONE (1): sheets now label non-code pages as "W16, source p.N" so they are not bound to a code provision. The
  validator still does not bind a page to the document named in its own citation span; this stays open.
- Sheet fixes made with these changes: structural (intent citations moved to a labelled paragraph), housing (intent cells
  name their provision), envelope (sentence id before its page), professional (non-code pages relabelled).
- DONE (10, partly): citations labelled as another edition or jurisdiction (`2019` before or just after the id, `(historical)`,
  `BC` before the id, or `the video's numbers` on the line) are reported as `historical_number` WARNINGS, not nonexistent
  errors. They still need a verified 2023 equivalent in any mapping table.
- DONE (2, partly): an NFC(AE) citation whose database is not built is checked for article presence in the NFC text
  (`nfc_text_only` warning, page bound for the page check). Sentence wording is still not checked. Building NFC into
  codedb is the real fix. Firefighting and egress sheets now validate with 0 errors.
- OPEN (12): a citation with no division word in its own line segment takes the division from the paragraph scope's
  last division mention, not from its own sentence. Reported by the occupancy child (paragraphs mixing divisions).
  Workaround in use: `[Div X, Sentence N, PDF p.M]`. Reproduce before changing the rule.
- OPEN (11): `code_tables` records the first textual mention of a table id, not its caption. `Table 9.36.3.10.` maps to
  PDF p.91 (a reference list) though the caption is on p.1085 with "(Continued)" on p.1086. A validator error on a correct page
  citation (`research/youtube/notes/xRfh_z8UZNg.md` line 77) is the result. Fix the table registry to use caption pages.
- Result: structural 0 errors; housing 0; envelope 0; professional 0; fire separations 0; egress 1 (NFC-AE
  unsupported_document, documented). Batch A notes: 1 error (item 11). Tests: 52 passing.
