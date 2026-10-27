#!/bin/bash
# Run the local gate before a pull request into main; GitHub Actions supplements these checks.
# Docs: docs/agents/git-workflow.md
# Usage: scripts/verify.sh [--web] [--engine] [--desktop]     (default: all)
# UI changes: also run `node evals/ui-artifacts/smoke.mjs` against the app from scripts/local-app.sh.
set -euo pipefail

root=$(git rev-parse --show-toplevel)
cd "$root"

want_web=0
want_engine=0
want_desktop=0
for a in "$@"; do
  case "$a" in
    --web) want_web=1 ;;
    --engine) want_engine=1 ;;
    --desktop) want_desktop=1 ;;
    *) echo "verify: unknown option $a" >&2; exit 2 ;;
  esac
done
if [ $want_web = 0 ] && [ $want_engine = 0 ] && [ $want_desktop = 0 ]; then want_web=1; want_engine=1; want_desktop=1; fi

step() { printf '\n== %s ==\n' "$*"; }

step "agent skills: pinned source and portable entrypoints"
python3 scripts/pstack_skills.py --check

if [ $want_web = 1 ]; then
  [ -d web/node_modules ] || { step "web: install"; (cd web && npm ci); }
  step "web: typecheck"; (cd web && npm run typecheck)
  step "web: unit tests"; (cd web && npm test)
  step "web: unwrap test"; (cd web && npm run test:unwrap)
  step "web: production build"; (cd web && npm run build)
  step "web: no code database in the web output"
  found=$(find web/dist web/public -name '*.sqlite' -print 2>/dev/null || true)
  if [ -n "$found" ]; then
    printf '%s\n' "$found" >&2
    echo "verify: a code database must not ship in web/dist or web/public." >&2
    exit 1
  fi
fi

if [ $want_engine = 1 ]; then
  step "engine: tests (tests that need the code database or TEST_DATABASE_URL skip unless you set them up; -rs lists them. Run those for the areas you touched)"
  common=$(cd "$(git rev-parse --git-common-dir)" && pwd)
  py=""
  for candidate in "$root/.venv/bin/python" "$root/.venv/Scripts/python.exe" \
    "$(dirname "$common")/.venv/bin/python" "$(dirname "$common")/.venv/Scripts/python.exe"; do
    if [ -x "$candidate" ]; then
      py="$candidate"
      break
    fi
  done
  [ -n "$py" ] || py=$(command -v python3)
  "$py" -m pytest -q engine/tests codedb/tests evals_dev -rs
fi

if [ $want_desktop = 1 ]; then
  [ -d desktop/node_modules ] || { step "desktop: install"; (cd desktop && npm ci); }
  step "desktop: typecheck"; (cd desktop && npm run typecheck)
  step "desktop: host and adapter tests"; (cd desktop && npm test)
  step "desktop: main and preload build"; (cd desktop && npm run build)
fi

step "secrets scan"
if command -v gitleaks >/dev/null 2>&1; then
  base=$(git rev-parse --verify -q origin/main || true)
  if [ -n "$base" ]; then
    gitleaks detect --redact --exit-code=2 --log-opts="$base..HEAD"
  else
    gitleaks detect --redact --exit-code=2
  fi
else
  echo "gitleaks is not installed (brew install gitleaks); skipping the scan CI would run."
fi

printf '\nverify: all selected checks passed\n'
