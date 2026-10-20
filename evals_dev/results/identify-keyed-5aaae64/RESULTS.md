# Keyed identify benchmark: PR #12 @ 5aaae64 (mean of 3 repeats)

Identify takes a pasted project description and suggests NBC(AE) 2023 provisions that may apply; the user confirms each one. top-1 is the share of cases where the first suggestion is the gold article. recall@5 is the share where the gold article is anywhere in the first 5 suggestions shown.

top-1 0.76 and recall@5 0.76 on 11 model-checked dev cases with a gold article (in-sample, mean of 3 runs on pinned 2025-04-14 snapshots; BM25 0.45); asks the applicant on 42% of cases; about C$0.03 per case, 4.5 s p50, 9.1 s p95.

- **Head benchmarked:** `5aaae64b70defcb4a949b04be891db62963ad362` (`backend/identify-api`, PR #12). Later heads change fact display, titles, the storey parser, questions and cards, but not BM25, rerank or verify. `c382ed7` was an earlier #12 checkout named for a rerun that was not used; this run is `5aaae64`.
- **Run:** 2026-10-20, 14:58-15:16 MDT, exit 0. Code was fetched file by file from GitHub at that sha, each blob checked against the tree SHA-1.
- **Command:** `BATATIS_LLM_PROVIDER=openai .venv/bin/python -m engine.identify.benchmark --repeats 3 --cases 20 --source evals_dev --fx-usd-cad 1.4097 --fx-date 2026-10-19`
- **Models (config.py pins, no env overrides):** rerank `gpt-4.1-mini-2025-04-14`, verifier `gpt-4.1-2025-04-14`. The API returned the same ids. Prices come from `config.PRICES`: $2/$8 for gpt-4.1 and $0.40/$1.60 for gpt-4.1-mini, per 1M input/output tokens.
- **FX:** 1.4097 CAD per USD on 2026-10-19 (Bank of Canada FXUSDCAD).
- **Sources:** `scripts/fetch_sources.py` matched every SHA-256 in `codedb/source_manifest.json`. The codedb build completed.
- **Cases:** evals_dev dev-001 to dev-020, with 3 repeats each. Figures are means over the repeats. The headline `scored_must_cite` group has n=11. `scored_ask_identify_gold` has n=4 and is not pooled into the headline. 5 cases have no gold.
- **Spend:** about US$2.21, from token counts times `config.PRICES` (not an invoice figure).

**Accuracy is model-checked, not human-verified. In-sample.**

## Terms

Names below are from `engine/identify/benchmark.py` at `5aaae64`. The plain "first suggestion" and "first 5" above are the ranked list: `benchmark.py:_read_repeat` sets `order` from `trace.ranked_ids`, and `benchmark.py:repeat_metrics` scores `order[:1]` and `order[:5]`. The `suggested` flag is a separate would-suggest hint. It is what the error and suggestion columns count.

- **scored_must_cite** (`benchmark.py:load_cases`). Headline group. Gold is copied from `gold.must_cite` only, via `gold_from_entries`. These cases are not pooled with the ask group. On this run, n=11.
- **scored_ask_identify_gold** (`benchmark.py:ask_group_summary`, gold list from `split_identify_gold`). Ask cases that carry `gold.identify_gold`. Only `role: benchmark` is the retrieval target. The score asks whether that article was found. It does not decide that the article applies. On this run, n=4.
- **MRR** (`benchmark.py:repeat_metrics`). For each gold case, `1 / (rank + 1)` of the first gold hit in `order`, or 0 when gold is absent, then the mean over those cases. The ask table uses the same formula in `ask_repeat_metrics`.
- **ask rate** (`benchmark.py:repeat_metrics`). Share of cases in the repeat whose intake is `ask`, divided by every case in the run (20), then averaged over the 3 repeats. `pipeline.py:run` sets `ask` when no article is marked suggested and the description is not a redirect.
- **stability** (`benchmark.py:aggregate`). Share of cases whose first ranked article (`order[0]`, recorded in `run_variants`) is the same on every repeat. The denominator is every case in the run.
- **majority top-1** (`benchmark.py:majority_top1`, rate in `aggregate`). For each gold case, the most common first ranked article across repeats. A tie keeps the article from the earliest repeat. The table is the share of the 11 gold cases where that article is in the gold list.
- **suggested errors (gold)** (`benchmark.py:repeat_metrics`). On must_cite cases, how many `suggested` articles fall outside that case's gold. The column is the sum for one repeat, averaged over the 3 repeats. It is a count of hints, not a share of 11, and not an acceptance.
- **suggested errors (ask)** (`benchmark.py:ask_repeat_metrics`). On ask-gold cases, how many `suggested` articles are outside the primary gold and the `role: secondary` articles. Suggesting a secondary article is not an error (`split_identify_gold`). Same kind of count as the gold column: a per-repeat sum, then the mean of 3.
- **suggestions (no gold)** (`benchmark.py:repeat_metrics`). On cases with neither must_cite nor identify_gold, how many articles are `suggested`. Recorded as that count, not as an error. Mean of the 3 repeats.

Headline `scored_must_cite`, n=11, mean of 3 repeats (min-max):

| Variant | top-1 | recall@5 | MRR | ask rate | stability | majority top-1 | suggested errors (gold) | suggestions (no gold) | in tok/case | out tok/case | p50 ms | p95 ms | USD/case | CAD/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_bm25 | 0.4545 | 0.6364 | 0.5422 | 1.00 | 1.00 | 0.4545 | 0 | 0 | 0 | 0 | 258 | 447 | $0.000000 | C$0.000000 |
| b_openai_rerank | 0.5455 (0.45-0.64) | 0.7879 | 0.6530 | 0.30 | 0.65 | 0.5455 | 10.3 | 9.0 | 10,425 | 245 | 2,232 | 6,466 | $0.004562 | C$0.006431 (C$0.006) |
| **c_openai_rerank_verify (shipped)** | **0.7576** (0.73-0.82) | 0.7576 | **0.7605** | 0.42 | 0.75 | **0.7273** | 3.7 | 7.0 | 16,580 | 581 | 4,548 | 9,073 | $0.019382 | C$0.027323 (C$0.03) |
| d_verify_700 | 0.6667 (0.64-0.73) | **0.8182** | 0.7374 | 0.37 | 0.75 | 0.7273 | 4.0 | 6.3 | 13,378 | 554 | 4,430 | 8,198 | $0.012868 | C$0.018139 (C$0.018) |

## Why c's recall@5 equals its top-1

The shipped verifier does reorder the list recall@5 reads. It does not make recall@5 stop at the suggestions that survive.

`benchmark.py:repeat_metrics` scores `order`. `benchmark.py:_read_repeat` fills `order` from `trace.ranked_ids`. In `pipeline.py:run` that list is the reranked pool (BM25 top 60, then the reranker). When the verifier returns picks, `run` moves the quote-checked picks to the front and leaves every other ranked article behind them. `llm.py:verify_candidates` calls `verify.py:check_quotes`: a pick whose quote is not in the article text is left out of that front group and stays at its rerank position. The verifier only sees the first 15 (`config.py` `VERIFY_N`). Nothing in that path deletes the tail, so the first 5 can still hold articles the verifier did not pick.

The `suggested` flag is a different hint in `pipeline.py:run`. At most 3 articles (`MAX_COMMITS`) are marked, and only with rerank probability at least 0.75, Part 9, and, once the verifier has run, membership in the kept picks. When none qualify, intake is `ask` (unless the text is a redirect). That changes the ask rate and the suggestion counts. It leaves `ranked_ids` as it was, so an ask still counts a gold article sitting at rank 2, 3, 4, or 5.

Variant d uses that same reorder with 700-character cards (`run_variants`). Its recall@5 is 0.8182 and its top-1 is 0.6667. The scorer allows recall@5 to exceed top-1 after verification.

What the reorder does explain for c against b: b leaves the verifier off (`run_variants`, `verify: False`), so its order is the rerank order and gold often sits in ranks 2–5 (recall@5 0.7879, top-1 0.5455). c runs the verifier on the full article text and puts kept picks first. Putting the gold article first turns a rank 2–5 hit into a top-1 hit. Putting five other picks in front of a gold article that had been inside the first 5 pushes that article out of the recall window.

On this run those two effects land together. `gold_from_entries` keeps one id per article, and dev-018's two sentences both collapse to `4.1.6.2.`, so each of the 11 cases is one article. top-1 and recall@5 are then each 0 or 1. The printed means 0.7576 and 0.7879 are 25/33 and 26/33 scored repeats. Equal means for c means the gold article was rank 1, or outside the first 5, on every one of those 33 repeats. b is one hit higher on recall@5, so on one scored repeat the full-text verifier pushed a gold article out of a top 5 that rerank had kept. The per-case `top5` and `first_gold_rank` that would name that repeat are written to `results.json` by `write_results`. That file is not in this repo.

`scored_ask_identify_gold`, n=4, mean of 3 repeats. This measures whether the article was found, not whether it applies:

| Variant | top-1 | recall@5 | MRR | suggested errors (ask) |
|---|---|---|---|---|
| a_bm25 | 0.00 | 0.25 | 0.125 | 0 |
| b_openai_rerank | 0.17 | 0.25 | 0.208 | 8.3 |
| c_openai_rerank_verify | 0.25 | 0.25 | 0.250 | 3.7 |
| d_verify_700 | 0.25 | 0.25 | 0.250 | 6.0 |

No variant fell back to BM25 (0 fallbacks).

## Caveats
- With n=11, one case moves top-1 by 0.09. With n=4 in the ask group, one case moves it by 0.25.
- Variant c (shipped) leads on top-1 and MRR; d leads on recall@5. Both vary between repeats (stability 0.75). Quote d's 0.818 only if d becomes the shipped config.
- The older single-run figures (c top-1 9/11 = 0.818, repeat 0 only, alias models, different error counting) are retired and not comparable.
- Suggested errors count the would-suggest hint. Identify does not accept any article without a user decision.
- Latencies come from one machine, with repeats run sequentially.
- These figures are not a finding that any design complies or is safe.
