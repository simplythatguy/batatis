# Coded rules API (`/rules`, `/cases/{id}/rules`)

For the articles applicants vary most often, Batatis compares the applicant's own numbers with one acceptable solution in Division B and says plainly where the design **follows** it or **departs** from it, with the citation. A rule check is a departure flag. It never says a design complies, is safe, approved or adequate, and it never decides anything for the officer.

Source: `engine/rules/` (`evaluator.py` authoritative, `case.py`, `models.py`, `golden.py`), `engine/routes_rules.py`, rule data `engine/data/rules/*.json`, browser evaluator `web/src/rules/evaluate.ts`, vectors `evals_dev/rules/vectors.json`.

**Status: unreviewed.** Every rule and vector carries `reviewed: false` until a domain reviewer signs the vectors (`evals_dev/rules/REVIEW.md`). Show that on any rule card.

## Rules

Edition: NBC(AE) 2023, 2nd printing. Every citation and PDF page is copied from the code database and re-checked by `engine/tests/test_rules_vectors.py`.

| `rule_id` | Sentence(s) | Exceptions coded | Tables |
|---|---|---|---|
| `glazed-openings-houses` | 9.10.15.4.(1) | (6) faces own detached garage, (7) glass blocks or sprinklered; half limiting distance under 9.10.15.3.(1) | Table 9.10.15.4. (PDF p.902), with interpolation per Note A-9.10.15.4.(2) (PDF p.1380) |
| `unprotected-openings` | 9.10.14.4.(1) | (6) wired glass or glass blocks, (7) sprinklered, (8) open-air storage garage, (9) street-level storey; half limiting distance under 9.10.14.3.(1), not for (8) and (9) | Table 9.10.14.4.-A (PDF p.895), both occupancy groups |
| `soffits-houses` | 9.10.15.5.(8), (9) | (10) faces a public way; half limiting distance under 9.10.15.3.(1) | none |
| `firewall-suite-rowhouses` | 9.10.11.2.(2) | none in the Sentence; scope: more than 2 houses, at least 2 with a secondary suite | none |
| `fire-dampers` | 9.10.13.13.(1) | (2) A/C branch duct, (3) branch into exhaust riser, (4) vertical service space, (5) commercial cooking, 9.10.5.1.(3) membrane ceiling | none |

`glazed-openings-houses` is the organizers' worked example (9.10.15.4.(1), pair [F03-OP3.1]) and the demo case ("east wall 1.2 m from the property line, more window area than the acceptable solution allows"). `unprotected-openings` is its counterpart for Part 9 buildings that are not houses. Every rule also checks Part 9 scope (Div A 1.3.3.3.(1)); when storeys or building area are not stated it assumes Part 9 and says so in `assumptions`.

## The four states

| `state` | Meaning | Card copy (`state_label`) |
|---|---|---|
| `follows` | The numbers given follow the acceptable solution in `provision` (including its exceptions) | Follows the acceptable solution |
| `departs` | They depart from it. `next_step` names the two halves as an applicant action: an alternative solution (Div C 2.3.1) and a request for variance (Safety Codes Act s.38) | Departs from the acceptable solution |
| `needs_info` | An input that would decide it is missing. `missing` lists exactly those inputs, each with a plain question and why it matters | Not enough information |
| `not_applicable` | The rule does not apply (other occupancy, outside Part 9, no soffit, no duct penetration ...). `message` says why and where the parallel requirement is | Not applicable |

Nothing is guessed. Logic is three-valued; an answer is asked only when it changes the state. Example: a soffit over a wall 0.3 m from the line departs from 9.10.15.5.(8) whether or not the limiting distance is halved, so the fire-response question is not asked; at 0.8 m it decides between (8) and (9), so it is.

## How to answer a question

Write the answer as an ordinary case fact, then re-read the rules:

```http
POST /cases/{id}/facts
{"field": "glass_blocks", "value": false, "kind": "pointed", "status": "confirmed",
 "source": {"type": "user_click", "ref": "rules:glazed-openings-houses", "quote": "No"}}
```

Values must have the input's type: `number`/`int` (JSON number, not negative), `bool` (JSON true/false), `enum` (one of `choices[].value`). Anything else is listed in `ignored_inputs` and asked again. The full input vocabulary (labels, units, questions, choices) is `GET /rules` → `index.inputs`. Several inputs are intake facts already (`occupancy`, `storeys`, `building_area_m2`, `sprinklered`, `limiting_distance_m`, see `docs/api/intake.md`).

The case route reads the **latest** fact per field. A `proposed` fact (model judgement) is never used: the rule asks instead. Inputs read from unconfirmed facts are listed in `unconfirmed_inputs`, so the card can say "based on values you have not confirmed".

## Routes

Read-only. No provider is called and nothing is written.

### `GET /cases/{id}/rules`

Same access policy as every case route (`engine/access.py` `authorize_case`, mode `read`): the owner, or a reviewer of the case's authority once submitted; anyone else gets `404 case not found`. Response `CaseRules`:

