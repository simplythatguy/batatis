# Human key and deterministic checks

Current evals are **model-checked**. The human key in this directory is **unfilled**.
Nothing reported here is human verification, and nothing here certifies that a design
complies with the building code.

The blank keys are a harness for later. No one is filling them in this pass. Do not
copy model gold labels from `evals_dev/cases/` into a key.

## How a key would be built later

A person who has not written the cases reads only the `scenario` field, then the
NBC(AE) 2023 2nd printing PDF and official Safety Codes Council or STANDATA documents.
They record the PDF page for every article they cite. They do not open the case's
`gold` object.

Allow about 30–45 minutes for one case once the PDF is familiar. Fifteen cases is a
full day. The first cases take longer.

`python evals_dev/human_key/select.py` redraws the 15 cases from seed `20261020`.
The persona rule and the variance-kind mix are in `SELECTION.md`.
`python evals_dev/human_key/select.py --write` rewrites a key only while every answer
is still null.

## Commands

Validate the blank keys (a verified key with no verifier name or date is rejected;
a codedb page mismatch is a warning):

```bash
python evals_dev/human_key/validate.py
```

Score a system output file. With the key unfilled this prints `n` 0 and says the
evals are model-checked. Accuracy and model-grader agreement are separate blocks.
Agreement is not added into accuracy.

```bash
python evals_dev/human_key/score.py
python evals_dev/human_key/score.py --system path/to/system.json --calibrate
python evals_dev/human_key/score.py --run-engine --calibrate
```

`--calibrate` reports committed-pick precision at probability thresholds 0.50, 0.55,
…, 0.95. A pick at threshold *t* is an article whose probability is at least *t*.
The 0.75 row is the engine's current auto-commit placeholder. It stays uncalibrated
until a key is filled.

System JSON is either `{"cases": [{"case_id", "articles", "intake_action", ...}]}`
or a map of case id to that object. `articles` may include `probability` and
`committed`.

Deterministic checks (no key, no model grader):

```bash
python evals_dev/deterministic_checks.py
python evals_dev/deterministic_checks.py --json
```

Each check is `x of n` with a Wilson 95% interval, under `grader: deterministic`.
That block is not mixed with model-graded scores. If `codedb/build/codedb.sqlite`
is absent, checks that need it report `n` 0 and `skipped: codedb missing` and the
command still exits 0. Set `BATATIS_CODEDB` to point at a database elsewhere. The
next run picks the file up on its own after the identify-api fetch script builds
`codedb/build/codedb.sqlite`.

Other branches plug outputs in by dropping JSON files:

```text
evals_dev/outputs/identify/*.json
evals_dev/outputs/section_c/*.json
evals_dev/outputs/section_d/*.json
evals_dev/outputs/completeness/*.json
evals_dev/outputs/case/*.json
evals_dev/outputs/export/*.json
```

See `evals_dev/output_adapters.py` for the fields that are read.

Appeal decisions are a separate weak-label set under `evals_dev/appeals/`. The
same command reports them as `label_source: appeals_weak`. Read
`evals_dev/appeals/README.md` before treating any of those labels as gold.

Tests, including the fake keys under `evals_dev/tests/fixtures/human_key/`:

```bash
python -m pytest evals_dev/tests/test_human_key.py evals_dev/tests/test_deterministic_checks.py -q
```
