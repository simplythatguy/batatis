# Engine HTTP contract

Shapes below are the routes on this branch. Completeness is administrative. A `provided` evidence item records what the applicant supplied. It does not verify the document, and it does not say the design complies or is safe.

There is no upload route here. `file_id` is an opaque applicant reference. The engine does not read file bytes.

`GET /cases/{id}/section-d/issues` is not on this branch.

## Cases and facts

`POST /cases` → `201` `Case`. Body optional: `title`, `jurisdiction` (`id`, `name`, optional `authority`).

`GET /cases/{case_id}` → `200` `Case`, or `404` `case not found`.

`Case` fields: `id`, `title`, `created_at`, `updated_at`, `jurisdiction`, `facts`, `provisions`, `section_c`, `evidence`, `gaps`.

`POST /cases/{case_id}/facts` → `200` `Case`, `404`, or `422`. Body is one `Fact`:

| field | type |
| --- | --- |
| `field` | string |
| `value` | string, number, boolean, or null |
| `kind` | `exact`, `pointed`, `computed`, or `proposed` |
| `source` | `{type, ref, page?, bbox?, quote?}` |
| `status` | `confirmed` or `unconfirmed` (default `unconfirmed`) |
| `confidence` | number 0–1, optional |
| `formula`, `inputs` | computed facts only |

`source.type` is `code`, `file`, `user_text`, `drawing`, `user_click`, or `description`. A `proposed` fact cannot be `confirmed`.

`PUT /cases/{case_id}/facts` → `200`, `404`, or `422`. Partial update of typed building facts. Omitted fields are left as they are. JSON `null` does not clear a field. An empty object is `422` with `no building facts were sent`. Unknown names and values outside the lists below are `422`.

Each sent field is appended as a confirmed `pointed` fact, `source.type` `user_text`, `source.ref` `applicant`. Response:

```json
{"updated": ["occupancy", "storeys"], "professional": {}, "case": {}}
```

`updated` is the sent field names in model order. `professional` is `ProfessionalResult` after the write, so the screen is re-evaluated. `case` is the stored case.

Fields (all optional): `occupancy`, `storeys` (integer ≥ 1), `building_area_m2` (number > 0), `principal_dwelling_units` (integer ≥ 1), `farm_public_use`, `part4_design`, `preserved_wood_foundation_part4`, `roof_trusses`, `prescriptive_route_confirmed`, `ahj_requires_professional`, `special_safety_concerns`, `professional_judgement_required`, `professional_scope_resolved`, `fire_suppression`, `fire_alarm`, `span_m` (number > 0).

`occupancy` is one of `single_family`, `multi_family`, `hotel`, `assembly`, `care`, `treatment`, `detention`, `business`, `mercantile`, `industrial`, `farm`, `relocatable_industrial_camp`, `mixed`, `other`.

`span_m` is the field PR #8 (`backend/section-d-issues`, not merged) reads as `span_m` or `professional.span_m`. A confirmed span above `12.20` (`PART9_MAX_SPAN_M` in `engine/professional.py`, the same threshold as that branch’s `section_d_issues.py`) is treated as Part 4 design for the screen only. The route does not write a `part4_design` fact. The screen still cites the Part 4 provision `professional.py` already looks up.

`ProfessionalResult`: `required` and `general_required` are `yes`, `no`, or `depends`; `reasons` (`code`, `required`, `message`, `citation`); `questions`; `scope_note`.

## Description

`POST /cases/{case_id}/description` → `200`, `404`, or `422`. Body `{text}` (1–8000 characters). Extra fields are rejected.

Response: `alternative_description` (string or null) and `facts`:

| field | type |
| --- | --- |
| `field` | `storeys`, `building_area_m2`, `span_m`, `occupancy`, or `alternative_description` |
| `value` | number or string |
| `source` | the string `description` |
| `quote` | the sentence the value was taken from |
| `status` | `unconfirmed` |

Stored facts are `pointed`, `unconfirmed`, `source.type` `description`, `source.ref` `description`. The applicant confirms them with the existing fact route. Question sentences (a `?`, or a sentence that starts with what/how/why/when/where/which/who) are left out of `alternative_description` and are not mined. The production extractor is the `normalised` winner in `evals_dev/description_facts/RESULTS.md`.

## Evidence

