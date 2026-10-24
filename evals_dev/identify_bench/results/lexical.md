# Lexical candidates + cross-reference graph (offline)

Run: `.venv/bin/python -m evals_dev.identify_bench.candidates_lexical --test` (2026-10-23, zero provider calls).
Full numbers: `results/lexical.json`. Code: `candidates_lexical.py`. Kinds = `benchmark` only.

**Case snapshot.** web-ab (`cases-alberta.json`) was still being written during this work. This run saw
22 web-ab cases. Tune = 68 cases (dev 24, precedent 33, web-ab 11), 91 gold articles. Test = 45 cases
(dev 14, precedent 20, web-ab 11), 60 gold articles. web-ca was absent. Every gold id is a code-database article.
The file has since grown to 45 web-ab cases, so a rerun will give different numbers.

## Graph

Parsed from Division B sentence/clause/subclause text plus appendix-note text (via note_links → the noted
article). 2,080 articles, 850 with outgoing references. Edges: article 1,875 · note 338 · table 87 ·
subsection 446 · section 204. "of Division A/C" and relative references ("Sentence (2)") are dropped.
Article ranges are enumerated in code order, capped at 60.

## Complete recall vs pool size (tune, 68 cases)

| recipe | 20 | 40 | 60 | 100 | 150 | 200 |
|---|---|---|---|---|---|---|
| bm25 | .691 | .779 | .779 | .824 | .838 | .838 |
| bm25_v3 (pipeline arm) | .721 | .779 | .779 | .779 | .824 | .853 |
| rrf(bm25, bm25_v3) | .735 | .794 | .794 | .824 | .838 | .838 |
| rrf + out-refs of top 5 | .721 | .809 | .809 | .824 | .853 | .853 |
| rrf + siblings of top 3 (seeds 5) | .676 | .809 | .838 | .838 | .838 | .868 |
| rrf + out-refs of top 8 | — | **.824** | — | — | — | — |
| **rrf + out-refs of top 5 + siblings of top 3** (`rrf+out@5+sib3`) | .676 | **.824** | **.853** | .853 | .853 | .882 |

Pool = top-5 RRF seeds, then their outgoing article/table/note references, then the subsection siblings of the
top 3, then the rest of the RRF list, truncated to the pool size.

## Test fold (reported once, after tuning)

| recipe | 20 | 40 | 60 | 100 | 150 | 200 |
|---|---|---|---|---|---|---|
| bm25 | .800 | .867 | .867 | .867 | .867 | .889 |
| bm25_v3 | .800 | .844 | .867 | .889 | .889 | .911 |
| rrf | .800 | .867 | .867 | .911 | .911 | .911 |
| **rrf+out@5+sib3** | .778 | **.867** | **.867** | .933 | .978 | .978 |

## Findings

- At pool 40 and 60 the lexical ceiling is about 82–85% complete recall on tune and 87% on test. On test, the
  graph recipe adds nothing at 40 or 60 over plain RRF (39/45 each). It helps only at 100 and above (.933 / .978 vs .911).
  Its tune gain at 40/60 is +2 and +4 cases out of 68. Many recipes tie at that level (four tie at 60), so treat the
  pick as weakly supported.
- RRF of bm25 and bm25_v3 beats either arm alone at small pools. bm25_v3 alone tops out early because it returns at most 300 ids.
- Expansion helps only after seeds are added. Neighbours of the top 10 alone reach .72 (out, mean 23 ids),
  .75 (both, 33 ids) or .76 (siblings, 78 ids). The extra recall comes from graph neighbours filling the slots between
  rank ~10 and the pool limit. Subsection siblings recover more than reference edges do. Two hops and whole-subsection
  reference expansion add little on top.
- bm25_v3 costs about 35 s per long description at the pipeline's limit of 300. The harness runs it on 8 processes.

## Misses at pool 60 (tune, recommended recipe): 10 cases, 9 of them precedent

Rank = position in the same recipe's 400-long list (— = not reached at all).

| case | gold (rank, ✗ = missed) |
|---|---|
| dev-014 | 9.9.8.2. (249 ✗) |
| standata-…-23-bcb-003 | 9.10.3.1. (— ✗) |
| standata-…-23-bcb-007 | 9.10.11.2. (27), 9.10.9.3. (— ✗), 9.32.1.2. (57) |
| standata-…-23-bci-001 | 4.1.1.1. (— ✗) |
| standata-…-23-bci-010 | 3.1.17.1. (92 ✗), 3.1.18.1. (— ✗) |
| standata-…-23-bci-025 | 9.10.3.1. (— ✗) |
| standata-…-23-bci-030 | 3.2.5.6. (— ✗), 8.1.1.1. (2) |
| standata-…-23-bci-043 | 3.2.4.5. (1), 3.2.9.1. (155 ✗) |
| standata-…-23-bcv-011r1 | 3.1.18.5. (168 ✗) |
| calgary-spv-006-… | 9.10.11.2. (1), 9.10.13.13. (— ✗) |

Pattern: the missed articles are general "hub" articles: ratings/scope (9.10.3.1., 4.1.1.1.), occupant-load and
special-event articles (3.1.17.1., 3.1.18.x), fire-department access (3.2.5.6.) and service penetrations (9.10.9.3.).
Precedent summaries describe the situation without the words in those articles. Half are absent from the lexical list
altogether, so no pool size or reference expansion recovers them. They need semantic or LLM candidate generation
(or a curated "always consider" hub list), not more lexical depth.
