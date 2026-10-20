#!/usr/bin/env bash
# Plain-checkout entry point for the keyed completeness benchmark.
# From the repository root, with only OPENAI_API_KEY already in the environment:
#   bash scripts/bench_completeness.sh
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is not set. Export it in the environment and rerun. The key is not printed." >&2
  exit 2
fi

if [[ ! -x .venv/bin/python ]]; then
  venv_log="$(mktemp)"
  if ! python3 -m venv .venv >"$venv_log" 2>&1; then
    rm -rf .venv
    if ! python3 -m venv --without-pip .venv >>"$venv_log" 2>&1; then
      cat "$venv_log" >&2
      echo "python3 -m venv failed. Install python3-venv for this Python and rerun. The key is not printed." >&2
      rm -f "$venv_log"
      exit 1
    fi
  fi
  rm -f "$venv_log"
fi

if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  bootstrap="$(mktemp)"
  python3 - "$bootstrap" <<'PY'
import sys, urllib.request
urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", sys.argv[1])
PY
  .venv/bin/python "$bootstrap" --disable-pip-version-check >/dev/null
  rm -f "$bootstrap"
fi

.venv/bin/python -m pip install --disable-pip-version-check -q -r engine/requirements.txt

export BATATIS_LLM_PROVIDER=openai
exec .venv/bin/python -m evals_dev.completeness_eval --live --repeats 3
