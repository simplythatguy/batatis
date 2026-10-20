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
**Time (150 wpm):** 0:21–0:40  |  **Spoken words:** 48  |  **At 150 wpm:** 19.2 s  |  **At 140 wpm:** 20.6 s

> Our engineer-needed check is now built into the engine. The shipped variant matched fifty of sixty cases it was tuned on, and sent twenty-seven unknowns to the applicant. On eight held-out cases, blind before a fix, the shipped variant got seven; after the fix, no longer blind, four.

### Slide 4: A ranked shortlist, measured against a named acceptable solution
**Time (150 wpm):** 0:40–0:54  |  **Spoken words:** 35  |  **At 150 wpm:** 14.0 s  |  **At 140 wpm:** 15.0 s

> Search finds nine point nine point ten point one, sentence two, second printing: at least point three five square metres. The window opens point three one two. Section C looks up its objective and function.

### Slide 5: Every citation resolves, or it's dropped
**Time (150 wpm):** 0:55–1:14  |  **Spoken words:** 49  |  **At 150 wpm:** 19.6 s  |  **At 140 wpm:** 21.0 s

> In an open pull request, the AI ranking put the right article first, and in the top five, on nine of eleven practice cases, in a single run. Keyword search alone put it first on five. It asked instead of guessing on forty percent. All of it is model-checked.

### Slide 6: It knows where to stop
**Time (150 wpm):** 1:15–1:26  |  **Spoken words:** 29  |  **At 150 wpm:** 11.6 s  |  **At 140 wpm:** 12.4 s

> It says when a registered professional is needed, cites the Division C rule, and never writes the evidence. An open fix keeps that flag until a professional is confirmed.

### Slide 7: Completeness review: built in the engine, officer screen in review
**Time (150 wpm):** 1:27–1:39  |  **Spoken words:** 31  |  **At 150 wpm:** 12.4 s  |  **At 140 wpm:** 13.3 s

> For officers, the check lists gaps by form section, never compliance. The screen, in review, shows one planted sample package; Copy request lists administrative items, not a decision. No timing data.

### Slide 8: One tool, three kinds of first-time applicants
**Time (150 wpm):** 1:40–1:48  |  **Spoken words:** 22  |  **At 150 wpm:** 8.8 s  |  **At 140 wpm:** 9.4 s

> Three fictional applicants, one form: homebuilder, manufacturer, general contractor. Each gets a role-shaped start and Not sure on every question, in review.

### Slide 9: Fills the current SCC form; built to travel
**Time (150 wpm):** 1:49–2:02  |  **Spoken words:** 34  |  **At 150 wpm:** 13.6 s  |  **At 140 wpm:** 14.6 s

> In the app, in review, once every gap closes, it downloads the Council's October sixth form, not Appendix 1, filled in by the engine, unsigned, officer's part blank. It is not a compliance finding.

### Slide 10: Ready for December 1
**Time (150 wpm):** 2:03–2:22  |  **Spoken words:** 48  |  **At 150 wpm:** 19.2 s  |  **At 140 wpm:** 20.6 s

> From December first, the Council's portal is the only way to register; registration isn't approval. A simulated walkthrough reached the form only because the engineer-needed gap cleared on its own answers. An open fix keeps it flagged until a professional and a seal or registration number are confirmed.

### Slide 11: Applicants pay to arrive complete
**Time (150 wpm):** 2:23–2:35  |  **Spoken words:** 30  |  **At 150 wpm:** 12.0 s  |  **At 140 wpm:** 12.9 s

> First buyer: production homebuilders. Price to test: one twenty-five to seven fifty dollars a package. Identification costs under three cents a case on dev cases, five point seven seconds median.

### Slide 12: We read the regulator's own data
**Time (150 wpm):** 2:35–2:48  |  **Spoken words:** 32  |  **At 150 wpm:** 12.8 s  |  **At 140 wpm:** 13.7 s

> In Q-one to Q-two twenty twenty-six, fifteen oh one of three thousand eighty-eight building article entries were one soffit article. No real user has tried Batatis. Batatis checks completeness. The officer decides.

---

**Total: 407 spoken words. With about 5 s of slide changes: 2:47 at 150 wpm, 2:59 at 140 wpm.**
## Traceability

BP = business-plan.md, IP = implementation-plan.md, QA = judge-qa.md, PO = pitch-outline.md (the v2 copies, re-based on ready/ as approved at 4389fb4). PR #20 = `docs/demo/script.md` at c432e32. PR #14 = demo case C README. PR #12 = PR body, keyed results at 67f06bc.

