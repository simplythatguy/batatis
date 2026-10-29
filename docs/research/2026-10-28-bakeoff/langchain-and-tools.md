# Would LangChain or another tool make Batatis measurably better?

Research memo, 2026-10-28. Written for the demo on 2026-10-29. Read-only research. No product code was changed and no paid model API was called.

## Bottom line

No. Do not add LangChain, LangGraph, LangSmith or Deep Agents before the demo. Batatis has no agent loop for them to improve. Its accuracy comes from deterministic steps: the production code search runs with zero model calls (`engine/identify/pipeline.json` sets `"screen": "requirements"`), Section C is a lookup, and every model quote is checked against CodeDB text before anyone sees it. LangChain's own docs recommend LangGraph when you need to "mix deterministic steps with LLM-driven agentic steps". Batatis already does that in about 100 lines of plain Python per call site. Adding the stack would add about 42 MB of packages and about 0.4 to 0.7 seconds of import time on a cold start, and it would not move any metric we measure. The one Claude-native idea worth borrowing is from the Citations feature: let the model point at numbered sentences instead of retyping quotes. Then a fabricated quote cannot happen by construction. The API feature cannot be tested tonight without an API key, but the same idea runs through T3 tasks (experiment T1, optional). The most useful thing to run tonight needs no new tool: score the production search on the 53 public STANDATA cases already in the repo (experiment T0, zero model calls). That gives judges a second number from real regulator documents.

## Verdicts

| Tool | Batatis part it touches | Verdict | Main reason |
|---|---|---|---|
| LangChain v1 (`create_agent`, middleware, structured output) | LLM call sites in intake, review, assistant | No | No agent loop exists. Native structured output is already used on both providers. |
| LangChain retrieval and integrations (loaders, retrievers, rerankers) | Code search, PDF reading | No | SQLite FTS5 BM25 with tuned variants and a reference graph already exists. The BM25 and ensemble retriever pages are no longer in the docs. |
| LangGraph (graph and functional APIs, persistence, interrupts, durable execution, streaming) | Question flow, jobs | Later, only if long background jobs grow | The question planner and path choice are deterministic. The case store already persists state. |
| LangSmith tracing | All model calls | Later | Sends case text to a hosted service. The app has its own redaction and spend ledger. |
| LangSmith datasets, experiments, pairwise, annotation queues | Evals | Later (annotation queues are the useful part) | Useful after the hackathon to collect officer labels. Not needed for tonight. |
| LangSmith prompt hub | Prompts | No | Prompts are pinned in code and hashed into `config_hash`. A remote prompt store breaks that. |
| Deep Agents and Managed Deep Agents | None | No | Planning, filesystem and subagents are the opposite of the deterministic design. |
| DSPy (GEPA, MIPROv2) | Verifier and intake prompts | Later | A light GEPA run on 100 examples is about 1,300 metric calls. Our T3 path is one task per call. |
| Pydantic AI (and Pydantic Evals) | LLM call sites | No | Would replace small working transports. No accuracy gain. |
| Instructor | LLM call sites | No | Native structured output already covers it. |
| LlamaIndex | Code search | No | Same as LangChain retrieval. |
| Inspect AI | Evals | Later | Good log viewer for a public eval. Not needed tonight. |
| promptfoo | Evals | Later | Its `echo` provider can grade saved outputs with zero model calls and show a web report. |
| Ragas | Evals | No | Its RAG metrics are model-judged. Our exact-substring checks are stricter. |
| Braintrust | Evals | Later | Hosted, same role as LangSmith. |
| Claude structured outputs | Verifier (Claude arm) | Keep (already used) | `engine/identify/verify.py:112` already uses it. |
| Claude Citations | Verifier quotes | Later for the API. Test tonight as a prompt pattern (T1). | API guarantees valid pointers to the source. It cannot be combined with structured outputs. |
| Claude prompt caching | Assistant | Later | One top-level field. Saves cents at Haiku 5.5 prices. Cannot be verified tonight without an API call. |
| Claude Message Batches | Evals | Later | 50% cheaper eval runs, but needs an API key. |
| Claude Files API | None | No | Batatis sends text it has already extracted. |
| Claude PDF input | Intake of scanned plans | Later | Could read drawings that `pypdf` cannot. Needs its own test on Data Prompts files. |
| Claude Agent SDK | Product: none. Evals: T3 already uses it. | No for the product | Agent harness. Batatis does not need one at runtime. |
| ObliQA, RePASs, AECBench, NBCC QA paper | Proof of accuracy | Later | Methods to borrow. None is an Alberta code dataset with gold article numbers. |
| STANDATA public benchmark (in repo) | Proof of accuracy | Test tonight (T0) | 53 regulator cases with gold article numbers. Runs with no model calls. |

