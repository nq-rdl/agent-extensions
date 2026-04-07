#!/bin/bash
# PreToolUse hook — ensures the pi-rpc server is running before pi_* MCP tools execute.
#
# 1. Health-checks the server; exits immediately if already running.
# 2. Uses flock to prevent concurrent startup races.
# 3. Resolves the platform-specific prebuilt binary from bin/.
# 4. Starts the server in the background and polls until healthy.

set -euo pipefail

# Drain stdin — Claude Code passes hook context that we don't need.
cat > /dev/null

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PORT="${PI_SERVER_PORT:-4097}"
SERVER_URL="${PI_SERVER_URL:-http://localhost:${PORT}}"
HEALTH_ENDPOINT="${SERVER_URL}/pirpc.v1.SessionService/List"

LOG_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/pi-rpc"
LOG_FILE="${LOG_DIR}/pi-server.log"
PID_FILE="${XDG_RUNTIME_DIR:-/tmp}/pi-server.pid"
LOCK_FILE="${XDG_RUNTIME_DIR:-/tmp}/pi-server.lock"

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

# ---------------------------------------------------------------------------
# Health check — curl the List endpoint with a short timeout
# ---------------------------------------------------------------------------
health_check() {
  curl -sf -m 2 \
    -H 'Content-Type: application/json' \
    -d '{}' \
    "${HEALTH_ENDPOINT}" > /dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Fast path — if server is already running, nothing to do
# ---------------------------------------------------------------------------
if health_check; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Resolve platform binary
# ---------------------------------------------------------------------------
resolve_binary() {
  local os arch
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"

  case "$arch" in
    x86_64)  arch="amd64" ;;
    aarch64) arch="arm64" ;;
  esac

  local bin_path="${PLUGIN_ROOT}/bin/pi-server-${os}-${arch}"
  if [[ -x "$bin_path" ]]; then
    echo "$bin_path"
    return 0
  fi

  echo "ensure-pi-server: no prebuilt binary for ${os}/${arch} at ${bin_path}" >&2
  return 1
}

BINARY="$(resolve_binary)" || exit 0

# ---------------------------------------------------------------------------
# Acquire lock — prevent concurrent startup from parallel hook invocations
# ---------------------------------------------------------------------------
mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"

if ! flock --nonblock 9; then
  # Another instance is starting the server — wait for it to become healthy
  for _ in $(seq 1 10); do
    sleep 0.5
    if health_check; then
      exit 0
    fi
  done
  echo "ensure-pi-server: timed out waiting for server started by another hook instance" >&2
  exit 1
fi

# Double-check after acquiring lock (another instance may have started it)
if health_check; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Start the server
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"

# Clean up stale PID file
if [[ -f "$PID_FILE" ]] && ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  rm -f "$PID_FILE"
fi

export PI_SERVER_PORT="$PORT"
export PI_DEFAULT_PROVIDER="${PI_DEFAULT_PROVIDER:-openai}"
export PI_DEFAULT_MODEL="${PI_DEFAULT_MODEL:-gpt-5.4}"

nohup "$BINARY" >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

# ---------------------------------------------------------------------------
# Poll until healthy (up to 5 seconds)
# ---------------------------------------------------------------------------
for _ in $(seq 1 10); do
  sleep 0.5
  if health_check; then
    exit 0
  fi
done

echo "ensure-pi-server: server started but health check failed after 5s — check ${LOG_FILE}" >&2
exit 1
