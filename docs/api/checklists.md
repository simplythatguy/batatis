# Standing-package checklists (WP-32)

Some offices publish standing alternative-solution packages: pre-reviewed conditions an applicant can
follow instead of building a case from scratch. A checklist turns one package into its operative
conditions, one row each, so the applicant can answer them one at a time.

**A checklist is never a determination.** A confirmed row is the applicant's own declaration that the
project follows the published package. The safety codes officer decides whether the package can be used
and whether its conditions are met. Every response carries this as `notice`; show it on the card. No
copy says the design complies, is safe, is approved or is adequate.

| Checklist | Package | Rows | Source |
|---|---|---|---|
| `calgary-spv-001` | Calgary SPV-001 Zero Lot Line, Revision 5, 2026-03-05 | 53 | City PDF, 6 pages |
| `calgary-spv-006` | Calgary SPV-006 Firewall in a Rowhouse with Secondary Suites, 2025-06-19 | 32 | City PDF, 5 pages |
| `edmonton-b23-01` | Edmonton Policy B23-01 Fire Separation Between Row Houses with More Than Two Secondary Suites, 2024-07-30 | 13 | City PDF, 2 pages |

Edmonton Policy B14-01 (reduced or zero lot line, cites the Alberta Building Code 2014) is **historical
only**. It never has a checklist; both routes list it under `historical` with its reason.

All three checklists are `reviewed: false` until a person reads them in full against the PDFs
(`evals_dev/checklists/REVIEW.md`). Show that state, for example "Not yet reviewed by a person".

## Data

| Path | Model | What it holds |
|---|---|---|
| `engine/data/jurisdictions/checklists/<id>.json` | `StandingChecklist` (`engine/models_checklists.py`) | One checklist. The file name is its id. |
| `engine/data/jurisdictions/pack.schema.json` | generated | Now also covers `checklists/*.json`. Regenerate with `python -m engine.jurisdictions.schema`. |

A checklist names its pack (`jurisdiction`) and package (`package`); the package's `checklist` names it
back. The loader (`engine/jurisdictions/checklists.py`) rejects a one-way link, a checklist on a
historical package, and a checklist whose code, issued date or source hash differ from its package. A
checklist whose pack file is removed is not loaded. Adding a checklist is adding a JSON file and setting
the package's `checklist`; no engine code changes, and no city name appears in engine code.

### A condition row

| Field | Meaning |
|---|---|
| `id` | Stable slug, unique in the checklist. Answers are keyed by it. |
| `group` | Group id; `groups[]` gives the title and a one-line `plain` for each. Render groups in order. |
| `kind` | `scope`, `construction`, `agreement`, `documents` or `declaration`. |
| `subject` | What it is about: `project`, `building`, `both_houses`, `zero_side`, `easement_side`, `both_parcels`, `each_house_with_suite`, `permit_documents`, `declaration`. SPV-001 rows with `both_houses` or `both_parcels` hold for the neighbouring house or parcel too. |
| `plain` | **Show first.** Plain-language wording. |
| `when` | Plain-language trigger when the row applies only in some designs; null when it always applies. |
| `one_of`, `option` | Rows sharing `one_of` are the options of one choice (for example SPV-001 cladding `c) i.`, `c) ii.`, `c) iii.`). The applicant follows one option and marks the other option rows "does not apply". |
| `may_not_apply` | `false`: the row always applies when the package is used; the answer route refuses `does_not_apply`. Hide that choice. |
| `source.page` | One-based PDF page. |
| `source.label` | Item label as printed, e.g. `b) ii.`, `4. a) i)`, `Authority and conditions`. |
| `source.quote` | **Behind a disclosure.** Short verbatim extract (at most 260 characters), checked word for word against the reference text. |
| `source.lead_in` | The sentence the item hangs from, when the item alone does not read (show above the quote). |
| `source.diagram` | A figure that shows the condition, with its page, or null. |

`source_notes[]` hold what the applicant should know but cannot confirm: `conflict` (the source
contradicts itself, e.g. SPV-001's 0.3 m and 0.6 m footing projections), `figure_only` (text only in a
figure), `warning` (offence sentences), `scope`. Each has `plain`, `page` and a verified `quote` (null for
figure-only text).

