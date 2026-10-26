# Independent code review — accuracy95 R2

## Verdict

The four round 1 findings are fixed in the current working tree. I found three remaining measurement-integrity issues: the local target gate accepts cherry-picked selections, cached judge verdicts are not bound to their request/task artifact, and the frozen source inventory omits runtime code used by the candidate and visible output.

This review did not run a candidate or judge model. No 95% result was measured here. The runner continues to set `target_met` and `production_accuracy_established` to `false`; its proposed score is model-graded local check coverage, not expert-validated or hosted-product accuracy.

## Review pin and boundary

- Branch: `work/luna-accuracy-95-20261025`
- Base and `HEAD`: `e5e794b6ab828afdfc52858cf3ed75d39e62a73c`
- Review boundary: current working-tree changes against that base, plus the direct input, scoring, code lookup, and user-visible review callers needed to verify the requested behavior.
- No source, gold, output, split, or attachment was changed by this review. The only file written is this report.
- The five corrected packets (`L04-001`, `L04-002`, `L04-005`, `L05-003`, `L14-003`) were confirmed as development cases using `corpus.select('dev')`. I inspected their changed packet diffs and split membership. I did not inspect holdout facts/errors or `diagnostic-results.json`, and did not read the old worktree.
- The parent’s healthy maintenance check for T3 version `0.1.2-nightly.20261021.3499` was reused.

## Findings

### [P1] The target gate can pass on a cherry-picked subset or one city

**Location:** `evals_dev/luna_accuracy.py:40-55, 233-240`; `evals_dev/data_prompts/corpus.py:153-165`.

`freeze()` accepts every selection supported by `corpus.select()`, including a single case ID, `all`, or `holdout`. The local target condition only requires nonempty rows and applies the 95% check to the cities present in those rows. It does not require the complete development split or even both Calgary and Edmonton. For example, a complete, all-passing `L04-001`-only run would make `check_coverage_target_met` true with no Edmonton cases. The always-false `target_met` flag prevents a production claim, but the local diagnostic target flag still overstates the requested two-city result.

**Fix:** Permit the target flag only for a predeclared complete split/run mode, require both target cities and report their denominators. Keep smoke or arbitrary case selections explicitly diagnostic. If holdout scoring is supported, make it a separate post-candidate-freeze mode. I did not execute a subset or holdout run.

### [P2] Judge-cache hits are not checked against their request or T3 response

**Location:** `evals_dev/data_prompts/judge.py:158-188`; `evals_dev/luna_accuracy.py:202-206`; `evals_dev/codex_transport.py:33-35, 57-64`.

`judge.grade()` stores `request_hash` in each cache artifact but, on a cache hit, checks only `validator_version` before using `payload`. The runner creates the judge transport without a `calls` list, so the cached verdict and score row do not carry the T3 task ID or response hash that the candidate-result binding now records. A copied/misplaced cache artifact can therefore be accepted for another request, and a cache hit does not validate that its corresponding T3 response still exists and matches. The strict excerpt validator still checks returned evidence against the current report, but it cannot establish which request produced the verdict.

**Fix:** Check the cached `request_hash` against the computed key and bind cached judge payloads and score rows to the exact T3 request, response hash, and task ID. Add regression coverage for a cache artifact from a different request and for a missing/mismatched task response.

### [P2] The frozen source inventory omits runtime code and the visible consumer

**Location:** `evals_dev/luna_accuracy.py:33-37, 72-82`; callers `engine/codes.py:9, 35-48`, `codedb/api.py`, and `web/src/calm/DocumentReview.tsx:59-121`.

`sources()` hashes `.py`/`.json` files under `engine` and `evals_dev/data_prompts`, plus the two runner files. It hashes the SQLite code database separately, but not the `codedb` Python package that implements provision lookup and search. It also omits the `web` component used to show the source facts that `render.report()` scores. If either code path changes after freeze, `selected()` will not report a source change, so a run can be resumed/graded against a changed citation implementation or a UI that no longer exposes the findings credited by the renderer.

**Fix:** Include the `codedb` runtime package and the web files that determine whether scored review content is visible in the frozen source manifest, or narrow the claim and score only a separately frozen output contract.

## Round 1 findings rechecked

