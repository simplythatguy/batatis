# Batatis: 3-Minute Pitch Narration

*Spoken script for the 12 slides in pitch-slides.md (Submission 1, Oct 29, 2026). Text is written the way it is said aloud, so word counts are spoken words (code numbers and figures count as spoken). Time windows are at 150 words a minute, with about 5 seconds of slide changes spread across the 11 transitions. Each slide also shows its time at 140 words a minute. Every number traces to the Business Plan (BP), Implementation Plan (IP), or the PR #14, #20 and #12 sources; see the table at the end. Line numbers are for the docs in this folder (docs/).*

---

### Slide 1: Alberta's variance paperwork keeps bouncing back
**Time (150 wpm):** 0:00–0:07  |  **Spoken words:** 18  |  **At 150 wpm:** 7.2 s  |  **At 140 wpm:** 7.7 s

> A variance request goes to a safety codes officer. Alberta registered seventeen thirteen building variances in twenty twenty-two.

### Slide 2: Describe your project in plain words
**Time (150 wpm):** 0:08–0:20  |  **Spoken words:** 31  |  **At 150 wpm:** 12.4 s  |  **At 140 wpm:** 13.3 s

> In the app, in review, you pick your role and reviewing authority, then describe the project. Gaps become questions, and Not sure is saved as an open question, not a guess.

### Slide 3: It asks before it guesses, and we test that
**Time (150 wpm):** 0:21–0:38  |  **Spoken words:** 44  |  **At 150 wpm:** 17.6 s  |  **At 140 wpm:** 18.9 s

> Our engineer-needed check is now built into the engine. The shipped variant matched fifty of sixty in-sample cases, model-checked, and sent twenty-seven unknowns to the applicant. On eight held-out cases, blind before a fix, it got seven; after the fix, no longer blind, four.

### Slide 4: A ranked shortlist, measured against a named acceptable solution
**Time (150 wpm):** 0:39–0:53  |  **Spoken words:** 35  |  **At 150 wpm:** 14.0 s  |  **At 140 wpm:** 15.0 s

> Search finds nine point nine point ten point one, sentence two, second printing: at least point three five square metres. The window opens point three one two. Section C looks up its objective and function.

### Slide 5: Citations come from the code database
**Time (150 wpm):** 0:53–1:13  |  **Spoken words:** 51  |  **At 150 wpm:** 20.4 s  |  **At 140 wpm:** 21.9 s

> In a draft pull request, the AI ranking put the right article first, and in the top five, on nine of eleven practice cases with a gold answer, nine excluded, single run; model-checked, not human-verified. Keyword search alone put it first on five. It asked instead of guessing on forty percent.

### Slide 6: It knows where to stop
**Time (150 wpm):** 1:14–1:22  |  **Spoken words:** 21  |  **At 150 wpm:** 8.4 s  |  **At 140 wpm:** 9.0 s

> Where no tested system fits, it's designed to say an engineer's judgment is needed, and stop. It never writes the evidence.

### Slide 7: Completeness review: built in the engine, officer screen in review
**Time (150 wpm):** 1:23–1:35  |  **Spoken words:** 31  |  **At 150 wpm:** 12.4 s  |  **At 140 wpm:** 13.3 s

> For officers, the check lists gaps by form section, never compliance. The screen, in review, shows one planted sample package; Copy request lists administrative items, not a decision. No timing data.

### Slide 8: One tool, three kinds of first-time applicants
**Time (150 wpm):** 1:36–1:43  |  **Spoken words:** 18  |  **At 150 wpm:** 7.2 s  |  **At 140 wpm:** 7.7 s

> Three fictional applicants, one form: homebuilder, manufacturer, general contractor. Each gets Not sure on every question, in review.

### Slide 9: Fills the current SCC form; built to travel
**Time (150 wpm):** 1:43–1:57  |  **Spoken words:** 34  |  **At 150 wpm:** 13.6 s  |  **At 140 wpm:** 14.6 s

> In the app, in review, once every gap closes, it downloads the Council's October sixth form, not Appendix 1, filled in by the engine, unsigned, officer's part blank. It is not a compliance finding.

### Slide 10: Built for the December 1 rules
**Time (150 wpm):** 1:57–2:17  |  **Spoken words:** 49  |  **At 150 wpm:** 19.6 s  |  **At 140 wpm:** 21.0 s

> From December first, the Council's portal is the only way to register; registration isn't approval. A simulated walkthrough reached the form only because the engineer-needed gap cleared on its own answers. An open fix would keep it flagged until a professional and a seal or registration number are confirmed.

### Slide 11: Applicants pay to arrive complete
**Time (150 wpm):** 2:17–2:31  |  **Spoken words:** 35  |  **At 150 wpm:** 14.0 s  |  **At 140 wpm:** 15.0 s

> First buyer: production homebuilders. Price to test: one twenty-five to seven fifty dollars a package. In the draft pull request, identification cost under three cents a case on practice cases, five point seven seconds median.

### Slide 12: We read the regulator's own data
**Time (150 wpm):** 2:32–2:45  |  **Spoken words:** 32  |  **At 150 wpm:** 12.8 s  |  **At 140 wpm:** 13.7 s

