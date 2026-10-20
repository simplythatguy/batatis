#!/usr/bin/env bash
# Run the keyed identify benchmark from a plain checkout.
# The director command is unchanged and still invokes .venv/bin/python directly.
# There is no root requirements.txt. This installs the engine and codedb files CI uses.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  if ! python3 -m venv .venv; then
    echo "python3 -m venv failed. Install python3-venv and run this script again." >&2
    exit 1
  fi
fi
.venv/bin/python -m pip install -q -r engine/requirements.txt -r codedb/requirements.txt
exec .venv/bin/python -m engine.identify.benchmark "$@"
