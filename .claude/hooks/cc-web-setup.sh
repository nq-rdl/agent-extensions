#!/usr/bin/env bash
#
# cc-web-setup.sh — pre-snapshot plugin pre-seed for Claude Code on the web.
#
# WHY THIS EXISTS — the first-session visibility bug. Claude Code enumerates
# plugin skills at PROCESS STARTUP, *before* any SessionStart hook runs. Plugins
# declared only via .claude/settings.json (extraKnownMarketplaces +
# enabledPlugins) are installed too late to appear in the FIRST session's slash
# menu — they surface only from the *next* session. Installing them HERE — from
# the web environment's **Setup script** field (exposed as `make cc-web-setup`),
# which runs ONCE before Claude starts and whose filesystem is captured in the
# environment snapshot — bakes them into the image so their /<plugin>:<skill>
# commands are present on the very first session.
#
# THE ONE MANUAL STEP: this script only helps if the web environment's **Setup
# script** field is set to `make cc-web-setup`. That field lives in the Claude
# Code web environment settings UI, NOT in the repo, so it cannot be committed —
# it must be set once per environment. Without it, plugin skills still only
# appear from the second session onward (the SessionStart self-heal path below).
#
# SINGLE SOURCE OF TRUTH: the marketplaces to register and the plugins to install
# are read straight from .claude/settings.json (every extraKnownMarketplaces
# entry, plus every enabledPlugins entry whose value is true), so this pre-seed
# never drifts from what the project declares. Add a plugin to settings.json and
# it is pre-seeded automatically; nothing to update here.
#
# Idempotent and safe to re-run: `marketplace add` falls back to `update`, and
# `plugin install` falls back to `update`, so a second run is a cheap no-op. The
# SessionStart hook (web-bootstrap.sh) also calls this as a SELF-HEAL for
# environments whose Setup-script field is not wired — on that path the skills
# still arrive next session, because the hook runs after skill enumeration.
#
# Exit status reflects provisioning (0 = installed or skipped, non-zero =
# failed), so a setup script can surface provisioning failures; the SessionStart
# hook invokes it with `|| …` so a failure there is logged, never fatal.
#
# Output discipline: keep stdout concise — when run from the hook it is injected
# into Claude's context — so verbose tool output goes to $LOG.
set -uo pipefail

# Only colorize on a TTY — cloud setup/SessionStart stdout is non-TTY and (for
# the hook) injected into the model context, where ANSI escapes are just noise.
if [ -t 1 ]; then _BLU=$'\033[34m'; _RST=$'\033[0m'; else _BLU=''; _RST=''; fi
log() { printf '%s[cc-web-setup]%s %s\n' "$_BLU" "$_RST" "$*"; }

# Imperative body. Wrapped in main() so the script is *sourceable* for unit
# tests (mirroring web-bootstrap.sh): executing it (`make cc-web-setup`, or
# `bash .claude/hooks/cc-web-setup.sh` from web-bootstrap.sh) runs main; sourcing
# it only defines the helper/globals above. LOG/PROJECT_DIR live IN here so
# sourcing never truncates the real log.
main() {
  # Verbose output sink (keeps stdout clean — see header).
  LOG="${TMPDIR:-/tmp}/rdl-cc-web-setup.log"
  ( umask 077; : > "$LOG" ) 2>/dev/null || LOG=/dev/null

  # Resolve the repo root. `make cc-web-setup` runs from the repo root and the
  # hook exports CLAUDE_PROJECT_DIR; fall back to the script's own location (this
  # file lives at .claude/hooks/, so the repo root is two levels up) so it also
  # works when run by hand.
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
  local settings="${PROJECT_DIR}/.claude/settings.json"

  local rc=0

  if ! command -v claude >/dev/null 2>&1; then
    log "claude CLI not on PATH — skipping plugin pre-seed."
    exit 0
  fi
  if ! command -v jq >/dev/null 2>&1; then
    log "WARNING: jq not on PATH — cannot read marketplaces/plugins from settings.json."
    exit 1
  fi
  if [ ! -f "$settings" ]; then
    log "WARNING: ${settings} not found — nothing to pre-seed."
    exit 1
  fi

  # --- 1. Register every declared marketplace -------------------------------
  # Read extraKnownMarketplaces from settings.json as "<github-repo>|<name>"
  # pairs. `marketplace add` takes the GitHub source; if it is already registered
  # that call fails harmlessly, so fall back to `update` by the registered name
  # (the settings key) to refresh it. On a cold VM this MUST run before any
  # install — otherwise the install fails with "No marketplaces configured".
  local entry mp_repo mp_name
  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    mp_repo="${entry%%|*}"; mp_name="${entry##*|}"
    if [ -z "$mp_repo" ] || [ "$mp_repo" = "null" ]; then
      log "WARNING: marketplace '${mp_name}' has no github repo source — skipping."
      continue
    fi
    log "Registering plugin marketplace ${mp_name} (${mp_repo})…"
    claude plugin marketplace add "$mp_repo" </dev/null >>"$LOG" 2>&1 \
      || claude plugin marketplace update "$mp_name" </dev/null >>"$LOG" 2>&1 \
      || log "  WARNING: could not register/update marketplace ${mp_name} (see ${LOG})."
  done < <(jq -r '(.extraKnownMarketplaces // {}) | to_entries[]
                  | "\(.value.source.repo // "null")|\(.key)"' "$settings" 2>/dev/null)

  # --- 2. Install every enabled plugin --------------------------------------
  # Read enabledPlugins (value == true) as "<plugin>@<marketplace>" ids — exactly
  # the argument `claude plugin install` expects. Installing HERE (pre-snapshot,
  # pre-startup) is what makes the skills available on the first session.
  local plugin
  while IFS= read -r plugin; do
    [ -n "$plugin" ] || continue
    log "Pre-seeding ${plugin}…"
    if claude plugin install "$plugin" --scope project </dev/null >>"$LOG" 2>&1 \
       || claude plugin update "$plugin" --scope project </dev/null >>"$LOG" 2>&1; then
      log "  ${plugin}: ready."
    else
      # A plugin that can neither install nor update is a real provisioning
      # failure: the documented exit-status contract (0 = installed/skipped,
      # non-zero = failed) requires surfacing it, even though the SessionStart
      # hook will retry next session.
      log "  WARNING: could not install/update ${plugin} (see ${LOG})."
      rc=1
    fi
  done < <(jq -r '(.enabledPlugins // {}) | to_entries[]
                  | select(.value == true) | .key' "$settings" 2>/dev/null)

  if [ "$rc" -eq 0 ]; then
    log "Plugin pre-seed complete."
  else
    log "Plugin pre-seed finished with errors (see ${LOG})."
  fi
  exit "$rc"
}

# Run the imperative body only when executed, not when sourced. cc-web-setup is
# invoked by direct exec (`make cc-web-setup`) and via `bash …/cc-web-setup.sh`
# from web-bootstrap.sh, so BASH_SOURCE[0] == $0 holds for the real run; a test
# harness that sources this file skips main and just exercises the globals.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
