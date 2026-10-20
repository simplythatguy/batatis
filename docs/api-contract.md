# API contract

Administrative completeness only. A response never certifies that a design complies or is safe.
Citations are returned only when they are in the code database.

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
| `POST /cases/{case_id}/identify/{provision_id}/decision` | Body `{ "decision": "yes" \| "no" \| "not_sure" }`. `yes` adds a `user_click` citation. `not_sure` opens a question. `no` records an exclusion. |
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

The fixed 404 detail strings are `case not found` and `provision not found`.


## Identify

`POST /cases/{id}/identify` is the primary call. Body:

```json
{"prose": "applicant description", "answers": [{"field": "building.storeys", "answer": "not sure"}]}
```

`GET /cases/{id}/identify/stream?prose=` and `POST` with `Accept: text/event-stream` emit stage events in order: `screen`, `rerank`, `verify`, `questions`, `done`. They are stage markers, not tokens.

The same function serves `engine/cli_sut.py`. Identify does not write `provisions` and does not accept an article onto the case. Model confidence at or above 0.75 is a ranking hint only. It sets `status` to `suggested`. It does not create a citation.

An answer of "not sure" or unknown on an intake question is stored as a fact with status `unknown` and is returned in `open_questions`. Identification continues. That intake answer is separate from the per-article decision below.

`open_questions` has at most about five targeted questions, plus any unknown answer that did not already appear. Each question has `field`, `text`, `why`, `status` (`open` or `unknown`), and `disambiguates` (candidate article ids). An unconfirmed value is asked back as a confirmation.

`variance_needed` is `not_indicated`, `likely`, or `unknown`. When nothing has confirmed a departure, the explanation is:

> No departure from the acceptable solution has been identified; if the design follows the cited acceptable solution, a variance may not be needed. Confirm with your Safety Codes Officer.

That sentence is not a compliance finding. `intake_action` is `redirect` for a request that belongs to the plumbing, electrical, gas, or private-sewage regime, which is where the development-case gold schema uses `redirect`. `redirect_to` names that regime.

Each item in `section_c`, including the rows under `benchmark.section_c`, uses `provision_id`, the same field as `SectionCRow`.

`benchmark` is one Division B article the proposal is measured against, or `identified: false` plus a question. `commit_policy.status` is `placeholder_uncalibrated` for the 0.75 threshold and the cap of 3 until `evals_dev/human_key/calibration.json` says `calibrated`.

`POST /cases/{id}/identify/confirm` with `{"provisions": ["9.10.15.5.(8)"]}` checks each id in the code database, then writes `provisions` and Section C. An unknown id returns 404 and leaves the case unchanged.

Every identify response has `mode`: `live`, `cached_demo`, or `bm25_fallback`.

`live` is used only when `OPENAI_API_KEY` is set and `BATATIS_LIVE` is `1` (also `true`, `yes`, or `on`). `BATATIS_OFFLINE=1` forces the non-live path even if both of those are set. The benchmark command calls `pipeline.run` directly and does not read `BATATIS_LIVE`.

Without a live call, a description whose normalized text matches a seeded demo case is the stored cache in `engine/identify/demo_cache.json`, with `mode` `cached_demo` and `source` `cache`. The cache key is the SHA-256 of the description after Unicode NFC, with surrounding whitespace removed and internal whitespace collapsed to one space. Answers are not part of the key. The seeded descriptions are `dev-001`, `dev-003`, and `dev-013`. Any other description is BM25: `mode` `bm25_fallback`, `source` `bm25`, `section_c` empty, and no article is `suggested`. When that BM25 path cannot read the code database, the response is still HTTP 200 with empty `articles` and no citation. It does not invent an article.

`GET /cases/{id}/identify` returns that same body after POST or the stream. It does not write `provisions`. A case that has not been identified is HTTP 404 with detail `identify result not found`.

When a live identify needs the code database and the file is missing, the response is HTTP 503 with the fixed detail `code database not found`. The body does not include a filesystem path. A live call that fails with an authentication, network, or timeout error uses the same non-live path as a missing key.