`POST /cases/{case_id}/evidence` → `201`, `400`, `404`, or `422`.

| field | type |
| --- | --- |
| `provision_id` | string, required |
| `objective` | string, optional; send with `function` or omit both |
| `function` | string, optional |
| `evidence_type` | one ladder or alternative type below |
| `description` | string, required, 1–4000 characters after trim |
| `file_id` | string, optional, 1–200 characters; not file bytes |

Evidence types: `manufacturer's literature`, `existing STANDATA variance`, `ISO 17025 test report`, `evaluation`, `evaluation + testing`, `qualification`, `ISO 17065 certification`, `CCMC evaluation`, `ICC-ES evaluation`, `registered professional opinion`, `engineering review`.

The provision must already be on the Section D plan (`400` `confirm this Division B benchmark before attaching evidence`). A pair must match a plan item (`400` `that objective/function pair is not on the attribution for this provision`). The stored `EvidenceItem` has `status` `provided` and `professional_required` null.

Response: `{evidence, gaps}`. `gaps` is the remaining grouped list for the current plan (same objects as below). Evidence with no objective and no function closes every open pair on that provision. A pair closes only that pair.

`DELETE /cases/{case_id}/evidence/{evidence_id}` → `204` empty body, or `404` `evidence not found` / `case not found`.

## Grouped evidence gaps

`GET /cases/{case_id}/gaps` → `200` list, or `404`. Each gap has `id`, `section`, `field`, `message`, `severity` (`blocking` or `warning`), `fix_hint`, `citation`, and, for evidence gaps, `provision_id` and `pairs` (`{function, objective}`).

Open objective/function pairs on one provision are one blocking gap:

- `id`: `evidence:{provision_id}`
- `field`: `evidence.{provision_id}`
- `message`: `Your application appears to be missing supporting evidence for {provision_id}.`
- `pairs`: the uncovered pairs

A plan item whose Section D status is already `provided` (a confirmed file-source `evidence.<id>.file_ref` fact) is covered. A provision with no objective and no function is one warning, `id` `evidence_scope:{provision_id}`, `pairs` empty. No objective or function is inferred.

`engine/evidence_gaps.py` is the function PR #11 should call. That branch still adds one gap per pair (`evidence:{plan item id}`, message `supporting evidence for {provision}, {function}–{objective}`). Replace that loop with `uncovered_items` plus `group_evidence_gaps`. Provision-scoped evidence (`provision_id` set) is not also an attachment gap; a file id is optional.

## Code, Section C, Section D, review

`GET /code/search?q=&division=B&limit=20` → list of `{id, division, level, article_title, title, text, citation}`. `division` is `A`, `B`, or `C`. `limit` is 1–100.

`GET /code/{provision_id}?division=` → the codedb record, `400` for a bad or ambiguous id, `404` if missing. Intent rows attach only for Division B, and a comparison status `provision_missing_in_ae` is omitted. Division A and C citations do not receive bare-id intent rows.

`POST /section-c` body `{provisions: [id, ...]}` → `200` list of `SectionCRow`, `400`, or `404`. Attribution is a lookup: own row (`direct`, `attributed_via` null), else an ancestor clause, sentence, or article row (`inherited from parent`, `attributed_via` that source id), else `no row in the attribution table` with empty `pairs`. Sibling sentences are not copied. Nothing is invented when the article has no row of its own.

`POST /cases/{case_id}/section-d` → `200` `SectionDPlan` (`items`, `notices`), `400`, or `404`. Optional body `{provisions}` replaces the case provisions, then Section C is looked up and stored.

`GET /cases/{case_id}/professional` → `200` `ProfessionalResult` (includes the span screen above).

`GET /ccmc/search?q=&limit=20` → `200` registry search, `422`, or `503`.

`GET /cases/{case_id}/process-fields` → `200` list. On the alternative path each item has `id` (`rationale`, `risk_assessment`, `mitigating_measures`, `assumptions_and_limits`, `maintenance_operation`, `qualifications`), `label`, `prompt`, `reviewer_looks_for`, `citation`, `required`, `answer`. Answers are confirmed applicant text. This route does not write them.

`POST /cases/{case_id}/export` body optional `{draft: false}` → `200` `application/pdf`, `409` when export is blocked (`reasons`), `503` when the form is missing, `500` on export failure.
