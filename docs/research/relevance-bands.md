# Relevance ring cut-offs for Division B articles

Date: 2026-10-20. Status: benchmark-derived, not field-calibrated. Model: `jev-1.13.0`. Labels: **measured** (computed today from the raw Jev judgments) and **judgement** (a choice rule, stated so you can change it). Code citations are NBC(AE) 2023, 2nd printing. The numbers are also in [relevance-bands.json](relevance-bands.json).

## Recommendation

Use x = 0.30 and y = 0.85. Both are judgement calls. Every number below is measured.

| Ring | Rule on the shown probability p | Articles per case (of 2,080) | Gold articles in the ring (of 84) | Gold rate per article |
|---|---|---|---|---|
| Grey | p is 0 or missing | 0 | 0 | not applicable |
| Green | 0 < p < 0.30 | 2,034 on average (98%) | 13 (15.5%) | 0.012% |
| Yellow | 0.30 <= p < 0.85 | median 28, mean 46, 90th percentile 68 | 56 (66.7%) | 2.3% |
| Red | p >= 0.85 | median 0, mean 0.34, at most 3 | 15 (17.9%) | 83% (15 of 18) |

Gold means an article the matching STANDATA or Calgary SPV precedent cites. The table is the display rule without the guard described below. In the benchmark a typical case shows no red, about 28 yellow and the rest green. Red appears in 15 of 53 cases (28%), and the strongest article in each of the other 38 cases is yellow.

Display rule:

- Show the rerank probability for an article the rerank judged (the 60 highest screen probabilities for the case). Show the screen probability for every other article. Both use the same x and y (see Screen versus rerank).
- Compare `round(p, 2)` with the cut-offs. Jev reports hundredths.
- Grey means "no Jev score". Jev never returned 0 in 110,240 screen judgments (minimum 0.01), so a literal p = 0 does not occur. Grey is the state before a case is scored, when Jev is unavailable, or when an article is missing from the response.
- Guard, recommended: an article the rerank did not judge is never yellow or red. That caps the flagged set at 60 per case, however the scores move on longer briefs (see Limits). It changes 10 of 53 benchmark cases and costs one gold article (14 in green instead of 13). With the guard, yellow has a median of 28, a 90th percentile of 56 and a maximum of 59. Articles ranked below 60 show green even when their screen score is 0.30 or more.

```
p = rerank[a] if a in rerank else screen.get(a)        # None when neither exists
ring = 'grey' if p is None or p <= 0 else 'green' if p < 0.30 else 'yellow' if p < 0.85 else 'red'
if a not in rerank and ring in ('yellow', 'red'): ring = 'green'     # the guard
```

Wiring. `engine/identify/relevance_bands.json` on `api/code-library` holds `{"x":0.2,"y":0.6,"status":"placeholder_uncalibrated"}`, and `display_probabilities()` in `engine/relevance.py` already applies the rerank-over-screen rule. Replace the file with `{"x":0.3,"y":0.85,"status":"benchmark-derived, not field-calibrated"}` and keep it to those three keys, because `engine/tests/test_relevance.py` compares the file with the validated model. Do not copy `relevance-bands.json` from this folder into the engine, since it carries extra keys. The guard needs no API change, because the response already carries the `rerank` map.

What each ring can claim. The labels in `web/src/calm/relevance.ts` already fit the evidence, so keep them:

- Red, "Likely applies · address this". Five in six red articles were precedent-cited. Do not write "definitely".
- Yellow, "Might apply · check this". About 1 in 43 yellow articles was cited, but yellow holds two thirds of all cited articles.
- Green, "Unlikely to apply". Do not write "definitely not related". Thirteen of 84 cited articles (15.5%) are green.
- Grey, "Not scored". The separate "No sign it applies" state for p = 0 never occurs with Jev data.
- Do not call the number a chance. The gold rate is 3% at p = 0.5 to 0.6 (table below), so p is a ranking score. "Jev relevance 34%" is fine. "34% chance" is not.

## Why these cut-offs

**Judgement.** y is the lowest round value where the red set is at least 80% gold. The gold rate stays below 70% up to 0.83, then reaches 81% at 0.84 and 83% at 0.85. Picking the lowest y on a 0.01 grid with a red set that is at least 80% gold (and at least 10 articles) gives 0.84 in 52 of 53 leave-one-case-out folds and 0.85 in the other. The price is coverage, so expect red in about one case in four.

**Judgement.** x is the last cut-off before recall falls quickly. Gold kept out of green is flat at 84.5% (71 of 84) for every x from 0.28 to 0.31, then drops to 75% at 0.35, while the median flagged count only falls from 28 to 20. At x = 0.30 the median case flags 28 articles (90th percentile 69). The data support anything from 0.27 to 0.33, depending on whether you ask for 85% or 80% of gold outside green.

