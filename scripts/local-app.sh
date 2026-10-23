#!/bin/bash
# The only way to run the app locally: web on 3000, engine on 8000. Nothing else.
# Usage: scripts/local-app.sh start | stop [--force] | status | wait [seconds]
#   status  who holds 3000/8000 (exit 1 if either is busy)
#   start   start both from THIS worktree; refuses if either port is busy (exit 3)
#   stop    stop what this worktree started; never touches another worktree's servers unless --force
#   wait    block until both ports are free (default 600 s), then start
# Docs: docs/agents/git-workflow.md
set -uo pipefail

WEB_PORT=3000
ENGINE_PORT=8000
for tool in lsof curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "local-app: $tool is required (it detects which process holds a port / checks readiness)" >&2; exit 2; }
done
root=$(git rev-parse --show-toplevel)
logs="$root/.data/local-app"

listener() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -1; }
cwd_of() { lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'; }

describe() {
  local pid
  pid=$(listener "$1")
  if [ -z "$pid" ]; then printf 'port %s: free\n' "$1"; return 0; fi
  printf 'port %s: BUSY  pid %s  up %s  cwd %s\n           %s\n' "$1" "$pid" \
    "$(ps -o etime= -p "$pid" | tr -d ' ')" "$(cwd_of "$pid")" "$(ps -o command= -p "$pid" | cut -c1-110)"
  return 1
}

status() {
  local busy=0
  describe $WEB_PORT || busy=1
  describe $ENGINE_PORT || busy=1
  return $busy
}

python_bin() {
  local common
  if [ -x "$root/.venv/bin/python" ]; then echo "$root/.venv/bin/python"; return; fi
  common=$(cd "$(git rev-parse --git-common-dir)" && pwd)
  if [ -x "$(dirname "$common")/.venv/bin/python" ]; then echo "$(dirname "$common")/.venv/bin/python"; return; fi
  command -v python3
}

# Give each server its own session. nohup alone ignores SIGHUP but leaves it in an agent command's
# process group, which some runners terminate after the start command returns.
detached() {
  "$py" -c 'import subprocess, sys; subprocess.Popen(sys.argv[1:], stdin=subprocess.DEVNULL, start_new_session=True)' "$@"
}

stop() {
  local force=0 port pid dir ppid i
  [ "${1:-}" = "--force" ] && force=1
  for port in $WEB_PORT $ENGINE_PORT; do
    pid=$(listener "$port")
    [ -n "$pid" ] || continue
    dir=$(cwd_of "$pid")
    case "$dir" in
      "$root"|"$root"/*) ;;
      *)
        if [ $force = 0 ]; then
          echo "local-app: port $port belongs to another worktree ($dir); leaving it. Use --force only if its owner is gone." >&2
          continue
        fi
        ;;
    esac
    ppid=$(ps -o ppid= -p "$pid" | tr -d ' ')
    kill "$pid" 2>/dev/null
    if ps -o command= -p "$ppid" 2>/dev/null | grep -q -E 'npm (exec|run)'; then kill "$ppid" 2>/dev/null; fi
    for i in 1 2 3 4 5; do [ -z "$(listener "$port")" ] && break; sleep 1; done
    [ -n "$(listener "$port")" ] && kill -9 "$pid" 2>/dev/null
    echo "local-app: stopped the server on port $port"
  done
  return 0
}

start() {
  local i
  local env_args=()
  if ! status; then
    echo "local-app: not starting; a port is in use. Ask the owner to stop it, or run: scripts/local-app.sh wait" >&2
    return 3
  fi
  mkdir -p "$logs"
  if [ ! -d "$root/web/node_modules" ]; then
    echo "local-app: installing web dependencies (npm ci)..."
    (cd "$root/web" && npm ci >"$logs/npm-ci.log" 2>&1) || { echo "local-app: npm ci failed; see $logs/npm-ci.log" >&2; return 1; }
  fi
  # Each worktree keeps its own cases so servers never share or wipe one another's data.
  # The helper exits after spawning a new session; all server output goes to files, so it also releases
  # the caller's output pipe: `scripts/local-app.sh start | tail` returns as soon as the servers are up.
  py=$(python_bin)
  # Only Uvicorn loads the worktree's server configuration. This never executes
  # shell syntax or exports provider credentials into the web process.
  if [ -f "$root/.env" ]; then
    if ! "$py" -c 'import dotenv' >/dev/null 2>&1; then
      echo "local-app: install engine/requirements.txt in the selected Python environment before loading .env" >&2
      return 2
    fi
    env_args=(--env-file "$root/.env")
  fi
  ( cd "$root" && BATATIS_CASES="${BATATIS_CASES:-$root/.data/cases.sqlite}" detached "$py" -m uvicorn engine.api:app \
      "${env_args[@]}" --host 127.0.0.1 --port $ENGINE_PORT >"$logs/engine.log" 2>&1 </dev/null )
  ( cd "$root/web" && detached npm run dev -- --port $WEB_PORT --strictPort --host 127.0.0.1 >"$logs/web.log" 2>&1 </dev/null )
  for i in $(seq 1 60); do
    if curl -fsS -m 3 -o /dev/null "http://127.0.0.1:$ENGINE_PORT/docs" 2>/dev/null && curl -fsS -m 3 -o /dev/null "http://127.0.0.1:$WEB_PORT/" 2>/dev/null; then
      echo "local-app: up. Web http://localhost:$WEB_PORT   Engine http://127.0.0.1:$ENGINE_PORT/docs   logs $logs"
      return 0
    fi
    sleep 1
  done
  echo "local-app: did not come up within 60 s; stopping it. Logs: $logs" >&2
  stop
  return 1
}

wait_free() {
  local limit=${1:-600} waited=0
  while ! status >/dev/null; do
    if [ "$waited" -ge "$limit" ]; then
      echo "local-app: still busy after ${limit}s:" >&2
      status >&2
      return 3
    fi
    sleep 10
    waited=$((waited + 10))
  done
  start
}

case "${1:-status}" in
  start) start ;;
  stop) shift; stop "$@" ;;
  status) status ;;
  wait) shift; wait_free "$@" ;;
  *) sed -n '2,8p' "$0" >&2; exit 2 ;;
esac
