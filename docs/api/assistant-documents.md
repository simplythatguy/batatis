# Typed document excerpts

`POST /api/assist` (also `/assist`) can select **verified document excerpts with
pointers and limited coverage** from genuine PDF files attached to an authorized
application. This is extractive help: a model selects literal quotations and the
server checks them. It is not full explanatory or semantic PDF Q&A, a complete
document review, or a determination of technical correctness or relevance.

The typed Help panel supports selecting application PDFs and uploading through
the existing authorized file route where editing is allowed. It displays selected
files, excerpt pointers and coverage limits. This API contract does not establish
browser acceptance or hosted behavior; those require verification of the combined
client and server revision.

## Request

Upload using the existing authenticated `POST /api/cases/{case_id}/files`. Its
owner/edit, draft-or-returned, PDF-only and 4 MB limits remain unchanged. Use the
actual returned file `id`; a filename, browser-supplied text, evidence listing,
provider instruction or URL cannot authorize a document.

```json
{
  "case_id": "case_actual_id",
  "case_version": 1,
  "context_id": "random-local-context-id",
  "revision": 2,
  "screen": "questions",
  "question": "What dimension is stated in the selected report?",
  "attachment_ids": ["file_actual_id"],
  "history": [],
  "destinations": []
}
```

Existing `focus` and closed `destinations` contracts still apply. Additive
`AssistRequest` fields:

| Field | Contract |
| --- | --- |
| `attachment_ids` | Defaults to `[]`; at most three unique strings of 1–100 characters. |
| `case_version` | Optional strict integer, at least 1; requires `case_id`. Required for attachments and any bound application. |
| `context_id` | Optional string of 16–80 ASCII letters, digits, `_` or `-`. Required with attachments. |
| `revision` | Optional strict integer, 0–1,000,000. Present together with `context_id`. |

Nonempty attachment selection requires `case_id`, `case_version`, `context_id`
and `revision`. Identity strings grant no permission. Case access uses the actual
cookie, owner and existing submitted-file reviewer/authority policy. Ownerless
legacy records cannot enable this new document capability.

Mint a new context identity for each account/selected-application lifetime, and
advance the local revision when the view, question focus or attachment selection
changes. The server is stateless: it cannot observe a purely local change, attest
a browser history's earlier scope, or invalidate another in-flight request merely
because a newer revision was sent. Attachment requests **exclude all chat history
from provider input**. Each selection must be grounded afresh in its current files.
Ordinary no-files chat retains its existing history behavior.

## Response and grounding

Existing `answer`, `cited`, `removed_citations`, `notice` and `navigation` remain.
Additive `AssistResult` fields always serialize:

| Field/type | Meaning |
| --- | --- |
| `context: AssistContextBinding \| null` | Server `user_id` plus original `context_id`, `revision`, `case_id`, `case_version`, `attachment_ids`; null for old unbound calls. |
| `attachments: AssistAttachment[]` | Every selected file's `case_id`, `file_id`, scrubbed `name`, `content_state`, supplied `pages`, `truncated`, and nullable `reason`. |
| `document_references: AssistDocumentReference[]` | Only accepted `case_id`, `file_id`, one-based `page`, and literal scrubbed `quote` pointers used in this answer. |

`content_state` is `text_excerpt` or `not_read`. `pages` identifies pages with
nonempty supplied excerpts; it is not an inventory of every page, image or scan.
`text_excerpt` always carries limited/unread-coverage wording. `truncated` reports
known source/excerpt limits, not proof that the unlisted content was understood.
Unreadable or ambiguous PDFs and image-only files remain `not_read`; a persuasive
filename cannot change that state. No OCR, image understanding, PDF bytes, form
values or external document fetch is sent to a provider.

The immutable document projection supplies at most three PDFs, three
text-bearing pages and 6,000 extracted source characters per PDF, with at most
2,000 source characters per page. Recognized personal details are replaced before
provider input; replacement labels may be longer than their source text. The
underlying reader examines at most 60 physical pages. The combined serialized
source context is capped at 64,000 UTF-8 bytes, with at most four selected code
benchmarks. Existing application-context trimming remains in effect. These limits
do not establish whole-file coverage or extraction/interpretation accuracy.

The model may return only:

```json
{
  "document_references": [
    {"file_id": "file_actual_id", "page": 1, "quote": "An exact supplied text excerpt."}
  ]
}
```

There must be at least one accepted source for a substantive excerpt response.
Each of at most nine quotes is 8–600 characters and must match the supplied
scrubbed text on that exact selected file/page. Unknown fields, arbitrary prose,
empty/missing sources, unselected or unread pages, fabricated quotations and
malformed selections yield fixed uncertainty with no document references. A
valid quote cannot attest an additional model-written explanation: the server
constructs the entire answer from accepted quotes and fixed neutral framing.

The entire constructed answer, including literal quotes, passes the existing
categorical safety/compliance and deterministic legal citation checks. Only actual
source lookup fields in the current context confer code citation authority;
numbers in an uploaded document, question or history do not. Blocked output has
no released quotes or document references. Explicit professional/Section D and
applicant process-field authoring requests receive conservative help. A genuine
document quotation never becomes a confirmed fact, evidence acknowledgment,
professional authorship, technical approval or saved application change.

With multiple files, `attachments` describes the supplied coverage and
`document_references` identifies the subset actually quoted. A readable but
unreferenced file does not support the answer. If no selected file yields text,
the server returns fixed uncertainty without a model attempt or allowance.

## Rechecks and existing paths

The real cookie/role/authority, authorized case/version and selected file
fingerprints are rechecked through preparation, immediately before the provider
attempt (including after allowance reservation), after its reply, and before
returning checked output. File fingerprints include bytes, content type, name,
size and identity. Public file IDs are immutable. This detects changes during
the request; there is no client-attested prior file hash or cross-request source
registry. A new request reads its current authorized files.

Missing/expired/revoked authentication returns 401, inaccessible/deleted cases
or files 404, changed version/identity/source 409, invalid input or oversized
context 422. No excerpt answer accompanies these errors. The client must also
discard any response whose server user, case/version, context/revision or
attachment selection no longer matches its own current state. An old response is
never relabeled with a newer request's identity.

No-files general chat and explicit closed navigation retain their existing
behavior. A recognized navigation request reads no attachments, returns empty
attachment/reference lists, and does not spend or imply that a destination opened.
Quoted/negated/hypothetical navigation stays ordinary help. Model or document
text cannot navigate, edit, submit, delete or confirm anything.

Provider configuration, model choice, 1,200 output tokens, 1,500 question
characters, eight history entries, assistant/shared rate gates and money caps
are unchanged. Reservation includes the actual serialized prompt, document
instruction suffix and conservative UTF-8 input bound. Successful fake/live calls
settle usage; uncertain failed attempts retain the existing reservation policy.
An authorization change after reservation can conservatively retain that allowance
even when the provider is not attempted. The complete provider notice is returned
only on a provider path; deterministic no-provider responses have an empty notice.

Verification uses actual application HTTP routes with genuine synthetic PDF
uploads, real synthetic account cookies/stores and fake provider transports.
It establishes local API behavior, not live provider acceptance, browser/client
acceptance, semantic answer quality, professional approval or deployment readiness.
