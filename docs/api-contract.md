# API contract

## Case API (backend/case-api)

Administrative completeness only. A response never certifies that a design complies or is safe. Citations are returned only when they come from the code database.

Dates are ISO-8601 strings. JSON bodies use `Content-Type: application/json`. Error bodies have a FastAPI `detail` field: an array for request-validation errors (422), otherwise a string unless a route below says otherwise.

### Reviewing jurisdiction

The completeness gap "missing the reviewing jurisdiction" reads one field: `case.jurisdiction`. It does not read a fact, the browser header, or a `jurisdiction_id` key.

`case.jurisdiction` is null until a request stores this object:

```json
{ "id": "edmonton", "name": "Edmonton", "authority": null }
```

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `id` | string | yes | Stable key. `calgary` or `edmonton` for those two authorities. This is the value the product header shows. |
| `name` | string | yes | Display name, such as `Edmonton`. |
| `authority` | string or null | no | Legal name of the authority having jurisdiction. Omit it or send null. |

A JSON string `"edmonton"` is rejected with 422. A body that only has `jurisdiction_id` does not set `case.jurisdiction`; the gap stays. Create and update both take the object above.

`POST /cases` stores it only when that object is in the create body. The first save often happens before the applicant picks an authority, and that create then stores null. `PUT /cases/{id}/jurisdiction` writes the same object later. Either write clears the gap. `GET /cases/{id}/gaps` is the list that shows it. The `gaps` array on the Case document is stored as sent and is not recomputed by these routes.

### Case

```json
{
  "id": "case_…",
  "title": "New house application",
  "created_at": "2026-10-20T18:00:00+00:00",
  "updated_at": "2026-10-20T18:00:00+00:00",
  "version": 1,
  "provenance": "user",
  "example_id": null,
  "seeded_at": null,
  "jurisdiction": { "id": "edmonton", "name": "Edmonton", "authority": null },
  "facts": [],
  "provisions": [],
  "section_c": [],
  "evidence": [],
  "gaps": []
}
```

Fact `kind` is `exact`, `pointed`, `computed`, or `proposed`. `status` is `confirmed` or `unconfirmed`. A `proposed` fact cannot be `confirmed` (422). `source.type` is `code`, `file`, `user_text`, `drawing`, `user_click`, or `demo_seed`. `seeded_at` is null on a case the applicant created. On a demo seed it is the seed time, not a submission time.

`POST /cases`, `PATCH /cases/{id}`, `POST /cases/{id}/facts`, `POST /cases/{id}/gaps`, and `PUT /cases/{id}/jurisdiction` serialize writes per case. A fact added while Section D is rebuilding is kept.

`version` starts at 1 on the first save and increases by 1 on every later write. A read does not change it. `provenance` is `user` or `example`. `example_id` is set only for an example, by `POST /cases` with `example_id` or by `POST /demo/seed`. A later fact or description edit leaves both fields as they were.

### `POST /cases`

Body, all fields optional:

```json
{ "title": "New house application", "jurisdiction": { "id": "edmonton", "name": "Edmonton", "authority": null }, "example_id": null }
```

`201` returns the Case, including `version` 1. `422` when `jurisdiction` is not the object above (a string is 422). Unknown keys such as `jurisdiction_id` are ignored, which leaves `jurisdiction` null. When `example_id` is a non-empty string, the case is stored with `provenance` `example` and that `example_id`.

### `PATCH /cases/{id}`

Body fields are optional. Extra keys are 422.

```json
{ "jurisdiction": { "id": "edmonton", "name": "Edmonton", "authority": "City of Edmonton" } }
```

`jurisdiction` replaces the object. `authority` sets `jurisdiction.authority` on the object already stored, or on the object in the same body. `422` `{"detail":"jurisdiction is not set"}` when `authority` is sent and the case has no jurisdiction. An empty body `{}` returns the case and does not change `version`. A body that changes jurisdiction or authority returns the case with `version` increased by 1. `404` unknown case.

### `POST /cases/{id}/gaps`

Body is one Gap (`id`, `section`, `field`, `message`, `severity`). `200` is the Case, with `version` increased. `404` unknown case, body `{"detail":"case not found"}` and no case `id`. `422` when the gap is invalid. A failed write is never HTTP 200.

### `GET /cases/{id}`