## What Batatis does now (checked in code at `95bf3d5e`)

The brief is partly stale. These facts were checked in the code:

- Code identification in production makes no model calls. `engine/identify/pipeline.json` sets `"screen": "requirements"`. `engine/identify/requirements.py` says "Zero-provider requirement discovery over the verified NBC(AE) 2023 p2 source." The Jev screen, Jev rerank and LLM verifier are kept as configurable benchmark arms (`engine/identify/pipeline.py`, docstring lines 1 to 17).
- `IdentifyConfig` refuses any model id that contains "haiku" (`engine/identify/config.py`, the `'Haiku models are not used'` check). `OpenAIVerifier` refuses it too (`engine/identify/llm.py:66`). A Haiku verifier arm must run through the eval harness, as the 17-case run in the README did, not through `pipeline.json`.
- Intake's model pass still pins GPT-6 Luna at medium effort over Chat Completions with a strict JSON schema (`engine/intake/model.py:24` to `25`, `engine/intake/model.py:253`). Document review also uses Luna (`engine/intake/review.py:45`).
- Claude Haiku 5.5 is the assistant's model only when `ANTHROPIC_API_KEY` is set (`engine/routes_assist.py:197`). README line 507 still says Sonnet 5.5 for that case. That line is stale.
- The README's 17 of 17 run used Jev 1.13.0 to rank and Claude Haiku 5.5 at medium effort to verify, with 3 quotes dropped and $0.31 spent (`evals_dev/judge_bench_results.json`, `summary`).
- The engine already depends on `anthropic>=1.0`, `pydantic>=2.7` and `httpx` (`engine/requirements.txt`).
- The existing T3 eval transport writes each structured request to `calls/<sha256>/request.json` and waits for a `response.json` written from a T3 task result (`evals_dev/task_transport.py`). `haiku('medium')` returns `{'provider': 'claudeAgent', 'model': 'claude-haiku-5-5', 'options': {'effort': 'medium'}}`.
- `evals_dev/model_comparison.py` uses Luna through Codex as the judge. Codex was out of quota on 2026-10-28. Tonight's experiments must use deterministic scoring, not a model judge.

## LangChain (Python, v1)

What it is. `create_agent` is "a minimal, highly configurable agent harness" built on LangGraph. Middleware wraps the model and tool loop. Built-in middleware: tool error, tool retry, model retry, model fallback, summarization, human-in-the-loop, model call limit, tool call limit, PII detection, to-do list, LLM tool selector, provider tool search, shell tool, filesystem, subagent, rubric grading, file search, context editing, LLM tool emulator. Structured output uses `ProviderStrategy` (the provider enforces the schema) or `ToolStrategy` (tool calling), chosen from the model's profile.

Where it would fit. Intake extraction, document review and the assistant each make one structured call. None of them loops over tools.

Gain. Small. One interface for OpenAI and Anthropic would make switching intake from Luna to Haiku a config change. `ModelFallbackMiddleware` and `ModelRetryMiddleware` would add retries, which Batatis deliberately leaves out ("No retry", `engine/intake/model.py:241`) so the spend ledger stays exact. `PIIMiddleware` covers email, credit card, IP, MAC and URL. Batatis already scrubs personal values the rules read (`engine/intake/extract.py`, `scrubbed`), which is more specific to the form.

