# Intake API (`/cases/{id}/intake`)

Intake reads the applicant's description and the PDFs they dropped, and writes what it read to the case's fact ledger as **unconfirmed** facts, each pointing at the words it came from. It never confirms a fact, never says a design complies or is safe, and never names an article that is not in NBC(AE) 2023, 2nd printing.

Source: `engine/routes_intake.py`, `engine/intake/` (`rules.py`, `pdf.py`, `model.py`, `extract.py`, `service.py`, `text.py`, `places.json`), `engine/models_intake.py`.

## How a fact is made

| Pass | Fact `kind` | What makes it trustworthy |
|---|---|---|
| Rules (always first) | `pointed` | `source.quote` is the exact phrase that states the value; the record's pointer gives the character span |
| Unit conversion (sq ft, ft, mm) | `computed` | `formula` and `inputs` (the `pointed` fact with the value as written) |
| Fillable form (AcroForm) | `exact` | the field's own value; `source.page` and `source.bbox` are the widget |
| Model (only when allowed) | `pointed` when the rules, re-run on the quoted sentence, read the same value; otherwise `proposed` | a quote not found in the source is dropped and counted (`record.model.dropped`) |

- Rules win: the model is asked only for fields the rules left empty, and it cannot change a rules value.
- Two different values for one field in the same text ("two storeys ... actually three") give **no** fact and a `record.conflicts` entry, so the question planner asks.
- Questions to the tool ("Can we ...?") are never read as facts.
- Article numbers the applicant typed become `claimed_provision` facts only when they resolve in the code database; the rest are listed, as typed, in `record.unresolved_citations`.
- The model sees text after `engine/redact.py` `scrub` (case personal values, account names, and the Section A and B values the rules just read). Personal fields are never asked of the model.

### Fields