`200` the Case. `404` `{"detail": "case not found"}`.

### `PUT /cases/{id}/jurisdiction`

Body is the jurisdiction object, not wrapped:

```json
{ "id": "edmonton", "name": "Edmonton", "authority": null }
```

`200` the updated Case. The reviewing-jurisdiction gap is gone on the next `GET /cases/{id}/gaps`. `404` unknown case. `422` when the body is a string, is null, or omits `id` or `name`.

### `POST /cases/{id}/facts`

Body is one Fact. `200` the Case, with `version` increased. `404` unknown case, body `{"detail":"case not found"}` and no case `id`. `422` when the fact is invalid, including a proposed fact sent as confirmed. A failed fact or gap write is never HTTP 200.

### `POST /cases/{id}/files`

`multipart/form-data` with one field, `file`. PDF only. The check is the `%PDF-` magic bytes in the first 1024 bytes, then a page count. The file's text is not read and is not stored on the case.

| Env | Default | Meaning |
| --- | --- | --- |
| `BATATIS_FILE_MAX_BYTES` | `4194304` (4 MB) | Reject larger uploads. Blank, non-integer, and non-positive values use the default. |
| `BATATIS_FILES` | `<repo>/.batatis-files` | Directory for the bytes. Git-ignored. Not returned to the client. |

`201`:

```json
{ "id": "file_…", "name": "plans.pdf", "pages": 1, "sha256": "<hex>", "read": true }
```

`name` is the base name of the upload. `pages` is the PDF page count. `sha256` is the hex digest of the stored bytes. `read` is always true: it means the bytes were stored and the page count was read, not that the document's text was read.

The case gains one confirmed fact. Nothing else is extracted.

| Fact field | Value |
| --- | --- |
| `field` | `file.<id>.name` |
| `value` | the base name |
| `kind` | `exact` |
| `status` | `confirmed` |
| `source.type` | `file` |
| `source.ref` | the file id |
| `source.quote` | null |

The PDF bytes are stored at `{BATATIS_FILES}/{case_id}/{file_id}.pdf`. The case JSON keeps the base name and the file id. It does not keep the bytes. There is no route that returns the file. A portal package in this process can read those bytes back from that path by case id and file id. The directory is git-ignored. Uploaded files are never committed.

`400` `{"detail": "invalid case id"}` when the id is empty, `.`, `..`, or leaves the case directory. That status is only for a bad id. `404` unknown case. `413` `{"detail": "file too large"}` when the file is over 4 MB, or over `BATATIS_FILE_MAX_BYTES` when that is set. `415` `{"detail": "not a PDF"}` when the magic bytes fail or the PDF parser cannot read a page count, including a truncated or garbage file. A parser `ValueError` is this 415, not 400. `422` when the `file` field is missing. Error bodies do not include a filesystem path.

### `POST /cases/{id}/export`

Body optional: `{ "draft": false, "expected_version": 1 }`. `expected_version` is optional. When it is sent and it is not the case's current `version`, the response is `409`:

```json
{ "code": "version_conflict", "current_version": 2 }
```

That check runs before the blocked-export check. `200` is `application/pdf` with `Content-Disposition: attachment; filename="<id>-scc-variance.pdf"` (`-DRAFT` when `draft` is true). The PDF metadata records `/BatatisCaseVersion` and `/BatatisFactsHash` (SHA-256 of the case facts). An example case (`provenance` `example`) also stamps `EXAMPLE DATA, fictional, not a real application` on every page and in `/Subject`. A draft stamps `DRAFT, open gaps` on every page and in `/Keywords`. `404` unknown case. `409` when the export is blocked:

```json
{
  "detail": ["unconfirmed pointed fact \"owner_name\" (fact_…)"],
  "reasons": [
    {
      "section": "A",
      "gap_id": "unconfirmed:owner_name",
      "fact_key": "owner_name",
      "label": "unconfirmed pointed fact \"owner_name\" (fact_…)",
      "fix_hint": "Confirm this fact, or remove it, before a final export.",
      "severity": "blocking"
    }
  ]
}
```

`detail` is the string list from before this shape. `reasons` is the structured list. `section` is `A`, `B`, `C`, or `D`. A process-section gap keeps its stable completeness id and is reported with `section` `D`. `gap_id` is stable for the same content. `fact_key` is null when the blocker is not a single field, including `section_c:empty`.

