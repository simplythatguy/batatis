# Git and environments: `dev` and `main` only

GitHub holds exactly two branches. This binds every agent, child agent and tool.

| Branch | Role | Vercel | Who changes it |
| --- | --- | --- | --- |
| `dev` | The user's test site | Preview, stable URL `batatis-git-dev-abdelwaly-projects.vercel.app` (Vercel login) | Agents, by fast-forward push of verified work |
| `main` | Production | Production, `batatis-vert.vercel.app` | Only the user, by merging the release PR |

Locally the app runs on **one** port pair: web on `3000`, engine on `8000`. Nothing else.

## The flow

1. **Work locally** in your own worktree on a local branch with any name. It stays local: never push it, never open a PR from it.
2. **Verify locally.** `scripts/verify.sh` runs what CI runs (GitHub Actions cannot gate while the account billing is failing, so this is the gate). Tests that need the built code database or `TEST_DATABASE_URL` (a real Postgres) skip unless you set them up, and the script says so: run them yourself for the areas you touched. Add your own feature checks. For anything visible, run the app with `scripts/local-app.sh start` and look at it.
3. **Land on `dev`.** `scripts/land.sh --note "what changed, what to check"` puts your work on top of `origin/dev`, re-verifies, pushes `HEAD:dev` fast-forward only, and makes sure the one release PR exists.
4. **The user tests the dev site** and merges the release PR `dev → main` with **Create a merge commit** (never squash or rebase: that makes `main` diverge from `dev`). Nothing else reaches `main`.

## Rules

- **Only `dev` and `main` exist on GitHub.** No feature branches, no per-feature PRs, no tags. A `pre-push` hook (`scripts/install-git-hooks.sh`, once per clone) refuses anything but a fast-forward of `dev`.
- **GitHub cannot enforce this for us.** Branch protection and rulesets return 403 on this private repo (free plan), and "Automatically delete head branches" is off (checked 2026-10-22). The local hook plus these rules are the guard; if the repo is upgraded or made public, protect `dev` and `main` against force-push and deletion and keep `main` PR-only. Bots can also commit to the release PR's branch (`dev`): CodeRabbit's "Auto-fix PRs" rule is a dashboard setting; keep it off for the release PR so nothing reaches `dev` outside `scripts/land.sh`.
- **Never** push or merge to `main`, force-push, or delete `dev` or `main`. After the user merges the release PR, nobody clicks GitHub's "Delete branch": that would delete `dev`.
- **One release PR, `dev → main`.** `scripts/land.sh` opens it when missing. After landing, comment on it: what changed, how you verified it, what the user should check on the dev site. Do not edit its description (parallel agents overwrite each other).
- **Push verified work only.** Each push to `dev` is a Vercel deployment, and the Hobby plan allows about 100 a day. No WIP, no re-pushing an unchanged SHA, batch small fixes.
- **Check ancestry before rebasing.** `git merge-base --is-ancestor origin/dev HEAD` true means nothing to rebase: push. Otherwise `git -c rebase.updateRefs=false rebase --rebase-merges origin/dev`. A plain `git rebase origin/dev` flattens merge commits and replays old history even when `dev` is already an ancestor, which produces old conflicts. Resolve conflicts yourself, then re-verify the rebased tree.
- **SSH `origin` fails in agent sandboxes.** Fetch and push over HTTPS with the `gh` credential, as `scripts/land.sh` does:
  `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push https://github.com/simplythatguy/batatis.git HEAD:refs/heads/dev`
- **Ports.** `scripts/local-app.sh status|start|stop|wait` manages `3000`/`8000`. If busy, find the owner (`status`) and wait for them. Never pick another port, never use `--port` variants, stop what you start. A parent that waits for a child's verification must release `3000`/`8000` first.
- **Children never push or open PRs.** The parent integrates and lands.
- **Local scratch** (`/tmp`, `~/.batatis-*`) is not durable: keep handoffs in the worktree or the user's backup folder, not only in `/tmp`.

## Setting up a new clone or worktree

```sh
scripts/install-git-hooks.sh   # once per clone; covers all its worktrees
```

## Vercel environment settings

The Vercel project (`abdelwaly-projects/batatis`) must have **Production Branch = `main`** (Settings, Environments, Production, Branch Tracking; older dashboards: Settings, Git), with **Preview deployments enabled** for `dev`. Both settings were corrected and read back on 2026-10-23. Changing branch tracking preserves the currently served production build until `main` deploys. `vercel.json` lets only `dev` and `main` deploy; keep that allowlist. See `docs/deploy.md`.

## Where parked work went

Stale branches and PRs closed during the 2026-10-22 consolidation, with how to restore each, are listed in `docs/agents/parked-work.md`.
