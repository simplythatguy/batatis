# Human-key subset

The key files next to this note are **unfilled**. Current evals are **model-checked**.
Nothing here is human verification.

Label: in-sample. These 15 cases are drawn from the development set. Scores on this subset are in-sample.

Seed `20261020`. Reproduce with `python evals_dev/human_key/select.py`.

## Persona rule

Persona is inferred from the case field `applicant_type`:

| `applicant_type` | Persona in this subset |
| --- | --- |
| `manufacturer` | manufacturer |
| `contractor` | general contractor |
| `homebuilder` | homebuilder |

`architect-engineer` and `owner` are outside this subset.
Variance kind is the case `topic` field.

## Draw

Cases are grouped by persona and by `gold.intake_action`, shuffled with Fisher-Yates
(`random.Random(20261020).randrange`), then drawn rarest action first (`redirect`, then
`ask`, then `proceed_conditionally`) up to one per action, then filled to 5 per persona
preferring a variance kind not yet chosen. The action label is used only to balance the
draw. It is not copied into the key.

Intake-action mix in this draw (counts only): redirect 2, ask 8, proceed_conditionally 5.

## Selected cases

| Case | Persona | Variance kind |
| --- | --- | --- |
| `dev-005` | manufacturer | `cladding` |
| `dev-011` | manufacturer | `engineered-walls` |
| `dev-022` | manufacturer | `envelope-insulation-sheathing` |
| `dev-041` | manufacturer | `part4-structural` |
| `dev-055` | manufacturer | `envelope-insulation-sheathing` |
| `dev-020` | general contractor | `single-exit` |
| `dev-024` | general contractor | `out-of-scope` |
| `dev-030` | general contractor | `single-exit` |
| `dev-057` | general contractor | `part9-fire-separations` |
| `dev-059` | general contractor | `out-of-scope` |
| `dev-014` | homebuilder | `single-exit` |
| `dev-021` | homebuilder | `part9-spatial-separation` |
| `dev-048` | homebuilder | `envelope-insulation-sheathing` |
| `dev-049` | homebuilder | `envelope-insulation-sheathing` |
| `dev-058` | homebuilder | `part3-fire-protection` |
