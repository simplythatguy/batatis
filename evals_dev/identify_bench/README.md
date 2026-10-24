# Article-identification battle tests

The target is complete citation retrieval for an Alberta alternative-solution application. A checked identifier or quotation does not prove applicability, technical equivalence, safety or professional approval. No universal accuracy claim or production threshold is supported by this work.

The engine candidate is **opt-in** (`screen=shortlist`). It combines the authoritative Division B table of contents with fast BM25, optionally scores the bounded pool with Elephant, and supplies every pool article's full text to the reviewer. Every bounded candidate reaches the response; `top_k` cannot silently hide the remainder. All results remain tentative and automatic commitment is disabled. Default configuration, historical hashes, relevance bands, provider pins, admission limits, deadlines and failure controls remain intact. See [provider setup](../../docs/elephant-provider.md) and the final [handoff](../../docs/research/2026-10-23-elephant/handoff.md).

## Data and split

- The canonical 60 development cases and earlier 53 Alberta precedent summaries are retained.
- Research adds 64 Alberta and 62 Canadian records. [Source audit](../../docs/research/2026-10-23-elephant/source-audit.md) checked every saved mapping against the local corpus and independently reopened 18 primary sources.
- Whole-topic checklists, ambiguous intake branches, out-of-scope requests and a Saskatchewan-only substitution have separate diagnostic kinds. They do not inflate positive recall.
- Raw ID-hash folds are historical. `groups.clean_test(all_cases())` joins connected rewrite, exact-gold, normalized-description and source-document groups across the whole universe, excludes groups touching tuning, and retains one representative. This removes known leakage; it does not prove statistical independence or exhaustive expert annotation.
- The final exact-engine panel selects 50 positive cases plus 18 ambiguous and four out-of-scope diagnostics. The selected IDs, configuration and corpus/source digests are in the result file. Provider prompts never receive reference answers.

## Reproduce without providers

Use the worktree's own virtual environment and private `codedb/build/codedb.sqlite`. No app server is required.

```sh
.venv/bin/python -m pytest -q evals_dev/identify_bench -p no:cacheprovider
.venv/bin/python -m evals_dev.identify_bench.validate_web_cases docs/research/2026-10-23-elephant/cases-alberta.json
.venv/bin/python -m evals_dev.identify_bench.validate_web_cases docs/research/2026-10-23-elephant/cases-canada.json
.venv/bin/python -m evals_dev.identify_bench.engine_bench report
.venv/bin/python -m evals_dev.identify_bench.pipeline_bench report --input evals_dev/identify_bench/results/e2e_toc40-lex_tune.json
```

Report commands read saved results and never call providers. Replay the cached development experiments with:

```sh
.venv/bin/python -m evals_dev.identify_bench.candidate_audit --suite basic
.venv/bin/python -m evals_dev.identify_bench.candidate_audit --suite graph
.venv/bin/python -m evals_dev.identify_bench.candidate_audit --suite ensemble
```

These last commands need the original private request cache; a fresh checkout reports cache misses as errors. Caches, credentials and local corpus files are deliberately excluded from Git. The saved records preserve the measured outcomes for inspection without private cache access.

## Explicit live measurements

Live mode is off by default. Set `BENCH_ENV_FILE` to an existing private environment file when needed; the harness reads credentials into process memory and never changes or copies that file. Its default is this worktree's `.env`, with no automatic borrowing from another checkout.

```sh
BENCH_ENV_FILE=/absolute/path/to/private.env BENCH_OPENAI_CAP_USD=6 \
  .venv/bin/python -m evals_dev.identify_bench.engine_bench run --live --workers 3
```

The paid-call ledger reserves a conservative maximum before dispatch, limits local concurrency, and counts unresolved failures/crashes against the cap. Free-model accounting retains ambiguous local holds through the following UTC day even if that conservatively under-uses an allowance. It makes one attempt per call and preserves completed responses. The ledger is cumulative across prior experiments; its prices estimate token spend and are not an account billing receipt. Replayed token usage is not fresh spend or live latency.

The one-case optional-scorer integration smoke uses an explicit request maximum and preserves two free quota slots:

```sh
BENCH_ENV_FILE=/absolute/path/to/private.env BENCH_OPENAI_CAP_USD=6 \
  .venv/bin/python -m evals_dev.identify_bench.engine_bench run --live --limit 1 --workers 1 \
  --elephant 5 --output evals_dev/identify_bench/results/engine_elephant_smoke.json
```

It is an integration smoke, not another independent accuracy sample. Do not repeat it unnecessarily: a 60-article pool still needs five conservative scoring requests in the measured case. The old exhaustive screen needs roughly 131 calls for the short synthetic packing example and was not completed live under the 50/day account allowance.

## Read the evidence correctly

| Artifact | Scope |
| --- | --- |
| `elephant_*_40_tune.json` | Paired 20-case ranker diagnostic; reference articles were inserted into the pool. |
| `verify.json` / `verify.md` | Conditional verifier preservation; pools already contain the answers. |
| `e2e_toc40-lex_tune.json` | Earlier 57-record development snapshot; 52 complete pools. The old format lacks a durable attempt manifest, so the repaired reporter marks its headline provisional. |
| `cached_*_tune.json`, `fast_graph_candidate_tune.json` | Development-only cached ablations, without answer insertion. Larger output sets can improve recall while increasing reviewer burden. |
| `engine_shortlist_heldout.json` | Final cache-only verification of the exact engine response boundary using saved live requests, with every attempt retained and matching corpus/WAL fingerprints. Optional scorer disabled to respect quota. |
| `engine_elephant_smoke.json` | Cache-verified integration run including pinned Elephant scoring and the full-text reviewer. |
| `*_live_capture.json` | Original live records, retained separately; those earlier evaluator versions recorded a primary DB hash without a WAL-aware before/after check. |

Positive complete-case recall means every minimum reference article appeared in the final returned set. Article recall, output size, model picks, provider failures, invalid identifiers and checked quotations must be read beside it. Extra predictions are not fully adjudicated. Neither low probabilities nor articles outside the pool establish that a requirement does not apply. The 100% conditional verifier result is not end-to-end accuracy.

Final exact-engine results: **46/50** positive cases returned every reference (93/97 reference articles), at 60 candidates per case. Restricting the same responses to the first ten gives 39/50 complete cases. Tentative model picks alone cover every reference in 36/50 cases. Ambiguous-input branch coverage is 14/18. All four out-of-scope direct calls still produced model picks; this experimental component is unsuitable as an intake scope gate.

These are API response measurements. The current web `identifyCandidates` adapter presents at most three quoted choices and its library uses separately stored exhaustive relevance. Complete pool review in the UI is a remaining integration gate. `headline_valid` describes a complete attempt manifest and stable engine source, not successful accuracy or professional validation.
