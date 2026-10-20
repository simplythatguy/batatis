# API contract

Engineer-needed flag (model-checked): rules_only 55/60 on the dev set (in-sample), 1 under-flag; shipped rules_plus_unknown: 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind). (on the 60 text-only dev cases it answered only yes or ask, 0 no, so 0 under-flags is partly by design; since 4425089 it can answer no when stated facts clear every trigger) Part 4 on text-only cases is derived from stated facts. A wood-frame building inside Part 9 with no Part 4 trigger is part4_design false, so the screen can answer no. On this dev set (model-checked, in-sample) the shipped screen still emits 0 no labels.

These are the routes the engine serves. There is no `POST /cases/{id}/files`.

## Routes

| Method and path | Response |
| --- | --- |
| `POST /cases` | `201` Case. Body is optional: `title`, `jurisdiction` (`id`, `name`, `authority`). |
| `GET /cases/{case_id}` | Case, or `404` with detail `case not found`. |
| `POST /cases/{case_id}/facts` | Case. Body is a Fact. `422` when a `proposed` fact is sent as `confirmed`. There is no `PATCH /cases/{case_id}/facts`. A `confirmed` status on `user_text` or `user_click` stays applicant-sourced. |
| `GET /cases/{case_id}/gaps` | `completeness.Gap` list: `id`, `section` (`A` `B` `C` `D` `process`), `field`, `message`, `severity` (`blocking` or `warning`), `fix_hint`, `citation`, `routed_to` (`officer`, `professional`, `applicant`, or null). |
| `GET /code/search` | Query `q`, `division` (`A` `B` or `C`, default `B`), `limit` (1–100, default 20). Hits as returned: `id`, `division`, `level`, `article_title`, `title`, `text`, `citation`. |
| `GET /code/{provision_id}` | Query `division` optional. The codedb provision record, or `404` detail `provision not found`. `400` when the id is invalid or the division is ambiguous. |
| `POST /section-c` | Body `{ "provisions": ["…"] }`. `SectionCRow` list. `404` when a provision is missing from codedb. `400` on an invalid id. |
| `POST /cases/{case_id}/section-d` | Body optional `{ "provisions": ["…"] }`. `{ "items", "notices" }`. Writes the case. |
| `GET /cases/{case_id}/section-d/issues` | Issue list below. Read-only. Does not write the case. |
| `GET /cases/{case_id}/professional` | `required` and `general_required`: `yes`, `no`, or `depends`. When a token is unresolved, `decision` and `general_decision` are the sentences to show. `involvement`: `professional_involved`, `not_required`, or `unresolved`. Also `reasons`, `questions`, `missing_facts`, `scope_note`. |
| `GET /ccmc/search` | Query `q` (1–200 characters) and `limit` (1–50, default 20). `422` on a rejected query. `503` when the registry is unavailable; that detail is the registry error text. |
| `GET /cases/{case_id}/process-fields` | Process-field list. Empty when the pathway is an acceptable solution. |
| `POST /cases/{case_id}/export` | Body optional `{ "draft": false }`. `200` is `application/pdf`. `409` detail is `{ "message": "export blocked; resolve these or export a draft", "reasons": […] }`. `503` when the blank form file is missing; that detail is the form error text. `500` on other export failures. |

A Case has `id`, `title`, `created_at`, `updated_at`, `jurisdiction`, `facts`, `provisions`, `section_c`, `evidence`, `gaps`. A Fact `kind` is `exact`, `pointed`, `computed`, or `proposed`. `status` is `confirmed` or `unconfirmed`. A `proposed` fact cannot be `confirmed`.

A fact's `source.type` is `code`, `file`, `user_text`, `drawing`, `user_click`, `officer`, or `professional`. `officer` and `professional` are authority sources. `user_text`, `user_click`, and `drawing` are applicant sources. `confirmed` does not change the source. Only an `officer`, `professional`, or `code` source can produce professional-screen `no`.

Gap `severity` is `blocking` or `warning`.

The fixed 404 detail strings are `case not found` and `provision not found`.

