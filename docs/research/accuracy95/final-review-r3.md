# Independent code and UI review — accuracy95 R3

## Verdict

One remaining P2 measurement-integrity finding. The R1/R2 code and UI findings were rechecked and their fixes hold in the reviewed source paths. I found no further defect in the local-dev target gate, request/result binding, judge-cache handling, source freeze, candidate input isolation, or reopened-input UI state.

The requested 95% Calgary/Edmonton target remains **unproven and not achieved**. I did not inspect a score or run output. The runner explicitly keeps `production_accuracy_established` and `target_met` false. Even a successful local gate would remain a model-graded diagnostic under T3 context, not hosted-product or expert-validated accuracy; the task context records 25 development cases across 11 independent source groups.

## Finding

### [P2] The judge receives a document-review guarantee that the applicant UI does not show

**Locations:** `evals_dev/data_prompts/render.py:46-63`; called by `evals_dev/luna_accuracy.py:219-221`; source evidence accepted at `engine/intake/review.py:703-705,726-738`; visible review at `web/src/calm/DocumentReview.tsx:90-107,120-125`.

For every `live` or `fake` review, `_review()` prepends: “Batatis read every readable page; each fact quotes the page it comes from.” The runner passes that generated transcript to the Luna judge. The applicant panel displays findings and their actual source excerpts, but does not display that guarantee; it labels description evidence “Your description.” The review pipeline accepts description evidence with no page number, and its 600,000-character selection budget can leave readable pages unsent. In the latter case deterministic `not_read` flags record the omission, and the local target gate blocks such a run, but the plain micro-accuracy score can still include the extra transcript claim.

This creates evaluator-only content and can overstate source coverage in the displayed diagnostic score. The current run’s score impact is unknown because result artifacts were not inspected. Remove the synthetic guarantee from the judged transcript or replace it with wording that exactly matches what the UI shows and what the recorded review actually read.

## Rechecked fixes

- **Applicant-visible facts:** intake keeps the semantic file-extraction pass; the new review panel displays advisory source facts with status, filename/page, and exact excerpt. The panel has no dispatch path into canonical facts or blocking gaps.
- **Frozen evaluation:** `index.json` is hashed and checked; source hashes now cover `engine`, `codedb`, `evals_dev/data_prompts`, and `web/src`, with the code database hashed separately. Results bind to manifest/input fingerprints and each model request, response, and T3 task receipt. The `--case` resume option skips other case writes, while grading still iterates the full frozen selection.
- **Target and denominator:** only the exact `local-dev` case set from both Calgary and Edmonton can set the local coverage gate. Integer arithmetic checks 95% overall and per city; failed cases, unread inputs, incomplete/invalid judges, and failed guardrails prevent the gate. `target_met` and `production_accuracy_established` remain false.
- **Cache and isolation:** the custom Codex transport bypasses the generic judge-verdict cache and validates its own request/response boundary; the legacy cache rejects a mismatched request hash. Candidate stages receive the prompt and default-input attachments through the engine path; gold references are loaded only after candidate output exists for grading. The runner supplies the custom transport to intake, review, identification, and judging and does not call the OpenAI HTTP fallback.
- **Reopened input and status:** saved description text is restored only after its SHA-256 matches the persisted intake hash; otherwise the UI marks it unverified and Start triggers a reread. File additions/removals, including removing the last file, mark the prior review stale. Failed, gated, off, not-needed, and unknown statuses suppress model claims while deterministic unread flags remain visible where appropriate.

## Review pin and boundaries

- Branch: `work/luna-accuracy-95-20261025`.
- Base and `HEAD`: `e5e794b6ab828afdfc52858cf3ed75d39e62a73c`.
- SHA-256 of `git diff --binary e5e794b6`: `4e8bdc520e0a293365e8dea745fdb562650524a3012678a9efb5990a8ce6efbb`.
- The table pins the reviewed changed code/tests and the unchanged code paths used to validate the finding and score boundary. Hashes are for current working-tree bytes.