Loss. Measured on 2026-10-28 in a scratch environment: `langchain 1.4.7`, `langchain-anthropic`, `langgraph 1.2.18` and their dependencies add about 42 MB unzipped beyond packages Batatis already has. `zstandard` alone is 24 MB. That fits easily under Vercel's 500 MB Python limit. Warm import on a Mac: `langchain_anthropic` about 750 ms (of which `anthropic` is about 515 ms), `langchain.agents` about 370 ms, `langgraph.graph` about 350 ms. Expect roughly 0.4 to 0.7 s more on a cold start. Every call site would change, so the 159/159, 18/18 and 33/33 receipts would need to be re-earned.

Retrieval. The current retriever index no longer lists BM25 or ensemble retrievers; their old URLs return "Page Not Found". Batatis already has BM25 over SQLite FTS5 with four tuned query variants (`engine/identify/search_rank.py`) and a cross-reference graph that raised tune recall at 40 candidates from .779 to .824 (`evals_dev/identify_bench/results/lexical.md`). The PDF loaders (`PyPDFLoader`, `PyMuPDFLoader`, Docling, Unstructured and others) wrap libraries Batatis already calls directly (`pypdf`, `pypdfium2`). The rerankers listed (Cohere, Pinecone, watsonx, Contextual AI) are paid hosted services.

Effort. 12 to 20 hours to move the three call sites and re-run the receipts.

Verdict: No.

## LangGraph (Python)

What it is. A low-level runtime for "long-running, stateful agents". It offers a Graph API and a Functional API (`@entrypoint`, `@task`), checkpointers (memory, SQLite, Postgres), stores, per-node retry, timeout and error handlers (`langgraph>=1.2`), `interrupt()` for human input with resume by `thread_id`, time travel, subgraphs and streaming.

Where it would fit. The five-question deck, path choice and package steps. Long drafting jobs (`engine/jobs.py`).

Gain. Little. The question planner (`engine/intake/plan.py`) and path choice (`engine/path_decision.py`, mirrored in `web/src/pathDecision.ts`) are pure functions. The web deck holds the UI state and the case store holds the server state. LangGraph's interrupt model needs a checkpointer and a `thread_id`. Batatis already has the case id and stored answers. Durable execution matters when one run spans minutes or crashes mid-way. Vercel functions run up to 300 s on Hobby and 800 s on Pro, and identify finishes in seconds.

Loss. Same packages as above. It would add a second source of truth for case state next to Postgres. It would also move the path rules from two mirrored pure functions into a graph, which makes the TypeScript mirror harder to keep equal.

Effort. 20 to 40 hours for the flow. High rewrite risk the night before.

Verdict: Later, only if background drafting jobs become long and need resume after a crash. Even then, compare it with the existing `jobs_store.py` first.

## LangSmith

What it is. Hosted tracing, datasets, experiments, evaluators (code, LLM judge, composite, summary, pairwise), annotation queues, prompt management and a Playground. `evaluate(..., upload_results=False)` runs locally without upload. `/datasets/upload-experiment` accepts experiments run elsewhere, so the existing harness could push results without being rewritten. Pairwise evaluation compares two existing experiments and has a `randomize_order` option against position bias.

Gain. Eval results judges could click through. Annotation queues are the best fit for the README row that says "Real applications an officer has tested: 0". An officer could label article picks in a queue and those labels would become a gold set.

Loss. Case text goes to a third-party host. The repo is public and the app promises redaction (`engine/redact.py`, `engine/privacy.py`). Prompt hub conflicts with the pinned prompts and `config_hash` check (`engine/identify/config.py`, docstring). A dashboard built tonight would show the same numbers the README already shows.

Effort. Tracing, about 2 hours with `@traceable` or OpenTelemetry. Uploading existing results, about 3 hours.

Verdict: Later. After the demo, start with annotation queues for officer labels.

## Deep Agents and Managed Deep Agents

What it is. A harness on top of `create_agent` with planning (to-do list), a virtual filesystem, subagents, skills, memory, sandboxes and rubric grading. Managed Deep Agents runs it on LangSmith. LangChain's comparison page sets it against the Claude Agent SDK. Deep Agents works with any model provider and has pluggable backends. The Claude Agent SDK is Claude-only and you host it yourself.

Gain for Batatis: none. The product's rules say Section C is a deterministic lookup, Section D evidence must not be authored, and no article number may be invented. An open-ended agent that plans and writes files makes all three harder to guarantee.