`503` `{"detail": "SCC variance form not found"}` when the blank form file is missing. The path is logged on the server and is not in the body. `503` `{"detail": "code database not found"}` when the code database is missing. `500` for another export failure.

### `GET /cases/{id}/gaps`

`200` is the administrative gap list from `check_completeness`. Each item has `id`, `section` (`A`, `B`, `C`, `D`, or `process`), `field`, `message`, `severity` (`blocking` or `warning`), `fix_hint`, and `citation`. An empty list is not a finding that the design complies or is safe.

The reviewing-jurisdiction item has `field` `jurisdiction`, `section` `B`, and message `Your application appears to be missing the reviewing jurisdiction.` It is present only when `case.jurisdiction` is null.

`404` unknown case. `503` when the code database is missing.

### `POST /cases/{id}/section-d`

Body optional. Extra keys are rejected.

```json
{ "provisions": ["9.25.5.2.(1)"] }
```

`200` is `{ "items": […], "notices": […] }`. Confirmed provisions and the Section C rows looked up for them are saved on the case. The route does not author evidence. `404` unknown case, or a provision id that is not in the code database (the case is left unchanged). `400` invalid provision id. `422` extra keys. `503` when the code database is missing.

### `GET /cases/{id}/professional`

`200` is `required` and `general_required` (`yes`, `no`, or `depends`), plus `reasons`, `questions`, and `scope_note`. This screens documented duties. It does not decide competence or safety. `404` unknown case. `503` when the code database is missing.

### `GET /cases/{id}/process-fields`

`200` is the alternative-path prompts. Risk assessment, mitigating measures, and assumptions/limits are process fields, not evidence-ladder rungs. `404` unknown case. `503` when the code database is missing.

### `GET /ccmc/search?q&limit`

`q` is required, 1 to 200 characters. `limit` is 1 to 50, default 20. `200` is a registry search. `422` when the query is invalid. `503` when the registry snapshot is unavailable.

### `GET /code/search?q&division&limit`

`division` is `A`, `B`, or `C` (default `B`). `limit` is 1 to 100, default 20. `200` is a list of hits with `id`, `division`, `level`, `article_title`, `title`, `text`, and `citation`. `422` when a query parameter is invalid. `503` when the code database is missing.

### `GET /code/{provision_id}?division`

`200` is the code-database record. `400` when the id is invalid or the division is ambiguous. `404` `{"detail": "provision not found"}`. `503` when the code database is missing.

### `POST /section-c`

```json
{ "provisions": ["9.10.15.5.(8)"] }
```

`200` is the Section C rows from deterministic lookup, in input order. `400` invalid provision id. `404` when a provision is not in the code database. `503` when the code database is missing.

### Code database

`BATATIS_CODEDB` overrides the path. The default is `<repo>/codedb/build/codedb.sqlite`. When that file is absent, `Codes` raises `CodeDbMissing`. The exception message is `code database not found` and contains no path.

The handler at the bottom of `create_app` in `engine/api.py` returns HTTP 503 `{"detail": "code database not found"}`. The resolved path is written to the server log only. There is no `FileNotFoundError` handler.

### CORS

Origins matching `http://localhost` or `http://127.0.0.1` with an optional port are allowed, including `http://localhost:5173`.

Responses expose `Content-Disposition`, `X-Batatis-Form-Version`, `X-Batatis-Form-Date`, `X-Batatis-Form-Id`, `X-Batatis-Jurisdiction`, and any other response header whose name starts with `X-Batatis-`.

## Case-building routes and Section D details

Engineer-needed flag (model-checked): rules_only 55/60 on the dev set (in-sample), 1 under-flag; shipped rules_plus_unknown: 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind).

These are the routes the engine serves. `POST /demo/seed` is off unless `BATATIS_DEMO` is exactly `1`.

## Routes

