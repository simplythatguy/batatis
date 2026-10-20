# Jev code-identification benchmark (2026-10-20)

A small, reproducible test of how well a decision model finds the NBC(AE) 2023, 2nd printing articles that govern a described situation. It uses only public Alberta precedents. The team's protected evaluation set (`evals/` on the archive branch) was not read or used.

## Data

- **Cases (53):** built by `scripts/build_cases.py` from the precedent index (`research/precedents/index.json` on branch `archive/local-main-2026-10-20`): 17 STANDATA variances, 3 Calgary SPVs, 24 STANDATA interpretations and 9 bulletins. The query is the precedent's title, summary and "applies to" text with every article number replaced by `[ref]`.
- **Gold:** the Division B articles each precedent cites whose 2023 heading was verified in the index (`same-number-present`, or a verified successor topic for variances). 84 gold articles, 1 to 3 per case. Interpretations and bulletins also cite context articles, so measured recall is a lower bound.
- **Corpus:** all 2,080 Division B articles in `codedb/build/codedb.sqlite` (heading path plus the first 700 characters of the article's sentences).

## Pipelines

| Pipeline | What happens |
|---|---|
| BM25 | SQLite FTS5 over all Division B provisions, best provision score per article |
| BM25 top 60 → Jev rerank | The 60 BM25 candidates go to Jev in one request; one Noul per article |
| Jev screens all | Every article judged, about 60 per request, 20 requests per case |
| Screen all → rerank top 60 | The screen's top 60 re-judged together in one request |

Noul used for code identification: "Article A{i} states a requirement that directly governs the situation described in `proposal`: the proposal must meet that requirement, relies on it, or departs from it." Model `jev-latest` (resolved to `jev-1.13.0` on 2026-10-20) through `jevkit.client.ask`.

## Results (53 cases)

| Pipeline | MRR | Top-1 | Top-5 | Recall@10 | Recall@50 | Recall@200 |
|---|---|---|---|---|---|---|
| BM25 | 0.485 | 32% | 66% | 65% | 77% | 83% |
| BM25 top 60 → Jev rerank | 0.728 | 66% | 81% | 73% | 77% | 83% |
| Jev screens all | 0.643 | 53% | 77% | 70% | 88% | 91% |
| Screen all → rerank top 60 | 0.723 | 64% | 81% | 72% | 88% | 91% |

- **Threshold curve (screen all):** p ≥ 0.10 keeps 96.5% of gold articles and passes 15% of the corpus (311 articles on average); p ≥ 0.05 keeps 100% and passes 41%.
- **Confidence:** the reranked top pick was correct in 7 of 8 cases with p ≥ 0.9 and 18 of 25 with p ≥ 0.8. Probabilities order candidates well but are not calibrated to "this is the governing article".
- **Cost and speed:** screening all 2,080 articles used about 0.38M input tokens per case (about $0.016 at $0.042 per million input tokens), 20 requests, about 1.6 s with 8 parallel requests. The whole study, including the project screens below, used about 23M input tokens (about $0.96) in about 1,260 requests with 0 failures.

### Project screen (synthetic rowhouse with secondary suites)

Scope fixed to Part 9 in code (1,055 articles). Noul: "A plan reviewer would likely raise an issue under Article A{i} for the project: the design as described appears not to meet this article, or the drawings omit information needed to check it." 0.9 s, about 190k tokens.

| Planted issue | Rank of 1,055 | Rank with the derived fact stated |
|---|---|---|
| 9.10.19.3. smoke alarm locations | 1 | 1 |
| 9.11.1.1. sound transmission | 5 | 7 |
| 9.10.9.16. separation of residential suites | 7 | 3 |
| 9.10.19.5. interconnection | 10 | 13 |
| 9.10.13.13. fire dampers | 21 | 16 |
| 9.10.11.2. firewalls not required | 84 | 30 |

The derived fact was "the building contains more than 2 houses with a secondary suite, and the party walls separating them are not firewalls". Multi-step conditions belong in code; the decision model then answers a direct question.

### Frontier verifier stage (blind)

On the 20 variance and SPV cases, the screen-all → rerank top 40 list was shuffled, stripped of scores and given to Claude Sonnet 5.5 (max effort) with only the case files readable (`scripts/prep_verifier.py`, answers in `verifier/sonnet-5.5-answers.jsonl`, scored by `scripts/score_verifier.py` against `verifier/manifest-with-gold.json`).

| Stage on the same 20 cases | MRR | Top-1 | Top-3 | Recall within 5 |
|---|---|---|---|---|
| Jev screen all → rerank | 0.748 | 65% | 85% | 69% |
| + Sonnet 5.5 verifier | 0.875 | 85% | 90% | 83% |

The verifier's top pick was correct 14 of 15 times at p ≥ 0.8 and 4 of 4 at p ≥ 0.9. It proposed 3 articles outside the shortlist, 2 of them gold (including 3.1.18.5. for the greenhouse-film case whose gold was not in the shortlist). Misses: oil and gas occupancy (picked 3.1.2.1. against gold 3.3.1.5.), elevator in place of a platform lift (ambiguous), and the greenhouse revision (gold outside the list).

## Rerun

The python.org Python 3.14 install on this Mac has no CA bundle, so `jev` calls fail with `"network"` unless a bundle is given:

```sh
SSL_CERT_FILE=/etc/ssl/cert.pem .venv/bin/python -I docs/research/2026-10-20-vision/jev-benchmark/scripts/run_bm25.py
SSL_CERT_FILE=/etc/ssl/cert.pem .venv/bin/python -I docs/research/2026-10-20-vision/jev-benchmark/scripts/run_jev.py
```

The scripts were written for scratch paths under `/tmp/jev-bench/`; edit the path constants at the top of each script, or recreate that layout from `data/` and `results/`. `results/jev_judgments.jsonl.gz` holds every judgment (case, article, probability) so the metrics can be recomputed without new calls. To test another decision model (for example Perplexity Decider v1.2 or vllm-sr/d3), replace `client.ask` in `scripts/jevrun.py` and keep everything else fixed.

## Limits

- Precedent summaries are short. Real intake facts from drawings are richer, so recall on real projects may be higher; that is untested.
- 53 cases from one province and one code. Not a held-out professional evaluation.
- Gold lists can be incomplete or include context references. A non-gold top pick can still be a relevant article.
