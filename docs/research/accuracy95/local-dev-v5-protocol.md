# Isolated Codex Luna local diagnostic

This run measures the complete corrected Calgary/Edmonton development slice. The 95% objective is not established. Each inference request uses a **fresh T3 task**, including each judge request: no prior case or prior stage conversation is carried into it. T3 still injects generic agent/workspace instructions, so this remains a Codex diagnostic rather than hosted-product inference.

## Frozen specification

- Run: `.dpe-cache/codex/local-dev-v5/`; manifest schema `codex-luna-experiment-v4`.
- Manifest file SHA-256: `91967cb361d352e224006820984ed387103bd42d27642bd343cdadfd15d0bc44`.
- All 25 local development cases, 11 connected source components: Calgary 8 cases/6 groups/92 checks; Edmonton 17 cases/5 groups/176 checks.
- Total 268 checks: 118 facts, 121 review points, 13 boundaries, 16 articles. No case is removed for failure or missing judgment.
- Existing 653-case/592-group corpus split preserved; no holdout errors inspected.
- Model for candidate and independent judging: `codex:gpt-6-luna`, max effort, priority tier. Parent verifies each returned T3 selection and saves its task identity under `dispatches/<request-sha>.json`. Usage/cost remain unknown.
- Inference input: actual engine system/user/schema; no curator facts, review-focus rows or evaluation files reach candidate tasks. The task answers one request and stops; only the parent resumes the pipeline. Exact duplicate requests may reuse their validated response, as with a normal request cache.
- Intake, review validation, planning, completeness and CodeDB lookup use the actual engine. Identification is the explicitly bounded BM25 top-60/Luna full-text path, with no Jev stage. Hosted transport/profile and the hosted 4 MB upload limit are not tested.
- 593 source files, the CodeDB bytes, full index, selected inputs/references and grouped split are frozen. All local default attachment bytes were restored and hash/size verified.

## Fairness and reference version

The historic local score used 259 checks. Source-packet v2 makes nine additional fact checks eligible (+1 L05-003, +1 L04-001, +4 L04-002, +3 L04-005), under the unchanged reference-construction algorithm. It also records the L14-003 R4/R6 expectation corrections. This is a different benchmark version, not a controlled model-only gain. The original 259-check support audit remains unchanged.

The judged transcript now has the neutral heading `DOCUMENT REVIEW`; the guarantee that every readable page was read was removed because it was not shown to applicants and could conflict with unread-page flags. The live/fake regression cases failed before that fix, then passed. Independent R4 review found no remaining issue in this scoped change.

## Completion and claims

Parent-only `resume` advances cases; children write only their assigned response file. Separate fresh tasks grade only each supplied report/reference request. Invalid JSON/verdicts, failed runs, pending work and unread inputs stay visible and block the local target gate. Candidate result seals and judge receipts bind exact request/response bytes and task IDs. Generic judge caches cannot bypass that boundary.

The local coverage flag requires the complete `local-dev` selection, both cities independently at least 95%, no failed/unread case, and all guardrails passing. `target_met` and `production_accuracy_established` remain **false**. Whole-case success and source-group counts must accompany any final score. This does not validate safety, code compliance, equivalence, professional evidence or population accuracy.

All earlier runs remain separate. In particular, V4's two city-batch tasks were stopped before scoring, and **no V4 response or result was copied into V5**. V2/V3 were pre-inference setup attempts. The earlier smoke run's unfinished planned cases remain in its recorded denominator.

The newly collected ECSD PDF is quarantined outside this run/tuning/retrieval. Later Calgary and procurement searches yielded no further qualifying originals. The ordinary Chromium check of Calgary attachment 93287 also returned HTTP 403 HTML (`Just a moment...`) on 2026-10-25, with no PDF saved.

Whole-app acceptance, a T3 walkthrough and Lint Apple remain unverified because existing sessions own ports 3000/8000 and T3 snapshots twice timed out. Inspected screenshots and Chromium checks demonstrate the actual React review component with labelled unit data only.
