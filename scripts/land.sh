#!/bin/bash
# Land verified work on dev: sit on top of origin/dev, re-verify, push HEAD to dev fast-forward only,
# and make sure the one release PR (dev -> main) exists. Docs: docs/agents/git-workflow.md
# Usage: scripts/land.sh [--note "what changed / what the user should test locally"] [--skip-verify] [--dry-run]
# --dry-run fetches and reports what it would do; it never rebases, verifies, pushes or opens a PR.
set -euo pipefail

REPO=simplythatguy/batatis
URL=https://github.com/$REPO.git
note=""
skip_verify=0
dry=0
while [ $# -gt 0 ]; do
  case "$1" in
    --note) note=${2:?--note needs text}; shift 2 ;;
    --skip-verify) skip_verify=1; shift ;;
    --dry-run) dry=1; shift ;;
    *) echo "land: unknown option: $1" >&2; exit 2 ;;
  esac
done

root=$(git rev-parse --show-toplevel)
cd "$root"

# The SSH origin fails in agent sandboxes; use HTTPS with the gh credential.
g() { git -c credential.helper= -c 'credential.helper=!gh auth git-credential' "$@"; }
say() { printf 'land: %s\n' "$*"; }

branch=$(git branch --show-current || true)
if [ "$branch" = "main" ]; then echo "land: refusing to land from main" >&2; exit 1; fi
if [ -n "$(git status --porcelain)" ]; then
  echo "land: commit or stash your changes first:" >&2
  git status --short >&2
  exit 1
fi

attempt=0
while :; do
  attempt=$((attempt + 1))
  if [ $attempt -gt 3 ]; then echo "land: dev kept moving; try again in a minute" >&2; exit 1; fi
  g fetch --quiet "$URL" '+refs/heads/dev:refs/remotes/origin/dev' '+refs/heads/main:refs/remotes/origin/main'

  if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/dev)" ]; then
    say "nothing to land: HEAD equals origin/dev"
    exit 0
  fi

  # Only rebase when needed. A plain `git rebase origin/dev` flattens merge commits and replays old
  # history even when origin/dev is already an ancestor, so check ancestry first.
  if git merge-base --is-ancestor origin/dev HEAD; then
    say "origin/dev ($(git rev-parse --short origin/dev)) is already an ancestor of HEAD: no rebase needed"
  elif [ $dry = 1 ]; then
    say "dry run: HEAD is not on top of origin/dev; would run: git -c rebase.updateRefs=false rebase --rebase-merges origin/dev"
  else
    say "putting your work on top of origin/dev (merge commits preserved)"
    if ! git -c rebase.updateRefs=false rebase --rebase-merges origin/dev; then
      echo "land: the rebase stopped on a conflict. Resolve it and run 'git rebase --continue' (or 'git rebase --abort'), then run land.sh again." >&2
      exit 1
    fi
  fi

  if [ $dry = 0 ] && [ $skip_verify = 0 ]; then scripts/verify.sh; fi

  if [ $dry = 1 ]; then
    say "dry run: git push --dry-run HEAD:dev"
    g push --dry-run "$URL" HEAD:refs/heads/dev
    break
  fi
  if g push "$URL" HEAD:refs/heads/dev; then break; fi
  # A failed push is a race only if dev actually moved. Anything else (credentials, network, the
  # pre-push hook) is not retryable and must not cost another full verification run.
  g fetch --quiet "$URL" '+refs/heads/dev:refs/remotes/origin/dev'
  if git merge-base --is-ancestor origin/dev HEAD; then
    echo "land: the push failed but dev did not move; see the output above (credentials, network or the pre-push hook)" >&2
    exit 1
  fi
  say "dev moved while verifying; starting over from the new origin/dev"
done

sha=$(git rev-parse --short HEAD)
subject=$(git log -1 --format=%s)
pr=$(gh pr list --repo "$REPO" --base main --head dev --state open --json number --jq '.[0].number // empty')
if [ -z "$pr" ]; then
  if [ $dry = 1 ]; then say "dry run: no open release PR; would open one"; exit 0; fi
  url=$(gh pr create --repo "$REPO" --base main --head dev --title "Release: dev → main" --body \
"The one standing release PR. GitHub has two branches: \`dev\` (shared integration source) and \`main\` (production).

Agents land locally verified work on \`dev\` and comment here with what changed and how to test it locally. Only \`main\` deploys to Vercel; preview deployments are disabled. The user approves and merges this PR with **Create a merge commit** after local testing. Keep the \`dev\` branch afterwards.

Process: docs/agents/git-workflow.md")
  pr=${url##*/}
  say "opened release PR #$pr"
fi
if [ $dry = 0 ]; then
  body=$(printf '**Landed `%s`**: %s\n\n%s\n' "$sha" "$subject" "${note:-(no note given)}")
  gh pr comment "$pr" --repo "$REPO" --body "$body" >/dev/null
  say "pushed $sha to dev"
fi
say "release PR: https://github.com/$REPO/pull/$pr"
