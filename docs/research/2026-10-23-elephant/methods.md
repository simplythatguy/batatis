# Article retrieval and honest uncertainty: methods and evidence

Research for Batatis, 2026-10-23. This replaces the unfinished literature draft with a concise, auditable synthesis. The task is administrative completeness of an NBC(AE) 2023, second-printing application. Neither an article match nor a checked quotation determines technical correctness, equivalence, safety or approval.

## 1. What the measurements establish

The benchmark separates three questions:

1. **Candidate recall:** did retrieval find every reference article, without reading the answers?
2. **Conditional verification:** if the reference articles are already in the pool, does the verifier retain them?
3. **Delivered recall:** did every reference article survive ranking, labeling, response limits and the applicant-facing boundary?

The original Elephant and verifier diagnostics inserted the known reference articles into their pools. Those experiments can compare rankers or measure conditional verification; they cannot establish candidate or application accuracy. The end-to-end experiment does not insert answers. Its saved 57-case development/precedent run surfaced every reference article in **52/57 cases**, with six missing article occurrences across five cases. Its 100% conditional-verifier result must never be substituted for that result.

The reference sets are minimum cited-article sets, not exhaustive expert annotations. An extra predicted article is not automatically wrong, so overlap precision is explicitly a lower bound. Conversely, matching every reference does not prove that all actually applicable articles were found. Ambiguous intake branches, out-of-scope requests and whole-topic checklists need separate evaluation rather than disappearing from denominators.

## 2. Provider guidance and the tested hypothesis

