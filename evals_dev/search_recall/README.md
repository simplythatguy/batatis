# Search recall

Comparison of four provision-search rankings on the codedb FTS5 index. The shipped ranking is `codedb.search` (`SHIPPED` in `codedb/search_rank.py`). The public signature is unchanged: words in, provisions out, `limit` 1..1000. The engine route still clamps the caller's limit.

Numbers in `results.json` are **model-checked, not human-verified**. Each row is labelled `in-sample` or `held-out`.

## Gold

| Pool | Has gold | How it is scored | Split |
| --- | --- | --- | --- |
| repo-key | 38 | `evals_dev` `must_cite`, provision level, ancestor/descendant counts | 27 in-sample, 11 held-out |
| identify-regression | 21 | `gold_articles`, article level, plus distractor@5 | 15 in-sample, 6 held-out |
| Mira regressions | 3 | Case A key `9.27.5.1.(2)`, `9.27.5.3.(3)(b)`, and `9.23.17.3.(1)` after Unc confirmed that article. Reported separately. Not in the scored n. | forced in-sample |
| other regressions | 6 | No repo key, so not gold. Includes the cladding/furring phrase and Unc's firestop queries. | forced in-sample |
| part3-held-out | 5 (idr-022..026) | Part 3 articles. idr-025 counts if either `3.2.2.64.(2)(a)` or `3.2.2.62.(2)` is covered. | held out as a block, not shuffled |

`idr-001`..`idr-021` are unchanged. The Part 3 block is scored on its own (`part3_hit@8` and `must_not_return@8`), so a Part 9 analogue is visible separately from a Part 3 hit.

Gold v2 is a second table, label `gold v2, 16 scored, article-level for 009`. It is the identify benchmark's 11 `must_cite` cases, still scored at provision level, plus dev-006, dev-010, dev-011, dev-015, and dev-009. dev-009 is scored as Article 9.27.2.2. The canonical identify label from PR #12 stays `model-checked, not human-verified`.

`evals/fixtures` and `evals/battle-prompts` have no provision gold. `should_cite` was not used. 9.23.17.3.(1) is counted as gold for idr-001 and idr-002. There is no with/without split.

Seed `20261020`, drawn before tuning and not reshuffled. `random.Random(seed)` shuffles sorted repo-key ids, then sorted idr ids. Holdout is `round(0.30 * n)` from the front of each shuffle. Regressions are not in either shuffle.

## Variants

- **v0** — historical query: quoted words OR'd, title weight 5, SQL limit = requested limit.
- **v1** — stop words plus a generic synonym map (siding/cladding, nail/fastener/attach, foam/insulation, furring/strapping, sheath). Same title weight.
- **v2** — historical query, title weight 12, and a Part 9 scale when the query names a house and not a Part 3 cue.
- **v3** — v1's query. When the query names two or more of those concepts: rank articles by how many concepts they match, then by whether the heading matches a concept, then by BM25. One extra full-match article from the leading section is pinned to position 2 when the head does not already have two. An attachment article keeps its furring article beside it when the query names sheathing or furring. Part 9 is a 1.15 tie-break on BM25, only when a house is named. Queries with fewer than two concepts use the AND path in the next paragraph.

v2's blanket title boost is the one that pulls 9.29.9.3.(2) (heading "Nails") into the top 5 of `sheathing nail siding`. v3 does not do that.

Queries that name fewer than two of those concept groups try an AND of the content words (at most six). Zero or very few AND hits keep every near-miss (each word dropped once), ranked by how many words match, then by the leading section, then by BM25. One article is shown before the rest of that article. If that set is still very small, the query falls back to OR. Queries with two or more concept groups keep the OR pool. `firestop plastic pipe penetration` is the empty-AND case: the near-miss set puts `3.1.9.1.(1)` and clause `3.1.9.4.(4)(b)` in the top 8. A query that is only an article, sentence, or clause id (`3.1.9.1`, `3.1.9.1.`, `3.1.9.1.(1)`, `9.10.19.3`) is looked up and returned first; an article is followed by its children. An unknown id stays a normal BM25 result. `fire stopping`, `fire-stopping`, `firestopping`, `fire stop`, `fire-stop`, and `fire stops` are folded to `firestop` before BM25, and that term also matches the split forms in the index. A search hit's `attribution` is the objective/function brackets for that provision, or `lookup not available` when none are listed. An article with no stored text carries `children`, one 25-word window per sentence.

An article whose indexed text is empty, or only a "See Note" pointer, is returned with one 25-word window from the child sentence that shares the most query words. The other sentences are not copied onto the card. `pdf_page` is the page to open. Each hit is at most 25 words and one search response is at most 75 words of code text; a later hit keeps its id and page with an empty snippet. A heading that is the only article title containing a query word is placed in front of its child sentence only when the window still has room. A full window is left as ranked, so the sprinkler sentences stay in the top 8.

Recall is the fraction of gold covered in the top 5 or top 8. A hit covers gold when it is the gold id, an ancestor, or a descendant. MRR is 1 over the first covered rank. distractor@5 is the fraction of queries whose top 5 contains any listed `must_not_return` article. Lower is better.