Verdict: No.

## Alternatives

DSPy. GEPA needs a metric that returns a score and feedback text, plus a strong reflection model. Its `auto` presets map to 6, 12 or 18 candidates. One docs example of a 2-predictor, 100-example task needs about 1,330 metric calls for light and about 2,045 for heavy. The T3 transport needs one task per call, so that is not practical tonight. Our labelled sets are also small and partly written by the team (the README says so). An optimizer would overfit them. Verdict: Later, after an officer-labelled set exists.

Pydantic AI. Typed agents. Output that fails validation is sent back for another try. It supports Anthropic. Pydantic Evals grades outputs and tool trajectories. Durable execution through Temporal or DBOS. Verdict: No. It replaces working code and adds retries the spend ledger does not expect.

Instructor. Adds structured output and retries on top of providers. Both of our providers enforce schemas natively now. Verdict: No.

LlamaIndex. A RAG framework with loaders, indexes and citation query engines. It overlaps with what CodeDB already does more precisely. Verdict: No.

Inspect AI (UK AI Security Institute). A task is a dataset, a solver and a scorer. It has the `inspect view` log viewer and supports Anthropic and custom model providers. I did not confirm on the pages I read that it can score saved outputs without generating them. Verdict: Later, for a reproducible public eval.

promptfoo. A local CLI with a web viewer. The `echo` provider returns the prompt as output with "no API call, cost, or token usage", so saved outputs can be graded with `contains` and similar assertions. Model-graded assertions still call a model. Verdict: Later. It is the cheapest way to get a clickable eval page, about 2 hours, but the README table already carries the numbers.

Ragas. Faithfulness and context precision metrics. The RAG metrics are judged by a model. There is an option to judge faithfulness with HHEM-2.1-Open, a local classifier. Batatis checks every quote as an exact substring of CodeDB, which is stricter than a faithfulness score. Verdict: No.

Braintrust. A hosted eval platform with a free Starter plan; Pro is $249 a month according to third-party pages. I did not check the vendor's own pricing page. Same role as LangSmith. Verdict: Later.

### Claude-native features

Structured outputs. Haiku 5.5 is supported. The schema goes in `output_config.format`. The raw `output_format` field is deprecated and needs a beta header. The SDK's `messages.parse(output_format=...)` helper is fine; that is what `engine/identify/verify.py:112` uses. Limits: no `minimum`, `maximum`, `minLength` or `maxLength`. `minItems` can only be 0 or 1. Enum values may come back in different capitals. The first request compiles a grammar, which is then cached for 24 hours. Verdict: keep.

Citations. Haiku 5.5 is supported. Documents can be plain text, PDF or custom content. With custom content you supply the chunks, for example one block per code sentence. The docs say citations "are guaranteed to contain valid pointers to the provided documents". `cited_text` does not count toward output tokens. Constraint: "Citations cannot be used together with structured outputs." A verifier built on Citations would read the article id from which document was cited and the quote from `cited_text`, not from a JSON field. Then a quote not in CodeDB cannot happen by construction. Today Batatis gets the same zero on screen by dropping bad quotes after the fact (3 dropped in the 17-case run). The gain is fewer lost picks. The count of fabricated quotes shown is already zero. Verdict: Later for the API, because it needs an API key and a new response parser. Tonight, test the same idea as a prompt pattern (T1).

Prompt caching. Haiku 5.5's minimum cacheable prompt is 512 tokens. A cache read costs 0.1 times the input price ($0.01 per million tokens on prompts up to 100K). A 5-minute cache write costs 1.25 times the input price. A single top-level `cache_control` turns on automatic caching. The assistant resends its system prompt and case context every turn, so it would benefit. At $0.10 per million input tokens the saving is cents. Verdict: Later, a one-line change after the demo.

Message Batches. Half price for asynchronous runs. Useful for eval runs with an API key. Not usable through T3 tasks. Verdict: Later.

Files API. No need. Batatis sends text it has already extracted.

PDF input. Claude can read PDF pages as images and text. That could help with scanned drawings in the Data Prompts cases. Intake already sends picture pages for vision (`engine/intake/extract.py`, `picture_url`). Verdict: Later, with its own test.

