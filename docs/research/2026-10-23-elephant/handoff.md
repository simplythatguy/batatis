# Elephant article-identification integration handoff

2026-10-23, America/Edmonton. Worktree: `work/elephant-accuracy-20261023`; base `12d44b11b15b8581361a96f401f459f677baf50b`. The local commit containing this handoff is the integration unit. Remote branches, canonical configuration/database and application servers were outside this work.

**The requested universal 100% accuracy target was not achieved.** The exact-engine experiment returned every minimum reference article for **46/50 positive cases (92%)**. Tentative model suggestions alone did so for **36/50 (72%)**. The candidate remains opt-in, with automatic article commitment disabled and existing uncalibrated relevance presentation preserved.

## What is ready for inspection

- `engine/identify/shortlist.py` implements an authoritative full-TOC selection plus fast BM25 union, a bounded candidate pool, and full-body review of every candidate. Exact code IDs are validated. Missing, malformed and duplicated answers remain unresolved; an assertion without a matching body quotation is downgraded.
- `screen=shortlist` returns every bounded candidate through the existing API model, independently of legacy `top_k` and `verify_n`. Optional Elephant reranking cannot discard candidates on failure. Selector failure produces an explicit bounded keyword fallback. No historical or injected calibration can enable automatic commitment for this experiment.
- `question_style=self` opts Elephant into the measured self-contained question format. Default shared payloads, default settings, historical configuration hashes and transport protections remain unchanged. New settings bind changed prompts and policies into new hashes.
- The benchmark records attempted cases and failures, separates conditional verifier diagnostics from retrieval, filters connected duplicate/source/rewrite groups, binds deterministic caches to DB/WAL identity, and supports offline report/replay. Live calls require an explicit context. Durable reservations, uncertain-usage holds, UTC-day quota reconciliation and process-safe cache claims protect the experimental budgets.
- Research includes 64 Alberta and 62 Canadian records. All 350 saved mapping titles/quotes were matched to the private corpus; 18 primary sources were reopened independently. The Calgary clearance qualifier was corrected, and the Saskatchewan-only detector substitution is isolated as a foreign-topic diagnostic. [Source audit](source-audit.md) records the original input hashes, limitations and parent dispositions.

## Exact-engine measurement

[Machine-readable result](../../../evals_dev/identify_bench/results/engine_shortlist_heldout.json) contains all 72 selected IDs and all 72 records. Configuration: TOC 40, pool 60, medium-effort text reviewer, optional Elephant disabled for the multi-case panel. The application engine runs directly with explicit benchmark transports; no app server or case database is used. No reference answer is inserted into a provider prompt. The engine source digest matched before and after the live run. A final cache-only replay under the repaired evaluator returned identical predictions for all 72 cases, with matching WAL-aware corpus fingerprints. Original live captures are retained beside the final replay artifacts; the original captures did not record a WAL-aware before/after pair and are marked accordingly.

The 50 positive cases comprise 15 Alberta records, 23 other Canadian/product records, nine authored development cases and three older Alberta precedent summaries. The full 239-record universe is used when constructing connected leakage groups. There is no known group overlap with tuning; source grouping does not prove independent real-world sampling or exhaustive expert annotation.

| Measured output | Result |
| --- | --- |
| All reference articles in returned 60-candidate response | 46/50 cases, 92% |
| Reference-article recall | 93/97 occurrences, 95.9% |
| Same responses truncated to first ten | 39/50 complete cases, 78% |
| Tentative model picks alone | 36/50 complete cases; 80/97 reference occurrences |
| Mean tentative model picks | 7.1/case |
| Reference/context overlap precision lower bound | 28.1%; extra picks were not exhaustively adjudicated |
| Ambiguous-input branch coverage, separate diagnostic | 14/18 cases, 27/33 branch references |
| Out-of-scope direct calls, separate diagnostic | 4/4 still produced model picks |
| Operational provider errors / invalid returned IDs / invalid verifier quotes | 0 / 0 / 0 |
| Automatic article commitments | 0 |
| Token-price usage estimate | $1.141818; not an account billing receipt |

The out-of-scope result is a substantive limitation: this component cannot serve as the application's intake scope gate. Operational success is not semantic accuracy. Literal citation/quotation validity does not establish applicability.

Four positive-case omissions remain:

| Case | Missing current article |
| --- | --- |
| `ca-bcab-1887-secondary-suite-separation-attic` | `9.10.5.1.` — Permitted Openings in Wall and Ceiling Membranes |
| `ca-bcab-2002-loft-in-vaulted-unit` | `9.8.2.1.` — Stair Width |
| `ca-ccmc-composite-decking-and-stair-treads` | `9.23.15.5.` — Subfloor Thickness or Rating |
| `ca-ccmc-pvc-footing-form-and-drain` | `4.1.1.3.` — Design Requirements |

These outcomes were not used to retune the frozen candidate. Another development iteration needs a fresh independent evaluation set and expert review of incomplete or cross-edition reference sets.

## Live optional-scorer integration

[One-case integration result](../../../evals_dev/identify_bench/results/engine_elephant_smoke.json): authoritative TOC selection → five serial self-contained Elephant requests covering all 60 pool articles → full-body text review → 60 returned tentative articles. Every reference was returned, both reported model identities were recorded, and no article was automatically committed. Response pin: `baseten/elephant-1-20261021`; reported Elephant price zero. This one case is an integration smoke and overlaps the larger panel, not a new independent accuracy sample.

