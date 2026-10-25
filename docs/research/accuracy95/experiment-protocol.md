# Local accuracy improvement experiment

Requested outcome: at least 95% source-grounded check coverage for Calgary and Edmonton, using Codex Luna through T3 and no OpenAI API calls. This work starts from `origin/main` at `e5e794b6` in its own worktree. Production approval remains with the user.

The existing evaluation's primary metric is passed F (facts), R (review points), B (boundaries), and A (article) checks divided by all eligible checks. It is not the share of applications handled correctly. Report whole-case success and each city's counts beside check coverage. Every citation, scope, execution, and professional-claim guardrail must also pass. A 95% check score alone does not establish professional correctness or a 95% population accuracy.

## Evidence boundaries

- Keep the existing source/attachment-connected development and holdout split. Tune only on development cases. Do not inspect holdout errors while tuning; report prior aggregate summaries as historical only.
- The model under test receives only the engine's actual system instructions, input text, supplied attachment pages, schema, and candidate code text. Never supply curator facts, review focus, outcomes held out from the input, or scoring instructions.
- Use a separate fresh Codex Luna task for judging. Apply the existing strict coverage rules unchanged, including exact report excerpts for positive verdicts and failed missing/malformed verdicts. Rejudge baseline and candidate under the same judge and settings before comparing them.
- Freeze source hashes, code database, prompt and attachment hashes, reference construction, split membership, and model settings before running each candidate. Changed source requires a new experiment. Preserve failures and unfinished cases in the final denominator.
- Count independent connected source groups. Multiple questions about the same PDFs do not increase the number of independent projects. New records require original bytes, provenance, explicit locality, source class, page locators, and duplicate checks.
- Keep new scraped sources out of candidate retrieval and tuning until assigned to a split. A public decision is historical evidence with known outcome, not an unseen application or a technical ground truth.

## Local execution

`evals_dev.codex_transport` stages exact prompts on disk. The parent creates T3-owned `codex:gpt-6-luna` tasks with `reasoningEffort=max` and `serviceTier=priority`; each response records the task identity and prompt hash. Pending work suspends the run instead of silently invoking a fallback. Python dispatches no HTTP or subprocess model. Unknown token usage and cost remain unknown.

`evals_dev.luna_accuracy` uses the actual intake, review validator, code database, identification, planning, and completeness functions. The initial bounded identification experiment uses keyword retrieval over the real code database followed by Luna reading 60 full candidate articles. It does not claim exhaustive screening. This local transport is an evaluation adapter; it does not replace the hosted provider transport. Real attachments are private and restored outside Git; the hosted 4 MB upload cap remains a separate product limitation.

Development smoke cases are `A03-003`, `L05-001`, `L04-001`, and `A06-001`, all from the pre-existing development split. Their results are diagnostic. A final holdout result requires a candidate frozen after development and reported without further tuning against that holdout.