| File | SHA-256 |
| --- | --- |
| `evals_dev/codex_transport.py` | `8578e5a266531eb1d56eeef2c2f2e373430239a4d071de91b11a7168b2777fc7` |
| `evals_dev/luna_accuracy.py` | `2404f83d3a3336e4de23940359c0f90e2f3afc17cf8067498063727e1e07d113` |
| `evals_dev/data_prompts/judge.py` | `9905dc9812d762331fba838c5669bc2c498c1ec16f30257fa12ea2a175f3a553` |
| `evals_dev/data_prompts/__main__.py` | `7dfba9facf87e714ca162aa18f10a730539ce313b33cd5b8128ec9aa6fcbbfa3` |
| `evals_dev/tests/test_codex_transport.py` | `cb6f64033d23a86429e1bd9d8f0b7f41cab86ca3b302a5c9c2180b060f2299d9` |
| `evals_dev/tests/test_luna_accuracy.py` | `b9fffbf0c4f20aed9b5dd778a098e274a83ca039b1cfe859b0b1fe4938788bae` |
| `evals_dev/tests/test_corpus_input_policy.py` | `c82159e3de470b5141f6be15c8c7358995522ea2c16be280591317ec275305e4` |
| `engine/tests/test_intake_review_pipeline.py` | `937833cbd897b5f59204fffd01a1a358444a5098000272804be1f41fd4d51d48` |
| `web/src/calm/DocumentReview.tsx` | `46205340b67d19e8529c03e8d1ae43f5a3a9f3a8ccd8b465bc70cd15cfbf1d92` |
| `web/src/calm/DocumentReview.css` | `c265288179a2feef8eb142462dedc1f32853f0d59cf5a6d68b2969a197ccbcec` |
| `web/src/calm/DocumentReview.test.ts` | `bd183bbe1c1f8a9ba0763feb4d6041fdaef1fd0f007b107fa6b10d33f26b75f4` |
| `web/src/calm/DocumentReview.test.tsx` | `ed3ab8a8f2d48590018729f02a8be7dd90dd35408835b3d96ad28ceb965a58e0` |
| `web/src/calm/QuestionDeck.tsx` | `7aa9b8e3a8527bd87e608dbd322a7ebc6277cacc084e0b41bfccebcafae13dbc` |
| `web/src/calm/Start.tsx` | `31219f5233c2c91a30c23183dc251a6360111fa5ca74aa04f111bdb3d9b12e77` |
| `web/src/calm/openCase.ts` | `dabb5a202912dde403e94c3be0a200b34589f86529fb6614e441ea56fc36bb65` |
| `web/src/calm/openCase.test.ts` | `e39b22ee3c2af845a821bc1fae7eeccfc77a835374183c383a77e759c1e44be9` |
| `web/src/intakeView.ts` | `0730f40e5ea28d848392aa7a9beb89bd9a4d63a6545d24757d1fbc99ae45ca17` |
| `web/src/model.ts` | `ed9474454ea03e69f6afe4d7e4e0b3b19b1850502d5dfaecbe881dc4391c9c4a` |
| `web/src/store.tsx` | `d7796c21ea5104a2e60c1876af6bb73982c0c14bf32b96feb167f03acb14cd81` |
| `web/src/types.ts` | `1c3b26dfa97f7ae6b6af9894f5a9e414fa80cfe06aa8dd74cdee3166c9f3b078` |
| `engine/intake/service.py` | `91f544ae4ebbafefcbbef4d45bcd66f4037ccfb530ee123b84b4a1e5c195677a` |
| `engine/intake/review.py` | `65442fb19c80d0b00ff9611e562101342153cb59d99a946e573ebff2a8edb026` |
| `evals_dev/data_prompts/corpus.py` | `4c6c91abdfd60d26685638d413d39d0c23876f8501e748204ac7a94b69f6d7a1` |
| `evals_dev/data_prompts/gold.py` | `97d15ac0c9b2d5538076d6127d40cd0765c0bbbe4cf7767c5ddc6bcd7fc1ab4c` |
| `evals_dev/data_prompts/render.py` | `73cac4486bb96572bb30b635953437e454198c6eedc7c3d8862e6df1ce35bf6c` |
| `evals_dev/data_prompts/checks.py` | `1c78d81ea12a1935117b1159b0625c1f25e5167ffe225428bb78b99ebb69eae9` |
| `evals_dev/data_prompts/score.py` | `9861f5df12ad527e28c72dcbe37f8a11dd9d3c28bf4f4d0258acc82cf522599c` |
| `codedb/api.py` | `18b7b6a16bb75c3c9a4eb32cc194df857b9f06ac13f4c4d18c1fa7bfa7d5eb18` |

The five previously reviewed development-packet corrections and curation metadata were not reopened. Their tracked changes are covered by the full tracked-diff hash above. I did not read holdout facts/errors, accuracy result artifacts, or `.dpe-cache/codex/local-dev-v4` requests/results/judge files.

## Verification and limits

- I did not run tests or the full gate. Task context reports the web typecheck and 30 Chromium/reopen checks passed after the latest fixes; the parent `scripts/verify.sh` run was still in progress and its output was not observed in this review.
- Whole-app browser capture remains unverified. The supplied T3 preview snapshot failed twice with `Preview automation snapshot timed out after 15000ms.` Prior component-fixture screenshots are not whole-app acceptance evidence.
- No provider/API calls, servers, ports, commits, pushes, or further delegation were used.

## Methods used

- T3 workflow: `/Users/aamia/.codex/skills/t3-workflow/SKILL.md`; review routing: `/Users/aamia/.codex/skills/t3-workflow/references/routes.md`; UI limits: `/Users/aamia/.codex/skills/t3-workflow/references/ui-quality.md` and `/Users/aamia/.codex/skills/t3-workflow/references/visual-evidence.md`.
- Matt Pocock `code-review`: `/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/code-review/SKILL.md`.
- Open Pstack `benchmark-checklist`, `typescript-best-practices`, and `principle-type-system-discipline` from `/Users/aamia/.agents/skill-libraries/pstack/skills/`.
- `better-ui`: `/Users/aamia/.agents/skills/better-ui/SKILL.md`.
- Project contracts: `AGENTS.md`, `GLOSSARY.md`, `docs/design-system-calm.md`, and `docs/research/accuracy95/experiment-protocol.md`.
