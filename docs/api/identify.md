# Requirement identification API

Identification finds source-backed requirements to address in an Alberta
alternative-solution application. It does not determine technical correctness,
equivalence, safety, or approval. See the [requirement contract](../identification/requirement-contract.md)
and [coverage evaluation](../evals/requirement-coverage.md).

## Production profile

The checked-in profile uses `screen=requirements`. It searches complete indexed
NBC(AE) 2023 second-printing passages across Divisions A, B and C, retains
unresolved discoveries, and follows code references. Rank is an ordering, not
permission to discard a requirement. This profile requires no model requests and
has no keyword fallback that loses exact article identifiers.

Source verification and applicability are separate. Verified citations and quotes
establish where text came from, not whether it applies. The machine-readable
requirement ledger records discovery evidence, dependencies, application role and
review state. Missing corpora, unread tables and unresolved conditions remain
coverage gaps. The legacy `articles` projection contains Division B cards; use the
ledger for requirements across divisions. It is not an exhaustive applicability
determination, even when every indexed article was searched.

The legacy provider screens and bounded shortlist remain explicitly selectable
for diagnostics. Their historical calibration and metrics do not transfer to the
requirement profile. The new profile does not produce relevance probabilities or
replace a historical relevance record with invented scores.

Configuration resolves dataclass defaults, then `engine/identify/pipeline.json`
(or `BATATIS_IDENTIFY_CONFIG`), then `BATATIS_IDENTIFY_<FIELD>` overrides. Record
`trace.config_hash` with every capture. Inactive historical options are not
production retrieval cutoffs.

## Inputs and updates

POST reads the current fact ledger and supported attachment text, including
plans-only applications. Confirmed facts, answers, uncertainty, and document
origins are retained. A later unconfirmed value cannot erase a conflicting
confirmed value. Unsupported files, image-only pages, and reader limits are
explicit input coverage gaps.

`input_sha256` covers active facts, jurisdiction, attachment inventory and bytes.
GET checks it and the current corpus identity without a provider call or a write. Title changes and generated
results do not invalidate it. Raw fact or file changes make the result stale;
POST recomputes it. Intake and intake-answer updates refresh the local profile
inside the existing save transaction. The reusable input composer and `refresh`
function are available to other mutation owners. Saving and job lifecycles remain
owned by their existing modules.

## Routes

Owner edits and existing access controls apply. Every mutation uses the existing
compare-and-swap contract: a concurrent case change produces 409 without retrying
against a newer snapshot. Responses carry `case_version`. Supply it as
`expected_version` on the next mutation. Changed attachment inputs detected during
a run also produce 409. GET never calls a provider.

- `POST /cases/{id}/identify`: optional `prose`, `answers`, `expected_version`.
  Prose supports up to 2,000,000 characters; input is not silently prefix-clipped.
  Answers must identify an issued question and may fill only its own field.
  Empty applications without usable facts or readable plans return 409.
- `GET /cases/{id}/identify`: saved result with current staleness and decisions;
  404 before any result exists.
- `POST /cases/{id}/identify/{provision}/decision`: legacy `yes`, `no`, or
  `not_sure` departure response. `yes` adds a source-validated Division B
  benchmark to `provisions` and rebuilds Section C. Withdrawing a departure does
  not remove a supporting requirement from the requirement ledger.
- `POST /cases/{id}/identify/confirm`: source-validates an explicit Division B
  provision selection and rebuilds Section C.
- `POST /cases/{id}/identify/benchmark`: source-validates the selected article or
  sentence and records an applicant-confirmed departure. Objective and function
  statements remain deterministic lookups.
- `POST /cases/{id}/identify/requirements/{requirement_id}/decision`: records
  `disposition` (`include`, `exclude`, `review`), `role` (`varied`, `supporting`,
  `admin`, `conditional`, `unresolved`), a nonempty `reason`, and required
  `expected_version`. It rejects stale inputs and a changed or unavailable code
  source. This decision governs the ledger's application scope; it does not
  silently write a new departure or Section C benchmark. A `varied` role is only
  available for Division B. Use the benchmark endpoint to confirm its departure.
- `GET /cases/{id}/identify/information-request`: legacy unresolved departure
  decisions, separate from the officer's sent information requests.
- `GET /cases/{id}/process-refs`: two historical compatibility process rows;
  this endpoint is not the full administrative requirement ledger.

JSON and the existing `Accept: text/event-stream` transport return the same final
result. SSE stage events contain counts/status, not applicant prose. The existing
rate limit, access rules, privacy redaction and source attribution remain in use.

## Accounting and verification

`trace` records the actual method, source/config provenance, stages, requests,
tokens, cost availability and elapsed identification time. Zero provider calls
means zero model request spend for that identification. It does not mean intake,
professional review or hosting is free. Missing provider cost is unknown, never
silently zero. End-to-end captures separately measure the complete call interval.

Run from the repository root with its installed Python environment and CodeDB:

```sh
python -m pytest -q engine/tests/test_requirement_identification.py engine/tests/test_identify_case_input.py engine/tests/test_requirement_routes.py evals_dev/requirement_bench
python -m engine.schema_export --check
scripts/verify.sh
```

No app server or provider credential is required for those requirement tests.
For app operation use `scripts/local-app.sh` and only ports 3000 and 8000.
The [historical report](../accuracy/report.md) is an archive, not a current
requirement-completeness score. No expert-verified exhaustive accuracy result is
claimed by this change.
