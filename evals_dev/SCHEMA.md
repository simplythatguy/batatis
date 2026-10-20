# Development case schema (`evals_dev/cases/*.json`)

Development cases for iterating on Batatis intake, code identification and Section C. They are written
from the code database (`codedb/`) only: each case starts from a Division B provision of NBC(AE) 2023,
2nd printing, and describes a design that departs from it in an applicant's own words. They are **not**
derived from the held-out judge set and must never be compared against it by hand.

One JSON object per file. The validator is `evals_dev/validate_cases.py`.

## Top level

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `dev-NNN`. Never reuse a held-out id pattern. |
| `applicant_type` | enum | `manufacturer` \| `homebuilder` \| `contractor` \| `architect-engineer` \| `owner` |
| `topic` | enum | `part9-spatial-separation`, `part9-fire-separations`, `envelope-insulation-sheathing`, `cladding`, `engineered-walls`, `single-exit`, `part3-fire-protection`, `part4-structural`, `out-of-scope` |
| `code_part` | int \| null | Part of Division B the seed provision belongs to; null for out-of-scope requests. |
| `jurisdiction` | string | Alberta municipality, or `unspecified`. Kept as data so cases stay portable across jurisdictions. |
| `seed_provision` | string | The Division B provision the author started from (not shown to the system under test). |
| `description` | string | The only text the system under test receives. Plain language, no article numbers. |
| `known_facts` | string[] | Facts the description states. A response must preserve them and must not contradict them. |
| `missing_info` | object[] | `{field, why, priority}`; `priority` is `critical` (changes the code route or the decision) or `administrative` (needed for the form, does not change the route). |
| `gold` | object | See below. |
| `authoring` | object | `{source: "codedb", author, date, notes}`. |

## `gold`

| Field | Type | Meaning |
|---|---|---|
| `departure` | string | One line: what the design does instead of the acceptable solution. Empty for `ask`/`redirect` cases. |
| `must_cite` | object[] | `{division, provision, role}`. Minimum provisions a correct answer identifies. `role` is `benchmark` (the acceptable solution departed from) or `scope` (applicability/handoff pointer). Empty for `ask` cases where the route is undecided. |
| `should_cite` | object[] | `{division, provision, why}`. Helpful or conditional references. Not recall targets; never penalised. In `ask` cases these are the candidate branches. |
| `must_not_cite` | object[] | `{division, provision, prohibited_use, why}`. A provision that is wrong **as used** here (for example an exception whose condition the facts rule out). Mentioning it to reject it is fine. |
| `section_c` | object[] | One row per benchmark sentence: `{provision, status, root_provision, pairs, conditional}`. Copied from `codedb.lookup(provision)`: `status` is the attribution status (`direct`, `none`, `clause_level`); `pairs` are unconditional table brackets such as `[F02,F03-OP3.1]`; `conditional` is `[{pair, when}]` for rows with an application note. `status: none` with empty `pairs` means the table has no row: Section C must say so and must not invent one. `root_provision` is the database's heuristic root and is never an attribution. |
| `engineering_required` | enum | `yes` \| `no` \| `depends`, scoped to the described work. |
| `engineering_reason` | string | The trigger, or for `depends` the unresolved fact. |
| `engineering_citations` | object[] | `{division, provision}`; normally Division C, Part 2. |
| `intake_action` | enum | `ask` (deciding facts missing), `proceed_conditionally` (enough to identify the benchmark; targeted questions remain), `redirect` (outside the building code's technical scope). |
| `out_of_scope` | bool | True only for `redirect`. |
| `redirect_to` | string \| null | The regime the request belongs to, for `redirect` cases. |

Every case also implicitly carries the process references Div A, Article 1.2.1.1. and Div C,
Article 2.3.1.1.; they are not repeated in each `must_cite`.

## Rules

1. Every provision named anywhere in `gold` exists in the database under the stated division.
2. `section_c` equals the database rows for that provision: same unconditional bracket set, same
   conditional `(pair, when)` set, same status.
3. `ask` cases have at least one `critical` missing field and an empty `must_cite`.
4. `redirect` cases have `out_of_scope: true` and a `redirect_to`.
5. `description` contains no code article numbers.
6. Edition: NBC(AE) 2023, 2nd printing only.
