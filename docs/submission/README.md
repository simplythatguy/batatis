# Submission package checklist

Checklist for Submission 1 of the Alberta Building Codes Challenge (Built World Tech — Venture Pilots 2026). It maps each judging criterion to evidence that exists. A line marked `GAP:` has no supporting file, pull request, or number in the places this checklist was allowed to use.

Evidence base:

- `dev` at `9813702` (`Enable CodeRabbit reviews on pull requests into dev (#10)`). Paths below are on that commit.
- Pull request [#7](https://github.com/simplythatguy/batatis/pull/7) merged into `dev` at `bbdd051` (`web: small a11y and copy polish (polish-1)`). That commit is after the pin above. Path citations in this file were checked at `9813702`.
- Open pull requests into `dev`. An open pull request is not on `dev`.
- Open pull request [#18](https://github.com/simplythatguy/batatis/pull/18), branch `docs/plans-draft`, adds `docs/business-plan.md`, `docs/implementation-plan.md`, `docs/pitch-outline.md`, and `docs/pilot-adoption-plan.md`.
- Numbers already written in those pull-request bodies. A number this file calls **model-checked** is model-checked. It is not human-verified.

This file does not add scores, citations, or demo results.

## Package rules this repo cannot confirm

The package's exact contents and the submission time are only posted in Discord. They are unverified from this repository.

The date this checklist is aimed at is **29 October 2026**. That date is in the task for this file and in [`docs/research/2026-10-20-vision/2-week-build.md`](../research/2026-10-20-vision/2-week-build.md) ("Thursday 29 October 2026, the submission deadline"). That research note is not the Discord posting, and it does not give a clock time.

## Rubric

The verbatim scoring text is open pull request [#15](https://github.com/simplythatguy/batatis/pull/15), branch `cursor/judging-rubric-verbatim-2dfc`, file `docs/judging-rubric.md`. It is not on `dev`. The scoring question under each criterion below is quoted from that file. The file's editor's note says the nine weights sum to 100, that the sum is computed, and that the PDF prints no total row.

| # | Criterion | Weight |
| --- | --- | ---: |
| 1 | Intake | 20% |
| 2 | Code Identification | 20% |
| 3 | Recommendations | 10% |
| 4 | Review | 10% |
| 5 | General Applicability | 5% |
| 6 | Implementation Plan | 10% |
| 7 | Business Plan | 10% |
| 8 | Usability and Portability | 10% |
| 9 | The X Factor | 5% |

## Expected deliverables

These are the deliverables we expect the package to need. Discord has not been checked, so this list can be wrong.

| Deliverable | Status |
| --- | --- |
| Demo video | `GAP:` no submission demo video is in the repo. [`2-week-build.md`](../research/2026-10-20-vision/2-week-build.md) has a six-minute demo script ("The six-minute demo"). That is a script. Pull request [#16](https://github.com/simplythatguy/batatis/pull/16) links an agent screen recording of a local preview (`vite-who-to-completeness.mp4`). That recording is a development walkthrough of the branch, not a submission video. |
| Business plan | in PR #18: [`docs/business-plan.md`](https://github.com/simplythatguy/batatis/blob/docs/plans-draft/docs/business-plan.md) on open pull request [#18](https://github.com/simplythatguy/batatis/pull/18), branch `docs/plans-draft`. It is not on `dev`. Research on `dev` remains [`docs/research/2026-10-20-vision/C-market-provinces-business.md`](../research/2026-10-20-vision/C-market-provinces-business.md). This checklist does not restate the plan. |
| Implementation plan | in PR #18: [`docs/implementation-plan.md`](https://github.com/simplythatguy/batatis/blob/docs/plans-draft/docs/implementation-plan.md) on open pull request [#18](https://github.com/simplythatguy/batatis/pull/18), branch `docs/plans-draft`. It is not on `dev`. Closest material on `dev` is the research schedule [`2-week-build.md`](../research/2026-10-20-vision/2-week-build.md) (dated 2026-10-20). Open pull request [#6](https://github.com/simplythatguy/batatis/pull/6) is a user-testing appendix whose body says it backs an implementation plan. The same body says no real-user or officer sessions have been run, simulated sessions are labelled SIMULATED, and the results tables are blank. |
| Pitch outline | in PR #18: [`docs/pitch-outline.md`](https://github.com/simplythatguy/batatis/blob/docs/plans-draft/docs/pitch-outline.md) on open pull request [#18](https://github.com/simplythatguy/batatis/pull/18), branch `docs/plans-draft`. It is not on `dev`. |
| Pilot plan | in PR #18: [`docs/pilot-adoption-plan.md`](https://github.com/simplythatguy/batatis/blob/docs/plans-draft/docs/pilot-adoption-plan.md) on open pull request [#18](https://github.com/simplythatguy/batatis/pull/18), branch `docs/plans-draft`. It is not on `dev`. |
| Working link | `GAP:` hosting plan in progress. No deployed URL is in the repo. On `dev`, `web/src/api/client.ts` proxies `/api` to `http://127.0.0.1:8000`. [`2-week-build.md`](../research/2026-10-20-vision/2-week-build.md) says "Demo runs locally" and "A skeleton deploys on day 3". Pull request [#16](https://github.com/simplythatguy/batatis/pull/16) records a production preview against `http://127.0.0.1:8000`. |
| Repo | Present: [https://github.com/simplythatguy/batatis](https://github.com/simplythatguy/batatis). This checklist's tree is `dev` at `9813702`, plus the open pull requests named below. Pull request [#7](https://github.com/simplythatguy/batatis/pull/7) merged into `dev` at `bbdd051` after that pin. The root [`README.md`](../../README.md) status line still says application product code is not the focus of that document. `engine/` and `web/` are already on `dev`. |

## Risks

| Risk | Status |
| --- | --- |
| Appendix 1 vs the Oct 6 SCC form | Brief §2.5(a) asks for Appendix 1. Export uses the Oct 6 SCC form. An explicit statement is being written in pull request [#18](https://github.com/simplythatguy/batatis/pull/18). |

## 1. Intake — 20%

Scoring question, from pull request #15: "Does the tool capture the information it needs across varied application types, prompt for what's missing or incomplete, and signal its own confidence rather than filling boxes regardless. Evidence of internal testing/evals."

### On `dev`

- Fact model: [`engine/models.py`](../../engine/models.py). A fact is `exact`, `pointed`, `computed`, or `proposed`. A `proposed` fact carries `confidence` and the validator rejects `proposed` plus `confirmed`.
- Development fixtures: [`evals_dev/SCHEMA.md`](../../evals_dev/SCHEMA.md) and [`evals_dev/cases/dev-001.json`](../../evals_dev/cases/dev-001.json) through `dev-060.json`. `intake_action` is `ask`, `proceed_conditionally`, or `redirect`. `missing_info` separates `critical` from `administrative`. `description` is the only text the system under test is supposed to receive, and it must contain no article numbers.
- Fixture review: [`evals_dev/REVIEW.md`](../../evals_dev/REVIEW.md). The file's own status line is **model-checked** development fixtures; not human reviewed. Counts written there: 60 cases; intake actions `ask` 18, `proceed_conditionally` 38, `redirect` 4; applicant types architect-engineer 14, contractor 13, homebuilder 8, manufacturer 14, owner 11. The same file says human/professional review completed for zero cases in that task, and that no held-out accuracy is claimed. Those counts are model-checked. They are not human-verified.
- Web intake chrome on `dev`: [`web/src/screens/Describe.tsx`](../../web/src/screens/Describe.tsx), confidence text for proposed facts in [`web/src/case-parts.tsx`](../../web/src/case-parts.tsx), and a "Not sure" answer in [`web/src/screens/CodeCheck.tsx`](../../web/src/screens/CodeCheck.tsx).
- A new visit loads a filled example. [`web/src/store.tsx`](../../web/src/store.tsx) session key `batatis-web-case-v2` falls through to [`web/src/fixture.ts`](../../web/src/fixture.ts). The screens do not call the engine's case or fact routes. The typed client does define `createCase` and `addFact` ([`web/src/api/client.ts`](../../web/src/api/client.ts)), and [`web/scripts/smoke-api.ts`](../../web/scripts/smoke-api.ts) calls them against a running engine. No result of that script is recorded in the repo. The routes themselves are in [`engine/api.py`](../../engine/api.py).

### Open pull requests

- [#16](https://github.com/simplythatguy/batatis/pull/16) (web-to-engine MVP, not merged). The body describes an empty case, three roles (manufacturer, general contractor, homebuilder), a typed description posted with `POST /cases` and `POST /facts`, and "Not sure" stored as an open question. It also says file upload `POST /files` returned 404, and that article ranking stays command-line only.
- [#14](https://github.com/simplythatguy/batatis/pull/14) (demo cases, not merged). Three applicant bundles: manufacturer nailbase sheathing, contractor firestop nonconformance, homebuilder infill house. The body says no loader reads `evals/demo-cases/` yet, people and products are fictional, and the cases were checked against the NBC(AE) 2023 1st printing. It says the 2nd printing wording and page numbers are unverified.

### GAP

- `GAP:` no human-verified intake score, and no scored run of the product on varied application types. The 60-case file is a model-checked fixture set. [`evals_dev/REVIEW.md`](../../evals_dev/REVIEW.md) says no held-out accuracy is claimed.
- `GAP:` on `dev`, the applicant UI starts from the fixture in `web/src/fixture.ts`.

## 2. Code Identification — 20%

Scoring question, from pull request #15: "Does it map the project to the right articles and rank them sensibly; does it name a plausible benchmark acceptable solution; is Section C's attribution table complete and accurate; do all citations resolve to real articles in the correct edition; is the rationale for each article's inclusion consistent with the code's structure."

### On `dev`

- Identifier library: [`engine/identify/__init__.py`](../../engine/identify/__init__.py). It screens Division B articles, reranks the top N, and can call [`engine/identify/verify.py`](../../engine/identify/verify.py). The module docstring says nothing there commits an article. There is no identify route in [`engine/api.py`](../../engine/api.py) or [`engine/routes_case.py`](../../engine/routes_case.py).
- Section C lookup: [`engine/section_c.py`](../../engine/section_c.py) and `POST /section-c` in [`engine/api.py`](../../engine/api.py). Code search and lookup: `GET /code/search`, `GET /code/{provision_id}`.
- Web Section C: [`web/src/api/sectionC.ts`](../../web/src/api/sectionC.ts) calls `POST /section-c`. If the engine cannot be reached, it falls back to fixture rows and sets `source` to `offline`.
- Fixture gold for benchmarks and Section C rows: [`evals_dev/SCHEMA.md`](../../evals_dev/SCHEMA.md). `gold.must_cite` uses role `benchmark` or `scope`. `gold.section_c` is specified as a copy of `codedb.lookup`. The checker is [`evals_dev/validate_cases.py`](../../evals_dev/validate_cases.py). Edition named in the schema: NBC(AE) 2023, 2nd printing. [`evals_dev/REVIEW.md`](../../evals_dev/REVIEW.md) says that review was model-checked and that no engine accuracy is claimed.
- Research benchmark, separate from the product API: [`docs/research/2026-10-20-vision/jev-benchmark/README.md`](../research/2026-10-20-vision/jev-benchmark/README.md). It records a run on 53 public Alberta precedent cases (84 gold articles) against 2,080 Division B articles. Figures written in that README: BM25 MRR 0.485, top-1 32%; BM25 top 60 then Jev rerank MRR 0.728, top-1 66%; screen-all then rerank MRR 0.723, top-1 64%; on 20 variance and SPV cases, adding a Sonnet 5.5 verifier moved MRR from 0.748 to 0.875 and top-1 from 65% to 85%. The same README says this is not a held-out professional evaluation, and that the protected evaluation set was not used. Those figures are the research note's measured results. They are not human-verified, and they are not a score of the applicant product.

### Open pull requests

- [#12](https://github.com/simplythatguy/batatis/pull/12) (identify pipeline and keyed OpenAI benchmark, draft, not merged). The body says `POST /cases/{id}/identify` and `engine/cli_sut.py` call `engine.identify.pipeline.run`, and that an answer of "not sure" is stored with status `unknown`. It gives the benchmark command (`python -m engine.identify.benchmark`, 20 `evals_dev` cases, 3 repeats, FX 1.4097 on 2026-10-19). It says pytest of the listed modules was 17 passed, and that a missing `OPENAI_API_KEY` exits 2. It also says demo-cache quotes and a live OpenAI score are not in that push.
- [#16](https://github.com/simplythatguy/batatis/pull/16). The body says Section C on that branch is a live lookup or a labelled cached demo, and that article ranking is command-line only.

### GAP

- `GAP:` no published OpenAI identification accuracy. Pull request #12 says the live score is not in the push.
- `GAP:` no product run, on `dev` or in a pull-request body, that ranks articles for an applicant description and scores the benchmark acceptable solution.

## 3. Recommendations — 10%

Scoring question, from pull request #15: "Does it identify the specific technical issues or code sections the supplemental documentation must address, and does it correctly flag where engineering or another licensed professional is required — including knowing where to stop rather than generating professional judgment itself."

### On `dev`

- Evidence plan: [`engine/section_d.py`](../../engine/section_d.py). Items offer evidence types in the confidence-ladder order, plus the alternative-path types (CCMC, ICC-ES, registered professional opinion, engineering review). The module docstring says no test, evaluation, professional opinion, or result is generated there.
- Professional screen: [`engine/professional.py`](../../engine/professional.py). The docstring says it is a deterministic screen, not a licence determination, and that missing facts cannot produce an overall `no`. Result values are `yes`, `no`, and `depends`.
- Process prompts: [`engine/process_fields.py`](../../engine/process_fields.py). The docstring says the module supplies prompts, never answers. Field ids include `rationale`, `risk_assessment`, `mitigating_measures`, and `assumptions_and_limits`.
- Routes in [`engine/routes_case.py`](../../engine/routes_case.py): `POST /cases/{id}/section-d`, `GET /cases/{id}/professional`, `GET /cases/{id}/process-fields`. There is no Section D issues route on `dev`.
- Fixture labels: [`evals_dev/REVIEW.md`](../../evals_dev/REVIEW.md) records professional-involvement flags of 33 `yes`, 17 `depends`, 10 `no` on the 60 cases. That review is model-checked. It is not human-verified. The file says zero cases received human/professional review.

### Open pull requests

- [#8](https://github.com/simplythatguy/batatis/pull/8) (Section D issues and practice-of-engineering screen, not merged). Numbers below are copied from the pull-request body. The body calls them model-checked. They are not human-verified.
  - Engineer-needed flag: 55/60 agreement on the model-checked dev set (in-sample), 1 under-flag, 13 unknowns sent to the applicant.
  - The body says the `rules_plus_unknown` row is in-sample, pending out-of-sample confirmation, and that the span rule came from development case `dev-050`.
  - Held-out, model-checked, as written: `held-out rules_plus_unknown: 7/8 [0.5291, 0.9776]`.
  - Also written: `held-out (post-fix, no longer blind for missing-fact cases) rules_plus_unknown: 4/8 [0.2152, 0.7848]`.
  - Dev `rules_plus_unknown` under-flag is 0.
  - Pytest written in the body: `python3 -m pytest engine/tests/test_section_d_issues.py -q` — 14 passed.
  - The body says citation text was not checked against a local code database in that run.
- [#9](https://github.com/simplythatguy/batatis/pull/9) (human-key harness, not merged). The body says the branch is rebased onto #8 because `dev` does not yet contain the Section D practice screen. Numbers below are copied from the pull-request body. The body marks `label_strength: weak; editions pre-2023`. They are not human-verified.
  - `rules_only`, `rules_plus_unknown`, and `always_unknown`: each `7/12 [0.3195, 0.8067]`.
  - `unknown: 12` on each variant. `confident_wrong: none`.
  - The body says stored facts do not establish a yes or a no, so every variant abstains; the 7 matches are the weak `depends` labels; the 5 weak `yes` labels land in the unknown column.
  - Pytest written in the body: 21 passed (`test_human_key.py`, `test_deterministic_checks.py`, `test_appeals.py`).

### GAP

- `GAP:` the issues list that names specific supplemental-documentation items is only on pull request #8. It is not on `dev`.
- `GAP:` no human-verified professional-flag score. The appeals labels in #9 are marked weak and pre-2023 in that pull request.

## 4. Review — 10%

Scoring question, from pull request #15: "Can it review a completed application, summarize it usefully for an SCO or applicant including supplemental material, and flag gaps or missing components. Does the reviewer-facing view actually save an SCO time."

### On `dev`

- Administrative checker: [`engine/completeness.py`](../../engine/completeness.py). The docstring limits this file to planted classes D01–D13 and D16, and says D09/D10 cover empty fields only. It says generic or unrelated narratives, attachment contradictions (D14), relevance (D15), engineering adequacy, and licence authenticity require human judgement. `check_completeness` says an empty list is no technical or acceptance determination.
- Route: `GET /cases/{id}/gaps` in [`engine/routes_case.py`](../../engine/routes_case.py).
- Tests for those classes: [`engine/tests/test_completeness.py`](../../engine/tests/test_completeness.py). This checklist does not restate a pass count; none is written beside the file.
- Planted-defect protocol only: [`evals_dev/planted/SPEC.md`](../../evals_dev/planted/SPEC.md). The spec says generating the seeded PDFs waits for form export. The directory contains that spec and no planted applications.
- Applicant pre-flight chrome: [`web/src/screens/Application.tsx`](../../web/src/screens/Application.tsx) at `9813702`. "Run pre-flight" stays disabled while blocking gaps from the client model remain. The dialog says filling the official SCC form arrives with the engine, and that the check is administrative. Pull request [#7](https://github.com/simplythatguy/batatis/pull/7) merged into `dev` at `bbdd051` and renames that button to "Check completeness".
- Officer screen: [`web/src/screens/Placeholders.tsx`](../../web/src/screens/Placeholders.tsx) renders "Not built yet" for officer review. The accuracy page in the same file says "No evaluation runs yet".

### Open pull requests

- [#11](https://github.com/simplythatguy/batatis/pull/11) (administrative completeness pipeline, draft, not merged). The body adds bulletin gates for IB-2025-11-18 and IB-2026-10-01, and says the 10-day copy to the Safety Codes Council is a reminder, not an export blocker. Numbers below are copied from the pull-request body (offline `python3 -m evals_dev.completeness_eval --repeats 1`, no `--live`, no code database). They are not human-verified.
  - Before, as written: variant A 0.992 (729/735), variant B 1.000 (735/735), clean-control false positives 0, invented values 0. Variant C not scored.
  - After, as written: variant A `overall_success=0.993 (845/851)`; variant B `overall_success=1.000 (851/851)`; both `invented_values=0` and `invented_value_gate=pass`; clean-control false positives 0. Variant C `status=skipped`.
  - The body says variant A still misses generic risk (D09 1/2), unrelated mitigations (D10 1/2), contradictions (D14 0/2), and relevance (D15 0/2), and that D05 and D07 are absent from that table because they need the code database.
  - Pytest written in the body, without a code database: 12 passed across `test_bulletin_gates.py`, `test_portal_package.py`, `test_jurisdiction_wording.py`, and `test_schema_export.py`.
  - The body says the draft is not ready to merge.
- [#16](https://github.com/simplythatguy/batatis/pull/16). The body says "Check completeness" stays disabled until blocking gaps close, then calls `POST /cases/{id}/export`. It also says `GET /gaps` returned 503 when `BATATIS_CODEDB` was missing.
- [#6](https://github.com/simplythatguy/batatis/pull/6) (user-testing appendix, not merged). `officer-timing-protocol.md` is the planned comparison of a manual checklist with Batatis. The body says no officer session has been run and the results tables are blank. Round 1b is planned as 1–2 officers.

### GAP

- `GAP:` no measurement that a reviewer-facing view saves an SCO time. The officer screen on `dev` is the placeholder in `web/src/screens/Placeholders.tsx`. Pull request #6 has a protocol and blank tables.
- `GAP:` no planted-gap applications in `evals_dev/planted/` on `dev`. The spec says the PDFs are not generated yet.

## 5. General Applicability — 5%

Scoring question, from pull request #15: "Could an inexperienced applicant of any type — manufacturer, general contractor, homebuilder — use this without prior variance experience or code fluency."

### On `dev`

- The 60 development cases include those roles. [`evals_dev/REVIEW.md`](../../evals_dev/REVIEW.md) counts, model-checked and not human-verified: manufacturer 14, contractor 13, homebuilder 8, plus architect-engineer 14 and owner 11. Descriptions are specified to be plain language with no article numbers ([`evals_dev/SCHEMA.md`](../../evals_dev/SCHEMA.md)).
- The web app on `dev` has one filled fixture ([`web/src/fixture.ts`](../../web/src/fixture.ts)), not a role chooser.

### Open pull requests

- [#14](https://github.com/simplythatguy/batatis/pull/14). One demo case each for a manufacturer, a general contractor, and a homebuilder, plus tester samples. The body says no loader reads them, and that only each case's `input/` folder (and tester bundles 01–03) would ever be uploaded. Answer keys live under `presenter/` and `tester-samples/key/`.
- [#16](https://github.com/simplythatguy/batatis/pull/16). The body describes a "Who are you?" step with manufacturer, general contractor, and homebuilder, each starting from an empty case, plus "Try an example" for three cached runs.

### GAP

- `GAP:` no session with an inexperienced applicant. Pull request #6 says no real-user sessions have been run.
- `GAP:` the three demo cases and the role chooser are not on `dev`.

## 6. Implementation Plan — 10%

Scoring question, from pull request #15: "Is there a realistic path to beta. How will the product testing with users inform final design? How does the product integrate with current user workflows?"

### On `dev`

- Research schedule only: [`docs/research/2026-10-20-vision/2-week-build.md`](../research/2026-10-20-vision/2-week-build.md), dated 2026-10-20. It names a build window of 21–29 October 2026, gates G1–G5, a cut order, and a day-3 skeleton deploy. It is a research note. It is not a submission implementation plan, and the gates in it are not results.

### Open pull requests

- [#18](https://github.com/simplythatguy/batatis/pull/18). in PR #18: `docs/implementation-plan.md` and `docs/pilot-adoption-plan.md` on branch `docs/plans-draft`. They are not on `dev`. This checklist does not restate those files.
- [#6](https://github.com/simplythatguy/batatis/pull/6). `docs/user-testing/`: round plan, think-aloud script, SUS, a consent form marked DRAFT, and an officer timing protocol. The body says this appendix backs the implementation plan, that no real-user or officer sessions have been run, and that the results tables are blank. Round 1 is planned as 3 applicants. Round 1b is planned as 1–2 officers.

### GAP

- `GAP:` no user-test results that could inform a final design. The testing kit is an open pull request with blank tables. The submission implementation plan and the pilot plan are in PR #18.

## 7. Business Plan — 10%

Scoring question, from pull request #15: "Is there a credible company here — buyer, willingness to pay, cost per application, and a defensible position as the underlying models improve."

### On `dev`

- Research notes only: [`docs/research/2026-10-20-vision/C-market-provinces-business.md`](../research/2026-10-20-vision/C-market-provinces-business.md). Header: "Research only." Claim labels in that file are VERIFIED, VENDOR CLAIM, ESTIMATE, and UNVERIFIED.
- Section "(a) One-page business case" is labelled "ESTIMATES unless marked". It discusses who pays, a cost-per-application anchor, and a moat. Those sentences stay inside that file's labels. This checklist does not promote them to a business plan.
- Section 5 records the file's own reading of willingness to pay. The same file says Alberta or Canadian consultant fees for alternative solutions were still not found after that pass.

### Open pull requests

- [#18](https://github.com/simplythatguy/batatis/pull/18). in PR #18: `docs/business-plan.md` on branch `docs/plans-draft`. It is not on `dev`. This checklist does not restate that file. The pitch outline on the same pull request is `docs/pitch-outline.md`.

## 8. Usability and Portability — 10%

Scoring question, from pull request #15: "Overall user experience for both sides. Would a design lead choose this over their current process; would an SCO open it twice. Is it designed for adaptability to individual jurisdictions."

### On `dev`

- Applicant screens: Describe, Code check, Section C, and Application under [`web/src/screens/`](../../web/src/screens/). Officer review and the accuracy report are placeholders ([`web/src/screens/Placeholders.tsx`](../../web/src/screens/Placeholders.tsx)).
- Visual system: [`docs/design-system-linear.md`](../design-system-linear.md) and [`docs/design/tokens.css`](../design/tokens.css).
- Jurisdiction is a data field, not a pack. [`engine/models.py`](../../engine/models.py) `Jurisdiction` has `id`, `name`, and `authority`. [`evals_dev/SCHEMA.md`](../../evals_dev/SCHEMA.md) says `jurisdiction` is kept as data so cases stay portable across jurisdictions. A search of the tree finds no jurisdiction-pack files. Packs are described as future work in [`2-week-build.md`](../research/2026-10-20-vision/2-week-build.md) and in the market research note.
- Export route on the engine: `POST /cases/{id}/export` in [`engine/api.py`](../../engine/api.py), implementation under [`engine/export/`](../../engine/export/). The Application screen on `dev` does not call it. The dialog says the SCC form arrives with the engine.
- After the pin: pull request [#7](https://github.com/simplythatguy/batatis/pull/7) merged into `dev` at `bbdd051`. Copy and accessibility polish on `web/`. The body says it renames the user-facing "Run pre-flight" button to "Check completeness".

### Open pull requests

- [#16](https://github.com/simplythatguy/batatis/pull/16). The body says the product surface moves to `web/`, that export is called after blocking gaps close, and that the official PDF still needs the code database and `BATATIS_SCC_FORM` on the machine that runs the engine. Screenshots in that body are of a local preview.
- [#11](https://github.com/simplythatguy/batatis/pull/11). The body says wire fields on `Jurisdiction` stay `id`, `name`, and `authority`, and that "authority having jurisdiction" wording follows IB-2026-10-16. That wording change is not on `dev`.

### GAP

- `GAP:` no evidence a design lead would choose this over a current process, and no evidence an SCO would open it twice. The officer screen on `dev` says it is not built yet.
- `GAP:` no jurisdiction packs. Portability on `dev` is the `Jurisdiction` field and the case schema, not a per-municipality package.

## 9. The X Factor — 5%

Scoring question, from pull request #15: "Hard-to-quantify edge — team, insight, unfair advantage."

### On `dev`

- Product thesis, as research: [`docs/research/2026-10-20-vision/README.md`](../research/2026-10-20-vision/README.md). It argues that Alberta variance volume is concentrated in a few Part 9 articles and that surveyed AI plan-review products check prescriptive rules. The market note ([`C-market-provinces-business.md`](../research/2026-10-20-vision/C-market-provinces-business.md), section 1) labels "no competitor prepares alternative-solution applications" as an UNVERIFIED negative (absence from search, not proof).
- The same vision note's measured identification work is the Jev benchmark in section 2 above. The benchmark README's own limit applies: not a held-out professional evaluation.

### GAP

- `GAP:` no team note, no biography, and no submission statement of an unfair advantage.
- `GAP:` the competitor claim stays an UNVERIFIED negative inside the research file. This checklist does not treat it as established.

## Open work that blocks the package

Nothing below is a result. It is the list of `GAP:` lines that still have no file.

1. Submission demo video.
2. A working link. Hosting plan in progress. Local preview only.
3. A scored identification run with a published accuracy. Pull request #12 has the command and says the live OpenAI score is absent.
4. Human-verified intake, code-identification, and professional-flag scores. What exists is model-checked, or marked weak, or a research measurement with the limits written in its own file.
5. An officer view with a time measurement. The screen on `dev` is a placeholder.
6. Jurisdiction packs, and the three applicant demo cases (pull request #14) loaded by the product.
7. User-test results that could inform a final design. Pull request #6 is a protocol with blank tables.

The business plan, the implementation plan, the pitch outline, and the pilot plan are in PR #18.
