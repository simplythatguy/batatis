# Path comparison on the merged tree

Measured on `cursor/package-w2-workflow-47fe` after merging `origin/main` `e34b4e4` (27 October 2026). The path code is `9f52347` plus that merge. The merge did not change `engine/path_decision.py`, `engine/process_fields.py`, or `web/src/calm/deck.ts`.

`origin/main` had moved three commits past the package base `e9fe416`:

- `b2cc8c0` turns AI on when someone signs in to Claude or ChatGPT (`desktop/src/main/controller.ts`, `desktop/tests/workflow-dispatch.test.ts`).
- `97239cb` ships the code database in the installer and installs it on first launch (`desktop/src/main/codedb.ts`, `desktop/src/main/controller.ts`, `desktop/electron-builder.cjs`, `desktop/scripts/audit-package.cjs`, `desktop/tests/vault-codedb-runtime.test.ts`). The settings line in `web/src/desktop/DesktopSettings.tsx` now says to reinstall Batatis or choose a database built by Batatis.
- `e34b4e4` is the merge of pull request 105.

No conflict. Those desktop files are the only files `origin/main` changed. The path decision on this branch is the same code the comparison ran.

## How the four columns were produced

Same 152 prompts as `frozen/prompts.json` (63 application, 89 rule). Same ten checks as `RUBRIC.md`. No model was called. Pass 2 ran the same functions. `results/both_passes.csv` has 1,216 rows. The largest absolute difference between passes is 0 quality points and 0 questions.

Balanced quality is `0.5 * (application mean) + 0.5 * (rule mean)`. Balanced questions use the same weights. Path match is the unweighted share of the 152 prompts. A fabricated citation is any provision id, STANDATA id, CCMC number, or function-objective pair that was not in the prompt, the coded check, the Section C lookup, or a Division C citation for a process field that was actually asked.

| workflow | what decided the path and the package |
|---|---|
| BEFORE | `origin/main` at `e34b4e4`. `engine/intake/scope.py` `classify`, `engine/intake/fork.py` `assess`, `engine/process_fields.py` `alternative_path` and `process_fields`, and `engine/section_d.py` evidence tuples. Loaded from a worktree of that commit, then called. |
| FLOWCHART | The attached drawing, in order, in `workflows.py` `run_w1`. A diamond answer other than yes or no does not open a package. |
| FLOWCHART+LOOKUP | The same diamond and the same performance, comparison, and gap questions. The objective, function, and intent questions are removed. Section C is the code database. `workflows.py` `run_w1l`. |
| AFTER | This branch. `engine/path_decision.py` `decide_path`, then `process_fields` and the Section D tuples. Process fields only when the path is alternative. Shared ladder when it is acceptable. No package when it is unresolved, not applicable, or a redirect. |

On every prompt, BEFORE's path, process-field list, and evidence flag matched a shadow run of the earlier harness arm, and AFTER matched the earlier W2 arm. Mismatches: 0 of 152 for each. The numbers below were recomputed from `results/per_prompt.csv` after that run. They are the same figures as the code-database rescore because the merge did not change this behavior, and because `decide_path` agrees with that arm.

## Scores

Recomputed from `results/per_prompt.csv` (608 rows: 4 workflows, 152 prompts).

| workflow | balanced quality | balanced questions | path match | fabricated citations | application quality | rule quality |
|---|---:|---:|---:|---:|---:|---:|
| BEFORE | 8.513 | 20.53 | 0.553 | 0 | 9.206 | 7.820 |
| FLOWCHART | 7.709 | 14.72 | 0.401 | 0 | 7.778 | 7.640 |
| FLOWCHART+LOOKUP | 8.709 | 10.98 | 0.401 | 0 | 8.778 | 8.640 |
| AFTER | 9.739 | 13.02 | 0.921 | 0 | 9.524 | 9.955 |

Exact means:

- BEFORE application quality 580/63 = 9.206349. Rule quality 696/89 = 7.820225. Balanced quality 8.513287. Balanced questions 20.532994. Path 84/152 = 0.552632.
- FLOWCHART application 490/63 = 7.777778. Rule 680/89 = 7.640449. Balanced quality 7.709114. Balanced questions 14.724006. Path 61/152 = 0.401316.
- FLOWCHART+LOOKUP application 553/63 = 8.777778. Rule 769/89 = 8.640449. Balanced quality 8.709114. Balanced questions 10.976012. Path 61/152 = 0.401316.
- AFTER application 600/63 = 9.523810. Rule 886/89 = 9.955056. Balanced quality 9.739433. Balanced questions 13.023542. Path 140/152 = 0.921053.