The requirement "green holds almost no gold" cannot be met without flooding. Getting green under 5% gold needs x of 0.12 or lower, which flags a median of at least 129 articles per case. Pick the row in the x table that matches how many flags the interface can show.

## Method

- **Inputs.** `docs/research/2026-10-20-vision/jev-benchmark/` holds `data/cases.json` (53 cases, 84 gold articles) and `results/jev_judgments.jsonl.gz`. The folder is on `main`, `dev` and `origin/main` with identical data and results files. It is not on `archive/local-main-2026-10-20`. Screen = qkey `govern_exhaustive` (53 cases x 2,080 articles = 110,240 judgments). Rerank = qkey `govern_stage2_exh60` (3,180 judgments: the screen's top 60 per case, re-judged in one request).
- **Same pipeline as the app.** `engine/identify/screen.py` and `engine/identify/__init__.py` on `ops/artisty-evidence-contract-r8-20261021` use the same question text, 700-character article cards, 56,000-character request limit and top-60 rerank. The model is pinned to `jev-1.13.0`, the version `jev-latest` resolved to when the benchmark ran.
- **The numbers measure the work.** All 110,240 screen cells exist, with no duplicates or conflicting rows. The main run's log shows 0 errors in 1,113 requests, and the benchmark README reports 0 failures in about 1,260 requests for the whole study. The rerank pool equals the screen's top 60 in 53 of 53 cases. Recomputed batching gives 20 screen requests and 1 rerank request per case.
- **Cases.** 24 interpretations, 17 variances, 9 bulletins and 3 Calgary SPVs. Gold is 1 to 3 Division B articles per case (mean 1.6). Base rate: 84 of 110,240 cells (0.076%), and 75 of 3,180 (2.4%) inside the rerank pool. Nine gold articles lie outside the pool.
- **Metrics.** Per case, count the articles in each ring and the gold articles in each ring, then pool over cases. Intervals resample the 53 cases 4,000 times. The red rate also gets a Wilson interval because it has only 18 articles.
- **Cross-check.** A second implementation written from the raw files, sharing no code with the first, reproduced the ring table, the probability table, the y and x tables, the top-score counts and the screen-only fallback.

## Results

Probability against gold rate, using the shown probability. This is why p is a ranking score and not a chance of being cited.

| p | Articles | Gold | Gold rate |
|---|---|---|---|
| below 0.10 | 93,928 | 3 | 0.003% |
| 0.10 to 0.19 | 10,997 | 6 | 0.05% |
| 0.20 to 0.29 | 2,864 | 4 | 0.14% |
| 0.30 to 0.39 | 1,180 | 10 | 0.8% |
| 0.40 to 0.49 | 635 | 5 | 0.8% |
| 0.50 to 0.59 | 359 | 11 | 3.1% |
| 0.60 to 0.69 | 170 | 10 | 5.9% |
| 0.70 to 0.79 | 72 | 14 | 19% |
| 0.80 to 0.84 | 17 | 6 | 35% |
| 0.85 to 0.89 | 10 | 8 | 80% |
| 0.90 and up | 8 | 7 | 88% |

The y table. Red per case is the mean number of red articles.

| y | Red per case | Cases with red | Gold in red | Gold rate (95% Wilson) | Share of all gold |
|---|---|---|---|---|---|
| 0.70 | 2.02 | 40 | 35 of 107 | 33% (25 to 42%) | 41.7% |
| 0.75 | 1.09 | 31 | 25 of 58 | 43% (31 to 56%) | 29.8% |
| 0.80 | 0.66 | 25 | 21 of 35 | 60% (44 to 74%) | 25.0% |
| **0.85** | 0.34 | 15 | 15 of 18 | 83% (61 to 94%) | 17.9% |
| 0.90 | 0.15 | 8 | 7 of 8 | 88% (53 to 98%) | 8.3% |

The x table. Flagged means yellow plus red, per case. The last three columns apply the guard.

| x | Gold in green | Flagged: median / mean / 90th / max | Gold in green | Flagged: median / 90th / max |
|---|---|---|---|---|
| 0.10 | 3 (3.6%) | 195 / 308 / 691 / 1,755 | 9 | 59 / 60 / 60 |
| 0.15 | 6 (7.1%) | 91 / 163 / 357 / 1,529 | 9 | 55 / 60 / 60 |
| 0.20 | 9 (10.7%) | 48 / 100 / 188 / 1,229 | 10 | 47 / 59 / 60 |
| 0.25 | 11 (13.1%) | 36 / 65 / 109 / 929 | 12 | 36 / 58 / 60 |
| **0.30** | 13 (15.5%) | 28 / 46 / 69 / 695 | 14 | 28 / 56 / 59 |
| 0.35 | 21 (25.0%) | 20 / 33 / 54 / 485 | 21 | 20 / 53 / 58 |
| 0.40 | 23 (27.4%) | 15 / 24 / 46 / 313 | 23 | 15 / 46 / 58 |
| 0.50 | 28 (33.3%) | 6 / 12 / 27 / 101 | 28 | 6 / 27 / 53 |

Against the current placeholders, x = 0.20 and y = 0.60 (`engine/identify/relevance_bands.json` on `api/code-library`, `DEFAULT_BANDS` in `web/src/calm/relevance.ts`):

| | Placeholders 0.20 / 0.60 | Recommended 0.30 / 0.85 |
|---|---|---|
| Red per case: mean / median / 90th / max | 5.2 / 3 / 12 / 37 | 0.34 / 0 / 1 / 3 |
| Cases with any red | 44 of 53 | 15 of 53 |
| Gold rate in red | 16% (45 of 277) | 83% (15 of 18) |
| Yellow per case: mean / median / 90th | 95 / 45 / 179 | 46 / 28 / 68 |
| Gold in green | 9 (10.7%) | 13 (15.5%) |

Other results at x = 0.30 and y = 0.85:

- The web code library rolls parts, sections and subsections up to the highest article score. With that roll-up a typical case lights 4 of 10 parts, 8 of 93 sections and 17 of 443 subsections (90th percentile 6, 19 and 42). With the guard the largest case lights 23 sections instead of 60.
- Without the guard, 6 of 53 cases flag more than 60 articles, 3 flag more than 100, and the largest flags 695. Flagged counts per case: 10th percentile 3, quartiles 10 and 43, 90th percentile 69.
- Among the 15 cases whose top score is at least 0.85, the top article is gold in 12. At 0.80 it is 18 of 25 cases, and at 0.90 it is 7 of 8. The median case's top score is 0.78 (quartiles 0.70 and 0.85).
- Variance and SPV cases (20, cleaner gold) have 3 of 28 gold articles in green (10.7%). Interpretation and bulletin cases (33, which cite context articles) have 10 of 56 (17.9%). Part 9 has 5 of 44 gold in green and Part 3 has 6 of 29. The other Parts have 11 gold articles, too few to compare.
- The 3 red articles that were not gold are 3.3.4.8., 9.9.6.7. and 4.4.3.1. Each reads as on topic for its case (openable-window protection, door locking, storage-rack design basis). That is my reading, not a human key, and it suggests strict gold rates understate true precision.
- Three of the 11 non-gold articles at 0.80 to 0.84 are generic "Scope" or "Application" articles from Parts 3, 8 and 9. The live run (Limits, item 2) also put 9.25.1.1. "Scope and Application" at 0.85.

## Screen versus rerank

The two scales are close enough to share one pair of cut-offs, so the rerank can override the screen. Recommended source: both.

- On the same 3,180 articles the mean is 0.313 for the screen and 0.312 for the rerank, and the rank correlation is 0.825.
- Gold against non-gold in that pool: area under the curve 0.859 for the screen and 0.877 for the rerank. The difference, +0.017, has a 95% interval of -0.014 to +0.048, so it is not measurable.
- The gold rate per probability bin overlaps between the two (for example 43% against 52% at 0.80 to 0.89, and 18% against 19% at 0.70 to 0.79).
- At matched flag budgets, five display rules keep the same gold within 2 articles (screen only, rerank override, max, mean and min keep 70, 71, 71, 72 and 71 of 84 at a median of 28 flagged). No blend beats one threshold on one probability, so use rerank override because it matches the order of the ranked list.
- Red sets: the screen has 19 red articles (all inside the pool) and the rerank has 18. They share 13, of which 11 are gold. Six are red only in the screen (4 gold) and five only in the rerank (4 gold).
- Fallback: with the screen alone, the same cut-offs keep 69 of 84 gold out of green (82.1%), flag a median of 23, and give a red set that is 79% gold (15 of 19).

## Uncertainty

- Case-resampled 95% intervals at x = 0.30, y = 0.85: red gold rate 64 to 100% (Wilson 61 to 94%), red per case 0.19 to 0.53, cases with any red 17% to 42%, gold in green 8.7% to 22.9%, yellow gold rate 1.3% to 4.1%, median flagged 18 to 35, 90th percentile flagged 46 to 144.
- The same request judged twice (60 judgments, one case) differs by 0.010 on average, at most 0.07, with no ring change.
- The same article judged in a different request, with different companion articles, differs by 0.04 to 0.08 on average (90th percentile 0.11 to 0.17). Of the articles at or above 0.30 in either context, 18% to 33% fall below 0.30 in the other. The green and yellow line is soft by about 0.05. Red is steadier, because only 11 of 3,180 articles cross 0.85 between screen and rerank.

## Limits

1. **Small sample.** 53 cases, four of which revise another case in the set, and 84 gold articles. Red rests on 18 articles in 15 cases. The step from 35% (0.80 to 0.84) to 80% (0.85 to 0.89) comes from 17 and 10 articles.
2. **Benchmark queries are not applicant prose.** They are STANDATA summaries of 16 to 42 words (median 29) that name one departure from the code. Applicant prose is broader and longer.
   - The one live run of the app pipeline on applicant prose scored 101 articles at or above 0.30 (55 with the guard) and 4 at or above 0.85. The input was a 36-word product description, and the receipt is in `engine/CODE_LIBRARY_API.md` on `api/code-library`. Only three of the 53 benchmark cases flag more than 101, and the benchmark's largest red count is 3. At x = 0.40 and 0.50 the same run flags 71 and 52 (53 and 49 with the guard). The placeholders (0.20 and 0.60) put 40 articles in red. Rolled up the code tree, the run lights 24 of 93 sections (14 with the guard). That run has no gold labels, so it says nothing about accuracy.
   - The 60 development descriptions in `evals_dev/cases/` run 20 to 98 words (median 50). The three demo briefs (`engine/identify/demo_cache.json` on `origin/backend/identify-api`) run 218 to 327 words. Inside the benchmark, longer queries score slightly higher (rank correlation 0.17 with the flagged count and 0.28 with the top score).
   - One 105-word rowhouse description, scored with a different question ("applies to this building"), put 47% of articles at or above 0.30 and 5.0% at or above 0.85, against 2.2% and 0.016% in the benchmark. That question differs from `GOVERN`, so it shows how far the scale can move, not what `GOVERN` would do.
   - Before relying on x and y, score the 60 development descriptions and the three demo briefs with `GOVERN` (about $0.02 per case). If the median flagged count is over about 40 or red is over about 3 per case, raise x toward 0.40 instead of leaning on the guard alone. The gold for those cases is model-authored, so that run tests volume, not accuracy.
3. **Gold is the precedent's own citation list.** Interpretations and bulletins also cite context articles, and some relevant articles are never cited. Gold rates are floors for true relevance. Recall is measured only against the cited list and can move either way. Ten of the 13 gold articles in green come from interpretation and bulletin cases (for example a sprinkler article cited in an occupant-load interpretation).
4. **Not calibrated.** The team's note on the vendor documentation says Jev's confidence page tells users to set thresholds on their own data (`docs/research/2026-10-20-vision/A-models-jev-s1mb.md`, "Calibration claims"). No `evals_dev/human_key/calibration.json` exists on any branch, and the human key is unfilled (n = 0). `COMMIT_THRESHOLD = 0.75` in `engine/identify/config.py` on `origin/backend/identify-api` is marked `placeholder_uncalibrated`. On this benchmark p >= 0.75 has a 43% gold rate (25 of 58), so do not reuse 0.75 for red. Red is a display state, not an accepted article.
5. **One model and one pipeline.** The cut-offs hold for `jev-1.13.0` with the `GOVERN` question. A new Jev version, another model, or the OpenAI-based default on `origin/backend/identify-api` (`gpt-4.1-mini`) has a different scale and needs its own fit.
6. **One run per case.** There is no repeat of the full benchmark. The only repeat is 60 judgments for one case.
7. **Editions.** 49 cases cite NBC(AE) 2023, three are Calgary SPVs with no edition number, and one is an ABC 2014 variance whose gold uses a successor-topic mapping. Gold uses 2023 article numbers throughout.
8. **Grey is untested.** No judgment in the data is 0 or missing, so grey behavior comes from the pipeline code, not from the benchmark. `engine/cli_sut.py` returns `None` probabilities when it falls back to BM25, and the code-library route answers 404 "not scored" until a case is scored.

## Recompute

Take each case's rerank probability where one exists and the screen probability otherwise, band it with `round(p, 2)`, and count articles and gold articles per band. Use `jev_judgments.jsonl.gz` rows with `qkey` of `govern_stage2_exh60` (rerank) and `govern_exhaustive` (screen), and the `gold` lists in `cases.json`. No script is committed for this analysis.
