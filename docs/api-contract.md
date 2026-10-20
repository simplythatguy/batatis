# API contract

Engineer-needed flag (model-checked): rules_only 55/60 on the dev set (in-sample), 1 under-flag; shipped rules_plus_unknown: 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind).

These are the routes the engine serves. There is no `POST /cases/{id}/files`. `file_id` on listed evidence is an opaque applicant reference. The engine does not read file bytes.

`evidence_listed` means the applicant listed evidence; not a check that it is sufficient, and not a compliance determination.

## Routes

| Method and path | Response |
| --- | --- |
| `POST /cases` | `201` Case. Body is optional: `title`, `jurisdiction` (`id`, `name`, `authority`). |
| `GET /cases/{case_id}` | Case, or `404` with detail `case not found`. |
| `POST /cases/{case_id}/facts` | Case. Body is a Fact. `422` when a `proposed` fact is sent as `confirmed`. |
| `PUT /cases/{case_id}/facts` | `{updated, professional, case}`. Partial building facts, including `span_m`. `422` when the body is empty or a value is outside the typed lists. `404` when the case is missing. |
| `POST /cases/{case_id}/description` | `{alternative_description, facts}`. Extracted facts are unconfirmed. `404` when the case is missing. `422` on a bad body. |
| `POST /cases/{case_id}/evidence` | `201` `{evidence, gaps, closed}`. `400` when the benchmark or pair is not on the plan. `404` when the case is missing. `422` on a bad body. |
| `DELETE /cases/{case_id}/evidence/{evidence_id}` | `204` empty body. `404` detail `evidence not found` or `case not found`. |
| `GET /cases/{case_id}/gaps` | `completeness.Gap` list: `id`, `section` (`A` `B` `C` `D` `process`), `field`, `message`, `severity` (`blocking` or `warning`), `fix_hint`, `citation`, and for evidence gaps `provision_id` and `pairs` (`{function, objective}`). Evidence gap text does not say the evidence was addressed, satisfied, or compliant. |
| `GET /code/search` | Query `q`, `division` (`A` `B` or `C`, default `B`), `limit` (1–100, default 20). Hits as returned: `id`, `division`, `level`, `article_title`, `title`, `text`, `citation`. |
| `GET /code/{provision_id}` | Query `division` optional. The codedb provision record, or `404` detail `provision not found`. `400` when the id is invalid or the division is ambiguous. |
| `POST /section-c` | Body `{ "provisions": ["…"] }`. `SectionCRow` list. `404` when a provision is missing from codedb. `400` on an invalid id. |
| `POST /cases/{case_id}/section-d` | Body optional `{ "provisions": ["…"] }`. `{ "items", "notices" }`. Writes the case. |
| `GET /cases/{case_id}/section-d/issues` | Issue list below. Read-only. Does not write the case. |
| `GET /cases/{case_id}/professional` | `required` and `general_required`: `yes`, `no`, or `depends`. Also `reasons`, `questions`, `scope_note`. |
| `GET /ccmc/search` | Query `q` (1–200 characters) and `limit` (1–50, default 20). `422` on a rejected query. `503` when the registry is unavailable; that detail is the registry error text. |
| `GET /cases/{case_id}/process-fields` | Process-field list. Empty when the pathway is an acceptable solution. |
| `POST /cases/{case_id}/export` | Body optional `{ "draft": false }`. `200` is `application/pdf`. `409` detail is `{ "message": "export blocked; resolve these or export a draft", "reasons": […] }`. `503` when the blank form file is missing; that detail is the form error text. `500` on other export failures. |

A Case has `id`, `title`, `created_at`, `updated_at`, `jurisdiction`, `facts`, `provisions`, `section_c`, `evidence`, `gaps`. A Fact `kind` is `exact`, `pointed`, `computed`, or `proposed`. `status` is `confirmed` or `unconfirmed`. A `proposed` fact cannot be `confirmed`.

A fact's `source.type` is `code`, `file`, `user_text`, `drawing`, `user_click`, or `description`.

