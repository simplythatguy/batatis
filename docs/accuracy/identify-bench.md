# Code identification benchmark: how to run it

The harness behind `docs/accuracy/code-id-decision.md` (generated) and `docs/accuracy/g1-report.md` (generated). Code is in
`evals_dev/identify_bench/`; the rule it applies is section 1 of `benchmark-plan.md`.

## Pieces

| piece | where | what it does |
|---|---|---|
| datasets | `datasets.py` | public53 (53), dev (60), idr26 (26); gold collapsed to the Division B article; 117 cases carry gold |
| folds | `evals_dev/folds/` | frozen with a hash (seed 20261021): public53 and idr26 are `selection`; dev splits 30/70 into `calibration` and `validation` per Part-group stratum |
| arms | `methods/`, `arms.py` | R0 BM25, R1 PR #33 ranking, R2 precedent matcher (leave-one-family-out), R4 Jev screen, R5 screen then rerank 60, R6 BM25 then Jev rerank, F1 reciprocal-rank fusion, A9 gpt-6-luna rerank, V* gpt-6-luna verifier (full text, word-for-word quote check) |
| runner | `runner.py` | resumable, rows keyed by config hash, arms interleaved case by case, deterministic arms run once |
| ledger | `ledger.py`, `ledger/*.jsonl` | OpenAI hard stop at US$10.00, worst case reserved before each call, spend recomputed from a hash-chained file; Jev accounting only |
| rows | `results/*.jsonl.gz` | one row per arm, case, repeat and profile; every figure in the reports is a function of these |
| reports | `report.py`, `decision.py`, `memo.py` | success rate, chains, decision rule, memo |
| gate | `scripts/gate_g1.py` | prints each G1 check, exits non-zero unless all pass |

## Commands

```sh
export SSL_CERT_FILE=/etc/ssl/cert.pem          # the python.org Python on this Mac has no CA bundle (the runner sets it if unset)
PY=/private/tmp/batatis-deploy-venv-20261020/bin/python
$PY -m evals_dev.identify_bench stage0            # reproduce 32%/66% (BM25) and 64%/81% (screen then rerank) with no API call
$PY -m evals_dev.identify_bench arms              # arms, config hashes, availability
$PY -m evals_dev.identify_bench run R5-jev-screen-rerank60 --workers 4        # Jev arms (paid; account credit applies)
$PY -m evals_dev.identify_bench pilot             # three cases through the Luna verifier: spend against the estimate
$PY -m evals_dev.identify_bench run V15f-R5 --folds selection --gold-only --workers 6
$PY -m evals_dev.identify_bench run V15f-R5 --profile interactive --upstream-profile throughput --folds selection --balanced 40 --repeats 1
                                                  # latency of one stage, one case at a time, shortlists from stored rows
$PY -m evals_dev.identify_bench ledger            # spend so far
$PY -m evals_dev.identify_bench decision --write [--write-pin]   # regenerate the memo, the G1 report and engine/identify/pipeline.json
$PY scripts/gate_g1.py
```

Keys come from the git-ignored `.env` (`OPENAI_API_KEY`, `JEV_API_KEY`, found in the checkout or the main checkout of the repository). They
are set in the running process only and never printed, logged or written to a row. `R1` needs PR #33's `search_rank` module: it is picked up from
`engine/identify/search_rank.py` (WP-20) or `codedb/search_rank.py` (#33), or from the file named by `BATATIS_SEARCH_RANK_PATH`; its sha256 is part of
the arm config.

## Rules the harness enforces

* **Spend.** `ledger.reserve` refuses a call whose worst case (long-context price, one token per two bytes in, the full completion cap out) would pass the
  stop. An unknown outcome (a timeout after the request was sent) is charged at worst case. The OpenAI ledger refuses a stop above US$10.00.
* **Models.** `gpt-6-luna` at reasoning effort `medium` on the standard tier (no `service_tier` is sent; the tier the API reports is stored). Jev is pinned
  to `jev-1.13.0`. No Anthropic arm exists and no Haiku model is accepted anywhere.
* **Latency** is read only from `interactive`-profile rows (one case at a time) that are not cached, repeat 0.
* **A failed row is a miss.** Missing rows count against a pipeline; they are never skipped.
* **The validation fold is not used to choose.** The decision rule reads the selection folds only.

## Adding an arm

Subclass `methods.base.Arm` (`name`, `kind`, `config()`, `run()`), return a `RowDraft`, register it in `arms.standard_arms`, and the contract tests in
`evals_dev/tests/test_identify_bench_contract.py` run it against the fakes. Any model id, size, prompt or upstream change gives new rows a new key.

## Incidents and limits of this run

* **The Jev account ran out of credit.** After 6,292 requests (116M input tokens, about US$5.4 at the assumed $0.042 per million) the
  vendor answered `credits_exhausted` for both the `.env` key and the keychain key. Every case has two complete draws of the screen,
  the screen-then-rerank and the BM25-then-rerank pipelines; the third draw failed on 12 cases and was set aside in
  `results/_incidents/jev-credits-exhausted-20261021.jsonl.gz`. The registry therefore defaults to two draws (`jev_repeats=2`) and a verifier repeat `r`
  reads draw `r mod 2` (`upstream_cycle=2`). The interactive-profile latency of the screen stage could not be measured; the memo says so and
  quotes the 2026-10-20 recorded timing as context only. `--jev-repeats 5 --upstream-cycle 0` runs the full plan once credit returns; rows
  already written keep their keys.
* **Throughput is not latency.** Accuracy runs use several workers; their stage times are inflated by our own concurrency. Only
  `--profile interactive` rows feed a latency figure.
* **Connection errors.** A request that never connected (`ConnectError`) is released from the ledger at no charge; one that failed after the request
  left (`ReadTimeout`, `RemoteProtocolError`) is charged at its worst case because the provider may have billed it.
* **Prompt cache.** Repeats of one prompt are partly served from OpenAI's prompt cache. The ledger and the cost columns bill cached input at the full
  price, and latency uses repeat 0 only.