`scripts/build_demo_cache.py` records a fresh live result for the three seeded cases when `OPENAI_API_KEY` is set, and it exits without writing a file when the key is absent.

### Article card

Each item in `articles` keeps `provision` (the Division B article id) and adds the fields below. `provision_id` and `benchmark_acceptable_solution` are the same sentence id when one codedb sentence, or one stored Section C row, contains the article's verbatim quote. More than one match, or no match, leaves both null. The service does not pick a first sentence and does not invent an id such as `9.9.10.1.(2)`.

| Field | Type | Meaning |
| --- | --- | --- |
| `rank` | number | 1-based order of the returned articles. |
| `provision` | string | Article id, such as `9.10.15.5.` |
| `provision_id` | string or null | Sentence id, such as `9.10.15.5.(8)`, when resolved as above. |
| `link` | string | Article lookup, `/code/{provision}?division=B`. |
| `citation` | string or null | Citation copied from codedb, or from the stored Section C row when the database is not open. |
| `title` | string | Article title from the identify result. |
| `snippet` | string or null | First 25 words of the resolved codedb sentence, or of the stored quote when the database is not open. Whitespace collapsed. Not a paraphrase. |
| `status` | string | Ranking hint. `suggested` when the model probability is at least 0.75 and the suggest cap and part rule would have marked it. `candidate` when a verifier ran and the article is not suggested. `unknown` for BM25 and for a cached demo replay. This is not an acceptance. |
| `verifier_status` | string | The same value as `status`. |
| `decision` | string or null | `yes`, `no`, or `not_sure` after `POST .../decision`. Null until the user decides. |
| `open_question_id` | string or null | Stable id of the open question when `decision` is `not_sure`. Otherwise null. |
| `excluded` | boolean | True when `decision` is `no`. |
| `why` | string or null | The match reason already on the article. |
| `benchmark_acceptable_solution` | string or null | The resolved sentence id. Null when the sentence is unknown. |
| `explainer` | object or null | `{ "text", "quote", "source", "label" }`. `label` is `explanation`. `source` is `deterministic` or `ai_written`. `quote` is the snippet. A reason that claims the design meets the Code stays off `text`; `source` stays `deterministic`. Null when there is no quote to ground it. |

`explainer.text` says it is an explanation of the quoted text. It is not a finding that the design meets the Code.

`Section C` on a suggested or benchmark row still carries `explainer.source` of `deterministic`, or `ai_written` when a quote-checked verifier reason does not claim the design meets the Code. A claim of that kind leaves the deterministic explainer in place. The benchmark command's BM25 variant is unchanged and is not this HTTP path.

### Article decision

`POST /cases/{id}/identify/{provision_id}/decision` with `{ "decision": "yes" | "no" | "not_sure" }` records the user's choice for one ranked article. `provision_id` may be the article id (`9.10.15.5.`) or the sentence id on that card. The same decision posted again does not add a second citation or a second question.

`yes` writes one case citation: a confirmed fact whose `source.type` is `user_click`, whose `source.ref` is the article id, and whose field is `citation.{article}`. That article is added to `provisions`, and Section C is the deterministic lookup for the case provisions. A second `yes` keeps the same fact id.

`not_sure` removes that citation and opens one question. The question id is stable for the case and article. The text names the article and asks whether it applies. `GET /cases/{id}/gaps` includes it (`section` `C`, `severity` `warning`, `id` equal to `open_question_id`). `GET /cases/{id}/information-request` includes the same id, the article, and the question text in `items`.

`no` removes the citation and the open question. The article stays on the identify response with `decision` `no` and `excluded` true.

An unknown article is HTTP 404 detail `provision not found`. A case with no identify result is HTTP 404 detail `identify result not found`. Another `decision` value is HTTP 422.

From a checkout that has no virtualenv, the same flags work through `scripts/bench_identify.sh`. The script creates `.venv`, installs `engine/requirements.txt` and `codedb/requirements.txt`, and sets `BATATIS_LLM_PROVIDER=openai`. The only value the caller supplies is `OPENAI_API_KEY`, and the script does not print it.

## Export

