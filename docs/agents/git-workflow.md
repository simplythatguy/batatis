# Git and environments: `dev` and `main` only

GitHub holds exactly two upstream branches. Vercel deploys only `main` (user decision, 2026-10-24).

| Branch | Role | Vercel | Who changes it |
| --- | --- | --- | --- |
| `dev` | Shared integration source | No deployment | Verified agent landings and teammate contributions |
| `main` | Production | `batatis-vert.vercel.app` | The user, by merging the release PR |

Locally the app uses web port **3000** and engine port **8000**.

## The flow

1. **Work locally** in an isolated checkout or worktree. Agent feature branches stay local.
2. **Verify locally** with `scripts/verify.sh` and checks appropriate to the change. Set up CodeDB and real PostgreSQL for affected areas; skipped prerequisites are coverage limits. Visible changes need actual app inspection and saved evidence. Local verification is required even when GitHub Actions runs.
3. **Land on `dev`** through `scripts/land.sh --note "what changed and how to verify it"`. The parent integrates, verifies and fast-forwards `HEAD:dev`. The script maintains the single release PR.
4. **The user tests locally and approves the release**, then merges `dev → main` with **Create a merge commit**. Vercel deploys that production commit. Squash/rebase merges make the two branches diverge.

Teammate PRs target `dev`; the production release stays separate. To keep the upstream at two branches, a teammate can contribute from `dev` in their fork. GitHub write permission controls who can merge those contribution PRs. Agents still use the parent landing path above.

## Rules

- **Keep upstream branches `dev` and `main`.** Agent branches remain local; agents open only the standing release PR. Install the pre-push hook once per clone with `scripts/install-git-hooks.sh`; it covers that clone's worktrees.
- **The user owns production approval and merging.** Agents never push/merge `main`, force-push, or delete `dev`/`main`. After a release, retain `dev`.
- **One release PR, `dev → main`.** After landing, comment with the exact source, verification and local testing steps. Do not overwrite its description.
- **Push verified work only.** `dev` pushes run CI without a Vercel deployment. Batch related fixes; avoid WIP pushes or repeating an unchanged SHA.
- **Check ancestry before rebasing.** If `git merge-base --is-ancestor origin/dev HEAD` succeeds, push without rebasing. Otherwise use `git -c rebase.updateRefs=false rebase --rebase-merges origin/dev`, resolve conflicts and verify the resulting source. Preserve merge history.
- **Use the configured safeguards.** Local hooks do not establish server-side protection. Check GitHub's actual branch rules separately; keep automated PR fixes from bypassing verified landing or production approval.
- **Use HTTPS in agent sandboxes.** `scripts/land.sh` fetches/pushes through the existing `gh` credential. Do not put credentials in command arguments or repository files.
- **Respect port ownership.** Use `scripts/local-app.sh status|start|stop|wait`. If 3000/8000 is busy, wait for its owner; do not start an alternative app port or stop another owner's server. A running user preview stays available during source-only work.
- **Children return source and evidence to the parent.** They do not push or open PRs. Keep durable handoffs in the recovery backup or checkout, not solely in temporary storage.

## Vercel controls

The `abdelwaly-projects/batatis` project must track **Production Branch = `main`**, with **preview deployments disabled**. `vercel.json` enables only `main` and disables every other branch. `dev` has no hosted test site; the former stable dev alias is retired. Keep historical deployments and database records preserved.

Changing this policy does not publish the restored source to production. The user still approves and merges the release PR. See [deployment operations](../deploy.md).

## Preserved work

Old branches/PRs and restoration pointers are recorded in [parked work](parked-work.md). Source preservation does not approve unverified experiments or a production release.
