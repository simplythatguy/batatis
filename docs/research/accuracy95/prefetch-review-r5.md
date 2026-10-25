# Parent request-preparation review (R5)

## Finding

- **P2 — The preparation count can silently omit failed calls.** In [`prefetch-v5.py`](../../../.dpe-cache/codex/prefetch-v5.py#L22), the sequence records a request only when the transport returns a response or raises `PendingCall`. Ordinary transport errors are caught inside intake [`model.run`](../../../engine/intake/model.py#L150) and review [`run`](../../../engine/intake/review.py#L684), which return failed states. `prepare()` discards the `Extraction`, and `--prepare` writes only `len(sequence)` per case. A bad saved request/response or write error can therefore leave a request out of the reported total without a failure count or completeness assertion. This does not put the temporary payload into a result, but the preparation total alone is not proof that every attempted call was staged. I observed no such failure among the seven A03-003 receipts checked below.

## Request independence and isolation

- The preparer calls the real `service.run` builder with the case prompt, ordered attachment bytes, `Codes()`, `scrubbed`, and the real intake/review transports. `service.run` first makes a no-transport rules/form pass; the per-page intake skip set and global personal-value list come from that pass. Intake then follows parsed text-page order and limits model calls to the first `MODEL_PAGES` pages. No earlier model response selects a later page or changes a later request.
- Review scrubbing is derived from the request, file names, and source page text. Its page-budget selection uses the scrubbed request and source pages. It does not use intake/model output. The temporary extraction returned by `service.run` is discarded by `prepare()`; it is never applied to a `Case` or sealed as a result.
- `Prepare` catches only `PendingCall`, records the request-directory hash, and returns `{'facts': []}` so preparation can continue. That placeholder can make the discarded extraction look `live`, but it is not written as `response.json`. In the actual runner, a missing response raises `PendingCall` through the engine; `resume()` counts it as pending and writes no result. Saved responses still pass `CodexTransport` identity checks and the normal engine intake/review handling. Identification and completeness judging are absent from `prepare()`; they remain in `run_case()`.
- `luna_accuracy.selected()` loads corpus records with reference fields, but this preparer passes only `case.prompt` and attachment bytes to `service.run`; it does not pass reference facts, review focus, or expected outcomes to the transport. The preparer writes request files and `prefetch-log.json` under the local cache; it does not alter the frozen manifest or result files.
- The request key covers the exact system/user/schema plus provider, model, and options. The transport requires a response to carry that key and the expected Codex model/options; result receipts bind the request and response file hashes. This prevents an accidentally mismatched request/response from satisfying a different actual request. The local receipt scheme is not a cryptographic attestation of the T3 task itself, and this review did not verify task IDs against T3.

## Cold-proof receipt check

The preparer’s `--proof` path compares the ordered source-only request hashes with the intake/review hashes consumed by the sealed A03-003 result and asserts that the fresh proof directory contains no saved responses. The supplied run record says that comparison passed. I did not rerun it. I extracted only the actual request identities and receipt digests from that result; I did not inspect request or response payloads, case output, scores, references, or holdout errors. The seven actual identities are:

| Order | Stage | `request_sha256` |
|---:|---|---|
| 1 | intake | `7b9da1e3b00311e8352873f58473190b931a7c4971c8d8b5392b04acd0b78387` |
| 2 | intake | `bedab70bae0c0bc0d4c2901a4b461bf49781ec514ab5013e5db90e8369845e19` |
| 3 | intake | `b1ca1a897b5c6e40806e1ff413e57e0c678a89fd3007bda363142dc76becf145` |
| 4 | intake | `6e1da171b51cfbe4b5e99954817507b4723fc5b36dd6454050bc973cee9d4784` |
| 5 | intake | `5737846ab684874e36838b7a5e4e4608e189c482113d71b030d68ea222e7f8f3` |
| 6 | intake | `549c299c4cc1c94bf74a5afe6099630142dc6e0c082622fe9dcee69e6d92b631` |
| 7 | review | `d10f6737721a874959d9e897a8ac093276e1a7b5ab769f6862625938a5feeece` |

For all seven, recomputing the request identity matched its directory key; the request-file digest and response-file digest each matched the sealed receipt (7/7). This independently checks receipt binding, not model quality. The prepared-versus-consumed sequence comparison is from the supplied prior run record; this review did not reproduce that run.

## Limits and checks

- This is a request-preparation review, not an accuracy measurement. It provides no evidence for or against a 95% score, and does not verify the corpus-wide 25-case / 313-logical-request tally. The cold receipt check covers A03-003 only.
- No resume, grade, provider/API call, test, browser, or port was run. No source or test file was changed. The only write is this review document. Unrelated shared-worktree changes were left untouched.
- The workflow maintenance check for T3 `0.1.2-nightly.20261021.3499` reported local status `healthy`, no issues, and compatibility `not_certified`.

## Reviewed revision and file hashes

Worktree `HEAD`: `e5e794b6ab828afdfc52858cf3ed75d39e62a73c`.

SHA-256 of the exact worktree bytes reviewed:

| File | SHA-256 |
|---|---|
| `.dpe-cache/codex/prefetch-v5.py` | `fa2bd85ba56cb5f22dfc75d76eaf4d57adc16a3b2fd7d482b8e8ec9dcedf2def` |
| `engine/intake/service.py` | `91f544ae4ebbafefcbbef4d45bcd66f4037ccfb530ee123b84b4a1e5c195677a` |
| `engine/intake/extract.py` | `3c9941c02006c9ab0ed448c92ecaf724a0a9c711ad221bcfb593ebd1a30e441e` |
| `engine/intake/model.py` | `72de1c4a92ac6abc90996eb8e92b3c89f347aca8357b4771fc3ada3a27aae948` |
| `engine/intake/review.py` | `65442fb19c80d0b00ff9611e562101342153cb59d99a946e573ebff2a8edb026` |
| `evals_dev/codex_transport.py` | `8578e5a266531eb1d56eeef2c2f2e373430239a4d071de91b11a7168b2777fc7` |
| `evals_dev/luna_accuracy.py` | `2404f83d3a3336e4de23940359c0f90e2f3afc17cf8067498063727e1e07d113` |

## Methods used

Matt Pocock, `engineering/code-review/SKILL.md` (scoped behavior/correctness review at pinned worktree hashes); pstack, `benchmark-checklist/SKILL.md` (kept request-preparation evidence separate from an accuracy claim). Routed by the installed T3 workflow and its `references/routes.md`.
