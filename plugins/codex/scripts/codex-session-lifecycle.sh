#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.
#
# Codex session lifecycle hook wrapper. Preflights Node >=18.18.0, then execs the
# vendored session-lifecycle-hook.mjs, preserving stdin and the child exit status.
set -eu

codex_require_node() {
  if ! command -v node >/dev/null 2>&1; then
    printf '%s\n' 'Codex plugin requires Node.js >=18.18.0; install or upgrade Node: https://nodejs.org/en/download' >&2
    exit 1
  fi
  # One `node -p`, not two. This preflight runs on every hook invocation,
  # PostToolUse included, and a second Node start-up costs ~40ms to fetch a
  # value the first process already had.
  version="$(node -p 'process.versions.node.split(".").slice(0, 2).join(" ")' 2>/dev/null || true)"
  major="${version%% *}"
  minor="${version##* }"
  # An unparseable probe must take the same exit as an old Node, not die inside
  # the arithmetic test below with `set -e` and no message.
  case "${major}.${minor}" in
    *[!0-9.]*|.*|*.)
      printf '%s\n' 'Codex plugin requires Node.js >=18.18.0; install or upgrade Node: https://nodejs.org/en/download' >&2
      exit 1
      ;;
  esac
  if [ "$major" -lt 18 ] || { [ "$major" -eq 18 ] && [ "$minor" -lt 18 ]; }; then
    printf '%s\n' 'Codex plugin requires Node.js >=18.18.0; install or upgrade Node: https://nodejs.org/en/download' >&2
    exit 1
  fi
}

codex_require_node
exec node "${CLAUDE_PLUGIN_ROOT}/scripts/session-lifecycle-hook.mjs"