## Routes

Both reads are free of side effects and call no provider. The case routes follow the case access policy
(`engine/access.py`): reads for the owner, or a reviewer of the case's authority once submitted; the
answer POST is an edit, owner only, while the case is a draft or returned. Others get `404 case not found`.

### `GET /jurisdictions/{id}/checklists`

Public. `JurisdictionChecklists`. `404` detail `jurisdiction not found`. A pack without packages (the
Alberta fallback) returns empty lists.

```json
{
  "jurisdiction": "edmonton",
  "checklists": [
    {
      "id": "edmonton-b23-01",
      "jurisdiction": "edmonton",
      "package": "edmonton-b23-01",
      "code": "B23-01",
      "title": "Fire Separation Between Row Houses with More Than Two Secondary Suites",
      "revision": null,
      "issued": "2024-07-30",
      "summary": "Lets a Part 9 row house with more than two adjacent houses that have a secondary suite use a party wall with a 1 h fire-resistance rating instead of the firewall in Sentence 9.10.11.2.(2). ...",
      "reviewed": false,
      "source": {"title": "City of Edmonton, Policy B23-01 (30 July 2024)", "url": "https://www.edmonton.ca/...", "retrieved": "2026-10-21", "pages": "pp.1-2", "sha256": "85d5c4d3...", "status": "verified", "note": null},
      "groups": [{"id": "scope", "title": "When this policy can be used", "plain": "Check these first. ..."}],
      "source_notes": [{"id": "offence", "kind": "warning", "plain": "When the policy is used, not meeting its requirements is an offence.", "page": 2, "quote": "When utilized, non-compliance with requirements of this policy is an offence."}],
      "notice": "A checklist is never a determination. ...",
      "conditions": [
        {
          "id": "scope-row-house", "group": "scope", "kind": "scope", "subject": "building",
          "plain": "The building is a Part 9 row house with more than two adjacent houses that each have a secondary suite, on freehold or condominium lots.",
          "when": null, "one_of": null, "option": null, "may_not_apply": false,
          "source": {"page": 1, "label": "Purpose", "quote": "for Part 9 row houses with more than two adjacent secondary suites, applicable to freehold or condominium lots.", "lead_in": null, "diagram": null}
        }
      ]
    }
  ],
  "historical": [
    {
      "id": "edmonton-b14-01", "code": "B14-01", "title": "Reduced or Zero Lot Line Side Yard Wall and Gable Construction",
      "issued": "2019-01-10", "status": "historical",
      "historical_reason": "The policy cites the Alberta Building Code 2014 (ABC2014), which is superseded by NBC(AE) 2023. ...",
      "source": {"title": "City of Edmonton, Policy 14-01 ...", "url": "https://www.edmonton.ca/...", "retrieved": "2026-10-21", "pages": "pp.1-2", "sha256": "2fe9366e...", "status": "verified", "note": null}
    }
  ],
  "notice": "A checklist is never a determination. ...",
  "meta": {"notice": "..."}
}
```

### `GET /cases/{case_id}/checklists`

`CaseChecklists`: the checklists of the pack the case resolves to (same resolution as
`GET /cases/{id}/jurisdiction/pack`), each row with the applicant's latest `answer`.

| Field | Meaning |
|---|---|
| `case_version` | The case version this read saw. Send it as `expected_version` on the next answer. |
| `jurisdiction`, `matched_by` | Pack id and how it matched (`id`, `name`, `reviewer_code`, `fallback`), or null. |
| `checklists[]` | `CaseChecklist`: the checklist plus `conditions[].answer`, `counts`, `provisions` (as printed in the pack) and `matches_case_provisions` (a provision the package varies is in `case.provisions`). Matching checklists come first. |
| `historical[]` | Superseded packages, shown for history only (Edmonton B14-01). |
| `none_reason` | When `checklists` is empty: the case names no jurisdiction yet, or the office has no current package with a checklist (the full variance is the route). Otherwise null. |
| `notice` | The never-a-determination sentence. |

`counts` is `{ total, confirmed, not_yet, does_not_apply, unanswered }`. It is a tally of the applicant's
own answers, never a score or a pass mark; do not show it as "complete" or "passed".

