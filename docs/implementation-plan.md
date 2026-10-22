# Batatis: Implementation Plan

*Building Codes Challenge, Submission 1 (Oct 29, 2026). Status is as of Oct 21, 2026, on `dev` at commit 054c632 and the live app at https://batatis-vert.vercel.app. Four status words are used. **Built** means merged on `dev` and reachable in the live app or API. **Backend only** means the API is merged and its screen is not finished. **In progress** means work on an open branch. **Roadmap** means not started, and it is never described as working. A result appears only where a file or a run backs it, with its limits next to it.*

## 1. Summary

Batatis fits into Alberta's variance process and replaces none of it. The applicant still files the Safety Codes Council's variance form. The safety codes officer (SCO) of the authority having jurisdiction still decides. From Dec 1, 2026 the SCO still registers the variance in the Council's portal. Batatis changes what arrives and what the officer sees first: an application that is complete, code-referenced and clear about what is missing, and a review view that lists administrative gaps without judging the design.

Batatis checks administrative completeness only. It never says that a design complies or is safe, never writes Section D professional evidence, and never fills an officer field.

**What a person can do in the live app today.**

- An applicant signs up, says whether they are a manufacturer, general contractor or homebuilder, describes the project, and answers one question at a time for Sections A to D. Batatis lists what is missing, looks up Section C from the code's attribution tables, and exports the Council's October 2026 form as a draft, or as the official PDF once no required item is missing. The applicant can submit the application to Calgary or Edmonton.
- An officer signs in with the authority's access code, sees a queue, claims an application, reads it as a paper sheet beside its completeness list, messages the applicant, and either accepts it as administratively complete or returns it with a message.

**What is merged but has no finished screen (backend only).** Intake extraction from the description and PDFs with a pointer to the source words, a planner that asks at most five questions, a flag for when no variance may be needed, scope redirects, code identification over all 2,080 Division B articles, jurisdiction packs, and the officer's package review (SCC form, fillable or flattened, with attachments; a deterministic information request; a re-upload diff; a close-out record). The screens for these are in progress.

**What is roadmap.** Coded rules for the three most-varied articles, standing-package condition checklists, the accuracy report page, the site twin, the Calgary form as a second export, Part 2 prefill for officers, other provinces, and any integration with the Council's portal.

**No person outside the team has used Batatis.** No pilot partner has agreed to anything, and no officer has seen the review screens. The testing in §7 is a protocol with targets, not results.

