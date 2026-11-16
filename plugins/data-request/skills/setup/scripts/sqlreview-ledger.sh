#!/usr/bin/env bash
# Small JSON/file plumbing, sourced by sqlreview.sh. Bash 3.2 + jq 1.6.
ledger_check() {
  local file="$1" mode="$2"
  sr_no_symlinks "$(sr_abspath "$file")" || exit 2
  [ -f "$file" ] || sr_die 4 "ledger input is not a regular file: $file"
  # Slurp and require exactly one JSON value (jq otherwise accepts a JSON stream).
  jq -e -s 'length == 1' "$file" >/dev/null 2>&1 || sr_die 4 "invalid ledger $mode schema: not exactly one JSON value"
  jq -e --arg mode "$mode" -f "$SR_SCRIPT_DIR/sqlreview-ledger.jq" "$file" >/dev/null 2>&1 && return 0
  # Name the failing fields, never their values or the file path (rule: Entry fields in triage ledger.rst).
  local fields=''
  case "$mode" in
    entry|store) fields="$(jq -r --arg mode "$mode-errors" -f "$SR_SCRIPT_DIR/sqlreview-ledger.jq" "$file" 2>/dev/null)" || fields='' ;;
  esac
  [ -n "$fields" ] || fields='unreadable'
  sr_die 4 "invalid ledger $mode schema: field $fields (rule: see Entry fields in the triage ledger reference)"
}

# Old ledgers name the SQL revision key sql. The scaffold sweep refuses a field named sql, so a write
# saves it as sql_commit. An entry that holds both keys is ambiguous and is refused.
ledger_sql_key() {
  local file="$1" state
  state="$(jq -r --arg mode sql-key -f "$SR_SCRIPT_DIR/sqlreview-ledger.jq" "$file")" || sr_die 2 "cannot read ledger draft"
  case "$state" in
    clash) sr_die 4 "invalid ledger entry schema: field evidence_revision has both sql and sql_commit (rule: use sql_commit only)" ;;
    legacy) printf 'sqlreview: ledger field evidence_revision key sql is saved as sql_commit (rule: the scaffold sweep refuses a field named sql)\n' >&2 ;;
  esac
}

# One row per waiver: waived for the head given, lapsed for any other head. Fields only, never the reason.
ledger_waivers() {
  local saved="$1" head="$2"
  printf '%s' "$saved" | jq -r --arg head "$head" '
    (.gate_waivers // [])[] |
    if .head_sha == $head then ["waived", .gate, .check, .by, .at, .source]
    else ["lapsed", .gate, .check, "head \(.head_sha[0:12])"] end | join("\t")'
}

ledger_resume() {
  local saved="$1" current="$2" bad='[]' stage path expected actual artifact_rows
  ledger_check "$current" revisions
  artifact_rows="$(printf '%s' "$saved" | jq -r '.stage_evidence | to_entries[] | .key as $stage | .value.artifacts[] | [$stage, .path, .sha256] | join("\t")')"
  # Artifact paths resolve in the child root, never the installed plugin or state directory.
  # Schema excludes tabs/newlines; raw joining preserves backslashes with read -r.
  while IFS="$(printf '\t')" read -r stage path expected; do
    [ -n "$stage" ] || continue
    # The path policy of #552 runs before any read. A recorded sha256 of a data/ file or of unreviewed sql/
    # would let a changed ledger confirm a guess about researcher values. The artifact is not read and its
    # stage is rechecked. In a subshell, because the policy exits on a refusal. The message is fixed.
    if ! ( sr_refuse_unreviewed "$SR_ROOT/$path" "$path" ) >/dev/null 2>&1; then
      printf 'sqlreview: ledger artifact not read: data/ and unreviewed sql/ paths are refused, so its stage is rechecked (rule: no data/ paths, sql/v[0-9]+([.-][0-9]+)*/ only)\n' >&2
      bad="$(printf '%s' "$bad" | jq -c --arg stage "$stage" '. + [$stage] | unique')" || exit 2
      continue
    fi
    sr_no_symlinks "$SR_ROOT/$path" || exit 2
    actual=""
    if [ -f "$SR_ROOT/$path" ]; then
      actual="$(sr_sha256 "$SR_ROOT/$path")" || sr_die 2 "cannot hash ledger artifact: $path"
    fi
    if [ "$actual" != "$expected" ]; then
      bad="$(printf '%s' "$bad" | jq -c --arg stage "$stage" '. + [$stage] | unique')" || exit 2
    fi
  done <<EOF
$artifact_rows
EOF
  # sql and sql_commit name the same SQL revision, so old and new ledgers and revision files compare.
  printf '%s' "$saved" | jq --slurpfile current "$current" --argjson bad "$bad" '
    def revision($rev; $key):
      if $key == "sql" or $key == "sql_commit" then ($rev.sql_commit // $rev.sql) else $rev[$key] end;
    . as $entry |
    [.stages_done[] | . as $stage | select(
      ($bad | index($stage)) != null or
      any($entry.stage_evidence[$stage].sources[]; . as $source |
        revision($current[0]; $source) != revision($entry.evidence_revision; $source)))] as $recheck |
    {entry: $entry, recheck: $recheck, unchanged: ($entry.stages_done - $recheck)}'
}

cmd_ledger() (
  sr_need_jq
  local session=0 action dest dir lock tmp='' root saved ticket draft ancestor staged
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
    waivers) [ $# -eq 2 ] || usage
      jq -en --arg head "$2" '$head | test("^[0-9a-f]{40}$")' >/dev/null || sr_die 4 "invalid head commit (rule: the full 40-character lowercase SHA)" ;;
    *) usage ;;
  esac
  ticket="$1"
  jq -en --arg ticket "$ticket" '$ticket | test("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*$")' >/dev/null || sr_die 4 "invalid ledger ticket (rule: the fully qualified form owner/repo#N)"
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
  if [ "$action" = get ] || [ "$action" = waivers ]; then
    [ -e "$dest" ] || sr_die 6 "no stored ledger: $dest"
    ledger_check "$dest" store
    saved="$(jq -ce --arg ticket "$ticket" '.entries[] | select(.ticket == $ticket)' "$dest")" || sr_die 6 "no ledger entry for $ticket"
    if [ "$action" = waivers ]; then
      ledger_waivers "$saved" "$2"
    elif [ $# -eq 3 ]; then
      SR_ROOT="$(sr_init_root)"
      ledger_resume "$saved" "$3"
    else printf '%s\n' "$saved"; fi
    exit $?
  fi
  draft="$2"
  ledger_check "$draft" entry
  ledger_sql_key "$draft"
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
  # Every entry in the written store uses sql_commit, so the whole file passes the scaffold sweep.
  staged="$(jq --arg mode rename-store -f "$SR_SCRIPT_DIR/sqlreview-ledger.jq" "$tmp")" || sr_die 2 "cannot stage ledger"
  printf '%s\n' "$staged" > "$tmp" || sr_die 2 "cannot stage ledger"
  ledger_check "$tmp" store
  mv -f "$tmp" "$dest" || sr_die 2 "cannot replace ledger"
  printf 'saved\t%s\t%s\n' "$ticket" "$dest"
)
