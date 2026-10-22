# Batatis: Pitch Slides

*Slide copy for Submission 1 (Oct 29, 2026), built from `pitch-outline.md`. Status is as of Oct 22, 2026. Rubric weights are in brackets. On every slide, the **Hero** line (one figure that is also on the slide) and the dash bullets are the only on-slide text. The detail, the speaker notes and the sources go into the speaker notes. The footer of each slide shows public sources only, and file paths stay in the notes. Status words follow the Implementation Plan, §3: **built** (merged and reachable in the live app or API), **backend** (the API is merged and the screen is in progress), **roadmap** (not started). Evaluation figures are model-checked and mostly in sample, and none is human-verified. No slide shows a screen that is not built: where the screen is pending, the slide shows the built screen or says "backend".*

---

## Slides

### Slide 1: Alberta's variances are frequent, repetitive and unmeasured

**Hero:** 3,088 | building-article entries in the Council's Data Hub, Q1 to Q2 2026

- One article, 9.10.15.5.(8), has 49% of them
- No public measure of how often applications come back

**Full slide detail (in notes):**

- The Data Hub counts varied articles, not applications. Building 3,088, plumbing 22, electrical 3, pressure equipment 3, fire 1, gas 1
- Top five building articles: 1,501, 366, 251, 218 and 167. All are in Part 9, Section 9.10
- Building variances registered 2019 to 2023: 1,553, 637, 1,698, 1,713 and 837 (2023 was still partial)
- The Council says it does not collect supporting materials or alternative solutions

**Speaker notes:** A request for a variance goes to a safety codes officer of the reviewing authority. Batatis fills the Council's current form, and Calgary also asks for its own request form. The organizers describe many first submissions failing as anecdotal, so we do not quote a return rate: nobody publishes one.
*Sources:* [Council Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/); [Council Annual Report 2023](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf), p.32; notes: `docs/research/2026-10-20-vision/C-market-provinces-business.md` §2.0, `docs/research/2026-10-21-source-checks.md` §1

### Slide 2: Describe it in plain words, then answer one question at a time [Intake, 20]

**Hero:** A to D | the form's sections, asked one card at a time (built)

- Built: describe, then one question at a time
- Backend: facts read with a pointer to your own words
- Facts read from your words are not added until you confirm them

**Full slide detail (in notes):**

- Built: the applicant picks a role in onboarding, describes the project, and answers cards in form order. Each card has a plain "Why we ask". "Not sure" keeps an open question for the officer and never blocks
- Backend: the intake reader takes the description and text PDFs. Rules read first and a model is asked only for fields the rules left empty. Every fact stores the phrase or box it came from. Two values for one field give no fact and a question. At most five questions, each with a reason. Pages with no text layer are reported as not read, with the reason, and nothing is guessed
- The screens that show the reader's facts and the five questions are in progress

**Speaker notes:** Intake is a fifth of the score, so we start with it. Today's screens ask one question at a time and keep what the applicant says apart from what is confirmed. The reader that points each fact at the words it came from is merged but is not yet on screen, and we say so rather than show a mock-up.
*Sources:* `docs/design-system-calm.md`; `docs/api/intake.md`

### Slide 3: It asks before it guesses, and we test that [Intake, 20]

**Hero:** 159/159 | typed facts read correctly on 60 development cases · in-sample · model-checked

- 3 missed (recall 159/162)
- Engineer-needed flag: 50 of 60 agree, 27 go to the applicant as unknown
- No human-verified subset exists

**Full slide detail (in notes):**

- Intake rules on the 60 development cases: precision 159/159 (95% Wilson 0.976 to 1.000), recall 159/162 (0.947 to 0.994). Misses: dev-014, dev-047, dev-051. Reproduce with `python -m evals_dev.intake_facts.score`
- In sample: the labels were written while the rules were written, and the cases are agent-authored
- Engineer-needed flag on the same 60 cases: the shipped variant agrees with model-written labels on 50 of 60 (95% Wilson 0.72 to 0.91) and sends 27 to the applicant as unknown. On these text-only cases it never answers "no", so zero under-flags holds by construction
- A rules-only variant that is not shipped agrees on 55 of 60 and under-flags once

