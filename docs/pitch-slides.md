# Batatis: Pitch Slides

*Slide copy for Submission 1 (Oct 29, 2026), built from pitch-outline.md. Rubric weights are in brackets. Status labels: **on dev** (engine or screen merged), **[if merged: PR #N]** (in an open pull request), **not built** or **planned**. The end-to-end applicant flow (description → Section C → export in one screen flow) is **not built** yet; where a slide shows it, it is a **cached demo run**. Evaluation figures are model-checked, not human-verified.*

---

### Slide 1: Alberta's variance paperwork keeps bouncing back
- 1,553 / 1,698 / 1,713 building variances in 2019, 2021 and 2022
- Edmonton: about 67% of 2023 variances (all disciplines)
- No published service standard for variance review

**Speaker notes:** Every alternative solution in Alberta goes through the same Safety Codes Council form. Incomplete packages lead to repeated "more information" requests, which cost applicants and officers time. The 2023 count (837) was still partial when the Council published it, so we quote the full years.
*Sources:* [SCC Annual Report 2023](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/Annual%20Report%202023.pdf); [challenge scope](https://edmontonunlimited.com/wp-content/uploads/2026/09/Building-Codes-Challenge-with-Appendix-.pdf)

### Slide 2: Describe your project in plain words [Intake, 20]
- Your description becomes facts, each tagged with where it came from [if merged: PR #16]
- Designed so applicant and site details come only from you; upload isn't available yet
- Planned: "Not sure" becomes an open question instead of a dead end

**Speaker notes:** Intake is a fifth of the score, so we start with it. Batatis is designed to build Sections A and B from the applicant's description; today the engine lists what's missing and the end-to-end screen flow is not built. Anything it can't confirm, it is designed to ask about instead of filling in.
*Sources:* dev `engine/models.py`, `engine/completeness.py`; [PR #16](https://github.com/simplythatguy/batatis/pull/16)

### Slide 3: It asks before it guesses, and we test that [Intake, 20]
- Missing fields become plain questions, each tied to a form section (engine on dev; screen in review)
- 55/60 rules_only in-sample, and 7/8 blind pre-fix held-out (PR #8, not merged), model-checked.
- Accuracy across all applicant types: still to be measured

**Speaker notes:** The completeness check on dev names each missing field and the question to ask. The engineer-needed flag has two variants in PR #8: rules_only scored 55 of 60 on the in-sample dev set, and rules_plus_unknown scored 7 of 8 on a held-out set that was blind before a later fix; re-runs after that fix are not blind. All answer keys are model-checked, not human-verified, so treat this as an early signal.
*Sources:* dev `engine/completeness.py`; [PR #8](https://github.com/simplythatguy/batatis/pull/8)

### Slide 4: A ranked shortlist, measured against a named acceptable solution [Code Identification, 20]
- Ranked articles with a named benchmark acceptable solution [if merged: PR #12]
- You confirm departures; the exception is a narrow Part 9 auto-commit (p ≥ 0.75, at most 3 articles, uncalibrated)
- Section C objectives and functions are looked up from the code's tables (on dev)

**Speaker notes:** For the homebuilder's window, the benchmark acceptable solution is Sentence 9.9.10.1.(2): at least 0.35 m² unobstructed, no dimension under 380 mm, and the case's 0.312 m² opening is the departure. Showing each requirement beside the code text is the design; on today's screens that view is still being fixed, so in the demo it is a cached run. Ranking is command-line only on dev and moves to HTTP in PR #12, which also runs BM25 first, then an OpenAI rerank and verifier.
*Sources:* dev `engine/section_c.py`, `engine/identify/`; [PR #12](https://github.com/simplythatguy/batatis/pull/12); case C [if merged: PR #14]

### Slide 5: Every citation resolves, or it's dropped [Code Identification, 20]
- Built by script from the official NBC(AE) 2023; the 2nd-printing pin is in PR #12
- A citation that doesn't quote the code word for word is removed (on dev)
- Identification: C$0.0277 per case, 5.7 s median, 11.3 s p95 (measured, 20 dev cases × 3 repeats, identification step only (excludes the completeness judge and Section D))

**Speaker notes:** Hallucinated citations are the failure that would sink an application, so the verifier drops any citation whose quote doesn't match the code text. Each Section C row carries its article, objective and function from the attribution tables, so the rationale follows the code's own structure; the three demo articles were checked against our code database. Code identification: top-1 9/11 and recall@5 9/11 on the model-checked dev cases that have a gold article (in-sample, single run, 9 cases without gold excluded); the BM25 baseline gets 5/11; it asks the applicant on 40% of cases. These are dev cases, not real applications, and the models are aliases until they are pinned to dated snapshots in PR #12 (in progress).
*Sources:* [Alberta building codes](https://www.alberta.ca/building-codes-and-standards); Implementation Plan §9

### Slide 6: It knows where to stop [Recommendations, 10]
- Lists the evidence an alternative solution needs, in order (engine on dev; screen in review)
- Says when a registered professional is required, with the code reference (engine on dev)
- Never writes engineering judgment itself

**Speaker notes:** The professional-involvement check answers yes, depends or no and cites the rule. In the firestop demo case, plastic pipe in a 5-storey building needs firestops tested at a 50 Pa pressure differential (Clause 3.1.9.4.(4)(b)), and the tool is designed to say an engineering judgment is required where no tested system fits, list what it must contain, and stop. That case hasn't been run through the engine yet.
*Sources:* dev `engine/section_d.py`, `engine/professional.py`; [IFC engineering-judgment guidelines](https://firestop.org/wp-content/uploads/2024/03/Guidelines_Firestop_Engineering_Judgments_Rev2024-02.pdf); case B [if merged: PR #14]

### Slide 7: Completeness review: built in the engine, officer screen in review [Review, 10]
- Gaps listed by form section A–D; completeness only, never compliance (engine on dev)
- Officer screen with a drafted information request [if merged: PR #16]
- Div C 2.3.1 and one-location gates, portal package [if merged: PR #11]

**Speaker notes:** Today the A–D gap check and the export block with reasons run in the engine on dev; the officer screen isn't on dev yet. The bulletin gates and portal package are in a draft pull request, and portal registration is not approval: the officer still decides. Saving an officer time is a target with a planted-gap protocol to measure it; we have no timing data.
*Sources:* [IB-2025-11-18](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf); [IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf); dev `engine/completeness.py`

### Slide 8: One tool, three kinds of first-time applicants [General Applicability, 5]
- Homebuilder: slab edges need detailing, the unvented roof probably fails its STANDATA as drawn, the window needs a variance and fall protection [case files: PR #14]
- Manufacturer: product acceptance goes to CCMC; the variance stays project-specific [case files: PR #14]
- General contractor: plastic pipe needs 50 Pa-tested firestops, Clause 3.1.9.4.(4)(b) [case files: PR #14]

**Speaker notes:** Our three demo cases cover a homebuilder, a manufacturer and a general contractor, with fictional people and real code citations. The STANDATA reasoning (23-BCV-003 covers the under-slab insulation but not the edges; the roof is probably not covered by 23-BCV-017 as drawn) is case content; the tool's STANDATA "you may not need a variance" check is not built. Whether a real first-time applicant could use it unaided is untested.
*Sources:* [STANDATA 23-BCV-017](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/2aa7678c-c476-4523-b0c3-36e71256e11b/download/ma-standata-variance-building-23-bcv-017-2025-09.pdf); [STANDATA 23-BCV-001](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/01b622f0-f4a1-426d-b15f-ffc25e725949/download/ma-standata-variance-building-23-bcv-001-2024-04.pdf); [STANDATA 23-BCV-003](https://open.alberta.ca/dataset/08ac69ae-5639-46a3-83d2-c52246c78621/resource/3915ba54-96dd-4c54-a9c1-63df5c917836/download/ma-standata-variance-building-23-bcv-003-2024-05.pdf); [Calgary B23-014](https://www.calgary.ca/content/dam/www/pda/pd/documents/building/advisories/b23-014-new-products-materials-and-systems-in-building-construction.pdf)

### Slide 9: The current SCC form out, designed for any jurisdiction [Usability and Portability, 10]
- Fills the SCC form dated Oct 6, 2026 (5 pages, 87 fields), which supersedes the challenge's Appendix 1 (export from the engine; screen in review)
- Export blocked with reasons until gaps clear, or exported as a labelled draft (engine on dev)
- Designed so local add-ons are configuration; per-jurisdiction form registry in PR #12

**Speaker notes:** We caught the Council's October form revision and fingerprinted the export to that exact file, leaving the officer's Part 2 blank. Target: an AI-agent walkthrough that reaches a finished export on the current screens, reported as before → after; that re-run is pending, so we report no result yet. No real user has tested it.
*Sources:* dev `engine/export/field_maps/scc_2026-10.json`, `engine/export/scc.py`; [SCC form](https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf); [PR #12](https://github.com/simplythatguy/batatis/pull/12)

### Slide 10: Ready for December 1 [Implementation Plan, 10]
- From Dec 1, 2026, the SCC portal is the only way to register a variance, and registration is not approval
- The authority having jurisdiction is the organization, so we pilot with an organization
- Oct 29 demo → Nov 26 Canadian hosting → Dec 2 – Mar 2 pilot window (not guaranteed)

**Speaker notes:** The Council says registration in its portal is not approval and doesn't move responsibility for the decision. The SCO still decides and still registers; Batatis is designed to prepare the package they upload. The Council invites high-volume organizations to build approved integrations, and we'd do that only on its terms; no pilot partner exists yet, and we have contacted no one.
*Sources:* [IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf); [IB-2026-10-16](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf); [onboarding guide](https://edmontonunlimited.com/wp-content/uploads/2026/09/Built-World-Challenge-Onboarding-Guide.docx.pdf)

### Slide 11: Applicants pay to arrive complete [Business Plan, 10]
- First buyer: production homebuilders, who write the Div C 2.3.1 documentation
- Price to test: C$125–750 per bespoke package (untested hypothesis)
- Identification model cost: C$0.0277 per case, about 0.02% of the C$125 floor (measured on dev cases; identification step only)

**Speaker notes:** The low end of the range is one hour at the Council's own C$125/hour alternative-solution rate. No buyer has seen a price. Authority pilots would sit under the C$75,000 trade-agreement threshold that Edmonton and Calgary apply.
*Sources:* [draft PR #12](https://github.com/simplythatguy/batatis/pull/12) (keyed run, Oct 20, 2026); [SCC fee schedule](https://ebs.safetycodes.ab.ca/documents/webdocs/sr/council%20fee%20schedule%20asca%20v2.pdf); [Edmonton Procurement Standard](https://www.edmonton.ca/sites/default/files/public-files/Procurement%20Standard.pdf); [Calgary procurement policy](https://www.calgary.ca/buy-sell/supply-to-city/procurement-policy.html)

### Slide 12: We read the regulator's own data [X Factor, 5]
- 1,501 of 3,088 building article entries are one soffit article, 9.10.15.5.(8)
- Designed around three SCC bulletins from the past year
- No code-AI product we reviewed advertises officer-side alternative-solution review

**Speaker notes:** Reading the Council's own data and bulletins is how we found both the form change and the soffit concentration. The competitor claim rests on public product pages as of Oct 20, 2026, so it's absence of evidence, not proof. This is a prototype: no real user, officer or pilot partner has used it.
*Sources:* [SCC Data Hub](https://www.safetycodes.ab.ca/data-hub/variance-data/); Business Plan §7