- **Semantic file facts:** `engine/intake/service.py:43-66` retains the file model extraction pass alongside document review. The new `DocumentReview` panel displays review source facts with page excerpts, and the evaluator renderer includes those same review facts. The new intake regression test covers file facts reaching the fact ledger and fallback behavior.
- **Current reopened-input state:** the latest web edits restore the saved description only when its SHA-256 matches the intake record, mark file additions/removals as stale until reread, and label previous or unverified review findings. I code-inspected this current path; I did not start the app or browser.
- **City/index freeze:** `freeze()` records `index.json` SHA-256 and `selected()` rejects a changed index.
- **Result reuse:** `freeze()` rejects existing result files; `seal()` binds results to the manifest and case inputs; `bound_result()` checks result content plus request/response hashes and task IDs. The focused tests cover copied and modified results.
- **Unread inputs:** score rows now include `not_read` flags, and `check_coverage_target_met` blocks on unread inputs. The test covers unread content even when the judge passes the text.
- **Attachment policy:** assembly now honors explicit `included_in_default_input` values; current assembly and corpus grouping use the same explicit-value/default-role policy. The five changed development packets pass the selected local attachment verifier: 5 prompts, 21 attachment/derived files, 0 errors.
- **Input isolation:** candidate stages receive `case.prompt` and verified default-input attachments. `gold.gold()` is used during grading after the candidate result exists; curator facts, review focus, and evaluation files are not passed into candidate calls.
- **Errors and API path:** `PendingCall` derives from `BaseException`, so broad engine exception handlers do not turn pending work into success. Missing results, failed runs, unread input, and pending/invalid judge verdicts remain failures in the denominator. The runner injects `CodexTransport` for intake, review, identification, and judging; that transport stages local request/response JSON and makes no HTTP call. `judge.py` retains its generic OpenAI HTTP fallback, but this runner supplies `transport=bridge` on every judge call.
- **Configuration and limits:** the manifest records `bm25_v3` top-60 retrieval with Luna full-text verification over 60 candidates, no Jev stage, unknown usage/cost, and that T3 injected context differs from hosted inference. Production and user target flags remain false.

## Verification and limits

Focused offline tests, with live providers disabled:

```text
BATATIS_CODEDB=$PWD/codedb/build/codedb.sqlite \
BATATIS_LIVE=0 BATATIS_LIVE_JEV=0 BATATIS_LIVE_ELEPHANT=0 \
PYTHONDONTWRITEBYTECODE=1 \
/Users/aamia/.t3/projects/batatis/.venv/bin/python -m pytest -q -p no:cacheprovider \
  engine/tests/test_intake_review_pipeline.py \
  evals_dev/tests/test_codex_transport.py \
  evals_dev/tests/test_luna_accuracy.py \
  evals_dev/tests/test_corpus_input_policy.py
```

Result: `19 passed in 0.34s`.

The focused local attachment verification returned `5 prompts, 21 attachment_files, 0 errors, 592 source_groups`. No provider or API call was made. The parent’s full gate was not rerun. No app server or browser was started. This report therefore verifies code paths and local fixtures only; it does not produce an accuracy score, a T3 acceptance result, or hosted-product evidence.

## Methods used

- Project and task contract: `AGENTS.md` and `docs/research/accuracy95/experiment-protocol.md`.
- T3 workflow routing: `/Users/aamia/.codex/skills/t3-workflow/SKILL.md` and `/Users/aamia/.codex/skills/t3-workflow/references/routes.md`.
- Matt Pocock code review: `/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/code-review/SKILL.md`.
- pstack benchmark checklist: `/Users/aamia/.agents/skill-libraries/pstack/skills/benchmark-checklist/SKILL.md`.
- No additional delegation was used.

## Exact reviewed file hashes

SHA-256 values below are for the exact bytes reviewed in this working tree.

