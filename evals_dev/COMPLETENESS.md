# Completeness benchmark

Administrative completeness only. The checker does not see gold labels.

Keyed run (variants A, B, and C; C calls the pinned OpenAI model). `OPENAI_API_KEY` must already be in the environment. The process does not print the key and exits if it is missing.

```sh
BATATIS_LLM_PROVIDER=openai python3 -m evals_dev.completeness_eval --live --repeats 3
```

Run it from the repository root. The case set is the planted fixtures, the 60 `evals_dev` cases, and the Unc samples (uncalibrated public precedent queries in `evals_dev/public_benchmark/cases.json`).

Each variant reports the pinned model id, input and output tokens per case, p50 and p95 latency, USD and CAD cost per case, and the planted success metrics. CAD uses the Bank of Canada FXUSDCAD rate printed with its date. A line compares that cost with the C$125 price floor. An invented value fails the run.

Offline A and B, with C left uncalled:

```sh
python3 -m evals_dev.completeness_eval
```
