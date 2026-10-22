#!/bin/sh
# Hit a running engine and print one latency line per request.
# BASE_URL is the API origin. Local: http://127.0.0.1:8000
# Preview: https://<deployment>.vercel.app/api
# Usage: scripts/e2e_smoke.sh [BASE_URL]
# Each pass is labeled cold then warm so a preview URL can be timed twice.
set -eu
BASE=${1:-${BASE_URL:-http://127.0.0.1:8000}}
BASE=${BASE%/}
fail=0

# timed METHOD PATH LABEL OUTFILE [curl args...]
# Prints: LABEL METHOD PATH STATUS SECONDS
timed() {
  method=$1
  path=$2
  label=$3
  outfile=$4
  shift 4
  meta=$(curl -sS -o "$outfile" -w '%{http_code} %{time_total}' -X "$method" "$@" "$BASE$path") || meta='000 0'
  code=${meta%% *}
  secs=${meta##* }
  printf '%s %s %s %s %ss\n' "$label" "$method" "$path" "$code" "$secs" >&2
  if [ "$code" = "000" ]; then
    fail=1
  fi
  printf '%s' "$code"
}

run_pass() {
  label=$1
  out=$(mktemp)
  code=$(timed POST /cases "$label" "$out" -H 'content-type: application/json' -d '{"title":"smoke"}')
  if [ "$code" != "201" ]; then
    fail=1
    rm -f "$out"
    return
  fi
  id=$(sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$out" | head -n 1)
  rm -f "$out"
  got=$(timed GET "/cases/$id" "$label" /dev/null)
  if [ "$got" != "200" ]; then
    fail=1
  fi
  timed GET '/code/search?q=egress&limit=5' "$label" /dev/null >/dev/null
}

echo "e2e smoke $BASE"
run_pass cold
run_pass warm
exit "$fail"
