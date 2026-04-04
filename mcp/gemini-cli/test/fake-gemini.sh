#!/usr/bin/env bash
#
# fake-gemini.sh — Test double for the Gemini CLI binary.
#
# Mimics `gemini --output-format stream-json` JSONL output for unit testing.
# Controlled via FAKE_GEMINI_SCENARIO environment variable:
#
#   FAKE_GEMINI_SCENARIO=success    (default) — normal JSONL response
#   FAKE_GEMINI_SCENARIO=error      — exits with code 1 + stderr message
#   FAKE_GEMINI_SCENARIO=input_err  — exits with code 42
#   FAKE_GEMINI_SCENARIO=turn_limit — exits with code 53
#   FAKE_GEMINI_SCENARIO=tool_use   — response with web_search tool use/result events
#   FAKE_GEMINI_SCENARIO=resume     — includes resume session simulation
#
# Usage in tests:
#   GEMINI_BINARY=/path/to/fake-gemini.sh bun test

set -euo pipefail

SCENARIO="${FAKE_GEMINI_SCENARIO:-success}"
SESSION_ID="fake-session-$(date +%s)"

# Extract the prompt from args (--prompt or -p flag)
PROMPT=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --prompt|-p) PROMPT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

case "$SCENARIO" in
  success)
    # Mimics `--output-format json` real output — nested models breakdown (verified against gemini CLI)
    echo '{"session_id":"'"$SESSION_ID"'","response":"This is a fake response from the test double.","stats":{"models":{"gemini-3-flash-preview":{"api":{"totalRequests":1,"totalErrors":0,"totalLatencyMs":100},"tokens":{"input":10,"prompt":10,"candidates":32,"total":42,"cached":0}}}}}'
    exit 0
    ;;

  tool_use)
    echo '{"session_id":"'"$SESSION_ID"'","response":"Based on web search results: fake web content.","stats":{"models":{"gemini-3-flash-preview":{"api":{"totalRequests":2,"totalErrors":0,"totalLatencyMs":350},"tokens":{"input":20,"prompt":20,"candidates":108,"total":128,"cached":0}}}}}'
    exit 0
    ;;

  resume)
    echo '{"session_id":"'"${FAKE_RESUME_SESSION:-$SESSION_ID}"'","response":"Continuing from previous session context.","stats":{"models":{"gemini-3.1-pro-preview":{"api":{"totalRequests":1,"totalErrors":0,"totalLatencyMs":200},"tokens":{"input":15,"prompt":15,"candidates":49,"total":64,"cached":0}}}}}'
    exit 0
    ;;

  error)
    echo "Gemini API error: model unavailable" >&2
    exit 1
    ;;

  input_err)
    echo "Invalid argument: --unknown-flag is not recognized" >&2
    exit 42
    ;;

  turn_limit)
    echo "Turn limit exceeded after 10 turns" >&2
    exit 53
    ;;

  *)
    echo "Unknown scenario: $SCENARIO" >&2
    exit 1
    ;;
esac
