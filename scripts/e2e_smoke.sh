#!/usr/bin/env bash
# Hand check of the case flow against a live uvicorn engine.api:app.
#
# Creates a case, posts one fact, uploads a synthetic PDF generated in a temp
# directory, then requests gaps and export. The PDF is not a user file and
# contains no code text. Uploads stay in that temp directory.
#
# Gaps and export need the code database. When it is absent those two steps
# expect HTTP 503 {"detail":"code database not found"} and the script exits 0.
# With the database, export of this incomplete case is 409. A draft export is
# 200 only when the blank SCC form is on disk.
#
# Usage: scripts/e2e_smoke.sh
# Requires the engine dependencies (uvicorn, fastapi, reportlab, pypdf) on PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "python3 is required" >&2
  exit 1
fi

WORK="$(mktemp -d)"
UVICORN_PID=""
cleanup() {
  if [[ -n "$UVICORN_PID" ]]; then
    kill "$UVICORN_PID" 2>/dev/null || true
    wait "$UVICORN_PID" 2>/dev/null || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT

export BATATIS_FILES="$WORK/files"
export BATATIS_CASES="$WORK/cases.sqlite"
mkdir -p "$BATATIS_FILES"

PORT="$("$PY" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
BASE="http://127.0.0.1:${PORT}"

"$PY" -m uvicorn engine.api:app --host 127.0.0.1 --port "$PORT" --log-level warning \
  >"$WORK/uvicorn.log" 2>&1 &
UVICORN_PID=$!

ready=0
for _ in $(seq 1 50); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/cases/missing" || true)"
  if [[ "$code" == "404" ]]; then
    ready=1
    break
  fi
  if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
    echo "uvicorn exited before it accepted requests" >&2
    cat "$WORK/uvicorn.log" >&2 || true
    exit 1
  fi
  sleep 0.1
done
if [[ "$ready" -ne 1 ]]; then
  echo "uvicorn did not become ready" >&2
  cat "$WORK/uvicorn.log" >&2 || true
  exit 1
fi

"$PY" -c 'from reportlab.pdfgen import canvas; c=canvas.Canvas("'"$WORK"'/sheet.pdf"); c.drawString(36,72,"SYNTHETIC e2e attachment"); c.showPage(); c.save()'

json_field() {
  "$PY" -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

echo "create"
created="$(curl -sf -X POST "$BASE/cases" -H 'content-type: application/json' -d '{"title":"Synthetic e2e case"}')"
case_id="$(printf '%s' "$created" | json_field id)"
echo "case ${case_id}"

echo "facts"
curl -sf -X POST "$BASE/cases/${case_id}/facts" \
  -H 'content-type: application/json' \
  -d '{"field":"municipal_address","value":"100 Example Avenue, Edmonton","kind":"exact","status":"confirmed","source":{"type":"user_text","ref":"e2e-synthetic"}}' \
  >/dev/null

echo "upload"
uploaded="$(curl -sf -X POST "$BASE/cases/${case_id}/files" -F "file=@${WORK}/sheet.pdf;type=application/pdf")"
file_id="$(printf '%s' "$uploaded" | json_field id)"
file_name="$(printf '%s' "$uploaded" | json_field name)"
test "$file_name" = "sheet.pdf"
stored="${BATATIS_FILES}/${case_id}/${file_id}.pdf"
test -f "$stored"
cmp -s "$WORK/sheet.pdf" "$stored"
echo "stored bytes ${file_id} (${file_name})"

db_present="$("$PY" -c 'from engine.codes import default_db; print("yes" if default_db().is_file() else "no")')"

gaps_body="$WORK/gaps.json"
gaps_code="$(curl -s -o "$gaps_body" -w '%{http_code}' "$BASE/cases/${case_id}/gaps")"
if [[ "$db_present" == "no" ]]; then
  test "$gaps_code" = "503"
  "$PY" -c 'import json,sys; body=json.load(open(sys.argv[1])); assert body=={"detail":"code database not found"}; assert "/" not in open(sys.argv[1]).read()' "$gaps_body"
  echo "gaps: skipped, code database not built (503)"
  export_body="$WORK/export.json"
  export_code="$(curl -s -o "$export_body" -w '%{http_code}' -X POST "$BASE/cases/${case_id}/export")"
  test "$export_code" = "503"
  "$PY" -c 'import json,sys; body=json.load(open(sys.argv[1])); assert body=={"detail":"code database not found"}; assert "/" not in open(sys.argv[1]).read()' "$export_body"
  echo "export: skipped, code database not built (503)"
  echo "e2e smoke: create, facts, upload ran; gaps and export skipped"
  exit 0
fi

test "$gaps_code" = "200"
"$PY" -c 'import json,sys; body=json.load(open(sys.argv[1])); assert isinstance(body, list); assert "complies" not in open(sys.argv[1]).read().lower()' "$gaps_body"
echo "gaps: 200"

export_body="$WORK/export.json"
export_code="$(curl -s -o "$export_body" -w '%{http_code}' -X POST "$BASE/cases/${case_id}/export")"
test "$export_code" = "409"
"$PY" -c 'import json,sys; body=json.load(open(sys.argv[1])); assert body["detail"]["message"]=="export blocked; resolve these or export a draft"; assert body["detail"]["reasons"]; assert "complies" not in open(sys.argv[1]).read().lower()' "$export_body"
echo "export: 409"

form_present="$("$PY" -c 'from engine.export import form_path; print("yes" if form_path().is_file() else "no")')"
if [[ "$form_present" == "no" ]]; then
  echo "export 200: skipped, SCC form not present"
  echo "e2e smoke: create, facts, upload, gaps, export 409"
  exit 0
fi

draft_code="$(curl -s -D "$WORK/draft.headers" -o "$WORK/draft.pdf" -w '%{http_code}' \
  -X POST "$BASE/cases/${case_id}/export" -H 'content-type: application/json' -d '{"draft":true}')"
test "$draft_code" = "200"
grep -q '%PDF' "$WORK/draft.pdf"
grep -i 'content-disposition:.*DRAFT' "$WORK/draft.headers" >/dev/null
echo "export: 200 draft"
echo "e2e smoke: create, facts, upload, gaps, export 409, draft 200"
