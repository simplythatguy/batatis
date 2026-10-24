# Development baseline and remaining recovery

The `dev` branch is the shared starting point for teammate coding. Production changes only after the user tests the release PR and approves its merge.

## Included in this baseline

- Restored applicant workspace, assistant and voice interface, comments navigation, and current-step labels.
- Per-application saved code selections and application-switch protections.
- Compatible assistant/document/navigation backend contracts.
- PDF field-visibility repair and PostgreSQL connection-option preservation.
- Elephant 1 scoring adapter through OpenRouter, with a separate uncalibrated scoring version and no automatic article commitment.
- Simplified README, one local web/engine pair, and the two-branch release workflow.

The runtime is based on the recovered core at `12d44b11`. That source passed 384 web tests and 3,170 backend/evaluation tests with owned PostgreSQL; only two opt-in live-provider tests skipped. The publication snapshot is verified separately before its fast-forward to `dev`. A tiny synthetic real Elephant adapter check passed; full-corpus inference and calibration remain unverified.

## Still being verified separately

The newer applicant/officer journey composition and its browser repairs are not part of this first baseline. They include exact-save submission, expanded professional handoff, correspondence/history, and reviewer continuity.

U1 restoration is also in progress. The supplied seven-page form and dynamic native rows are absent from this baseline. Known PDF-reading defects remain around non-text or invisible attachment answers and uncertainty in legal/objective/function cells. These require matched source restoration and regression checks. This baseline is for development; it is not a completed reader recovery or production signoff.

All original commits and unfinished changes remain preserved. No failed broad composite was merged to create this baseline. The remaining verified slices will follow through `dev` after integration, checks, and independent review.

## Start coding

Clone `dev` and follow the [local setup guide](local-development.md). Work in a separate local checkout or worktree. GitHub retains only `dev` and `main`; keep feature branches local.

Run `scripts/verify.sh`, then use `scripts/land.sh` to land verified changes on `dev`. Keep the single `dev` to `main` release PR. The [Git workflow](agents/git-workflow.md) defines the full process.
