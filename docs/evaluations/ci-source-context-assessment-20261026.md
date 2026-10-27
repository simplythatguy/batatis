# Why the CI tests need to reflect project and reference context

Assessment date: 2026-10-26. This report concerns [PR90](https://github.com/simplythatguy/batatis/pull/90) at head `857a4d2b91b0d31fd1c0239881af8fb1c8212a6b`, containing code commit `7f312229c8a906f9b26382ad4a2c9f5a426cd6d9` and base `9a09a1daa7619145908130f91e58db94f6776851`. Recommendations below are proposed work, not completed fixes. This report adds documentation and diagnostic evidence. It does not change production code, test fixtures, or workflow configuration.

## High-level explanation

### The tests assume an attachment always supplies project context

PR90 changes when attachment text can become an answer about the applicant's project. An uploaded PDF may contain a policy, an example, a consultant's address, or an earlier project. Finding an exact quotation proves that the words occur in the document. It does not establish that those words describe the current application.

The recorded policy requires positive project context before extracting project fields. Explicit project headings or supported first-person construction statements establish that context. Reference material ends it. Unknown passages remain available for document review and citations but cannot supply project answers or conflict questions. Completed mapped form fields have a separate path. This distinction is explicit in [ADR0002, lines 5-7](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/docs/adr/0002-use-what-the-applicant-gave.md#L5-L7).

Three failing test cases, two of them repeated across operating systems, use short synthetic PDFs without that context. Their assertions still require an attachment intake model call. Production code now deliberately omits that call for these inputs. The fixtures therefore fail to exercise the branches their tests intend to protect.

Updating these tests means restoring their preconditions while retaining their timeout and cancellation assertions. The observed failures do not establish defective CI infrastructure, and their repair does not require a workflow YAML change or runner upgrade.

### CI identifies a real verification gap

The inspected results are specific:

- The [engine job](https://github.com/simplythatguy/batatis/actions/runs/40367644816/job/121729576926) reports **1 failed, 4,145 passed, and 95 skipped**, taking **1,669.64 seconds** for pytest. Its sole failure is `test_service_partial_attached_page_failure_is_operationally_incomplete`.
- The [macOS desktop job](https://github.com/simplythatguy/batatis/actions/runs/40367644772/job/121729692308) and [Windows desktop job](https://github.com/simplythatguy/batatis/actions/runs/40367644772/job/121729692480) each report **228 tests, 226 passes, two failures, and zero skips**. Both fail the same ordinary-request and cancelled-request test cases.
- [Web](https://github.com/simplythatguy/batatis/actions/runs/40367644816/job/121729577455), [gitleaks](https://github.com/simplythatguy/batatis/actions/runs/40367644816/job/121729576235), and the desktop [Plan job](https://github.com/simplythatguy/batatis/actions/runs/40367644772/job/121729576918) pass.

Both desktop jobs fail inside **Typecheck and test the desktop host**. Their logs show typechecking completes and the test command produces the failures. Engine freezing succeeds earlier, but native engine regressions, app packaging, signing checks, and packaged-app acceptance do not run. Job names containing "Packaged desktop" must not be read as evidence that the packaged app passed verification. The [workflow order](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/.github/workflows/desktop.yml#L120-L146) and job step conclusions establish that limit. The failures shown are assertions, not operating-system symlink errors.

Release publication is intentionally disabled for pull requests. The [PR plan sets `release=false` at line 55](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/.github/workflows/desktop.yml#L54-L55), and [the release job requires `release == 'true'`](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/.github/workflows/desktop.yml#L264-L267). Its packaged dependencies also failed. A skipped release is therefore not another publishing defect to fix.

## Low-level trace

### Project classification suppresses the attachment intake call

The mechanism spans four small decisions:

1. [`context.py`, lines 18-45](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/intake/context.py#L18-L45), recognizes project headings and first-person cues. Neither failing PDF contains one. Words such as "proposed" alone are insufficient.
2. [`project_pages`, lines 48-79](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/intake/context.py#L48-L79), starts in `unknown`. It replaces excluded characters with spaces while preserving newlines and offsets. These fixtures produce no nonblank project text.
3. [`extract.read_file`, lines 268-280](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/intake/extract.py#L268-L280), supplies the scoped text to `read_text`. At line 277, the model transport is conditional on `text.strip()` and the model-page limit. Blank scoped text receives `transport=None`.
4. [`read_text`, lines 139-145](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/intake/extract.py#L139-L145), still reads citations from the original page but returns before the model call when transport is absent.

The page can still have a `read` receipt. "Read" describes access to its text, not acceptance of its contents as project facts. [Lines 298-301](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/intake/extract.py#L298-L301) add an explanation when no project passages or populated form fields were identified.

[`service.run`, lines 48-68](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/intake/service.py#L48-L68), first gathers rules, form values, and personal details, then performs model intake. Document review runs through a separate transport and source-reading path. It retains readable source content within its supported format and budget limits. Excluded project passages still contribute personal details to redaction. Project classification does not globally switch off document review.

### The desktop failures occur at different assertions

The Python fixture draws this single line into its PDF:

```text
Synthetic wall documentation. A novel cladding is proposed.
```

The fixture uses the production private bridge and intake route with a synthetic store. See [`request-lifetime.py`, lines 19-41](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/desktop/tests/fixtures/request-lifetime.py#L19-L41). The TypeScript test supplies a description, attaches that PDF, and records each host-provider task.

For the ordinary request, [line 315](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/desktop/tests/workflow-request-lifetime.test.ts#L303-L323) expects:

```text
["intake", "intake", "document-review"]
```

Both CI logs instead show:

```text
["intake", "document-review"]
```

The description reaches intake. The unclassified PDF does not reach attachment intake. Document review still runs. The ordinary test's assertion message says "a cancelled worker cannot reacquire provider authority", but that message is shared by both branches. This ordinary-case failure is not evidence of a cancellation leak.

For the cancelled request, the origin assertion correctly expects an empty call list. Execution gets past that assertion and the `engine.busy == 0` check. The fresh request returns HTTP 200, then fails at line 321 because its call list also lacks attachment intake. The missing task explains this failure without assuming that cancelled work regained authority.

The early failures matter. The ordinary branch does not reach its later busy-state or fresh-request assertions. Neither branch reaches the explicit clean-exit assertion after the fresh call-list check. These logs cannot establish that all lifecycle protections pass.

### The engine test never induces its intended timeout

[`test_r4_review_boundaries.py`, lines 126-141](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/tests/test_r4_review_boundaries.py#L126-L141), supplies `Attached record of wall dimensions.` as PDF text. Its synthetic intake callback raises `httpx.ReadTimeout` only when a request contains `Attached record`.

The description model call succeeds. The PDF remains unclassified, so the attachment callback never runs. The CI log shows the first assertion fails at line 139 with `assert (1 == 2)`. Its recorded request list contains only `Review the submitted building proposal.` This test does not configure document review.

Consequently, neither the `ReadTimeout` reason assertion nor the operational-completion assertion executes. The existing mechanisms remain relevant: [`model.run`](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/intake/model.py#L144-L158) records exception types, and [`Extraction.merge`](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/intake/extract.py#L50-L66) can retain a successful description status alongside a later attachment failure reason. [`checks.completion`, lines 99-107](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/evals_dev/data_prompts/checks.py#L99-L107), treats that combination as operationally partial. The intended expected marker is `intake_model:partial:ReadTimeout`.

### An existing diagnostic isolates the fixture precondition

The [saved offline diagnostic](ci-source-context-diagnostic-20261026.json) records the same production service with the synthetic PDF, without tracked edits:

- Without a project heading, calls are `intake` and `document-review`, and `project_pages` is empty.
- With `Project brief`, calls are `intake`, `intake`, and `document-review`, and `project_pages` contains page 1.
- The original engine test fails. Adding a project heading to its PDF input makes its existing assertions pass, including the timeout reason and partial-completion marker.

The diagnostic generated PDFs in memory and used injected callbacks instead of external AI providers. It also ran the existing engine test unchanged, then temporarily wrapped its PDF factory to prepend `Project brief: ` to the input. The original assertions all passed with that input variation, and the factory was restored afterward. The original test's `live` status is test metadata in this experiment, not evidence of a live provider call. The diagnostic supports the proposed fixture repair. It does not replace rerunning the desktop host tests or native acceptance.

## Recommendations and acceptance criteria

### Restore the intended branches and keep their protections

Give both synthetic PDFs an explicit `Project brief` heading and an actual statement about the project. Preserve the expected three-task sequence for ordinary desktop requests and fresh requests after cancellation. Preserve zero dispatches for the cancelled origin, zero busy operations, and clean engine shutdown. Give the ordinary assertion an accurate diagnostic message.

Retain the engine test's two-call assertion, attachment timeout, `ReadTimeout` reason, and partial-completion marker. Call counts are useful here because they prove that the targeted attachment branch executes. Replacing three with two, or weakening the assertion to "some calls occurred", would remove that protection.

Acceptance requires both desktop cases to reach all their assertions on macOS and Windows. The timeout test must demonstrate that its attachment callback executes and that a description success cannot hide an attachment failure.

### Cover excluded documents through the same boundaries

Add or extend reference, unknown, and mixed-document fixtures at service and desktop integration boundaries. Check that excluded passages create no project ledger facts or project conflict questions. Check that document review remains enabled, original-page citations remain available, and personal details stay redacted in outbound requests. For mixed documents, distinguish admitted project passages from excluded reference sections.

Build on [the existing source-context regressions](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/engine/tests/test_intake_source_context.py#L1-L176). A low-level classifier test alone cannot establish that the desktop bridge preserves request authority or that the final case ledger excludes reference facts.

### Verify in layers and report each layer accurately

Run a fast cross-boundary group first, including the timeout test and desktop request-lifetime tests. Then run the full engine gate on a supported environment and retain the native macOS and Windows matrix. [`scripts/verify.sh`](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/scripts/verify.sh#L44-L59) already defines full engine and desktop checks. [Ubuntu CI](https://github.com/simplythatguy/batatis/blob/857a4d2b91b0d31fd1c0239881af8fb1c8212a6b/.github/workflows/ci.yml#L76-L112) supplies PostgreSQL, official-source builds, and key-free evaluations.

Acceptance requires the full engine assertion failure to clear and both desktop jobs to proceed through their applicable native checks. Report skip reasons separately. Keep all gates enabled. Quarantining this known failure, stubbing `fcntl`, or publishing just to obtain a green result would leave the verification gap unresolved.

## Evidence limits and the separate product-policy question

Earlier local results of **217 engine passes with 16 skips** and **392 web passes with one skip** are recorded in `final-tests.log` and `verify-web-final.log`. The documented affected-test selection did not include the failing review-boundary test or desktop integration suite. Those counts remain valid for their selected checks, but do not establish a full passing gate.

Local full-engine attempts encountered MSYS Python without pytest, then 12 native-Windows collection errors for missing `fcntl`. Those are separate from Ubuntu CI's completed run with one assertion failure. Missing local `lsof` blocked ordinary app startup, not the remote jobs. The 95 CI skips cover unavailable reference sources, explicit live-provider opt-ins, and specially owned PostgreSQL clusters. They are not equivalent to the 16 local PostgreSQL-dependent skips. The raw CI records are `.data/source-context/ci-engine-failed.log`, `ci-macos-failed.log`, and `ci-windows-failed.log`.

Finally, conservative unknown-PDF handling creates a separate product question. A genuine applicant report without recognized structural cues can lose automatic project extraction. Assess that limitation with representative, separately evaluated inputs and an explicit business-policy decision. It does not justify making reference text authoritative to satisfy lifecycle fixtures. Conversely, repairing these fixtures does not prove universal report comprehension, live-model accuracy, or packaged-app correctness. Batatis supports administrative completeness review. None of these checks establishes technical code compliance or design safety.


## Concrete update scope

The smallest repair for the observed failures concerns these test inputs and assertions:

- `desktop/tests/fixtures/request-lifetime.py` needs an explicit current-project PDF fixture so the attachment intake branch executes.
- `desktop/tests/workflow-request-lifetime.test.ts` should retain the targeted dispatch, cancellation, fresh-request, busy-state, and shutdown assertions. The ordinary-request failure message should describe dispatch rather than cancellation.
- `engine/tests/test_r4_review_boundaries.py` needs a project-scoped PDF in the partial-timeout test so its injected attachment error actually occurs.
- Service and desktop integration tests need separate reference and unknown-document cases to prove that intentional exclusions do not become project facts or accidental provider failures.

The current evidence does not require weakening either `.github/workflows/ci.yml` or `.github/workflows/desktop.yml`. A separate improvement to local Windows interpreter selection and file-locking support could make complete local verification more reliable. That work should preserve real locking behavior and has different acceptance criteria from the fixture repair.

A passing fixture-only diagnostic is insufficient for declaring the PR green. The repaired tests must execute their complete assertions, the full engine job must pass, and both desktop jobs must finish their applicable acceptance steps. Any remaining skips or blockers must retain their individual explanations. The existing recorded PDF demo shows the project-field correction; it does not substitute for these integration checks.
