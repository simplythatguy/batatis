# Corrected local development run

**Superseded before scoring.** The city-wide tasks were stopped to prevent unrelated case context carrying between requests. R3 also found an evaluator-only reading guarantee; it was removed and R4 verified the fix. V4's responses/results remain preserved, but none are imported into the replacement `local-dev-v5` run. No V4 accuracy claim is made. The original planned scope below is retained as an audit record.

This is a Codex Luna diagnostic of the complete Calgary/Edmonton development slice. It cannot establish hosted-product accuracy: T3 injects agent instructions and the worker retains prior stages; the hosted provider transport is unchanged. `target_met` and `production_accuracy_established` remain false regardless of its score.

## Frozen scope

- Run directory: `.dpe-cache/codex/local-dev-v4/`; manifest schema `codex-luna-experiment-v4`.
- Manifest file SHA-256: `d5e755b7ddd7b36ff228c93b66f58397a6de52f846679855c82d69d7510b3881`.
- Selection: the `local-dev` preset, all 25 Calgary/Edmonton cases from the existing grouped development split, across 11 connected source components. No holdout errors were used.
- Calgary: 8 cases, 6 groups, 92 checks. Edmonton: 17 cases, 5 groups, 176 checks.
- Expected checks: 268 = 118 F + 121 R + 13 B + 16 A. Missing results and judgments stay in this denominator.
- 593 source files are frozen, including the engine, CodeDB runtime, evaluation code and web consumer. The full index, selected inputs/references, SQLite database and grouped split are also bound.
- All 63 default attachment instances were restored and verified by size/SHA-256; they represent 25 unique original byte hashes. Restoration is not newly collected data.
- Candidate and independent judge: `codex:gpt-6-luna`, max effort, priority tier, through T3 tasks. Usage and cost are unknown. No OpenAI API request is used by this adapter.
- Article identification: BM25 top 60, no reranker, Luna full-text verification of 60 candidates. This differs from the hosted Luna/Jev profile and is not a paired test of that profile.

## Reference changes are a new benchmark version

The historical 25-case baseline was 181/259 checks. The preserved input/reference audit still contains those original 259 checks. Correcting the five source packets makes nine additional facts eligible under the unchanged reference-construction algorithm: +1 in L05-003, +1 in L04-001, +4 in L04-002 and +3 in L04-005. The R/B/A counts are unchanged, although the separate v2 ledger records the revised L14-003 R4/R6 expectations. The historic score and this corrected run are not a controlled before/after model comparison.

## Dispatch and scoring

Two disjoint T3 workers execute the eight Calgary and seventeen Edmonton cases. They use `resume --case <id>` so one worker cannot overwrite another's case result. Their returned provider/model/options and task IDs are saved in `dispatch-calgary.json` and `dispatch-edmonton.json`. Responses are bound to exact staged prompts; result files are sealed to the manifest, inputs and model-call receipts.

Candidate workers receive no answer keys, curator facts, review-focus rows or scoring requests. A separate fresh task grades finished reports with the existing strict excerpt validator. Generic judge-cache files cannot bypass the Codex response/task boundary. Score rows retain the judge call receipts. No missing/invalid judgment is credited.

`check_coverage_target_met` requires the complete predefined local selection, both cities at or above 95% on their own exact denominators, no failed case or unread input, and every guardrail passing. Custom/smoke selections cannot satisfy it. This flag measures local source-check coverage only, not the share of viable applications, expert correctness, or population accuracy.

## Preserved setup attempts and limits

The earlier `local-dev-v2` and `local-dev-v3` directories were staged before review fixes changed frozen source. No candidate responses were generated in them. They remain as pre-inference setup artifacts and are not resumed. Earlier smoke results, including their unfinished planned cases, remain recorded separately in `diagnostic-results.json`.

The new ECSD report remains quarantined, outside tuning, retrieval and this run. It is one new source group for two Edmonton preliminary-design projects, not two new independent evaluation cases. Later Calgary and procurement searches found no further eligible local originals.

Full-app browser acceptance and a T3 walkthrough remain unverified: ports 3000 and 8000 are owned by existing sessions; T3 snapshots twice timed out. The saved UI screenshots and Chromium checks demonstrate the actual React component using labelled unit data only. Model-graded reference support is not expert validation.