| Method and path | Response |
| --- | --- |
| `POST /cases` | `201` Case. Body is optional: `title`, `jurisdiction` (`id`, `name`, `authority`), `example_id`. |
| `GET /cases/{case_id}` | Case, or `404` with detail `case not found`. |
| `PATCH /cases/{case_id}` | Updated Case. Body may set `jurisdiction` and `authority`. `422` when authority is sent with no jurisdiction, or when the body has an unknown key. |
| `PUT /cases/{case_id}/jurisdiction` | Updated Case. Body is a jurisdiction object (`id`, `name`, optional `authority`). `404` unknown case; `422` invalid body. |
| `POST /cases/{case_id}/files` | `201` stored-file metadata. Multipart `file`, PDF only. `400` invalid case id; `404` unknown case; `413` over 4 MB; `415` unreadable PDF; `422` missing file. |
| `POST /cases/{case_id}/facts` | Case. Body is a Fact. `422` when a `proposed` fact is sent as `confirmed`. `404` unknown case. A failure is not HTTP 200. |
| `POST /cases/{case_id}/gaps` | Case. Body is a Gap. `422` invalid gap. `404` unknown case. A failure is not HTTP 200. |
| `GET /cases/{case_id}/gaps` | `completeness.Gap` list: `id`, `section` (`A` `B` `C` `D` `process`), `field`, `message`, `severity` (`blocking` or `warning`), `fix_hint`, `citation`. |
| `GET /code/search` | Query `q`, `division` (`A` `B` or `C`, default `B`), `limit` (1–100, default 20). Hits as returned: `id`, `division`, `level`, `article_title`, `title`, `text`, `citation`. |
| `GET /code/{provision_id}` | Query `division` optional. The codedb provision record, or `404` detail `provision not found`. `400` when the id is invalid or the division is ambiguous. |
| `POST /section-c` | Body `{ "provisions": ["…"] }`. `SectionCRow` list. `404` when a provision is missing from codedb. `400` on an invalid id. |
| `POST /cases/{case_id}/section-d` | Body optional `{ "provisions": ["…"] }`. `{ "items", "notices" }`. Writes the case. |
| `GET /cases/{case_id}/section-d/issues` | Issue list below. Read-only. Does not write the case. |
| `GET /cases/{case_id}/professional` | `required` and `general_required`: `yes`, `no`, or `depends`. Also `reasons`, `questions`, `scope_note`. |
| `GET /ccmc/search` | Query `q` (1–200 characters) and `limit` (1–50, default 20). `422` on a rejected query. `503` when the registry is unavailable; that detail is the registry error text. |
| `GET /cases/{case_id}/process-fields` | Process-field list. Empty when the pathway is an acceptable solution. |
| `POST /cases/{case_id}/export` | Body optional `{ "draft": false, "expected_version": 1 }`. `200` is `application/pdf`. `409` is either `{ "code": "version_conflict", "current_version": N }` or `{ "detail": ["…"], "reasons": […] }`. `503` when the blank form file is missing; detail is exactly `SCC variance form not found`. `500` on other export failures. |
| `POST /demo/seed` | The fictional demo cases, including the officer after-fixes package, or `404` `{"detail":"not found"}` unless `BATATIS_DEMO` is `1`. |

A Case has `id`, `title`, `created_at`, `updated_at`, `version`, `provenance` (`example` or `user`), `example_id`, `seeded_at`, `jurisdiction`, `facts`, `provisions`, `section_c`, `evidence`, `gaps`. A Fact `kind` is `exact`, `pointed`, `computed`, or `proposed`. `status` is `confirmed` or `unconfirmed`. A `proposed` fact cannot be `confirmed`.

A fact's `source.type` is `code`, `file`, `user_text`, `drawing`, `user_click`, or `demo_seed`.

Gap `severity` is `blocking` or `warning`.

The fixed 404 detail strings are `case not found`, `provision not found`, and, when the demo seed is off, `not found`.

### `POST /demo/seed`

Off unless `BATATIS_DEMO` is exactly `1`. Otherwise `404` `{"detail":"not found"}`. With the flag, `200` is the fictional cases. The first three come from `evals/demo-cases/<case>/input/` only, in the order `demo-a-manufacturer-nailbase`, `demo-b-gc-firestop`, `demo-c-homebuilder-infill`. The fourth is `demo-officer-after-fixes`. A second call returns the same documents. `provisions` and `section_c` are empty, so this route does not fill Code ID cards. `scripts/seed_demo.py` writes the same cases with no network. The Playwright recorder notes are in `docs/demo/seed.md`. Every seeded case has `provenance` `example` and `example_id` equal to its case id. `version` is 1. Titles start with `EXAMPLE DATA · `. Seeded facts use `source.type` `demo_seed`. `seeded_at` is the seed time, not a submission time. Case A (`demo-a-manufacturer-nailbase`) has no `building.storeys` fact. `product.permeance` on that case stays `unconfirmed`.

