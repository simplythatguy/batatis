# Selected workflow and evaluation findings

The selected workflow uses **GPT-6 Luna at medium effort for extraction, document review and full-text verification, and Jev 1.13.0 for article screening and reranking**. The original Luna review prompt is retained. The user ended further benchmarking after the last running comparison and requested this configuration be locked in.

This is the best-supported choice from the completed Luna results and the requested Jev provider configuration. **The final combined Luna + Jev workflow has not received a complete, reliable accuracy evaluation. No result establishes greater than 97% accuracy.** The later correctness repairs have regression coverage, rather than a new accuracy score, because further benchmarks were stopped.

## What is selected

The checked-in [pipeline profile](../../engine/identify/pipeline.json) resolves to configuration hash `5f1c92331550984a`.

| Stage | Selected behavior | Reason and limit |
| --- | --- | --- |
| Initial intake | Deterministic field/form reading, followed by Luna medium for facts the rules missed | Preserve exact source values and distinguish proposed facts from confirmed facts. |
| Document review | Luna medium, original review prompt, readable attachment pages and request | This is the prompt used by the strongest completed Luna checkpoint. Its SHA-256 is `4a29a9bd45488d5d531b9cfaa6c5d37cab285c3576b6fb63a27743611b3054d0`. It matches commit `437e0f55`. |
| Article screen | Jev 1.13.0; all 2,080 current Division B articles; 700-character cards | Broad candidate coverage before narrowing. This is relevance scoring, not a compliance decision. |
| Article rerank | Jev 1.13.0; top 60 candidates | Recheck the candidate set before the more expensive full-text stage. |
| Full-text verification | Luna medium; top 15 candidates | Require a quote from the actual article text. Return up to 10 article cards and 3 choices. |
| Unavailable identification | Labelled BM25 fallback | Availability failure remains visible; fallback does not establish successful model execution. |
| Section C and completeness | Deterministic code-database lookup and administrative checks | Objective/function/intent lookup follows article identification. Applicant/professional evidence and approval remain human-owned. |

The model pins come from the existing provider registry. The profile omits redundant model fields so an explicit alternate-provider configuration can resolve its own correct pin. The [workflow contract test](../../engine/tests/test_workflow_profile.py) independently asserts the resolved Luna/Jev versions, efforts and limits. This also catches a later model upgrade that silently changes the selected workflow.

Explicit configuration overrides remain supported. Provider-specific regression fixtures now select their provider explicitly, rather than depending on the former Elephant default. No new automatic-commit threshold or calibration was introduced. The existing uncalibrated policy continues to require user confirmation.

## How the workflow handles evidence

The intake service reads source material, finds personal values, and scrubs outbound text. Document review receives the intended workflow instructions, schema, redacted request and attachments. Evaluation answer keys, scores, repository instructions, agent tools and conversation history are excluded from these inference requests.

Luna proposes facts, conflicts, cited provisions, missing evidence and questions. Deterministic checks verify excerpts against the named source, preserve numeric-token boundaries, distinguish independent assertions, and resolve code references against CodeDB. A source quotation is evidence of what that source says; it does not establish technical correctness or approval.

Identification currently uses the intake description and extracted case facts. The richer document-review result is stored separately. A reviewed fact is therefore not automatically guaranteed to reach relevance scoring. The earlier prose-to-identification experiment was incomplete and unscored; its proposed handoff should be investigated before adoption.

Runtime anchors: [intake service](../../engine/intake/service.py), [document review and checks](../../engine/intake/review.py), [identify configuration](../../engine/identify/config.py), [identify pipeline](../../engine/identify/pipeline.py), and [evaluation forwarding](../../evals_dev/data_prompts/sut.py).

## What the saved results support

Accuracy is the fraction of reference checks passed: source facts (F), review points (R), boundaries (B), and named articles (A). It is not the fraction of requests that returned an answer. Compound reference items require all their parts. Operational completion and other guards are reported separately.

The original split contains 334 development cases and 319 holdout cases. The historical development metric contains 2,981 applicable checks. Availability filtering excludes 212 other development facts; image-only facts are outside that historical text metric. This is not complete visual-document accuracy.

The branch also repairs five malformed evaluation files in commit `8dbf2760`, before its harness implementation. Four review-point arrays had split a sentence into individual characters; the fifth stored a single string instead of a list. An audit reconstructed every contiguous character sequence and confirmed that all five repairs preserve the original wording exactly. The evidence snapshot records the before/after hashes and counts without copying answer text. These are data-shape repairs, not relaxed reference requirements; the missing historical manifests still limit reconstruction of old runs.

| Saved result | Cases | Passed / applicable checks | Reported accuracy | Judge |
| --- | ---: | ---: | ---: | --- |
| Initial development workflow | 334 | 597 / 2,981 | 20.03% | Sol low |
| Initial holdout, aggregate only | 319 | 589 / 2,851 | 20.66% | Sol low |
| Luna document-review checkpoint | 334 | 2,308 / 2,981 | 77.42% | Sol low |
| Luna review, matched development subset | 99 | 711 / 850 | 83.65% | DeepSeek max |
| DeepSeek review, same matched subset | 99 | 707 / 850 | 83.18% | DeepSeek max |

