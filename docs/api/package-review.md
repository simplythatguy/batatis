# Officer package review API (WP-34)

The package review checks a variance application for **administrative completeness** only. It reads a
Batatis case, or an uploaded SCC variance form (fillable or flattened) with its attachments, and lists what is
present, blank or not found. It **never fills a missing item, never states compliance, and never writes risk,
mitigation, assumptions or the officer's decision**. Every response carries `administrative_only: true`,
`not_a_compliance_determination: true` and a notice.

In the officer's process (accept, refuse, or **request more information**), the drafted information request
below is the **request-more-information** path. Accept and return are #48's decision route
(`POST /review/{case_id}/decision`); refuse is not part of this backend.

Wire types: `ReviewSession`, `PackageReviewIndex`, `CloseOut`, `SentInformationRequests` (responses) and
`InformationRequestEdit` (request) in `web/src/api/types.gen.ts`. Models: `engine/models_review.py`. Code:
`engine/review/`, routes `engine/routes_package_review.py`.

## Routes

| Route | Who | Behaviour |
| --- | --- | --- |
| `POST /review/{case_id}/package-review` | Claimer (current claim, status `in_review`) | No body (or `{}`): review the saved case. `multipart/form-data` with one or more PDFs (any field name): review the uploaded package. 201 `ReviewSession`, next version; `diff` against the previous version. 409 without the claim; 503 `code database not found` for a saved-case review without codedb; 409 `case was updated concurrently` if the case changes during the review. |
| `GET /review/{case_id}/package-review` | Any reviewer of the case's authority | `PackageReviewIndex`: session summaries (version, author, open gaps, diff statement, sent time), the latest session, and `close_out` when decided. |
| `GET /review/{case_id}/package-review/{version}` | Same | One `ReviewSession`. |
| `PUT /review/{case_id}/package-review/{version}/information-request` | Claimer | `{"intro"?: str, "items": [{"id"?: str, "text": str, "included": bool}]}` replaces the item list in that order. Items with an existing `id` keep their finding link (reworded text becomes `authored_by: "officer"`); items without `id` are officer items. Unknown id 422; after sending 409. |
| `POST /review/{case_id}/package-review/{version}/information-request/send` | Claimer | Posts the included items to the case thread as a message from the reviewer (each item as a structured `DecisionItem`), so the applicant gets the usual #48 notification. Freezes the request. 409 when already sent or nothing is included. Does not change status or record a decision. |
| `GET /cases/{case_id}/information-request` | Owner, or a reviewer of the authority (central guard, read mode) | `SentInformationRequests`: only requests that were sent. Drafts are never shown. |
| `GET /review/{case_id}/close-out` | Any reviewer of the authority | `CloseOut` for a decided case (see below); 404 before a final decision. |
| `POST /review/{case_id}/close-out/sent` | The reviewer who recorded the decision (or the claimer) | Records the officer's statement that they sent the copy to the Council. Batatis sends nothing. 409 when already recorded for that decision. |
| `POST /package-review` | Reviewer | Standalone third-party package (no Batatis case): multipart PDFs. 201 `ReviewSession` with a new `package_id` (`pkg_…`), scoped to the reviewer's authority. |
| `POST /package-review/{package_id}` | Reviewer of that authority | Re-upload: next version with `diff`. |
| `GET /package-review/{package_id}` and `/{version}` | Reviewer of that authority | Index and one session. |
| `PUT /package-review/{package_id}/{version}/information-request` | Reviewer of that authority | Edit; the text is copied out by the officer (no applicant account to send to). |
| `POST /cases/{case_id}/completeness` | Ported saved-case report (`batatis.completeness.v1`) | See "Saved-case completeness report". |

Access: `/review/{case_id}/…` handlers apply the central `authorize_case(..., mode='review')` first, so
applicants, other authorities and anonymous callers get **404** (unowned legacy cases have no reviewer
workflow and also 404), then require a reviewer account. Standalone routes return 401 signed out, 403 for
non-reviewers, 404 for another authority's package. Uploads: at most 12 files, 4 MB in total
(`413` above), `415` when the body is not multipart. Uploaded bytes are read in memory and not stored; the
session keeps the extracted values and quotes.

