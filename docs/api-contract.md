# API contract

Engineer-needed flag (model-checked): rules_only 55/60 on the dev set (in-sample), 1 under-flag; shipped rules_plus_unknown: 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind).

These are the routes the engine serves. `POST /cases/{case_id}/files` stores the PDF in the case database.

## Routes

| Method and path | Response |
| --- | --- |
| `POST /cases` | `201` Case. Body is optional: `title`, `jurisdiction` (`id`, `name`, `authority`). |
| `GET /cases/{case_id}` | Case, or `404` with detail `case not found`. |
| `POST /cases/{case_id}/facts` | Case. Body is a Fact. `422` when a `proposed` fact is sent as `confirmed`. `409` detail `case was updated concurrently` when the stored version changed during the write. |
| `POST /cases/{case_id}/files` | `201` `{ "id", "name", "size", "content_type" }`. Body is raw `application/pdf` (optional header `x-filename`) or multipart with one file part. Bytes go in `case_files`. `404` detail `case not found`. `413` detail `PDF too large: the limit is 4 MB. Try compressing the file or splitting it.` `415` detail `only PDF files are accepted`. |
| `DELETE /cases/{case_id}` | `204` empty body. Removes the case, its facts, its evidence, and its files. `404` detail `case not found`. |
| `GET /cases/{case_id}/gaps` | `{ "items", "meta" }`. `items` is the `completeness.Gap` list: `id`, `section` (`A` `B` `C` `D` `process`), `field`, `message`, `severity` (`blocking` or `warning`), `fix_hint`, `citation`. |
| `GET /code/search` | Query `q`, `division` (`A` `B` or `C`, default `B`), `limit` (1–20, default 20). `422` detail `The maximum is 20.` when `limit` is above 20. `429` detail `Search limit reached; try again in N seconds`, with a `Retry-After` header of N seconds. Default budget is 60 searches per 10 minutes per IP. `GET /ccmc/search` shares that budget. The window is in memory on each engine instance, so it is per instance, not a cap shared by every instance. The client IP is the first hop of `x-vercel-forwarded-for`, then `X-Forwarded-For`, then the peer address. Body is `{ "items", "meta" }`. Each hit has `id`, `division`, `level`, `article_title`, `title`, `text`, `citation`. |
| `GET /code/{provision_id}` | Query `division` only. Any other query parameter, including a sentence offset, page, or cursor, is `400` detail `this route accepts only division`. The codedb provision record, or `404` detail `provision not found`. `400` when the id is invalid or the division is ambiguous. |
| `POST /section-c` | Body `{ "provisions": ["…"] }`. `{ "items", "meta" }` where `items` is the `SectionCRow` list. `404` when a provision is missing from codedb. `400` on an invalid id. |
| `POST /cases/{case_id}/section-d` | Body optional `{ "provisions": ["…"] }`. `{ "items", "notices", "meta" }`. Writes the case. |
| `GET /cases/{case_id}/section-d/issues` | `{ "items", "meta" }`. `items` is the issue list below. Read-only. Does not write the case. |
| `GET /cases/{case_id}/professional` | `required` and `general_required`: `yes`, `no`, or `depends`. Also `reasons`, `questions`, `scope_note`. |
| `GET /ccmc/search` | Query `q` (1–200 characters) and `limit` (1–50, default 20). `422` on a rejected query. `503` when the registry is unavailable; that detail is the registry error text. `429` uses the same detail, `Retry-After` header, and per-IP window as `GET /code/search`. The two routes share that window. |
| `GET /cases/{case_id}/process-fields` | `{ "items", "meta" }`. `items` is the process-field list. Empty when the pathway is an acceptable solution. |
| `POST /cases/{case_id}/export` | Body optional `{ "draft": false }`. `200` is `application/pdf`. `409` detail is `{ "message": "export blocked; resolve these or export a draft", "reasons": […] }`. `503` detail `PDF export is unavailable on this deployment: SCC form not configured` when the blank form file is missing. `500` on other export failures. The PDF's NRC text is described under Exported PDF. |

A Case has `id`, `title`, `created_at`, `updated_at`, `jurisdiction`, `facts`, `provisions`, `section_c`, `evidence`, `gaps`. A Fact `kind` is `exact`, `pointed`, `computed`, or `proposed`. `status` is `confirmed` or `unconfirmed`. A `proposed` fact cannot be `confirmed`.

A fact's `source.type` is `code`, `file`, `user_text`, `drawing`, or `user_click`.

Gap `severity` is `blocking` or `warning`.

The fixed 404 detail strings are `case not found` and `provision not found`.

### Uploads

`POST /cases/{case_id}/files` is the single implementation of this upload. It is database-backed: the PDF is stored in `case_files`, and a file over 4 MB is HTTP 413 with `PDF too large: the limit is 4 MB. Try compressing the file or splitting it.` The body may be a raw `application/pdf` or multipart. A function disk is ephemeral, and Vercel stops request bodies at 4.5 MB. #21's PDF parser plugs in as a helper this route calls. There is no separate disk-backed route.

