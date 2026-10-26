# Haiku 5.5 comparison

The user requested Haiku 5.5 at low and medium effort with the same workflow and the same judge as Luna. This is a local model-graded diagnostic, not a hosted-product accuracy claim.

- Candidate arms: `claudeAgent:claude-haiku-5-5`, with native `effort=low` and `effort=medium` respectively. Intake, document review and identification all use the arm's candidate.
- Judge for both arms and the current Luna baseline: `codex:gpt-6-luna`, `reasoningEffort=max`, `serviceTier=priority`. Its system prompt, schema, strict validator and reference construction are unchanged. The judge nonce is explicitly empty, matching the saved current Luna judge request.
- Inputs, engine, CodeDB, split and references match `.dpe-cache/codex/local-dev-v5`. Each arm predeclares all 25 local development cases, 11 connected source components and 268 checks: Calgary 8 cases/92 checks; Edmonton 17 cases/176 checks. The historic 259-check benchmark is a different reference version.
- Each structured call receives a fresh T3 task with only its assigned request and the common execution brief. Candidate tasks cannot read gold, other outputs or scores. Judge tasks receive only their report and reference items, with no prior verdicts. Actual returned provider/model/options and task IDs are retained as dispatch receipts. No OpenAI or Anthropic API client is used.
- The adapter loads an isolated copy of the unchanged Luna workflow and replaces only its transport factory. Candidate request identity includes model and effort. Judge transport always selects Luna. The base module is not patched; workflow bytecode equality and model/effort binding are tested.
- Partial progress keeps unfinished cases/checks visible. No case is removed for errors or unread inputs. Any interim single-case result is a smoke test, not an estimate of full-set accuracy. Whole-case success and city/source-group counts accompany completed comparisons. A paired model-only result requires the same completed cases in every reported arm.

## Freeze and replay lineage

The first setup roots `arm-a` (low) and `arm-b` (medium) each contained seven source requests and one completed review response. Independent R6 review found two conditional freeze gaps: the nonce was not recorded and adapter validation accepted an incomplete hash map. Both are corrected, with regression coverage. The live and baseline nonce were verified empty.

The corrected immutable roots are `.dpe-cache/task-comparison/h55/arm-c` (low) and `arm-d` (medium). They preserve the exact source/CodeDB/index/input/reference/split/candidate/judge identities of their respective setup roots. Only canonical-hash-verified candidate request/response bytes and original task receipts were replayed; no case result, judgment or score was copied. Each corrected root contains `cache-replay.json` with original/new manifest hashes and every replayed file hash. Selection did not use payload contents or outcomes.

One initial medium review task reported skipping the requested workflow/skill reads. Its original response is retained, and this process deviation must remain visible. It answered the supplied structured request; no replacement was selected on quality grounds. Subsequent briefs reiterate the shared reads. T3 may inject provider-specific agent/workspace instructions, so matching engine requests does not establish identical hosted inference context. Usage/cost are unknown.

New scraped ECSD records remain quarantined outside both arms and the current Luna baseline. No holdout item-level errors or outputs are inspected for this comparison. No professional correctness, code compliance, safety, equivalence or approval is inferred from these checks.
