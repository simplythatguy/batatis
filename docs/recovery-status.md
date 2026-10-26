# Restored development source

`main` is the only permanent branch: production, the only Vercel deployment branch, and the starting point for all work. Work arrives as pull requests from short-lived branches, which the user tests locally and merges.

## Included

- Applicant workspace with Describe, Questions, Review and Application stages, the icon rail and application sidebar, typed assistant/upload Help, per-application saved article choices and application-switch guards. [The calm design system](design-system-calm.md) is the single design authority.
- Authorized, bounded typed-PDF excerpts with checked literal quotes, source pointers and explicit coverage limits; no whole-document or professional-authorship claim.
- Exact saved-revision submission, temporary editing lock during dispatch, professional handoff controls, evidence binding/downloads, resubmission history and read-only review/export.
- Officer decisions with displayed-version concurrency checks, terminal administrative refusal and appeal notice, separate decision/notices, message receipts/history and refresh continuity.
- Supplied seven-page variance form with dynamic attribution rows, complete long-value appendices and the original printed pages; legacy form support remains available.
- Conservative PDF field, attachment-passage, legal/objective/function and coordinator uncertainty. Unverified readings go to officer review with source pointers and do not become applicant answers or missing-item claims.
- Elephant 1 through OpenRouter with its own uncalibrated relevance version, fixed free-route/version checks and no automatic article commitment.
- Offline accuracy reports in `docs/accuracy/report.md` and `docs/accuracy/report.json`, with their generator and benchmark provenance. There is no shipped accuracy UI or public authentication exemption.
- Open Pstack workflows, Sol-only Fast subagents, one local port pair and `main` with short-lived pull-request branches.

Voice controls and transport, both accuracy UIs, the legacy Officer and Section C screen bodies, and `styles.css` are retired. Historical `#/officer` opens current Review; `#/references` and `#/section-c` open Application. The Code library's references link remains a backward alias. The current calm reviewer workspace and typed Help remain supported.

## Evidence and limits

Each publication must pass local verification and a fresh independent review; the release PR records the exact revision and checks. Browser checks use synthetic local records. Historical hosted development checks, before the main-only deployment decision, exercised save/reload and PDF export on the isolated Neon `preview/dev` branch. They do not establish current production behavior.

Live provider accuracy, full-corpus Elephant calibration, typed-PDF extraction quality, real device behavior and user/professional acceptance require their own evidence. Offline/mock checks and a small real adapter request do not establish those results. Batatis checks administrative completeness and never certifies design compliance, safety or equivalent performance.

The restoration preserved the original commits and unfinished work. The failed broad composite and unverified reader experiments were not imported wholesale. Retired product screens and voice transport are now removed from the running app; their history remains in Git.

## Start coding

Clone `main` and install the Git hook once per clone; it covers all of that clone's worktrees:

```bash
git clone https://github.com/simplythatguy/batatis.git
cd batatis
scripts/install-git-hooks.sh
```

Follow [local setup](local-development.md) in an isolated local checkout or worktree. Start a short-lived branch from the latest `main`. Run `scripts/verify.sh`, then let the parent open the pull request into `main` with `scripts/land.sh`. Only the user merges pull requests; never push directly to `main`. Follow the [Git workflow](agents/git-workflow.md), including ports 3000/8000 and user-only production approval.