[TypeSafe Noul documentation](https://docs.typesafe.ai/primitives/noul.md), fetched directly on resumption, describes a yes/no decision with optional true/false criteria. Its construction guidance favors one clear judgment per question and placing the candidate's content directly in that question rather than requiring a lookup in a shared candidate list. This motivates the tested question format; it is not proof of building-code accuracy.

The paired experiment kept the same 20 diagnostic pools, each containing 40 articles. Shared-list prompting gave mean AUC 0.912; a self-contained question containing the article card gave 0.948. Complete reference coverage in the first ten positions rose from 16/20 to 19/20. Both samples are small, answer-injected diagnostics. No applicability threshold was fitted from them. See the two `elephant_*_40_tune.json` artifacts for per-case results.

The [Elephant model card](https://huggingface.co/baselabs/elephant-1/raw/main/README.md) identifies a decision model built from Qwen3.5-9B. Its model-level calibration claims do not establish calibration on Alberta variance applications. The app independently validates the exact response pin, shape, finite probabilities, complete answer set and zero reported price.

[OpenRouter's limits documentation](https://openrouter.ai/docs/api_reference/limits) describes account-dependent free-model daily allowances and a key endpoint that reports current quota. The account reported 42/50 used before the resumed smoke. One fresh transport request then succeeded with the exact `baseten/elephant-1-20261021` response pin and reported cost zero. That smoke checks transport acceptance only. The public model catalog did not list Elephant during the same investigation, so catalog visibility is not used to infer route availability or future continuity. The earlier draft recorded a free-week end date from a model-page snapshot; that page could not be independently reopened on resumption, so no future availability is promised here.

Forty-card diagnostic requests fit the provider's context despite exceeding the app's deliberately conservative byte admission policy. Measured bytes/token ratios do not provide a universal upper bound for new inputs, especially different scripts or unusual text. Therefore production's existing admission, no-truncation, TLS, deadline, response-pin and no-retry controls are retained. The larger-packing probe remains benchmark-only.

## 3. Research that informs the workflow

These are primary research sources. Descriptions below distinguish what the papers studied from the proposed Batatis adaptation; the reported improvements are not imported as Batatis results.

| Source | Finding relevant to the task | Batatis experiment or boundary |
| --- | --- | --- |
| [Aqib et al., 2025, Building-code QA](https://arxiv.org/abs/2505.04666) | Evaluates retrieval and model adaptation on Canada's national building code; retrieval choice materially affects answers. | Keep an authoritative lexical baseline. A QA benchmark does not establish complete variance-article recall. Abstract checked on resumption. |
| [Louis et al., 2023, Finding the Law](https://arxiv.org/abs/2301.12847) | Statutory articles depend on the structure of legislation; graph-augmented retrieval improves their studied dataset. | Test explicit article-reference and subsection expansion. This local deterministic graph is not the paper's trained graph neural network. Abstract checked. |
| [Gao et al., 2022, HyDE](https://arxiv.org/abs/2212.10496) | Uses a generated hypothetical document as input to a dense retriever, grounding the result in real documents. | Test generated code-vocabulary facets with corpus retrieval. Our BM25 expansion is inspired by this idea but is not a reproduction of dense HyDE. Abstract checked. |
| [Liu et al., 2023, Lost in the Middle](https://arxiv.org/abs/2307.03172) | Relevant information's position can change long-context model performance. | Test reversed article order and separate title screening from full-text reads. Larger context alone is not a completeness guarantee. Abstract checked. |
| [Dhuliawala et al., 2023, Chain-of-Verification](https://arxiv.org/abs/2309.11495) | Independent verification questions reduce hallucinations on the authors' tasks. | Check literal quotations deterministically and evaluate a second semantic pass separately. A second model agreeing is not independent professional ground truth. Abstract checked. |
| [Angelopoulos et al., Conformal Risk Control](https://arxiv.org/html/2208.02814v4) | Calibrates bounded monotone losses on a separate sample, including false-negative loss; statistical statements concern the defined loss and sampling assumptions. | Freeze the pipeline and define case-level omissions before calibration. A marginal risk statement is not certainty for a particular application. Full introduction and algorithm checked. |

The earlier investigation also linked legal retrieval, query expansion, rank fusion, relevance judging and selective prediction literature. No unverified paper-specific result is needed to select the candidate shipped in this worktree. The experiments below test mechanisms directly on the available cases.

## 4. Workflow alternatives and decision rules

**Exhaustive decision screening.** Every Division B article receives a score. This avoids a lexical retrieval cutoff but does not ensure that the scores or labels are correct. The app's offline packing measurement needs about 131 screening calls plus reranking for one short input; that exceeds this account's 50/day allowance. No completed exhaustive live baseline is claimed.

**TOC screening plus lexical union.** Read the full authoritative table of contents once, validate every returned identifier, and combine the list with corpus search. This reduces provider requests while keeping a deterministic second retrieval channel. Its candidate cap can still omit a required article. Invalid or absent identifiers must be recorded, never repaired by guessing article numbers.

**Reference expansion.** Follow explicit article references and optionally complete nearby subsections. These links retrieve supporting rules that an applicant may not name. Unbounded expansion quickly becomes a large general checklist; caps, source provenance and returned list size must be reported. Tune-only graph experiments plateaued below complete recall in this task.

**Generated query facets.** Generate search vocabulary for the design's different elements, retrieve real articles for each, and fuse their rankings. Hypothetical prose is never legal evidence or a citation source. Cached tune experiments improve some misses only with a materially larger candidate pool, so the extra burden must be measured.

**Full-pool review.** Read every shortlisted article, rather than only the first fifteen. A missing or malformed model row becomes unresolved; an asserted application without a matching quotation is downgraded. Every response limit matters: returning only ten of sixty internally retained candidates cannot inherit the sixty-candidate recall figure.

**Independent review and abstention.** Use unresolved facts to ask the applicant a specific question. Preserve the distinction between model suggestions and an officer's review. A low score, an omitted title or an unavailable provider does not mean the article definitely does not apply.

## 5. What a statistical claim would require

Define the loss as one when a case has any reference article missing from the final surfaced set, zero otherwise. Freeze candidate generation, prompts, model pins, ordering, caps and failure behavior before using a separate calibration set. Group reissued precedents and rewritten scenarios across folds; a hash split by itself does not prevent this leakage.

A simple uncertainty calculation is useful even before conformal calibration. With zero omissions in n independent representative cases, the one-sided 95% binomial upper bound on omission probability is `1 - 0.05**(1/n)`. Thus zero omissions in 34 cases still allows roughly an 8.4% underlying omission rate. Around 299 independent zero-omission cases are needed for that bound to fall below 1%; no finite sample establishes a zero rate. These calculations are not valid evidence when cases are duplicated, cherry-picked, or conditional on answer-containing pools.

Case-level split-conformal prediction can instead calibrate the minimum reference-article score across each calibration case. Its coverage concerns a new exchangeable case under the frozen procedure. It neither repairs incomplete expert annotations nor supplies pointwise certainty for a particular building. If retrieval never scores an omitted article, a useful threshold may not exist without enlarging the returned set. The committed metric helper is experimental; no production threshold is fitted or promoted here.

## 6. Evaluation and promotion requirements

Record the exact corpus digest, case IDs, duplicate-group policy, configuration and requested/returned model pins. Keep diagnostic, tuning and held-out results distinct. Persist every attempted case, including transport, parsing and quota failures. Headline complete recall uses all attempted eligible cases; successful-only results are conditional diagnostics.

Report complete-case recall, article recall, mean returned list size, reference-overlap precision with its limitation, missing facts, invalid identifiers, quotation downgrades, provider failures, calls and actual billed-token usage. Do not treat replay wall time as live latency or an input-token price estimate as an account billing receipt.

A request cache must bind the complete request; a deterministic corpus cache must also bind the corpus digest and recipe. Offline report commands must not dispatch providers. Concurrent paid calls need reservations or serialization before dispatch, and uncertain failed-call cost must not become free budget. Credentials stay in process memory; neither cache entries nor errors should contain them.

The engine candidate remains opt-in. Historical scoring paths, their calibration identities, and the existing uncalibrated relevance presentation remain intact. Automatic article commitment is disabled for the candidate regardless of a supplied historical policy. Any future promotion needs an independent review of the exact final response boundary and fresh expert-adjudicated held-out cases. No automatic guaranteed/definitely-does-not-apply label is supported by the present evidence.

Methods applied: Matt Pocock research; pstack benchmark-checklist; Batatis hackathon and variance-workflow domain contracts. See the integration handoff for final checks, live measurements and remaining limitations.