**Path.** The dates marked "program" come from the [Built World Challenge onboarding guide](https://edmontonunlimited.com/wp-content/uploads/2026/09/Built-World-Challenge-Onboarding-Guide.docx.pdf).

| When | What | Kind |
|---|---|---|
| Oct 21 to 26 | Finish the screens that use the intake, code identification, jurisdiction pack and package review backends. Feature freeze on Oct 26 | Our plan |
| Oct 27 to 28 | Record the demo video from `docs/demo/script.md`. Polish | Our plan |
| Oct 29 | Submission 1, the semi-final package. About 10 teams go to semi-finals | Program |
| Nov 10 | Semi-final presentations. Up to 5 teams go to finals | Program |
| Nov 10 to 26 | Build and refine with coaches. Finish the code identification benchmark. Start the first user sessions if a sponsor engages | Our plan |
| Nov 26 | Submission 2, the final package | Program |
| Dec 1 | Demo Day. Portal registration becomes the only route for variances | Program and Council |
| Dec 2 to Mar 2 | Implementation in a customer environment. The guide says this is "not guaranteed" | Program |

## 2. Terms and the officer workflow

### 2.1 Terms

The Council's hackathon presentation ("Alternative Solutions Under Alberta's Objective-Based Codes", Adam Salkeld, Safety Codes Council) separates two things that people often treat as one. Batatis keeps them apart in the product and in every document.

| Term | What it is | Test applied | Authority | Who issues or prepares it |
|---|---|---|---|---|
| Variance (the "request for variance" half) | The legal authorization to deviate from a code requirement | Approximately equivalent or greater safety performance, which is the wording of Part 2(a) of the Council's form | Safety Codes Act, s.38 | An administrator or SCO, who may set conditions. A refusal is written and an applicant can appeal an SCO's refusal to the Council within 30 days |
| Alternative solution | The proponent's technical evidence that the design performs as well as the acceptable solution | At least the minimum level of performance Division B requires in the objectives and functional statements attributed to the acceptable solution (NBC(AE) Division A, Clause 1.2.1.1.(1)(b), documented under Division C, 2.3.1) | NBC(AE) Division C, 2.3.1 | The proponent, usually a design professional. It is not a decision |
| Accepted variance | A request for variance plus an alternative solution, accepted by the officer | Both tests above | Safety Codes Act, s.38 | The officer. Compliance with a variance is deemed to be compliance with the Act (s.40(2), as the presentation quotes it) |
| Acceptable solution | The Division B requirement the design departs from. Batatis calls it the benchmark | | | |

Batatis helps prepare both halves and helps the officer check that both are present. It does not issue, accept or refuse either half. The test is equivalence, "as well as" and not "well enough". The Division A text, from the code database for the 2nd printing (PDF p.38), reads: "using alternative solutions that will achieve at least the minimum level of performance required by Division B in the areas defined by the objectives and functional statements attributed to the applicable acceptable solutions".

Sources: the presentation (slides 4 to 8); `engine/data/jurisdictions/provinces/AB.json`, notes `ab-who-requests` and `ab-appeal`; `codedb/README.md`.

### 2.2 The Council's six steps and where Batatis sits

| Step | What happens (Council presentation) | Applicant in Batatis | Officer in Batatis | Status |
|---|---|---|---|---|
| 1. Recognize | The designer flags the conflict with the code | Describe the project in plain words. Backend: a fork flag says whether a variance looks likely, not indicated or unknown, and a scope check redirects questions that belong to another code (plumbing, fire, energy, electrical, gas, private sewage) | None | Describe screen built. Fork flag and redirects backend only |
| 2. Pre-apply | The designer meets the authority and emergency services early | A "before you submit" note with the authority's name and contact and any emergency-services guide, from the jurisdiction pack | None | Backend only |
| 3. Submit | The variance form and supporting documents go in with the permit application | Part 1 Sections A to D one question at a time. Section C by lookup. A Section D list of what the evidence must address. A review of what is missing. Draft or official PDF. Submit to Calgary or Edmonton | The application appears in the authority's queue | Built |
| 4. Review | The SCO reviews. Peer review if the risk is high | Answers the officer's questions | Queue, claim, paper sheet, completeness list and messages are built. The package review of the SCC form and attachments, with a drafted information request and a "peer review may be warranted" signal for the officer only, is backend only | Built and backend only |
| 5. Decide | Accept, refuse, or ask for more information | Reads the officer's message, fixes the items and resubmits | Accept as administratively complete, or return with a message (built). A drafted information request posts to the applicant's thread (backend only). Refusal is not in Batatis: the officer's written reasons and the 30-day appeal notice stay in the authority's own process | Built, backend only and roadmap (refusal) |
| 6. Close out | The authority sends a copy of the variance to the Council within 10 days. From Dec 1, 2026 the SCO registers it in the Orders and Variances Portal | None | A close-out record shows a due date 10 days after the decision and lists what to send and what to keep. The officer records that the copy was sent. Batatis sends and registers nothing | Backend only |

The presentation also lists where practice varies: requirements differ by discipline, small buildings may not need a professional, and Alberta has no set peer review procedure. Batatis answers the first two with a professional-involvement check that says "required", "depends" or "no" and says when facts are missing. It answers the third with a signal to the officer, not a finding.

### 2.3 What the file must contain, and what Batatis checks

The presentation lists what a Division C, 2.3.1 file must contain. The package review turns each item into a named finding when the item is absent. It checks presence only and never adequacy. The Division C and "demonstrate, don't assert" checks are keyword presence checks, so a passage worded differently can show as "not found", and the officer resolves it.

| Item in the file | Division C reference | Check in the package review |
|---|---|---|
| Code analysis and attributions | 2.3.1.1.(3) | Section C rows are present, each article exists in the 2nd printing, and each objective and function pair matches the Division B table |
| Assumptions, limits, testing | 2.3.1.1.(3) | Assumptions and limits, and testing procedures, are present. The review also asks when failure conditions, lapsed maintenance or emergency-response assumptions are not mentioned |
| Qualifications of the people responsible | 2.3.1.1.(4) | Qualifications are present, and a responsible person is named for each Section D document |
| A single co-ordinator | 2.3.1.1.(6) | A co-ordinator is named when more than one person or firm takes responsibility |
| Maintenance, operation, commissioning | 2.3.1.1.(2)(b) | Present or absent |

Source: `docs/api/package-review.md`. The sentence numbers were checked in the code database on Oct 21. Division C, 2.3.1.1.(2)(b), (3), (4) and (6) are on PDF p.739.

## 3. State of the product on Oct 21

| Area | What exists | Status | Evidence |
|---|---|---|---|
| Accounts and workflow | Sign-up and sign-in (password, plus Google or Microsoft where configured). Onboarding as an applicant (manufacturer, general contractor or homebuilder) or as a reviewer with the authority's access code. Application list, notifications, settings, an assistant | Built | `web/src/calm/`, `docs/api/accounts-review.md` (PR #48, #49) |
| Applicant deck | Describe. One-question cards in form order: check what we read, code check, reviewing authority, Section A and B fields, the applicant's own rationale, risk, mitigation, assumptions, maintenance and qualifications, then Section D. Review and application sheet | Built | `docs/design-system-calm.md` |
| Code library | Browse NBC(AE) 2023, 2nd printing, with a relevance estimate for the project on each article and a structured reader. The estimates are not Section C and not compliance | Built | PR #56 |
| Section C | Looked up from the code's attribution tables. The screen says so when the table has no row for a sentence. NBC 2020 intent statements are shown as explanatory only | Built | `codedb/README.md` |
| Official SCC form | The October 2026 form (5 pages, 87 fields). The field map is pinned to the form's SHA-256. Draft and official PDF. The official PDF is blocked, with reasons, while a required item is missing. Part 2 and signatures stay blank | Built | `engine/export/field_maps/scc_2026-10.json`, `docs/deploy.md` |
| Submit and review workflow | Submit to Calgary or Edmonton, queue, claim and take over, accept or return, messages, notifications | Built | `docs/api/accounts-review.md` |
| Intake extraction | Reads the description and text PDFs. Every fact points at the words it came from. At most five questions, each with a reason. "Not sure" never blocks. Fork flag and scope redirects | Backend only | `docs/api/intake.md` (PR #54) |
| Code identification | Screens all 2,080 Division B articles, re-ranks the top 60, and has a verifier read the full text of the top 15 and quote it word for word. Offers up to three quoted choices. Commits nothing automatically. Labelled keyword fallback when a model stage is unavailable | Backend only, benchmark unfinished | `docs/api/identify.md` (PR #52), draft PR #58 |
| Jurisdiction packs | Calgary, Edmonton and the rest of Alberta, as data. Coverage labels for the other 12 provinces and territories (preview) | Built as data and API. Picker and process-notes screen in progress | `docs/api/jurisdictions.md` (PR #51) |
| Officer package review | Reads a fillable or flattened SCC form and its attachments. Findings, a documents panel, a deterministic information request, an "x of y gaps resolved" diff after a re-upload, a close-out record | Backend only | `docs/api/package-review.md` (PR #53) |
| Privacy and spend | Recognizable personal details are removed before any AI call. Cases and files are deleted after 7 days. A daily spend cap and per-IP limits apply | Built | `docs/deploy.md`, `engine/redact.py`, `engine/llm_gate.py` |
| Automated tests | On `dev` at 054c632, CI ran 1,698 tests (5 skipped) over the engine, the code database and the key-free evals. The web typecheck, build and UI smoke test passed | Built | GitHub Actions run 39720990321 |
| Roadmap | Coded rules for 9.10.15.5.(8) to (10), 9.10.11.2.(2) and 9.10.13.13.(1). Standing-package checklists. Accuracy report page. Site twin. Calgary form export. Part 2 prefill. Other provinces. Portal integration | Roadmap | `docs/research/2026-10-20-vision/2-week-build.md` |

## 4. How it fits current workflows and rules

### 4.1 Authority by authority

Each office keeps its own intake. Batatis holds these differences as data in a jurisdiction pack, not in code. Every note below comes from `engine/data/jurisdictions/packs/`, where each note carries its source URL, the date it was fetched (2026-10-21) and the file's SHA-256.

- **Calgary.** A variance is tied to a building permit and is site specific. The owner or agent discusses it with an SCO first, then submits the City's own Request for Specific Variance form with the supporting documents, and the City asks for stamped and sealed documents where a professional is needed. Calgary also issues Standing Posted Variances, such as SPV-001 (zero lot line) and SPV-006 (firewall in a rowhouse with secondary suites), that cannot be altered. Batatis exports the Council's form. The Calgary form is a roadmap item.
- **Edmonton.** The pack found no Edmonton-specific variance form in the City sources it reviewed, so the Council's form is used. Designs outside the acceptable solutions are considered building by building. Alternative solutions that may affect emergency services go through a joint review with Fire Rescue Services. A City policy such as B23-01 is used with a signed Letter of Construction Intention in place of a request. A single-exit-stair building needs an alternative solution prepared by a qualified fire protection or life safety consultant.
- **Any other Alberta office.** The fallback pack gives the provincial process notes and says that each accredited office may have its own intake, so the applicant should confirm it with the officer.

### 4.2 The Council's bulletins

Three Council bulletins set the rules that Batatis is designed around. The quotations below were checked against the Council's PDFs on Oct 21, and each file matched the SHA-256 recorded in the pack.

| Bulletin | Clause | How Batatis responds | What Batatis will not do | Status |
|---|---|---|---|---|
| [IB-2025-11-18](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2025-11-18%20Mandatory%20Documentation%20of%20Variances.pdf), Mandatory Documentation of Variances | "Building, fire, and plumbing: Document alternative solutions as required by Division C of the applicable code." And: "Submit a copy of each variance to the Safety Codes Council within 10 days of issuance." | The package review lists the Division C 2.3.1.1 file items that are absent. The close-out record shows the 10-day due date | Judge whether the documentation proves equivalence. Send anything to the Council | Backend only |
| [IB-2026-10-01](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-01%20Orders%20and%20Variances%20Registration%20Changes.pdf), Orders and Variances Registration Changes | "All variances must be registered individually, for a specific location, including those relying on jurisdictional alternative solutions." "The revised variance form must be completed and included when the variance is registered through OVP." "Only SCOs will have access to register variances and orders in OVP." | The export fills the revised form. The close-out record lists what to send and what to keep | Register anything or log in to the portal. Imply approval: the bulletin says registration "does not constitute Council approval" | Export built. Close-out record backend only. Portal integration roadmap |
| [IB-2026-10-16](https://ebs.safetycodes.ab.ca/documents/webdocs/SR/IB-2026-10-16_AHJ_Clarification.pdf), Clarifying Authority Having Jurisdiction | "Authority Having Jurisdiction rests with accredited organizations and the Alberta Safety Codes Authority." "SCOs do not supersede or replace the AHJ established under the Act." | Each application records its receiving authority. Reviewer accounts belong to an authority and its access code. A pilot would be agreed with the organization, not with one officer. Part 2 stays blank | Act as or speak for the authority having jurisdiction. Decide acceptance or refusal. Pressure an officer: the bulletin names directing an SCO to issue a variance "based on anything other than an administratively compliant alternative solution" as undue influence | Built |

From Dec 1, 2026 the legacy e-mail copy ends. The bulletin says variances must be registered in the portal "at the time of issuance or as soon as reasonably practicable thereafter", with the supporting documentation the SCO used. The bulletin also invites high-volume organizations to "work with the Council to develop automated interfaces, integrations, or other approved solutions". Batatis would build such an interface only with a partner authority and on the Council's terms.

**Update runbook (roadmap).** The Council changes forms and bulletins quickly: the variance form changed on Oct 6, 2026, and three bulletins date from the past year. The runbook will check the Council's bulletin index and the form's SHA-256 weekly and before every release, classify each change (none, wording, new check, new form), update the check or the field map with a test that plants the new gap, and record the bulletin id and form hash against each case. A hash mismatch already blocks export of the affected form.

### 4.3 Export target: the current Council form, not the challenge brief's Appendix 1

The brief asks for an export that matches Appendix 1. The Council has since replaced that template with the form dated Oct 6, 2026 (5 pages, 87 fields), and IB-2026-10-01 says the revised form "must be completed and included" at registration. An application on Appendix 1 would have to be re-keyed before an officer could register it, so Batatis exports the revised form. Part 1 has the same four sections on both. The differences, read from the two forms:

| Appendix 1 (challenge brief) | Council form dated Oct 6, 2026 | Handling |
|---|---|---|
| Section B checkbox: the alternative "is for a Jurisdiction and is not site-specific" | The alternative "has been submitted to the Safety Codes Council for review for jurisdictional use" | Mapped to the new meaning |
| Section D: one combined field for the document and the responsible person | Two columns, document and responsible person | Mapped to the two columns |
| Privacy block: collection under section 4(c) of the Protection of Privacy Act, a list of fields the Council may publish, an acknowledgement checkbox, and a declaration of "equal or better performance" above the signatures | Collection still cites section 4(c). Sharing with the Council cites section 13(1)(b), and only "non-personal information" may be published. No checkbox and no performance declaration in Part 1 | Printed names are mapped. Signatures and any declaration are left for the owner |
| Part 2(a): "equal or better performance" | "approximately equivalent or greater safety performance" | Part 2 is left blank for the officer |
| Part 2(b): refusal reasons use "equal or better performance" | The same reasons use "approximately equivalent or greater safety performance" and add a line recording how the refusal was served | Left blank |
| Part 3: appeal within 30 days "the Written Notice was served in person" | Appeal within 30 days of the date the refusal "was served" | Left blank |

The filled PDF is the 5-page form plus an appendix. The appendix length depends on the case: the synthetic sample in the Oct 20 checkpoint (`docs/research/2026-10-20-vision/build-checkpoint.md`) has ten appendix pages. An Appendix 1 export would be a second field map plus a rendered overlay for Section C. It is roadmap, to be built only if the judges ask for it.

### 4.4 Integration, in three phases

1. **Pilot with nothing to install (built and in progress).** The authority's officers use the web app. Applicants arrive by link. The officer queue, the paper sheet, the messages and the accept or return decision are built. The package review and close-out screens are in progress. The package review also accepts any completed SCC form with attachments, so an officer can use it on an application that was not made with Batatis.
2. **Next (roadmap): a documented API with webhooks.** A permitting system could push applications and pull completeness results. The research notes name POSSE and Cloudpermit as the systems a reviewer tool must work with (`docs/research/2026-10-20-vision/C-market-provinces-business.md`, §5.2).
3. **Later (roadmap): a portal interface agreed with the Council.** After the Council publishes its integration requirements.

### 4.5 Adding an office

A pack is one JSON file that the loader checks against a generated schema. It holds the authority, process notes, forms, standing packages, guides and notices. Every claim in it carries a source (title, URL, retrieval date, SHA-256) or is marked `unverified` with a reason. The engine needs no code change, and a test adds a synthetic fourth pack and shows the behavior changing. A lint test fails if the engine code names Calgary or Edmonton outside the data and test folders (`docs/api/jurisdictions.md`).

That is how Batatis reaches the 433 accredited organizations the Council lists (`docs/research/2026-10-20-vision/C-market-provinces-business.md`, §2.0): the fallback pack serves any office without its own pack, and an office gets its own pack when a pilot starts there. Two limits apply today. Reviewer accounts exist only for Calgary and Edmonton, because the account type lists those two authorities (a documented exception in `docs/api/jurisdictions.md`), and the in-app submit list has the same two. We have not measured how long a new pack takes. The three existing packs were built in one work package (PR #51).

Other provinces appear as labelled coverage ("preview": neither the adopted code nor a pack) and nothing more.

## 5. Architecture, models, hosting and data handling

**Components.** A FastAPI engine and a React and Vite web app, served from one Vercel project. Cases and accounts are stored in PostgreSQL (a Neon database in the US East region, `iad1`). The code database is a read-only SQLite file built by script from the official NBC(AE) 2023 PDFs, with every source checked against a SHA-256. The PDFs and the database are never committed. It holds 13,743 provisions, including 2,080 Division B articles, and 9,810 attribution source rows (`codedb/README.md`). The Division B attribution table has a row for 72.1% of the sentences in the parts that have a table, so the screens say so when a lookup has no row.

**What is exact and what uses a model.**

| Part | Uses a model | How it is controlled |
|---|---|---|
| Code text, citations, Section C attributions, edition, form export, completeness checks, officer package review | No | Deterministic code over the code database. The package review calls no model anywhere |
| Relevance estimate and code identification screen and re-rank | Yes, a third-party relevance model, pinned to one version and shown to users only as `relevance-1` | The estimate orders candidates. It is not a code determination |
| Code identification verifier | Yes, a third-party language model | It must quote the article word for word. A quote that is not in the article's text is dropped and counted. The pipeline checks again before display |
| Intake model pass | Yes, the same class of model | It is asked only for fields the rules left empty and cannot change a rule's value. A quote not found in the source is dropped |
| Assistant | Yes, a third-party language model | Signed-in users only. Answers use the application's own facts and verbatim code text. Article ids that do not exist are replaced with "[unknown reference removed]". Verdict words trigger conservative help text |

**Controls that apply to every model call.**

- **Redaction.** Names, contact details and addresses the system recognizes are removed before text leaves for an AI provider (`engine/redact.py`). It recognizes known case values, account names, contact phrasing, email addresses, phone numbers, street addresses and postal codes. An unrelated name typed with no context can still pass, which is why the notice says "recognizes".
- **Spend.** Each call reserves its worst-case cost before it runs and settles with the reported tokens afterwards. A daily cap (default US$5) is kept in the shared PostgreSQL ledger, and per-IP limits apply. When the gate is shut, identification falls back to labelled keyword search and commits nothing.
- **Offline path.** With no live provider, the app still runs. Results carry a label such as "Ranked by keyword search because scoring was unavailable. Nothing is committed."
- **Retention.** A case and its files are deleted 7 days after creation, or sooner on request. Package review sessions follow the same rule. Accounts are kept.
- **Access.** A matrix test covers the owner, another applicant, a same-authority reviewer, an other-authority reviewer and an anonymous caller on every case route. Passwords use scrypt. Session tokens are stored only as SHA-256 digests (`docs/api/accounts-review.md`).

**Hosting and residency.** The demo runs on Vercel with the database in the US East region. Third-party AI providers process text in the United States. Both are acceptable for a demo that uses example data. Neither would be acceptable for a pilot that handles real applicants' information without the organization's approval. For a pilot we plan to move the database and storage to a Canadian region, send only code text and redacted facts to any model, and keep the keyless path available. A pilot partner's privacy review decides whether the model path is allowed. Private applicants fall under Alberta's PIPA, which the federal Privacy Commissioner treats as substantially similar to PIPEDA. PIPEDA can still apply to a disclosure across provincial or national borders, case by case (`docs/research/2026-10-21-source-checks.md`, §2b). Municipalities fall under the Protection of Privacy Act, which has been in force since June 11, 2025 (`docs/research/2026-10-20-vision/C-market-provinces-business.md`, §5.2).

## 6. Path to beta

### 6.1 Milestones

| When | Engineering | Evidence we will produce | Program |
|---|---|---|---|
| Oct 21 to 26 | Screens for intake (read and confirm, the five questions, fork and scope notices), code identification (quoted choices and the benchmark acceptable solution), the jurisdiction picker and process notes, and the officer package review (findings, information request, diff, close-out). Official PDF closure | Browser run of the whole applicant and officer flow with screenshots that we inspect. CI green | |
| Oct 27 to 28 | Demo video and polish | | |
| Oct 29 | | | Submission 1 |
| Nov 10 | | Finish the code identification benchmark: a third relevance-model draw and the latency pass need account credit. Then fix the pipeline and calibrate the commit rule | Semi-finals |
| Nov 10 to 26 | Coded rules for the three most-varied articles and the standing-package checklists for Calgary SPV-001, SPV-006 and Edmonton B23-01, each needing a code or domain reviewer. The accuracy report page. Canadian-region hosting. Officer onboarding for a pilot authority | First sessions with applicants and officers, only if a sponsor engages | Submission 2 on Nov 26 |
| Dec 1 | Pilot-ready build with monitoring of ask rate, override rate and dropped-quote rate | Pilot agreement in principle with one accredited organization (a target) | Demo Day |
| Dec 2 to Mar 2 | Pilot support. Weekly review of officer overrides. Re-calibrate thresholds | Pilot success criteria in `docs/pilot-adoption-plan.md` | Implementation window, not guaranteed |

### 6.2 What decides whether code identification is ready for a beta

The benchmark harness is in draft PR #58. It holds the frozen datasets and folds, the ledger of spend, and two complete draws of the relevance stage for 139 cases. It does not yet have a third draw, the latency pass, the decision memo or the pinned pipeline file. The commit policy therefore stays at its safe default: with no calibration file on `dev`, nothing is committed automatically, and every article is a candidate or one of up to three quoted choices. A beta needs, at least, a calibrated rule for Part 9, a measured result on cases that were not used to tune anything, and a stated error bound. Until then the product asks and quotes, and the applicant decides.

## 7. Testing with users: how it will shape the design

### 7.1 Evidence so far

No person outside the team has used Batatis. The evidence below comes from automated tests and agent-run checks. It is internal and model-checked, and none of it is a human verification.

| Evidence | Result | Limits |
|---|---|---|
| CI on `dev` at 054c632 | 1,698 tests passed, 5 skipped (engine, code database, key-free evals) | Tests show the code behaves as written, not that it is right |
| Intake rules on 60 development cases (`python -m evals_dev.intake_facts.score`, run on Oct 21) | Typed-fact precision 159/159 and recall 159/162 | In sample: the labels were written while the rules were written. Cases are agent-authored and model-checked |
| Engineer-needed flag on the same 60 cases (`evals_dev/section_d_flag/RESULTS.md`) | The shipped variant agrees with model-written labels on 50 of 60 cases and sends 27 to the applicant as unknown | It never answers "no" on these text-only cases, so zero under-flags holds by construction. In sample. Not human-verified |
| Planted defects in officer review (`engine/tests/test_package_review_planted.py`) | Defects from 16 classes (D01 to D16), planted in synthetic fillable and flattened SCC forms, are named by the review, and the information request asks the applicant | Written alongside the checker, on synthetic forms. Not the blind 20-application test in `evals_dev/planted/SPEC.md`, which has not been run |
| Agent-run browser walk against the engine (PR #49) | Sign-up, submit, claim, return, resubmit and accept all completed | One scripted path run by an agent, not a person |
| Public-precedent test of the relevance pipeline (`docs/research/2026-10-20-vision/README.md`, §6) | On 53 Alberta precedents, screening every article and re-ranking the top 60 put an article the precedent cites first in 64% of cases and in the first five in 81%. Keyword search alone: 32% and 66% | Run on 2026-10-20 without the verifier stage. 53 cases from one province and one code. The gold lists can be incomplete. Not a held-out professional evaluation |

### 7.2 Protocol for the first human sessions

The protocol files are in [`docs/user-testing/`](./user-testing/): the applicant session script, a consent form, and the officer timing protocol. Every number in a results table stays blank until a session takes place. With fewer than 10 participants, results are indicative only.

| Round | Who | Task | Success metric (a target, not a result) | What the result changes |
|---|---|---|---|---|
| 1 | Three first-time applicants: one homebuilder, one general contractor, one manufacturer | One demo case each, thinking aloud | At least 2 of 3 finish Part 1 without help in a time set from internal dry runs. At most one question per session that the tool should have asked and did not | The wording and order of the questions, and the plain-language explainers |
| 1b | One or two SCOs or plan examiners at a partner organization | Review a package with planted gaps with the Batatis report and without it | Fewer minutes with Batatis than without, and at least Y of Z planted gaps found, with Y and Z fixed before the session | The layout of the officer view, which gaps show first, the wording of the information request |
| 1 retest | The same three applicants or new ones | The same cases after fixes | Every Round 1 failure point is passed, and time drops against Round 1 | Confirms the fixes before the design is frozen |
| 2 | A pilot authority's staff and its applicants | Live applications, in parallel with today's process | Returns for more information against the authority's own baseline. Override rate. "Would you open it twice" | Commit thresholds, jurisdiction-pack fields, and the decision to ask for a paid contract |

**Officer timing.** No timing data exists, from officers or from the team. The planted-gap comparison above is a protocol. Any internal dry-run time will be labelled as an internal estimate.

## 8. Pilot targets

Everything in the pilot plan is a target. See `docs/pilot-adoption-plan.md` for phases, segments, metrics and gating conditions.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A fabricated or wrong citation | The verifier must quote word for word and a quote that does not match is dropped. Section C comes from a lookup. A property test shows that a lying model produces zero fabricated ids or quotes on screen (PR #52) |
| A confident wrong identification | Nothing is committed automatically. The commit rule is empty until a benchmark calibrates it, and only Part 9 can ever commit |
| Model outage or provider change | The model version is pinned and recorded with each result. A labelled keyword fallback commits nothing. The relevance estimate never writes Section C |
| Personal information reaching a model | Redaction before every call, with a stated limit. Retention of 7 days. A pilot uses Canadian hosting and the organization's own approval |
| A claim that the design complies | Every screen and export says it checks administrative completeness only. Server decision text says "Accepted as administratively complete" and never "approved" or "compliant". The package review's boundary tests check that it uses no compliance language, fills no field and writes no decision |
| Eval validity | The 60 development cases are model-checked and in sample. We report them that way. No human-verified subset exists. A domain review of the rule vectors and checklists is needed from an engineer or an officer |
| Form or rule changes | The field map is pinned to the form's SHA-256 and a mismatch blocks export. The update runbook in §4.2 covers new bulletins |
| Code-text licensing | NRC code text is quoted for citations and linked to the NRC publication. Written NRC terms are needed before a public commercial launch (`docs/research/2026-10-20-vision/C-market-provinces-business.md`, §3.2 and (c)) |
| An official template replaces us | The Council and SSRIA are developing a template and guide. We fill the Council's form and would add their template as a form version |
| Officer adoption | The officer stays the decision-maker and edits every information request. Time saved is a target until a session measures it |
| Demo hosting limits | The demo project is on a free tier. The project's deployment allowance was exhausted once on Oct 20, so the demo must be tested on the final commit (`docs/deploy.md`) |

## 10. What we have not validated

- **No person has tested Batatis.** No applicant, officer or pilot partner has used it. Time saved for an officer is a target.
- **Code identification accuracy on the final pipeline is not measured.** The benchmark is unfinished (draft PR #58), and the commit rule is uncalibrated.
- **The screens that use the new backends are not finished.** Intake, code identification, jurisdiction packs and package review are merged as APIs.
- **All evaluation cases are model-checked and mostly in sample.** There is no human-verified subset.
- **Hosting is a US demo.** Canadian-region hosting is a plan for a pilot.
- **Officer refusal, the Calgary form, Part 2 prefill and portal integration are roadmap.**
