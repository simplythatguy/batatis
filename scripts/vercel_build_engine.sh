#!/bin/sh
# Build the code database into the engine bundle. Prefer scripts/build_codedb.sh
# (backend/codedb-repro). Otherwise fetch pinned PDFs and run the codedb builder.
# A missing sqlite fails the build. Do not commit the PDF or the sqlite.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
# fonttools is required for the pinned page-text sha256. It is removed after the extract.
python -m pip install -q 'fonttools>=4.39'
if [ -f "$ROOT/scripts/build_codedb.sh" ]; then
  echo "engine build: scripts/build_codedb.sh"
  bash "$ROOT/scripts/build_codedb.sh"
else
  echo "engine build: scripts/build_codedb.sh is absent; fetching sources then python -m codedb build"
  python "$ROOT/scripts/fetch_sources.py"
  python -m codedb build
fi
if [ ! -s "$ROOT/codedb/build/codedb.sqlite" ]; then
  echo "engine build failed: codedb/build/codedb.sqlite is missing. Refusing to deploy without a sha256-checked code database. Do not commit the NRC PDF or the sqlite." >&2
  exit 1
fi
echo "engine build: codedb/build/codedb.sqlite is present"
python "$ROOT/scripts/fetch_sources.py" --scc-form
if [ ! -s "$ROOT/codedb/build/SCC-Variance-Form.pdf" ]; then
  echo "engine build failed: codedb/build/SCC-Variance-Form.pdf is missing. Do not commit the SCC form." >&2
  exit 1
fi
python -m pip uninstall -y fonttools >/dev/null 2>&1 || true
echo "engine build: SCC variance form sha256-checked"
