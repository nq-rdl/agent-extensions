#!/usr/bin/env bash
# Sourced by sqlreview.sh. Read-only GitHub tag/tree/blob plumbing, never a checkout/import.
# Stable release tags only: prereleases and arbitrary refs have no supported ordering here.
_sr_release_tag() {
  printf '%s\n' "$1" | grep -Eq '^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
}

_sr_lift_tree() { # library tag -> cached complete tree, or failure (unknown, never absent)
  local library="$1" tag="$2" file obj type sha depth=0
  file="$LS_TMP/${library##*/}-$tag.json"
  [ ! -f "$file.unknown" ] || return 1
  if [ -f "$file" ]; then printf '%s\n' "$file"; return 0; fi
  : > "$file.unknown"
  obj="$(gh api "repos/$library/git/ref/tags/$tag" 2>/dev/null)" || return 1
  while :; do
    type="$(printf '%s' "$obj" | jq -er '.object.type' 2>/dev/null)" || return 1
    sha="$(printf '%s' "$obj" | jq -er '.object.sha | select(test("^[0-9a-f]{40}$"))' 2>/dev/null)" || return 1
    [ "$type" != commit ] || break
    [ "$type" = tag ] && [ "$depth" -lt 8 ] || return 1
    obj="$(gh api "repos/$library/git/tags/$sha" 2>/dev/null)" || return 1
    depth=$((depth + 1))
  done
  obj="$(gh api "repos/$library/git/commits/$sha" 2>/dev/null)" || return 1
  sha="$(printf '%s' "$obj" | jq -er '.tree.sha | select(test("^[0-9a-f]{40}$"))' 2>/dev/null)" || return 1
  gh api "repos/$library/git/trees/$sha?recursive=1" > "$file" 2>/dev/null || return 1
  jq -e '.truncated == false and (.tree | type == "array")' "$file" >/dev/null 2>&1 || return 1
  rm -f "$file.unknown"
  printf '%s\n' "$file"
}

_sr_lift_symbol() { # library tag path symbol -> present|absent|unknown
  local library="$1" tag="$2" path="$3" symbol="$4" tree node sha file
  tree="$(_sr_lift_tree "$library" "$tag")" || { printf 'unknown\n'; return; }
  node="$(jq -c --arg path "$path" '[.tree[] | select(.path == $path)]' "$tree")" || { printf 'unknown\n'; return; }
  if [ "$node" = '[]' ]; then printf 'absent\n'; return; fi
  sha="$(printf '%s' "$node" | jq -er 'select(length == 1) | .[0] | select(.type == "blob" and (.mode == "100644" or .mode == "100755")) | .sha | select(test("^[0-9a-f]{40}$"))')" || { printf 'unknown\n'; return; }
  file="$LS_TMP/${library##*/}-$sha.blob"
  if [ ! -f "$file" ]; then
    gh api "repos/$library/git/blobs/$sha" > "$file.tmp" 2>/dev/null &&
      jq -e '.encoding == "base64" and (.content | type == "string")' "$file.tmp" >/dev/null 2>&1 &&
      mv "$file.tmp" "$file" || { printf 'unknown\n'; return; }
  fi
  # Exact identifier token, not a semantic/API compatibility claim. This is only a nudge.
  jq -er --arg symbol "$symbol" '.content | gsub("\\s"; "") | @base64d | if test("(^|[^A-Za-z0-9_])" + $symbol + "([^A-Za-z0-9_]|$)") then "present" else "absent" end' "$file" 2>/dev/null || printf 'unknown\n'
}

cmd_lifts_stale() {
  [ $# -eq 3 ] && [ "$2" = --tag ] || usage
  local slug="$1" tag="$3" ledger entry library id unit path symbol absent_tag prior current result
  local entries='[]' units message count total
  _sr_release_tag "$tag" || sr_die 2 "--tag requires a stable X.Y.Z release tag (optional v prefix)"
  sr_need_jq; sr_require_root; sr_safe_slug "$slug"
  ledger="$SR_REVIEWS/$slug/lifts.json"
  sr_no_symlinks "$ledger" || exit 2
  [ -f "$ledger" ] || sr_die 2 "missing lift ledger for $slug"
  cmd_check "$ledger" >/dev/null || sr_die 4 "invalid lift ledger for $slug"
  jq -e '.kind == "lifts" and .slug == $slug' --arg slug "$slug" "$ledger" >/dev/null || sr_die 4 "ledger kind/slug mismatch"
  command -v gh >/dev/null 2>&1 || sr_die 2 "gh is required for read-only tagged-library inspection"
  LS_TMP="$(mktemp -d "${TMPDIR:-/tmp}/sqlreview-lifts.XXXXXX")" || sr_die 2 "cannot create scratch directory"
  trap 'rm -rf "$LS_TMP"' EXIT
  while IFS= read -r entry; do
    id="$(printf '%s' "$entry" | jq -r '.id')"
    library="$(printf '%s' "$entry" | jq -r '.library')"
    units='[]'
    while IFS= read -r unit; do
      path="$(printf '%s' "$unit" | jq -r '.path')"
      symbol="$(printf '%s' "$unit" | jq -r '.symbol')"
      absent_tag="$(printf '%s' "$unit" | jq -r '.absent_tag')"
      if ! jq -en --arg tag "$tag" --arg old "$absent_tag" '
        def version: ltrimstr("v") | split(".") | map(tonumber);
        ($tag | version) > ($old | version)' >/dev/null; then result=not-newer
      else
        prior="$(_sr_lift_symbol "$library" "$absent_tag" "$path" "$symbol")"
        current="$(_sr_lift_symbol "$library" "$tag" "$path" "$symbol")"
        if [ "$prior" = unknown ] || [ "$current" = unknown ]; then result=unknown
        elif [ "$prior" = present ]; then result=absence-contradicted
        elif [ "$current" = present ]; then result=may-be-resolved
        else result=absent; fi
      fi
      units="$(printf '%s' "$units" | jq -c --argjson unit "$unit" --arg result "$result" '. + [$unit + {result: $result}]')"
    done < <(printf '%s' "$entry" | jq -c '.units[]?')
    total="$(printf '%s' "$units" | jq 'length')"
    count="$(printf '%s' "$units" | jq '[.[] | select(.result == "may-be-resolved")] | length')"
    if [ "$total" -eq 0 ]; then result=untracked
    elif [ "$count" -eq "$total" ]; then result=may-be-resolved
    elif [ "$count" -gt 0 ]; then result=partly-resolved
    else result="$(printf '%s' "$units" | jq -r '
      if any(.[]; .result == "unknown") then "unknown"
      elif any(.[]; .result == "absence-contradicted") then "absence-contradicted"
      elif all(.[]; .result == "not-newer") then "not-newer" else "absent" end')"; fi
    case "$result" in
      may-be-resolved) message="$id may be resolved in $tag; inspect behaviour and approval before adoption" ;;
      partly-resolved) message="$id may be resolved in $tag for $count/$total tracked units only; remaining shortfalls still need review" ;;
      *) message="$id: $result in $tag (no adoption decision)" ;;
    esac
    entries="$(printf '%s' "$entries" | jq -c --arg id "$id" --arg library "$library" --arg result "$result" --arg message "$message" --argjson units "$units" '. + [{id: $id, library: $library, result: $result, message: $message, units: $units}]')"
  done < <(jq -c '.lifts[]' "$ledger")
  jq -n --arg slug "$slug" --arg tag "$tag" --argjson entries "$entries" '{slug: $slug, tag: $tag, entries: $entries}'
}