Claude Agent SDK. An agent harness that runs Claude Code's loop. The T3 `claudeAgent` provider used by `evals_dev/task_transport.py` already gives us Haiku through it for evals. Verdict: No for the product.

### Other grounded-retrieval and proof resources

- RIRAG and ObliQA (arXiv 2409.05677). 27,869 questions over 40 Abu Dhabi Global Market financial regulations. Experts reviewed 1,847 passages and marked 86.91% relevant. RePASs is a reference-free score that combines obligation coverage with a penalty for contradictions. Worth borrowing as a method: score whether a draft covers every obligation in the cited sentences. It is not building-code data.
- NBCC question answering (arXiv 2505.04666). Retrieval-augmented QA over the National Building Code of Canada. Elasticsearch was the most robust retriever they tested. It supports our choice of BM25. I did not find a public dataset release.
- AECBench (arXiv 2509.18776). 4,800 expert-checked questions in architecture, engineering and construction. Models did poorly on code tables. I did not check which national codes it uses.
- BuildingQA (LBNL, BuildSys 2025) is about building knowledge graphs, not codes. CEQuest (arXiv 2508.16081) is about drawings. Neither fits.
- The best real-data proof available tonight is already in the repo. `evals_dev/public_benchmark/cases.json` has 53 STANDATA cases from Alberta: 24 interpretations, 17 variances, 9 bulletins and 3 SPV cases. 49 are NBC(AE) 2023, 1 is ABC 2014 and 3 have no edition number. Each has gold article numbers. `evals_dev/public_benchmark/families.py` groups related cases so that near-duplicates are not counted twice.

## Experiments for tonight

Neither experiment changes product code. Both write outputs only under the bakeoff's run folder (outside git).

### T0. Production search on 53 public STANDATA cases (zero model calls)

- Question. How often does the production profile (`screen: requirements`) put a gold article in the first three shown on real regulator documents?
- Arms. One arm: the checked-in `pipeline.json`. An optional second arm is the `bm25_v3` fallback, as a baseline.
- Inputs. `evals_dev/public_benchmark/cases.json`. Keep the 49 NBC(AE) 2023 cases. Report the ABC 2014 case and the 3 cases without an edition number separately, under the edition rule. Drop any gold id that does not resolve in CodeDB and report how many were dropped. Count one case per family from `families.py`.
- Metrics. Hit@1 and hit@3 (a gold article is first, or among the first three). Full recall of gold. Fabricated ids shown, which should be 0 because every id comes from CodeDB. Report per type (interpretation, variance, bulletin, SPV).
- How to run. Set `BATATIS_LIVE=0` and unset `BATATIS_PROVIDER`. For each case call `engine.identify.pipeline.run(case['query'], codes=Codes())` and compare the article ids returned with `gold`. Save every result row. Rerun once and confirm the rows are identical.
- Expected result. Unknown. Lexical recall at 40 candidates was .824 on tune and .867 on test (`lexical.md`), but hit@3 is a stricter test than recall over a pool. A hit@3 between 50% and 80% would be a believable range. Report whatever comes out. A low number is still evidence.
- Caution. Some STANDATA records may already be in the tuning cases ("precedent 33" in `lexical.md`). Check for overlap with `evals_dev/identify_bench/groups.py` before calling it held out.
- Time. About 1 hour, no cost.

### T1 (optional). Sentence-ID verifier versus quote verifier, Haiku 5.5 medium through T3

- Question. If the verifier returns sentence ids instead of typed quotes, as Claude Citations' custom-content documents do, does it lose fewer picks without losing recall?
- Arms.
  - A. The current verifier prompt (`engine/identify/verify.py` or `llm.py`, `SYSTEM` and `prompt`). It returns `{article, quote, reason, confidence}`, and `check_quotes` drops any quote that is not in the article.
  - B. The same candidates, with each article's sentences numbered (`3.2.4.1.(2)` and so on, taken from CodeDB). The schema returns `{article, sentence_id, reason, confidence}`. The quote is filled in from CodeDB. An id that does not exist counts as a drop.
