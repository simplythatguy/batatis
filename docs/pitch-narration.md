# Batatis: 3-Minute Pitch Narration

*Spoken script for the 12 slides in `pitch-slides.md` (Submission 1, Oct 29, 2026). Status is as of Oct 21, 2026. Text is written the way it is said aloud, so numbers are spelled out and word counts are spoken words. Time windows use 150 words a minute plus about 5 seconds in total for the 11 slide changes. Each slide also shows its length at 140 words a minute. Every claim traces to the table at the end.*

---

## Script

### Slide 1: Alberta's variances are frequent, repetitive and unmeasured

**Time (150 wpm):** 0:00 to 0:14  |  **Spoken words:** 34  |  **At 150 wpm:** 13.6 s  |  **At 140 wpm:** 14.6 s

> Alberta's building variances are frequent, repetitive and unmeasured. In the first half of twenty twenty-six, the Council counted three thousand and eighty-eight building articles varied, and one soffit article is nearly half of them.

### Slide 2: Describe it in plain words, then answer one question at a time

**Time (150 wpm):** 0:14 to 0:26  |  **Spoken words:** 30  |  **At 150 wpm:** 12.0 s  |  **At 140 wpm:** 12.9 s

> Describe the project in plain words. Batatis asks one question at a time for the form's sections A to D, and nothing you say is used until you confirm it.

### Slide 3: It asks before it guesses, and we test that

**Time (150 wpm):** 0:27 to 0:41  |  **Spoken words:** 36  |  **At 150 wpm:** 14.4 s  |  **At 140 wpm:** 15.4 s

> It asks before it guesses. On sixty practice cases that we wrote ourselves, the rules read a hundred and fifty-nine facts and got none wrong. They missed three. Where facts conflict or are missing, it asks.

### Slide 4: Every Division B article is screened, then quoted

**Time (150 wpm):** 0:41 to 0:55  |  **Spoken words:** 33  |  **At 150 wpm:** 13.2 s  |  **At 140 wpm:** 14.1 s

> Code identification scores all two thousand and eighty Division B articles, re-ranks sixty, and has a verifier quote the text. It offers up to three quoted choices, and it commits nothing by itself.

### Slide 5: Citations come from the code database

**Time (150 wpm):** 0:55 to 1:14  |  **Spoken words:** 48  |  **At 150 wpm:** 19.2 s  |  **At 140 wpm:** 20.6 s

> A quote that does not match the code word for word is dropped. Section C is a lookup. On fifty-three public precedents, screening and re-ranking put a cited article first sixty-four percent of the time, against thirty-two for keyword search. The benchmark for the final pipeline is unfinished.

### Slide 6: It knows where to stop

**Time (150 wpm):** 1:15 to 1:24  |  **Spoken words:** 24  |  **At 150 wpm:** 9.6 s  |  **At 140 wpm:** 10.3 s

> It knows where to stop. It says whether an engineer is required, and lists what the evidence must address. It never writes the evidence.

### Slide 7: Officers see gaps by section, never a verdict

**Time (150 wpm):** 1:25 to 1:34  |  **Spoken words:** 24  |  **At 150 wpm:** 9.6 s  |  **At 140 wpm:** 10.3 s

> For officers, there is a queue, a paper sheet, and gaps by section. There is never a verdict. We have no timing data yet.

### Slide 8: One flow for three kinds of first-time applicants

**Time (150 wpm):** 1:35 to 1:44  |  **Spoken words:** 22  |  **At 150 wpm:** 8.8 s  |  **At 140 wpm:** 9.4 s

> One flow serves a manufacturer, a general contractor and a homebuilder. Whether a real first-time applicant can use it unaided is untested.

### Slide 9: It fills the Council's current form and is built to travel

**Time (150 wpm):** 1:44 to 1:54  |  **Spoken words:** 26  |  **At 150 wpm:** 10.4 s  |  **At 140 wpm:** 11.1 s

> It fills the Council's current form, dated October sixth, and leaves the officer's part blank. Jurisdiction packs are data: Calgary, Edmonton and the rest of Alberta.

### Slide 10: It fits the Dec 1 portal switch

