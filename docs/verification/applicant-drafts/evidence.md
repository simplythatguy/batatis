# Applicant drafting evidence

The implementation prepares source-linked applicant writing and requires an explicit decision before it enters the answer ledger. This evidence separates interface behavior, persistence checks and writing quality.

## Interface walkthrough

[Recorded walkthrough](media/interface-demo.webm), [desktop screenshot](media/desktop.png), [phone screenshot](media/phone.png).

The recording shows the actual `ApplicantDrafts` component under the production `CaseProvider`, compiled from the branch, with **simulated API responses and synthetic wording**. Its visible banner labels that limitation. It demonstrates opening a claim's sources, accepting the proposed alternative, retaining the source/question display, choosing another piece and rejecting it without adding an answer. It does not demonstrate live text generation, HTTP/provider integration or professional correctness.

The visual implementation is the signed-in panel at `e8862ca43d542f188834849e4c8018dbebeb8651`. The walkthrough ran at `873c54be` with the same visual source. Desktop (1440 × 1000) and phone (390 × 844) fixture interactions passed acceptance, rejection, source-retention and JavaScript-error checks. Scoped Lint Apple 0.1.20 page checks found no findings under the project's typography and control policy. Layout annotations and an automated keyboard interaction plan were absent; these are coverage limits, not passes.

T3 screenshot capture timed out twice with `Preview automation snapshot timed out after 15000ms`. T3 recording start also timed out twice with `Preview automation recordingStart timed out after 15000ms`; no T3 recording path was returned. The fallback used the browser's built-in recording with the existing local Chromium/FFmpeg, without starting another application server. The saved 8.28-second WebM was inspected through seven extracted frames covering the initial state, sources, acceptance, piece selection and rejection. That frame-based inspection does not establish motion or timing quality. The exact saved desktop and phone images were separately inspected.

## Live writing quality

The raw-input manufacturer attempt at `52f4ec3365fb21b6dce735bbf6c5c1d7c7ef121e` failed before generating writing. The provider returned HTTP 429: **“You have no credits remaining.”** A separate diagnostic request confirmed the same provider error. The application returned 503 and saved no writing. No other cases or quality-judge calls were attempted after that account-level blocker was established.

Consequently **zero of the four planned cases has verified live writing quality**. Scripted transport tests and the interface fixture are not substitutes for that acceptance requirement. The three raw demo cases and a clearly labelled synthetic BTRboard surrogate are prepared by `scripts/eval_applicant_drafts.py`; its generator inputs exclude answer keys and completed export narratives. The local organizer package names continuous sheathing insulation followed by “Details coming soon,” so the actual organizer worked example was not available. The surrogate cannot establish acceptance of that missing example.

See [the evaluation protocol](../../../evals/drafting-protocol.md) and [the data contract](../../api/applicant-drafts.md) for generation inputs, source validation, professional limits and adjacent-thread interfaces.
