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
#   verify <settings.json>
#       Phase 2/5 assertion. cover/ensure only check the @marketplace SUFFIX is
#       declared/known — they never check the plugin NAME exists in that
#       marketplace's catalog, so a hallucinated id (real marketplace, non-existent
#       plugin, e.g. `pyright-lsp@claude-plugins-official`) sails through and lands
#       as "Declared but NOT installed" forever. verify closes that hole: for every
#       enabled id it resolves the marketplace's catalog (the curated
#       marketplaces.json set, a pre-fetched WEB_SETTINGS_CATALOG_DIR/<mkt>.json, or a
#       best-effort HTTPS fetch of the marketplace's .claude-plugin/marketplace.json)
#       and classifies the id three ways:
#         - verified     — id is curated or present in an obtained catalog (silent).
#         - non-existent — the marketplace catalog WAS obtained and the id is absent
#                          → printed to STDOUT, exit 1 (the dataops #169 failure).
#         - unverifiable — the catalog could not be obtained (offline / git-proxy 403)
#                          → noted on STDERR, never fails (can't prove non-existence).
#       Read-only. Honours WEB_SETTINGS_CATALOG_DIR (pre-fetched catalogs, keyed by
#       marketplace name) and WEB_SETTINGS_NO_FETCH=1 (skip the network entirely —
#       used by the unit tests for determinism).
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

