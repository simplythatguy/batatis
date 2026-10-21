# API contract

Public `POST /cases/{id}/facts` accepts applicant provenance (`user_text`, `user_click`, `file`, or `drawing`). It rejects client-asserted `officer`, `professional`, or `code` authority with HTTP 422. Trusted internal records remain readable; accepting an applicant fact does not promote its authority.

Engineer-needed flag. At measured source `d479e82`, the shipped facts-only `rules_plus_unknown` agreed with model gold on 50/60 text-only dev cases (0 no outputs, 27 unknowns) and 8/11 model-constructed no-ground-truth (no-gt) cases (PR #26; 8 no outputs, 3 unknowns). Unshipped `rules_only` had 55/60 dev agreement and 1 under-flag.

Both shipped sets had 0 under-flags, defined only as gold yes to system no. The three no-gt gold-yes cases (`ngt-101`, `ngt-102`, `ngt-103`) abstained; these are misses, not correct answers. Zero under-flags on dev is by design because it never answered no. All current cases are in-sample, model-checked, not human-verified. Neither model gold nor the receipt's self-check is independent expert validation.

These counts do not establish applicability, equivalence, professional approval or safety, or validate the full Case/API/export flow. They apply only to `d479e82`, not this document branch, newer source, a deployment or a final release. Historical shipped-variant results remain 7/8 blind pre-fix and 4/8 post-fix (no longer blind); neither was rerun for this receipt. Source: [Data Nerd receipt `d75e7ff`](https://github.com/simplythatguy/batatis/blob/d75e7ff0fabb89a2d3f23792ceba8ce116536b35/evals_dev/section_d_flag/RESULTS.md).


These are the routes the engine serves. `POST /cases/{case_id}/files` stores the PDF in the case database.

The public path on Vercel is `/api` plus the path in the table. `vercel.json` sends `/api/(.*)` to the engine and rewrites it to `/:path`. `HttpGuard` also strips a leading `/api` before the route runs, so `GET /api/cases/{id}` and `GET /cases/{id}` are the same handler. Local Vite proxies `/api` to the engine. The web client base is `/api` (`VITE_API_BASE`).

Every response sets `X-Robots-Tag: noindex, nofollow` and `X-Batatis-Notice` to the privacy notice below. Every JSON body includes `meta.notice` with that same sentence. A JSON array is returned as `{ "items": [...], "meta": { "notice": "..." } }`. An object keeps its own fields and gains `meta`. `GET /cases/{case_id}/professional` is an object, so the client reads its fields directly. List routes (`search`, section C, gaps, process fields, section D issues) are unwrapped with `unwrapItems`.

## Routes

| Method and path | Response |
| --- | --- |
| `POST /cases` | `201` Case. Body is optional: `title`, `jurisdiction` (`id`, `name`, `authority`). |
| `GET /retention/purge` | `{ "deleted": N, "meta" }`. Deletes cases with `created_at` older than 7 days, and their files. A second call returns `deleted: 0`. The daily Vercel cron calls `/api/retention/purge` with `Authorization: Bearer <CRON_SECRET>`. Hosted runs require that secret (`503` detail `retention purge not configured` if missing); a missing or incorrect header is `401` detail `unauthorized`. Auth is checked before any bulk purge. Responses use `Cache-Control: no-store`. |
| `GET /cases/{case_id}` | Case, or `404` with detail `case not found`. |
| `PUT /cases/{case_id}/jurisdiction` | Required body `{ "jurisdiction": { "id", "name", "authority" } \| null, "expected_version": N }`. Changes or clears the same case and returns the full Case with its actual new row `version`. Strict positive integer version; malformed/missing/extra wrapper fields `422`, stale/racing writes `409`, unknown/deleted/expired case `404`. See **Jurisdiction updates** below. |
| `POST /cases/{case_id}/facts` | Case. Body is a Fact. `422` when a `proposed` fact is sent as `confirmed`. `409` detail `case was updated concurrently` when the stored version changed during the write. Public sources are restricted to `user_text`, `user_click`, `file`, and `drawing`; callers cannot assert officer, professional, or code authority. Confirmed `evidence.<slot>.file_ref` must match a case-owned uploaded file ID and file-source reference; unknown, cross-case or mismatched IDs return `422`. Validation and insertion share the current-case transaction. Unconfirmed withdrawal and ordinary file/drawing extraction remain supported. There is no PATCH facts route. |
| `POST /cases/{case_id}/files` | `201` `{ "id", "name", "size", "content_type" }`. Body is raw `application/pdf` (optional header `x-filename`) or multipart with exactly one file part and optional text fields. File bytes go in `case_files` unchanged. Malformed or ambiguous multipart is `400`. `404` detail `case not found`. `413` detail `PDF too large: the limit is 4 MB. Try compressing the file or splitting it.` `415` detail `only PDF files are accepted`. |
| `DELETE /cases/{case_id}` | `204` empty body. Removes the case, its facts, its evidence, and its files. `404` detail `case not found`. |
| `POST /cases/{case_id}/evidence` | `200` `{ "evidence", "case", "case_version", "meta" }`. Required body: explicit `operation` (`create` or `update`), stable `evidence_id`, strict positive `expected_version`, `title`, `description`, `evidence_type`. Optional separate metadata and explicit scope are described under **Applicant evidence listings**. Text only; no file, reviewed result or professional authentication is created. |
| `DELETE /cases/{case_id}/evidence/{evidence_id}` | Required JSON body `{ "expected_version": N }`. `200` full committed Case with actual incremented `version`. Withdraws exactly that slot and its fact revisions; keeps unrelated slots and case-owned file rows/bytes. Stale/racing version `409`; missing slot `404` detail `evidence not found`; missing/deleted/expired case `404` detail `case not found`. Missing/invalid version or destructive prefix ambiguity `422`. No CodeDB is required. See **Applicant evidence listings**. |
| `GET /cases/{case_id}/gaps` | `{ "items", "meta" }`. `items` is the `completeness.Gap` list: `id`, `section` (`A` `B` `C` `D` `process`), `field`, `message`, `severity` (`blocking`, `warning`, or `info`; `info` comes from the case's jurisdiction pack and never blocks), `fix_hint`, `citation`. |
| `GET /jurisdictions`, `GET /jurisdictions/{id}`, `GET /cases/{case_id}/jurisdiction/pack` | Jurisdiction packs (data in `engine/data/jurisdictions/`). See [`docs/api/jurisdictions.md`](api/jurisdictions.md). |
| `GET /code/search` | Query `q`, `division` (`A` `B` or `C`, default `B`), `limit` (1–20, default 20). `422` detail `The maximum is 20.` when `limit` is above 20. `429` detail `Search limit reached; try again in N seconds`, with a `Retry-After` header of N seconds. Default budget is 60 searches per 10 minutes per IP. `GET /ccmc/search` shares that budget. The window is in memory on each engine instance, so it is per instance, not a cap shared by every instance. The client IP is the first hop of `x-vercel-forwarded-for`, then `X-Forwarded-For`, then the peer address. Body is `{ "items", "meta" }`. Each hit has `id`, `division`, `level`, `article_title`, `title`, `text`, `citation`. |
| `GET /code/{provision_id}` | Query `division` only. Any other query parameter, including a sentence offset, page, or cursor, is `400` detail `this route accepts only division`. The codedb provision record, or `404` detail `provision not found`. `400` when the id is invalid or the division is ambiguous. |
| `POST /section-c` | Body `{ "provisions": ["…"] }`. `{ "items", "meta" }` where `items` is the `SectionCRow` list. `404` when a provision is missing from codedb. `400` on an invalid id. |
| `POST /cases/{case_id}/section-d` | Body optional. Omitted `provisions` retains the current selection and rebuilds deterministically. Explicit `provisions: []` withdraws all references; nonempty `provisions` replaces them after CodeDB validation. Either explicit list requires `expected_version` from the client's last Case acknowledgment (strict positive integer). `provisions: null`, a missing mutation version, or an invalid version is `422`. Response `{ "items", "notices", "case_version", "meta" }` acknowledges the committed row version. A stale client version or a concurrent write returns `409` detail `case was updated concurrently`; reload and explicitly reconcile, with no implicit retry. A deleted or expired case returns `404` detail `case not found`. No insert fallback. |
| `GET /cases/{case_id}/section-d/issues` | `{ "items", "meta" }`. `items` is the issue list below. Read-only. Does not write the case. |
| `GET /cases/{case_id}/professional` | Object, plus `meta`. `required` and `general_required`: `yes`, `no`, or `depends`. Also `involvement`, `decision`, `general_decision`, `reasons`, `questions`, `missing_facts`, `scope_note`. Not an `{ items }` list. |
| `GET /ccmc/search` | Query `q` (1–200 characters) and `limit` (1–50, default 20). `422` on a rejected query. `503` when the registry is unavailable; that detail is the registry error text. `429` uses the same detail, `Retry-After` header, and per-IP window as `GET /code/search`. The two routes share that window. The registry index is cached on the instance. Report-date fetches are cached by CCMC number, and one search opens at most 8 new report requests. |
| `GET /cases/{case_id}/process-fields` | `{ "items", "meta" }`. `items` is the process-field list. Empty when the pathway is an acceptable solution. |
| `POST /cases/{case_id}/export` | Body optional `{ "draft": false }`. `200` is `application/pdf`. `409` detail is `{ "message": "export blocked; resolve these or export a draft", "reasons": […] }`. `503` detail `SCC variance form not found` when the blank form file is missing. `500` detail `The SCC variance form could not be exported.` on other export failures. That body has no server path. The PDF's NRC text is described under Exported PDF. |

A Case has `id`, `title`, `created_at`, `updated_at`, `version`, `jurisdiction`, `facts`, `provisions`, `section_c`, `evidence`, `gaps`. `version` is the actual stored row version, published consistently by Case create/read/fact-write/evidence-delete responses on both backends. Embedded legacy JSON or caller-supplied Case metadata cannot choose it. A Fact `kind` is `exact`, `pointed`, `computed`, or `proposed`. `status` is `confirmed` or `unconfirmed`. A `proposed` fact cannot be `confirmed`.

A fact's `source.type` is `code`, `file`, `user_text`, `drawing`, `user_click`, `officer`, or `professional`. `officer` and `professional` are authority sources. `user_text`, `user_click`, and `drawing` are applicant sources. `confirmed` does not change the source. Only an `officer`, `professional`, or `code` source can produce professional-screen `no`.

Gap `severity` is `blocking` or `warning`.

The fixed 404 detail strings are `case not found` and `provision not found`.

An `EvidenceItem` has `status` `needed`, `evidence_listed`, or `not_applicable`, and `kind` `text` or `file`. A stored `provided` value loads as `evidence_listed`. `kind` is `file` only when a confirmed file-source `evidence.<id>.file_ref` fact identifies stored bytes owned by this case; otherwise it is `text`. SQLite and PostgreSQL snapshots read file ownership in the same transaction as the case. Old missing/cross-case file claims retain their listing and provenance as unconfirmed facts and cannot clear attachment gaps or final export. Pure offline Case fixtures are metadata tests, not upload evidence. A text item is listed by the applicant, has no file attached, and is not reviewed. Typed text does not write `file_ref`. There is no separate POST evidence route. The single evidence-withdrawal DELETE route is described above.

Full-Case fact-write and evidence-delete acknowledgments apply that same current case-owned inventory normalization while holding the write transaction. An unrelated answer or deleting another slot cannot reassert a legacy ghost file as confirmed/file in its response. Listing text, source provenance, actual same-case attachments and bytes remain intact; the returned `version` acknowledges that exact committed mutation.

### Uploads

`POST /cases/{case_id}/files` is the single implementation of this upload. It is database-backed: the PDF is stored in `case_files`, and a file over 4 MB is HTTP 413 with `PDF too large: the limit is 4 MB. Try compressing the file or splitting it.` The body may be a raw `application/pdf` or multipart. A function disk is ephemeral, and Vercel stops request bodies at 4.5 MB. #21's PDF parser plugs in as a helper this route calls. There is no separate disk-backed route.

Multipart parsing preserves the original case-sensitive boundary and selects the single `form-data` part with a filename, ignoring ordinary text fields. It preserves binary content and trailing line endings without storing MIME framing. At most 32 parts and 64 KiB of total framing, headers, and other fields are accepted in addition to the 4 MiB PDF payload. The request stream is bounded to that combined limit; raw uploads remain bounded to 4 MiB. Missing/invalid framing, multiple files, and excess part counts return `400`; excess payload or overhead returns `413`.

### NRC attribution

Code text is returned in full. That includes provision text, objective and functional-statement wording, intent statements and notes, clauses, and a fact `quote` or `value` when `source.type` is `code`. An applicant `user_text` quote is not code text, and it is not given the NRC link. The object keeps its citation and gains the NRC publication link (`https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499`) when it had no link.

`GET /code/{provision_id}` returns that one provision, including its full clause text. It accepts only `division`. It exposes no sentence offset, page, cursor, or other parameter. `GET /code/search` returns at most 20 hits.

Returning code text is not a finding that a design complies. The code database file is not served by any route.

### Exported PDF

`POST /cases/{case_id}/export` fills the Safety Codes Council form and appends a generated appendix. The form cells carry provision ids, objective and function codes, and a pointer to the appendix for the intent statement. They do not carry provision sentences.

The appendix carries the NRC text for each Section C row: the citation, objective and functional-statement titles, any application note, the full provision text, and the NBC 2020 intent statements and their notes, each with the NRC publication link. Applicant-written process answers and other confirmed form values stay the applicant's words. JSON responses and the appendix do not clip provision text.

### Privacy notice and retention

Batatis automatically removes the names, contact details and addresses it recognizes before any text is sent to an AI provider. In live mode, the remaining text is processed in the US by OpenAI, Anthropic or Jev under their API data policies (https://openai.com/policies/api-data-usage-policies); Batatis deletes its own stored case data and files after 7 days or on request. Every JSON response includes that sentence as `meta.notice`. Responses without a route-specific `X-Batatis-Notice` header also send it in that header; a route's own notice is preserved. A JSON array is returned as `{ "items": [...], "meta": { "notice": "..." } }`.

A case older than 7 days, measured from `created_at`, is deleted with its facts, evidence, and files. Deleting sooner is allowed. `DELETE /cases/{case_id}` removes that case and its files immediately (`204`, or `404` detail `case not found`). Both sqlite and Postgres remove an expired case and its files when it is accessed, even between periodic sweeps. Reads, file access, and fact or file additions cannot extend the retention window. Timestamp comparisons use elapsed time, including timezone offsets. Case create, and the sweep at the start of each request, run the bulk purge at most once every 10 minutes per engine instance. `GET /retention/purge` (Vercel cron path `/api/retention/purge`, once a day on the Hobby plan) and `python -m engine.retention` run it immediately. A second purge deletes nothing. Failed sweeps and explicit purge requests return `503` detail `case purge failed`, plus `meta`; logs name the exception type without its text.

The engine log line is the method, the path, and the status. It does not include case JSON or uploaded bytes.

Public evidence withdrawal uses the same snapshot/versioned CAS as evidence listing. It requires the client's current `expected_version` and increments the version once only after a successful commit. An absent slot is `404` without a write. A stale client or a concurrent change is `409`; no retry or unconditional upsert occurs. Both backends check the 7-day `created_at` cutoff after obtaining the write lock and commit expiry removal before returning failure. Uploaded bytes remain until case deletion/expiry. The JSON privacy notice and response headers apply to errors too. The sole public DELETE remains in `engine/routes_case.py`; the existing internal `remove_evidence(case_id, evidence_id)` primitive retains its prior contract.

### Applicant evidence listings

`POST /cases/{case_id}/evidence` (also `/api/cases/{case_id}/evidence`) accepts applicant-entered **text metadata**, with each field stored separately. For example, against the latest Case acknowledgment `version: 7`:

```json
{
  "operation": "create",
  "evidence_id": "doc_wall_01",
  "expected_version": 7,
  "title": "Applicant report title",
  "description": "Applicant description; this text is not an attached report.",
  "evidence_type": "engineering review",
  "responsible_party": "Applicant-supplied person or organisation",
  "date": "Applicant-supplied revision/date",
  "issuer": "Applicant-supplied issuer"
}
```

`operation`, `evidence_id`, `expected_version`, `title`, `description` and `evidence_type` are required on both create and update. New POST IDs use `[A-Za-z0-9][A-Za-z0-9_~-]*`, at most 128 characters, with no dot, whitespace or path separator. The ID is the actual durable slot ID, independent of title. Distinct IDs with the same title remain distinct. `create` against an existing slot is `409`; `update` against an absent/deleted slot is `404`. There is no implicit upsert, generated replacement ID, replay success, or case resurrection.

All metadata is strict string data. The three required text fields must contain a non-whitespace character; their original whitespace and full text are preserved. Optional `responsible_party`, `date`, and `issuer` may be omitted or explicitly null. On update, omission retains the current value; null records an explicit withdrawal. No responsible person, date, issuer, professional status or missing field is inferred from prose. No text is silently truncated or parsed. Each submitted metadata field appends a confirmed, pointed `user_text` fact under `evidence.<id>.<field>`, keeping earlier metadata revisions and unrelated facts. Confirmed here means the applicant submitted the text, not that its claims have been verified. An `EvidenceItem` holds the actual ID, description, evidence type, `status: "evidence_listed"`, and `kind: "text"`.

The response is `200` `{ "evidence": <actual saved EvidenceItem>, "case": <full saved Case>, "case_version": 8, "meta": ... }`; `case.version` equals `case_version` and the committed store row version. GET/reload returns the same saved facts and listing. The full Case carries title, responsible party, date and issuer as separate ledger facts. `source`, `kind`, `file_id`, `file_ref`, caller-selected status, professional seal and other unsupported body fields are rejected with `422`. A real attached document at the same slot is also rejected with `422` by this text endpoint. The existing upload and case-owned file-fact workflow remains the attachment path. Snapshot normalization of uncertain legacy file claims still applies; raw legacy JSON byte identity is not promised.

Optional `scope` controls only explicit document linkage:

- Omit `scope` to keep current links. A metadata edit cannot restore scope withdrawn by reference selection.
- Send `"scope": null` to remove that document's old provision/objective/function/item/covers links.
- Send `"scope": { "item_id": "<current plan item ID>" }` to explicitly bind to that one current item. Optional `provision_id`, `objective`, and `function` are consistency assertions. Alternatively send `provision_id` plus enough objective/function assertions to resolve exactly one item. IDs and assertions must match the canonical values in the current plan.

Explicit scope is re-resolved through the actual CodeDB against only the Case's currently selected provisions. No cached row or function/objective match across other provisions supplies scope. No match, conflicting assertions, or multiple possible items is `422` without mutation. Invalid/missing stored provisions retain the existing `400`/`404` behavior; missing corpus is the fixed `503` `code database not found`. An unscoped create/edit, explicit unscope or DELETE does not open CodeDB or resolve a provider. A no-attribution item retains null function/objective and its missing-benchmark uncertainty.

`EvidenceItem` has no provision field. Scope is recorded in the existing `evidence.<id>.item_id`, `.provision_id`, `.objective`, and `.function` facts; old links for that exact document are replaced only on an explicit scope request. `auto_link: false` is a computed fact that prevents document identity alone from supplying coverage. Reference withdrawal preserves authored metadata and bytes while removing withdrawn links. Reselecting a stable old plan ID leaves the document unscoped until an explicit current relink. If bytes are later linked through the existing attachment workflow, that explicit item link identifies its intended plan item; matching pairs on another provision do not attach it there.

Saving/listing text does **not** mark a plan item attached, reviewed, adequate, equivalent or complete, or satisfy professional authentication. Existing attachment, performance-evidence, no-attribution, administrative, process and professional gates remain in force. This response deliberately contains no placeholder closure counts or grouped gap results. PR #30/#11 grouped-gap policy and consumer integration remain separate work.

DELETE requires the same actual slot ID and a body such as `{ "expected_version": 8 }`, and returns the full saved Case with `version: 9`. It removes all revisions of that slot's facts and its `EvidenceItem`, preserving other slots, file rows/metadata/bytes and other cases. Replaying version 8 is `409`; deleting the now-absent slot with current version 9 is `404`. `wall` does not match `wall~2`, `wallpaper`, or `Wall`. Safe legacy dotted IDs such as `wall.child` remain deletable exactly. Deleting `wall` when a distinct `wall.child` slot exists is ambiguous and returns `422` without mutation; delete the exact child first. IDs containing path separators, ASCII characters below U+0020 or the ledger's reserved `.covers.` delimiter (including an ID ending in `.covers`), or duplicate same-ID EvidenceItems, are rejected as ambiguous. Legacy dotted metadata editing through POST is outside its new flat-ID contract.

Both operations read a consistent Case/version snapshot, check the strictly positive client version, and save the whole mutation with one `put(..., expected_version=...)`. Concurrent fact writes, reference changes, evidence removal and case deletion/expiry cannot be overwritten or resurrected. Errors expose the usual notice/meta/noindex contract. On `409`, refresh and explicitly reconcile; do not automatically retry. The current web evidence caller must adapt to this body, store the returned actual ID/Case/version, preserve separate metadata, and send a versioned DELETE body. A `404` is a failed save/delete, never an acknowledgment. No current bare-client compatibility is claimed.

Section D uses `get_snapshot(case_id)` to read the Case and version from one stored row, then saves with `put(..., expected_version=version)`. Reading a Case and later calling `get_version` is not a valid snapshot. An explicit replacement/clear must also match the client's `expected_version` before lookup/planning starts. Versioned updates never insert a missing case. Both backends check the current retention cutoff after acquiring the write lock, including for fact/file additions and Section D saves, and commit expiry removal of the case and its files before reporting failure. New-case creation retains its existing behavior. The public Case `version` is taken from the row column in that same transaction, and `case_version` acknowledges the Section D save. File-byte uploads alone do not change the Case JSON/version; the fact write linking an uploaded file does.

### Jurisdiction updates

`PUT /cases/{case_id}/jurisdiction` (also `/api/cases/{case_id}/jurisdiction`) requires both wrapper fields:

```json
{ "jurisdiction": { "id": "test-ahj", "name": "TEST jurisdiction (synthetic)", "authority": null }, "expected_version": 7 }
```

The jurisdiction object uses the existing `Jurisdiction` model: `id` and `name` are required strings, and `authority` is an optional string or null. The server does not resolve a municipality, infer an authority, or apply a jurisdiction whitelist. Explicit `"jurisdiction": null` clears the jurisdiction on this same case; omission does not mean clear. Missing/null/malformed bodies, either missing wrapper field, unsupported wrapper fields, and invalid jurisdiction objects return `422`. `expected_version` must be a positive integer from the client's last Case acknowledgment; null, booleans, strings, floats (including `7.0`), zero and negative numbers return `422`.

Success is `200` with the full saved Case, its unchanged `id` and `created_at`, the actual new row `version` (8 in this example), and the usual HTTP notice, JSON `meta` and noindex headers. Each accepted update increments the version once, including an already-equal jurisdiction or already-null clear, and refreshes `updated_at`. All other fields from the current Case snapshot and all stored file bytes and metadata are preserved. Existing snapshot normalization of derived attachment kind and legacy attachment claims still applies. This deterministic edit does not open CodeDB or resolve/call a provider.

The handler reads `get_snapshot(case_id)`, compares its row version to the required client version, then saves with `put(..., expected_version=version)`. A stale client version or a racing write returns `409` detail `case was updated concurrently`, preserving the newer data. Unknown/deleted/expired cases, including deletion or expiry while waiting to save, return `404` detail `case not found`; expiry cleanup of the row and files commits before that response. There is no case creation, retry, unconditional upsert or resurrection fallback. On conflict, refresh and explicitly reconcile before sending a newly acknowledged version. The notice, `meta` and noindex headers apply to errors too. The web caller must send this wrapper and version; frontend adaptation is separately owned.

### Reference withdrawal and revisions

After a Case acknowledgment with `"version": 7`, these are the three existing-route request forms:

```json
{}
```

Omission rebuilds the currently stored selection. It requires no provider or provider intent, and may omit `expected_version`; its own snapshot/CAS still rejects concurrent writes. A supplied `expected_version` is checked even on a rebuild. A successful rebuild increments the version and returns the committed `case_version`.

```json
{ "provisions": [], "expected_version": 7 }
```

This withdraws all references. The response has `"items": []` and `"case_version": 8`. It clears stored provisions, Section C rows, cached gaps and all old `citation.*` / `open_question.*` decisions. Replacing a subset withdraws matching removed decisions and scope while retaining unaffected reference links. No stored plan/check/identify-result table exists on this source; later identify integration must bind results and decisions to this same revision and reject stale completions. The version bump already rejects an old snapshot's CAS save.

```json
{ "provisions": ["9.25.5.2.(1)(b)"], "expected_version": 8 }
```

Reselection requires a fresh deterministic CodeDB lookup. Invalid/missing provisions leave the Case untouched, and a missing corpus returns the existing fixed `503`. A clear or an already-empty rebuild needs no CodeDB. It returns a missing-benchmark notice with empty C/D; current gaps and final-export preflight still require a confirmed benchmark, alternative-path risk/mitigation/assumptions and applicable professional material.

Withdrawal preserves applicant descriptions, process/professional facts, document ids, titles, dates, issuer/responsible-party/seal metadata and stored bytes. Removed objective/function/provision/plan-coverage links become unscoped. The ledger records `evidence.<id>.auto_link = false` for withdrawn document scope: an id equal to an old stable plan id cannot silently restore coverage when that benchmark is selected again. Explicit new `evidence.<id>.item_id` or `evidence.<id>.covers.<plan id> = true` facts can re-link a preserved document after applicant review. Slot deletion still removes that exact slot's facts and item, including the scope marker, while preserving uploaded bytes.

A stale replacement/clear returns `409 { "detail": "case was updated concurrently", "meta": … }` and preserves all current facts. A missing/deleted/expired case returns `404 { "detail": "case not found", "meta": … }` and remains absent. There is no retry, upsert, or `expected_version: 0` path for either mutation. The client must refresh on conflict and send a newly acknowledged version only after reconciling the draft.

The API model change adds `Case.version`. The parent UI integration must regenerate `web/src/api/engine.schema.json` (`python -m engine.schema_export`) and its generated TypeScript types, and adapt the Section D caller to send the acknowledged version and explicit `[]`. That frontend adaptation is separately owned.

### Section D plan item

`POST /cases/{case_id}/section-d` returns `{ "items", "notices", "case_version", "meta" }`. `case_version` is the committed Case version; an offline `section_d_plan` call has no stored acknowledgment and leaves it null. Each item is `engine/section_d.py` `EvidencePlanItem`. Every plan item is a provision codedb already resolved. `provision_id` and `citation` sit on the item.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable id for this provision and attribution pair. |
| `provision_id` | string | Division B provision id codedb resolved. |
| `citation` | string | Citation string copied from the code database. |
| `status` | string | `needed` or `evidence_listed`. Not a sign-off or compliance determination. |
| `attribution_status` | string | `direct`, `inherited from parent`, or `no row in the attribution table`. |
| `attributed_via` | string or null | Parent provision when the row is inherited. |
| `objective` | string or null | Objective code from the attribution pair. Null when the table has no row. |
| `function` | string or null | Functional-statement code from the same pair. |
| `bracket` | string or null | Bracket on that pair. |
| `clauses` | string[] | Clause ids. Empty means the whole sentence. |
| `application_note` | string or null | Attribution condition from the pair. |
| `performance_issue` | string | What the comparison should address. Wording recommends; it does not conclude. |
| `recommended_types` | string[] | `EvidenceType` values from `engine/section_d.py`: the seven-step ladder, then on the alternative path CCMC evaluation, ICC-ES evaluation, registered professional opinion, and engineering review. |
| `responsible_party` | string | Names copied from linked applicant documents. Empty when none are named. |
| `attachments` | object[] | Linked supporting documents: `id`, `title`, `file`, `item_ids`, `responsible_party`, `issuer`, `date`, `professional_seal`. |

### Practice-of-engineering on `GET /professional`

Identity confirmation accepts the latest explicit engineer/architect role independently of name and discipline, plus a seal or registration identifier. Integer registration IDs are normalized; booleans, commercial roles and trainee/student/intern/EIT/technologist/technician qualifications do not satisfy this field. Withdrawing the explicit role reopens it. This is applicant metadata, not licence verification.

Authentication of professional work is a separate administrative check. Registration alone does not authenticate work. All three seal aliases (`professional.seal`, `professional_seal`, `registered_professional.seal`) share the same source-aware check; file extraction alone and unsigned/commercial metadata cannot close it. Uploaded-document seals remain subject to the same negative metadata checks. Authenticity and scope still require human review.

`required` and `general_required` are `yes`, `no`, or `depends`. The unresolved token means a deciding fact is missing. That route does not return `true`, `false`, or `"unknown"`. Show `decision` and `general_decision` for an unresolved screen. Each is a sentence naming the deciding question and who decides (`routed_to`): the officer, the applicant, or a registered professional. An unresolved reason `message` is the same kind of sentence. Those sentences do not render the unresolved token on its own, and they do not repeat it.

`involvement` is `professional_involved`, `not_required`, or `unresolved`. An alternative-solution case never counts `prescriptive_route_confirmed` as yes. A Yes on that route is a contradiction and clears nothing. Reserved professional judgement, professional scope, authority-requires-professional, and special-safety answers whose only source is the applicant stay unresolved. `professional_involved` is reached only when those answers come from an `officer`, `professional`, or `code` source and the applicant has confirmed an engineer or architect (normalised role match, for example `R. Singh, P.Eng.`, and a registration or seal number). That resolution is not `not_required`. If any Yes/No input to the screen is applicant-sourced, including a user-confirmed fact, the screen does not return `no`; it returns `depends`. That holds on an acceptable-solution case and on an alternative solution. Applicant answers on `special_safety_concerns` and `professional_scope_resolved` stay unresolved on both. The completeness gap is then exactly `Routed to the officer: whether a registered professional is required`, `routed_to` `officer`, severity `blocking`. That gap blocks the official PDF. A draft export stays allowed. `questions` remains a list of strings. `prompts` repeats each question with `help` (what Yes means and what No means) and `not_sure` (`Not sure (the officer decides)`). A Not sure answer is an open item routed to the officer.

The Section D professional fields `engineer_engaged` and `architect_engaged` (engineer or architect engaged) and `registered_professional` accept the explicit answers `not_sure` and `not_engaged_yet`. Both stay unresolved. They are not a `no`. On the issues route the practice flag is `unknown`. The completeness gap is exactly `Routed to the officer: whether a registered professional is required`, `routed_to` `officer`, severity `blocking`. That is the same rule as an applicant-sourced yes or no. `not_engaged_yet` is not `professional_status` `not_engaged`.

`professional_status` is `not_engaged` when a confirmed applicant fact (`user_text` or `user_click`) states `not_engaged` or `No professional engaged yet`. A file or an officer note does not set it. That statement does not confirm a professional and does not write a registration number or a seal. The blocking professional-involvement gaps (named professional, qualifications, authentication) become one gap: `Professional involvement not yet confirmed; the officer decides whether it is required.`, severity `warning`, `routed_to` `officer`. Official export stays allowed. The exported package lists that sentence under open items. When this statement is absent, the officer gap sentence above is unchanged.

This exception covers professional identity and involvement only. Independently unresolved source chains remain blocking `professional_source` findings for official export. Draft exports remain available and include the unresolved reference and reviewer action.

The issues route maps the same screen: `yes` → `true`, `no` → `false`, `depends` → `"unknown"`. `"unknown"` requires a question. Those two tokens are not the same. An `"unknown"` issue `reason` and the professional-requirement gap name the deciding question and who decides. They do not render the unresolved token.

When a professional is required, a missing applicant-confirmed engineer/architect role and seal or registration also creates the blocking `D12:professional_confirmation` gap, routed to the professional. A name and document metadata alone cannot clear official export. Draft export and the explicit `professional_status: not_engaged` warning path above retain their behavior.

Screening questions follow the case topic, the cited provision prefixes, and whether the building is Part 3 or Part 9. Part 3 is derived when storeys are above 3, building area is above 600 m2, occupancy is assembly or institutional, or a cited provision is in Part 3. A Part 9 occupancy inside those limits, or citations that are only Part 9, stays on the Part 9 questions. When the part cannot be derived, the screen asks one question, which part applies, and does not ask the Part 9 items. A Part 3 case, including a 5-storey building and a case cited to Part 3, does not ask about a preserved wood foundation, roof trusses, or a farm building. A fire-separation or firestop case (a Division B `3.1.8` or `3.1.9` provision, or a firestop, fire-separation, or penetration topic, without a structural provision) asks whether the fire separation stays intact at each penetration, including sprinkler piping. It still asks the fire-suppression question (Div C 2.4.1.3) and the fire-alarm question (Div C 2.4.1.4) when those facts are unresolved. Every yes/no screening question, including those two, is offered with `not_sure` `Not sure (the officer decides)`. Answering that option leaves the fact unresolved. When it leaves the screen unresolved, the issues flag is `unknown` and `routed_to` is `officer`. The mandatory codedb-only triggers stay in their routing order. When both a fire-suppression system and a fire-alarm system are unresolved, one system-presence line is returned.

An unsigned email from a vendor or sales rep does not satisfy professional authentication and does not count as professional evidence. A seal string copied from that email does not close the authentication gap.

### Process field ids

Canonical ids on `GET /process-fields` and on an issue's `empty_process_fields` are `rationale`, `risk_assessment`, `mitigating_measures`, `assumptions_and_limits`, `maintenance_operation`, and `qualifications`.

The ledger accepts `process.<id>` and the bare id. Aliases, from `engine/process_fields.py`:

| Canonical id | Also accepted |
| --- | --- |
| `rationale` | `rationale` |
| `risk_assessment` | `risk` |
| `mitigating_measures` | `mitigation` |
| `assumptions_and_limits` | `assumptions_limits`, `assumptions` |
| `maintenance_operation` | `operation_maintenance` |
| `qualifications` | `qualifications` |

## Section D — evidence issues

`GET /cases/{case_id}/section-d/issues`

Recommendations for the evidence an alternative-solution application must address. The list is administrative. It does not decide that a design complies, is safe, or that a supplied professional opinion is adequate. The route is read-only.

An empty list is not returned for a case with no confirmed benchmark. That case returns one issue whose `provision` is null and whose `question` asks for the benchmark.

### Issue

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable id for this benchmark and objective/function pair, or an unresolved-reference id. |
| `provision` | object or null | Confirmed Division B provision. Null when the entered reference is not in the code database. |
| `provision.provision_id` | string | Provision id that `codedb` resolved. |
| `provision.division` | `"A"` \| `"B"` \| `"C"` | Division of that row. Benchmark issues use `"B"`. |
| `provision.citation` | string | Citation string copied from the code database. The service does not format its own citation. |
| `entered_reference` | string or null | The applicant's unresolved token. Not a citation. |
| `question` | string or null | Present when the benchmark or the attribution is incomplete. The practice object carries its own question. |
| `objective` | string or null | Objective code from the attribution row, such as `OP3.1`. Null when the table has no row. |
| `function` | string or null | Functional-statement code from the same row, such as `F03`. |
| `at_stake` | string | What the evidence should address. Wording recommends; it does not conclude. |
| `recommended_types` | string[] | Same `EvidenceType` values as a Section D plan item, in ladder order. The field name matches `engine/section_d.py`. |
| `practice_of_engineering` | object | Whether the stated facts indicate practice of engineering. |
| `empty_process_fields` | object[] | Required alternative-path process fields that still have no confirmed applicant answer. Not evidence types. |
| `human_review` | object[] | `{trigger_id, who, why, cite, source, act, quote}`. `source` is `codedb` or `statute`. Not a sign-off or compliance determination. |
| `status` | string | `open`, `evidence_listed`, or `needs_professional`. This is the issues enum. The plan route uses `needed` or `evidence_listed`. Not a sign-off or compliance determination. |
| `routed_to` | string or null | `officer`, `professional`, or `applicant`. An unknown flag from an applicant answer or from Not sure is `officer`. `needs_professional` is `professional`. |

`empty_process_fields[]`:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | `rationale`, `risk_assessment`, `mitigating_measures`, `assumptions_and_limits`, `maintenance_operation`, or `qualifications`. |
| `label` | string | Prompt label. |
| `citation` | string | Division C documentation provision from the code database. |

Process fields are required on the alternative path. They are not rungs of the evidence ladder. Risk assessment, mitigating measures, and assumptions/limits are not dropped.

### `practice_of_engineering`

| Field | Type | Meaning |
| --- | --- | --- |
| `value` | `true`, `false`, or `"unknown"` | `true` or `false` only when the Division C screen resolves. `"unknown"` when a deciding fact is missing, or when a yes or no result has no resolvable Division C citation. In that citation case `reason` says the rule did not resolve. The route returns that flag; it does not return 500. The service does not guess a boolean. |
| `rule` | string or null | Provision id of the Division C rule that triggered the flag, or of the rule that could not be applied. |
| `division` | `"A"` \| `"B"` \| `"C"` or null | Division of `rule`. |
| `citation` | string or null | That rule's citation from the code database. Omitted when the citation does not resolve. A mapped known rule ID and division remain visible with a lookup-specific reviewer question; unmapped reasons do not invent an ID. Mandatory rule IDs come from resolved database rows in `human_review`. |
| `reason` | string | Recommendation tied to the rule. When `value` is `"unknown"`, the sentence names the deciding question and who decides (`routed_to`). |
| `question` | string or null | Required when `value` is `"unknown"`: the deciding question, not a generic stand-in unless every specific question was unusable. When `value` is `true`, the question asks the applicant for the registered professional's name, discipline (engineer or architect), and APEGA or AAA registration number. A seal the applicant confirms can stand in for the number. The service does not fill those fields. |
| `prompts` | object[] | Each asked question: `text`, `help`, `not_sure`. `help` says what Yes and No mean. `not_sure` is `Not sure (the officer decides)`. |
| `routed_to` | string or null | `officer`, `professional`, or `applicant`, same as the issue. |

Confirmed `professional.span_m` (or `span_m`) above 12.20 m is screened as Part 4 design by the shared case decision. The professional endpoint, issues, completeness and export consume that same decision, including mandatory triggers with database-resolved citations; issues no longer promote a different decision after export preflight. This span handoff came from development case dev-050. The cited rule is Div C 2.4.1.2.(1), the same provision `engine/professional.py` already uses for Part 4 design. No other provision id is added for the span.

### `status`

| Value | When |
| --- | --- |
| `needs_professional` | `practice_of_engineering.value` is `true` and the applicant has not confirmed a registered-professional role of engineer or architect together with a seal or a registration number. The confirmation is `user_text` or an explicit confirmation (`user_click`). A name or seal on an uploaded document does not count, and the service does not infer one. Not a sign-off or compliance determination. |
| `evidence_listed` | An applicant-supplied item is linked to the issue, the practice flag is not `"unknown"`, and a `true` flag also has that confirmed role and seal or registration number. Listing the item is not a sign-off or compliance determination. |
| `open` | No applicant-supplied item is linked, or the practice flag is `"unknown"`. Not a sign-off or compliance determination. |

The UI does not read the old issue status `addressed`, so that token is not accepted as an alias. Plan-item `needed` and `evidence_listed` are also not a sign-off or compliance determination. A stored evidence status `provided` loads as `evidence_listed`. The issues route does not write the case and does not fill the professional's name, discipline, or registration number.

`human_review` is routing, not a determination. Every row has `source`: `codedb` or `statute`. Code `cite` values are copied from the code database; a provision that does not resolve is left off the list. Codedb rows are only the mandatory `verification_class` `codedb-only` triggers, in this order: `HR-03` (Div C 2.4.1.2.(1)), `HR-01` (Div C 2.4.1.1.(3)), `HR-06`, `HR-07`, `HR-05`, `HR-04`, `HR-11`, `HR-14`, `HR-13`, `HR-12`. Each of those can push the practice flag toward yes, which is `needs_professional` until a registered professional is confirmed. The other 11 codedb-only triggers are discretionary or an authority-having-jurisdiction acceptance (`HR-15`, `HR-17`, `HR-31`, `HR-32`, `HR-33`, `HR-34`, `HR-35`, `HR-40`, `HR-41`, `HR-42`, `HR-44`). They set `routed_to` `officer` and do not push yes, and they are not `human_review` rows. Mixed code triggers stay off, including `HR-02`, `HR-08`, `HR-10`, `HR-16`, `HR-20`, and `HR-43`. There is no Table 2.4.2.1. A Division B `3.8` provision, `requests_interpretation`, and a dimensional difference of not more than 2% are in that officer route. Statute rows are emitted only for a pinpoint confirmed from the Act. `HR-21` dwelling units cite `EGPA s.2(7)(b)(ii)`. `HR-22` cites `Architects Act s.2(6)(b)(ii)`. Their `why` is `counts dwelling units (4 or less); whether a suite counts is for the officer`. `EGPA s.2(7)(a)` is emitted only for assembly or institutional occupancy. Other occupancies get no Act gross-area row. `HR-30` cites `Safety Codes Act s.38(1)`. A statute row carries `act` (full name, RSA chapter, current-as-of date) and a verbatim `quote`. `total_unit_count` includes suites. When total units exceed four but the principal-unit exception may still apply, the suite-count question remains unresolved and routes to the officer. The separate Act rows retain their pinpoints; Div C 2.4.1.1.(5), an authentication sentence, is not cited as a unit-count rule. An unsettled gross area is medium confidence: the flag is unknown and asks. It does not answer no. `gross_area_per_floor_m2` and `total_unit_count` are confirmed facts. The code screen still uses building area and principal dwelling units.

The per-variant table is `python3 -m engine.section_d_flag_eval --codedb PATH`. Without a readable codedb the script prints `numbers: not final`. With one, it also prints `citation_resolution: resolved/total`. The shipped variant alone, on a JSONL file in the #8 case format (`id`, `description`, `known_facts`, `gold.engineering_required`), is `python3 -m engine.section_d_flag_eval --codedb PATH --cases cases.jsonl`. That command scores `rules_plus_unknown` only. The README placeholder for that run is: (on the 60 text-only dev cases it answered only yes or ask, 0 no, so 0 under-flags is partly by design; since 4425089 it can answer no when stated facts clear every trigger).

### Evidence-type order

Shared ladder, low confidence to high:

1. manufacturer's literature
2. existing STANDATA variance
3. ISO 17025 test report
4. evaluation
5. evaluation + testing
6. qualification
7. ISO 17065 certification

Alternative path only, after the ladder: CCMC evaluation, ICC-ES evaluation, registered professional opinion, engineering review.

### Example

The live body is `{ "items": <the array below>, "meta": { "notice": "Batatis automatically removes the names, contact details and addresses it recognizes before any text is sent to an AI provider. In live mode, the remaining text is processed in the US by OpenAI, Anthropic or Jev under their API data policies (https://openai.com/policies/api-data-usage-policies); Batatis deletes its own stored case data and files after 7 days or on request." } }`.

```json
[
  {
    "id": "ev_0123456789abcdef",
    "provision": {
      "provision_id": "9.10.15.5.(8)",
      "division": "B",
      "citation": "<citation string returned by codedb for this provision>"
    },
    "entered_reference": null,
    "question": null,
    "objective": "OP3.1",
    "function": "F03",
    "at_stake": "Recommend evidence that addresses F03 and OP3.1 for benchmark <citation string returned by codedb for this provision>. Identify the proposed configuration, the comparison the responsible designer selects, the report passages they rely on, the differences and the limits.",
    "recommended_types": ["manufacturer's literature", "existing STANDATA variance"],
    "practice_of_engineering": {
      "value": "unknown",
      "rule": "2.4.1.1.(1)",
      "division": "C",
      "citation": "<citation string returned by codedb for Div C 2.4.1.1.(1)>",
      "reason": "What is the confirmed occupancy/building type, including each use in a mixed-use building? The officer decides.",
      "question": "What is the confirmed occupancy/building type, including each use in a mixed-use building?"
    },
    "empty_process_fields": [
      {
        "id": "risk_assessment",
        "label": "Risk assessment",
        "citation": "<citation string returned by codedb for Div C 2.3.1.1.(3)>"
      }
    ],
    "status": "open"
  }
]
```

A live response copies the citation string the code database returns. The placeholders above are not citations.

### Errors

| Status | When |
| --- | --- |
| 404 | Fixed detail strings are `case not found` and `provision not found`. Section C, the plan, and this issues route can also 404 with the text of a missing codedb provision. |
| 400 | Invalid provision id, an ambiguous division on `GET /code/{provision_id}`, or any query parameter other than `division` on that route (`this route accepts only division`). |
| 409 | Export is blocked. Detail is the object under Routes. Fact writes, evidence withdrawal, and Section D saves return 409 with detail `case was updated concurrently` on a write conflict. |
| 413 | `POST /cases/{case_id}/files` when the PDF is over 4 MB. Detail is `PDF too large: the limit is 4 MB. Try compressing the file or splitting it.` |
| 415 | `POST /cases/{case_id}/files` when the body is not a PDF. Detail is `only PDF files are accepted`. |
| 422 | A `proposed` fact was sent as `confirmed`, `GET /code/search` `limit` is above 20 (detail `The maximum is 20.`), or `GET /ccmc/search` rejected the query. |
| 429 | `GET /code/search` or `GET /ccmc/search` when the caller is over the shared search rate limit. Detail is `Search limit reached; try again in N seconds`. The response also sets `Retry-After: N`. The limit is per engine instance (an in-memory window), per IP. |
| 500 | Export failed for a reason other than a missing form. Detail is `The SCC variance form could not be exported.` The body has no server path. The exception, including a form path, stays in the server log. |
| 503 | The code database file is absent: detail `code database not found`, plus `meta`. Raised only by `CodeDbMissing` in `engine/codes.py`. Not a `FileNotFoundError`. The body has no server path. A missing SCC variance form is HTTP 503 with detail `SCC variance form not found`, plus `meta`. The server log says the export is unavailable on this deployment. An unavailable CCMC registry is also HTTP 503, and its detail is that error's own text, plus `meta`. An unreachable case database is HTTP 503 with detail `case store unavailable`, plus `meta`, and that body does not include the server address. A failed case purge is HTTP 503 with detail `case purge failed`, plus `meta`; only the exception type is logged. |
| 200 | An unknown Division B token on this issues route does not 404. It returns `provision: null` and a question. |