Fabricated citations: 0 prompts, 0 ids, on all 608 drafts.

AFTER is 1.226 balanced points above BEFORE (9.739433 − 8.513287) and asks 7.51 fewer balanced questions (20.532994 − 13.023542). AFTER is 2.030 points above the strict flowchart and 1.030 points above the flowchart with the database lookup. The lookup arm asks fewer questions (10.98 versus 13.02). The rubric picks the higher quality when the gap is larger than 0.25, so AFTER still wins. The lookup arm's shorter list is the diamond stopping early: path match stays 61/152.

The deck still shows one "here's what I understood" card. The AFTER column does not ask it. A separate run that adds only that card (`workflows.py` `run_w2c`, saved in `results/confirm-card.json`) scored balanced quality 9.739433 and balanced questions 13.991796, with the same 140/152 path matches and 0 fabricated citations. Same quality, about one more question. The winner does not change. That card is already on both the old deck and the new deck (`web/src/calm/deck.ts`, the understood card).

## Path confusion

Counts are gold path → chosen path. Each row sums to the number of prompts with that gold path: acceptable 38, alternative 61, unresolved 32, not applicable 17, redirect 4.

BEFORE (`origin/main` gate), 68 misses:

| gold \ chosen | acceptable | alternative | unresolved | not applicable | redirect |
|---|---:|---:|---:|---:|---:|
| acceptable | 0 | 0 | 38 | 0 | 0 |
| alternative | 0 | 56 | 5 | 0 | 0 |
| unresolved | 0 | 8 | 24 | 0 | 0 |
| not applicable | 0 | 1 | 16 | 0 | 0 |
| redirect | 0 | 0 | 0 | 0 | 4 |

Chosen path was acceptable on 0 prompts. Every one of the 38 acceptable rule vectors came back unresolved.

FLOWCHART, 91 misses. FLOWCHART+LOOKUP has the same 91. The lookup does not change the diamond.

| gold \ chosen | acceptable | alternative | unresolved | not applicable | redirect |
|---|---:|---:|---:|---:|---:|
| acceptable | 0 | 0 | 38 | 0 | 0 |
| alternative | 0 | 37 | 24 | 0 | 0 |
| unresolved | 0 | 8 | 24 | 0 | 0 |
| not applicable | 0 | 1 | 16 | 0 | 0 |
| redirect | 0 | 2 | 2 | 0 | 0 |

Chosen path was acceptable on 0 prompts and redirect on 0 prompts.

AFTER, 12 misses:

| gold \ chosen | acceptable | alternative | unresolved | not applicable | redirect |
|---|---:|---:|---:|---:|---:|
| acceptable | 37 | 0 | 1 | 0 | 0 |
| alternative | 0 | 58 | 3 | 0 | 0 |
| unresolved | 0 | 8 | 24 | 0 | 0 |
| not applicable | 0 | 0 | 0 | 17 | 0 |
| redirect | 0 | 0 | 0 | 0 | 4 |

The 12 misses are `dev-007`, `dev-012`, `dev-020`, `dev-021`, `dev-028`, `dev-048`, `dev-053`, `dev-055`, `dev-056`, `U05`, `S14`, and `demo-a`. Eleven of them are a wording fork with no firm coded check: eight unresolved gold prompts were called alternative, and three alternative gold prompts stayed unresolved. `S14` is the one acceptable miss. Its vector expects `follows` with one labeled assumption (`evals_dev/rules/vectors.json`, storeys and area not stated). `decide_path` treats a labeled assumption as not firm (`engine/path_decision.py` `_firm`), so the path stays unresolved and the package stays closed. That prompt scores 9 of 10. The only failed check is the path.

Check failures across the 152 prompts:

| workflow | path | process fields | evidence | code-analysis quiz | judgment or compliance claim |
|---|---:|---:|---:|---:|---:|
| BEFORE | 68 | 87 | 87 | 0 | 1 |
| FLOWCHART | 91 | 72 | 35 | 152 | 0 |
| FLOWCHART+LOOKUP | 91 | 72 | 35 | 0 | 0 |
| AFTER | 12 | 11 | 11 | 0 | 0 |

