# Build plan to 29 October: the vision, cut to what we can ship and prove

Date: 2026-10-20, revised the same day after two independent reviews (feasibility, judging), the checks listed under each section, and the deadline. Build window: Wednesday 21 October to Thursday 29 October 2026, the submission deadline (9 days). The full vision stays in [README.md](README.md) and is not reduced. This plan decides which parts of it we build now, which parts we build only if a gate passes, and which parts we show as the roadmap. Code citations are NBC(AE) 2023, 2nd printing only.

## The product we ship

An Alberta applicant describes an alternative solution in a sentence or two, or drops the files they already have. Batatis returns a complete Safety Codes Variance Template, Part 1, Sections A to D, filled into the official SCC form. Every code reference, attribution and fact links to its source, and nothing is filled by guesswork. A Safety Codes Officer opens the same case, or uploads any completed variance form with its attachments, and gets a one-screen completeness review with a drafted information request. For Part 9 houses and rowhouses, a builder can also open a site plan: Batatis turns it into an interactive site plan, flags the variances Alberta grants most often, and shows the standing package the city already accepts.

| Way in | For | What happens |
|---|---|---|
| **Describe it** | Any applicant: manufacturer, contractor, builder, designer, owner | Plain description plus any files → facts with sources → at most five questions → articles confirmed in plain language → Sections A to D → pre-flight → official form |
| **Open a site plan** | Homebuilders with Part 9 houses and rowhouses | Site plan → interactive site plan → flags for the most-varied articles → design fix, standing package, or variance |
| **Review an application** | Safety Codes Officers | A Batatis case, or any filled SCC variance PDF with attachments → completeness summary → information request → after re-upload, which gaps closed |

All three ways produce one case record, so every screen, check and export works the same way for all of them.

## How the two-week build keeps the whole vision

| Vision element | Two-week form | Comes next |
|---|---|---|
| Drop anything, type almost nothing | Drop PDFs (drawings, product literature, test reports, a filled SCC form) plus one sentence; at most five questions, each with a reason | DWG, IFC and RVT; scans and phone photos read automatically |
| Plan Twin | Site twin. On vector sheets, Batatis highlights the dimension strings it found and asks you to confirm which is which; on other sheets, two clicks set the scale and a few clicks mark lines. Limiting distance and soffit checks update live as you drag | Floor plans: walls, rooms, windows, doors, materials |
| Flags the officer would raise | Coded rules for 9.10.15.5.(8) to (10), 9.10.11.2.(2) and 9.10.13.13.(1): the three most-varied articles, 69% of Alberta's building-article variance entries in Q1–Q2 2026 | The 25 computable Part 9 checks in [B](B-drawings-interactive-acc.md), then Part 3 |
| Cheapest way out | Design fix, standing package (conditions checklists for Calgary SPV-001 and SPV-006, Edmonton B23-01), or full variance | Every Alberta standing package, kept current |
| Variance in about a minute | Built: Sections A to D, process fields, evidence plan, official form | Revisions and e-signature |
| Pre-flight and officer view | Built for applicants and officers, including uploaded third-party forms and their attachments | Permit-system integration, SCC registration |
| Anywhere in Canada | Alberta built on jurisdiction packs (Calgary, Edmonton, rest of Alberta) that are data, not code. Other provinces appear as labelled coverage | Province packs: SK and MB, BC, ON, Atlantic, QC, territories |
| Never confidently wrong | The core of the build: guaranteed and measured claims kept apart, abstention, an accuracy report | Error bounds per jurisdiction from 300 officer-labelled cases |
| Billion-dollar path | Pitch: wedge, buyers, cost per application, pilot, expansion | Unchanged ([C](C-market-provinces-business.md)) |

**One change from the vision's build order.** The vision built the drawing reader first. This plan builds the **Describe it** path first and the site twin behind a gate. The judges score intake and code identification across "varied application types" for manufacturers, contractors and homebuilders (40% of the score), and a manufacturer has no site plan. The Describe path also carries Recommendations and Review (another 20%), and its accuracy can be measured on held-out scenarios.

## Accuracy: what is guaranteed and what is measured

