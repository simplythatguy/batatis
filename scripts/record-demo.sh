#!/usr/bin/env bash
# Record a Batatis walkthrough video. See docs/demo/record.md.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
if [[ ! -d scripts/demo-record/node_modules/playwright-core ]]; then
  npm ci --prefix scripts/demo-record
fi
exec node scripts/demo-record/record.mjs "$@"
