#!/usr/bin/env bash
#
# web-settings.sh — deterministic guards for the .claude/settings.json that
# cc-web-setup provisions. The skill (SKILL.md Phases 0/2/5) runs these instead of
# hand-editing JSON, so the marketplace-consistency (#157) and self-marketplace
# (#149) guards are mechanical, not prose the model might skip.
#
# Three subcommands, all PATH-ARG in -> STDOUT out (no stdin), VALIDATE-BEFORE-EMIT
# (a full document is computed and only printed on success — a failure prints
# nothing to stdout, so a caller piping the output never gets partial/corrupt JSON):
#
#   cover <settings.json>
#       Phase 5 assertion. Print every enabled plugin whose @marketplace is not a
#       key in extraKnownMarketplaces (it would install nothing, silently). Exit 1
#       if any orphan, 0 if fully covered. Read-only.
#
#   ensure <settings.json>
#       Phase 2 guard. Emit <settings.json> with every missing-but-KNOWN marketplace
#       added from assets/marketplaces.json. If any referenced marketplace is UNKNOWN
#       (not already declared and not in the lookup), print those marketplace names to
#       stderr and exit 4 with NO stdout — the skill then stops and asks the user.
#
#   strip-self <repo-root> <settings.json>
#       Phase 0 guard. If <repo-root>/.claude-plugin/marketplace.json exists, the repo
#       IS a marketplace; remove every enabledPlugins entry whose @marketplace equals
#       this repo's marketplace name and drop that marketplace from
#       extraKnownMarketplaces (enabling it would shadow working-tree edits with main's
#       published copy). Passthrough (emit unchanged) when the file is absent.
#
# Portability: POSIX-leaning bash, safe on macOS bash 3.2 — no associative arrays
# (declare -A), no mapfile/readarray, no GNU-only flags. Requires jq.
#
# Asset resolution: the marketplaces lookup is found relative to THIS script, so it
# works from both the canonical skills/cc-web-setup/scripts/ and the synced
# plugins/claude-code/skills/web-setup/scripts/ copy. Override with
# WEB_SETTINGS_MARKETPLACES for tests.

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
MARKETPLACES="${WEB_SETTINGS_MARKETPLACES:-${SCRIPT_DIR}/../assets/marketplaces.json}"

die() { printf '%s\n' "$1" >&2; exit "${2:-1}"; }

command -v jq >/dev/null 2>&1 || die "web-settings.sh: jq is required but not on PATH" 3

# Fail fast (exit 2, no stdout) if a settings file is not valid JSON, so every
# subcommand has a known-good document and set -e cannot mask a parse failure as
# an empty (and thus falsely "covered" / "no unknowns") result.
require_json() { jq empty "$1" >/dev/null 2>&1 || die "$2: not valid JSON: $1" 2; }

usage() {
  cat >&2 <<'EOF'
usage:
  web-settings.sh cover <settings.json>
  web-settings.sh ensure <settings.json>
  web-settings.sh strip-self <repo-root> <settings.json>
EOF
}

# List enabled plugins whose @marketplace is undeclared (or missing entirely).
cmd_cover() {
  [ "$#" -eq 1 ] || die "cover: expected <settings.json>" 2
  settings="$1"
  [ -f "$settings" ] || die "cover: no such file: $settings" 2
  require_json "$settings" cover
  orphans="$(jq -r '
    (.extraKnownMarketplaces // {} | keys) as $known
    | (.enabledPlugins // {}) | to_entries[]
    | select(.value == true)
    | .key as $id
    | ($id | split("@")[1]) as $mkt
    | select($mkt == null or ($known | index($mkt) | not))
    | $id
  ' "$settings")"
  if [ -n "$orphans" ]; then
    printf '%s\n' "$orphans"
    exit 1
  fi
}

# Add missing-but-known marketplaces; refuse (exit 4, no stdout) on unknowns.
cmd_ensure() {
  [ "$#" -eq 1 ] || die "ensure: expected <settings.json>" 2
  settings="$1"
  [ -f "$settings" ] || die "ensure: no such file: $settings" 2
  [ -f "$MARKETPLACES" ] || die "ensure: marketplaces lookup not found: $MARKETPLACES" 2
  require_json "$settings" ensure

  lookup="$(jq -c '.marketplaces' "$MARKETPLACES")"

  # Unresolved = an enabled plugin id with NO @marketplace, or one whose marketplace
  # is neither already declared nor in the known lookup. Report the plugin ids (so a
  # malformed bare id surfaces too — matching cover, not silently ignored).
  unresolved="$(jq -r --argjson lk "$lookup" '
    (.extraKnownMarketplaces // {} | keys) as $known
    | (.enabledPlugins // {}) | to_entries[]
    | select(.value == true) | .key as $id
    | ($id | split("@")[1]) as $mkt
    | select($mkt == null or (($known | index($mkt) | not) and ($lk | has($mkt) | not)))
    | $id
  ' "$settings")"
  if [ -n "$unresolved" ]; then
    {
      printf 'web-settings.sh ensure: enabled plugin(s) with an unresolved marketplace.\n'
      printf 'Each id below has no @marketplace or an unknown one — fix the id or declare\n'
      printf 'the marketplace in extraKnownMarketplaces, then re-run:\n'
      printf '%s\n' "$unresolved"
    } >&2
    exit 4
  fi

  # Validate-before-emit: jq builds the complete document or errors (nothing to stdout).
  jq --argjson lk "$lookup" '
    . as $root
    | ([ $root.enabledPlugins // {} | to_entries[] | select(.value == true) | .key | split("@")[1] ]
        | map(select(. != null)) | unique) as $needed
    | .extraKnownMarketplaces = (
        reduce $needed[] as $mkt (($root.extraKnownMarketplaces // {});
          if (.[$mkt] != null) then .
          elif ($lk[$mkt] != null) then . + { ($mkt): $lk[$mkt] }
          else . end)
      )
  ' "$settings"
}

# Drop self-referential plugins/marketplace when the target repo is itself a marketplace.
cmd_strip_self() {
  [ "$#" -eq 2 ] || die "strip-self: expected <repo-root> <settings.json>" 2
  repo_root="$1"
  settings="$2"
  [ -f "$settings" ] || die "strip-self: no such file: $settings" 2
  require_json "$settings" strip-self

  mkfile="${repo_root}/.claude-plugin/marketplace.json"
  if [ ! -f "$mkfile" ]; then
    jq '.' "$settings"   # not a marketplace repo — passthrough (still validated)
    return 0
  fi
  self="$(jq -r '.name // empty' "$mkfile")"
  if [ -z "$self" ]; then
    jq '.' "$settings"   # marketplace file without a name — nothing to strip (validated)
    return 0
  fi

  jq --arg self "$self" '
    .enabledPlugins = ((.enabledPlugins // {})
        | with_entries(select((.key | split("@")[1]) != $self)))
    | if (.extraKnownMarketplaces // {} | has($self))
      then del(.extraKnownMarketplaces[$self])
      else . end
  ' "$settings"
}

[ "$#" -ge 1 ] || { usage; exit 2; }
sub="$1"; shift
case "$sub" in
  cover)      cmd_cover "$@" ;;
  ensure)     cmd_ensure "$@" ;;
  strip-self) cmd_strip_self "$@" ;;
  -h|--help|help) usage ;;
  *) usage; exit 2 ;;
esac