BEFORE's 87 process-field failures are the prompts where the six fields were asked and the gold path was not alternative: all 38 acceptable, all 17 not applicable, and all 32 unresolved. The 24 unresolved prompts whose path label matched still fail the process and evidence checks, because the package opened. The five alternative prompts left unresolved fail the path check and pass the process check, because the fields were asked. 38 + 17 + 32 = 87. Evidence fails on the same 87, because the list included CCMC, ICC-ES, a registered professional opinion, and an engineering review.

## dev-001

`evals_dev/cases/dev-001.json`. Infill house, north wall 0.3 m from the side lot line, 450 mm overhang, vented aluminum soffit. Gold path: alternative. Benchmark article on the case: 9.10.15.5.(8).

`engine/intake/fork.py` `assess` returns `unknown`. The sentence that mentions a variance is a question, and `assess` skips questions. The soffit numbers are a firm departure once they are in the case.

`decide_path` on those facts returns `alternative`, source `coded_check`, rule `soffits-houses`, article `9.10.15.5.(8)`.

Section C from `engine/section_c.py` against `codedb/build/codedb.sqlite` (13,743 provisions), one row:

- provision `9.10.15.5.(8)`
- attribution status `direct`
- function-objective pair `F03-OP3.1`
- intent objective `OP3`
- intent statements: 1

The draft line is `9.10.15.5.(8) | direct | pairs F03-OP3.1 | intent objectives OP3 | intent statements 1`. The database row's intent prose is 277 characters. That prose is not in the draft. Sentence text is not in the draft.

| workflow | path | article | quality | questions | what was asked |
|---|---|---|---:|---:|---|
| BEFORE | alternative | 9.10.15.5.(8) | 10 | 20 | reading confirmation; assembly description; sprinklers; exposing-face area; glazed area; add the departing rule; six process fields; one evidence question; seven paperwork fields including municipality-wide scope |
| FLOWCHART | unresolved | none | 6 | 8 | which acceptable solution; objectives; functional statements; intent; minimum performance; comparison; gaps; the diamond. Diamond answer: Not sure. Package stayed closed. |
| FLOWCHART+LOOKUP | unresolved | 9.10.15.5.(8) | 7 | 5 | which acceptable solution; minimum performance; comparison; gaps; the diamond. The firm soffit check committed the article and the database line above. The diamond was still Not sure, so the package stayed closed. |
| AFTER | alternative | 9.10.15.5.(8) | 10 | 14 | six process fields; one evidence question (shared ladder plus the four alternative types); seven paperwork fields including scope. The soffit inputs were already in the prompt, so no further rule question was asked. |

BEFORE and AFTER both pass all ten checks on this fixture. BEFORE asks six more questions: the confirmation, three inputs for other rules that are merely in play, the glazed-area input, and the "add this rule" card. The flowchart scores 6 because the path, the process fields, the evidence list, and the code-analysis quiz all fail. The lookup version scores 7: the quiz is gone and Section C matches the database, and the path, process fields, and evidence still fail.

## Why the packaged path scores higher

The gap is the package gate, measured on the same prompts.

On `origin/main`, `engine/process_fields.py` `alternative_path` is true unless a confirmed fact named `pathway` or `path` is already `acceptable` or `acceptable_solution`. An unknown fork does not write that fact. `engine/section_d.py` appends CCMC, ICC-ES, registered professional opinion, and engineering review whenever `alternative_path` is true. The deck in `web/src/calm/deck.ts` on that commit pushes the six process cards for every case, then drops case and proof cards only when `journey.route` is `standard` or the product scope is product acceptance (`usualRoute`, around the paperwork filter). On these 152 prompts `assess` never returned `not_indicated`, so that filter never selected the standard route. A firm `follows` result does not write `pathway`. Result on the rule slice: all 38 acceptable vectors stayed unresolved, and the variance package still opened. That is 38 path misses plus a process-field miss and an evidence miss on each of them, and the same package miss on the unresolved and not-applicable prompts. Rule quality is 696/89 = 7.820. Balanced questions are 20.53 because the six fields, the evidence question, and the paperwork are asked on the prompts that should have stopped.