**Speaker notes:** These are our own cases, so the numbers show the code behaves as designed and nothing more. The point is the behavior: when facts conflict or are missing, Batatis asks. It does not fill the box. A human-verified set needs an engineer or an officer to label cases, and that is not scheduled.
*Sources:* `evals_dev/intake_facts/score.py`; `evals_dev/section_d_flag/RESULTS.md`; `docs/research/2026-10-21-source-checks.md` §6

### Slide 4: Every Division B article is screened, then quoted [Code Identification, 20]

**Hero:** 2,080 | Division B articles scored for each description

- A relevance model scores all of them, re-ranks 60, and a verifier quotes the text
- Up to three quoted choices. Nothing is committed automatically
- Backend merged. Screen in progress. Benchmark unfinished

**Full slide detail (in notes):**

- Pipeline: screen every Division B article, re-rank the top 60 in one request, have a verifier read the full text of the top 15 and quote it word for word
- Quotes that do not match the article are dropped. The pipeline checks again before display
- Commit rule: only Part 9 and at most three articles can ever be committed, and only with a calibration file from the benchmark. No such file exists yet, so every article is a candidate or one of up to three quoted choices
- Each result stores a benchmark acceptable-solution record: the quoted Division B sentence the design departs from, and its objective and function codes. Div A 1.2.1.1. and Div C 2.3.1.1. are attached read-only to every case
- If a model stage is unavailable, a labelled keyword fallback runs and commits nothing
- The Council deck's worked example is Sentence 9.10.15.4.(1), openings in an exposing building face: function F03, objective OP3.1 (Table 9.38.1.1., PDF p.1130)

**Speaker notes:** We would rather ask than guess. The commit rule is empty on purpose until the benchmark calibrates it. The relevance model is a third-party service pinned to one version and shown to users only as "relevance-1".
*Sources:* `docs/api/identify.md`; `engine/identify/`; `docs/research/2026-10-21-source-checks.md` §7

### Slide 5: Citations come from the code database [Code Identification, 20]

**Hero:** 64% | an article the precedent cites ranked first · relevance stage · 53 public precedents · keyword search alone: 32%

- A quote that does not match word for word is dropped
- Section C is a lookup. It has a row for 72.1% of the sentences in parts with a table, and the screen says so when it has none
- Final-pipeline benchmark: unfinished

**Full slide detail (in notes):**

