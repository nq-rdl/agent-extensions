#!/usr/bin/env bash
#
# cc-web-setup.sh — OPTIONAL pre-snapshot provisioning for a Claude Code on the
# web (cloud) VM.
#
# Plugins do NOT need this script. Plugins declared in .claude/settings.json
# (extraKnownMarketplaces + enabledPlugins) are installed by Claude Code at
# session start in the cloud, so their skills are available on the FIRST session
# with no setup-script step. See SKILL.md (Phase 2) for the declarative path.
#
# What this script is for: baking HEAVY, non-plugin dependencies into the
# environment snapshot ONCE, before Claude starts. Run from the web
# environment's *setup script* — the bash that runs before Claude and whose
# filesystem is captured in the snapshot — exposed as `make cc-web-setup`.
# Anything installed here is in the image, so every later session starts with it
# already present instead of re-fetching it per session. This is a latency
# optimization, not a requirement: a repo with no heavy pre-snapshot deps does
# not need to wire it at all.
#
# The script itself is PORTABLE and carries no project-specific dependencies — it
# only sources an optional, repo-owned `scripts/cc-web-setup.local.sh` (the
# pre-snapshot extension seam) if present. Put project specifics there.
#
# Idempotent and safe to re-run: with no project hook it is a no-op; the project
# hook guards its own heavy work.
#
# Exit status reflects provisioning (0 = done or nothing to do, non-zero =
# the project hook failed) so a setup script can surface provisioning failures.
#
# Output discipline: keep stdout concise — verbose tool output goes to $LOG.
set -uo pipefail

# Only colorize on a TTY — cloud setup stdout is non-TTY, where ANSI escapes are
# just noise.
if [ -t 1 ]; then _BLU=$'\033[34m'; _RST=$'\033[0m'; else _BLU=''; _RST=''; fi
log() { printf '%s[cc-web-setup]%s %s\n' "$_BLU" "$_RST" "$*"; }

# Imperative body. Wrapped in main() so the script is *sourceable* for unit
# tests: executing it (`make cc-web-setup`, or `bash …/cc-web-setup.sh`) runs
# main; sourcing it (the test harness) only defines the function/globals above so
# they can be exercised without running the body or touching the log file. LOG/
# PROJECT_DIR live IN here (mirroring web-bootstrap.sh) so sourcing never
# truncates the real log.
main() {
  # Verbose output sink (keeps stdout clean — see header).
  LOG="${TMPDIR:-/tmp}/rdl-cc-web-setup.log"
  ( umask 077; : > "$LOG" ) 2>/dev/null || LOG=/dev/null

  # Resolve the repo root. `make cc-web-setup` runs from the repo root; fall back
  # to the script's own location so it also works when run by hand.
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

  local rc=0

  # --- SOURCE PROJECT HOOK (optional, project-specific) ---------------------
  # A repo that needs heavy provisioning baked into the snapshot (language
  # toolchains, container runtimes, k8s-in-docker, large model/data caches, etc.)
  # puts it in scripts/cc-web-setup.local.sh, which is sourced here if present. A
  # subshell inherits main()'s helpers and globals (log, $LOG, $PROJECT_DIR), so
  # file/system side effects persist; the hook signals a hard provisioning
  # failure by exiting/returning non-zero, which the subshell exit status
  # captures into rc.
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
  else
    log "No project setup hook (scripts/cc-web-setup.local.sh) — nothing to pre-snapshot."
  fi

  if [ "$rc" -eq 0 ]; then
    log "Provisioning complete."
  else
    log "Provisioning finished with errors (see ${LOG})."
  fi
  exit "$rc"
}

# Run the imperative body only when executed, not when sourced. cc-web-setup is
# invoked by direct exec (`make cc-web-setup`) and via `bash …/cc-web-setup.sh`,
# so BASH_SOURCE[0] == $0 holds for the real run; the test harness (which sources
# this file) skips main and just exercises the globals.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
