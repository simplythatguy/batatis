# Applicant drafts

Batatis drafts the applicant's explanations. It does not produce professional analysis, calculations, test results, opinions of equivalence or seals. Draft acceptance records the applicant's ownership of the wording, not a technical finding.

## Interface agreed for implementation

`Case.drafting` stores the latest drafting record, including its source snapshots, input fingerprint, generation metadata, registry searches, notices and draft history. It is separate from `Case.facts`, Section C attributions and supporting evidence. Reading a case never generates writing.

- `POST /cases/{id}/drafts` takes `{expected_version}` and produces the writing from the saved description, latest source facts, readable owned document pages, confirmed provision text and deterministic Section C, reviewer guidance and precedent structures. It returns the full saved Case.
- `POST /cases/{id}/drafts/{draft_id}/decision` takes `{expected_version, decision: "accept" | "reject"}` and returns the full saved Case. Acceptance and rejection use compare-and-swap, enforce applicant edit access and reject stale input. Neither accepts client-authored draft text or sources.
- `GET /cases/{id}/drafts` returns the record with current staleness, without provider requests.

Each draft has `id`, `field`, `title`, `text`, `claims`, `questions`, `status` (`draft`, `accepted`, `rejected`), and decision metadata. Fields are `alternative_description`, `process.rationale`, `process.risk_assessment`, `process.mitigating_measures`, `process.assumptions_and_limits`, `process.maintenance_operation`, `process.qualifications`, `section_c.<provision_id>.explanation`, and `evidence_plan`.

Each claim has `text`, `kind` (`fact`, `assumption`, `plan`) and `sources`: exact `{source_id, quote}` references into the record's `sources`. A source snapshot identifies its kind, reference, page where applicable, label, text and optional public URL. Source quotations are checked against the actual supplied text. Assumptions remain visibly labelled; requested work is a plan, never a report of completed work. Missing facts are explicit questions with `routed_to` (`applicant` or `professional`), rather than fabricated prose or placeholders.

On acceptance, the server writes one confirmed applicant-owned fact at the draft's canonical field, with `kind: "pointed"`, `source.type: "user_click"`, `source.ref: "applicant-draft:<draft_id>"` and `source.quote` equal to the accepted text. The retained draft preserves claim-level provenance and the original generated wording. Section C lookup rows and evidence completion never change as a consequence of accepting writing. Rejection writes no answer. Repeated decisions are idempotent; a contrary decision requires a new draft.

Generation excludes prior generated/accepted draft prose as evidence for new claims. A fingerprint binds drafts to input facts, confirmed provisions and owned document bytes; regeneration does not silently overwrite accepted answers. Provider errors, unread pages, truncated context and registry fallback are explicit. A registry match is a discovery lead requiring a scope/status/edition check, never product acceptance or evidence of project equivalence.

## Adjacent threads

The application workspace may render, edit or highlight `claims` and source references. An edited answer remains applicant text and must retain its relation to the draft if it is presented as a revision. The question flow may consume `questions` without adopting this thread's presentation or ordering. Finding codes continues to own provision discovery/selection; drafting only reads the confirmed selection and deterministic lookup results.

The current UI supplies generation and accept/reject actions within the existing flow. It adds no rewriting editor and changes no question-order policy.

Implementation details and verification results will be added as the interface is exercised.
