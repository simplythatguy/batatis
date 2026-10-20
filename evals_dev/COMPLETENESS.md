# Completeness benchmark

Administrative completeness only. The checker does not see gold labels.

Keyed run (variants A, B, and C; C calls the pinned OpenAI model). From a plain checkout, with `OPENAI_API_KEY` already in the environment and no virtualenv prepared. The script creates `.venv`, installs `engine/requirements.txt` and `codedb/requirements.txt`, and runs the benchmark. It does not print the key and exits if the key is missing.

```sh
bash scripts/bench_completeness.sh
```

Run that from the repository root. The case set is the planted fixtures, the 60 `evals_dev` cases, and the Unc samples (uncalibrated public precedent queries in `evals_dev/public_benchmark/cases.json`).

Each variant reports the pinned model id, input and output tokens per case, p50 and p95 latency, USD and CAD cost per case, and the planted success metrics. CAD uses the Bank of Canada FXUSDCAD rate printed with its date. A line compares that cost with the C$125 price floor.

Each variant also writes a per-case dump under `evals_dev/bench_dumps/` (`variant-<letter>.json` and `variant-<letter>.md`): case id, invented values (field and value), false flags on clean controls, and missed planted classes such as D14 and D15. A short form of the same rows is printed. The dump is redacted. API keys are not written.

The code database is `BATATIS_CODEDB` when that file exists, otherwise a repo-relative file (`codedb/build/codedb.sqlite`, the database `codedb` builds). If none of those files exist, the run stops and names the paths it checked.

An invented value on a gating variant fails the run. `--gate` lists those variants and defaults to `B`. Variant C is reported and does not change the exit code unless it is named in `--gate`.

Planted classes include IB-DOC (Division C Section 2.3.1 documentation, IB-2025-11-18) and IB-LOC (one location per registration, IB-2026-10-01). The 10-day copy to the Safety Codes Council is an applicant reminder, not a scored verdict.

Offline A and B, with C left uncalled:

```sh
python3 -m evals_dev.completeness_eval
```