Gap `severity` is `blocking` or `warning`.

The fixed 404 detail strings are `case not found` and `provision not found`.

### Section D plan item

`POST /cases/{case_id}/section-d` returns `{ "items", "notices" }`. Each item is `engine/section_d.py` `EvidencePlanItem`. Every plan item is a provision codedb already resolved. `provision_id` and `citation` sit on the item.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable id for this provision and attribution pair. |
| `provision_id` | string | Division B provision id codedb resolved. |
| `citation` | string | Citation string copied from the code database. |
| `status` | string | `not provided` or `provided`. This is the plan-item file flag. It is not `EvidenceItem.status`. |
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

## Building facts, description, and listed evidence

`PUT /cases/{case_id}/facts` appends one confirmed `pointed` fact per field that was sent (`source.type` `user_text`, `source.ref` `applicant`). Omitted fields stay as they are. JSON `null` does not clear a field. Fields are the `ProfessionalFacts` names plus `span_m` (number > 0). `occupancy` is `single_family`, `multi_family`, `hotel`, `assembly`, `care`, `treatment`, `detention`, `business`, `mercantile`, `industrial`, `farm`, `relocatable_industrial_camp`, `mixed`, or `other`. Response `professional` is the screen after the write. A confirmed `span_m` above 12.20 m is Part 4 design on that screen only. The route does not write a `part4_design` fact.

`POST /cases/{case_id}/description` body is `{text}` (1–8000 characters). Response facts are `storeys`, `building_area_m2`, `span_m`, `occupancy`, and `alternative_description`, each unconfirmed, with `source` the string `description`. Stored facts use `source.type` `description`. A question is left out of `alternative_description` and is not mined: the clause or sentence that contains `?`, or a sentence that starts with what/how/why/when/where/which/who. Splits are sentence ends, line breaks, and `;` or `—`. The rest of the row stays. Occupancy comes from a word for the building or its use, not from a product or process adjective such as `factory-bonded`. One residential category wins when another category is also present; a conflict with no single residential category stays empty. The production extractor is `normalised` (`evals_dev/description_facts/RESULTS.md`, synthetic, in-sample). Held-out text is in `evals_dev/description_facts/HELD_OUT.md` and is agent-labelled, not human-verified.

`POST /cases/{case_id}/evidence` body: `provision_id`, `evidence_type`, `description` (1–4000 characters), optional `objective` and `function` together, optional `file_id` (1–200 characters). The stored `EvidenceItem.status` is `evidence_listed` and `professional_required` is null. `evidence_listed` means the applicant listed evidence; not a check that it is sufficient, and not a compliance determination. Other stored statuses are `needed` and `not_applicable`.

`gaps` is the remaining grouped list. `closed` entries are `{provision_id, pairs, reason}` and `reason` is `evidence listed (not reviewed)`. Evidence with no objective and no function closes every open pair on that provision. A pair closes only that pair. `400` detail `confirm this Division B benchmark before attaching evidence` or `that objective/function pair is not on the attribution for this provision`.

Open evidence gaps from `GET /cases/{id}/gaps` use `id` `evidence:{provision_id}`, `field` `evidence.{provision_id}`, and `pairs`. A provision with no objective and no function is one warning, `id` `evidence_scope:{provision_id}`. Evidence gap text does not say the evidence was addressed, satisfied, or compliant. A plan item whose status is `provided` is a confirmed file-source `evidence.<id>.file_ref` fact. That plan flag is separate from `evidence_listed`.

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
| `status` | string | `open`, `addressed`, or `needs_professional`. This is the issues enum. The plan route uses `not provided` or `provided`. Stored evidence uses `evidence_listed`, not this enum. |

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
| `addressed` | An applicant-supplied file is linked to the issue (and, if a professional is indicated, a responsible party or seal is named). This records that the file was linked. It does not assess the item. `GET /cases/{id}/gaps` does not use this word. Listing evidence on `POST /cases/{id}/evidence` closes a gap with reason `evidence listed (not reviewed)`. |
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
