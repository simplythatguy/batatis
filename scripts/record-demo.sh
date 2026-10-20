#!/usr/bin/env bash
# Record a Batatis walkthrough video. See docs/demo/record.md.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -d "$root/scripts/demo-record/node_modules/playwright-core" ]]; then
  npm ci --prefix "$root/scripts/demo-record"
fi
exec node "$root/scripts/demo-record/record.mjs" "$@"