### NRC text budget

Every JSON response is under one budget for NRC code text. The budget counts provision text, objective and functional-statement wording, intent statements and notes, clauses, fact quotes, and search snippets. Identifiers, citations, and URLs are not counted.

`title` and `article_title` are headings, not provision sentences, so the clipper does not shorten them and they do not spend the 25-word snippet cap. They are not a place to repeat a provision. The route check counts seeded code-text words across the entire JSON body, including `message`, `fix_hint`, `reasons`, `title`, and `article_title`. That total is still at most 75. Engine prose in `message`, `fix_hint`, and `reasons` is administrative and does not carry provision sentences.

A single snippet is at most 25 words (`SNIPPET_MAX_WORDS`). The response carries at most 75 words of that text in total (`RESPONSE_NRC_MAX_WORDS`). Both limits apply. Words past either limit are not returned. A fact `quote` or `value` counts only when `source.type` is `code`. An applicant `user_text` quote is not code text, and it is not given the NRC marker or link. The object keeps its citation, gains the NRC publication link (`https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499` when the object had no link), sets `clipped` to true, and the clipped string is `… [clipped, see NBC p.N]`, where N is the `pdf_page` on that object, or `… [clipped, see NBC(AE) 2023]` when no page is known. An unclipped string has no marker, and an object with no clipped text has no `clipped` flag.

`GET /code/{provision_id}` accepts only `division`. It exposes no sentence offset, page, cursor, or other parameter a client can use to reassemble an article.

A clipped field is not a finding that a design complies.

### Exported PDF

`POST /cases/{case_id}/export` fills the Safety Codes Council form and appends a generated appendix. The form cells carry provision ids, objective and function codes, and a pointer to the appendix for the intent statement. They do not carry provision sentences.

The appendix carries the NRC text for each Section C row: the citation, objective and functional-statement titles, any application note, the provision text, and the NBC 2020 intent statements and their notes. Applicant-written process answers and other confirmed form values stay the applicant's words.

That NRC text follows the same snippet rules as a JSON response. Each snippet is 25 words or fewer, and the PDF keeps at most 75 words of NRC text in total. Beyond that budget the appendix keeps the citation and the NRC publication link, with `… [clipped, see NBC p.N]` (or `… [clipped, see NBC(AE) 2023]` when no page is known).

### Demo data and retention

Do not upload personal information. In live mode, text you enter is sent to OpenAI (US) for processing and is retained by OpenAI under its API data policy (https://openai.com/policies/api-data-usage-policies); Batatis deletes its own stored case data and files after 7 days or on request. Every JSON response includes that sentence as `meta.notice`. Every response also sends it in the `X-Batatis-Notice` header. A JSON array is returned as `{ "items": [...], "meta": { "notice": "..." } }`.

A case older than 7 days, measured from `created_at`, is deleted with its facts, evidence, and files. The purge runs when a case is accessed and on a sweep at the start of each request.

The engine log line is the method, the path, and the status. It does not include case JSON or uploaded bytes.

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

The live body is `{ "items": <the array below>, "meta": { "notice": "<the privacy notice>" } }`.

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
| 404 | Fixed detail strings are `case not found` and `provision not found`. Section C, the plan, and this issues route can also 404 with the text of a missing codedb provision. |
| 400 | Invalid provision id, an ambiguous division on `GET /code/{provision_id}`, or any query parameter other than `division` on that route (`this route accepts only division`). |
| 409 | Export is blocked. Detail is the object under Routes. `POST /cases/{case_id}/facts` also returns 409 with detail `case was updated concurrently`. |
| 413 | `POST /cases/{case_id}/files` when the PDF is over 4 MB. Detail is `PDF too large: the limit is 4 MB. Try compressing the file or splitting it.` |
| 415 | `POST /cases/{case_id}/files` when the body is not a PDF. Detail is `only PDF files are accepted`. |
| 422 | A `proposed` fact was sent as `confirmed`, `GET /code/search` `limit` is above 20 (detail `The maximum is 20.`), or `GET /ccmc/search` rejected the query. |
| 429 | `GET /code/search` or `GET /ccmc/search` when the caller is over the shared search rate limit. Detail is `Search limit reached; try again in N seconds`. The response also sets `Retry-After: N`. The limit is per engine instance (an in-memory window), per IP. |
| 500 | Export failed for a reason other than a missing form. |
| 503 | The code database file is absent. Body is exactly `{"detail": "code database not found"}`. Raised only by `CodeDbMissing` in `engine/codes.py`. Not a `FileNotFoundError`. The body has no server path. A missing SCC variance form is HTTP 503 with detail `PDF export is unavailable on this deployment: SCC form not configured`. An unavailable CCMC registry is also HTTP 503, and its detail is that error's own text. An unreachable case database is HTTP 503 with detail `case store unavailable`, and that body does not include the server address. |
| 200 | An unknown Division B token on this issues route does not 404. It returns `provision: null` and a question. |