> In Q-one to Q-two twenty twenty-six, fifteen oh one of three thousand eighty-eight building article entries were one soffit article. No real user has tried Batatis. Batatis checks completeness. The officer decides.

---

**Total: 399 spoken words. With about 5 s of slide changes: 2:44 at 150 wpm, 2:56 at 140 wpm.**
## Traceability

BP = business-plan.md, IP = implementation-plan.md, QA = judge-qa.md, PO = pitch-outline.md (the files in this docs/ folder). PR #20 = `docs/demo/script.md` at c432e32. PR #14 = demo case C README. PR #12 = PR body, keyed results at 67f06bc.

| Slide | Claim | Source |
|---|---|---|
| 1 | A variance request goes to a safety codes officer of the reviewing authority (Calgary's guide points applicants to its own attached Request for Specific Variance form) | BP §1; City of Calgary guide, step 3 |
| 1 | 1,713 building variances registered in 2022 | BP §3 |
| 2 | Role picker ("Who are you?") and reviewing-authority pick, which clears "Reviewing authority missing" (PR #16, in review; #16 @579cd2c) | PR #20 shots 1, 2 and 7; IP §3; QA Q9 |
| 2 | Gaps become questions; "Not sure" is saved as an open question (PR #16, in review) | PR #20 shot 3 ("Logged as an open question"); IP §1; QA Q5 |
| 3 | Engineer-needed check built into the engine (PR #8, on dev as 69fb4ff) | IP §10; QA Q2; PO slide 3 row |
| 3 | Shipped variant (rules_plus_unknown) 50/60 in-sample, model-checked (gold labels derived from the rules under test); 27 unknowns sent to the applicant | IP §10 |
| 3 | Shipped variant held-out 7/8 blind (pre-fix), 4/8 post-fix (no longer blind) | IP §10; QA Q2 |
| 4 | Search finds Sentence 9.9.10.1.(2); 2nd printing; at least 0.35 m² | PR #20 shot 4; IP §9; code database snapshot (NBC(AE) 2023 p2, 9.9.10.1.(2)(a): "not less than 0.35 m²") |
| 4 | Demo window opens 0.312 m² (400 × 780 mm) | PR #14 case C README ("0.312 m² fails on area"); PR #20 Case C paste |
| 4 | Section C looks up objective and function from the code's attribution tables | QA Q3, Q18; PO slide 5 row |
| 5 | Identification in a draft pull request (PR #12) | IP §4 |
| 5 | AI ranking (c_openai_rerank_verify): top-1 9/11 and recall@5 9/11, in-sample, single run; keyword (BM25) baseline top-1 5/11 (its recall@5 is 7/11) | IP §4; BP §6; PR #12 body ("repeat-0 only"; a_bm25 recall@5 0.6364) |
| 5 | Asks the applicant on 40% of cases | IP §4; BP §6 |
| 5 | 9/11 on dev cases with gold, 9 excluded; model-checked, not human-verified | IP §4; IP §10 |
| 6 | Where no tested system fits, designed to say an engineer's judgment is needed, and stop; never writes the evidence | Slides s6; QA Q19; PO slide 6 row |
| 7 | Gaps by form section; never judges compliance | IP §3; IP §2 |
| 7 | Officer screen in review, one planted sample package; Copy request lists administrative items, not a decision (PR #16; not on `dev`) | PR #20 shot 6; PO slide 7 row |
| 7 | No timing data | IP §7; IP §11 |
| 8 | Three fictional applicants, one form, "Not sure" on every question (PR #16, in review) | IP §9; PR #20 shots 1 and 3 |
| 9 | In the app (PR #16, in review), once every gap is closed, Check completeness downloads the Council's Oct 6, 2026 form (not Appendix 1), filled in by the engine, unsigned, officer Part 2 blank; the "not a finding that the design complies" notice is the app's dialog | Hands-on downloads at #16 @579cd2c (the 5-page Oct 6, 2026 form plus engine-generated attachment pages, 7 in total for the simulated walkthrough case; not the brief's Appendix 1; field map scc_2026-10); IP §3; BP §1; QA Q6 |
| 10 | From Dec 1, the portal is the only registration route; registration is not approval | IP §3 |
| 10 | A simulated walkthrough reached the form only because the engineer-needed gap cleared on the simulated user's own answers; PR #26 (open) would keep it flagged until a professional and a seal or registration number are confirmed | IP §7 (session 3 re-run row); QA Q17; PR #26 |
| 11 | First buyer: production homebuilders | BP §4 |
| 11 | Price to test C$125–750 per package | BP §5 |
| 11 | Identification model cost under three cents a case on practice (dev) cases, in draft PR #12 (C$0.0277; US$0.019676 × 1.4097 = C$0.027738) | BP §6; IP §4; PR #12 |
| 11 | 5.7 s median latency | BP §6; IP §4 |
| 12 | Q1–Q2 2026: 1,501 of 3,088 building article entries are one soffit article, 9.10.15.5.(8) | BP §2 |
| 12 | No real user has tested Batatis | IP §11 |
