# W1b handoff

Implemented and verified locally. All task writes are under `codedb/`; no commits, pushes, nested delegation, external publication or held-out eval access.

## Deliverables

- `codedb/validator.py`: citation scanner and JSON-serializable gate reports.
- `codedb/api.py`, `codedb/__init__.py`: importable `lookup`, `search`, `children`, `validate`, `validate_text`, and `AmbiguousProvisionError`.
- `codedb/__main__.py`: `python -m codedb build|lookup|search|children|validate`.
- `codedb/tests/`: 47 passing source-receipt, query, parser and gate tests.
- `codedb/audit.py`: repeatable, stratified random 30-provision source comparison through `tools/codesearch.py page`.
- `codedb/README.md`: schema, usage, coverage, source controls and known limitations.
- Rebuilt `codedb/build/codedb.sqlite`, `stats.json`, nine domain JSONL exports; source PDF/text SHA-256 fingerprints and page counts included in build metadata.

## Gate ready for other agents

```sh
.venv/bin/python -m codedb validate <path...> --json
```

Exit 0 = no detected errors; exit 1 = citation/file errors; exit 2 = command/setup error. Warnings explicitly identify unbound pairs/pages. The scanner checks recognized citations and source links, not interpretation, relevance or technical correctness. Keep related id, pair and page tokens together. Ambiguous division must be explicit. NFC references fail as unsupported because NFC was not built.

## Parsing fixes from the resume audit

- Source headings: no missing article-like headings in the initial body inventory; provision count remains 13,743 after fixes.
- Removed table/figure contents and their footnotes from body sentence text while preserving table locations and provision nodes.
- Identifier parsing now requires a complete valid hierarchy; trailing junk and zero/extra numeric levels fail.
- Root inference prioritizes same-article sentence references over earlier exception-article references; status remains explicitly heuristic and never substitutes for a direct table attribution.
- Editorial square brackets in quoted application notes remain application text rather than false parser errors.
- Sorted note-reference sets. A repeated fresh-process rebuild originally exposed unstable insertion/export order; the fix made SQLite, stats and all nine exports byte-identical on the final repeated rebuild.
- Read-only query connections close explicitly. New build metadata lets the gate check page bounds with SQLite alone, without source page files at runtime.

## Raw verification receipts

Executed from `~/.t3/projects/batatis`:

```text
.venv/bin/python -m pytest codedb/tests -q
...............................................                          [100%]
47 passed in 0.61s

.venv/bin/python -m codedb.audit
30 source checks; 0 mismatches (0.0%)

Repeated rebuild SHA-256 comparison:
rebuild_consistency True []

SQLite integrity:
{"sqlite_integrity":"ok","orphan_children":0,"invalid_page_ranges":0,
 "provisions":13743,"articles":2177,"sentences":5493,"intent_blocks":10122}

git diff --check -- codedb
(no errors)
```

Real CLI exercises:

```text
validate codedb/build/gate/valid.md --json
exit 0; 1 file; 4 citation tokens; 0 errors

validate codedb/build/gate/invalid.md --json
exit 1; 1 file; 4 citation tokens
errors: superseded_edition, nonexistent_provision,
        attribution_not_in_table, page_mismatch

lookup 9.9.10.1.(1)       → correct id and full structured result
search egress bedrooms --limit 3 → 3 ranked rows
children 9.9.10.1.       → 6 sentence rows
```

Source receipts verified using `tools/codesearch.py page`:

- Bedroom egress: body PDF p.873; direct `[F10-OS3.7]` table attribution PDF p.1126.
- Part 3 example: body PDF p.179; sentence (2) table attribution PDF p.326. Sentence (1) has no direct attribution; its suggested same-article root is sentence (2).
- Div C documentation: article and six sentences at PDF p.739.
- Functional statement F10: definition PDF p.80; objective OS3.7: PDF p.69.
- NBC 2020 explanatory intent for the bedroom-egress example: PDF p.1333.

Detailed ignored evidence: `build/spot-check.json`, `build/audit/pages/*.txt`, `build/rebuild-consistency.json`, `build/integrity.json`, `build/gate/*-report.json`, `build/rebuild-7.log`. The audit compares ordered raw lines/title and claimed start/end pages with actual `codesearch.py page` output; headers/footers between page continuations do not count as text mismatches. It is an extraction sample, not exhaustive proofreading.

## Coverage

- 13,743 provision nodes, 2,177 articles, 5,493 sentences, 774 notes, 148 objective/functional definitions.
- 9,810 attribution source rows; 11,501 expanded bracket rows; no undefined attribution codes or parser anomalies.
- Div B sentences with direct/clause-level attribution: 3,817/5,291 = 72.1% in attributed parts; 3,817/5,308 = 71.9% across all Div B sentences.
- 5,026 distinct national intent provisions; 4,805 exist in AE (95.6%). Pair comparisons: 3,414 match, 64 differ, 29 missing AE pairs, 14 missing intent pairs, 1,284 neither side has pairs, 221 provisions absent in AE. Pair-bearing match rate: 97.0% of 3,521 comparable entries.
- Per-division/part article/sentence/node counts are in README and generated stats.

## Limits and unresolved source issues

- Printed table PDF p.514 refers to clauses (c)/(d) under its serviceability sentence (5), while the body at p.428 has only (a)/(b). Both unmatched table targets are preserved and reported. The gate rejects nonexistent body clauses.
- Full table cells, formulas, diagrams and semantic application-note conditions are not reconstructed or technically assessed. PDF extraction/word repair can require manual confirmation. Exception roots remain heuristic.
- Scanner context is local text, not a semantic Markdown/JSON/YAML document model; unbound tokens warn, and complex interleaving should be rewritten as explicit complete citations. National intent remains explanatory and is compared by provision presence/pair equality only.
- NFC stretch work was not attempted; the registered NFC source is explicitly unsupported by this build.
- No UI was built, so there is no meaningful screenshot/video surface. Actual CLI/API outputs, tests and saved source comparisons are the evidence.
- No independent child review was run because the preamble forbids further delegation. A local spec/correctness review found and fixed the issues listed above.
- Workflow maintenance check reported intentional/unresolved drift in `~/.agents/pstack-models.md`; it was preserved. No workflow configuration was changed.

## Methods used

Files actually read and applied:

- T3 workflow router: `~/.codex/skills/t3-workflow/SKILL.md` and `~/.codex/skills/t3-workflow/references/routes.md`.
- pstack feature slices: `~/.agents/skill-libraries/pstack/skills/poteto-mode/playbooks/feature.md` (adapted to no-delegation/no-commit contract).
- pstack domain structures: `~/.agents/skill-libraries/pstack/skills/principle-model-the-domain/SKILL.md`.
- pstack proof against actual artifacts: `~/.agents/skill-libraries/pstack/skills/principle-prove-it-works/SKILL.md`.
- Matt Pocock module interfaces: `~/.agents/skill-libraries/mattpocock/skills/engineering/codebase-design/SKILL.md`.
- Matt Pocock targeted regression diagnosis: `~/.agents/skill-libraries/mattpocock/skills/engineering/diagnosing-bugs/SKILL.md`.
- Matt Pocock spec/correctness review: `~/.agents/skill-libraries/mattpocock/skills/engineering/code-review/SKILL.md` (local review; no nested agents).
- Nonvisual evidence rules: `~/.codex/skills/t3-workflow/references/visual-evidence.md`.
- Drift handling: `~/.agents/t3-workflow/UPDATE-SAFETY.md`.