Section A and B use the SCC export keys: `owner_name`, `owner_rep_name`, `mailing_address`, `municipal_address`, `legal_description`, `lot`, `block`, `plan`, `ats_qtr`, `ats_sec`, `ats_twp`, `ats_rge`, `ats_mer`, `permit_number`, `request_date`. Others: `applicant_role` (`owner`, `designer`, `architect-engineer`, `contractor`, `homebuilder`, `manufacturer`), `municipality`, `scope` (`site` or `jurisdiction`), `storeys`, `building_area_m2`, `floor_area_m2` (per storey), `dwelling_units`, `occupancy` (the professional screen's list: `single_family`, `multi_family`, `business`, `assembly`, ...), `sprinklered` (`yes`, `no`, `partial`), `building_height_m`, `top_floor_height_m`, `limiting_distance_m`, `span_m`, `part4_design` (bool), `alternative_description` (the departure sentences, as written), `claimed_provision`, plus `<field>_ft2` / `_ft` / `_mm` for values as written before conversion. Model statements are `statement.<hash>` with the quote as the value. Labels for every field: `engine/intake/rules.py` `FIELDS`.

The description itself is stored as a confirmed `project.description` fact (the applicant's own words, as the web already does), which code identification reads.

### Files

Each file gets a `record.files[]` report. `status` is `read`, `partly_read` or `not_read`; `reason` is always set unless `read`:

| Case | Result |
|---|---|
| Text PDF | rules over each page's text layer; facts carry `source.page` (1-based) and `source.bbox` in PDF points, origin bottom-left: `[left, bottom, right, top]` |
| Page with no text layer (scan, photo) | that page is in `pages_not_read`, reason "This page has no text layer ... Batatis does not read images ..."; no OCR, no guessing |
| Filled SCC variance form (fillable) | Section A and B fields and the Section C article cells (resolved in codedb) as `exact` facts; officer, signature and button fields are in `form_fields_skipped`; the printed form text is not read |
| Flattened SCC form | `not_read`: "This looks like a flattened copy of the SCC variance form ..." |
| Other fillable form | fields whose names read like Section A/B labels become `exact`; the rest are skipped by name; the text layer is read too |
| Password-protected, broken, not a PDF | `not_read` with that reason |

At most 60 pages are read per file (`partly_read` past that); the model reads at most 5 text pages per file.

## Routes

Owner writes; reviewers read (the access policy in `engine/access.py`; `POST` is mode `edit`).

### `POST /cases/{id}/intake`

Body (`IntakeRequest`, extra fields are 422):

```json
{"text": "Renovation contractor. ...", "file_ids": ["file_3f2a..."], "role": "contractor", "model": true, "expected_version": 4}
```

- `text` up to 20,000 characters and/or `file_ids` (up to 10, no repeats; ids from `POST /cases/{id}/files`). One of them is required.
- `role`, optional: the applicant's pick, stored as a confirmed `user_click` `applicant_role` fact; it wins over a role read from the text.
- `model`, default true: run the model pass if this deployment allows it. False: rules and forms only.
- `expected_version`, optional: the `case_version` the client last saw. One compare-and-swap, no retry: a stale version or a write during the run is `409 case was updated concurrently`.

A re-run removes the facts the previous run left unconfirmed and keeps everything confirmed; a fact whose value the applicant already confirmed is not added again.

Errors: `404 case not found`, `404 file not found`, `409` (above), `422` validation.

### `GET /cases/{id}/intake`

The stored run (same body). Never calls a provider. `404 intake not run` before the first run.

### Response (`IntakeResult`)

```json
{
  "case_id": "case_e7a1e5b4cdc0",
  "case_version": 2,
  "facts": [
    {"id": "fact_fffba3ce0057", "field": "applicant_role", "value": "contractor", "kind": "pointed",
     "source": {"type": "user_text", "ref": "intake:description", "page": null, "bbox": null, "quote": "Renovation contractor"},
     "confidence": 0.8, "status": "unconfirmed", "formula": null, "inputs": []},
    {"id": "fact_b205ab94416e", "field": "storeys", "value": 1, "kind": "pointed",
     "source": {"type": "user_text", "ref": "intake:description", "page": null, "bbox": null, "quote": "single-storey"},
     "confidence": 0.9, "status": "unconfirmed", "formula": null, "inputs": []},
    {"id": "fact_4c658a91f8fd", "field": "building_area_ft2", "value": 1500, "kind": "pointed",
     "source": {"type": "user_text", "ref": "intake:description", "page": null, "bbox": null, "quote": "1,500 sq ft"},
     "confidence": 0.7, "status": "unconfirmed", "formula": null, "inputs": []},
    {"id": "fact_0cb86a304db9", "field": "building_area_m2", "value": 139.35, "kind": "computed",
     "source": {"type": "user_text", "ref": "intake:description", "page": null, "bbox": null, "quote": "1,500 sq ft"},
     "confidence": 0.7, "status": "unconfirmed", "formula": "1500 sq ft × 0.09290304 = 139.35 m²", "inputs": ["fact_4c658a91f8fd"]},
    {"id": "fact_9b1c...", "field": "owner_name", "value": "Jane Example", "kind": "exact",
     "source": {"type": "file", "ref": "file_3f2a...", "page": 1, "bbox": [113.0, 481.0, 571.0, 496.0], "quote": "Jane Example"},
     "confidence": 1.0, "status": "unconfirmed", "formula": null, "inputs": []}
  ],
  "record": {
    "ran_at": "2026-10-21T18:32:03.800900+00:00",
    "text_sha256": "236cc9d6...",
    "pointers": [
      {"fact_id": "fact_b205ab94416e", "field": "storeys", "method": "rules", "source_ref": "description",
       "page": null, "start": 28, "end": 41, "verified": true}
    ],
    "files": [
      {"file_id": "file_3f2a...", "name": "scc-form.pdf", "status": "read", "reason": null, "pages": 5,
       "pages_read": [1, 2, 3, 4, 5], "pages_not_read": [], "form": "scc_variance", "form_fields_read": 6,
       "form_fields_skipped": ["SCO", "Signature1"], "facts": 6},
      {"file_id": "file_8d01...", "name": "site-photo-scan.pdf", "status": "not_read",
       "reason": "This page has no text layer (it looks like a scan or a photo). Batatis does not read images, so nothing was taken from it. Type the facts, or attach a PDF with selectable text.",
       "pages": 1, "pages_read": [], "pages_not_read": [1], "form": null, "form_fields_read": 0, "form_fields_skipped": [], "facts": 0}
    ],
    "model": {"status": "off", "model": null, "reason": null, "pointed": 0, "proposed": 0, "dropped": 0,
              "input_tokens": 0, "output_tokens": 0},
    "conflicts": [{"field": "storeys", "values": [2, 3], "quotes": ["two storeys", "three storeys"], "source_ref": "description", "page": null}],
    "unresolved_citations": [{"entered": "9.99.99.9.", "source_ref": "description", "page": null}]
  }
}
```

`record.pointers[].start`/`end` index the description (`source_ref: "description"`) or the text layer of `page` of that file, so the UI can highlight the span. `verified: false` marks a `proposed` model value. `record.model.status`: `off` (no provider allowed, or `model: false`), `fake`, `live`, `gate_closed` (spend gate refused; `reason` is the gate's source such as `offline-cap`), `failed` (`reason` is the exception type only), `not_needed`.

## Model pass, spend and privacy

- Live only with `BATATIS_LIVE=1` and `OPENAI_API_KEY`; model `gpt-6-luna`, `reasoning_effort: medium`, standard tier (no `service_tier`), strict JSON schema, no retry. Each call reserves its worst case through `engine/llm_gate.py` `authorize` and records the reported tokens; a failed call keeps its reservation.
- `BATATIS_PROVIDER=fake` (refused on Vercel) uses a deterministic offline fake labelled `fake`, never a measurement.
- Outbound text passes through `engine/redact.py` `scrub`.

## Verification

```bash
python -m pytest -q engine/tests/test_intake_extract.py engine/tests/test_intake_pdf.py
python -m evals_dev.intake_facts.score       # typed-fact precision and recall on the 60 dev cases
```

## Plan: scope, fork and questions (WP-22)

Every write below stores `record.plan` (`IntakePlan`) and returns the same `IntakeResult` as `POST /cases/{id}/intake`. The plan is deterministic and never calls a provider. Source: `engine/intake/scope.py`, `fork.py`, `questions.py`, `preapplication.py`, `notices.py`, `plan.py`.

`plan.next` is `redirect` (another regime: show the redirect page), `questions` (at least one critical question is open) or `identify` (go on to code identification).

### Scope (`plan.scope`)

`status` is `in_scope`, `redirect` or `overridden`. On `redirect`, `regime` gives `id` (`plumbing`, `fire`, `energy`, `electrical`, `gas`, `private_sewage`), `name`, `code`, `framework` and `coverage`, and `route` (where to take it); `message` is the copy to show; `cue`/`start`/`end` are the applicant's words that decided it.

- Electrical, gas and private sewage (`framework: no_division_c_framework`, `coverage: not_covered`): the copy says the regime has no equivalent mandatory Division C alternative-solution framework and that best practice is to follow the National Model Codes approach in principle.
- Fire (NFC(AE)), plumbing (NPC) and energy (NECB) (`framework: national_model_code`, `coverage: roadmap`): the copy says they have the same pathway and Batatis coverage is on the roadmap, not built. A house's energy efficiency (NBC(AE) Section 9.36) is building code and stays in scope.
- A redirect is also stored on the case as a `computed` fact `scope.redirect` (value: the regime id, `formula` naming the cue, `inputs`: the description fact). It stays unconfirmed, so the official export is blocked; no questions are asked and nothing writes Section C.

Example (`plan.scope` for "Plumbing contractor. We want an air admittance valve instead of a vent through the roof."):

```json
{"status": "redirect",
 "regime": {"id": "plumbing", "name": "plumbing", "framework": "national_model_code", "coverage": "roadmap",
            "code": "Plumbing Code Regulation / National Plumbing Code (plumbing permit and plumbing safety codes officer)",
            "route": "the plumbing safety codes officer at the office that issues plumbing permits for the site"},
 "message": "This reads as a plumbing question (...). It is a National Model Code with the same alternative-solution pathway as the building code, but Batatis prepares building-code (NBC(AE)) applications only: plumbing coverage is on the roadmap, not built. Take the request to the plumbing safety codes officer at the office that issues plumbing permits for the site.",
 "cue": "air admittance valve", "start": 32, "end": 52,
 "scores": {"plumbing": 5, "electrical": 0, "gas": 0, "private_sewage": 0, "fire": 0, "energy": 0, "building": 0},
 "override_allowed": true}
```

#### `POST /cases/{id}/intake/scope`

`{"building_code": true, "expected_version": 3}`: the applicant's "this is a building-code question" override, stored as a confirmed `user_click` fact `scope.redirect` = `overridden`; later intake runs keep it. `{"building_code": false}` records a confirmed "check the scope again" click (it never blocks export) and checks the scope again; a redirect found then is a new computed fact.

### Fork (`plan.fork`)

`variance_needed` is `likely`, `not_indicated` or `unknown`, read from the description before Section C (and from identify decisions once they exist: any `yes` is `likely`, all `no` is `not_indicated`). `explanation` never says the design complies, is approved, adequate or safe. `cues` are the applicant's words. `halves` always lists the two distinct things an accepted variance needs:

```json
[{"id": "variance_request", "label": "Request for variance", "basis": "Safety Codes Act, s.38",
  "who": "Issued by a safety codes officer or an Administrator, who may set conditions",
  "what": "The legal authorization to build in a way the code does not prescribe"},
 {"id": "alternative_solution", "label": "Alternative solution (Div C 2.3.1)", "basis": "NBC(AE) Division C, 2.3.1",
  "who": "Prepared by the proponent, usually a design professional",
  "what": "The technical evidence that the design achieves at least the level of performance required by Division B in the attributed objectives and functions"}]
```

### Questions (`plan.questions`, at most five)

```json
{"id": "intake.storeys", "field": "storeys", "text": "How many storeys does the building have?",
 "why": "Storey count decides between Part 9 and Part 3 and changes which exit, fire-separation and construction requirements are candidates.",
 "unblocks": ["Part 9 or Part 3", "exit and fire-separation requirements"],
 "splits": ["9.9.8.1.", "3.4.2.1."], "priority": "critical", "kind": "missing", "provision": null}
```

Order: conflicts in the applicant's own words (`kind: conflict`, "You wrote "two storeys", "three storeys". ...") first; then how evenly the fact splits the open code-identification candidates (`splits` lists the candidate articles it separates; these come from the identify result, so they are codedb articles); then facts that decide the route (Part 9 or Part 3, the departure itself); then Section A and B fields (`priority: administrative`). A field that already has a value on the case is not asked (its confirm card is). Run `POST /cases/{id}/intake/plan` after code identification to re-rank against the candidates.

#### `POST /cases/{id}/intake/answers`

`{"answers": [{"question_id": "intake.storeys", "answer": "three"}], "expected_version": 4}` (1 to 5 answers). Each `question_id` must be in the stored `plan.questions`, and `field`, if sent, must be that question's own field; anything else is `422` and nothing is written. An answer is stored as a confirmed `pointed` fact quoting the applicant's words, typed as the field needs ("three" is 3, "an office" is `business`); an answer that cannot be read as that field is `422`. "Not sure" (or empty) writes no fact: the question id goes to `plan.not_sure`, is not asked again and never blocks anything.

#### `POST /cases/{id}/intake/plan`

`{"expected_version": 4}` (optional): recompute and store the plan.

All three writes follow the same contract as `POST /cases/{id}/intake`: optional `expected_version`, one compare-and-swap, `409 case was updated concurrently` with no retry, `404 case not found`.

### Pre-application note (`plan.pre_application`)

`steps` are `meet_authority` and `emergency_services` ("before you submit": the SCC presentation's process step 2). With a jurisdiction pack (the case's jurisdiction, else a municipality read from the description, `resolved_by: "description"`, unconfirmed) the text adds the authority's name, contact and entry-point notes and any emergency-services guide, with their sources (`origin: "pack"`). Without one the steps are generic.

### Product route notice (`plan.route_notice`)

For a manufacturer, or a request for acceptance across the jurisdiction: `summary` and sourced `bullets` on product acceptance (evaluation reports) versus a site variance. Ported from #44, reworded to keep the variance (Safety Codes Act, s.38) and the alternative solution (Division C, 2.3.1) distinct.
