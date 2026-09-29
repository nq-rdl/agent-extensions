#!/usr/bin/env bash
# check-config.sh — Check, enable, or disable Claude Code agent teams.
#
# Usage:
#   bash check-config.sh                       # Check current status
#   bash check-config.sh --enable              # Set the flag to "1" in ~/.claude/settings.json
#   bash check-config.sh --disable             # Set the flag to "0" in ~/.claude/settings.json
#   bash check-config.sh --enable --project    # Target .claude/settings.json in the current directory
#
# Requires Bash 3.2+ and jq. Settings precedence (highest first), per
# https://code.claude.com/docs/en/settings#settings-precedence: managed,
# project local (.claude/settings.local.json), shared project
# (.claude/settings.json), user (~/.claude/settings.json). A value in any
# settings file overrides a shell export; "0" disables agent teams.
# --settings, MDM and server-managed settings are not visible to this script.

set -euo pipefail
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd -P)/$(basename "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

ENV_VAR="CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"

# ── Parse arguments ──────────────────────────────────────────────────────────
ACTION="check"
SCOPE="user"

while [ $# -gt 0 ]; do
  case "$1" in
    --enable)  ACTION="enable";  shift ;;
    --disable) ACTION="disable"; shift ;;
    --project) SCOPE="project";  shift ;;
    --user)    SCOPE="user";     shift ;;
    -h|--help)
      echo "Usage: bash check-config.sh [--enable|--disable] [--project|--user]"
      echo ""
      echo "  --enable   Set ${ENV_VAR} to \"1\" in settings.json"
      echo "  --disable  Set ${ENV_VAR} to \"0\" in settings.json"
      echo "  --project  Target .claude/settings.json in current directory"
      echo "  --user     Target ~/.claude/settings.json (default)"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if ! command -v jq >/dev/null 2>&1; then
  echo "check-config.sh needs jq (https://jqlang.org/download/)." >&2
  exit 2
fi

# ── Settings file locations ──────────────────────────────────────────────────
managed_path() {
  if [ -n "${CHECK_CONFIG_MANAGED_FILE:-}" ]; then
    printf '%s\n' "$CHECK_CONFIG_MANAGED_FILE"
  elif [ "$(uname -s)" = "Darwin" ]; then
    printf '%s\n' "/Library/Application Support/ClaudeCode/managed-settings.json"
  else
    printf '%s\n' "/etc/claude-code/managed-settings.json"
  fi
}

settings_path() {
  case "$1" in
    Managed) managed_path ;;
    'Project local') printf '%s/.claude/settings.local.json\n' "$PWD" ;;
    Project) printf '%s/.claude/settings.json\n' "$PWD" ;;
    User) printf '%s/.claude/settings.json\n' "$HOME" ;;
  esac
}

# Print the flag's value from a settings file; nothing if unset. Fails on invalid JSON.
flag_value() {
  jq -r --arg k "$ENV_VAR" '(.env // {})[$k] // empty | tostring' "$1"
}

# ── Enable / Disable ────────────────────────────────────────────────────────
if [ "$ACTION" != "check" ]; then
  if [ "$SCOPE" = "project" ]; then
    TARGET="$PWD/.claude/settings.json"
    LABEL="Project"
  else
    TARGET="$HOME/.claude/settings.json"
    LABEL="User"
  fi

  if [ "$ACTION" = "enable" ]; then
    NEW_VALUE="1"
  else
    NEW_VALUE="0"
    if [ ! -f "$TARGET" ]; then
      echo "Agent teams not configured in $TARGET — nothing to disable"
      exit 0
    fi
  fi

  mkdir -p "$(dirname "$TARGET")"
  [ -f "$TARGET" ] || printf '{}\n' > "$TARGET"

  if ! jq -e 'type == "object"' "$TARGET" >/dev/null 2>&1; then
    echo -e "${RED}${BOLD}Not changed:${NC} $TARGET is not a valid JSON object. Fix it, then re-run." >&2
    exit 1
  fi

  tmp="$(mktemp "${TARGET}.XXXXXX")"
  if jq --arg k "$ENV_VAR" --arg v "$NEW_VALUE" '.env = ((.env // {}) + {($k): $v})' "$TARGET" > "$tmp"; then
    mv "$tmp" "$TARGET"
  else
    rm -f "$tmp"
    echo "Failed to update $TARGET" >&2
    exit 1
  fi

  if [ "$ACTION" = "enable" ]; then
    echo -e "${GREEN}${BOLD}Enabled${NC} agent teams in ${LABEL} settings: $TARGET"
  else
    echo -e "${YELLOW}${BOLD}Disabled${NC} agent teams in ${LABEL} settings: $TARGET (${ENV_VAR}=\"0\")"
  fi
  echo "  Higher-precedence settings files can still override this value."
  exit 0