| Slide | Claim | Source |
|---|---|---|
| 1 | A variance request goes to a safety codes officer of the reviewing authority (Calgary uses its own form) | BP §1 L8; fact-check (Calgary guide, step 3) |
| 1 | 1,713 building variances registered in 2022 | BP §3 L23 |
| 2 | Role picker ("Who are you?") and reviewing-authority pick, which clears "Reviewing authority missing" (PR #16, in review; #16 @579cd2c) | PR #20 shots 1, 2 and 7; IP §3 L45; QA L30 |
| 2 | Gaps become questions; "Not sure" is saved as an open question (PR #16, in review) | PR #20 shot 3 ("Logged as an open question"); IP §1 L11; QA L18 |
| 3 | Engineer-needed check built into the engine (PR #8, on dev as 69fb4ff) | IP §10; QA L9; PO L15 |
| 3 | Shipped variant (rules_plus_unknown) 50/60 in-sample ("cases it was tuned on": gold labels derived from the rules under test); 27 unknowns sent to the applicant | IP §10 |
| 3 | Shipped variant held-out 7/8 blind (pre-fix), 4/8 post-fix (no longer blind) | IP §10; QA L9 |
| 4 | Search finds Sentence 9.9.10.1.(2); 2nd printing; at least 0.35 m² | PR #20 shot 4; IP §9; code database snapshot (NBC(AE) 2023 p2, 9.9.10.1.(2)(a): "not less than 0.35 m²") |
| 4 | Demo window opens 0.312 m² (400 × 780 mm) | PR #14 case C README ("0.312 m² fails on area"); PR #20 Case C paste |
| 4 | Section C looks up objective and function from the code's attribution tables | QA L12, L57; PO L17 |
| 5 | Identification in an open pull request (PR #12) | IP §4 |
| 5 | AI ranking (c_openai_rerank_verify): top-1 9/11 and recall@5 9/11, in-sample, single run; keyword (BM25) baseline top-1 5/11 (its recall@5 is 7/11) | IP §4 L89; BP §6 L72; PR #12 ("repeat-0 only") |
| 5 | Asks the applicant on 40% of cases | IP §4 L89; BP §6 L72 |
| 5 | All results model-checked | IP §4 L89; IP §10 |
| 6 | Says when a registered professional is needed, with the Division C rule; never writes the evidence | Slides s6; IP §9; QA L60; PR #20 shot 5 |
| 6 | The open fix keeps the flag until a professional and a seal or registration number are confirmed | PR #26 (open), "Require a confirmed professional before an issue lists evidence" |
| 7 | Gaps by form section; never judges compliance | IP §3 L43; IP §2 L27 |
| 7 | Officer screen in review, one planted sample package; Copy request lists administrative items, not a decision (PR #16; not on `dev`) | PR #20 shot 6; PO L19 |
| 7 | No timing data | IP §7; IP §11 |
| 8 | Three fictional applicants, one form, role-shaped start, "Not sure" on every question (PR #16, in review) | IP §9 L152; PR #20 shots 1 and 3 |
| 9 | In the app (PR #16, in review), once every gap is closed, Check completeness downloads the Council's Oct 6, 2026 form (not Appendix 1), filled in by the engine, unsigned, officer Part 2 blank; the "not a finding that the design complies" notice is the app's dialog | Hands-on downloads at #16 @579cd2c (7-page PDF: the 5-page form plus appendix; field map scc_2026-10); IP §3; BP §1 L6; QA L21 |
| 10 | From Dec 1, the portal is the only registration route; registration is not approval | IP §3 L44 |
| 10 | A simulated walkthrough reached the form only because the engineer-needed gap cleared on the simulated user's own answers; PR #26 (open) would keep it flagged until a professional and a seal or registration number are confirmed | IP §7 (session 3 re-run row); QA L54; PR #26 |
| 11 | First buyer: production homebuilders | BP §4 L42 |
| 11 | Price to test C$125–750 per package | BP §5 L65 |
| 11 | Identification model cost under three cents on dev cases (C$0.0277; US$0.019676 × 1.4097 = C$0.027738) | BP §6 L72; IP §4 L89; PR #12 |
| 11 | 5.7 s median latency | BP §6 L72; IP §4 L89 |
| 12 | Q1–Q2 2026: 1,501 of 3,088 building article entries are one soffit article, 9.10.15.5.(8) | BP §2 L15 |
| 12 | No real user has tested Batatis | IP §11 |
