# Local validation of proposed CI criteria changes

Assessment date: 2026-10-26. Base commit: `e3d2fccb08ba96d8d270691549b46bc42c148bd5`. The initial assessment below records local validation before publication. The user subsequently approved committing and pushing this candidate to PR #90 for hosted CI verification; merge approval remains separate.

The candidate implements the fixture and checking changes proposed in the [CI assessment](ci-source-context-assessment-20261026.md). The criteria live in the tests that the existing CI jobs already discover. Workflow YAML and production code remain unchanged.

## What changes

- [The synthetic desktop PDF fixture](../../desktop/tests/fixtures/request-lifetime.py) explicitly identifies a project brief. Separate project, reference, unknown, and mixed documents test each source context.
- [The desktop request-lifetime tests](../../desktop/tests/workflow-request-lifetime.test.ts) preserve exact project dispatch counts, zero dispatch after cancellation, fresh-request recovery, idle-state checks, and clean engine exit. They test ordinary and cancelled requests for all four document contexts.
- The same desktop tests verify that project values survive, reference values do not become project answers or conflict questions, document review still reads reference content, contextual citations remain recorded, and private names and addresses stay out of provider requests. Both the ordinary response and the fresh response are checked. A saved-run readback verifies persistence.
- API responses enter the desktop test as `unknown`. Ajv validates the generated `IntakeResult` schema before semantic assertions. This avoids relying on untyped JSON or handwritten response shapes.
- [The engine review-boundary tests](../../engine/tests/test_r4_review_boundaries.py) give the attachment-timeout fixture explicit project context. The original two-call, timeout-reason, and partial-completion assertions remain. New reference, unknown, and mixed cases prove that document-review facts stay separate from project facts and that intentional extraction exclusions are operationally complete.

## Before and after

The before runs used the committed base without source edits. After runs used the local candidate. Commands returned real process exit codes captured alongside the logs.

- The original engine timeout regression changed from **one failure** to **one pass**. The timeout callback executes again, and all its existing assertions pass.
- The original desktop request-lifetime file changed from **9 passes and 2 failures** to **11 passes** after the fixture correction alone. The completed candidate adds six context scenarios and reports **17 passes, no failures, and no skips**.
- The complete engine review-boundary file reports **48 passes**. The expanded engine selection reports **265 passes and 16 PostgreSQL-dependent skips**. It includes intake extraction, PDFs, plans, document review, saved-case completeness, schema export, and evidence attachment checks.
- The full local desktop suite changed from **219 passes, 8 failures, and 1 skip** to **227 passes, 6 failures, and 1 skip**. Both target failures are gone. The same six protocol tests still fail during Windows symlink fixture setup with `EPERM`, before their protocol assertions run.
- The repository desktop typecheck and a strict standalone typecheck of the changed test file and its imports pass. Diff whitespace checks pass.

The desktop skip requires preparation of the pinned native Codex runtime for install-resolution testing. It is separate from the six symlink failures. The full local desktop gate remains failing and is not represented as green.

## Tests were checked against deliberate faults

The following faults were injected only into isolated diagnostic processes. Production files were not edited. Every fault made the corresponding new or preserved assertions fail:

1. Admit all attachment text as project text. Reference and unknown cases detect extra extraction, and mixed cases detect inappropriate project facts or conflicts.
2. Omit document review while reporting a live status. The tests detect that the review callback and quoted review fact are missing.
3. Bypass personal-data scrubbing. The tests detect synthetic names and addresses in provider requests.
4. Drop contextual citations. The tests detect the missing source, page, and citation records.
5. Lose valid project storey facts. The mixed-document case detects that the confirmed two-storey project answer disappeared.
6. Hide the attachment timeout reason. The original timeout test detects the missing `ReadTimeout` reason rather than accepting the successful description call as complete work.

A separate ignored copy of the desktop test injected permissive extraction inside its synthetic private-bridge process. All **six reference, unknown, and mixed desktop cases failed through assertions**. The failure was not a module-load or setup error. This establishes that the new desktop criteria can reject the original class of cross-document mistakes.

These experiments demonstrate sensitivity to specific faults. They do not prove universal correctness or measure live-model accuracy.

## Independent review

Specification review found no material gaps and independently ran the 48 engine boundary tests and 17 desktop request-lifetime tests successfully. Standards review initially found an untyped response boundary. The candidate now uses the authoritative generated schema and typed validator. A fresh review found no remaining standards or specification findings and confirmed that malformed responses are rejected.

## Remaining verification limits

The full engine gate was attempted with the installed native interpreter and original CodeDB and variance form. Collection stops on **12 existing `fcntl` import errors** in evaluation tooling on native Windows. No locking behavior was stubbed. This is separate from the single Ubuntu CI assertion failure diagnosed in the original assessment.

The full desktop gate was also attempted. Typechecking passes, but its test step still stops on the six existing symlink-permission failures. The ordinary native macOS matrix and packaged-app acceptance have not run for this local candidate. The 16 PostgreSQL-dependent engine checks remain skipped locally.

The production engine, desktop runtime, CI job definitions, and verification script have no changes in this candidate. No gates, assertions for the original project/cancellation/timeout cases, or test files were disabled to obtain the targeted passes.

## Approval and next validation

The candidate is ready for review of its local diff and evidence. The user approved committing and pushing it to PR #90 after reviewing these findings. That publication can trigger the hosted Ubuntu engine job and the native desktop matrix on the actual candidate.

Hosted verification is still required. Publication approval does not imply merge approval or a claim that all gates are green. If hosted checks expose another failure, investigate it and preserve the relevant protections before recommending merge.

## Local evidence

Raw logs, process receipts, fault-experiment summaries, and the proposed test patch are retained in `.data/ci-criteria/`. They are ignored local artifacts. The compact receipt is `.data/ci-criteria/findings.json`.

The command families used were:

```sh
python -m pytest -q engine/tests/test_r4_review_boundaries.py
node --experimental-strip-types --import ./desktop/scripts/register-ts.mjs --test desktop/tests/workflow-request-lifetime.test.ts
scripts/verify.sh --desktop
scripts/verify.sh --engine
```

The expanded engine run additionally selected the intake, schema-export, saved-case completeness, and evidence-file tests. Engine runs used the available CodeDB and official form. Desktop runs used the installed engine interpreter through `BATATIS_DESKTOP_PYTHON`. For the full engine script, a shell function selected that native interpreter instead of the MSYS Python without pytest. Neither selection changes the tests or their criteria.

The SHA256 of the proposed three-file test diff is `68090e38d0c2c79e2711cf0ef4fc592b03e4a67bae716ce0c30f729004d90d90`. This hash identifies the reviewed test-only diff against the assessment base, before merging newer main changes for publication.

## Publication follow-up

The user approved publication on 2026-10-26. Latest main `544b10839b00323050760b88f247bc72b479cc52` was merged without conflicts at `79d0e1b8f5c895cb4930c93d5b3c77a2951e544c`. Post-merge validation passed: **280 engine tests, 16 PostgreSQL-dependent skips**, including the new main branch's case-input and requirement-route integration tests; **17 desktop request-lifetime tests**, no failures or skips; strict standalone test typechecking and diff whitespace checks. The original full native-Windows gate limits above remain unresolved. The desktop test process returned zero; the local receipt printer subsequently encountered a Windows console Unicode encoding error, which did not affect that test result. Hosted CI must still verify the published revision. No merge is authorized.