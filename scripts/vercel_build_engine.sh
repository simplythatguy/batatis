#!/bin/sh
# Build the code database into the engine bundle.
# Fetch pinned PDFs, check sha256, then `python -m codedb build`.
# A missing sqlite fails the build. Source PDFs and JSONL exports are removed
# afterwards so they are not shipped in the function. Do not commit the PDF or the sqlite.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
echo "engine build: fetching pinned sources then python -m codedb build"
python -m pip install -q 'fonttools>=4.39'
python "$ROOT/scripts/fetch_sources.py"
python -m codedb build
if [ ! -s "$ROOT/codedb/build/codedb.sqlite" ]; then
  echo "engine build failed: codedb/build/codedb.sqlite is missing. Refusing to deploy without a verified code database. Do not commit the NRC PDF or the sqlite." >&2
  exit 1
fi
if [ ! -s "$ROOT/reference/guides/SCC-Variance-Form.pdf" ]; then
  echo "engine build failed: reference/guides/SCC-Variance-Form.pdf is missing. Do not commit the SCC form." >&2
  exit 1
fi
# fonttools is only needed to extract page text. It is not part of the deployed function.
python -m pip uninstall -y fonttools >/dev/null 2>&1 || true
# The engine reads the sqlite and the SCC form. Page extracts and JSONL exports are build inputs only.
rm -rf "$ROOT/reference/codes" "$ROOT/reference/text" "$ROOT/codedb/build/export"
echo "engine build: codedb/build/codedb.sqlite is present ($(wc -c < "$ROOT/codedb/build/codedb.sqlite") bytes)"
echo "engine build: SCC variance form sha256 verified"
