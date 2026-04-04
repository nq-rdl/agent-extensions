#!/usr/bin/env bash
#
# fake-gemini-acp.sh — Test double for `gemini --acp` persistent sessions.
#
# Reads JSON-RPC 2.0 requests from stdin (ND-JSON), writes responses to stdout.
# Handles: initialize, session/new, session/prompt
#
# Controlled via FAKE_ACP_SCENARIO:
#   success    (default) — normal multi-turn conversation
#   error      — session/prompt returns an error response
#   crash      — process exits mid-session (tests auto-restart)
#
# Usage in tests:
#   GEMINI_BINARY=/path/to/fake-gemini-acp.sh bun test

set -euo pipefail

# Only activate ACP mode when --acp flag is present
ACP_MODE=false
for arg in "$@"; do
  case "$arg" in
    --acp) ACP_MODE=true ;;
  esac
done

if [ "$ACP_MODE" != "true" ]; then
  # Fall through to normal fake-gemini behavior if --acp not passed
  exec "$(dirname "$0")/fake-gemini.sh" "$@"
fi

SCENARIO="${FAKE_ACP_SCENARIO:-success}"
TURN=0

# Read ND-JSON lines from stdin, respond to each
while IFS= read -r line; do
  # Skip empty lines
  [ -z "$line" ] && continue

  # Extract method and id from JSON-RPC request
  METHOD=$(echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('method',''))" 2>/dev/null || echo "")
  REQ_ID=$(echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")

  case "$METHOD" in
    initialize)
      echo '{"jsonrpc":"2.0","id":'"$REQ_ID"',"result":{"protocolVersion":1,"agentInfo":{"name":"fake-gemini","version":"0.0.1"},"authMethods":[]}}'
      ;;

    session/new)
      echo '{"jsonrpc":"2.0","id":'"$REQ_ID"',"result":{"sessionId":"fake-acp-session-001","modes":{},"models":{}}}'
      ;;

    session/prompt)
      TURN=$((TURN + 1))

      case "$SCENARIO" in
        success)
          # Send a session/update notification (no id = notification)
          echo '{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"fake-acp-session-001","update":{"sessionUpdate":"agent_message_chunk","text":"Fake ACP response for turn '"$TURN"'."}}}'
          # Send the final result
          echo '{"jsonrpc":"2.0","id":'"$REQ_ID"',"result":{"stopReason":"end_turn","usage":{"inputTokens":15,"outputTokens":25,"totalTokens":40}}}'
          ;;

        error)
          echo '{"jsonrpc":"2.0","id":'"$REQ_ID"',"error":{"code":-32000,"message":"Model unavailable"}}'
          ;;

        crash)
          if [ "$TURN" -ge 2 ]; then
            # Crash on second prompt
            exit 1
          fi
          echo '{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"fake-acp-session-001","update":{"sessionUpdate":"agent_message_chunk","text":"Fake ACP response before crash."}}}'
          echo '{"jsonrpc":"2.0","id":'"$REQ_ID"',"result":{"stopReason":"end_turn","usage":{"inputTokens":10,"outputTokens":20,"totalTokens":30}}}'
          ;;
      esac
      ;;

    *)
      echo '{"jsonrpc":"2.0","id":'"$REQ_ID"',"error":{"code":-32601,"message":"Method not found: '"$METHOD"'"}}'
      ;;
  esac
done