### Section D plan item

`POST /cases/{case_id}/section-d` returns `{ "items", "notices" }`. Each item is `engine/section_d.py` `EvidencePlanItem`. Every plan item is a provision codedb already resolved. `provision_id` and `citation` sit on the item.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable id for this provision and attribution pair. |
| `provision_id` | string | Division B provision id codedb resolved. |
| `citation` | string | Citation string copied from the code database. |
| `status` | string | `not provided` or `provided`. |
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

`required` and `general_required` are `yes`, `no`, or `depends`. `depends` means a deciding fact is missing. That route does not return `true`, `false`, or `"unknown"`.

The issues route maps the same screen: `yes` → `true`, `no` → `false`, `depends` → `"unknown"`. `"unknown"` requires a question. `depends` and `"unknown"` are not the same token.

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
| `question` | string or null | Present when the benchmark, the attribution, or the practice screen is incomplete. |
| `objective` | string or null | Objective code from the attribution row, such as `OP3.1`. Null when the table has no row. |
| `function` | string or null | Functional-statement code from the same row, such as `F03`. |
| `at_stake` | string | What the evidence should address. Wording recommends; it does not conclude. |
| `recommended_types` | string[] | Same `EvidenceType` values as a Section D plan item, in ladder order. The field name matches `engine/section_d.py`. |
| `practice_of_engineering` | object | Whether the stated facts indicate practice of engineering. |
| `empty_process_fields` | object[] | Required alternative-path process fields that still have no confirmed applicant answer. Not evidence types. |
| `status` | string | `open`, `addressed`, or `needs_professional`. This is the issues enum. The plan route uses `not provided` or `provided`. |

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
| `value` | `true`, `false`, or `"unknown"` | `true` or `false` only when the Division C screen resolves. `"unknown"` when a deciding fact is missing. The service does not guess a boolean. |
| `rule` | string or null | Provision id of the Division C rule that triggered the flag, or of the rule that could not be applied. |
| `division` | `"A"` \| `"B"` \| `"C"` or null | Division of `rule`. |
| `citation` | string or null | That rule's citation from the code database. Omitted when the rule does not resolve. The rule id is one `engine/professional.py` already passes to its screen. |
| `reason` | string | Recommendation tied to the rule. |
| `question` | string or null | Required when `value` is `"unknown"`. |

Confirmed `professional.span_m` (or `span_m`) above 12.20 m is recorded as Part 4 design. This span handoff came from development case dev-050. The cited rule is Div C 2.4.1.2.(1), the same provision `engine/professional.py` already uses for Part 4 design. No other provision id is added for the span.

### `status`

| Value | When |
| --- | --- |
| `needs_professional` | `practice_of_engineering.value` is `true` and no applicant-supplied item linked to the issue names a responsible party or a seal. |
| `addressed` | An applicant-supplied item is linked to the issue (and, if a professional is indicated, a responsible party or seal is named). This records that the item was supplied. It does not assess the item. |
| `open` | No applicant-supplied item is linked. Also used when the practice flag is `"unknown"`. |

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
      "reason": "These facts do not establish whether practice of engineering applies. Ask before setting the flag to yes or no.",
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
| 404 | Fixed detail strings are `case not found`, `provision not found`, and, when the demo seed is off, `not found`. Section C, the plan, and this issues route can also 404 with the text of a missing codedb provision. |
| 400 | Invalid provision id, or an ambiguous division on `GET /code/{provision_id}`. |
| 409 | Export is blocked. Detail is the object under Routes. |
| 422 | A `proposed` fact was sent as `confirmed`, or `GET /ccmc/search` rejected the query. |
| 500 | Export failed for a reason other than a missing form. |
| 503 | The code database file is absent. Body is exactly `{"detail": "code database not found"}`. Raised only by `CodeDbMissing` in `engine/codes.py`. Not a `FileNotFoundError`. The body has no server path. A missing blank form is also HTTP 503 with detail `SCC variance form not found`. An unavailable CCMC registry is HTTP 503 with its error text. |
| 200 | An unknown Division B token on this issues route does not 404. It returns `provision: null` and a question. |
