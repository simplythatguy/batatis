# The held-out judge

`python -m evals_dev.judge` scores a system under test (SUT) against the 48 held-out scenarios in `~/batatis-judge` (override with
`BATATIS_JUDGE_DIR`). The scenarios never enter the repository clone. Code: `evals_dev/judge/`; tests: `evals_dev/tests/test_judge.py`.

## What it guarantees

| rule | how |
|---|---|
| the SUT sees only the applicant's words | the description goes to the SUT's stdin; no id, split, topic or gold is passed on the command line or in the environment |
| separate process, scrubbed environment | temporary working directory; allow-listed variables only (`PATH`, `HOME`, `SSL_CERT_FILE`, `BATATIS_*`, provider keys); `BATATIS_JUDGE_DIR` and any variable that mentions the judge folder are removed |
| the SUT cannot read the folder | on macOS the SUT runs under `sandbox-exec` with `file-read*` and `file-write*` denied on the judge folder (tested); the test split refuses to run without it unless `--allow-weak-isolation` |
| output is aggregates and error categories only | no scenario text, id or per-scenario result is printed; groups under 5 scenarios are suppressed; an internal error prints its class and place, never its message |
| the test split runs once per registered arm | `register` freezes the command and config hash; `run --split test --arm NAME` takes `state/run-test-NAME.lock` with `O_EXCL` before the SUT starts (a crash still consumes the run); a second run, or a re-registration, needs `--override-run-once` / `--override` with at least 20 characters of reason, appended to `state/overrides.log`, and the printed result says `override: true` |
| held-out numbers exclude low-confidence gold | the headline block leaves out scenarios whose confidence is `low` or that the dataset manifest excludes; `diagnostic_all` has them |

Per-scenario detail is written to `<judge folder>/state/`, readable by the owner only. Do not open it before the run is closed.

## Commands

```sh
python -m evals_dev.judge audit                       # counts only: 48 scenarios, 16 dev, 32 test, projection check
python -m evals_dev.judge run --split dev --sut bm25-floor      # free iteration on the 16 dev scenarios
BATATIS_LIVE=1 BATATIS_DAILY_SPEND_CAP_USD=5 python -m evals_dev.judge run --split dev --sut identify   # the pipeline of PR #52

# at gate G4 time, once thresholds are fitted and calibration.json is committed:
python -m evals_dev.judge register --arm winner --label "<pipeline> <config_hash>" --config-hash <config_hash> -- \
    /abs/python /abs/repo/evals_dev/judge/suts/identify_pipeline.py
python -m evals_dev.judge register --arm bm25-floor --label "BM25 floor" --config-hash bm25 -- \
    /abs/python /abs/repo/evals_dev/judge/suts/bm25_floor.py
BATATIS_LIVE=1 BATATIS_DAILY_SPEND_CAP_USD=5 python -m evals_dev.judge run --split test --arm winner
python -m evals_dev.judge run --split test --arm bm25-floor
python -m evals_dev.judge status
```

Report the result as it is. Do not tune on it: if the held-out failures are used to change anything, the set is spent and a new one must be frozen.

## Scores

`m2_required_article_in_top5` (a required Division B article, collapsed to its article, is in the first five), hit@1 and @3, committed-pick precision
(required only, and required or helpful) with Wilson and the exact one-sided 95% lower bound, commits on scenarios with no required article, commits on
a prohibited article, intake-action agreement and redirect recall, engineering agreement and under-flagging, fabricated citations (an id not in the
code database), a crude un-negated "complies / is approved" flag, and the SUT failure categories (`launch_failed`, `timeout`, `no_response`,
`nonzero_exit`, `invalid_json`, `schema_invalid`). A SUT failure keeps the scenario in every denominator with zero recall. Section C and the Section D
requests need the blinded extractor of RUBRIC.md and are not scored here.