On this branch, `alternative_path` is `decide_path(case).path == 'alternative'` (`engine/process_fields.py`). `decide_path` maps a firm check with no labeled assumption: `follows` to acceptable, `departs` to alternative, `not_applicable` to stop (`engine/path_decision.py`). Unknown wording does not open the alternative package. The deck asks the six process fields only when `decision.path === "alternative"` and asks the Section D card when the path is acceptable or alternative (`web/src/calm/deck.ts`). Acceptable evidence is the shared ladder only, which is what `section_d.py` recommends when `alternative_path` is false. Not applicable and unresolved do not open that card (`path-stop`). Result: 37 of 38 acceptable vectors match, 17 of 17 not-applicable vectors match, 4 of 4 redirects match. Rule quality is 886/89 = 9.955. The 11 process-field failures and 11 evidence failures are the same wording misses as 11 of the 12 path misses, not a second package bug.

Used as the applicant's question order, the drawing asks objectives, functional statements, and intent before the diamond, then minimum performance, a comparison, and the gaps, then the diamond. `workflows.py` `run_w1` does that. The oracle answers the diamond from `assess`. Yes and no are the only answers that open a package. Not sure stops. On this set `assess` never returned `not_indicated`, so the diamond never returned yes, and acceptable was chosen 0 times. The drawing has no redirect, so the 4 out-of-scope prompts were split 2 alternative and 2 unresolved. A firm `follows` or `departs` does not move the diamond. That is why dev-001, which is a firm soffit departure and an unknown wording fork, stays unresolved and scores 6. Replacing the quiz with the database (`run_w1l`) adds the one code-quiz point on all 152 prompts, which is the entire move from 7.709 to 8.709, and it leaves the path counts unchanged at 61/152. The drawing's own diamond is what holds the path match at 0.401.

## Checks on this tree

Targeted engine tests, one process, 75 passed, 0 failed: `test_path_decision.py` 12, `test_assist.py` 45, `test_dana_section_d.py` 7, `test_draft_document.py` 2, `test_voice_context.py` 9.

Web unit tests for the deck path: `deck.test.ts` 39 passed, `rulesDeck.test.ts` 19 passed, `journey.test.ts` 8 passed, `journeyFlow.test.ts` 14 passed. 80 passed, 0 failed. `tsc --noEmit` in `web/` completed with no errors.

The full engine suite (`engine/tests`, `codedb/tests`, `evals_dev`) was split into eight shards with `scripts/pytest_shard.py`. `TEST_DATABASE_URL` was not set, so Postgres tests skipped. Totals: 4,182 passed, 716 skipped, 1 failed. The failure is `evals_dev/tests/test_mandatory_triggers.py::test_must_not_holds_and_outcomes_stay_frozen`. `mtt-30a` (HR-30, fires) expects the Safety Codes Act s.38 row. `engine/human_review.py` adds that row only when `alternative_path` is true. On `origin/main` an unset pathway stayed on the alternative path. On this branch the fixture's facts are `variance_requested=true` and `variance_scope`, with no project description, so `decide_path` returns unresolved and the row is absent (`site row absent; value unknown; routed officer`). `must_not` still passes. Scoring all 12 cases, `mtt-32b` also loses the site row and would fail the same assertion once `mtt-30a` is past it. The screen was not retuned, and the frozen expectations were not edited. That is the routing change this comparison measured, showing up on a fixture the 152 prompts do not contain.

## Reproduction

`python experiments/workflow-bakeoff/product_compare.py` from the repo root, with `origin/main` checked out at `/tmp/origin-main` (this run used `e34b4e4`). The script refuses to load `alternative_path` unless that file still has the pre-change predicate and does not mention `decide_path`. The code database it reads is the local `codedb/build/codedb.sqlite`, which is not in git.

## What these numbers are not

- No safety codes officer scored these drafts. The judge is the ten checks in `RUBRIC.md`.
- The applicant oracle answers "Not sure" when the fixture does not contain the fact and the hidden rule input was not asked. A person who knows the fact would answer it. Asking a useful question the fixture cannot answer does not raise the score.
- The ten checks do not grade prose. They grade the path, citations, which fields were asked, whether process fields were listed as evidence, Section C codes, compliance wording, silent fills, and whether the closing review says it is administrative.
- The code database was open. Section C is the lookup for the article the run committed. It is not a grade of whether that article was the right one, and it is not National Research Council sentence text.
- Demo path labels come from the case READMEs. `demo-a` is one of AFTER's 12 misses. Dev-case and rule-vector labels are mechanical.
- The procedures do not vary between runs, so there is no sampling error to compute. The limit is this set of 152 prompts and these ten checks.
- The comparison calls the path, process, and evidence functions and counts the questions those gates ask. It does not click through the browser.
- A passing completeness check is an administrative-gap list. It is not a finding that a design complies or is safe.