**Time (150 wpm):** 1:55 to 2:10  |  **Spoken words:** 37  |  **At 150 wpm:** 14.8 s  |  **At 140 wpm:** 15.9 s

> From December first, the Council's portal is the only way to register a variance, and registration is not approval. Our path is Submission two, Demo Day, then a pilot with one accredited organization, which is a target.

### Slide 11: Applicants pay to arrive complete

**Time (150 wpm):** 2:10 to 2:25  |  **Spoken words:** 36  |  **At 150 wpm:** 14.4 s  |  **At 140 wpm:** 15.4 s

> Applicants pay to arrive complete. One identification run costs about two cents in model fees. The price to test is one hundred fifty to seven hundred fifty dollars a package. No buyer has seen a price.

### Slide 12: We read the regulator's own data

**Time (150 wpm):** 2:25 to 2:37  |  **Spoken words:** 29  |  **At 150 wpm:** 11.6 s  |  **At 140 wpm:** 12.4 s

> We read the regulator's own data. Three articles make up sixty-nine percent of the entries. No one outside our team has tried Batatis. It checks completeness. The officer decides.

---

**Total: 379 spoken words. With about 5 seconds of slide changes: 2:37 at 150 wpm, 2:47 at 140 wpm.**

## Traceability

IP is `implementation-plan.md`, BP is `business-plan.md`, SC is `research/2026-10-21-source-checks.md`, C is `research/2026-10-20-vision/C-market-provinces-business.md`, and all paths are under `docs/`.

| Slide | Claim | Source |
|---|---|---|
| 1 | 3,088 building-article entries in Q1 to Q2 2026 | C §2.0; BP §3 |
| 1 | One soffit article, 9.10.15.5.(8), has 1,501 of them, which is 49% ("nearly half") | C §2.0 |
| 2 | One question at a time for Sections A to D. Nothing is used until confirmed | `design-system-calm.md` (deck order); IP §3 |
| 3 | The rules read 159 facts and got none wrong, and missed 3, on 60 development cases we wrote, in sample | `evals_dev/intake_facts/score.py` run on Oct 21; SC §6 |
| 3 | Where facts conflict or are missing, it asks | `api/intake.md` (conflicts, questions) |
| 4 | All 2,080 Division B articles are scored, 60 re-ranked, a verifier quotes the text, up to three quoted choices, nothing committed | `api/identify.md`; IP §6.2 |
| 5 | A quote that does not match word for word is dropped | `api/identify.md` (verify stage) |
| 5 | Section C is a lookup | `codedb/README.md`; IP §3 |
| 5 | On 53 public precedents the relevance stage put a cited article first 64% of the time, keyword search 32%, without a verifier stage | `research/2026-10-20-vision/README.md` §6 |
| 5 | The benchmark for the final pipeline is unfinished | draft PR #58; IP §6.2 |
| 6 | It says whether an engineer is required and lists what the evidence must address. It never writes it | `engine/professional.py`; `web/src/calm/Review.tsx` |
| 7 | A queue, a paper sheet, gaps by section, no verdict, no timing data | IP §3 and §7; `api/accounts-review.md` |
| 8 | Manufacturer, general contractor and homebuilder, one flow, untested unaided | `web/src/calm/auth/onboardingSteps.ts`; IP §7 |
| 9 | The Council's form dated October 6, with the officer's part blank | `engine/export/field_maps/scc_2026-10.json`; SC §1 |
| 9 | Packs for Calgary, Edmonton and the rest of Alberta are data | `api/jurisdictions.md` |
| 10 | From Dec 1 the portal is the only way to register, and registration is not approval | SC §1 (IB-2026-10-01) |
| 10 | Submission 2, Demo Day, pilot as a target | SC §2; IP §1 |
| 11 | About two cents in model fees per identification run (US$0.019 to US$0.020) | BP §6; SC §5 |
| 11 | Price to test C$150 to C$750 a package, no buyer has seen a price | BP §5.2 |
| 12 | Three articles make up 69% of the entries (2,118 of 3,088) | C §2.0; BP §2 |
| 12 | No one outside the team has tried Batatis | IP §1 |