```json
{
  "case_id": "case_e7a1e5b4cdc0",
  "case_version": 7,
  "edition": "NBC(AE) 2023, 2nd printing",
  "notice": "A rule check compares the numbers you gave with one acceptable solution in Division B. It flags where the design departs from that acceptable solution; it is not a review of the design and not an officer's decision.",
  "results": [
    {
      "rule_id": "glazed-openings-houses",
      "title": "Window area in a wall near the property line (houses)",
      "article": "9.10.15.4.",
      "state": "departs",
      "state_label": "Departs from the acceptable solution",
      "outcome_id": "departs",
      "provision": {"id": "9.10.15.4.(1)", "division": "B",
                    "citation": "NBC(AE) 2023 p2, Div B, Sentence 9.10.15.4.(1) [PDF p.901]", "pdf_page": 901},
      "message": "Glazed openings of 4 m² exceed the 2.1 m² that Sentence 9.10.15.4.(1) permits for a 30 m² face at a limiting distance of 1.2 m (Table 9.10.15.4., or the limiting distance squared). This departs from the acceptable solution in Sentence 9.10.15.4.(1).",
      "next_step": "To build it this way, the applicant prepares an alternative solution (NBC(AE) Division C, Subsection 2.3.1.) showing at least the level of performance of this acceptable solution in its attributed objectives and functions, and submits it with a request for variance (Safety Codes Act, s.38). A safety codes officer decides the request.",
      "missing": [],
      "inputs": [
        {"field": "limiting_distance_m", "label": "Limiting distance", "unit": "m", "value": 1.2,
         "fact_id": "fact_4c658a91f8fd", "fact_status": "unconfirmed"},
        {"field": "glazed_area_m2", "label": "Area of glazed openings", "unit": "m²", "value": 4,
         "fact_id": "fact_0cb86a304db9", "fact_status": "confirmed"},
        {"field": "adjacent_rooms_sprinklered", "label": "Rooms behind this wall sprinklered", "unit": null, "value": null,
         "fact_id": null, "fact_status": null}
      ],
      "ignored_inputs": [],
      "computed": [
        {"name": "limiting_distance_used_m", "label": "Limiting distance used (halved under Sentence 9.10.15.3.(1) where it applies)", "unit": "m", "value": 1.2},
        {"name": "table_percent", "label": "Table 9.10.15.4. percentage (lesser column)", "unit": "%", "value": 7},
        {"name": "table_limit_m2", "label": "Table 9.10.15.4. limit (lesser column)", "unit": "m²", "value": 2.1},
        {"name": "square_limit_m2", "label": "Limiting distance squared (Clause (c), only where it is 1.2 m or more)", "unit": "m²", "value": 1.44},
        {"name": "sentence_1_limit_m2", "label": "Largest area Sentence (1) permits (Clause (a) or (c))", "unit": "m²", "value": 2.1}
      ],
      "assumptions": [],
      "not_checked": ["Clause 9.10.15.4.(1)(b): conformance with Subsection 3.2.3. (a Part 3 spatial separation calculation)", "..."],
      "reviewed": false,
      "unconfirmed_inputs": ["limiting_distance_m"]
    },
    {
      "rule_id": "soffits-houses",
      "state": "needs_info",
      "state_label": "Not enough information",
      "outcome_id": null,
      "provision": {"id": "9.10.15.5.(8)", "division": "B",
                    "citation": "NBC(AE) 2023 p2, Div B, Sentence 9.10.15.5.(8) [PDF p.904]", "pdf_page": 904},
      "message": "To compare the design with 9.10.15.5.(8), answer the questions below.",
      "next_step": null,
      "missing": [{"field": "soffit_projects", "label": "Roof soffit projects over this wall",
                   "question": "Does a roof soffit (eave overhang) project above this wall?",
                   "why": "Sentences 9.10.15.5.(8) to (10) only apply to projecting roof soffits."}],
      "...": "other fields as above"
    }
  ]
}
```

(`inputs` and `computed` are shortened above; the response lists every input of the rule and every computed value. `computed[].value` is null when it depends on an answer not given.)

Errors: `404 case not found`.

### `GET /rules`

The rule definitions for the browser evaluator: `{"version", "edition", "index", "rules"}` where `index` is `engine/data/rules/index.json` (input vocabulary, state labels, shared copy) and `rules` the five rule files in order. No case, no access check.

## Live evaluation in the browser

```ts
import { evaluateAll } from "./rules/evaluate";
const { index, rules } = await (await fetch(`${API}/rules`)).json();
const byId = Object.fromEntries(rules.map((r) => [r.id, r]));
const results = evaluateAll(byId, index, { limiting_distance_m: 1.2, ebf_area_m2: 30, glazed_area_m2: 4, ... });
```

The browser evaluator gives the same output as the engine for every vector (cross-language agreement, below). Use it for what-if as the applicant types; the stored state of record is `GET /cases/{id}/rules`.

## Verification

```bash
python -m pytest -q engine/tests/test_rules_vectors.py   # vectors, golden outputs, citations and table pages vs codedb, wording, API, access
python -m engine.rules.golden --check                    # evals_dev/rules/outputs.json is current
cd web && npm run test:rules                             # same vectors in TypeScript; deep-equal to outputs.json
```

Changing a rule: edit the JSON, add or update vectors (expected values set by hand from the code text), run `python -m engine.rules.golden`, then both test commands. A difference between the Python and TypeScript outputs fails CI.

Rule data format: `inputs` (field names from `index.inputs`), `derived` (named expressions), `outcomes` (ordered; the first whose `when` holds decides; `if_unknown: "assume"` records `assumption` instead of asking), `tables` (transcribed with table id and PDF page; `null` is the printed dash), `not_checked` (related requirements the rule does not evaluate). Expression ops: `var`, `and`, `or`, `not`, `eq`, `ne`, `lt`, `le`, `gt`, `ge` (tolerance 1e-9), `in`, `add`, `sub`, `mul`, `div`, `min`, `max`, `if`, `table` (`mode`: `lesser` column or `interpolate`).