These historical results precede the integrity repairs described below and lack fully verified frozen-run provenance. They are retained as historical evidence, rather than relabelled as final-source results. The 77.42% and 83.65% figures have different judges and workloads and cannot be read as an improvement between those runs.

The matched comparison did not establish an advantage for DeepSeek review: its observed difference from Luna was -0.47 percentage points, with an exploratory source-group interval of approximately -3.63 to +2.32 points. The saved Jev runs `it5-jev` and `it6-prose-jev` have incomplete outputs and no completed scores. They establish configuration provenance, not a higher measured combined accuracy. This is the remaining evidence gap behind the selected Luna + Jev combination.

The portable [aggregate evidence snapshot](workflow-accuracy-evidence-20261025.json) includes original artifact paths, hashes, denominators, guards, costs and the selected configuration. It contains no attachment text or credentials. The original local experiment folders remain the detailed record.

## The last comparisons and the stopping decision

The last 14-case prompt comparison used independent development source components, the same redacted inputs, DeepSeek Flash at max in both arms, the same checker and `judge-v7-strict`, and explicitly configured keyword identification. It tested review behavior, not the complete live Luna + Jev product workflow.

| Review prompt | Passed / expected checks | Accuracy | Review completion |
| --- | ---: | ---: | ---: |
| Original | 89 / 130 | 68.46% | 13 / 14 |
| Proposed v3 | 91 / 130 | 70.00% | 13 / 14 |

The exploratory source-group interval for the difference was -13.33 to +15.17 percentage points. This small experiment did not establish an improvement. One review failed in each arm; two additional v3 cases contained invalid/unverified judge evidence. All expected checks stayed in the denominator. The original Luna prompt remains selected.

An initial setup accidentally attempted disabled identification before keyword fallback. The completion gate correctly rejected it. That artifact was preserved, and a separately named run explicitly selected BM25/no rerank/no verifier, replaying all 28 review outputs with zero fresh inference calls. It was not repaired by deleting failed cases or suppressing the completion guard.

The context audit verified 28 intended inputs, 14 equal request/schema pairs and 32 captured live requests. It found no additional agent or evaluation context in the submitted API bodies. Normal Codex Luna agent access was available, but the exposed T3 route injected orchestration/workspace context; those agent completions were excluded from accuracy evidence.

The already-dispatched four-case Responses-schema pilot was also completed after the stop instruction; its expansion never started. Responses passed 28/29 checks, versus Chat's 24/29, but this is **four development cases, not a 97% workflow result**. The v3 Chat arm produced the same per-case improvement, and Responses had one more rejected first attempt and a capped retry. The protocol hypothesis was rejected and its implementation remains an external experiment. Neither DeepSeek nor Responses replaces Luna in the selected product profile.

## Findings and lessons

### Generation coverage is the largest unresolved accuracy mechanism

Source-backed document review accompanied the largest saved improvement. A later offline replay of 94 valid cached completions found 3,126 raw facts; the earlier checker retained 3,069 and the stricter checker 2,998. A lexical inspection of prior failed fact checks suggested that many facts were absent before checking. That diagnosis is not a semantic accuracy score, but it argues against trying to recover most missing information by weakening evidence validation.

The last comparison likewise passed only 27/51 and 30/51 fact checks, versus 15/16 boundary checks in both arms. More generated facts alone did not establish better overall coverage. Future work should test bounded source coverage and compact atomic extraction, with identical inputs and a frozen evaluator.

### Evidence normalization can change meaning

Review found numeric fragments borrowing digits from decimals/grouped values, incomplete nested citations, overlapping excerpts being treated as independent conflicts, and line boundaries disappearing between genuinely different values. These paths now have regression coverage.

The final normalization repair applies Unicode and punctuation normalization consistently before locating row boundaries. It distinguishes punctuation dashes from genuine word wrapping. It also preserves line-wrapped numeric ranges: `25-` followed by `30` must not become an invented value `2530`. This is a general source-integrity rule, not a corpus-specific exception.

### Privacy and restoration require source identity

Conflicting personal candidates, short personal values and later-page values must be scrubbed too. Attachment names are pseudonymized. Restoration must abstain when a placeholder cannot be uniquely anchored to the original source; a known person's name cannot be assigned to an unresolved quotation. Verified source evidence survives a rejected model restatement through neutral fallback text.

### Passing a lexical guard is limited evidence

Repairs distinguish attribution, requirements, negation, independent clauses and shared-subject questions. Compound questions remain questions. However, a separate synthetic probe found ordinary unqualified assertions such as “Structural safety is assured” that escaped both the production filter and the independent lexical harness detector.

This remains a known limitation. Repeated wording-specific fixes do not establish comprehensive semantic protection. Future structural or semantic approaches must be evaluated independently, while preserving the distinction between an attributed source position, a request for professional evidence and Batatis's own conclusion. Guard pass rates must not be described as safety or compliance certification.

