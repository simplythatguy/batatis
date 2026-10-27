# Workflow bakeoff rubric

Revised before the code-database rescore. The procedures below are the whole judge. They are deterministic. A second run is the inter-run check. No model grades the drafts.

The prompt ids are the same 152 already frozen in `frozen/prompts.json`. This revision does not add, drop, or replace a prompt.

## What a point measures

Quality is 0 to 10. Each check is pass or fail. The sentence in the results table names every miss.

1. **Path.** The workflow's path equals the fixture label: `acceptable`, `alternative`, `unresolved`, `redirect`, or `not_applicable`.
2. **No fabricated citation.** Every provision id, STANDATA id, and CCMC number in the draft was either written in the prompt, returned by the coded-rule evaluator on this run, returned by the Section C lookup for the article id this run committed, or is a Division C process citation for a process field this run actually asked. An objective/function pair that is neither in those lookup rows nor already written in the prompt counts as fabrication.
3. **Process fields.** On `alternative`, the run asks all six applicant fields the product already requires (`engine/process_fields.py`): rationale, risk assessment, mitigating measures, assumptions and limits, maintenance and operation, qualifications. It does not write those answers itself. On every other path it asks none of the six.
4. **Process is not evidence.** Risk assessment, mitigating measures, and assumptions/limits do not appear in the evidence-type list.
5. **Evidence matches the path.** `alternative` recommends the shared ladder and the four alternative-path evidence types (CCMC, ICC-ES, registered professional opinion, engineering review). `acceptable` recommends none of those four (an empty list or the shared ladder both pass). `unresolved`, `redirect`, and `not_applicable` do not open a required evidence package.
6. **Section C discipline.** When an article, sentence, or clause id is committed, the draft's Section C lines are the code-database rows for that id, rendered as provision id, attribution status, function-objective pairs, intent objective codes, and the count of intent statements. Sentence text and intent prose are not copied. The lines must equal that rendering. An invented pair still fails. If the committed id is not a Division B article, sentence, or clause in the database, the draft says the lookup missed that id. The old "lookup unavailable" sentence fails this check once the database is open. A workflow that commits an id the database can answer and does not include that rendering fails this check.
7. **No professional judgment and no compliance claim.** The draft does not author a risk conclusion, an engineering opinion, or say the design complies, is safe, is approved, or meets the code. "Follows the acceptable solution" is the coded rule's own wording and is allowed.
8. **No silent fills.** Every fact used in a rule check was in the prompt text or was asked. Hidden scenario inputs do not leak in.
9. **Administrative completeness.** The closing review lists missing items and says it is not a compliance determination.
10. **Code analysis is not an applicant quiz.** The run does not ask the applicant to supply objectives, functional statements, or intent statements. Those are a lookup after an article id. Asking for them is redundant now that the database can answer.

## Questions

A question is one prompt a person must answer before the draft, including applicant, designer, and office prompts. Confirmation of a reading counts as one question. Evidence types listed inside one question count as one question.

- **Necessary.** Not redundant under the rules below.
- **Redundant.** A repeat; a re-ask of a fact already in the prompt (the single reading confirmation is not redundant); an objective/function/intent question; a process field when the gold path is not alternative; paperwork or a required evidence package when the gold path is unresolved, redirect, or not applicable.

`quality_per_question = quality / max(questions, 1)`.

## Winner

A workflow with any fabricated citation is ineligible.

Primary quality is the mean of two slices, weighted equally:

- application prompts: `evals_dev/cases` plus the three demo briefs
- diamond prompts: `evals_dev/rules/vectors.json`

`balanced_quality = 0.5 * mean(application) + 0.5 * mean(rule)`

The same weights apply to the question mean. The higher balanced quality wins. If two eligible workflows are within 0.25 quality points, the one with fewer balanced questions wins.

## What this number is not

The code database is open for this rescore. Section C is the lookup above, not a grade of whether the committed article is the right one, and not a copy of National Research Council sentence text. Path labels on the demo briefs come from each case README and can require retrieval the workflows do not all do. Dev-case and rule-vector labels are mechanical. The procedures do not vary between runs. The limit on the result is the prompt mix and these ten checks, not sampling error.
