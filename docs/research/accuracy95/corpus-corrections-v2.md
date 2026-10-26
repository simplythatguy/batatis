# Local DEVELOPMENT corpus corrections v2

**Date:** 2026-10-25  
**Scope:** L04-001, L04-002, L04-005, L05-003, L14-003 only  
**Version note:** This corrects packet inputs and reference wording. It contains no model outputs, accuracy measurement, or 95% claim.

## Historical audit remains frozen

The existing [input-reference-audit.json](./input-reference-audit.json) is unchanged by v2. The audit Markdown later received a provenance clarification that its judgments are model-generated, not human review; the JSON companion records that editorial change separately. The JSON still contains 259 original checks across 25 Calgary/Edmonton development cases and 11 source groups: 109 F, 121 R, 13 B, and 16 A checks. All rows remain marked in the original denominator; none were deleted or reweighted. The JSON SHA-256 is e204776ddbf287775021f61a67a30d1ad40a212ea20cb99ee52c4801f94c129e.

V2 records corrected inputs and semantic reference edits as a new version. No benchmark score is computed, and v2 must not be reported as the same score or model gain against the historical reference set.

## Packet corrections

| Case | Correction | Default inputs | Excluded references |
| --- | --- | ---: | ---: |
| L04-001 | SPV-001 Revision 5 is now a default published standing reference; Revision 4 remains included as prior-version context. | 3 → 4 | 1 → 0 |
| L04-002 | SPV-002 is now included because the prompt says it is attached; it remains a historical standing variance, not a project permit outcome. | 2 → 3 | 1 → 0 |
| L04-005 | SPV-006 is now included because the prompt says to use it; it remains a historical standing variance, not a project permit outcome. | 4 → 5 | 1 → 0 |
| L05-003 | The authenticated Point Access Block Technical Report, Revision 4, is now a named default historical reference; the prompt asks for explicit attribution and no Batatis professional conclusion. | 3 → 4 | 1 → 0 |
| L14-003 | The proponent profile remains excluded; the packet stays drawing-only, the hidden-path and hidden-acceptance checks are replaced, and all six review checks remain. | 3 → 3 | 1 → 1 |

The three Calgary SPVs remain published standing references. Their publication/CSTIC acceptance does not establish an approval or permit decision for any individual project; outcome_leakage remains explicitly true. SPV-001 Revision 4 stays as version context.

For L05-003, PDFKit inspection of the original City report confirmed the prompt’s requested source claim before the report was promoted: its Executive Summary (PDF p.6) and section 5.2 (PDF p.26) describe Design Study 2’s vestibule-protected, four-storey/16-unit exemplar as demonstrating equivalent resilience relative to a code-compliant two-stair design. The prompt explicitly attributes this to the report and separates it from any permit decision or Batatis professional conclusion.

For L14-003, the three drawing images remain the only default inputs and the profile remains excluded under _evaluation. The historic R4 expectation to independently confirm proponent-reported acceptance is replaced by a request for original permit and authority-issued records if relevant. Historic R6’s evaluator storage-path check is replaced by a check of visible drawing evidence boundaries. All six review checks remain; the old R4/R6 rows remain untouched in the frozen historical audit.

## Source bytes and split boundary

All newly promoted PDFs and the retained SPV-001 Revision 4 were checked against their recorded SHA-256 and byte counts before copying. The selected attachment verifier rechecked the copied originals. The four newly included hashes had no default-input owners in the pre-correction inventory; after promotion each is owned only by its intended development case. The source-group helper therefore produced identical connected-component hashes before and after, and no dev/holdout assignment changed.

| Affected component | Source-group hash before and after | Members |
| --- | --- | --- |
| L04-001 | 4414740917f24309 → 4414740917f24309 | L04-001, L04-002, L04-005 |
| L04-002 | 4414740917f24309 → 4414740917f24309 | L04-001, L04-002, L04-005 |
| L04-005 | 4414740917f24309 → 4414740917f24309 | L04-001, L04-002, L04-005 |
| L05-003 | e13a13e04e52d10e → e13a13e04e52d10e | L05-001, L05-002, L05-003, L05-004, L05-005, L05-006, L05-007, L05-008, L05-009, L05-010, L05-011, L05-012, L05-013 |
| L14-003 | 19d4395eae6a5d6a → 19d4395eae6a5d6a | L14-003 |

Across the full corpus inventory, default attachment records changed from 815 to 819, and unique default hashes from 714 to 718. This is four additional historical reference inputs; the 592 source groups and aggregate split counts (334 development, 319 holdout) are unchanged. The source catalogue already contained every promoted hash, so source_catalogue.jsonl did not need regeneration.

## Verification

- Full metadata verification: python3 'Data Prompts/_tools/verify_corpus.py' — 653 prompts, 592 source groups, 0 errors.
- Selected byte verification: python3 'Data Prompts/_tools/verify_corpus.py' --case L04-001 --case L04-002 --case L04-005 --case L05-003 --case L14-003 --attachments — 5 prompts, 21 attachment/derived-text files checked, 0 errors.
- The generated prompt attachment lists match each source metadata default-input list; no _evaluation path is listed as default.
- A scoped diff check confirmed that non-target curation override entries and all five cases’ source fact fields are unchanged; index and source-catalogue content is unchanged.
- Index JSON/CSV files were regenerated through the existing write_indexes helper; group tags were unchanged. The full assembler and generic regroup script were not run.

The per-case before/after prompt, attachment, reference, and manifest hashes; source byte hashes and sizes; historical audit fingerprints; component members; and verifier results are in [corpus-corrections-v2.json](./corpus-corrections-v2.json).

## Methods used

- T3 workflow routing: /Users/aamia/.codex/skills/t3-workflow/SKILL.md and references/routes.md.
- Matt Pocock diagnosing-bugs: /Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/diagnosing-bugs/SKILL.md.
- pstack poteto-mode bug-fix: /Users/aamia/.agents/skill-libraries/pstack/skills/poteto-mode/playbooks/bug-fix.md, adapted to this data-correction task and the no-delegation boundary.
- Batatis domain guidance: .cursor/skills/batatis-hackathon/SKILL.md.
- PDF source reading: /Users/aamia/.codex/plugins/cache/openai-primary-runtime/pdf/26.1020.11618/skills/pdf/SKILL.md; original PDFs were read locally with PDFKit.

No delegation, network download, model API, engine/evaluation-code edit, or model run was used for this correction.
