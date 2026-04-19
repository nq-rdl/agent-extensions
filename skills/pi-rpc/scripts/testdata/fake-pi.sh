#!/usr/bin/env bash
#
# fake-pi.sh — Test double for the pi CLI binary in RPC mode.
#
# Mimics `pi --mode rpc` JSONL-over-stdio behaviour for unit testing.
# Controlled via FAKE_PI_SCENARIO environment variable:
#
#   FAKE_PI_SCENARIO=idle        (default) — stays alive reading stdin, no events
#   FAKE_PI_SCENARIO=echo        — emits agent_start + message_update + agent_end
#   FAKE_PI_SCENARIO=fail_start  — writes error to stderr and exits immediately
#   FAKE_PI_SCENARIO=hang        — starts but never emits events (inactivity tests)
#
# Usage in tests:
#   binary := filepath.Join("testdata", "fake-pi.sh")
#   mgr := session.NewManager(binary)

set -euo pipefail

SCENARIO="${FAKE_PI_SCENARIO:-idle}"

case "$SCENARIO" in
  idle)
    # Stay alive reading stdin; emit no events.
    # Used for Create/List/Delete/GetState tests.
    cat
    ;;

  echo)
    # Emit a full agent lifecycle then echo any stdin prompts back as messages.
    # message_update uses pi's real delta format; message_end carries the complete message.
    echo '{"type":"agent_start"}'
    while IFS= read -r line; do
      MSG=$(echo "$line" | grep -o '"message":"[^"]*"' | sed 's/"message":"//;s/"//')
      echo "{\"type\":\"message_update\",\"delta\":{\"type\":\"text_delta\",\"text\":\"echo: $MSG\"}}"
      echo "{\"type\":\"message_end\",\"role\":\"assistant\",\"content\":\"echo: $MSG\",\"is_error\":false}"
      echo '{"type":"agent_end"}'
    done
    ;;

  fail_start)
    # Exit immediately with an error on stderr — simulates bad API key / bad model.
    echo 'Error: No API key found for openai.' >&2
    echo 'Use /login or set an API key environment variable.' >&2
    exit 1
    ;;

  hang)
    # Start but never emit events — triggers the inactivity watchdog.
    sleep 300
    ;;

  *)
    echo "Unknown scenario: $SCENARIO" >&2
    exit 1
    ;;
esac
