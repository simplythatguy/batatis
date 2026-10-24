# Restored development source

`dev` is the shared starting point for teammate coding and the user's test site. `main` is production. The single release PR records each verified publication; only the user merges it after testing.

## Included

- Applicant workspace, assistant/voice interface, current-stage labels, per-application saved article choices and application-switch guards.
- Exact saved-revision submission, temporary editing lock during dispatch, professional handoff controls, evidence binding/downloads, resubmission history and read-only review/export.
- Officer decisions with displayed-version concurrency checks, terminal administrative refusal and appeal notice, separate decision/notices, message receipts/history and refresh continuity.
- Supplied seven-page variance form with dynamic attribution rows, complete long-value appendices and the original printed pages; legacy form support remains available.
- Conservative PDF field, attachment-passage, legal/objective/function and coordinator uncertainty. Unverified readings go to officer review with source pointers and do not become applicant answers or missing-item claims.
- Elephant 1 through OpenRouter with its own uncalibrated relevance version, fixed free-route/version checks and no automatic article commitment.
- Simple README, Open Pstack workflows, Sol-only Fast subagents, one local port pair and two remote branches.

## Evidence and limits

Each publication must pass local verification and a fresh independent review; the release PR records the exact revision and checks. Browser checks use synthetic local records. Hosted save/reload and PDF checks use the isolated Neon `preview/dev` branch. Production remains separate.

Live provider accuracy, full-corpus Elephant calibration, real voice/device behavior and user/professional acceptance require their own evidence. Offline/mock checks and a small real adapter request do not establish those results. Batatis checks administrative completeness and never certifies design compliance, safety or equivalent performance.

All original commits and unfinished files remain preserved. The failed broad composite and unverified reader experiments were not imported wholesale. The restored source combines matched, tested slices; old work was not deleted to obtain a green gate.

## Start coding

Clone `dev` and install the Git hook once per clone; it covers all of that clone's worktrees:

```bash
git clone --branch dev https://github.com/simplythatguy/batatis.git
cd batatis
scripts/install-git-hooks.sh
```

Follow [local setup](local-development.md) in an isolated local checkout or worktree. GitHub keeps only `dev` and `main`; feature branches stay local. Run `scripts/verify.sh`, then let the parent land verified work on `dev` through `scripts/land.sh`. Only the user merges the release PR `dev → main`; never push directly to `main`. Follow the [Git workflow](agents/git-workflow.md), including ports 3000/8000 and user-only production approval.
