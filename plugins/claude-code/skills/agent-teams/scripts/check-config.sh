#!/usr/bin/env bash
# check-config.sh — Check, enable, or disable Claude Code agent teams.
#
# Usage:
#   bash check-config.sh            # Check current status
#   bash check-config.sh --enable   # Enable in user settings (~/.claude/settings.json)
#   bash check-config.sh --disable  # Disable in user settings
#   bash check-config.sh --enable --project  # Enable in project settings (.claude/settings.json)
#
# Checks all settings.json locations for CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS,
# reports status, and optionally toggles the feature flag.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

ENV_VAR="CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"

# ── Parse arguments ──────────────────────────────────────────────────────────
ACTION="check"
SCOPE="user"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --enable)  ACTION="enable";  shift ;;
    --disable) ACTION="disable"; shift ;;
    --project) SCOPE="project";  shift ;;
    --user)    SCOPE="user";     shift ;;
    -h|--help)
      echo "Usage: bash check-config.sh [--enable|--disable] [--project|--user]"
      echo ""
      echo "  --enable   Enable agent teams in settings.json"
      echo "  --disable  Disable agent teams (remove from settings.json)"
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

# ── Settings file locations ──────────────────────────────────────────────────
declare -A LOCATIONS=(
  ["Project"]="$(pwd)/.claude/settings.json"
  ["Project local"]="$(pwd)/.claude/settings.local.json"
  ["User"]="$HOME/.claude/settings.json"
  ["User local"]="$HOME/.claude/settings.local.json"
)

# ── Enable / Disable ────────────────────────────────────────────────────────
if [[ "$ACTION" != "check" ]]; then
  if [[ "$SCOPE" == "project" ]]; then
    TARGET="$(pwd)/.claude/settings.json"
    LABEL="Project"
  else
    TARGET="$HOME/.claude/settings.json"
    LABEL="User"
  fi

  # Ensure directory exists
  mkdir -p "$(dirname "$TARGET")"

  if [[ "$ACTION" == "enable" ]]; then
    if [[ -f "$TARGET" ]]; then
      # Check if env block exists
      if grep -q '"env"' "$TARGET" 2>/dev/null; then
        if grep -q "$ENV_VAR" "$TARGET" 2>/dev/null; then
          # Update existing value
          sed -i "s/\"$ENV_VAR\"[[:space:]]*:[[:space:]]*\"[^\"]*\"/\"$ENV_VAR\": \"1\"/" "$TARGET"
        else
          # Add to existing env block
          sed -i "s/\"env\"[[:space:]]*:[[:space:]]*{/\"env\": {\n    \"$ENV_VAR\": \"1\",/" "$TARGET"
        fi
      else
        # Add env block to existing JSON
        sed -i "s/^{/{\\n  \"env\": {\\n    \"$ENV_VAR\": \"1\"\\n  },/" "$TARGET"
      fi
    else
      # Create new file
      cat > "$TARGET" <<EOF
{
  "env": {
    "$ENV_VAR": "1"
  }
}
EOF
    fi
    echo -e "${GREEN}${BOLD}Enabled${NC} agent teams in ${LABEL} settings: $TARGET"
    exit 0
  fi

  if [[ "$ACTION" == "disable" ]]; then
    if [[ -f "$TARGET" ]] && grep -q "$ENV_VAR" "$TARGET" 2>/dev/null; then
      # Remove the line containing the env var (and trailing comma if present)
      sed -i "/$ENV_VAR/d" "$TARGET"
      echo -e "${YELLOW}${BOLD}Disabled${NC} agent teams in ${LABEL} settings: $TARGET"
      echo "  (You may want to clean up empty \"env\": {} blocks manually)"
    else
      echo "Agent teams not configured in $TARGET — nothing to disable"
    fi
    exit 0
  fi
fi

# ── Check mode ───────────────────────────────────────────────────────────────
found=false
found_locations=()

echo -e "${BOLD}Agent Teams Configuration Check${NC}"
echo "================================"
echo ""

for label in "Project" "Project local" "User" "User local"; do
  file="${LOCATIONS[$label]}"

  if [[ ! -f "$file" ]]; then
    echo -e "  ${YELLOW}SKIP${NC}  $label — file not found"
    echo "         $file"
    continue
  fi

  if grep -q "$ENV_VAR" "$file" 2>/dev/null; then
    value=$(grep -o "\"$ENV_VAR\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" | head -1 | sed 's/.*: *"//' | sed 's/"//')

    if [[ "$value" == "1" ]]; then
      echo -e "  ${GREEN}OK${NC}    $label — ${ENV_VAR}=\"1\""
      echo "         $file"
      found=true
      found_locations+=("$label")
    elif [[ "$value" == "true" ]]; then
      echo -e "  ${RED}WARN${NC}  $label — ${ENV_VAR}=\"true\" (should be \"1\", not \"true\")"
      echo "         $file"
      echo -e "         ${YELLOW}FIX:${NC} Change \"true\" to \"1\" — the feature flag expects \"1\""
    else
      echo -e "  ${RED}WARN${NC}  $label — ${ENV_VAR}=\"${value}\" (not \"1\")"
      echo "         $file"
    fi
  else
    echo -e "  ${YELLOW}---${NC}   $label — not configured"
    echo "         $file"
  fi
done

echo ""

# Check environment variable directly
if [[ "${!ENV_VAR:-}" == "1" ]]; then
  echo -e "  ${GREEN}OK${NC}    Shell environment — ${ENV_VAR}=1"
  found=true
  found_locations+=("Shell environment")
else
  echo -e "  ${YELLOW}---${NC}   Shell environment — not set"
fi

echo ""

# Teammate mode
echo -e "${BOLD}Teammate Mode${NC}"
echo "-------------"
teammate_mode="auto (default)"

# Check ~/.claude.json (global config) first
if [[ -f "$HOME/.claude.json" ]] && grep -q '"teammateMode"' "$HOME/.claude.json" 2>/dev/null; then
  mode=$(grep -o '"teammateMode"[[:space:]]*:[[:space:]]*"[^"]*"' "$HOME/.claude.json" | head -1 | sed 's/.*: *"//' | sed 's/"//')
  teammate_mode="$mode (from ~/.claude.json)"
fi

echo "  Mode: $teammate_mode"
echo ""

# tmux availability
if command -v tmux &>/dev/null; then
  tmux_version=$(tmux -V 2>/dev/null || echo "unknown")
  echo -e "  ${GREEN}OK${NC}    tmux available — $tmux_version"
else
  echo -e "  ${YELLOW}INFO${NC}  tmux not installed (needed for split-pane mode only)"
fi

# Claude Code version
echo ""
echo -e "${BOLD}Claude Code Version${NC}"
echo "-------------------"
if command -v claude &>/dev/null; then
  claude_version=$(claude --version 2>/dev/null || echo "unknown")
  echo "  Version: $claude_version"
  echo "  (Agent teams require v2.1.32+)"
else
  echo -e "  ${YELLOW}WARN${NC}  claude CLI not found in PATH"
fi

echo ""

# Summary
echo "================================"
if $found; then
  echo -e "${GREEN}${BOLD}Agent teams are ENABLED${NC} (via: ${found_locations[*]})"
else
  echo -e "${RED}${BOLD}Agent teams are NOT ENABLED${NC}"
  echo ""
  echo "To enable, run:"
  echo "  bash scripts/check-config.sh --enable"
  echo ""
  echo "Or add manually to settings.json:"
  echo '  {'
  echo '    "env": {'
  echo "      \"${ENV_VAR}\": \"1\""
  echo '    }'
  echo '  }'
fi
