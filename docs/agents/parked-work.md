# Parked work

On 2026-10-22 GitHub was reduced to two branches (`dev`, `main`). 51 branches that were already fully merged were deleted; their commits are in the history of `dev` and `main`. The 31 branches below were **not** merged. Their PRs were closed and the branches deleted, and nothing was lost. On 2026-10-24 `dev` was retired as well; all of its commits are in the history of `main`, which is now the only permanent branch:

- A PR's head stays fetchable from GitHub as `refs/pull/<N>/head`, even after the PR is closed and the branch deleted.
- Every branch, including the ones without a PR, is in a local backup bundle (`~/.t3/backups/batatis-20261022/t3-clone-all-refs.bundle`).

Restore a branch that had a PR into a local branch. To ship it, merge the latest `main` into it, verify, and open a pull request with `scripts/land.sh` (see `docs/agents/git-workflow.md`):

```sh
git fetch https://github.com/simplythatguy/batatis.git pull/<N>/head:parked/<name>
```

Restore any branch from the bundle:

```sh
git fetch ~/.t3/backups/batatis-20261022/t3-clone-all-refs.bundle refs/remotes/origin/<name>:parked/<name>
```

Rows marked **Freshest product line** or **Unlanded** need a decision. The rest is the 2026-10-20/21 line, 70 or more commits behind `dev` (most are 223 or more), and was superseded by the later WP-numbered work unless its note says otherwise.

