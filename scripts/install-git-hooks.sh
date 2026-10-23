#!/bin/sh
# Install the Batatis git hooks into this clone's shared hooks directory, which covers every worktree of the clone.
# Run once per clone. Docs: docs/agents/git-workflow.md
set -eu
root=$(git rev-parse --show-toplevel)
hooks=$(cd "$(git rev-parse --git-common-dir)" && pwd)/hooks
mkdir -p "$hooks"
for h in pre-push; do
  cp "$root/scripts/git-hooks/$h" "$hooks/$h"
  chmod +x "$hooks/$h"
  echo "installed $hooks/$h"
done