- 53 Alberta precedents, 2,080 articles, run on Oct 20, 2026. Keyword search: first 32%, in the first five 66%. Screening all articles then re-ranking 60: first 64%, in the first five 81%, and 88% of cited articles within the first 50 (keyword search 77%)
- Limits: no verifier stage in that run, 53 cases from one province and one code, gold lists can be incomplete. Not a held-out professional evaluation
- A separate blind test on 20 cases with a different verifier model raised the first-place rate from 65% to 85%. The verifier in the product is a different model, and its measurement is part of the unfinished benchmark (draft PR #58: two draws are done, a third draw and a latency pass wait for account credit)
- Code database: NBC(AE) 2023, 2nd printing, 13,743 provisions, built by script from the official PDFs, with a 30-provision spot audit that found 0 mismatches

**Speaker notes:** A fabricated citation would sink an application, so the verifier and the lookup are the heart of this. We report the earlier public-precedent result with its limits, and we do not report an accuracy figure for the final pipeline because we do not have one yet.
*Sources:* [Alberta building codes](https://www.alberta.ca/building-codes-and-standards); `docs/research/2026-10-20-vision/README.md` §6; `codedb/README.md`

### Slide 6: It knows where to stop [Recommendations, 10]

**Hero:** 3 answers | required, depends, no

- Says when an engineer or architect is required, and why, when the facts support it
- Lists what Section D evidence must address. Never writes it
- Risk, mitigation and assumptions are the applicant's own words

**Full slide detail (in notes):**

- The professional-involvement check is deterministic over confirmed facts. Missing facts never produce "no". It cites the Division C rule when one applies, for example 2.4.1.1.(3) and 2.4.1.2.(1)
- The review screen shows an amber callout, "An engineer or architect is required for Section D", and the line "Batatis can list what that evidence must address, but it can't write it."
- The cards for rationale, risk assessment, mitigating measures, assumptions and limits, maintenance and qualifications say "You write this in your own words. Batatis never writes it for you."
- Section D lists evidence documents and the responsible person for each. The API also has a CCMC registry search that shows whether a product already has an evaluation, and no screen uses it yet

**Speaker notes:** Where no tested system fits, the tool says an engineer's judgment is needed and stops. It never writes the evidence, a test result or a professional opinion. The agreement figures for the flag are on slide 3 and carry the same limits.
*Sources:* `engine/professional.py`; `research/facts/professional-involvement.md`; `web/src/calm/Review.tsx`; `evals_dev/section_d_flag/RESULTS.md`

### Slide 7: Officers see gaps by section, never a verdict [Review, 10]

**Hero:** 16 | planted defect classes in the package review's tests (synthetic forms)

- Built: queue, claim, paper sheet, completeness list, messages, accept or return
- Backend: reads any SCC form with its attachments, drafts the information request, shows "x of y gaps resolved" after a re-upload
- No officer timing data exists

**Full slide detail (in notes):**

- Built: the officer creates an account, entering the authority's access code once, then signs in, sees the queue, claims an application, reads it as a paper sheet beside its completeness list, messages the applicant, and accepts it as administratively complete or returns it with a message
- Backend: the package review reads a fillable or flattened SCC form and its attachments. It tells a blank field (certain) from one it could not find (ask the officer). It lists named findings for the Division C 2.3.1.1 file items, drafts an information request in which every item is a question to the applicant, and keeps a close-out record. Its due date is 10 days after the decision, the rule before Dec 1, 2026. From Dec 1 the Council's portal rule applies (register at issuance or as soon as reasonably practicable after), and the record does not follow that timing yet. The officer sends or registers. Batatis never does
- Tests plant defects from 16 classes in synthetic forms. They were written alongside the checker and are not a blind evaluation
- No model is called anywhere in the package review

**Speaker notes:** The review lists administrative gaps. It does not say the design is acceptable. "Saves an officer time" is a target with a timing protocol, and we have no timing data.
*Sources:* `docs/api/package-review.md`; `docs/api/accounts-review.md`; `engine/tests/test_package_review_planted.py`; `docs/user-testing/officer-timing-protocol.md`

### Slide 8: One flow for three kinds of first-time applicants [General Applicability, 5]

**Hero:** 3 | applicant types: manufacturer, general contractor, homebuilder

- Onboarding sets the role, and the starting questions differ by role
- Every card says why it asks
- Unaided use by a real first-time applicant is untested

**Full slide detail (in notes):**

- Onboarding asks whether the person applies or reviews, and an applicant then picks the type that describes them best. A manufacturer sees "What is your product, and how will builders use it?" and others see "What are you building, and what do you want to do differently?"
- Three fictional demo cases (a manufacturer, a general contractor and a homebuilder) are test inputs for user sessions, not tool output (`evals/demo-cases/`)

**Speaker notes:** The aim is that nobody needs code fluency or prior variance experience. We have not tested that with a person, and the testing plan names the three first-time applicants we would recruit.
*Sources:* `web/src/calm/auth/onboardingSteps.ts`; `web/src/calm/Start.tsx`; `docs/implementation-plan.md` §7

### Slide 9: It fills the Council's current form and is built to travel [Usability and Portability, 10]

**Hero:** Oct 6, 2026 | form version the export is pinned to (SHA-256)

- Draft or official PDF. Part 2 and signatures stay blank
- Jurisdiction packs are data: Calgary, Edmonton, rest of Alberta
- Other provinces are labelled preview only

**Full slide detail (in notes):**

- The export fills Part 1, Sections A to D of the Council's form dated Oct 6, 2026 (5 pages, 87 fields), not the brief's older Appendix 1. The two differ in six places, listed in the Implementation Plan §4.3. A changed form fails the hash check and blocks export
- The official PDF unlocks only after a current check finds no required item missing. Drafts can be incomplete and say so
- A field shows N/A only when the applicant has confirmed that it does not apply, with a reason, and the appendix lists each one. A blank is never shown as N/A. There is no screen yet for stating it (backend)
- A pack is one JSON file with sources, dates and hashes for each note. A test adds a fourth pack with no code change. The Calgary form (R2014-06) is a roadmap item
- The code library reads the code as a numbered outline and shows a relevance ring on each article. "Add to my application" turns an article into a Code check card, and Section C holds only what the applicant confirms

**Speaker notes:** We caught the Council's October form revision and pinned the export to that exact file. Part 2 is the officer's. We never sign, declare or fill it.
*Sources:* `engine/export/field_maps/scc_2026-10.json`; `docs/api/jurisdictions.md`; [Council form](https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf)

### Slide 10: It fits the Dec 1 portal switch [Implementation Plan, 10]

- From Dec 1, 2026 the Council's portal is the only way to register a variance. Registration is not approval
- Any pilot would be with an accredited organization, not one officer
- Oct 29 Submission 1, Nov 26 Submission 2, Dec 1 Demo Day, then a Dec 2 to Mar 2 window (not guaranteed)

**Full slide detail (in notes):**

- The Council's six steps are Recognize, Pre-apply, Submit, Review, Decide and Close out. Batatis covers the applicant's side of the first three and the officer's side of the last three. The Implementation Plan §2 maps each step to a screen or a backend and gives its status
- Close out: before Dec 1, 2026 the authority sends the Council a copy of the variance within 10 days of issuance. From Dec 1 the SCO registers the variance in the portal at issuance or as soon as reasonably practicable after, with the supporting documentation. The close-out record lists what to send and keep and shows a 10-day due date. It does not follow the portal timing yet. The officer sends or registers. Batatis never does
- First user sessions are a protocol with targets, and none has run

**Speaker notes:** The Council says registration does not move responsibility for the decision. The officer still decides and still registers. Batatis prepares and checks. The Council invites high-volume organizations to build approved integrations, and we would do that only on its terms. No pilot partner has agreed to anything.
*Sources:* [IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf); [IB-2026-10-16](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf); [onboarding guide](https://edmontonunlimited.com/wp-content/uploads/2026/09/Built-World-Challenge-Onboarding-Guide.docx.pdf)

### Slide 11: Applicants pay to arrive complete [Business Plan, 10]

**Hero:** US$0.02 | model cost of one identification run (measured, draft benchmark ledger)

- First buyer: production homebuilders. Price to test: C$150 to C$750 a package (assumption)
- Alberta wedge: a C$0.9M to C$14M a year pool, of which Batatis could capture C$0.3M to C$7M (estimate)
- Defensible: jurisdiction packs, officer workflow, an exact core

**Full slide detail (in notes):**

- One identification run: screen US$0.0173, re-rank US$0.0006, verifier US$0.001 to US$0.0017. Total US$0.019 to US$0.020, or C$0.027 to C$0.028. One application with stated usage: US$0.05 (typical) to US$0.12 (generous). No other cost is priced, and hosting today is a free-tier demo
- Prices are hypotheses and no buyer has seen one. Seats for repeat filers: about C$2,400 a year (assumption). Authorities: no price, and pilots sized under C$75,000
- Pools (estimates): Alberta bespoke work C$0.9M to C$14M a year before capture. Canadian authority-side pre-check US$23M to US$50M a year if every application were covered
- The officer tier is free in Alberta. Calgary and Edmonton charge no variance fee, so the authority has no fee income to pay from

**Speaker notes:** Model cost is not what decides this business. Pack upkeep, support and distribution do, and we have not priced them. We do not claim a billion-dollar market. The sourced Alberta pool is C$0.9M to C$14M a year, and the share we could capture is at most single-digit millions. The plan says what would have to be true to grow beyond it.
*Sources:* `docs/business-plan.md` §5 to §7; `docs/research/2026-10-21-source-checks.md` §5

### Slide 12: We read the regulator's own data [X Factor, 5]

**Hero:** 69% | of Q1 to Q2 2026 building-article entries are three articles

- Caught the Council's Oct 6, 2026 form change
- Designed around three Council bulletins from the past year
- No person outside our team has used Batatis

**Full slide detail (in notes):**

- 9.10.15.5.(8) has 1,501, 9.10.11.2. has 366 and 9.10.13.13. has 251, which is 2,118 of 3,088 (our arithmetic). Coded rules for these three are roadmap
- Calgary reviewed and accepted 382 zero-lot-line requests between Jan 1 and Sep 1, 2017, then created standing posted variances
- No product in our competitor survey prepares or reviews alternative-solution applications. That is absence of evidence from web search on Oct 20, 2026

**Speaker notes:** Reading the Council's own data and bulletins is how we found both the form change and the concentration in one soffit article. This is a prototype. No applicant, officer or pilot partner has used it. Batatis checks completeness. The officer decides.
*Sources:* [Council Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/); `docs/research/2026-10-20-vision/C-market-provinces-business.md` §1.2 and §2.0