## A session

- `files[]`: name, sha256, size, pages, `role` (`scc_form_fillable`, `scc_form_flattened`, `attachment`,
  `unreadable`, `case_record`), `form_version` (field map, e.g. `scc_2026-10`), note.
- `fields[]`: one row per form field (the form's own widget names, typos included) and per applicant passage
  read from the appendix or attachments (`alternative_description`, `rationale`, `risk_assessment`, `mitigating_measures`,
  `assumptions_and_limits`, `professional_name`, `professional_qualifications`). `status`:
  - `present`: the exact text read (`value`).
  - `blank` (certain): a fillable field with no value; a flattened box with no text on a page whose text layer
    matches the blank form and with nothing else drawn in the box; a heading with nothing under it; a saved
    case with no value.
  - `not_found` (ask the officer): a page without a text layer, handwriting/image/stamp in the box, a check
    box or signature on a flattened form, an unrecognised layout, a passage whose heading was not found.
  Every row has a `pointer`: file, 1-based page, `form_field`, `bbox` (PDF points), `quote`.
- `findings[]`: `key` (stable across versions), section (`A`–`D`, `process`), field, label, `status`
  (`blank`, `not_found`, `missing`, `unclear`), `problem`, `defect_class` (planted SPEC D01–D16 where it
  applies), message, severity, `routed_to`, `pointers[]`, `citations[]`.
- `documents[]`: the supporting-documents panel. One row per attachment (and per Section D row with no matching
  upload): `title`, `type`, `issuer`, `date`, `evidence_rung` (the `engine.section_d` evidence type the document
  says it is), `seal` (`seal stated in text (not verified)` or unknown), `responsible`. Each cell is
  `{value, known, source}`; `value` is `"unknown"` when nothing labelled was read. Never a guess.
- `citations[]`: every provision cited on the form or in attachments, verified through codedb: `exists`,
  `edition_ok`, `page_ok` (when a page is cited), `canonical_citation`, `pdf_page`, validator `issues`.
  Without codedb, `lookup_skipped: true` and each check carries a `lookup_skipped` issue.
- `section_c[]`: each form row compared with the Division B attribution table: `match`, `mismatch` (message
  names the form's values and the table's pairs), `no_table_row`, `provision_not_found`, `not_checked`
  (e.g. values continue in an appendix).
- `information_request`: `intro`, `items[]` (`id`, `finding_key`, `text`, `authored_by`, `included`,
  `officer_check`), `edited`, `sent_at`, `sent_by_name`, `message_id`, `text` (numbered, ready to copy).
  Items are generated deterministically from findings; each one asks the applicant ("Please provide …",
  "Please confirm …"). Not-found findings become items with `officer_check: true` and `included: false`: the
  officer looks first. Officer-routed findings (unreadable files, the peer-review signal, the officer's own
  Div C 2.3.1 registration documentation) are never asked of the applicant.
- `diff` (from version 2): `resolved`, `still_open`, `new` (by finding key) and `statement`, e.g.
  `"2 of 3 gaps resolved, 1 still open, 1 new"`. Counts applicant gaps only (not-found officer checks and
  officer-routed findings are excluded).

## What is checked

- Applicant rationale on the alternative path, separately from the proposed-alternative description and the
  other process fields: presence only, never adequacy. Saved cases use the latest `rationale` or
  `process.rationale` applicant passage; a confirmed acceptable-solution route does not require it. Uploads
  (including standalone packages) read `Rationale`, `Rationale for [the] [proposed] variance/alternative
  [solution]`, or a numbered appendix heading such as `P-1 Rationale`. Every labelled candidate is read,
  including repeated headings within one page. Consistent blank-only candidates on fully readable inputs
  (including the draft's explicit no-answer notice) are a blocking applicant gap (`rationale:presence`).
  Multiple candidates containing text or uncertainty become one excluded officer check with all source
  pointers, in stable order; the review never chooses which candidate controls, even when text matches.
  An unreadable supplied file also prevents blank-only input from establishing absence. A single readable
  passage remains present beside an unrelated unreadable file.
  Whole-answer placeholders are gaps; a placeholder word inside applicant prose is not. A missing heading,
  non-text objects in the passage region, or a passage crossing pages stays `not_found`, with no partial
  `value` and the request item excluded by default. Cross-page findings retain page-linked extracted
  fragments in `pointers[]` for the officer; the field's single-pointer wire shape is unchanged. These
  checks do not perform OCR or establish the completeness of a multi-page passage. A present passage is
  copied, never assessed or drafted by the review.
- Ported deterministic screens (variant B) over the reading: presence and placeholders (D01–D04), edition
  presented as current (D06), intent label (D08), generic or blank risk, mitigation and assumptions (D09–D11),
  professional named when stated as required (D12), supporting document and its responsible person (D13),
  Section B against attachment values (D14), limited topic screen (D15).
- Per row: provision exists (D05), objective/function pair against the table (D07), intent label (D08); a
  benchmark named in Section B without a Section C row (D16); Section D rows without a responsible person.
- Division C 2.3.1.1 file items, each a named finding with its citation when absent (presence only, never
  adequacy): code analysis with the attributed objectives and functions (2.3.1.1.(3)); testing procedures
  (2.3.1.1.(3)); qualifications of the people responsible (2.3.1.1.(4)); maintenance, operation and
  commissioning (2.3.1.1.(2)(b)); a single co-ordinator when more than one person or firm takes
  responsibility (2.3.1.1.(6)). On a saved case, qualifications and maintenance are the existing process
  fields.
- "Demonstrate, don't assert" prompts (warnings, worded as requests): no mention of failure conditions, of
  lapsed maintenance, or of emergency-services response assumptions.
- Peer review: `peer_review:signal`, "Peer review may be warranted", routed to the officer when a
  registered professional is stated to be required, a Part 3 provision is cited, or a product is relied on
  with no CCMC evaluation among the documents. The officer's call; never a finding about the design.

## Close-out

`CloseOut` exists once the case has a final decision (`accept`; a future `refuse` outcome is included
automatically): `decided_at`, `due_date` (10 days later), `days_remaining`, `overdue`, `sent`, `sent_at`,
`sent_by_name`, and a deterministic `record_package`: `send_to_council` (the copy of the variance as decided,
the single location) and `retain_on_file` (Section C references, supporting documents, information requests
sent, the latest package review, the decision record), with the bulletin `basis` (IB-2025-11-18,
IB-2026-10-01, the Orders and Variances Portal). The officer sends and registers; Batatis never sends.

## Storage and retention

Sessions and close-out records live in `package_review_sessions` and `package_review_closeouts`, created with
`CREATE TABLE IF NOT EXISTS` in the same SQLite file or PostgreSQL database as the cases. Rows for a case are
removed when the case is deleted or purged (swept on every package-review access); standalone packages follow
the same seven-day creation-based retention. At most 50 versions per package. The `Case` schema is unchanged.

## Saved-case completeness report (ported)

`POST /cases/{case_id}/completeness` is the r4 branch's read-only `batatis.completeness.v1` report (variant B
by default, `A` on request, `C` returns 503: provider-assisted review is unavailable and off). Request body at
most 1 KiB; `documents` or other fields 422. Under the central guard this path runs in edit mode, so it serves
the owner of a draft or returned case; reviewers get the same screens inside
`POST /review/{case_id}/package-review`. No LLM is used anywhere in the package review; if the optional model
variant is ever enabled it must stay off by default and use OpenAI (the live providers are OpenAI and Jev).

## Limits

- Flattened reading needs the blank SCC form for the field map version (`BATATIS_SCC_FORM`, hash-checked);
  without it a flattened form's fields are all `not_found`. Fillable forms need only the field map.
- Applicant passages are found by headings (and `Heading: text` lines); a passage under another heading is
  `not_found`, never `blank`.
- Attachment cells come from labelled lines (`Issued by:`, `Date:`, …). Scanned attachments are listed as
  unreadable with every cell unknown.
- Signatures cannot be established from text; they are always an officer check.
- Div C, demonstrate and peer-review screens are keyword presence checks; they can miss a passage worded
  differently, which the officer resolves.
