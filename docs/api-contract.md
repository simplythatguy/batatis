# API contract

Engineer-needed flag (model-checked): rules_only 55/60 on the dev set (in-sample), 1 under-flag; shipped rules_plus_unknown: 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind).

These are the routes the engine serves. There is no `POST /cases/{id}/files`.

## Routes

| Method and path | Response |
| --- | --- |
| `POST /cases` | `201` Case. Body is optional: `title`, `jurisdiction` (`id`, `name`, `authority`). |
| `GET /cases/{case_id}` | Case, or `404` with detail `case not found`. |
| `POST /cases/{case_id}/facts` | Case. Body is a Fact. `422` when a `proposed` fact is sent as `confirmed`. |
| `POST /cases/{case_id}/identify` | Ranked article cards. Does not write `provisions`. See Identify. |
| `GET /cases/{case_id}/identify` | The stored card payload from the last identify call, or `404` detail `identify result not found`. |
| `GET /cases/{case_id}/identify/stream` | Query `prose`. Server-sent stage events. See Identify. |
| `POST /cases/{case_id}/identify/{provision_id}/decision` | Body `{ "decision": "yes" \| "no" \| "not_sure" }`. Returns a `SectionCRow`. See Identify. |
| `GET /cases/{case_id}/information-request` | Officer draft: `{ "case_id", "items" }`. Each `not_sure` decision is an item with `id`, `provision_id`, and `text`. |
| `POST /cases/{case_id}/identify/confirm` | Body `{ "provisions": ["…"] }`. Writes `provisions` and Section C after a codedb check. |
| `GET /cases/{case_id}/gaps` | `completeness.Gap` list: `id`, `section` (`A` `B` `C` `D` `process`), `field`, `message`, `severity` (`blocking` or `warning`), `fix_hint`, `citation`. |
| `GET /code/search` | Query `q`, `division` (`A` `B` or `C`, default `B`), `limit` (1–100, default 20). Hits as returned: `id`, `division`, `level`, `article_title`, `title`, `text`, `citation`. |
| `GET /code/{provision_id}` | Query `division` optional. The codedb provision record, or `404` detail `provision not found`. `400` when the id is invalid or the division is ambiguous. |
| `POST /section-c` | Body `{ "provisions": ["…"] }`. `SectionCRow` list. `404` when a provision is missing from codedb. `400` on an invalid id. |
| `POST /cases/{case_id}/section-d` | Body optional `{ "provisions": ["…"] }`. `{ "items", "notices" }`. Writes the case. |
| `GET /cases/{case_id}/section-d/issues` | Issue list below. Read-only. Does not write the case. |
| `GET /cases/{case_id}/professional` | `required` and `general_required`: `yes`, `no`, or `depends`. Also `reasons`, `questions`, `scope_note`. |
| `GET /ccmc/search` | Query `q` (1–200 characters) and `limit` (1–50, default 20). `422` on a rejected query. `503` when the registry is unavailable; that detail is the registry error text. |
| `GET /cases/{case_id}/process-fields` | Process-field list. Empty when the pathway is an acceptable solution. |
| `POST /cases/{case_id}/export` | Body optional `{ "draft": false }`. `200` is `application/pdf`. `409` detail is `{ "message": "export blocked; resolve these or export a draft", "reasons": […] }`. `503` when the blank form file is missing; that detail is the form error text. `500` on other export failures. |

A Case has `id`, `title`, `created_at`, `updated_at`, `jurisdiction`, `facts`, `provisions`, `section_c`, `evidence`, `gaps`. A Fact `kind` is `exact`, `pointed`, `computed`, or `proposed`. `status` is `confirmed`, `unconfirmed`, `open`, or `unknown`. A `proposed` fact cannot be `confirmed`.

A fact's `source.type` is `code`, `file`, `user_text`, `drawing`, or `user_click`.

Gap `severity` is `blocking` or `warning`.

The fixed 404 detail strings are `case not found` and `provision not found`. A case that has not been identified is `identify result not found`.

## Identify

`POST /cases/{id}/identify` is the primary call. Body:

```json
{"prose": "applicant description", "answers": [{"field": "building.storeys", "answer": "not sure"}]}
```