### `POST /cases/{case_id}/checklists/{checklist_id}/answers`

Records one answer. Body (`ChecklistAnswerRequest`, unknown keys rejected):

```json
{ "condition_id": "b-i-balcony-no-openings", "state": "does_not_apply", "reason": "No front or rear balcony.", "expected_version": 1 }
```

| Field | Rule |
|---|---|
| `state` | `confirmed`, `not_yet` or `does_not_apply`. |
| `reason` | Required (non-blank) for `does_not_apply`; optional otherwise, at most 1000 characters. Sending no reason clears an earlier one. |
| `expected_version` | Required strict positive integer: the `case_version` (or `Case.version`) the client last saw. |

Responses:

| Status | When |
|---|---|
| `200` | `ChecklistAnswerResult` `{ "case_version", "checklist": CaseChecklist }`: the committed version and the whole checklist with answers. |
| `404` | `case not found`; or `checklist not found for this case's jurisdiction` (the checklist is not in the case's pack). |
| `409` | `case was updated concurrently`: `expected_version` is stale, or another write landed first. Reload `GET /cases/{id}/checklists` and let the person re-answer; no automatic retry. |
| `422` | Body invalid (missing version, bad state, blank reason for `does_not_apply`); `condition not found in this checklist`; or `does_not_apply` on a row with `may_not_apply: false` (detail explains that the package then cannot be used as published). Nothing is written. |

```json
{
  "case_version": 2,
  "checklist": {
    "id": "calgary-spv-001",
    "code": "SPV-001",
    "title": "Zero Lot Line",
    "reviewed": false,
    "notice": "A checklist is never a determination. ...",
    "conditions": [
      {
        "id": "b-i-balcony-no-openings",
        "group": "both-houses",
        "kind": "construction",
        "subject": "zero_side",
        "plain": "A front or rear balcony on or next to the zero-side wall has no glazed openings and no unprotected mechanical openings.",
        "when": "Only if there is a front or rear balcony on or next to the zero-side wall.",
        "one_of": null, "option": null, "may_not_apply": true,
        "source": {"page": 2, "label": "b) i.", "quote": "i. No glazed openings or unprotected mechanical openings.", "lead_in": "All front or rear facing balconies on or adjacent to the exposing building face at zero limiting distance shall have:", "diagram": null},
        "answer": {"state": "does_not_apply", "reason": "No front or rear balcony.", "fact_id": "fact_8a43a08282ca"}
      }
    ],
    "counts": {"total": 53, "confirmed": 0, "not_yet": 0, "does_not_apply": 1, "unanswered": 52},
    "matches_case_provisions": false,
    "provisions": ["9.10.15.5.(8)", "9.10.15.5.(9)"]
  },
  "meta": {"notice": "..."}
}
```

(The example is trimmed: the real `checklist` carries every field of `CaseChecklist` and every row.)

### Answers are case facts

The POST appends two confirmed facts with `kind: exact`:

| Field | Value | Source |
|---|---|---|
| `checklist.<checklist id>.<condition id>` | the state | `user_click`, `ref: checklist:<checklist id>:<condition id>` |
| `checklist.<checklist id>.<condition id>.reason` | the reason or null | `user_text`, same `ref` |

The latest fact per field wins. Only applicant facts count (`user_click` or `user_text`, `confirmed`,
never `proposed`), so a model can never answer for the applicant. A raw `POST /cases/{id}/facts` with
these fields is read the same way, but it has no `expected_version` and skips the route's checks; a
`does_not_apply` on an always-applies row written that way is ignored. The card should use the answer
route.

## Card guidance for WP-35

- Plain text first; the source quote, label, page and figure behind a "Source wording" disclosure, with a
  link to `source.url`.
- One question at a time works: walk `conditions` in order, grouped by `group`, skipping `one_of`
  options once one is confirmed (still record "does not apply" for the others).
- Show `source_notes` of kind `conflict` and `figure_only` as "Ask the office" items, not as rows.
- Show `notice` on the card and `reviewed: false` as "Not yet reviewed by a person".
- A "not yet" or an unanswered always-applies row means the package is not yet followed in full; say
  so in those words. Never say the design passes or complies.