- Inputs. The same 49 STANDATA cases as T0. Candidates are the top 15 from the offline `rrf+out@5+sib3` recipe (`evals_dev/identify_bench/candidates_lexical.py`), so no Jev call is needed. Both arms get exactly the same candidate list in the same order.
- Metrics. Primary: picks dropped per arm, as a share of picks. Secondary: gold among the verifier's top three picks, paired by case (McNemar test). Also mean picks per case.
- Expected effect. A drops a few percent of picks; the 17-case run dropped 3. B should drop close to 0, because it can only point at sentences that exist. Recall should stay within about ±5 points. With 49 cases, only a difference of about 15 points or more would be detectable, so treat a recall difference as a hint only.
- How to run without an API key. Follow `evals_dev/model_comparison.py`. Build each arm's request with `TaskTransport(root, case_id, 'verify', haiku('medium'))`. A first pass raises `PendingCall` and leaves `calls/<sha>/request.json` files; list them with the `pending` helper in `evals_dev/codex_transport.py`. Dispatch each pending request as one T3 `delegate_task` with provider `claudeAgent`, model `claude-haiku-5-5`, option `effort: medium`, and a brief that contains only the request's system prompt, user prompt and schema. Write each task's JSON payload to `response.json` with `request_sha256`, `task_id` and the same target fields. Then resume and score with code, not a model judge. Luna is not available until 2026-11-02. `IdentifyConfig` rejects Haiku, so this has to run in the eval harness, not through `pipeline.json`.
- Size. 2 arms × 49 cases = 98 Haiku tasks.
- Time. About 2 hours for the adapter plus the task run time.
- Decision rule. Adopt B after the demo if it drops fewer picks and its hit@3 is no worse than A by more than one case. Then consider the real Citations API with an API key.

## Coverage

Docs read on 2026-10-28 from docs.langchain.com. The site is organized as Build, Deploy, Monitor and Test, not by product. Its `llms.txt` index lists 1,473 lifecycle pages and 214 setup pages.

Read in full (prose; code blocks skipped):
- LangChain: overview, structured output, guardrails, Agent Evals (`test/evals`).
- LangGraph: overview, fault tolerance (retries, timeouts, error handlers).
- Deep Agents: comparison with the Claude Agent SDK, first part.
- Integrations: Anthropic provider page; ChatAnthropic sections on citations, structured output and prompt caching (section headings for the rest); retriever index; checkpointer index (SQLite row); document loader index (PDF section).
- LangSmith: evaluation concepts (headings and key passages), run an evaluation locally, pairwise evaluation, upload experiments run elsewhere, annotation queues (retention notes).

Read as section headings and opening lines. All 231 pages in the Python Build index were downloaded (4.9 MB) and turned into a heading digest:
- LangChain: install, quickstart, philosophy, agents, models, messages, tools, short-term memory, streaming, event streaming, all middleware pages (with the full list of built-in middleware), frontend patterns, runtime, context engineering, human-in-the-loop, retrieval and knowledge base, long-term memory, MCP pages, multi-agent pages, Studio, Agent Chat UI, unit and integration tests, deployment, observability.
- LangGraph: install, quickstart, local server, thinking in LangGraph, workflows and agents, persistence, checkpointers, stores, streaming, interrupts, time travel, memory, subgraphs, application structure, test, backward compatibility, frontend, runtime (Pregel), choosing between the APIs, Graph API, Functional API.
- Deep Agents: all pages under Get started, Deployment, Execution environment, Context management, Delegation, Steering (including grading rubrics), Middleware, Frontend and Protocols.
- Managed Deep Agents: page titles and descriptions only.
- Integration provider pages, the learn tutorials, the conceptual overviews, reference, release notes and migration guides, and the contribution pages.

Read as titles only: the LangSmith Test index (datasets, evaluators, annotation queues, Playground, Studio) and the Monitor index (tracing integrations, debugging, dashboards, online evaluators, automations).

Not read:
- JavaScript and TypeScript pages (241). I found no reason to expect they differ for our question.
- The Deploy section (253 pages), downloaded but not opened.
- The Products and setup section (214 pages), including LangSmith self-hosting and plan details.
- The LangSmith REST API reference (572 pages).
- OpenWiki pages beyond the headings.
- The BM25 and ensemble retriever pages, which return "Page Not Found" at `docs.langchain.com/oss/python/integrations/retrievers/bm25` and `.../ensemble_retriever`.
- LangSmith pricing.

