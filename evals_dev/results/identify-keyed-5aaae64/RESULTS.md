# Keyed identify benchmark: PR #12 @ 5aaae64 (mean of 3 repeats)

- **Head benchmarked:** `5aaae64b70defcb4a949b04be891db62963ad362` (`backend/identify-api`, PR #12). Later heads change fact display, titles, the storey parser, questions and cards, but not BM25, rerank or verify. This is not the `c382ed7` checkout.
- **Run:** 2026-10-20, 14:58-15:16 MDT, exit 0. Code was fetched file by file from GitHub at that sha, each blob checked against the tree SHA-1.
- **Command:** `BATATIS_LLM_PROVIDER=openai .venv/bin/python -m engine.identify.benchmark --repeats 3 --cases 20 --source evals_dev --fx-usd-cad 1.4097 --fx-date 2026-10-19`
- **Models (config.py pins, no env overrides):** rerank `gpt-4.1-mini-2025-04-14`, verifier `gpt-4.1-2025-04-14`. The API returned the same ids. Prices come from `config.PRICES`: $2/$8 for gpt-4.1 and $0.40/$1.60 for gpt-4.1-mini, per 1M input/output tokens.
- **FX:** 1.4097 CAD per USD on 2026-10-19 (Bank of Canada FXUSDCAD).
- **Sources:** `scripts/fetch_sources.py` matched every SHA-256 in `codedb/source_manifest.json`. The codedb build completed.
- **Cases:** evals_dev dev-001 to dev-020, with 3 repeats each. Figures are means over the repeats. The headline `scored_must_cite` group has n=11. `scored_ask_identify_gold` has n=4 and is not pooled into the headline. 5 cases have no gold.
- **Spend:** about US$2.21, from token counts times `config.PRICES` (not an invoice figure).

**Accuracy is model-checked, not human-verified. In-sample.**

Headline `scored_must_cite`, n=11, mean of 3 repeats (min-max):

| Variant | top-1 | recall@5 | MRR | ask rate | stability | majority top-1 | suggested errors (gold) | suggestions (no gold) | in tok/case | out tok/case | p50 ms | p95 ms | USD/case | CAD/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a_bm25 | 0.4545 | 0.6364 | 0.5422 | 1.00 | 1.00 | 0.4545 | 0 | 0 | 0 | 0 | 258 | 447 | $0.000000 | C$0.000000 |
| b_openai_rerank | 0.5455 (0.45-0.64) | 0.7879 | 0.6530 | 0.30 | 0.65 | 0.5455 | 10.3 | 9.0 | 10,425 | 245 | 2,232 | 6,466 | $0.004562 | C$0.006431 |
| **c_openai_rerank_verify (shipped)** | **0.7576** (0.73-0.82) | 0.7576 | **0.7605** | 0.42 | 0.75 | **0.7273** | 3.7 | 7.0 | 16,580 | 581 | 4,548 | 9,073 | $0.019382 | C$0.027323 |
| d_verify_700 | 0.6667 (0.64-0.73) | **0.8182** | 0.7374 | 0.37 | 0.75 | 0.7273 | 4.0 | 6.3 | 13,378 | 554 | 4,430 | 8,198 | $0.012868 | C$0.018139 |

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
