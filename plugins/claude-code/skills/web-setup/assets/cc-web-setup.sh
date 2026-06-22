#!/usr/bin/env bash
#
# cc-web-setup.sh — provision a Claude Code on the web (cloud) VM.
#
# Run this ONCE per environment from the web environment's *setup script* — the
# bash that runs before Claude starts and whose filesystem state is captured in
# the environment snapshot. It is exposed as `make cc-web-setup`.
#
# Why a setup-script step rather than (only) the SessionStart hook: Claude
# enumerates skills at process startup, BEFORE SessionStart hooks run. A plugin
# installed by the hook (scripts/web-bootstrap.sh) therefore only surfaces its
# skills on the NEXT session. Installing the plugin here — before the snapshot,
# before Claude starts — bakes it into the image so its skills are available on
# the FIRST session.
#
# Idempotent and safe to re-run: the plugin pre-seed is a cheap no-op when
# already current, and an optional project hook (cc-web-setup.local.sh) guards
# its own heavy work. The SessionStart hook also calls this as a self-heal for
# environments whose setup script does not run it (on that path the plugins'
# skills still arrive next session, because the hook runs after skill enumeration).
#
# This script is PORTABLE: it carries no project-specific dependencies. Project
# specifics (language toolchains, container runtimes, heavy installs) belong in
# an optional, gitignored-or-committed `scripts/cc-web-setup.local.sh` that this
# script sources if present — see the SOURCE PROJECT HOOK section below.
#
# Exit status reflects provisioning (0 = installed or skipped, non-zero =
# failed) so a setup script can surface provisioning failures; callers that must
# not fail (the SessionStart hook) invoke it with `|| …`.
#
# Output discipline: keep stdout concise — when run from the hook it is injected
# into Claude's context — so verbose tool output goes to $LOG.
set -uo pipefail

# Only colorize on a TTY — cloud setup/SessionStart stdout is non-TTY and (for
# the hook) injected into the model context, where ANSI escapes are just noise.
if [ -t 1 ]; then _BLU=$'\033[34m'; _RST=$'\033[0m'; else _BLU=''; _RST=''; fi
log() { printf '%s[cc-web-setup]%s %s\n' "$_BLU" "$_RST" "$*"; }

# Marketplaces to register before installing plugins. On a cold VM this can run
# BEFORE Claude loads extraKnownMarketplaces from .claude/settings.json, so an
# explicit `marketplace add` is required — otherwise the plugin install fails with
# "No marketplaces configured". Each entry is "<github-source>|<registered-name>":
# `marketplace add` takes the GitHub source, but `marketplace update` takes the
# name shown by `marketplace list` (these can differ).
#
# Parameterized: override the defaults by exporting CC_WEB_MARKETPLACES as a
# whitespace-separated list of "<source>|<name>" entries (e.g. in
# cc-web-setup.local.sh or the environment), so a repo can pre-seed extra
# marketplaces without forking this script.
if [ -n "${CC_WEB_MARKETPLACES:-}" ]; then
  read -r -a MARKETPLACES <<<"$CC_WEB_MARKETPLACES"
else
  MARKETPLACES=("nq-rdl/agent-extensions|rdl")
fi

# Plugins to pre-seed. Override with CC_WEB_PLUGINS (whitespace-separated
# "<plugin>@<marketplace>" entries). Default pre-seeds the RDL meta-plugin, which
# pulls in every RDL subject plugin in one install.
if [ -n "${CC_WEB_PLUGINS:-}" ]; then
  read -r -a PLUGINS <<<"$CC_WEB_PLUGINS"
else
  PLUGINS=("rdl@rdl")
fi

# Imperative body. Wrapped in main() so the script is *sourceable* for unit
# tests: executing it (`make cc-web-setup`, or `bash …/cc-web-setup.sh` from
# web-bootstrap.sh) runs main; sourcing it (the test harness) only defines the
# functions/globals above so they can be exercised against stubbed external
# tools without running the imperative body or touching the log file. LOG/
# PROJECT_DIR live IN here (mirroring web-bootstrap.sh) so sourcing never
# truncates the real log.
main() {
  # Verbose output sink (keeps stdout clean — see header).
  LOG="${TMPDIR:-/tmp}/rdl-cc-web-setup.log"
  ( umask 077; : > "$LOG" ) 2>/dev/null || LOG=/dev/null

  # Resolve the repo root. `make cc-web-setup` runs from the repo root and the
  # hook exports CLAUDE_PROJECT_DIR; fall back to the script's own location so it
  # also works when run by hand.
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

  local rc=0

  # --- 1. plugin marketplace + plugin pre-seed ------------------------------
  # Installing the plugin HERE (pre-snapshot, pre-startup) is what makes its skills
  # available on the first session. Run every invocation (not sentinel-gated) so a
  # transient marketplace/network failure self-heals on the next call.
  if command -v claude >/dev/null 2>&1; then
    # Register marketplaces first so plugins resolve on a cold VM (see MARKETPLACES).
    # `marketplace add` pulls the marketplace by its GitHub source; if it is already
    # registered that call fails harmlessly, so fall back to `update` by its
    # registered name to refresh it.
    local entry mp_src mp_name plugin
    for entry in "${MARKETPLACES[@]}"; do
      mp_src="${entry%%|*}"; mp_name="${entry##*|}"
      log "Registering plugin marketplace ${mp_name}…"
      claude plugin marketplace add "$mp_src" </dev/null >>"$LOG" 2>&1 \
        || claude plugin marketplace update "$mp_name" </dev/null >>"$LOG" 2>&1 \
        || log "  WARNING: could not register/update marketplace ${mp_name} (see ${LOG})."
    done
    for plugin in "${PLUGINS[@]}"; do
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
    done
  else
    log "claude CLI not on PATH — skipping plugin pre-seed."
  fi

  # --- 2. SOURCE PROJECT HOOK (optional, project-specific) ------------------
  # The portable engine above carries no project dependencies. A repo that needs
  # heavy provisioning baked into the snapshot (language toolchains, container
  # runtimes, k8s-in-docker, etc.) puts it in scripts/cc-web-setup.local.sh,
  # which is sourced here if present. A subshell inherits main()'s helpers and
  # globals (log, $LOG, $PROJECT_DIR), so file/system side effects persist; the
  # hook signals a hard provisioning failure by exiting/returning non-zero, which
  # the subshell exit status captures into rc.
  #
  # SECURITY/ISOLATION: cc-web-setup.local.sh is trusted, repo-owned code — the
  # same trust level as this committed script (and every other file in scripts/).
  # Running it in a SUBSHELL means a stray `exit` cannot abort provisioning and
  # its variable edits cannot leak back into main(); it does NOT sandbox the code
  # (a project hook legitimately needs the session's git/gh credentials).
  local local_hook="${PROJECT_DIR}/scripts/cc-web-setup.local.sh"
  if [ -f "$local_hook" ]; then
    log "Running project setup hook (cc-web-setup.local.sh)…"
    # shellcheck source=/dev/null
    ( source "$local_hook" ) || { log "WARNING: project setup hook reported errors (see ${LOG})."; rc=1; }
  fi

  if [ "$rc" -eq 0 ]; then
    log "Provisioning complete."
  else
    log "Provisioning finished with errors (see ${LOG})."
  fi
  exit "$rc"
}

# Run the imperative body only when executed, not when sourced. cc-web-setup is
# invoked by direct exec (`make cc-web-setup`) and via `bash …/cc-web-setup.sh`
# from web-bootstrap.sh, so BASH_SOURCE[0] == $0 holds for the real run; the test
# harness (which sources this file) skips main and just exercises the globals.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
