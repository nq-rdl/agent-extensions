#!/usr/bin/env bash
# Launcher for the gemini-cli MCP server. Selects the prebuilt binary for the
# current OS/arch and execs it. No arguments — the binary speaks MCP over stdio.
set -euo pipefail

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"
case "$arch" in
  x86_64)  arch="amd64" ;;
  aarch64) arch="arm64" ;;
esac

BINARY="${PLUGIN_ROOT}/bin/mcp/gemini-cli-mcp-${os}-${arch}"

if [[ ! -x "$BINARY" ]]; then
  echo "gemini-cli-mcp: no prebuilt binary for ${os}/${arch} at ${BINARY}" >&2
  exit 1
fi

exec "$BINARY" "$@"
