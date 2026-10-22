# Submission package checklist

*Internal checklist for Submission 1 of the Building Codes Challenge (Thursday Oct 29, 2026). It is not for judges: its file paths can contain internal names that the judge-facing documents avoid. Status is as of Oct 22, 2026, on `dev` at commit 43e7c09 (CI run 39747003798 passed) and the live app at <https://batatis-vert.vercel.app> as last checked on Oct 21. Each line names a file, a pull request (PR) or a number that exists now. A line marked **GAP** has none. Status words follow `docs/implementation-plan.md` §3: **built**, **backend only** (the API is merged and the screen is in progress), **in progress** and **roadmap**.*

The plans, pitch text, Q&A and demo script in this list are in PR #59. They are on `dev` only after it merges.

## Package rules this repo cannot confirm

The program's onboarding guide says: "Exact submission deadlines, templates and instructions to be posted in Discord." This checklist assumes Thursday Oct 29, 2026, "Submission 1: your semi-final package" (about 10 teams go on to the Nov 10 semi-finals).

**GAP:** confirm in Discord the exact submission time, the list of files, and the demo video's format and length limit.

## Deliverables

| Deliverable | Status | Evidence now | GAP |
|---|---|---|---|
| Demo video | Not recorded | `docs/demo/script.md`: shot list, narration sized to the clock, EXAMPLE DATA overlay, and the preconditions to record | **GAP:** record it. It needs the screens marked "pending UI" in the script, a live-mode decision, and a seeded officer account for the recording |
| Working link | Live | <https://batatis-vert.vercel.app> answered HTTP 200 on Oct 21. `GET /api/jurisdictions` returned the three packs and 13 coverage rows. `GET /api/code/search` returned 9.10.15.4.(1) among its top three. The OpenAPI document lists 64 paths (`docs/research/2026-10-21-source-checks.md` §6) | **GAP:** the site does not show which commit it serves, so confirm it is the final one. The Vercel Hobby deployment allowance ran out on Oct 20 (`docs/deploy.md`), so a late redeploy can fail. **GAP:** decide whether live model access is on. `docs/deploy.md` says to keep it off until the US$20 total cap (PR #41, still open) is integrated. Without live access code identification shows its labelled keyword fallback and the relevance rings stay unscored. **GAP:** decide how judges sign in as an officer. The access code is a secret (`BATATIS_REVIEWER_CODES`), and cases are deleted after 7 days |
| Repo | Private: <https://github.com/simplythatguy/batatis> | `main` is 7 commits behind `dev`. The last release was PR #50 | **GAP:** confirm that judges can open the repo. Release `dev` to `main` after the last merge. Decide which branch the package names |
| Business plan | Rewritten | `docs/business-plan.md`, with sources in `docs/research/2026-10-21-source-checks.md` | No team section. See "Decisions for you" |
| Implementation plan | Rewritten | `docs/implementation-plan.md`. The user-testing appendix is `docs/user-testing/` (no real session has run) | No human session. No pilot partner |
| Pilot plan | Rewritten | `docs/pilot-adoption-plan.md` | No partner has agreed to anything |
| Pitch | Text current. PDF stale | `docs/pitch-slides.md` (12 slides), `docs/pitch-outline.md`, `docs/pitch-narration.md` (388 spoken words, 2:51 at 140 wpm) | **GAP:** `docs/pitch-deck/batatis-pitch-deck.pdf` is stale, so do not submit it. `index.html` has current text and no screenshots. Steps to export a new PDF are in `docs/pitch-deck/SCREENSHOTS.md` |
| Judge Q&A | Rewritten | `docs/judge-qa.md` (23 questions) | |

## Rubric

The verbatim criteria are in `docs/judging-rubric.md`. The weights sum to 100.

| # | Criterion | Weight | Status in one line |
|---|---|---:|---|
| 1 | Intake | 20% | Deck built. Reader, planner and fork flag are backend only. Rules scored in sample |
| 2 | Code Identification | 20% | Library and Section C built. The pipeline is backend only and its final benchmark is unfinished |
| 3 | Recommendations | 10% | Engineer callout and Section D cards built. Checklists and coded rules are roadmap |
| 4 | Review | 10% | Queue, claim, sheet, accept and return built. Package review is backend only. No timing data |
| 5 | General Applicability | 5% | Role-aware flow built. Untested with a person |
| 6 | Implementation Plan | 10% | Rewritten. No human session, no partner |
| 7 | Business Plan | 10% | Rewritten with sourced numbers. No buyer has seen a price |
| 8 | Usability and Portability | 10% | Calm interface, Council form export and packs built. No usability test |
| 9 | The X Factor | 5% | Regulator-data insight documented. Team text missing |

### 1. Intake (20%)

**Evidence now:**