`GET /cases/{id}/identify/stream?prose=` and `POST` with `Accept: text/event-stream` emit stage events in order: `screen`, `rerank`, `verify`, `questions`, `done`. They are stage markers, not tokens.

Identify does not write `provisions` and does not accept an article onto the case. A ranking hint is not a Yes.

An answer of "not sure" or unknown on an intake question is stored as a fact with status `unknown` and is returned in `open_questions`. Identification continues. That intake answer is separate from the per-article decision below.

`open_questions` entries have `field`, `text`, `why`, and `status` (`open` or `unknown`). The question id is stable for that field.

Every identify response has `mode`: `live`, `cached_demo`, or `bm25_fallback`. `cached` is `true` only when `mode` is `cached_demo`. That replay is the stored demo cache. It does not accept an article. Any other description that cannot call the live ranker is `bm25_fallback` with `cached` `false`. When that path cannot read the code database, the response is still HTTP 200 with empty `articles` and no citation.

`GET /cases/{id}/identify` returns that same body after POST or the stream. A case that has not been identified is HTTP 404 with detail `identify result not found`.

When a live identify needs the code database and the file is missing, the response is HTTP 503 with the fixed detail `code database not found`. The body does not include a filesystem path.

### Article card

| Field | Type | Meaning |
| --- | --- | --- |
| `provision` | string | Article id, such as `9.10.15.5.` |
| `provision_id` | string or null | Sentence id when one codedb sentence contains the quote. Otherwise null. |
| `title` | string or null | Article title from the identify result. |
| `status` | string | `suggested`, `candidate`, or `unknown`. A ranking hint. Not an acceptance. |
| `decision` | string or null | `yes`, `no`, or `not_sure` after the decision route. Null until the user decides. |
| `open_question_id` | string or null | Stable id of the open question when `decision` is `not_sure`. Otherwise null. |
| `why` | string or null | The match reason already on the article. |

### Article decision

`POST /cases/{id}/identify/{provision_id}/decision` with `{ "decision": "yes" | "no" | "not_sure" }` records the user's choice for one ranked article. `provision_id` may be the article id or the sentence id on that card.

The response is a `SectionCRow`: the deterministic Section C lookup for that article. `explainer` on the row is a note on the quoted text. It is not a finding that the design meets the Code. `not_sure` and `no` still return the row when the lookup succeeds, and they do not add the article to `provisions`.

The same route may instead return the stored identify body (`articles` and `section_c`). `open_question_id` is on the matching article. A bare `SectionCRow` has no question id; that id is then the matching item from `GET /cases/{id}/information-request`.

`yes` writes one confirmed `user_click` citation and adds the article to `provisions`. `not_sure` removes that citation and opens one question. The question id is stable for the case and article (`open_question_id`). `GET /cases/{id}/gaps` includes it (`section` `C`, `severity` `warning`, `id` equal to that question id). `GET /cases/{id}/information-request` includes the same id, the article, and the question text in `items`. `no` removes the citation and the open question.

The same decision posted again does not add a second citation or a second question.

An unknown article is HTTP 404 detail `provision not found`. A case with no identify result is HTTP 404 detail `identify result not found`. Another `decision` value is HTTP 422.

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
| 404 | Fixed detail strings are `case not found` and `provision not found`. Section C, the plan, and this issues route can also 404 with the text of a missing codedb provision. |
| 400 | Invalid provision id, or an ambiguous division on `GET /code/{provision_id}`. |
| 409 | Export is blocked. Detail is the object under Routes. |
| 422 | A `proposed` fact was sent as `confirmed`, or `GET /ccmc/search` rejected the query. |
| 500 | Export failed for a reason other than a missing form. |
| 503 | The code database file is absent. Body is exactly `{"detail": "code database not found"}`. Raised only by `CodeDbMissing` in `engine/codes.py`. Not a `FileNotFoundError`. The body has no server path. A missing blank form and an unavailable CCMC registry are also HTTP 503, and their detail is that error's own text. |
| 200 | An unknown Division B token on this issues route does not 404. It returns `provision: null` and a question. |
