# Search recall

Comparison of four provision-search rankings on the codedb FTS5 index. The shipped ranking is `codedb.search` (`SHIPPED` in `codedb/search_rank.py`). The public signature is unchanged: words in, provisions out, `limit` 1..1000. The engine route still clamps the caller's limit.

Numbers in `results.json` are **model-checked, not human-verified**. Each row is labelled `in-sample` or `held-out`.

## Gold

| Pool | Has gold | How it is scored | Split |
| --- | --- | --- | --- |
| repo-key | 38 | `evals_dev` `must_cite`, provision level, ancestor/descendant counts | 27 in-sample, 11 held-out |
| identify-regression | 21 | `gold_articles`, article level, plus distractor@5 | 15 in-sample, 6 held-out |
| Mira regressions | 3 | Case A key `9.27.5.1.(2)`, `9.27.5.3.(3)(b)`, and `9.23.17.3.(1)` after Unc confirmed that article. Reported separately. Not in the scored n. | forced in-sample |
| other regressions | 3 | No repo key, so not gold. The cladding/furring phrase is asserted in the test. | forced in-sample |

`evals/fixtures` and `evals/battle-prompts` have no provision gold. `should_cite` was not used. 9.23.17.3.(1) is counted as gold for idr-001 and idr-002. There is no with/without split.

Seed `20261020`, drawn before tuning and not reshuffled. `random.Random(seed)` shuffles sorted repo-key ids, then sorted idr ids. Holdout is `round(0.30 * n)` from the front of each shuffle. Regressions are not in either shuffle.

## Variants

- **v0** — historical query: quoted words OR'd, title weight 5, SQL limit = requested limit.
- **v1** — stop words plus a generic synonym map (siding/cladding, nail/fastener/attach, foam/insulation, furring/strapping, sheath). Same title weight.
- **v2** — historical query, title weight 12, and a Part 9 scale when the query names a house and not a Part 3 cue.
- **v3** — v1's query. When the query names two or more of those concepts: rank articles by how many concepts they match, then by whether the heading matches a concept, then by BM25. One extra full-match article from the leading section is pinned to position 2 when the head does not already have two. An attachment article keeps its furring article beside it when the query names sheathing or furring. Part 9 is a 1.15 tie-break on BM25, only when a house is named. Queries with fewer than two concepts keep the FTS order.

v2's blanket title boost is the one that pulls 9.29.9.3.(2) (heading "Nails") into the top 5 of `sheathing nail siding`. v3 does not do that.

Recall is the fraction of gold covered in the top 5 or top 8. A hit covers gold when it is the gold id, an ancestor, or a descendant. MRR is 1 over the first covered rank. distractor@5 is the fraction of queries whose top 5 contains any listed `must_not_return` article. Lower is better.
