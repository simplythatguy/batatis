# Independent code review — accuracy95 R1

## Result

Four actionable findings: two P1 and two P2. The strongest issue is that the new path removes semantic file facts from the applicant-facing intake flow while the evaluation renderer still scores those facts as visible output.

## Review pin and boundary

Base commit: `e5e794b6ab828afdfc52858cf3ed75d39e62a73c` (resolved from `e5e794b6`). All nine entries in `.dpe-cache/code-review-pin.json` matched their SHA-256 values at review start and close.

| Pinned file | SHA-256 |
|---|---|
| `engine/intake/service.py` | `2c457721dbe0c65e6f45472bedc07ee601f1c91298a78a90092701848141ab60` |
| `engine/tests/test_intake_review_pipeline.py` | `8fa6e4d98b7d7004f4da2dd1c15570cc78e6d877eb483a5947d33cbe13b9150e` |
| `evals_dev/codex_transport.py` | `32839f7b9c44433b87da62fc1844e09c8b0fe6251ca5aedbae4b419cdf57fdae` |
| `evals_dev/luna_accuracy.py` | `0fc0919c573a987a901749667367ff8839b51e5f6fa774b57532b832f26b49ac` |
| `evals_dev/data_prompts/judge.py` | `cb5cecadae33e755f7bdf6f7b5b2a07efe96d31fb55de7da15af31754c5ea7ee` |
| `evals_dev/tests/test_codex_transport.py` | `cb6f64033d23a86429e1bd9d8f0b7f41cab86ca3b302a5c9c2180b060f2299d9` |
| `evals_dev/tests/test_luna_accuracy.py` | `729a8b632018a0541ae9dd550ef9b677daa56b776ceff7c4790d3dd21eeb76b2` |
| `evals_dev/tests/test_corpus_input_policy.py` | `c82159e3de470b5141f6be15c8c7358995522ea2c16be280591317ec275305e4` |
| `Data Prompts/_tools/assemble.py` | `362884330e3dfd56d7a7bdf98d3ecb89bfcd689536cf202fa4fb3a471f7c8b31` |

Reviewed only those pinned files plus the necessary intake, scoring, corpus-grouping, rendering, and web intake callers/consumers. I did not inspect mutable corpus metadata or attachment contents. No source files were changed; the only intentional workspace write is this report. No API or model calls were made.

## Findings

### [P1] The skipped file pass hides semantic file facts from applicants while the evaluator credits them

**Location:** `engine/intake/service.py:64-73`; `engine/routes_intake.py:100-102`; `web/src/intakeView.ts:114-119`; `evals_dev/data_prompts/render.py:46-64`; `evals_dev/luna_accuracy.py:156-158`.

**Trigger:** A complete review finds a file-only fact that deterministic extraction does not map to a field, such as the test's proposed soffit projection. `complete_review` then disables the file model pass. The fact stays under `IntakeRecord.review.facts`; it is not converted into an intake `Fact` or returned in `IntakeResult.facts`. The web intake cards are built from case/intake facts and do not consume `record.review.facts`. In contrast, `render.report()` includes those review facts, and the Luna runner grades that report.

**Consequence:** The user cannot confirm or correct the semantic file fact in the intake flow, and it is absent from `case.facts` used by the plan and identification path. The local score can still count it as covered because the evaluation renderer includes it. That makes the diagnostic score more favorable than the applicant-facing app behavior. Preserve a user-visible, evidence-linked path for these facts (or retain file extraction until one exists), and score only content the app actually surfaces.

### [P1] The frozen run does not freeze index metadata used by the per-city target

**Location:** `evals_dev/luna_accuracy.py:61-80, 182-188`; `evals_dev/data_prompts/corpus.py:93-102`.

**Trigger:** After `freeze`, `Data Prompts/index.json` changes a selected case's `city_or_town` while its prompt, attachments, `source.json`, `evaluation.json`, and split assignment remain the same. `selected()` checks the split map and selected prompts/attachment hashes/reference files, but does not hash `index.json` or compare the `Case` metadata loaded from it. City is read from that index and does not affect the split computation.

**Consequence:** The subsequent score silently re-buckets the case in `by_city`; because the 95% target is checked per city, a metadata edit can change whether `check_coverage_target_met` passes without invalidating the frozen experiment. Freeze and validate the selected case metadata (or the relevant index digest) alongside the current prompt/reference/input hashes.

### [P2] Existing result files are accepted without binding them to the frozen run

**Location:** `evals_dev/luna_accuracy.py:122-138, 142-149`.

**Trigger:** A run directory has `results/<case_id>.json` but no `manifest.json` when `freeze()` starts, or a result file is copied from another experiment. `freeze()` rejects only an existing manifest; `resume()` treats result-file existence as completion, and `grade()` reads it without checking its `case_id`, frozen input hashes, model/options, or task/request identities.

**Consequence:** A stale result can bypass the current model workflow and be graded against the new run's references, despite the transport itself correctly binding response files to a request hash, provider, model, options, and task ID. Store and validate a result fingerprint tied to the manifest and case inputs before reusing or scoring cached results.

### [P2] Unread source inputs are always reported as zero

**Location:** `evals_dev/luna_accuracy.py:172-188`; consumer `evals_dev/data_prompts/score.py:59`.

**Trigger:** A live document review has a deterministic `not_read` flag for a scan, unreadable file, or pages outside the review budget. The runner records `review_status` but never adds the `unread_input` field that `score.summarize()` reads.

**Consequence:** `cases_with_unread_input` is always zero for this runner, and `check_coverage_target_met` can pass without showing that some source pages were unavailable. Propagate the unread-input state into each score row and report it separately from answer accuracy; decide explicitly whether it should also block the diagnostic coverage target.

## Checks that passed review

- `PendingCall` escapes broad `Exception` handlers, so pending T3 work is not recorded as a successful fallback. The transport checks the request hash, provider, model, options, task ID, and payload shape.
- The runner supplies the Codex transport to intake, review, identification, and judging; the runner's manifest and summary leave usage/cost unknown. I found no path from this runner to the OpenAI HTTP transport.
- Missing engine output and pending judges remain in the expected denominator. The strict judge validator fails closed for malformed, missing, duplicate, or unverified verdicts; invalid cases cannot satisfy the target.
- Corpus assembly and `source_groups()` apply the same explicit `included_in_default_input` value and the same legacy role fallback.

## Verification

Focused offline tests, with the requested code database environment:

```text
BATATIS_CODEDB=/Users/aamia/.t3/projects/batatis/codedb/build/codedb.sqlite \
  /Users/aamia/.t3/projects/batatis/.venv/bin/python -m pytest -q \
  engine/tests/test_intake_review_pipeline.py \
  evals_dev/tests/test_codex_transport.py \
  evals_dev/tests/test_luna_accuracy.py \
  evals_dev/tests/test_corpus_input_policy.py
15 passed in 0.39s
```

No separate pre-existing finding was identified in the reviewed behavior. The production-accuracy limit is correctly explicit: the runner records a local Codex diagnostic, sets `production_accuracy_established` and `target_met` to false, and does not certify hosted-app accuracy.

## Methods used

- Project contract: `AGENTS.md`.
- T3 workflow route: `/Users/aamia/.codex/skills/t3-workflow/SKILL.md` and `/Users/aamia/.codex/skills/t3-workflow/references/routes.md` — Code Review route.
- Matt Pocock method: `/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/code-review/SKILL.md` — standards and requested-behavior review. Its normal parallel reviewers were not used because this task explicitly forbids delegation.
