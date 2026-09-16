#!/usr/bin/env bash
# Wrapper around lychee with sensible defaults for documentation link checking.
# Usage: bash scripts/check-links.sh [lychee-args...] <paths/globs>
#
# If a lychee.toml exists in the skill directory, it's used automatically.
# All arguments are forwarded to lychee — the wrapper just injects defaults
# that make sense for non-interactive CI/agent use.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="${SKILL_DIR}/lychee.toml"

# Check lychee is available
if ! command -v lychee &>/dev/null; then
  cat >&2 <<'MSG'
lychee not found on PATH. Install via one of:

  pixi global install lychee
  cargo install lychee
  brew install lychee
  conda install -c conda-forge lychee
MSG
  exit 1
fi

ARGS=()

# Inspect individual arguments so a path containing " --config " is not a flag.
# Stop at --, after which even option-looking inputs are positional.
HAS_CONFIG=false
for arg in "$@"; do
  case "$arg" in
    --) break ;;
    --config|--config=*|-c|-c?*) HAS_CONFIG=true; break ;;
  esac
done
if [[ "$HAS_CONFIG" == false ]] && [[ -f "$CONFIG_FILE" ]]; then
  ARGS+=(--config "$CONFIG_FILE")
fi

# Non-interactive default (no progress bar).
ARGS+=(--no-progress)

# Forward all user-provided arguments
ARGS+=("$@")

exec lychee "${ARGS[@]}"
