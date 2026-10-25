#!/bin/bash
# Verify the current work branch and open or update its pull request into main.
# Docs: docs/agents/git-workflow.md
# Usage: scripts/land.sh [--title TEXT] [--body-file FILE] [--note TEXT] [--skip-verify] [--dry-run]
# --dry-run fetches and checks the push without changing branches or pull requests.
set -euo pipefail

REPO=simplythatguy/batatis
URL=${BATATIS_LAND_URL:-https://github.com/$REPO.git}
title=""
body_file=""
note=""
skip_verify=0
dry=0
while [ $# -gt 0 ]; do
  case "$1" in
    --title) title=${2:?--title needs text}; shift 2 ;;
    --body-file) body_file=${2:?--body-file needs a file}; shift 2 ;;
    --note) note=${2:?--note needs text}; shift 2 ;;
    --skip-verify) skip_verify=1; shift ;;
    --dry-run) dry=1; shift ;;
    *) echo "land: unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ -n "$body_file" ]; then
  if [ ! -f "$body_file" ]; then
    echo "land: body file not found: $body_file" >&2
    exit 1
  fi
  body_file="$(cd "$(dirname "$body_file")" && pwd)/$(basename "$body_file")"
fi

root=$(git rev-parse --show-toplevel)
cd "$root"

# The SSH origin fails in agent sandboxes; use HTTPS with the gh credential.
g() { git -c credential.helper= -c 'credential.helper=!gh auth git-credential' "$@"; }
say() { printf 'land: %s\n' "$*"; }

branch=$(git branch --show-current || true)
case "$branch" in
  ""|main|dev)
    echo "land: refusing to publish from main, dev or a detached HEAD; create a work branch with 'git switch -c <name>' from the latest main." >&2
    exit 1
    ;;
esac
if [ -n "$(git status --porcelain)" ]; then
  echo "land: commit or stash your changes first:" >&2
  git status --short >&2
  exit 1
fi

g fetch --quiet "$URL" '+refs/heads/main:refs/remotes/origin/main'

if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ]; then
  say "nothing to publish: HEAD equals origin/main"
  exit 0
fi

if ! git merge-base --is-ancestor origin/main HEAD; then
  if [ $dry = 1 ]; then
    say "dry run: would merge origin/main with git merge --no-edit origin/main"
  else
    say "merging origin/main into $branch"
    if ! git merge --no-edit origin/main; then
      echo "land: the merge stopped. Resolve any conflicts, run 'git add <resolved-files>' and 'git commit', then rerun scripts/land.sh. To cancel, run 'git merge --abort'." >&2
      exit 1
    fi
  fi
fi

if [ $dry = 0 ] && [ $skip_verify = 0 ]; then scripts/verify.sh; fi

set --
if [ $dry = 1 ]; then
  say "dry run: git push --dry-run HEAD:refs/heads/$branch"
  set -- --dry-run
fi
if ! g push "$@" "$URL" "HEAD:refs/heads/$branch"; then
  echo "land: push failed; see the error above. If the remote branch has commits you lack, run 'git pull --no-rebase origin $branch' on this branch, then rerun scripts/land.sh." >&2
  exit 1
fi

sha=$(git rev-parse --short HEAD)
subject=$(git log -1 --format=%s)
pr=$(gh pr list --repo "$REPO" --head "$branch" --base main --state open --json number,url \
  --jq '.[0] | select(. != null) | [.number, .url] | @tsv')
if [ -z "$pr" ]; then
  pr_title=${title:-$subject}
  pr_body_file=${body_file:-.github/pull_request_template.md}
  if [ $dry = 1 ]; then
    say "dry run: would create a pull request from $branch into main with title '$pr_title' and body file '$pr_body_file'"
    exit 0
  fi
  pr_url=$(gh pr create --repo "$REPO" --base main --head "$branch" --title "$pr_title" \
    --body-file "$pr_body_file")
  if [ -z "$body_file" ]; then
    say "fill in the pull request description in plain language under all three template sections: New features added, Improvements, and Bug Fixes. See docs/agents/git-workflow.md."
  fi
else
  IFS=$'\t' read -r pr_number pr_url <<< "$pr"
  set --
  if [ -n "$title" ]; then set -- "$@" --title "$title"; fi
  if [ -n "$body_file" ]; then set -- "$@" --body-file "$body_file"; fi
  if [ $# -gt 0 ]; then
    if [ $dry = 1 ]; then
      say "dry run: would update pull request #$pr_number with the supplied title or body file"
    else
      gh pr edit "$pr_number" --repo "$REPO" "$@"
    fi
  fi
fi
if [ $dry = 0 ] && [ -n "$note" ]; then
  body=$(printf '%s %s\n\n%s\n' "$sha" "$subject" "$note")
  gh pr comment "$pr_url" --repo "$REPO" --body "$body" >/dev/null
fi
if [ $dry = 0 ]; then say "pushed $sha to $branch"; fi
say "pull request: $pr_url"