A fresh transport-only smoke also accepted the exact pin. The account's allowance was 50/day; after the recovered 42 scoring calls, one resumed transport request and five integration requests, only two free scoring slots remained. No credits were purchased or account settings changed. A read-only closing quota query confirmed 48 used of 50, with two remaining. The cumulative experimental ledger estimate was $4.966710, below its $6 cap; this is not an account billing receipt. The local admission/TLS/deadline/no-retry controls were retained; measured bytes/token ratios were not promoted to a universal tokenizer bound.

## Earlier experiments and their limits

- Paired 20-case, 40-article **answer-injected ranker diagnostic**: shared-list AUC .912 → self-contained .948; complete top-ten reference coverage 16/20 → 19/20. These figures do not measure candidate recall.
- The verifier's 57-development/34-test diagnostic retained every in-pool reference at the applies/check boundary, but answers had been inserted into the pool. Reversing order changed around 22% of labels. This cannot justify guaranteed applicability labels.
- The earlier 57-record TOC/V3 hybrid snapshot found complete pools in 52/57 cases. Its original format lacks an attempt manifest, so the repaired reporter marks its headline provisional.
- Cached development-only ablations: TOC40 alone 49/57; fast BM25 union 50/57; bounded graph expansion 51/57; generated lexical facets reached 53/57 with a 100-article pool. More output is an extra review burden. These experiments did not produce a calibrated production threshold.
- [Methods research](methods.md) links the primary papers and explains statistical assumptions and the distinction between retrieval, conditional verification and final response recall.

## Verification and review

Parent ran `scripts/verify.sh` in this worktree:

```text
web typecheck: passed
web unit tests: 384 passed, 0 failed
web unwrap test: passed
web production build and generated-type check: passed
no SQLite database in web output: passed
Python engine/codedb/evals_dev: 2809 passed, 511 skipped in 358.46s
```

The worktree initially lacked an ignored intent-source text file. A private local copy was supplied from the existing source before final verification; the previously failing numerical-content test then passed. The canonical source/database was not modified. Environment-dependent skips include real PostgreSQL paths; they are not provider, database-persistence or production proof.

After benchmark review fixes, the entire benchmark subtree passed:

```text
192 passed in 7.93s
```

`engine.schema_export --check` and whitespace checks passed. The engine source remained identical to the independently reviewed snapshot; no generated API-model edits were needed.

The independent engine reviewer found no actionable defects and separately exercised an in-memory endpoint → serialized CAS → GET round trip preserving 60 candidates, existing selected provisions and relevance, with no GET scoring and repeated-IP rejection before dispatch. That evidence is synthetic; real PostgreSQL persistence, SSE/browser delivery and production were not exercised.

The first benchmark review found four issues: absent usage becoming free spend, per-object Elephant quota reserve, Unicode JSONL separators, and the candidate CLI's ineffective live flag. Regression fixes retain uncertain spend reservations, split cache records on LF bytes and enter the explicit live context. Quota accounting now retains each ambiguous local hold on its admission/start UTC dates and the following UTC day; conservative under-use is deliberate because aggregate remote counters cannot prove acknowledgement or bound reservation-save latency. Failed provider usage is retained in engine records, and corpus/WAL drift invalidates a headline. Admission is rechecked before dispatch across UTC midnight, and bounded cross-day request holds remain reserved. Synthetic subprocess tests include concurrency and crash recovery.

The final independent quota review reported no findings. It repeated 103 focused checks plus 17 additional calendar/legacy checks; the original UTC reproduction now permits eight dispatches and preserves four of twelve quota slots.

The standard script reported that `gitleaks` is unavailable, so that scanner was skipped. A separate staged-content check compared both configured provider credential values against all 58 staged files and found zero matches. This check is narrower than a general secret scanner.

## Integration gates

1. **UI review of the full pool is unfinished.** `web/src/intakeView.ts:identifyCandidates` presents at most three quoted choices. The remainder does not become a reviewed checklist merely because it exists in `IdentifyResult.articles`; the library uses separately stored exhaustive relevance. The 92% figure belongs to the engine API response, not the applicant's rendered journey. Update the UI flow and its exhaustive-screen wording, then exercise it before enabling this mode for users.
2. Keep labels tentative, preserve the acceptable/alternative-solution intake fork and collect missing facts. All four direct out-of-scope inputs produced suggestions; preserve or strengthen the separate intake boundary rather than treating this selector as one.
3. Obtain expert-adjudicated complete reference sets, especially supporting/general articles and older-edition mappings. Keep the 47-reference secondary-suite checklist and foreign provincial substitutions separate. Do not fit guaranteed/definitely-does-not-apply bands from these samples.
4. For local API evaluation, use the documented opt-in configuration; `rerank=none` permits testing the text path without exhausting free scorer quota. Defaults remain unchanged. Apply the local commit in the integrating worktree, supply its private corpus/environment inputs, and re-run `scripts/verify.sh`; server start and any dev landing require the integrating task's authorization.

This work is backend/research scope. The user prohibited new application servers and ports, so no browser screenshot or working UI recording was captured. No deployment or professional approval is implied.

Methods applied: Matt Pocock research, codebase-design, diagnosing-bugs/TDD and code-review; pstack feature, bug-fix and benchmark-checklist; T3 workflow/orchestration; Batatis hackathon and variance-workflow contracts. Method paths and the actual worker receipts were checked; all resumed delegates used GPT-6.1-Sol at max, with priority service after the user's Fast-mode request.