`POST /cases/{id}/export` reads the blank form from `engine/export/forms.json`, keyed by jurisdiction and form id. The default is `alberta` / `scc-variance`, version `scc_2026-10`, PDF last-modified `2026-10-06`, 5 pages, 87 fields. The file SHA-256 must match the registry and `engine/export/field_maps/scc_2026-10.json`. A mismatch is HTTP 422.

The response is the PDF. Headers `X-Batatis-Form-Version`, `X-Batatis-Form-Date`, `X-Batatis-Form-Id`, and `X-Batatis-Jurisdiction` repeat the registry entry. The same values are in the PDF info dictionary.

The October 2026 Safety Codes Council form differs in wording from the challenge brief's Appendix 1 (Section B checkbox label, privacy text, and the officer line "approximately equivalent or greater safety performance"). Appendix 1 is not the export target.

Optional body fields `jurisdiction` and `form_id` select another registry entry. `BATATIS_SCC_FORM` overrides only the default entry's path. The SHA check still applies.

## Keyed benchmark

```sh
BATATIS_LLM_PROVIDER=openai .venv/bin/python -m engine.identify.benchmark \
  --repeats 3 --cases 20 --source evals_dev \
  --fx-usd-cad 1.4097 --fx-date 2026-10-19
```

The process exits 2 when `OPENAI_API_KEY` is missing. It does not print the key. `--fx-usd-cad` (CAD per 1 USD) and `--fx-date` are required and are printed on every variant line. The rate above is Bank of Canada series FXUSDCAD for 2026-10-19; pass a different pair when you have a newer one. Defaults are dated snapshots, not the floating aliases: screen and rerank `gpt-4.1-mini-2025-04-14`, verifier `gpt-4.1-2025-04-14`. Those are the default snapshots on OpenAI's model pages for `gpt-4.1-mini` and `gpt-4.1`. `BATATIS_SCREEN_MODEL`, `BATATIS_RERANK_MODEL`, and `BATATIS_VERIFY_MODEL` replace them. Each variant line prints the requested id (`rerank_model`, `verifier_model`) and the id the API returned (`rerank_returned`, `verifier_returned`, or `none` when that stage made no call). It also includes input and output tokens per case, p50 and p95 latency, USD and CAD per case, then a line comparing CAD per case with the C$125 price floor.

Accuracy is the mean of every repeat, with min, max, and the per-repeat values. The command reports two groups and does not pool them.

`scored_must_cite` is the headline. Gold is `must_cite` only. On the first 20 development cases that is n=11. A case with neither `must_cite` nor `identify_gold` stays out of both rates. A suggestion on that case is `suggestions_no_gold`, not an error.

`scored_ask_identify_gold` is separate. It scores ask cases whose `gold.identify_gold` has `role: benchmark`. The note on that group is: retrieval of the candidate article on ask cases; measures finding the article, not deciding it applies. Those rows are labelled model-checked, not human-verified. On the first 20 development cases that is n=4 (`dev-006`, `dev-010`, `dev-011`, `dev-015`). `identify_gold_candidates` is unscored. Suggested errors on the ask group are `suggested_errors_ask`, not `suggested_errors_gold` and not `suggestions_no_gold`.

`suggested` is the would-suggest hint (probability at least 0.75, within the cap and part rule). It is not an article accepted onto a case. The counts are `suggested_errors_gold` and `suggested_errors_ask`.

Article match uses the leading `N.N.N.N.` id. A sentence such as `9.25.5.2.(1)` matches the ranked article `9.25.5.2.`. The stored gold keeps the sentence id. Only `role: benchmark` is the ask retrieval target. `role: secondary` is not a recall target, and suggesting that article is not an ask suggested error.

The CSV `group` column keeps the two blocks apart. On ask rows, `n` is the group size and `n_gold` is blank, so the headline gold count is not repeated there.

`stability` is the share of cases whose top-1 article is the same on every repeat. Each headline case also has a majority-vote top-1. The command writes `results.json` and `summary.csv` under `out/identify-benchmark/` (gitignored) unless `--out` is set. Those files carry model ids, the FX rate and date, and token counts. They do not carry keys. The command fetches official sources and builds the code database first.


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