| File | SHA-256 |
|---|---|
| `AGENTS.md` | `867d6f9ac37542e7a67547da577c156c2606d0f574e892e99134006e3faf80e9` |
| `docs/research/accuracy95/code-review-r1.md` | `9d029ca5a53e5bef0938f03cfb324b9bcd0d8e7142b21b228ea6179f96abb21a` |
| `docs/research/accuracy95/experiment-protocol.md` | `c5f8c4b7207a9e6c413fc37d06e22c02de74b30f821b496e8e89cc6ba8fcfdc6` |
| `docs/research/accuracy95/corpus-corrections-v2.md` | `745cc7e737dfd84edf8e26d4291afb9bda84fece4daf1ffc048bae2d7f9388f6` |
| `evals_dev/codex_transport.py` | `8578e5a266531eb1d56eeef2c2f2e373430239a4d071de91b11a7168b2777fc7` |
| `evals_dev/luna_accuracy.py` | `fd9edbc094354b1b45e52db27a9364d661d3e17231a6cf1f458a10eaed1bde49` |
| `evals_dev/data_prompts/judge.py` | `cb5cecadae33e755f7bdf6f7b5b2a07efe96d31fb55de7da15af31754c5ea7ee` |
| `evals_dev/data_prompts/corpus.py` | `4c6c91abdfd60d26685638d413d39d0c23876f8501e748204ac7a94b69f6d7a1` |
| `evals_dev/data_prompts/gold.py` | `97d15ac0c9b2d5538076d6127d40cd0765c0bbbe4cf7767c5ddc6bcd7fc1ab4c` |
| `evals_dev/data_prompts/render.py` | `73cac4486bb96572bb30b635953437e454198c6eedc7c3d8862e6df1ce35bf6c` |
| `evals_dev/data_prompts/checks.py` | `1c78d81ea12a1935117b1159b0625c1f25e5167ffe225428bb78b99ebb69eae9` |
| `evals_dev/data_prompts/score.py` | `9861f5df12ad527e28c72dcbe37f8a11dd9d3c28bf4f4d0258acc82cf522599c` |
| `evals_dev/tests/test_codex_transport.py` | `cb6f64033d23a86429e1bd9d8f0b7f41cab86ca3b302a5c9c2180b060f2299d9` |
| `evals_dev/tests/test_luna_accuracy.py` | `23614a42f6ad7ead798ad151650f991706d438bfae8c64c3202f0210472b2174` |
| `evals_dev/tests/test_corpus_input_policy.py` | `c82159e3de470b5141f6be15c8c7358995522ea2c16be280591317ec275305e4` |
| `engine/intake/service.py` | `91f544ae4ebbafefcbbef4d45bcd66f4037ccfb530ee123b84b4a1e5c195677a` |
| `engine/intake/review.py` | `65442fb19c80d0b00ff9611e562101342153cb59d99a946e573ebff2a8edb026` |
| `engine/intake/extract.py` | `3c9941c02006c9ab0ed448c92ecaf724a0a9c711ad221bcfb593ebd1a30e441e` |
| `engine/codes.py` | `a97ade68ba40e08dcc5cdfef65223c6199ee057686e7c6e16cc4954dc0e62f82` |
| `engine/identify/pipeline.py` | `840caabd9f9e8acf4ae6329b97425a4d9c3506b34539ea5615746b517b022c50` |
| `engine/identify/search_rank.py` | `ca1bc7a5c19b1185a3fada658cf84f3572afabe4e61c50bcb1ac70bfa367153f` |
| `engine/tests/test_intake_review_pipeline.py` | `937833cbd897b5f59204fffd01a1a358444a5098000272804be1f41fd4d51d48` |
| `codedb/__init__.py` | `3001b97ba05e92d3aa873fb5f861ae523bc88f1737b538f4d5454b6a0534fe6e` |
| `codedb/api.py` | `18b7b6a16bb75c3c9a4eb32cc194df857b9f06ac13f4c4d18c1fa7bfa7d5eb18` |
| `codedb/store.py` | `1d7f02204f4d551443dfcba973d76a2cf89d45241323b7ae20da31241a772e33` |
| `codedb/build/codedb.sqlite` | `672f2c44d4ca3568630bb6046c7bfece5837bbab33b01a57a35da9a5b46fc03f` |
| `web/src/calm/QuestionDeck.tsx` | `7aa9b8e3a8527bd87e608dbd322a7ebc6277cacc084e0b41bfccebcafae13dbc` |
| `web/src/calm/DocumentReview.tsx` | `35b298ec51831ad1c408658310824c5b79a98b1c93f6a5c965d34c46fd394e2b` |
| `web/src/calm/DocumentReview.test.tsx` | `ed3ab8a8f2d48590018729f02a8be7dd90dd35408835b3d96ad28ceb965a58e0` |
| `web/src/calm/Start.tsx` | `31219f5233c2c91a30c23183dc251a6360111fa5ca74aa04f111bdb3d9b12e77` |
| `web/src/calm/openCase.ts` | `dabb5a202912dde403e94c3be0a200b34589f86529fb6614e441ea56fc36bb65` |
| `web/src/intakeView.ts` | `0730f40e5ea28d848392aa7a9beb89bd9a4d63a6545d24757d1fbc99ae45ca17` |
| `web/src/model.ts` | `ed9474454ea03e69f6afe4d7e4e0b3b19b1850502d5dfaecbe881dc4391c9c4a` |
| `web/src/store.tsx` | `d7796c21ea5104a2e60c1876af6bb73982c0c14bf32b96feb167f03acb14cd81` |
| `web/src/types.ts` | `1c3b26dfa97f7ae6b6af9894f5a9e414fa80cfe06aa8dd74cdee3166c9f3b078` |
| `Data Prompts/_tools/assemble.py` | `362884330e3dfd56d7a7bdf98d3ecb89bfcd689536cf202fa4fb3a471f7c8b31` |
| `Data Prompts/_tools/corpus.py` | `04f8f59d26e2a76d1267ba2fc947fd7d205fe9e84ffe419cb7e3c8934459966c` |
| `Data Prompts/index.json` | `3a9f59b5c69aa8b57fdb4441fccdc85d6b367252948c68beba82bce8cbfe0644` |
| `Data Prompts/_research/curation_overrides.json` | `b0aea5289589de87034eca410c18bdcacfb25009042becf7bd7a4dc7dcf93140` |
| `Data Prompts/Canada/Alberta/Calgary/Prompts/L04-001-calgary-spv-001-zero-lot-line-revision-5-with-revision-4-history/evaluation.json` | `f0c6b5760e27d065d7a6cfead1f8f2c993a795f689afd533fb2d55cd52dfc7eb` |
| `Data Prompts/Canada/Alberta/Calgary/Prompts/L04-001-calgary-spv-001-zero-lot-line-revision-5-with-revision-4-history/prompt.txt` | `892f9f446d8447229fd2c1b494d00ae0f9304eda631af898b91eb77ebe2f722f` |
| `Data Prompts/Canada/Alberta/Calgary/Prompts/L04-001-calgary-spv-001-zero-lot-line-revision-5-with-revision-4-history/source.json` | `f1ce19e1974911cb1e8c995ea0df9e2d3111bb719d837500bbef3c058b5b394f` |
| `Data Prompts/Canada/Alberta/Calgary/Prompts/L04-002-calgary-spv-002-blazemaster-cpvc-in-residential-partial-flow-through-fir/evaluation.json` | `103170640be3d33b5a49cc0a2594dc0127159019cb3ca3f40299b353b2d2f826` |
| `Data Prompts/Canada/Alberta/Calgary/Prompts/L04-002-calgary-spv-002-blazemaster-cpvc-in-residential-partial-flow-through-fir/prompt.txt` | `da0e73fef414be7f59f3c1c36bed0843a6c4727f0403350ccb3d4650a265e28b` |
| `Data Prompts/Canada/Alberta/Calgary/Prompts/L04-002-calgary-spv-002-blazemaster-cpvc-in-residential-partial-flow-through-fir/source.json` | `13e5e064b27bcddf81a01bae20107fbf8066f5f78c6813cf51e61eca879bf7c8` |
| `Data Prompts/Canada/Alberta/Calgary/Prompts/L04-005-calgary-spv-006-firewall-in-a-rowhouse-with-secondary-suites/evaluation.json` | `8e5443bb9cda66fdbd191356cec2a9e7aefcaf23e3cbe19b02e83a962eb8d10f` |
| `Data Prompts/Canada/Alberta/Calgary/Prompts/L04-005-calgary-spv-006-firewall-in-a-rowhouse-with-secondary-suites/prompt.txt` | `724a20fa813b23e532898326346414545280a1e68229a8b0fe80951e68219173` |
| `Data Prompts/Canada/Alberta/Calgary/Prompts/L04-005-calgary-spv-006-firewall-in-a-rowhouse-with-secondary-suites/source.json` | `1acfbf9695fc69a0576226c8ca74083afc62151d50a2fb88c402ef9e3b828109` |
| `Data Prompts/Canada/Alberta/Edmonton/Prompts/L05-003-city-of-edmonton-point-access-block-catalogue-example-c/evaluation.json` | `e68ea1403f3dd15942395abe7d143055f7481643acef137b146087de2028171a` |
| `Data Prompts/Canada/Alberta/Edmonton/Prompts/L05-003-city-of-edmonton-point-access-block-catalogue-example-c/prompt.txt` | `3018f2d2b2054c847b05fff13ca91cd5cca87360c33601e2feadd152478dfb67` |
| `Data Prompts/Canada/Alberta/Edmonton/Prompts/L05-003-city-of-edmonton-point-access-block-catalogue-example-c/source.json` | `0be81215c399eab0d71606b2a212771ab8737fbf5bf58c791d29af480ba55838` |
| `Data Prompts/Canada/Alberta/Edmonton/Prompts/L14-003-kha-edmonton-three-storey-apartment-proposal/evaluation.json` | `a8b91fddf2fd719f22b1aec053ae36cef81e837a23a4e2e4440efd7c52925de6` |
| `Data Prompts/Canada/Alberta/Edmonton/Prompts/L14-003-kha-edmonton-three-storey-apartment-proposal/prompt.txt` | `8ba6a99839e243bd0b882480fa5e19fccb1d9fd7bd57de00732696a4f1e6cbe6` |
| `Data Prompts/Canada/Alberta/Edmonton/Prompts/L14-003-kha-edmonton-three-storey-apartment-proposal/source.json` | `390ac46297001cc587de8ac4a5b58ab3a4c5fac65b91dd2b481c875b2e8044ee` |
