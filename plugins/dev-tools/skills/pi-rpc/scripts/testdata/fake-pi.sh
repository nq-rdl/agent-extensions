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
    # message_end uses the nested wire shape matching real pi --mode rpc output.
    echo '{"type":"agent_start"}'
    while IFS= read -r line; do
      MSG=$(echo "$line" | sed -n 's/.*"message":"\([^"]*\)".*/\1/p')
      echo "{\"type\":\"message_update\",\"delta\":{\"type\":\"text_delta\",\"text\":\"echo: $MSG\"}}"
      echo "{\"type\":\"message_end\",\"message\":{\"role\":\"assistant\",\"content\":[{\"type\":\"text\",\"text\":\"echo: $MSG\"}],\"is_error\":false}}"
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

  real_shape)
    # Emit events matching the real `pi --mode rpc` wire format from upstream
    # packages/agent/src/types.ts (AgentEvent union).
    #
    # Real events wrap the message inside a nested "message" field:
    #   message_update: { type, message: AgentMessage, assistantMessageEvent: {...} }
    #   message_end:    { type, message: AgentMessage }
    #   agent_end:      { type, messages: AgentMessage[] }
    #
    # AgentMessage for assistant role (AssistantMessage from @mariozechner/pi-ai types.ts):
    #   { role, content: [{type:"text",text:...},...], api, provider, model,
    #     usage: {...}, stopReason, timestamp }
    echo '{"type":"agent_start"}'
    while IFS= read -r line; do
      MSG=$(echo "$line" | sed -n 's/.*"message":"\([^"]*\)".*/\1/p')
      # streaming delta: message_update with nested message + assistantMessageEvent
      echo "{\"type\":\"message_update\",\"message\":{\"role\":\"assistant\",\"content\":[{\"type\":\"text\",\"text\":\"echo: $MSG\"}],\"api\":\"anthropic-messages\",\"provider\":\"anthropic\",\"model\":\"claude-sonnet-4-5\",\"usage\":{\"input\":10,\"output\":5,\"cacheRead\":0,\"cacheWrite\":0,\"totalTokens\":15,\"cost\":{\"input\":0.001,\"output\":0.002,\"cacheRead\":0,\"cacheWrite\":0,\"total\":0.003}},\"stopReason\":\"stop\",\"timestamp\":1700000000000},\"assistantMessageEvent\":{\"type\":\"text_delta\",\"contentIndex\":0,\"delta\":\"echo: $MSG\",\"partial\":{\"role\":\"assistant\",\"content\":[{\"type\":\"text\",\"text\":\"echo: $MSG\"}],\"api\":\"anthropic-messages\",\"provider\":\"anthropic\",\"model\":\"claude-sonnet-4-5\",\"usage\":{\"input\":10,\"output\":5,\"cacheRead\":0,\"cacheWrite\":0,\"totalTokens\":15,\"cost\":{\"input\":0.001,\"output\":0.002,\"cacheRead\":0,\"cacheWrite\":0,\"total\":0.003}},\"stopReason\":\"stop\",\"timestamp\":1700000000000}}}"
      # final message_end: nested message, no flat role/content at top level
      echo "{\"type\":\"message_end\",\"message\":{\"role\":\"assistant\",\"content\":[{\"type\":\"text\",\"text\":\"echo: $MSG\"}],\"api\":\"anthropic-messages\",\"provider\":\"anthropic\",\"model\":\"claude-sonnet-4-5\",\"usage\":{\"input\":10,\"output\":5,\"cacheRead\":0,\"cacheWrite\":0,\"totalTokens\":15,\"cost\":{\"input\":0.001,\"output\":0.002,\"cacheRead\":0,\"cacheWrite\":0,\"total\":0.003}},\"stopReason\":\"stop\",\"timestamp\":1700000000000}}"
      echo "{\"type\":\"agent_end\",\"messages\":[{\"role\":\"user\",\"content\":\"$MSG\",\"timestamp\":1700000000000},{\"role\":\"assistant\",\"content\":[{\"type\":\"text\",\"text\":\"echo: $MSG\"}],\"api\":\"anthropic-messages\",\"provider\":\"anthropic\",\"model\":\"claude-sonnet-4-5\",\"usage\":{\"input\":10,\"output\":5,\"cacheRead\":0,\"cacheWrite\":0,\"totalTokens\":15,\"cost\":{\"input\":0.001,\"output\":0.002,\"cacheRead\":0,\"cacheWrite\":0,\"total\":0.003}},\"stopReason\":\"stop\",\"timestamp\":1700000000000}]}"
    done
    ;;

  capture_args)
    # Write all argv to FAKE_PI_ARGS_FILE (null-byte separated) then stay alive.
    # Null bytes preserve any embedded newlines inside individual arguments
    # (e.g. multi-line system prompts).
    # Used to assert that flags like --system-prompt are forwarded by the handler.
    if [ -n "${FAKE_PI_ARGS_FILE:-}" ]; then
      printf '%s\000' "$@" > "$FAKE_PI_ARGS_FILE"
    fi
    cat
    ;;

  *)
    echo "Unknown scenario: $SCENARIO" >&2
    exit 1
    ;;
esac