| Branch | PR | Tip | Last commit | Subject | Note |
| --- | --- | --- | --- | --- | --- |
| `work/mvp-improvement-20261022` | #69 (was open) | `a8fb50c7b` | 2026-10-22 | fix(dev): forward API WebSocket upgrades | **Freshest product line.** Stack #62 → #67 → #68 → #69, 140 commits ahead of `dev`, 0 behind (a pure fast-forward). Not verified or landed. The same commits sit in the local worktrees. |
| `feat/wp35-rules-packs-ui` | #68 (was open) | `f16d13239` | 2026-10-22 | test: keep refusal harness compatible with applicant deck extras | Part of the freshest stack (see `work/mvp-improvement-20261022`). |
| `feat/wp16-accuracy` | #67 (was open) | `a93e29bdf` | 2026-10-22 | Merge refusal correspondence review fixes | Part of the freshest stack (see `work/mvp-improvement-20261022`). |
| `feat/wp36-officer-ui` | #62 (was open) | `675a01852` | 2026-10-22 | fix: preserve refusal correspondence and refresh open-file notices | Part of the freshest stack (see `work/mvp-improvement-20261022`). |
| `feat/wp10-11-evals` | #58 (was open) | `6a4279525` | 2026-10-21 | evals: ledger after the connection experiments | WP-10/11/12 Code ID benchmark harness and results. 16 ahead, 11 behind `dev`; its local worktree also had 8 uncommitted files. |
| `backend/spend-cap` | #41 (was open) | `13ab58277` | 2026-10-20 | fix: require coherent chat usage before refunding reservations | **Unlanded and still needed.** Total OpenAI spend cap (`engine/spend.py`, `engine/openai_only.py`, tests). `docs/deploy.md` makes it the go-live gate for live OpenAI; `dev` only has the daily ledger in `engine/llm_gate.py`. Port it onto current `main` before enabling `BATATIS_LIVE`. |
| `backend/answerable-gaps` | #23 (closed) | `2ca778bdd` | 2026-10-20 | Label description scores as agent-labelled, and note file_id is unchecked. |  |
| `backend/calgary-notice-casec-gold` | #40 (was open) | `db83f841a` | 2026-10-20 | Merge branch 'dev' into backend/calgary-notice-casec-gold | Calgary form notice and Case C smoke-alarm gold. May be a head start for WP-44 (Calgary form). |
| `backend/case-api` | #21 (was open) | `7bb0e3ab1` | 2026-10-20 | Skip the smoke upload when the files route answers 404 or 405. |  |
| `backend/case-api-followups` | #44 (was open) | `5d39244a6` | 2026-10-20 | Parse Mira's NailBase description and keep the sheathing card off it. |  |
| `backend/completeness-pipeline` | #11 (was open) | `006e1fcf5` | 2026-10-20 | fix: restore completeness API contracts and CI fixtures |  |
| `backend/export-appendix` | #25 (was open) | `a97075424` | 2026-10-20 | Add appendix explainers and the Appendix 1 export facts. |  |
| `backend/fact-extraction` | #36 (was open) | `1eab388c8` | 2026-10-20 | Write a confirmed permit number into the SCC form's Permit field. |  |
| `backend/gap-scoping` | #30 (was open) | `64b4a1ea3` | 2026-10-20 | State evidence gaps in plain words and skip no-row article sentences. |  |
| `backend/identify-api` | #12 (was open) | `b4fcd3329` | 2026-10-20 | Route identify LLM calls through the spend gate and clip served quotes. |  |
| `backend/identify-keyed-results` | #43 (was open) | `669034290` | 2026-10-20 | docs: define the keyed identify metrics and explain variant c recall |  |
| `backend/search-recall` | #33 (was open) | `4107bf635` | 2026-10-20 | Look up a typed provision id and fold firestop spellings. |  |
| `cursor/demo-recorder-21a8` | #28 (was open) | `08f4b4ab7` | 2026-10-20 | Mark the Section D still pending while its header is the Application screen. |  |
| `cursor/demo-video-script-1e38` | #20 (closed) | `3fdba8394` | 2026-10-20 | Correct the identify still's gold-case count. |  |
| `cursor/env-harden-opus-pending-f0b6` | #2 (was open) | `82093d2ff` | 2026-10-20 | Harden clone-ready env while Opus seal blocked |  |
| `docs/nrc-no-word-cap` | #42 (was open) | `21020e0eb` | 2026-10-20 | docs: scope NRC attribution to the engine and the PDF appendix |  |
| `docs/plans-v2` | #32 (closed) | `3f4faa30d` | 2026-10-20 | docs: plans and pitch deck round 5 |  |
| `ops/completeness-b-integration-r2-20261021` | none | `d7577b2d1` | 2026-10-20 | style: trim trailing bulletin helper blank line | No PR. Earlier step of the same line as `ops/completeness-b-pending-r4-20261021`. |
| `ops/completeness-b-pending-r4-20261021` | none | `8a91889b5` | 2026-10-20 | fix: expose pending confirmation task on acceptable-path report | No PR. Variant-B completeness work; its read-only report endpoint was ported into `dev` (`docs/api/package-review.md`). |
| `ops/completeness-b-policy-fix-r3-20261021` | none | `fa9e10635` | 2026-10-20 | docs: clarify current completeness screen and provenance contract | No PR. Earlier step of the same line as `ops/completeness-b-pending-r4-20261021`. |
| `ops/flow-integration-r1-20261021` | none | `cd7fe44e4` | 2026-10-20 | test: align public evidence deletion with versioned CAS contract | No PR. One test commit. |
| `research/data-nerd-2026-10-20` | #35 (closed) | `b4d44df25` | 2026-10-20 | research: exclude unclipped NRC quotes from the Data Nerd set |  |
| `research/data-nerd-2026-10-20-clean` | #39 (was open) | `9e8ff5311` | 2026-10-20 | research: cite NRC on each code quote and drop box paths |  |
| `ui/code-id` | #46 (was open) | `f62177412` | 2026-10-20 | docs: Code ID before/after screenshots (1440x900, 390x844) |  |
| `ui/minimal-redesign` | #45 (was open) | `0ab1dfd06` | 2026-10-20 | BAT-62 PR 1 WIP: redesign in progress, plus spec and after-v3 mockups (wrap-up c |  |
| `wip/demo-script-final` | none | `94f4af33d` | 2026-10-20 | Save the demo script against PR #16 at 579cd2c. | No PR. Demo script saved against PR #16. |
