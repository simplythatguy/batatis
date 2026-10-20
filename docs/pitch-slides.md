# Batatis: Pitch Slides

*Slide copy for Submission 1 (Oct 29, 2026), built from pitch-outline.md. Rubric weights are in brackets. On every slide, the **Hero** line (one figure already on the slide, where there is one) and the `- ` bullets are the only on-slide text; the approved detail under **Full slide detail (in notes)**, the speaker notes and the full sources render into the speaker notes. On every slide the footer shows only public sources; PR references stay in the notes. Status labels in the detail: **on dev** (engine or screen merged), **[if merged: PR #N]** (in an open pull request), **not built** or **planned**; on-slide tags are plain words (in review, draft, model-checked, simulated session). The end-to-end applicant flow (description → Section C → export in one screen flow) is in review in PR #16, not yet on `dev` (it reaches the engine-filled form PDF; identification is still command line only); where a slide shows it, the demo uses PR #16's screens in review or a labelled still. A **cached demo run** is a recorded real model run for a seeded example case, replayed and labelled as such on screen instead of a live model call. Evaluation figures are model-checked, not human-verified.*

---

### Slide 1: Alberta's variance paperwork keeps bouncing back
**Hero:** 1,713 | building variances registered in Alberta in 2022 · SCC Annual Report 2023
- Edmonton: about 67% of 2023 variances (all disciplines)
- No published service standard for variance review

**Full slide detail (in notes):**
* 1,553 / 637 / 1,698 / 1,713 building variances in 2019–2022
* Edmonton: about 67% of 2023 variances (all disciplines)
* No published service standard for variance review

**Speaker notes:** A variance request goes to a safety codes officer of the reviewing authority; Batatis fills the Council's current form (Calgary's guide points applicants to its own attached Request for Specific Variance form). Incomplete packages lead to repeated "more information" requests, which cost applicants and officers time. The 2023 count (837) was still partial when the Council published it, so we quote the full years.
*Sources:* [SCC Annual Report 2023](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf); [challenge scope](https://edmontonunlimited.com/wp-content/uploads/2026/09/Building-Codes-Challenge-with-Appendix-.pdf)

### Slide 2: Describe your project in plain words [Intake, 20]
- Keeps your words; picks out a few facts
- The rest become questions (in review)

**Full slide detail (in notes):**
* Each fact carries a status and its source (engine on dev); reading facts out of your description is in progress (BAT-65, not built; PR #23, open, reads storeys, area and occupancy). On the in-review screens (PR #16 @27bec3e), only the storey count was read from a pasted description; the rest become questions
* Designed so applicant and site details come only from you; upload isn't available yet
* "Not sure" becomes an open question instead of a dead end (in review, PR #16)

**Speaker notes:** Intake is a fifth of the score, so we start with it. Batatis is designed to build Sections A and B from the applicant's description; today the engine lists what's missing, and the end-to-end screen flow is in review in PR #16, not yet on dev. Anything it can't confirm, it is designed to ask about instead of filling in.
*Sources:* dev `engine/models.py`, `engine/completeness.py`; [PR #16](https://github.com/simplythatguy/batatis/pull/16)

### Slide 3: It asks before it guesses, and we test that [Intake, 20]
**Hero:** 50/60 | in-sample · model-checked
- 27 unknowns sent to the applicant
- Held-out: 7/8 blind, 4/8 after a fix

**Full slide detail (in notes):**
* Missing fields become plain questions, each tied to a form section (engine on dev; screen in review)
* Engineer-needed flag (PR #8, on dev): rules_only 55/60 in-sample, 1 under-flag; shipped rules_plus_unknown 50/60 in-sample, 0 under-flags (on text-only cases it answers only yes or ask, never no, so 0 under-flags holds by construction), 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind); model-checked, not human-verified. (rules_only is the rules-only checker.)
* Accuracy across all applicant types: still to be measured

**Speaker notes:** The completeness check on dev names each missing field and the question to ask. The engineer-needed flag has two variants on dev (PR #8). The shipped variant, rules_plus_unknown, scored 50 of 60 on the in-sample dev set with 0 under-flags (on text-only cases it answers only yes or ask, never no, so 0 under-flags holds by construction) and 27 unknowns sent to the applicant, and 7 of 8 on a held-out set that was blind before a later fix, and 4 of 8 after that fix, which is no longer blind. The unshipped rules_only variant scored 55 of 60 in-sample. All answer keys are model-checked, not human-verified, so treat this as an early signal.
*Sources:* dev `engine/completeness.py`; [PR #8](https://github.com/simplythatguy/batatis/pull/8)

### Slide 4: A ranked shortlist, measured against a named acceptable solution [Code Identification, 20]
**Hero:** 0.312 m² | Example case · window opening vs 0.35 m² required
- Ranked against a named acceptable solution (draft, not in app)

**Full slide detail (in notes):**
* Ranked articles with a named benchmark acceptable solution [if merged: PR #12]
* In draft PR #12, identify never adds an article on its own: you confirm each one, and p ≥ 0.75 only sets a "suggested" hint (uncalibrated). Until #12 merges, the command-line tool on dev still auto-commits up to 3 Part 9 articles at p ≥ 0.75; no screen does.
* Section C objectives and functions are looked up from the code's tables where a row exists; otherwise the screen says the lookup is not available (on dev); the table stays empty until an article is added from Search, because identification is command-line only

**Speaker notes:** For the homebuilder's window, the benchmark acceptable solution is Sentence 9.9.10.1.(2): at least 0.35 m² unobstructed, no dimension under 380 mm, and the case's 0.312 m² opening is the departure. Showing each requirement beside the code text is the design; on today's screens that view is still being fixed, so in the demo it is a labelled still from PR #12 (not in this app build). Ranking is command-line only on dev and moves to HTTP in PR #12, which also runs BM25 (keyword search ranking) first, then an OpenAI rerank and verifier.
*Sources:* dev `engine/section_c.py`, `engine/identify/`; [PR #12](https://github.com/simplythatguy/batatis/pull/12); case C (PR #14, on dev)

### Slide 5: Citations come from the code database [Code Identification, 20]
**Hero:** 76% | right article first · 3-run mean · draft
- NBC(AE) 2023, 2nd printing · model-checked, 11 cases

**Full slide detail (in notes):**
* Built by script from the official NBC(AE) 2023; the codedb README on dev names the 2nd printing; the SHA-256 pin is in draft PR #12
* In the identify step (command line on dev; HTTP in draft PR #12), a citation that doesn't quote the code word for word is removed; app search shows database rows, and some article-level rows have no text yet
* Identification (draft PR #12; pinned 2025-04-14 models): C$0.027 per case, 4.5 s median, 9.1 s p95 (measured, 20 dev cases, mean of 3 repeats, identification step only (excludes the completeness judge and Section D))

**Speaker notes:** Hallucinated citations are the failure that would sink an application, so the identify step's verifier (command line on dev) drops any citation whose quote doesn't match the code text. Each Section C row carries its article, objective and function from the attribution tables (where the attribution table has a row; otherwise the screen shows that the lookup is not available), so the rationale follows the code's own structure; the three demo articles were checked against our code database. Code identification (draft PR #12, not on dev): top-1 0.758 and recall@5 (correct article in the top 5) 0.758 (MRR 0.761) on the 11 model-checked dev cases that have a gold article (mean of 3 repeats, in-sample, not human-verified; the 4 ask cases are scored separately, top-1 0.25 at most; 5 cases have no gold); the BM25 baseline gets top-1 0.455, and a 700-character verifier variant reaches recall@5 0.818; it asks the applicant on 42% of cases. These are dev cases, not real applications, and the models are pinned to dated 2025-04-14 snapshots in draft PR #12.
*Sources:* [Alberta building codes](https://www.alberta.ca/building-codes-and-standards); draft [PR #12](https://github.com/simplythatguy/batatis/pull/12) (keyed run, Oct 20, 2026; mean of 3 repeats); Implementation Plan §9

### Slide 6: It knows where to stop [Recommendations, 10]
**Hero:** 50 Pa | Example case · firestop test pressure differential
- Designed to say an engineer's judgment is needed, and stop
- Never writes the evidence

**Full slide detail (in notes):**
* Lists the evidence an alternative solution needs, in order (engine on dev; screen in review)
* The engine says when a registered professional is required, and cites the Division C rule (e.g. 2.4.1.1.(3), 2.4.1.2.(1)) when it applies (engine on dev; on screen, in review, no rule is shown, and a missing-facts answer reads "More facts are needed before this screen can say whether practice of engineering applies. This is not a licence decision.")
* Never writes engineering judgment itself

**Speaker notes:** Where no tested system fits, it's designed to say an engineer's judgment is needed, and stop. It never writes the evidence. The engine's professional-involvement check answers yes, depends or no, and the engine cites the Division C rule (e.g. 2.4.1.1.(3), 2.4.1.2.(1)) when it applies; on screen (PR #16, in review) no rule is shown, and when facts are missing it reads "More facts are needed before this screen can say whether practice of engineering applies. This is not a licence decision." In the firestop demo case, plastic pipe in a 5-storey building needs firestops tested at a 50 Pa pressure differential (Clause 3.1.9.4.(4)(b)), and the tool is designed to say an engineering judgment is required where no tested system fits, list what it must contain, and stop. A simulated general-contractor walkthrough of this case on an in-review build (PR #16 @27bec3e) reached a draft 8-page PDF (marked "DRAFT - not for submission") in about 6 minutes, but the final application PDF download stayed locked with 1 blocking item (professional involvement), which a contractor can't clear without a professional registration number or seal. Search found 3.1.9.4.(2)/(4)/(7) and 9.10.9.7 with the S115 text, but not 3.1.9.1; the app gave no variance-vs-fix guidance, didn't flag the sales-rep email as not an engineering judgment, and didn't challenge the sprinkler "exempt" claim.
*Sources:* dev `engine/section_d.py`, `engine/professional.py`; [IFC engineering-judgment guidelines](https://firestop.org/wp-content/uploads/2024/03/Guidelines_Firestop_Engineering_Judgments_Rev2024-02.pdf); case B (PR #14, on dev)

### Slide 7: Completeness review: built in the engine, officer screen in review [Review, 10]
**Hero:** A–D | gaps listed by form section
- Completeness only, not a compliance finding
- Officer screen in review

**Full slide detail (in notes):**
* Gaps listed by form section A–D; completeness only, never compliance (engine on dev)
* Officer screen with a drafted information request [if merged: PR #16]
* Div C 2.3.1 and one-location gates, portal package [if merged: PR #11]

**Speaker notes:** Today the A–D gap check and the export block with reasons run in the engine on dev; the officer screen isn't on dev yet. The bulletin gates and portal package are in a draft pull request, and portal registration is not approval: the officer still decides. Saving an officer time is a target with a planted-gap protocol to measure it; we have no timing data.
*Sources:* [IB-2025-11-18](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf); [IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf); dev `engine/completeness.py`

### Slide 8: One tool, three kinds of first-time applicants [General Applicability, 5]
**Hero:** 3 | fictional first-time applicants, real code citations
- Homebuilder, manufacturer, general contractor
- Unaided use untested

**Full slide detail (in notes):**
* Homebuilder: slab edges need detailing, the unvented roof probably fails its STANDATA as drawn, the window needs a variance and fall protection [case notes, not tool output; case files: PR #14, on dev]
* Manufacturers can seek a voluntary CCMC assessment (or another recognized evaluation) as evidence for the authority having jurisdiction, which makes the approval decision; a site-specific variance covers only that project [case notes, not tool output; case files: PR #14, on dev]
* General contractor: plastic pipe needs 50 Pa-tested firestops, Clause 3.1.9.4.(4)(b) [case notes, not tool output; case files: PR #14, on dev]

**Speaker notes:** Our three demo cases cover a homebuilder, a manufacturer and a general contractor, with fictional people and real code citations. The STANDATA reasoning (23-BCV-003 covers the under-slab insulation but not the edges; the roof is probably not covered by 23-BCV-017 as drawn) is case content; the tool's STANDATA "you may not need a variance" check is not built. Whether a real first-time applicant could use it unaided is untested.
*Sources:* [STANDATA 23-BCV-017](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/2aa7678c-c476-4523-b0c3-36e71256e11b/download/ma-standata-variance-building-23-bcv-017-2025-09.pdf); [STANDATA 23-BCV-001](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/01b622f0-f4a1-426d-b15f-ffc25e725949/download/ma-standata-variance-building-23-bcv-001-2024-04.pdf); [STANDATA 23-BCV-003](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/3915ba54-96dd-4c54-a9c1-63df5c917836/download/ma-standata-variance-building-23-bcv-003-2024-05.pdf); [Calgary B23-014](https://www.calgary.ca/content/dam/www/pda/pd/documents/building/advisories/b23-014-new-products-materials-and-systems-in-building-construction.pdf)

### Slide 9: Fills the current SCC form; built to travel [Usability and Portability, 10]
**Hero:** Oct 6, 2026 | SCC form version
- Unsigned, officer Part 2 blank (in review)
- Not a compliance finding

**Full slide detail (in notes):**
* Fills Part 1, Sections A–D of the Council's current SCC form (PDF last modified Oct 6, 2026), not the brief's older Appendix 1 template; same field names, differences listed in the Implementation Plan (the engine fills the SCC form; in the app, PR #16 in review, Check completeness opens a review, and Download application PDF gives it unsigned, officer Part 2 blank, once there are 0 blocking gaps)
* The engine blocks export with reasons until gaps clear, or returns a labelled draft (engine on dev; in the app (PR #16, in review), Check completeness opens a review and the official PDF stays locked until there are 0 blocking gaps; then Download application PDF gives the Council's October 2026 variance form, filled in by the engine, unsigned, officer Part 2 blank, with a notice that it is not a finding that the design complies; the review also offers Download draft PDF and Download text record)
* Designed so local add-ons are configuration; per-jurisdiction form registry in PR #12

**Speaker notes:** We caught the Council's October form revision and fingerprinted the export to that exact file, leaving the officer's Part 2 blank. A third AI-agent simulated walkthrough on PR #16 @d076aa2 did not reach export; a simulated re-run on PR #16 @579cd2c reached the engine-filled form PDF in about 6 minutes; the professional-involvement gap cleared on the simulated user's own answers, with no confirmed professional; one evidence item was lost. The fix is in PR #26 (open), which requires a confirmed professional before an issue lists evidence. The engine fills the SCC form; in the app (PR #16, in review), Check completeness opens a review and the official PDF stays locked until there are 0 blocking gaps; then Download application PDF gives the Council's October 2026 variance form, filled in by the engine, unsigned, officer Part 2 blank, with a notice that it is not a finding that the design complies; the review also offers Download draft PDF and Download text record. No real user has tested it.
*Sources:* dev `engine/export/field_maps/scc_2026-10.json`, `engine/export/scc.py`; [SCC form](https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf); [PR #12](https://github.com/simplythatguy/batatis/pull/12)

### Slide 10: Built for the December 1 rules [Implementation Plan, 10]
- From Dec 1, 2026: SCC portal only; registration is not approval
- Any pilot would be with an authority having jurisdiction (an organization)
- Oct 29 Submission 1 → Nov 26 build (our plan) → pilot Dec 2–Mar 2 (not guaranteed)

**Full slide detail (in notes):**
* From Dec 1, 2026, the SCC portal is the only way to register a variance, and registration is not approval
* The authority having jurisdiction is the organization, so any pilot would be with an organization
* Oct 29 Submission 1 (demo build) → Nov 26 Submission 2, pilot build in a Canadian region (our plan) → Dec 2 – Mar 2 pilot window (not guaranteed)

**Speaker notes:** The Council says registration in its portal is not approval and doesn't move responsibility for the decision. The SCO still decides and still registers; Batatis is designed to prepare the package they upload. The Council invites high-volume organizations to build approved integrations, and we'd do that only on its terms; no pilot partner exists yet, and we have contacted no one.
*Sources:* [IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf); [IB-2026-10-16](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf); [onboarding guide](https://edmontonunlimited.com/wp-content/uploads/2026/09/Built-World-Challenge-Onboarding-Guide.docx.pdf)

### Slide 11: Applicants pay to arrive complete [Business Plan, 10]
- Production homebuilders pay C$125–750 per package (untested hypothesis)
- Identification: C$0.027 per case, about 0.02% of the floor (draft, measured)
- Defensible as models improve: form tracking, citation validator, officer workflow

**Full slide detail (in notes):**
* First buyer: production homebuilders, who write the Div C 2.3.1 documentation
* Price to test: C$125–750 per bespoke package (untested hypothesis)
* Identification model cost (pinned models): C$0.027 per case, about 0.02% of the C$125 floor (measured on dev cases; identification step only)
* Defensible as models improve: form-version tracking, the Section C attribution layer with its citation validator, and a place in the officer's workflow (Judge Q&A 13)

**Speaker notes:** The low end of the range is one hour at the Council's own C$125/hour alternative-solution rate. No buyer has seen a price. Authority pilots would sit under the C$75,000 trade-agreement threshold that Edmonton and Calgary apply.
*Sources:* [draft PR #12](https://github.com/simplythatguy/batatis/pull/12) (keyed run, Oct 20, 2026); [SCC fee schedule](https://ebs.safetycodes.ab.ca/documents/webdocs/sr/council%20fee%20schedule%20asca%20v2.pdf); [Edmonton Procurement Standard](https://www.edmonton.ca/sites/default/files/public-files/Procurement%20Standard.pdf); [Calgary procurement policy](https://www.calgary.ca/buy-sell/supply-to-city/procurement-policy.html)

### Slide 12: We read the regulator's own data [X Factor, 5]
- Caught the Council's Oct 6, 2026 form change; export pinned to it
- 1,501 of 3,088 building article entries (Q1–Q2 2026): one soffit article
- Designed around three SCC bulletins from the past year

**Full slide detail (in notes):**
* Caught the Council's Oct 6, 2026 form change; export pinned to it
* 1,501 of 3,088 building article entries (Q1–Q2 2026) are one soffit article, 9.10.15.5.(8)
* Designed around three SCC bulletins from the past year
* No code-AI product we reviewed advertises officer-side alternative-solution review

**Speaker notes:** Reading the Council's own data and bulletins is how we found both the form change and the soffit concentration. The competitor claim rests on public product pages as of Oct 20, 2026, so it's absence of evidence, not proof. This is a prototype: no real user, officer or pilot partner has used it.
*Sources:* [SCC Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/); Business Plan §7
