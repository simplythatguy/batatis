# Haiku Adapter Review r6

## Verdict

No workflow, scoring, or criterion change was found in the resume/grade path. The adapter loads `evals_dev/luna_accuracy.py` as a separate module instance and replaces only that instance's `CodexTransport`. The requested candidate target is carried by each request and checked against the returned task metadata. The judge target remains the same constant for both arms, and `judge.grade` uses the injected transport, bypassing its direct HTTP `_call` branch and its generic verdict cache.

The two arm roots keep request and response files separate. Candidate request hashes differ with effort; equivalent judge requests have the same identity when the judge environment is the same. The adapter's direct writes are inference `request.json` files and a preparation-count JSON; it has no direct response, `Case`, or scored-result write. When a call is pending, it returns an in-memory `{'facts': []}` placeholder so the engine call can continue; that placeholder is not persisted. Transport failures are promoted to `PreparationFailure`, which escapes ordinary `Exception` handlers.

No provider/model calls, resumes, grades, comparison-root contents, outcomes, scores, payloads, or holdout errors were inspected. This review establishes no 95% accuracy claim and does not verify external T3 dispatch receipts.

## Findings

1. **P2 — The judge nonce is outside the frozen comparison profile.** `evals_dev/data_prompts/judge.py:118-121,172-180` reads `DPE_JUDGE_NONCE` into the judge request (and its cache identity). `model_comparison.freeze` records the judge model/options but not this value, and `validate` does not pin or check it (`evals_dev/model_comparison.py:38-50`). If the variable differs between separate arm runs, the judge receives a different request despite matching model/options. Record and enforce the nonce used by the current Luna baseline, or explicitly require it to be empty. This is a conditional comparability gap; no run-time mismatch was checked.

2. **P2 — Adapter hash validation accepts an incomplete hash map.** `validate` checks only entries present in `manifest['adapter_sources']` (`evals_dev/model_comparison.py:51-53`). The underlying source freeze does not include the two adapter files (`evals_dev/luna_accuracy.py:33-38`), so deleting either adapter entry lets a changed file pass validation. Require the manifest key set to equal `ADAPTER_FILES` before checking the digests.

## Focused checks

- `evals_dev/tests/test_model_comparison.py`: **5 passed** with `BATATIS_LIVE`, `BATATIS_LIVE_JEV`, and `BATATIS_LIVE_ELEPHANT` set to `0`, and `BATATIS_PROVIDER` unset. The tests confirm `run_case`/`grade` bytecode equality, unchanged original transport binding, candidate request identity, response-model binding, and equal judge request identity under the same environment.
- The actual judge implementation is `evals_dev/data_prompts/judge.py`; there is no root-level `evals_dev/judge.py` in this checkout.

## SHA-256 of reviewed sources

| File | SHA-256 |
|---|---|
| `evals_dev/task_transport.py` | `7476b920302c7bca043008c276858c595ebf570c6cd1d93b93bf19cc32150755` |
| `evals_dev/model_comparison.py` | `447a7774048832b244092ce40a6d37643d86f5a92d900cd0cad84ee9bb7361a3` |
| `evals_dev/tests/test_model_comparison.py` | `a0fc83aab00a042ec3e883851d1011f692483d32fe09459c0d0d1c46fe01b0a2` |
| `evals_dev/luna_accuracy.py` | `2404f83d3a3336e4de23940359c0f90e2f3afc17cf8067498063727e1e07d113` |
| `evals_dev/data_prompts/judge.py` | `9905dc9812d762331fba838c5669bc2c498c1ec16f30257fa12ea2a175f3a553` |
| `evals_dev/codex_transport.py` | `8578e5a266531eb1d56eeef2c2f2e373430239a4d071de91b11a7168b2777fc7` |

## Methods used

- Matt Pocock `engineering/code-review`: scoped implementation and caller review against the stated spec.
- pstack `benchmark-checklist`: checked comparability controls and limited verification claims; no performance or accuracy result was reported.
