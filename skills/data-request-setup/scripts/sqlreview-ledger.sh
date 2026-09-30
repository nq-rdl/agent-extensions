#!/usr/bin/env bash
# Small JSON/file plumbing, sourced by sqlreview.sh. Bash 3.2 + jq 1.6.
ledger_check() {
  local file="$1" mode="$2"
  sr_no_symlinks "$(sr_abspath "$file")" || exit 2
  [ -f "$file" ] || sr_die 4 "ledger input is not a regular file: $file"
  # Slurp and require exactly one JSON value (jq otherwise accepts a JSON stream).
  jq -e -s 'length == 1' "$file" >/dev/null 2>&1 &&
    jq -e --arg mode "$mode" -f "$SR_SCRIPT_DIR/sqlreview-ledger.jq" "$file" >/dev/null 2>&1 ||
    sr_die 4 "invalid ledger $mode schema: $file"
}

ledger_resume() {
  local saved="$1" current="$2" bad='[]' stage path expected actual
  ledger_check "$current" revisions
  # Artifact paths resolve in the child root, never the installed plugin or state directory.
  while IFS="$(printf '\t')" read -r stage path expected; do
    [ -n "$stage" ] || continue
    sr_no_symlinks "$SR_ROOT/$path" || exit 2
    actual=""
    if [ -f "$SR_ROOT/$path" ]; then
      actual="$(sr_sha256 "$SR_ROOT/$path")" || sr_die 2 "cannot hash ledger artifact: $path"
    fi
    if [ "$actual" != "$expected" ]; then
      bad="$(printf '%s' "$bad" | jq -c --arg stage "$stage" '. + [$stage] | unique')" || exit 2
    fi
  done <<EOF
$(printf '%s' "$saved" | jq -r '.stage_evidence | to_entries[] | .key as $stage | .value.artifacts[] | [$stage, .path, .sha256] | @tsv')
EOF
  printf '%s' "$saved" | jq --slurpfile current "$current" --argjson bad "$bad" '
    . as $entry |
    [.stages_done[] | . as $stage | select(
      ($bad | index($stage)) != null or
      any($entry.stage_evidence[$stage].sources[]; . as $source |
        $current[0][$source] != $entry.evidence_revision[$source]))] as $recheck |
    {entry: $entry, recheck: $recheck, unchanged: ($entry.stages_done - $recheck)}'
}

cmd_ledger() (
  sr_need_jq
  local session=0 action dest dir lock tmp='' root saved ticket draft ancestor
  if [ "${1:-}" = --session ]; then session=1; shift; fi
  [ $# -ge 1 ] || usage
  action="$1"; shift
  if [ "$action" = check ]; then
    [ $# -eq 1 ] || usage
    ledger_check "$1" store
    printf 'ok\n'; exit 0
  fi
  case "$action" in
    get) [ $# -eq 1 ] || { [ $# -eq 3 ] && [ "$2" = --against ]; } || usage ;;
    set) [ $# -eq 2 ] || usage ;;
    *) usage ;;
  esac
  ticket="$1"
  jq -en --arg ticket "$ticket" '$ticket | test("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*$")' >/dev/null || sr_die 4 "invalid ledger ticket"
  if [ "$session" = 1 ]; then
    root="${XDG_STATE_HOME:-${HOME:?HOME is required}/.local/state}"
    case "$root" in /*) ;; *) sr_die 2 "session state root must be absolute" ;; esac
    dest="$root/rdl-agent-extensions/data-request/ledger.json"
    sr_no_symlinks "$dest" || exit 2
    ancestor="$root"
    while [ ! -d "$ancestor" ] && [ "$ancestor" != / ]; do ancestor="$(dirname "$ancestor")"; done
    if git -C "$ancestor" rev-parse --show-toplevel >/dev/null 2>&1; then
      sr_die 2 "session state must be outside repositories: $root"
    fi
  else
    root="$(sr_init_root)"
    dest="$root/$SR_DIR/ledger.json"
  fi
  sr_no_symlinks "$dest" || exit 2
  if [ "$action" = get ]; then
    [ -e "$dest" ] || sr_die 6 "no stored ledger: $dest"
    ledger_check "$dest" store
    saved="$(jq -ce --arg ticket "$ticket" '.entries[] | select(.ticket == $ticket)' "$dest")" || sr_die 6 "no ledger entry for $ticket"
    if [ $# -eq 3 ]; then
      SR_ROOT="$(sr_init_root)"
      ledger_resume "$saved" "$3"
    else printf '%s\n' "$saved"; fi
    exit $?
  fi
  draft="$2"
  ledger_check "$draft" entry
  jq -e --arg ticket "$ticket" '.ticket == $ticket' "$draft" >/dev/null || sr_die 4 "ledger draft ticket does not match $ticket"
  # Lock prevents two per-ticket updates from losing each other. Never remove another writer's lock.
  umask 077
  dir="$(dirname "$dest")"; lock="$dir/.ledger.lock"
  mkdir -p "$dir" || sr_die 2 "cannot create ledger directory"
  mkdir "$lock" 2>/dev/null || sr_die 2 "ledger locked: $lock (retry; inspect stale lock before removing it)"
  trap '[ -z "$tmp" ] || rm -f "$tmp"; rmdir "$lock"' EXIT
  trap 'exit 2' HUP INT TERM
  sr_no_symlinks "$dest" || exit 2
  tmp="$(mktemp "$dir/.ledger.XXXXXX")" || sr_die 2 "cannot stage ledger"
  if [ -e "$dest" ]; then
    ledger_check "$dest" store
    jq --slurpfile draft "$draft" --arg ticket "$ticket" \
      '.entries = ([.entries[] | select(.ticket != $ticket)] + $draft)' "$dest" > "$tmp" || sr_die 2 "cannot stage ledger"
  else
    jq -n --slurpfile draft "$draft" '{schemaVersion: 1, entries: $draft}' > "$tmp" || sr_die 2 "cannot stage ledger"
  fi
  ledger_check "$tmp" store
  mv -f "$tmp" "$dest" || sr_die 2 "cannot replace ledger"
  printf 'saved\t%s\t%s\n' "$ticket" "$dest"
)