fi

# ── Check mode ───────────────────────────────────────────────────────────────
effective=""
effective_from=""

echo -e "${BOLD}Agent Teams Configuration Check${NC} (highest precedence first)"
echo "================================"
echo ""

for label in "Managed" "Project local" "Project" "User"; do
  file="$(settings_path "$label")"

  if [ ! -f "$file" ]; then
    echo -e "  ${YELLOW}SKIP${NC}  $label — file not found"
    echo "         $file"
    continue
  fi

  if ! value="$(flag_value "$file" 2>/dev/null)"; then
    echo -e "  ${RED}WARN${NC}  $label — invalid JSON, ignored here"
    echo "         $file"
    continue
  fi

  if [ -z "$value" ]; then
    echo -e "  ${YELLOW}---${NC}   $label — not configured"
    echo "         $file"
    continue
  fi

  if [ "$value" = "1" ]; then
    echo -e "  ${GREEN}OK${NC}    $label — ${ENV_VAR}=\"1\""
  elif [ "$value" = "0" ]; then
    echo -e "  ${YELLOW}OFF${NC}   $label — ${ENV_VAR}=\"0\" (explicitly disabled)"
  elif [ "$value" = "true" ]; then
    echo -e "  ${RED}WARN${NC}  $label — ${ENV_VAR}=\"true\" (should be \"1\", not \"true\")"
    echo -e "         ${YELLOW}FIX:${NC} Change \"true\" to \"1\" — the feature flag expects \"1\""
  else
    echo -e "  ${RED}WARN${NC}  $label — ${ENV_VAR}=\"${value}\" (not \"1\")"
  fi
  echo "         $file"

  if [ -z "$effective_from" ]; then
    effective="$value"
    effective_from="$label settings"
  fi
done

echo ""

shell_value="${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-}"
if [ -n "$shell_value" ]; then
  echo -e "  ${GREEN}SET${NC}   Shell environment — ${ENV_VAR}=${shell_value}"
  if [ -z "$effective_from" ]; then
    effective="$shell_value"
    effective_from="Shell environment"
  else
    echo "         (overridden by $effective_from)"
  fi
else
  echo -e "  ${YELLOW}---${NC}   Shell environment — not set"
fi

echo ""

# Teammate mode (a settings key allowed in any settings file)
echo -e "${BOLD}Teammate Mode${NC}"
echo "-------------"
teammate_mode="in-process (default)"

for label in "Managed" "Project local" "Project" "User"; do
  mode_file="$(settings_path "$label")"
  [ -f "$mode_file" ] || continue
  mode="$(jq -r '.teammateMode // empty' "$mode_file" 2>/dev/null || true)"
  if [ -n "$mode" ]; then
    teammate_mode="$mode (from $mode_file)"
    break
  fi
done

echo "  Mode: $teammate_mode"
echo "  (claude --teammate-mode overrides this for one session)"
echo ""

# tmux availability
if command -v tmux >/dev/null 2>&1; then
  tmux_version=$(tmux -V 2>/dev/null || echo "unknown")
  echo -e "  ${GREEN}OK${NC}    tmux available — $tmux_version"
else
  echo -e "  ${YELLOW}INFO${NC}  tmux not installed (needed for split-pane mode only)"
fi

# Claude Code version
echo ""
echo -e "${BOLD}Claude Code Version${NC}"
echo "-------------------"
if command -v claude >/dev/null 2>&1; then
  claude_version=$(claude --version 2>/dev/null || echo "unknown")
  echo "  Version: $claude_version"
  echo "  (Agent teams first shipped in v2.1.32; this skill requires v2.1.178+)"
else
  echo -e "  ${YELLOW}WARN${NC}  claude CLI not found in PATH"
fi

echo ""

# Summary
echo "================================"
if [ "$effective" = "1" ]; then
  echo -e "${GREEN}${BOLD}Agent teams are ENABLED${NC} (via: $effective_from)"
else
  echo -e "${RED}${BOLD}Agent teams are NOT ENABLED${NC}"
  if [ -n "$effective_from" ]; then
    echo "  Effective value \"$effective\" comes from: $effective_from"
  fi
  echo ""
  echo "To enable, run:"
  printf '  bash %q --enable\n' "$SCRIPT_PATH"
  echo ""
  echo "Or add manually to settings.json:"
  echo '  {'
  echo '    "env": {'
  echo "      \"${ENV_VAR}\": \"1\""
  echo '    }'
  echo '  }'
fi