An `EvidenceItem` has `status` `needed`, `evidence_listed`, or `not_applicable`, and `kind` `text` or `file`. A stored `provided` value loads as `evidence_listed`. `kind` is `file` only when a confirmed file-source `evidence.<id>.file_ref` fact exists; otherwise it is `text`. A text item is listed by the applicant, has no file attached, and is not reviewed. Typed text does not write `file_ref`. `POST /cases/{case_id}/evidence` and `DELETE /cases/{case_id}/evidence/{evidence_id}` are not on this service.

### Section D plan item

`POST /cases/{case_id}/section-d` returns `{ "items", "notices" }`. Each item is `engine/section_d.py` `EvidencePlanItem`. Every plan item is a provision codedb already resolved. `provision_id` and `citation` sit on the item.

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

`required` and `general_required` are `yes`, `no`, or `depends`. The unresolved token means a deciding fact is missing. That route does not return `true`, `false`, or `"unknown"`. Show `decision` and `general_decision` for an unresolved screen. Each is a sentence naming the deciding question and who decides (`routed_to`): the officer, the applicant, or a registered professional. An unresolved reason `message` is the same kind of sentence. Those sentences do not render the unresolved token on its own, and they do not repeat it.

`involvement` is `professional_involved`, `not_required`, or `unresolved`. An alternative-solution case never counts `prescriptive_route_confirmed` as yes. A Yes on that route is a contradiction and clears nothing. Reserved professional judgement, professional scope, authority-requires-professional, and special-safety answers whose only source is the applicant stay unresolved. `professional_involved` is reached only when those answers come from an `officer`, `professional`, or `code` source and the applicant has confirmed an engineer or architect (normalised role match, for example `R. Singh, P.Eng.`, and a registration or seal number). That resolution is not `not_required`. If any Yes/No input to the screen is applicant-sourced, including a user-confirmed fact, the screen does not return `no`; it returns `depends`. That holds on an acceptable-solution case and on an alternative solution. Applicant answers on `special_safety_concerns` and `professional_scope_resolved` stay unresolved on both. The completeness gap is then exactly `Routed to the officer: whether a registered professional is required`, `routed_to` `officer`, severity `blocking`. That gap blocks the official PDF. A draft export stays allowed. `questions` remains a list of strings. `prompts` repeats each question with `help` (what Yes means and what No means) and `not_sure` (`Not sure (the officer decides)`). A Not sure answer is an open item routed to the officer.

The Section D professional fields `engineer_engaged` and `architect_engaged` (engineer or architect engaged) and `registered_professional` accept the explicit answers `not_sure` and `not_engaged_yet`. Both stay unresolved. They are not a `no`. On the issues route the practice flag is `unknown`. The completeness gap is exactly `Routed to the officer: whether a registered professional is required`, `routed_to` `officer`, severity `blocking`. That is the same rule as an applicant-sourced yes or no. `not_engaged_yet` is not `professional_status` `not_engaged`.

`professional_status` is `not_engaged` when a confirmed applicant fact (`user_text` or `user_click`) states `not_engaged` or `No professional engaged yet`. A file or an officer note does not set it. That statement does not confirm a professional and does not write a registration number or a seal. The blocking professional-involvement gaps (named professional, qualifications, authentication) become one gap: `Professional involvement not yet confirmed; the officer decides whether it is required.`, severity `warning`, `routed_to` `officer`. Official export stays allowed. The exported package lists that sentence under open items. When this statement is absent, the officer gap sentence above is unchanged.

The issues route maps the same screen: `yes` → `true`, `no` → `false`, `depends` → `"unknown"`. `"unknown"` requires a question. Those two tokens are not the same. An `"unknown"` issue `reason` and the professional-requirement gap name the deciding question and who decides. They do not render the unresolved token.

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
| `citation` | string or null | That rule's citation from the code database. Omitted when the rule does not resolve. The rule id is one `engine/professional.py` already passes to its screen. |
| `reason` | string | Recommendation tied to the rule. When `value` is `"unknown"`, the sentence names the deciding question and who decides (`routed_to`). |
| `question` | string or null | Required when `value` is `"unknown"`: the deciding question, not a generic stand-in unless every specific question was unusable. When `value` is `true`, the question asks the applicant for the registered professional's name, discipline (engineer or architect), and APEGA or AAA registration number. A seal the applicant confirms can stand in for the number. The service does not fill those fields. |
| `prompts` | object[] | Each asked question: `text`, `help`, `not_sure`. `help` says what Yes and No mean. `not_sure` is `Not sure (the officer decides)`. |
| `routed_to` | string or null | `officer`, `professional`, or `applicant`, same as the issue. |