- Built: Describe, then one question per card in form order, with a "Why we ask" on each card and "Not sure" as an open question (`web/src/calm/Start.tsx`, `web/src/calm/deck.ts`; PRs #49, #56).
- Backend only: `POST /cases/{id}/intake` reads the description and text PDFs, attaches a pointer to each fact, turns conflicts into questions, asks at most five questions with reasons, flags when a variance may not be needed, and redirects other codes (`docs/api/intake.md`; PR #54).
- Rules on 60 development cases: precision 159/159, recall 159/162 (`python -m evals_dev.intake_facts.score`, run Oct 21; PR #54). In sample, model-checked.
- Invariant (PR #54): over the 60 cases and four stripped copies of each, with the rules and the offline fake model, no fact has a quote that is not in its source.
- Live model check (PR #54): 19 calls, 73 model facts pointed, 0 proposed, 5 dropped, about US$0.012.
- Engineer-needed flag: 50/60 agreement, 27 unknown, in sample (`evals_dev/section_d_flag/RESULTS.md`).

**Gaps:**

- **GAP:** the screens for the reader's pointers, the five questions and the fork and scope notices (in progress).
- **GAP:** no human-verified labels, so every intake figure is model-checked and in sample.
- **GAP:** accuracy across all applicant types is not measured. The 60 cases are agent-authored.

### 2. Code Identification (20%)

**Evidence now:**

- Backend only: all 2,080 Division B articles screened, 60 re-ranked, 15 read by a verifier that must quote word for word, up to three quoted choices, a benchmark acceptable-solution record per result, Div A 1.2.1.1. and Div C 2.3.1.1. attached read-only, a labelled keyword fallback (`docs/api/identify.md`; PR #52). The commit rule needs a calibration file and none exists, so nothing is committed automatically.
- Built: code library with a relevance ring on each article and a structured reader (PRs #47, #56). Section C looked up from the attribution tables, with a row for 72.1% of Division B sentences in parts with a table (`codedb/README.md`).
- Measured on 53 public precedents (relevance stage only, no verifier): first place 64% against 32% for keyword search, first five 81% against 66% (`docs/research/2026-10-20-vision/README.md` §6, which names the subfolder that holds the data and scripts).
- Cost: US$0.019 to US$0.020 per run, measured in the benchmark ledger (draft PR #58; `docs/research/2026-10-21-source-checks.md` §5).
- Citations: every citation in the docs was looked up in the 2nd-printing database (`docs/research/2026-10-21-source-checks.md` §7). A fixed-seed audit of 30 provisions found 0 mismatches (`codedb/README.md`).

**Gaps:**

- **GAP:** accuracy of the final pipeline. Draft PR #58 holds two complete draws of the relevance stage for 139 cases. The third draw and the latency pass need about US$3 to US$4 of account credit, and the decision memo and `pipeline.json` are not generated.
- **GAP:** the commit rule is uncalibrated, so there is no committed-pick precision to report.
- **GAP:** the screens for quoted choices and the benchmark record (in progress).
- **GAP:** the written explainer paragraph per article (brief §2.1.c.iii). The `Explainer` field exists in `engine/models.py` and nothing fills it. What exists is a one-line verifier reason per pick (backend) and the national intent statements shown as "Why this rule exists".
- **GAP:** no held-out result is reported. The judge-only set of 48 scenarios sits outside the repo and its harness is in draft PR #58.

### 3. Recommendations (10%)

**Evidence now:**

- Built: the professional-involvement result as an amber callout on the review screen, with the line "Batatis can list what that evidence must address, but it can't write it." Section D cards list evidence documents and the responsible person. Cards for rationale, risk, mitigation, assumptions, maintenance and qualifications say the applicant writes them (`web/src/calm/Review.tsx`, `web/src/calm/deck.ts`).
- Engine: `engine/professional.py` answers required, depends or no, with the Division C rule (2.4.1.1.(3), 2.4.1.2.(1) and others; the rules and PDF pages are in `research/facts/professional-involvement.md`) and never answers "no" on missing facts. Flag agreement 50/60 in sample (`evals_dev/section_d_flag/RESULTS.md`).
- Roadmap: coded rules for 9.10.15.5.(8) to (10), 9.10.11.2.(2) and 9.10.13.13.(1), and standing-package checklists (`docs/research/2026-10-20-vision/2-week-build.md`).

**Gaps:**

- **GAP:** no engineer or officer has reviewed the professional-involvement labels, the rule vectors or the checklists.
- **GAP:** the CCMC registry search exists in the API (`/ccmc/search`, with a bundled snapshot of the public registry index dated 2026-10-18; PR #60), and no screen uses it.

### 4. Review (10%)

**Evidence now:**

- Built: queue with tabs and claim, take-over, the application as a paper sheet beside its completeness list, messages, notifications, "Accept as complete" and "Return with message" (`docs/api/accounts-review.md`; PRs #48, #49). An agent-run browser walk completed sign-up, submit, claim, return, resubmit and accept (PR #49).
- Backend only: the package review of fillable and flattened SCC forms with attachments, a documents panel, a deterministic information request, an "x of y gaps resolved" diff, the Division C 2.3.1.1 file-item findings, a peer-review signal for the officer, and a close-out record with a due date 10 days after the decision (`docs/api/package-review.md`; PR #53). The 10-day date is the rule before Dec 1, 2026, and the record does not yet follow the portal timing that starts on Dec 1. Tests plant defects from 16 classes in synthetic forms (`engine/tests/test_package_review_planted.py`).

**Gaps:**

- **GAP:** the package review and close-out screens (in progress).
- **GAP:** the package review does not check that a rationale is present. It checks the description of the proposed alternative, the risk assessment, the mitigating measures and the assumptions and limits (`docs/implementation-plan.md` §2.3).
- **GAP:** officer time saved. The timing protocol is `docs/user-testing/officer-timing-protocol.md`, and no session has run.
- **GAP:** the blind 20-application planted-defect evaluation in `evals_dev/planted/SPEC.md`.
- **GAP:** refusal is not in Batatis. The officer's written reasons and the 30-day appeal notice stay in the authority's process.

### 5. General Applicability (5%)

**Evidence now:**

- Built: onboarding sets manufacturer, general contractor or homebuilder, and the starting questions differ by role (`web/src/calm/auth/onboardingSteps.ts`, `web/src/calm/Start.tsx`). Every card says why it asks.
- Three fictional demo cases, one per type, as test inputs (`evals/demo-cases/`).

**Gaps:**

- **GAP:** no first-time applicant has tried it. The target is 2 of 3 finishing Part 1 unaided (`docs/implementation-plan.md` §7.2).
- **GAP:** the demo cases were checked against the 1st printing and spot-checked in the 2nd (`evals/demo-cases/README.md`), so they are not used as evidence of code accuracy.

### 6. Implementation Plan (10%)

**Evidence now:**

- `docs/implementation-plan.md`: state of the product, the Council's six steps mapped to Batatis, the officer workflow with the Council copy and the Dec 1 portal rule, the regulatory fit, hosting and data handling, the path to beta with the definition of beta and its dependencies, and the user-testing plan.
- `docs/user-testing/` (session script, consent form, officer timing protocol). `docs/pilot-adoption-plan.md`. Jurisdiction onboarding by data packs: `docs/api/jurisdictions.md` (PR #51).

**Gaps:**

- **GAP:** no human session has run and no pilot partner has agreed to anything.
- **GAP:** Canadian-region hosting is a plan. The demo runs in the US East region.

### 7. Business Plan (10%)

**Evidence now:**

- `docs/business-plan.md`: buyers ranked, willingness to pay with anchors and assumed prices, cost per application from the measured per-stage cost, market size from estimates, competitors, defensibility, and what has not been validated.
- Sources: `docs/research/2026-10-20-vision/C-market-provinces-business.md` and `docs/research/2026-10-21-source-checks.md`.

**Gaps:**

- **GAP:** no buyer has seen a price. Hosting, support and pack upkeep are not priced.
- **GAP:** no team section (see "Decisions for you").

### 8. Usability and Portability (10%)

**Evidence now:**

- Built: the calm interface (`docs/design-system-calm.md`), the official Oct 6, 2026 form as a draft or official PDF pinned to its SHA-256 (`engine/export/field_maps/scc_2026-10.json`), and submit and review for Calgary and Edmonton.
- Export gate G3 (`python scripts/gate_g3.py`, PR #60) passes on three fictional demo cases and a synthetic sample: every applicant field is filled or marked N/A from the applicant's own facts, the exported text passes `codedb validate` with 0 errors, and the appendix uses none of "complies", "safe", "approved" or "adequate" (`docs/research/2026-10-21-source-checks.md` §6).
- Built as data and API: packs for Calgary, Edmonton and the rest of Alberta, 12 other provinces and territories labelled preview, a lint test against city names in code, and a test that adds a fourth pack with no code change (`docs/api/jurisdictions.md`).

**Gaps:**

- **GAP:** no usability test with a person on either side.
- **GAP:** the jurisdiction picker and process-notes screen (in progress). The Calgary form export, the Appendix 1 export and Part 2 prefill are roadmap.
- **GAP:** reviewer accounts exist only for Calgary and Edmonton.

### 9. The X Factor (5%)

**Evidence now:**

- The Oct 6 form change was caught and the export pinned to it (`docs/research/2026-10-21-source-checks.md` §3). Three articles are 69% of the Q1 to Q2 2026 Data Hub entries (`docs/research/2026-10-20-vision/C-market-provinces-business.md` §2.0). The product follows the Council's own terms and six steps (`docs/implementation-plan.md` §2).

**Gaps:**

- **GAP:** the team, the insight and the unfair advantage are not described in any file. Only the user can supply this text.

## Challenge scope requirements

From the Challenge Scope, §2 ("Detailed Technical Scope").

| Item | Status |
|---|---|
| 1.a Prompt for the information Sections A and B need | Built (deck). The reader that fills them from files is backend only |
| 1.b.i Select relevant codes and rank them | Backend only. The library ranks articles with relevance rings (built) |
| 1.b.ii Recommend the most likely benchmark acceptable solution, with an explanation | Backend only (benchmark record per result) |
| 1.c Complete Section C by lookup | Built. A row exists for 72.1% of sentences in parts with a table |
| 1.c.iii An explainer paragraph for each article and why | **GAP** (see criterion 2) |
| 2 Say when a professional or an engineer is involved | Built (callout) over the engine check |
| 3 Recommend issues and code sections for Section D | Built: the Section D card loads the engine's issues and evidence plan. It never writes the evidence |
| 4 Review an application for completeness | Built for Batatis cases. Backend only for uploaded forms with attachments |
| 5.a Export a PDF that matches the template | Built for the Oct 6, 2026 form. The Appendix 1 layout is roadmap by decision (`docs/implementation-plan.md` §4.3) |
| 5.b Portable data | Built (packs) |

## Open work, ranked by rubric weight

1. **Screens for intake and code identification** (40 points between criteria 1 and 2). In progress.
2. **The code identification benchmark and the commit decision.** Needs account credit.
3. **Package review and close-out screens** (criterion 4).
4. **Record the demo video** after the screens land (script preconditions).
5. **Refresh the pitch deck** after the screens land.
6. **Human sessions.** None are scheduled.
7. **The live-mode decision** and the total spend cap (PR #41).
8. **Release `dev` to `main`** and confirm judge access to the repo.
9. **Team and X-factor text.**
10. **The explainer paragraph** (brief §2.1.c.iii).
11. **Close-out timing for Dec 1.** `engine/review/close_out.py` sets every due date to 10 days after the decision. From Dec 1, 2026 the Council wants variances registered at issuance or as soon as reasonably practicable after (IB-2026-10-01). Change the record before a pilot.

## Decisions for you

These need an answer or a file that only you can supply.

1. **Live model access for the demo.** Turn it on, which needs the spend cap in PR #41, or keep it off and accept the labelled keyword fallback and unscored rings.
2. **How judges and the video sign in as an officer.** Share the access code, or seed a demo reviewer.
3. **Who the plans can say you have spoken to.** The earlier plans said "we have contacted no one". The rewritten plans say only that no partner has agreed to anything. If you have spoken with Safety Codes Council experts, say what may be written.
4. **The team text** for criterion 9 and the business plan.
5. **Whether the reviewer's "Accept as complete" also stands for the officer's decision to issue the variance.** The product says "Accepted as administratively complete", and the close-out record starts its 10-day clock at that decision. The Council's decision to issue a variance is the officer's own act under s.38. Decide how the demo and the plans should describe it.
6. **Account credit** for the benchmark (about US$3 to US$4) and whether to spend it before Oct 29.
7. **Whether to close PR #32 and PR #20** after PR #59 merges. Both are superseded.

## How the claims were checked

- Every figure in the judge-facing documents was extracted by script and matched against the repo's source files, the new source-check note and the primary PDFs read on Oct 21 (`docs/research/2026-10-21-source-checks.md`). Derived figures are labelled arithmetic, and assumed figures carry their basis.
- Council bulletins were re-downloaded, and each file's SHA-256 matched the hash in `engine/data/jurisdictions/provinces/AB.json`.
- Every code citation was looked up with `python -m codedb lookup` in the NBC(AE) 2023, 2nd-printing database.
- Judge-facing documents name no AI or scoring provider. They say "a relevance model" and "a third-party AI provider".
- No statistic, quote, customer or pilot result is invented, and the user-testing appendix still says that no real session has run.

## Open pull requests that touch the package

| PR | What | Action |
|---|---|---|
| #59 | This refresh. Supersedes #32 | Merge |
| #58 | Code identification benchmark (draft) | Finish after account credit. Do not merge as it is |
| #41 | Hard total spend cap and pre-public checks | Decide with the live-mode question |
| #32 | The earlier v2 plans and deck | Superseded by #59. Close after #59 merges |
| #20 | A 3-minute demo script for the retired interface | Superseded by `docs/demo/script.md`. Close after #59 merges |
| #28 | A one-command demo recorder | Check against the final screens before use |
| #43 | Keyed benchmark results from the superseded pipeline | Stale. Review before merging |
| #42 | NRC attribution wording | Review |