# Fail fast (exit 2, no stdout) unless the file is a JSON OBJECT with object-typed
# enabledPlugins/extraKnownMarketplaces when present. `jq empty` alone accepts ANY
# well-formed JSON (null, [], scalars), which would let a non-object slip the guard:
# a `null` settings file reads as "fully covered", and ensure's documented
# `> tmp && mv` could overwrite the user's file with a stub; a wrong-typed field
# would leak a bare jq exit 5. Asserting shape collapses every malformed input into
# the advertised exit 2.
require_json() {
  jq -e '
    type == "object"
    and ((.enabledPlugins // {})        | type == "object")
    and ((.extraKnownMarketplaces // {}) | type == "object")
  ' "$1" >/dev/null 2>&1 \
    || die "$2: must be a JSON object with object-typed enabledPlugins/extraKnownMarketplaces: $1" 2
}

usage() {
  cat >&2 <<'EOF'
usage:
  web-settings.sh cover <settings.json>
  web-settings.sh ensure <settings.json>
  web-settings.sh verify <settings.json>
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
  # The lookup must itself be an object with an object .marketplaces, or the reduce
  # below would leak a bare jq exit 5 instead of the advertised exit 2.
  jq -e 'type == "object" and (.marketplaces | type == "object")' "$MARKETPLACES" >/dev/null 2>&1 \
    || die "ensure: marketplaces lookup must be an object with an object .marketplaces: $MARKETPLACES" 2

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

# Assert every enabled plugin id actually EXISTS in its marketplace catalog.
cmd_verify() {
  [ "$#" -eq 1 ] || die "verify: expected <settings.json>" 2
  settings="$1"
  [ -f "$settings" ] || die "verify: no such file: $settings" 2
  require_json "$settings" verify

  # Curated known-good ids (teamExternals + baseline) — always trusted, no network.
  # A missing/odd lookup just yields an empty curated set; verify still works off catalogs.
  curated=""
  if [ -f "$MARKETPLACES" ] && jq -e 'type == "object"' "$MARKETPLACES" >/dev/null 2>&1; then
    curated="$(jq -r '
      ((.teamExternals // []) + (.baseline.always // []) + (.baseline.lsp // []))
      | map(.id // empty) | .[]
    ' "$MARKETPLACES" 2>/dev/null || true)"
  fi

  enabled_ids="$(jq -r '(.enabledPlugins // {}) | to_entries[] | select(.value == true) | .key' "$settings")"
  # Nothing enabled, or nothing with a marketplace — nothing to verify.
  [ -n "$enabled_ids" ] || return 0

  work="$(mktemp -d)"
  trap 'rm -rf "$work"' EXIT

  # Resolve each referenced marketplace's catalog once. A catalog is "obtained" only
  # when we can actually read its plugin names; otherwise the marketplace is unreachable
  # and its ids are unverifiable, NOT non-existent.
  mkts="$(printf '%s\n' "$enabled_ids" | sed -n 's/^[^@]*@\(..*\)$/\1/p' | sort -u)"
  for mkt in $mkts; do
    catfile="$work/cat.$mkt"; okflag="$work/ok.$mkt"
    # 1) Pre-fetched catalog dir (deterministic; used by tests and by callers that
    #    fetched once up front).
    if [ -n "${WEB_SETTINGS_CATALOG_DIR:-}" ] && [ -f "$WEB_SETTINGS_CATALOG_DIR/$mkt.json" ]; then
      if jq -r '.plugins[]?.name // empty' "$WEB_SETTINGS_CATALOG_DIR/$mkt.json" > "$catfile" 2>/dev/null; then
        : > "$okflag"
      fi
      continue
    fi
    # 2) Best-effort HTTPS fetch of the marketplace's authoritative manifest. raw.* is
    #    allowlisted on the web (it is ordinary HTTPS, not the git protocol the proxy 403s).
    [ "${WEB_SETTINGS_NO_FETCH:-0}" = "1" ] && continue
    command -v curl >/dev/null 2>&1 || continue
    repo="$(jq -r --arg m "$mkt" '.extraKnownMarketplaces[$m].source.repo // empty' "$settings" 2>/dev/null || true)"
    if [ -z "$repo" ] && [ -f "$MARKETPLACES" ]; then
      repo="$(jq -r --arg m "$mkt" '.marketplaces[$m].source.repo // empty' "$MARKETPLACES" 2>/dev/null || true)"
    fi
    [ -n "$repo" ] || continue
    raw="https://raw.githubusercontent.com/$repo/HEAD/.claude-plugin/marketplace.json"
    if curl -fsSL --max-time 8 "$raw" -o "$work/raw.$mkt" 2>/dev/null \
       && jq -r '.plugins[]?.name // empty' "$work/raw.$mkt" > "$catfile" 2>/dev/null; then
      : > "$okflag"
    fi
  done

  missing=""; unverifiable=""
  for id in $enabled_ids; do
    case "$id" in *@*) ;; *) continue ;; esac   # bare ids are cover/ensure's job
    name="${id%@*}"; mkt="${id##*@}"
    # Curated ids are trusted without a fetch.
    if printf '%s\n' "$curated" | grep -Fxq "$id"; then continue; fi
    if [ -f "$work/ok.$mkt" ]; then
      if grep -Fxq "$name" "$work/cat.$mkt"; then
        continue                                   # verified: present in catalog
      fi
      missing="${missing}${id}
"
    else
      unverifiable="${unverifiable}${id}
"
    fi
  done

  if [ -n "$unverifiable" ]; then
    {
      printf 'web-settings.sh verify: could NOT reach the marketplace catalog for these enabled\n'
      printf 'plugins, so their existence is UNVERIFIED (marketplace unreachable — e.g. offline or\n'
      printf 'the git-proxy 403). Re-run with network, or confirm each id against its\n'
      printf 'marketplace.json before committing:\n'
      printf '%s' "$unverifiable"
    } >&2
  fi
  if [ -n "$missing" ]; then
    printf '%s' "$missing"   # non-existent ids -> stdout (mirrors cover)
    exit 1
  fi
}

# Drop self-referential plugins/marketplace when the target repo is itself a marketplace.
cmd_strip_self() {
  [ "$#" -eq 2 ] || die "strip-self: expected <repo-root> <settings.json>" 2
  repo_root="$1"
  settings="$2"
  # Fail fast on a bad repo-root rather than silently skipping the Phase 0 guard.
  [ -d "$repo_root" ] || die "strip-self: not a directory: $repo_root" 2
  [ -f "$settings" ] || die "strip-self: no such file: $settings" 2
  require_json "$settings" strip-self

  mkfile="${repo_root}/.claude-plugin/marketplace.json"
  if [ ! -f "$mkfile" ]; then
    jq '.' "$settings"   # not a marketplace repo — passthrough (still validated)
    return 0
  fi
  # A present marketplace file must be valid JSON, or we cannot trust the guard.
  require_json "$mkfile" strip-self
  self="$(jq -r '.name // empty' "$mkfile")"
  if [ -z "$self" ]; then
    jq '.' "$settings"   # valid marketplace file but no name — nothing to strip
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
  verify)     cmd_verify "$@" ;;
  strip-self) cmd_strip_self "$@" ;;
  -h|--help|help) usage ;;
  *) usage; exit 2 ;;
esac