Confirmed `professional.span_m` (or `span_m`) above 12.20 m is recorded as Part 4 design. This span handoff came from development case dev-050. The cited rule is Div C 2.4.1.2.(1), the same provision `engine/professional.py` already uses for Part 4 design. No other provision id is added for the span.

### `status`

| Value | When |
| --- | --- |
| `needs_professional` | `practice_of_engineering.value` is `true` and the applicant has not confirmed a registered-professional role of engineer or architect together with a seal or a registration number. The confirmation is `user_text` or an explicit confirmation (`user_click`). A name or seal on an uploaded document does not count, and the service does not infer one. Not a sign-off or compliance determination. |
| `evidence_listed` | An applicant-supplied item is linked to the issue, the practice flag is not `"unknown"`, and a `true` flag also has that confirmed role and seal or registration number. Listing the item is not a sign-off or compliance determination. |
| `open` | No applicant-supplied item is linked, or the practice flag is `"unknown"`. Not a sign-off or compliance determination. |

The UI does not read the old issue status `addressed`, so that token is not accepted as an alias. Plan-item `needed` and `evidence_listed` are also not a sign-off or compliance determination. A stored evidence status `provided` loads as `evidence_listed`. The issues route does not write the case and does not fill the professional's name, discipline, or registration number.

`human_review` is routing, not a determination. Every row has `source`: `codedb` or `statute`. Code `cite` values are copied from the code database; a provision that does not resolve is left off the list. Codedb rows are only the mandatory `verification_class` `codedb-only` triggers, in this order: `HR-03` (Div C 2.4.1.2.(1)), `HR-01` (Div C 2.4.1.1.(3)), `HR-06`, `HR-07`, `HR-05`, `HR-04`, `HR-11`, `HR-14`, `HR-13`, `HR-12`. Each of those can push the practice flag toward yes, which is `needs_professional` until a registered professional is confirmed. The other 11 codedb-only triggers are discretionary or an authority-having-jurisdiction acceptance (`HR-15`, `HR-17`, `HR-31`, `HR-32`, `HR-33`, `HR-34`, `HR-35`, `HR-40`, `HR-41`, `HR-42`, `HR-44`). They set `routed_to` `officer` and do not push yes, and they are not `human_review` rows. Mixed code triggers stay off, including `HR-02`, `HR-08`, `HR-10`, `HR-16`, `HR-20`, and `HR-43`. There is no Table 2.4.2.1. A Division B `3.8` provision, `requests_interpretation`, and a dimensional difference of not more than 2% are in that officer route. Statute rows are emitted only for a pinpoint confirmed from the Act. `HR-21` dwelling units cite `EGPA s.2(7)(b)(ii)`. `HR-22` cites `Architects Act s.2(6)(b)(ii)`. Their `why` is `counts dwelling units (4 or less); whether a suite counts is for the officer`. `EGPA s.2(7)(a)` is emitted only for assembly or institutional occupancy. Other occupancies get no Act gross-area row. `HR-30` cites `Safety Codes Act s.38(1)`. A statute row carries `act` (full name, RSA chapter, current-as-of date) and a verbatim `quote`. `total_unit_count` includes suites. Above 4, the practice flag can be yes and cites Div C 2.4.1.1.(5), the codedb authentication sentence. An unsettled gross area is medium confidence: the flag is unknown and asks. It does not answer no. `gross_area_per_floor_m2` and `total_unit_count` are confirmed facts. The code screen still uses building area and principal dwelling units.

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
| 400 | Invalid provision id, or an ambiguous division on `GET /code/{provision_id}`. |
| 409 | Export is blocked. Detail is the object under Routes. |
| 422 | A `proposed` fact was sent as `confirmed`, or `GET /ccmc/search` rejected the query. |
| 500 | Export failed for a reason other than a missing form. |
| 503 | The code database file is absent. Body is exactly `{"detail": "code database not found"}`. Raised only by `CodeDbMissing` in `engine/codes.py`. Not a `FileNotFoundError`. The body has no server path. A missing blank form and an unavailable CCMC registry are also HTTP 503, and their detail is that error's own text. |
| 200 | An unknown Division B token on this issues route does not 404. It returns `provision: null` and a question. |