Other sources read: the Claude docs pages on citations, structured outputs and prompt caching; Vercel's function limits; Inspect AI's home and models pages; promptfoo's intro and echo provider pages; Pydantic AI's overview; the Ragas faithfulness page (navigation only). DSPy's own optimizer pages would not render, so the GEPA numbers come from search results that quote dspy.ai. Braintrust numbers come from third-party pages.

## Sources (all read 2026-10-28)

- LangChain docs index: https://docs.langchain.com/llms.txt and the `/_llms/` section indexes it links
- LangChain overview: https://docs.langchain.com/oss/python/langchain/overview.md
- Structured output: https://docs.langchain.com/oss/python/langchain/structured-output.md
- Built-in middleware: https://docs.langchain.com/oss/python/langchain/middleware/built-in.md
- Guardrails: https://docs.langchain.com/oss/python/langchain/guardrails.md
- Agent Evals: https://docs.langchain.com/oss/python/langchain/test/evals.md
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview.md
- LangGraph fault tolerance: https://docs.langchain.com/oss/python/langgraph/fault-tolerance.md
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts.md
- LangGraph Functional API: https://docs.langchain.com/oss/python/langgraph/functional-api.md
- Deep Agents compared with the Claude Agent SDK: https://docs.langchain.com/oss/python/deepagents/comparison.md
- Anthropic integrations: https://docs.langchain.com/oss/python/integrations/providers/anthropic.md
- ChatAnthropic: https://docs.langchain.com/oss/python/integrations/chat/anthropic.md
- Retriever integrations: https://docs.langchain.com/oss/python/integrations/retrievers/index.md
- Checkpointer integrations: https://docs.langchain.com/oss/python/integrations/checkpointers/index.md
- Document loader integrations: https://docs.langchain.com/oss/python/integrations/document_loaders/index.md
- LangSmith evaluation concepts: https://docs.langchain.com/langsmith/evaluation-concepts.md
- LangSmith local evaluation: https://docs.langchain.com/langsmith/local.md
- LangSmith pairwise evaluation: https://docs.langchain.com/langsmith/evaluate-pairwise.md
- LangSmith upload of outside experiments: https://docs.langchain.com/langsmith/upload-existing-experiments.md
- LangSmith annotation queues: https://docs.langchain.com/langsmith/annotation-queues.md
- Claude citations: https://platform.claude.com/docs/en/build-with-claude/citations
- Claude structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Claude prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Vercel function limits: https://vercel.com/docs/functions/limitations
- Inspect AI: https://inspect.aisi.org.uk/ and https://inspect.aisi.org.uk/models.html
- promptfoo: https://www.promptfoo.dev/docs/intro/ and https://www.promptfoo.dev/docs/providers/echo/
- Pydantic AI: https://pydantic.dev/docs/ai/overview/
- Ragas faithfulness: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/
- DSPy GEPA (from search results quoting these pages): https://dspy.ai/api/optimizers/GEPA and https://dspy.ai/diving-deeper/gepa-in-depth/
- Braintrust limits: https://www.braintrust.dev/docs/reference/limits (pricing from third-party pages)
- RIRAG and ObliQA: https://arxiv.org/abs/2409.05677
- NBCC question answering: https://arxiv.org/abs/2505.04666
- AECBench: https://arxiv.org/abs/2509.18776
- CEQuest: https://arxiv.org/abs/2508.16081
- BuildingQA: https://bies.lbl.gov/publications/buildingqa-benchmark-natural
- Measured locally: package sizes and import times from `pip download` and `python -X importtime` in a scratch environment under `/tmp` (langchain 1.4.7, langgraph 1.2.18, langsmith 0.14.14, anthropic 2.3.0)

## Methods used

- Matt Pocock, research (primary sources): (local skill library)
- pstack, unslop (plain prose): (local skill library)
- T3 workflow router and routes ("Research, explanation, or design investigation"): (local skill library) (local skill library)
