# Description fact labels

`labelled.json` is a synthetic, in-sample set of applicant descriptions. Each row is written for this comparison; it is not a filed variance and it is not `evals_dev/cases/`.

`held_out.json` is a separate check on text that was not used to tune the extractors: the Case C and Case A pastes from PR #20 `docs/demo/script.md`, and the three PR #14 project briefs under `evals/demo-cases/*/input/project-brief.md`. That gold is agent-labelled, not human-verified. See `HELD_OUT.md`.

Gold values are the facts a person should confirm from the sentence. They are not copied from a model under test. A null means the field is absent. Question sentences are not part of `alternative_description` and are not mined for facts.

`engine.description_facts.score_variant` reports field-level precision and recall. The production extractor is `WINNER` in `engine/description_facts.py`. See `RESULTS.md`.