Batatis never types a fact; it points to one. Every value on screen is **exact** (from the code database or the form), **pointed** (a span the AI selected from the user's words or files, never generated), **computed** (code over exact and pointed values, formula shown) or **proposed** (AI judgement, shown with confidence and needing a click). Judges will trust the numbers only if the two kinds of claim below stay apart.

### Guaranteed by construction, tested in CI

1. Every citation is built from the database (`lookup().citation`) and passes the citation validator.
2. Section C values equal the attribution tables, checked against an independent re-extraction of the tables. The exported PDF shows the same text: a test renders the PDF and compares the extracted text.
3. Where a table has no row for the article (for example Article 9.10.14.2.), Section C says so. Where the national 2020 intent statement is attributed differently from NBC(AE) 2023 (64 provisions), Section C labels the difference.
4. No Section A or B value appears without a source. Export stays blocked while a required field is empty or a proposed item is unconfirmed.
5. Batatis never writes the officer's decision, the risk assessment or mitigating measures, or any statement that a design complies.

### Measured, can fail, reported as "x of y" with a 95% confidence bound

| Claim | Gate or target | Data |
|---|---|---|
| Committed article picks are right | At least 50 committed picks with at most 1 error (95% lower bound 91%); coverage reported; Part 9 and other Parts reported separately | Validation fold of the development set |
| A required article appears in the top 5 | Reported with its interval | Development set; held-out test split |
| Batatis asks instead of guessing | Asks or abstains on at least 90% of scenarios with key facts removed; 0 invented Section A or B values | Stripped copies of development scenarios |
| Professional involvement is flagged | Agreement reported; under-flagging reported on its own, target 0; 10 labels checked by an engineer or officer | Held-out test split |
| Review catches gaps | Every miss reported; half the planted defects written by an author who never saw the checker | 20 seeded applications |
| Drawing values, if candidate picking ships | Every auto-accepted value correct; every miss becomes a question | 2 real vector sets held out of development |
| Held-out test split | Run once, on day 7, and reported as is | 32 scenarios. Even 32 of 32 shows only 91% at 95% confidence |

### What today's data says, and what it changes

- **Accuracy splits by Part.** On our public benchmark, the Jev screen and rerank put the right article first for 20 of 24 Part 9 cases and 9 of 20 cases outside Part 9. The Sonnet 5.5 verifier did the same for 11 of 11 Part 9 cases and 4 of 7 outside Part 9 (recomputed 2026-10-20 from `jev-benchmark/`). Batatis therefore commits automatically only for Part 9 at first. For other Parts, it shows the top three as quoted choices that the applicant confirms in plain language: "The code says X. Does your design do Y instead?" Article numbers sit behind a disclosure. A Part gets automatic commits only when its validation numbers clear the gate.
- **The verifier result does not transfer yet.** It ran once, as a subagent reading files, with article text cut at 900 characters. Latency and cost were not recorded. Sonnet 5.5 and Opus 5.5 do not accept a temperature setting, so run-to-run variation must be measured with repeats. Gate G1 re-measures it as an API call with full text, five repeats, at medium and max effort.
- **The benchmark is smaller than it looks.** Two revision pairs leave 18 independent variance cases, not 20. Precedent matching must be evaluated leave-one-out by revision family, or it finds its own answer.
- **The development set needs new cases.** 76 of the 151 precedents have verified 2023 articles, and they already make up the 53 benchmark cases. An author agent writes about 60 new cases from the code, with at least 4 each for single-exit buildings, cladding and engineered walls (the challenge's examples), and Part 3 and 4 included. A second agent checks them and a person spot-checks 20.

### Keep the held-out set held out

- Move the 48 held-out scenarios out of the repository clone and out of `/tmp` into a judge-only folder. The judge runs as a separate process and prints only scores and error categories. The world-readable copy in `/tmp` was deleted on 2026-10-20. The rule applies to that folder, not to `evals/ui-artifacts` on `main`.
- Iterate on the 16 development scenarios. Run the 32 test scenarios once, on day 7, and report the result as is.

### What real drawings showed

A [probe on 2026-10-20](D-drawing-probe.md) measured 11 real applicant plan sets from public Calgary and Canmore appeal-board packages. In 9 of them, the site plan and the elevations carry dimension strings in the text layer, so "pick, never write" works. One set was raster images and one had its text converted to outlines. The City of Calgary's own sample drawings for garages, suites, basements and renovations are low-resolution images, and Edmonton's public agendas contain no applicant drawings. These packages hold designers' copyrighted drawings and neighbours' letters. They stay outside the repository as local test data and never appear in the demo. The demo uses a synthetic drawing set, or a builder's set shown with written permission.

## Scope

### Build: never cut

1. **Intake for any applicant type.**
   - A Describe screen: one text box and one drop zone.
   - Facts with pointers in a fact ledger; at most five questions, each with its reason.
   - Section A and B details (owner, address, legal description) in a separate panel, pre-filled from files and never invented.
   - Detects the acceptable-solution fork early: the applicant may not need a variance.
2. **Scope check.** Requests outside NBC(AE) 2023 (plumbing, fire code, energy, electrical) get a clear redirect.
3. **Code identification over all 2,080 Division B articles.**
   - Steps: Jev screen of every article (pinned model version) → one-request rerank → verifier with full text and word-for-word quote match → Part 9 commits, other Parts quoted choices.
   - The **benchmark acceptable solution** is defined as the quoted Division B sentence the design departs from, a one-line description of the departure, and its objective and function codes.
   - Every case also gets the process references Div A, Article 1.2.1.1. and Div C, Article 2.3.1.1.
4. **Section C by lookup.**
   - Sentence-level rows from the attribution tables.
   - Intent labelled "NBC 2020 Intent Statements, explanatory only".
   - Explicit "no row in the table" and "attribution differs" labels.
   - Day-one fix: the intent parser drops spaced brackets. 57 intent blocks are affected, 51 of them with a matching NBC(AE) attribution. Fix the parser, then audit every Division B row against an independent re-extraction.
5. **Alberta's most common variances as coded rules.**
   - Rules: 9.10.15.5.(8) to (10), 9.10.11.2.(2) and 9.10.13.13.(1), driven by intake facts.
   - Conditions checklists for Calgary SPV-001 and SPV-006 and Edmonton B23-01.
   - A checklist is never a determination. SPV-001, for example, has conditions on both houses and a registered agreement.
6. **Jurisdiction packs.** A schema plus data for Calgary, Edmonton, and the rest of Alberta: authority, process notes, forms and standing packages, including Edmonton's Point Access Block guide for single-stair buildings. Edmonton B14-01 cites the 2014 Alberta Building Code, so it appears only as historical.
7. **Section D evidence plan.**
   - Each row tied to the Section C objective and function it must address.
   - The confidence ladder and the alternative-path evidence types.
   - Professional-involvement rules from `research/facts/professional-involvement.md`.
   - A lookup in the CCMC Registry, which the organizers note has a JSON API, shows whether a product already has an evaluation.
   - It stops where professional judgement starts.
8. **Process fields: Batatis asks, the applicant writes.**
   - Rationale, risk assessment, mitigating measures, and assumptions and limits.
   - Maintenance and operation requirements: Div C, Clause 2.3.1.1.(2)(b).
   - Qualifications of the people responsible: Div C, Sentence 2.3.1.1.(4).
   - Batatis supplies prompts, structure and precedent examples, and never the content.
9. **Pre-flight and export.**
   - Fills the current SCC form, which the organizers' data package calls equivalent to the challenge appendix. Its Section B checkbox wording differs from the appendix, so the field map is version-keyed.
   - Fills the 50 applicant fields and skips officer, signature, button and help fields.
   - Flattened, so every viewer shows the same thing. The help pop-ups are hidden.
   - Long text goes to an appendix by default, because the Objective and Function boxes are about 92 by 16 points.
   - An override exports the official form marked DRAFT.
10. **Officer review.**
    - Inputs: Batatis cases, and uploaded SCC PDFs, fillable or flattened. Batatis tells "blank" (certain) from "not found" (ask the officer).
    - A supporting-documents panel: type, issuer, date, evidence rung, professional seal.
    - Verified citations, a Section C cross-check, and missing items.
    - A drafted information request.
    - After re-upload, a line such as "5 of 8 gaps resolved".
11. **Accuracy report.** A static page built from the evaluation runs: guaranteed claims, then measured ones with intervals, then boundary prompts. For example, asked to "say it complies", Batatis declines.

### Build if the gate passes: the wow

12. **Site twin.**
    - **Triage every sheet on upload.** Each sheet is classed as text usable, partial, outlined or raster, from its text layer, paths, images and rotation. Route per sheet, not per upload: every real set in the probe had some sheets that needed the fallback.
    - **Text-usable sheets: the model picks, never writes.** Batatis extracts dimension strings with their positions, pairs metric and imperial twins, and normalizes units and page rotation. The model returns only a candidate ID and a role (east side setback, stated limiting distance, eave projection, window size). You confirm by clicking the highlighted string on the sheet.
    - **Partial sheets get a visibility check.** Numbers visible on the render but missing from the text layer become "type or confirm". On one real site plan the only selectable "1.45m" strings were walkway widths.
    - **Outlined and raster sheets: trace mode.** Two clicks on a known dimension set the scale. Then mark property lines, street or lane centre lines, and building faces. Values are labelled "measured".
    - **Limiting distance follows the Div A definition.** It is measured at right angles to the face, to the property line, the centre line of a street or lane, or an imaginary line between buildings. Batatis compares it with the limiting distance designers often state on elevation sheets, and flags any difference.
    - **Soffit projection is often deferred** ("eaves: see architectural"), so Batatis asks for it instead of guessing.
    - **Rules and live what-if.** Div B, Sentences 9.10.15.5.(8) to (10) apply, and the flags update live as you drag a wall or change the soffit.
    - **Gate G2 decides candidate picking.** On 2 held-out real vector sets, Batatis must pick the right string for each side setback, the stated limiting distance and the eave projection, or ask, with no wrong auto-accepted value. Otherwise the twin ships in trace mode only.

### Keep in the vision, show as the roadmap

These appear in the pitch and as labelled coverage in the app, and are not built now:
- Other provinces and territories.
- Floor-plan twin; DWG, IFC and RVT; automatic reading of scans and photos.
- The full Part 9 checks and Part 3 drawing checks.
- NFC, NECB and NPC.
- Permit-system integration and SCC registration.
- Canadian data residency through a self-hosted open decision model.
- Professional sign-off marketplace.
- Calgary's own variance request form as a second export, and a limited Part 2 prefill for officers (cut for the 29 October deadline).

## Architecture: reuse first

| Part | Choice | Reuses |
|---|---|---|
| Engine | Python, FastAPI, one process; SQLite for cases | `codedb/` and the precedent index from branch `archive/local-main-2026-10-20`; the [benchmark scripts](jev-benchmark/scripts/) become the identify module |
| Code data | `codedb/build/codedb.sqlite`, read-only, rebuilt locally from the PDFs. Never committed or served publicly (NRC copyright) | Existing build: 13,743 provisions, attributions, intents |
| Decision model | Jev, pinned to a version (not `jev-latest`); client vendored into the repo | Measured harness: 0.42 s median per request, 0 errors |
| Verifier and drafting | Claude Sonnet 5.5; Opus 5.5 if it measures better | Progress streams to the screen, because max effort shows no thinking text |
| Drawing reader | pypdfium2 (character boxes, rendering) and pypdf (operators, images). PyMuPDF (AGPL) only in throwaway spikes | The probe's scripts in `/tmp/drawing-probe/scripts/` (sheet triage, string extraction with boxes, rotation transform, tiled rendering) |
| Form export | pypdf fills a version-keyed field map, then flattens; appendix PDF | `reference/guides/SCC-Variance-Form.pdf`; fill test passed 2026-10-20 |
| Web app | React, TypeScript, Vite; PDF.js page with an SVG overlay | The six screens in `evals/ui-artifacts/` (fix their known gaps: no rationale field, mitigating measures not gated, override saves a text file), `docs/design/tokens.css`, `smoke.mjs` |
| Model-call cache | Only for the scripted demo path. Evaluations and gate G5 bypass it | — |
| Hosting | Demo runs locally. A private deployment mounts the database privately. A skeleton deploys on day 3 | — |
| Keys | Anthropic, OpenAI and Jev keys live in a git-ignored `.env` that you fill in; agents never read or print them | `.env.example` lists the names |

## Schedule

**Capacity.** At most three Claude agents run at once. Codex returns on the evening of 24 October (day 4). Code roles run on Opus 5.5; UI is implemented and reviewed with Opus 5.5, following the project rule. Checkpoint every task: this project's first delegation round failed on Claude rate limits.

| Day | Engine | Web | Evals and data | You | Gate at the end |
|---|---|---|---|---|---|
| 1 (Wed 21 Oct) | Case schema and API; `codedb/`, precedents and facts into `main`; intent-parser fix and Section C audit | Describe screen mock; app shell | Judge-only folder; judge script; author agent starts about 60 development cases; planted-defect classes | Fill in `.env`; try the mock as a first-time applicant | — |
| 2 (Thu 22) | Identify service as API calls with full text; Section C rows | Port the intake, ranking and Section C screens with plain-language confirmation | Checker reviews the new cases; leave-one-out precedent index; drawing test sets, 2 held out | Spot-check 20 development cases for plain-language sense | **G1:** on the 53 public cases, leave-one-out: rerank MRR at least 0.70; verifier top-1 by Part with intervals over 5 repeats; latency and cost recorded |
| 3 (Fri 23) | Section D tied to codes; professional rules; CCMC lookup; process prompts; completeness checker | Describe flow end to end; skeleton deployed | Development run 1 (calibration fold); planted defects, half from an independent author | User session 1 with one of the Safety Codes Council experts you spoke to | — |
| 4 (Sat 24) | Official-form export: field map, flattening, appendix, render test | Pre-flight and export screens | Planted-defect run 1. Codex from the evening: coded rules, checklists, jurisdiction packs | Draft the deck and beta plan | **G3:** three demo cases, including BTRboard, export with every applicant field filled or marked not applicable, 0 validator errors and a passing render test |
| 5 (Sun 25) | Officer review: uploads, attachments panel, information request, re-upload diff | Officer screens | Codex: site twin, trace mode first | Write the planted-gap package for the officer demo | — |
| 6 (Mon 26) | Fixes from error analysis | Jurisdiction switch; accuracy report | Development run 2 (validation fold) and error analysis. Codex: candidate picking spike | Session 2: you, as a first-time applicant, on the live app | **G2:** candidate picking right or asking on the 2 held-out vector sets, with no wrong auto-accepted value; else trace mode only |
| 7 (Tue 27) | Thresholds fitted on the calibration fold, reported on the validation fold; **feature freeze at the end of the day** | Fixes from sessions; Opus 5.5 UI review | Held-out test run, once, reported as is | Officer session 2 if an expert is available | **G4:** at least 50 committed picks with at most 1 error on the validation fold; every guaranteed claim passes. If not, Batatis asks more and commits less |
| 8 (Wed 28) | Local demo build and private deployment | End-to-end tests for the three demo flows; P0 fixes only | Accuracy report regenerated from the final runs | Backup video; two rehearsals | **G5:** 9 of 10 uncached live runs of the three demo flows pass |
| 9 (Thu 29) | Buffer | Buffer | — | Final rehearsal; submit | — |

## Cut order if we fall behind

Cut from the top first:
1. Candidate picking on site plans. Keep trace mode.
2. The jurisdiction-switch animation. Keep the packs and labels.
3. Reading flattened forms on the officer side. Keep fillable forms and attachments.
4. The site twin entirely. Keep the coded rules, fed by intake questions.

Never cut the guaranteed claims, abstention, the required process fields, the official-form export, officer review, the jurisdiction packs, or the accuracy report. Without them the accuracy story fails.

## The six-minute demo

| Time | Scene | Scores |
|---|---|---|
| 0:00 | Cold open. Five Part 9 articles are 81% of Alberta's building-article variance entries, and one is 49%. Calgary created standing variances after 26 builders filed 382 separate zero-lot-line requests in eight months of 2017 | Business |
| 0:15 | **A manufacturer types a vague description of a continuous sheathing insulation product, like the organizers' BTRboard example.** Batatis asks instead of guessing, offers quoted choices in plain language, fills Section C with honest labels, ties the evidence plan to the codes, and stops at professional judgement. Export stays blocked until the presenter writes the risk assessment. The official form appears. A 20-second single-exit run shows range | Intake, Code ID, Recommendations, Applicability |
| 2:00 | **An officer opens the same case, then a package with planted gaps.** A 60-second review with the supporting documents, a wrong Section C pair caught, and the information request drafted. A re-upload shows "5 of 8 gaps resolved" | Review, Usability |
| 2:55 | **A builder opens a Calgary site plan.** A few clicks build the site twin. A wall at 0.30 m limiting distance under a projecting soffit flags Sentence 9.10.15.5.(8). Removing the soffit, or moving the wall past 0.45 m, clears it, and then Sentence (9) checks that the soffit face stays 0.45 m from the property line. Keeping the design shows the SPV-001 checklist. In Edmonton, with no current standing package, Batatis builds the full variance | X factor, Portability |
| 4:05 | **The accuracy report.** Guaranteed claims, then measured ones as "x of y" with intervals, Part 9 against other Parts, held-out run 1, and a boundary prompt declined | Intake evidence, Code ID |
| 5:00 | **Business, beta and the vision.** Buyers, cost per application, the pilot plan, and what user sessions changed. Swapping in a newer model and rerunning the evaluation shows the moat grows with better models. The concept page closes as "next, not built" | Implementation, Business, X factor |

Every demo case is our own; none comes from the held-out set. The scripted path can replay cached runs; live judge inputs stream their progress.

## Decisions settled on 2026-10-20

1. **Deadline:** 29 October 2026.
2. **Repository:** full access. `codedb/`, `research/precedents/` and `research/facts/` come into `main` through a pull request; the held-out set stays off GitHub in a judge-only folder.
3. **Keys:** Anthropic, OpenAI, Jev and Runware keys exist. You put them in the git-ignored `.env`.
4. **Data:** none beyond the public sources. The development cases are written from the code and checked; the drawing tests use public appeal packages kept outside the repository.
5. **Outreach:** not needed for the hackathon (advice from Safety Codes Council experts). NRC consent matters only if Batatis launches publicly; the pitch says so.
6. **Supplied material:** the organizers' data package is final. It names the current SCC form as equivalent to the appendix and lists BTRboard continuous sheathing insulation as the product worked example.
