#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 nq-rdl
#
# Codex defect-report hook wrapper. Preflights Node >=18.18.0, then execs the
# first-party defect-report-hook.mjs, preserving stdin and the child exit status.
set -eu

codex_require_node() {
  if ! command -v node >/dev/null 2>&1; then
    printf '%s\n' 'Codex plugin requires Node.js >=18.18.0; install or upgrade Node: https://nodejs.org/en/download' >&2
    exit 1
  fi
  major="$(node -p 'process.versions.node.split(".")[0]')"
  minor="$(node -p 'process.versions.node.split(".")[1]')"
  if [ "$major" -lt 18 ] || { [ "$major" -eq 18 ] && [ "$minor" -lt 18 ]; }; then
    printf '%s\n' 'Codex plugin requires Node.js >=18.18.0; install or upgrade Node: https://nodejs.org/en/download' >&2
    exit 1
  fi
}

codex_require_node
exec node "${CLAUDE_PLUGIN_ROOT}/scripts/defect-report-hook.mjs"