### Measurement integrity mattered as much as prompt changes

The investigation repaired missing outputs and judge failures disappearing from denominators, reuse of incompatible configurations, incomplete stage-success checks, lenient verdict types and missing verdicts, stale judge caches, truncated JSON acceptance, and cost double counting.

The harness now freezes relevant source/configuration identities, retains all expected checks, records dispatch attempts and unknown costs, preserves original cache pricing, and carries case accounting into worker threads. Partial intake failure remains an operational failure even when another source succeeded. Unread images remain a capability/readability limitation rather than automatically erasing every otherwise applicable check.

Changing the judge or its validation changes the measurement. A higher score under another judge is not evidence of workflow improvement. Named-article references are incomplete positives, so their apparent precision cannot justify an automatic commit threshold.

## Costs and practical limits

The last 14-case Chat comparison recorded workflow estimates of $0.4655 and $0.4969 for its two arms. Replaying those reviews added no fresh inference spend. Judging added known subtotals of $0.101448 and $0.127168, plus four unknown-cost transport attempts. The four-case Responses pilot added $0.165191 with no unknown attempts. These are provider-call estimates, separate from engineering-agent usage, and not a cumulative bill.

Exact historic cumulative spend is unrecoverable because earlier retries/caches overwrote records and some failures lacked usage. Unknown costs remain unknown. The laptop entered low-power sleep during judging; interrupted elapsed times must not be used as provider latency evidence. The schema pilot also showed that apparently equivalent JSON serialization can differ at the wire, and provider-reported token counts may include protocol overhead.

The content harness bypasses the hosted upload limit and does not verify authentication, persistence, applicant follow-up, browser behavior or export. Many historical identification runs used fallback. The DeepSeek comparison transport's limits also differ from the product's request deadline. None of these content scores establishes complete production acceptance.

## Verification at lock-in

The integrated workflow passed **3,581 tests across the engine, CodeDB and evaluation tools, with 607 prerequisite-dependent tests skipped** (`scripts/verify.sh --engine`). Web typechecking, unit checks, unwrap checks and production build passed on the identical integrated implementation. The separate accounting/evaluation harness suite passed **91 tests**. The optional secrets scan did not run because `gitleaks` is not installed.

Independent scoped review found no additional actionable findings, with 388 focused offline tests and 16 synthetic checks. The later provider-fixture corrections were verified by the complete local run. Integration with main `8e1a497f` also passed an independent 30-check review with no additional findings. The shared PDFium lock covers the new review reader, and main’s issued/withdrawn-question behavior is retained. Ignored reference assets were restored locally before the final engine run; they are not published. This is nonvisual engine/tooling verification with simulated provider responses; it is not fresh model accuracy, a browser journey, a real-provider acceptance test or production approval.

## What to test or improve next

This is a prioritized backlog, **not an instruction to resume benchmarking automatically**.

1. **Close known evidence and semantic boundaries first.** Independently review the final source normalization, restoration and claim behavior. Evaluate a structural or semantic alternative to the lexical claim filter against both unsafe assertions and valid source attribution/questions. Keep professional decisions human-owned.
2. **Verify the actual product journey.** Exercise the selected Luna + Jev path through upload, readable/unreadable pages, source redaction, review-to-identification handoff, case persistence, follow-up and export. Include upload limits, shared PDF-reader concurrency, deadlines, retry reservations and missing usage.
3. **When accuracy testing is reopened, measure this exact combined profile.** Freeze code, prompts, provider pins, all checks and group membership. Group related reports about the same project; attachment hashes alone do not establish independence. Run development first, then a protected holdout without tuning against holdout errors. Preserve all failures and distinguish content accuracy from operational success.
4. **Validate the dataset and judge independently.** Reject malformed evaluation shapes, including character arrays, before scoring. Use expert-adjudicated positive, partial, contradicted and prohibited answers, including compound requirements. Measure false credits and false rejections. A report that merely copies a reference instruction is not necessarily a valid oracle answer.
5. **Investigate missing source coverage.** Test bounded source chunks/atomic facts and the reviewed-facts handoff as separate changes. Compare against the selected prompt without adding gold hints, example answers or case-specific rules.
6. **Tune cost and latency only after correctness.** Measure reasoning/output caps and real end-to-end deadlines under matched conditions, with complete attempt accounting. Do not adopt an uncalibrated relevance or auto-commit threshold from incomplete article labels.

No further benchmark schedule is enabled for this task. The one-time Opus continuation ran once and its timer is disabled. Further accuracy testing is a future decision, rather than an automatic continuation of this work.

## Investigation scope

This record draws on saved aggregate artifacts, the current source and Git history, exact request captures, offline reproductions, independent engine/harness reviews, the final prompt comparison and the bounded protocol pilot. It does not claim an organization-wide search or independent professional assessment. It uses T3 workflow routing, pstack's benchmark checklist, attack-the-premise and why methods, and Matt Pocock's debugging/code-review methods, adapted to the authorized repository and thread scope.
