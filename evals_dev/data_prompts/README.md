# Data Prompts accuracy

This folder measures how well the engine handles the 653 practice cases in [`Data Prompts/`](../../Data%20Prompts/README.md). Each case is a request plus published attachments. The harness runs the real engine on each case, turns what the engine returns into a report, and checks that report against reference items taken from the case's own metadata.

## What is measured

Each case gets four kinds of checks:

| Kind | Source | Passes when |
| --- | --- | --- |
| F, source fact | `source.json` facts that the attachments or the request actually state | the report states the same fact, with its values |
| R, review point | `evaluation.json` `review_focus` | the report addresses the point; a prohibition passes unless the report breaks it |
| B, boundary | built from the metadata | the report flags an outside-Alberta record, another safety-codes discipline, or a code edition other than NBC(AE) 2023 |
| A, article | NBC(AE) 2023 articles that the metadata names and the code database resolves | the article appears among the provisions the output presents |

Accuracy is passed checks divided by all checks, over the chosen cases. A Sol judge (`gpt-6.1-sol`, low effort) grades F, R and B. Every positive verdict must quote the report exactly, or it does not count. Lines that only repeat the request text can cover a fact but never a review or boundary point.

Four guardrails are reported beside accuracy and must all pass: no compliance, safety or approval verdict in Batatis's own text; every provision the output presents resolves in NBC(AE) 2023; no committed Alberta article on an outside-Alberta case; and the run finished without an error.

A fact counts only when its wording matches one attachment page or the request (overlap 0.6 or more). Facts with overlap from 0.3 to 0.6 were labelled once by the judge model against their best-matching pages; `availability.json` freezes those labels. Facts under 0.3 are not counted. These are mostly catalogue metadata, images and outcome documents that are kept out of the input.

## Split

`corpus.split()` puts every case into `dev` (334) or `holdout` (319). Cases that share a source group or any attachment file stay on the same side, and each priority tier is balanced. Tune on `dev` only.

## Run it

You need the restored attachments (see the corpus README) and a private `.env` with `OPENAI_API_KEY`.

```sh
export DPE_ENV_FILE=/absolute/path/to/.env
export DATA_PROMPTS_ROOT=/absolute/path/to/restored/Data\ Prompts
.venv/bin/python -m evals_dev.data_prompts run --name my-run --split dev
.venv/bin/python -m evals_dev.data_prompts score --name my-run --split dev
.venv/bin/python -m evals_dev.data_prompts show --name my-run --case L04-001
```

`run` uses one process per worker, because the engine's PDF reader (pdfium) crashes under concurrent threads. Provider responses are cached under `.dpe-cache/`, so an unchanged rerun costs nothing. `DPE_HTTP_CACHE=refresh` forces fresh calls. Every result records its provider calls, tokens and cost at OpenAI's Standard-tier list prices. No request uses the priority tier.

`python -m evals_dev.data_prompts.calibrate` checks the judge with synthetic reports: a perfect report, an empty one, another case's report, and a perfect report with its numbers changed.

## Limits

The reference items come from published sources and a curator's notes, not from expert review of a new application. A passing check means the output covers what the curator flagged. It does not mean the output is complete, correct for a real project, or a code determination.
