# Development case schema (`evals_dev/cases/*.json`)

Development cases for iterating on Batatis intake, code identification and Section C. They are written
from the code database (`codedb/`) only: each case starts from a Division B provision of NBC(AE) 2023,
2nd printing, and describes a design that departs from it in an applicant's own words. They are **not**
derived from the held-out judge set and must never be compared against it by hand.

One JSON object per file. Committed JSON is the single authoring source for narratives, semantic
labels and authoring receipts. The reviewed set is exactly `dev-001` through `dev-060`, with matching
filenames and IDs. The validator is `evals_dev/validate_cases.py`.

## Top level

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `dev-NNN`. Never reuse a held-out id pattern. |
| `applicant_type` | enum | `manufacturer` \| `homebuilder` \| `contractor` \| `architect-engineer` \| `owner` |
| `topic` | enum | `part9-spatial-separation`, `part9-fire-separations`, `envelope-insulation-sheathing`, `cladding`, `engineered-walls`, `single-exit`, `part3-fire-protection`, `part4-structural`, `out-of-scope` |
| `code_part` | int \| null | Part of Division B the seed provision belongs to when the route is identified. Null means an unresolved route (`ask`, `out_of_scope: false`) or a separate-regime request (`redirect`, `out_of_scope: true`); null alone is not an out-of-scope label. |
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

## Refreshing deterministic Section C values

Edit the JSON files directly when authoring or reviewing case semantics. The historical
`author_cases.py` filename now identifies a **Section C refresher**, not a narrative generator.
It contains no second copy of the fixture narratives and does not update authoring receipts or
claim human review.

The default run, or explicit `--check`, reads the existing 60 files and CodeDB without writing.
Only Division B references already listed with `role: benchmark` in `gold.must_cite` supply Section C
rows. Seed provisions, scope references and candidate citations do not select additional rows.
`--write` explicitly permits updates to **`gold.section_c` only**. Unchanged files are not rewritten;
every other JSON value, including unknown metadata fields, is preserved.

The entire projected set is validated before any source file is replaced. Missing/unexpected files,
filename/ID mismatches, malformed JSON, invalid case labels or unknown benchmark provisions abort the
batch. Replacements are prepared first and applied with per-file atomic renames. This is not a
filesystem-wide crash transaction.

```sh
.venv/bin/python evals_dev/author_cases.py --check
.venv/bin/python evals_dev/author_cases.py --write
.venv/bin/python evals_dev/validate_cases.py
.venv/bin/python -m pytest evals_dev -q
```

Both scripts accept `--db PATH` and `--cases DIR`; use the main checkout's Python environment when
the isolated worktree has no `.venv` (the exact verified commands are in `REVIEW.md`). Refresher exit
codes: `0` means current or successfully refreshed, `1` means check mode found Section C drift, and
`2` means invalid input or an I/O failure. Fix semantic/input errors in JSON; the refresher does not
choose a different benchmark, rewrite a narrative or repair an authoring decision.
