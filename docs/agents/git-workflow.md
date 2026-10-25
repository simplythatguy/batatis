# Git workflow: one `main` branch

GitHub keeps one permanent branch, `main` (user decision, 2026-10-24). Each batch of work happens on a short-lived branch that becomes a pull request into `main`. GitHub deletes the branch after the pull request merges. Vercel deploys only `main`.

| Branch | Role | Vercel | Who changes it |
| --- | --- | --- | --- |
| `main` | Production, and the starting point for all work | Deploys to `batatis-vert.vercel.app` | Only merged pull requests |
| Work branches | One batch of related work each | Not deployed | Their author, until the pull request merges |

`dev` was retired on 2026-10-24. Two permanent branches had to be kept in step after every release, and they kept drifting apart.

Locally the app uses web port **3000** and engine port **8000**.

## The flow

1. **Start a branch from the latest `main`**, in an isolated checkout or worktree. Give it a short name that says what the work is, such as `fix-intake-wording`.
2. **Verify locally** with `scripts/verify.sh` and the checks the change needs. Set up CodeDB and real PostgreSQL for affected areas; skipped prerequisites are coverage limits. Visible changes need actual app inspection and saved evidence. Local verification is required even though GitHub Actions also runs.
3. **Open or update the pull request** with `scripts/land.sh --body-file <description> --note "<technical details>"`. The script merges the latest `main` into the branch when needed, runs `scripts/verify.sh`, pushes the branch, and opens or updates its pull request into `main`.
4. **The user tests the pull request locally and merges it** with **Create a merge commit**, so `main` keeps the exact commits that were verified. GitHub then deletes the branch, and Vercel deploys `main`.

Teammates without write access fork the repository, push a branch to their fork, and open a pull request into `main`. The README's agent prompt covers this.

## Pull request descriptions

Every pull request into `main` uses [the PR template](../../.github/pull_request_template.md). Keep its three sections in order: **New features added:**, **Improvements:**, **Bug Fixes:**. This format takes precedence over generic PR-writing skills.

Use short bullets in everyday language. Explain what someone can do now, what is easier, or what problem is fixed. Describe changes to research or contributor tools as such; only describe an app feature when the app actually provides it. Keep every section and write "None." when it has no changes. Put technical details and verification results in comments.

When a branch gets more work, the coordinating parent updates the description so that it covers the whole pull request. Children return their changes and evidence through task output for the parent to include. Before editing, read the latest description and comments, and review all changes between `origin/main` and the branch. Keep accurate existing entries and user edits; add, combine, or correct bullets as needed. Re-read the description just before saving to catch someone else's update.

Find the branch's pull request and prepare a multiline draft:

```sh
pr=$(gh pr list --repo simplythatguy/batatis --base main --head "$(git branch --show-current)" --state open --json number --jq '.[0].number // empty')
gh pr view "$pr" --repo simplythatguy/batatis --comments
body=$(mktemp)
cp .github/pull_request_template.md "$body"
```

Edit the file at `$body` so it holds the finished description, then save it and read it back:

```sh
gh pr edit "$pr" --repo simplythatguy/batatis --body-file "$body"
gh pr view "$pr" --repo simplythatguy/batatis --json body --jq .body
```

Confirm that the saved description covers the whole pull request and has exactly the three sections. Updating a description does not approve or merge anything.

## Rules

- **`main` is the only permanent branch.** Never push to `main`; it changes only when a pull request is merged. Never delete `main`. Never recreate `dev`.
- **Keep work branches short-lived.** One batch of related work per branch. GitHub deletes the branch after its pull request merges.
- **The user owns production approval and merging.** Agents open and update pull requests. They merge one only when the user explicitly asks.
- **Push verified work only.** Pull requests into `main` run CI, and a merge into `main` triggers Vercel. Batch related fixes; avoid pushing work in progress.
- **Catch up by merging, never by rebasing.** Bring the latest `main` into a branch with `git merge origin/main` (`scripts/land.sh` does this). Rebasing a branch that is already on GitHub would need a force-push, and force-pushing is never allowed.
- **Install the pre-push hook** once per clone with `scripts/install-git-hooks.sh`. It covers that clone's worktrees. It refuses pushes to `main`, recreating `dev`, rewriting any branch, and tags.
- **Use HTTPS in agent sandboxes.** `scripts/land.sh` fetches and pushes through the existing `gh` credential. Do not put credentials in command arguments or repository files.
- **Respect port ownership.** Use `scripts/local-app.sh status|start|stop|wait`. If 3000 or 8000 is busy, wait for its owner; do not start the app on another port or stop another owner's server. A running user preview stays available during source-only work.
- **Children return source and evidence to the parent.** They do not push or open pull requests. Keep durable handoffs in the recovery backup or checkout, not only in temporary storage.

## GitHub settings

These settings enforce the rules on GitHub's side, where a local hook cannot reach:

- The default branch is `main`.
- **Automatically delete head branches** is on, so merged work branches disappear.
- Branch protection on `main` requires a pull request before merging, with no required approvals, blocks force-pushes and deletion, and applies to administrators too.

## Vercel controls

The `abdelwaly-projects/batatis` project tracks **Production Branch = `main`**, with **preview deployments disabled**. `vercel.json` enables only `main` and disables every other branch, so work branches never deploy. Keep historical deployments and database records preserved. See [deployment operations](../deploy.md).

## Preserved work

Old branches and pull requests, with restoration pointers, are recorded in [parked work](parked-work.md). Preserving source does not approve unverified experiments or a production release.
