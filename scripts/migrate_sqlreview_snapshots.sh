#!/usr/bin/env bash
# Maintainer-only cleanup. The passive hash index is never runtime evidence.
set -euo pipefail

fail() { printf 'sqlreview cleanup: %s\n' "$*" >&2; exit 1; }
usage() { printf 'usage: bash scripts/migrate_sqlreview_snapshots.sh --root CHILD [--check]\n' >&2; exit 2; }
root=
check=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --root) [ "$#" -ge 2 ] || usage; [ -z "$root" ] || usage; root=$2; shift 2 ;;
        --check) check=true; shift ;;
        *) usage ;;
    esac
done
[ -n "$root" ] || usage
command -v jq >/dev/null 2>&1 || fail 'jq is required'
command -v git >/dev/null 2>&1 || fail 'git is required'
[ ! -L "$root" ] && [ -d "$root" ] || fail 'root must be a real directory'
root=$(cd "$root" && pwd -P)
[ "$(git -C "$root" rev-parse --show-toplevel 2>/dev/null)" = "$root" ] || fail 'root must be the child git working-tree root'
case "$root" in *[[:cntrl:]]*) fail 'root contains a control character' ;; esac

scratch=$(mktemp -d "${TMPDIR:-/tmp}/sqlreview-cleanup.XXXXXX")
atomic_temp=
trap 'if [ -n "$atomic_temp" ]; then rm -f -- "$atomic_temp"; fi; rm -rf -- "$scratch"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Check each path component without following a symlink or accepting a FIFO.
check_directory() {
    [ ! -L "$1" ] || fail "symlink refused: $1"
    if [ -e "$1" ]; then [ -d "$1" ] || fail "directory required: $1"; fi
}
check_file() {
    [ ! -L "$1" ] || fail "symlink refused: $1"
    if [ -e "$1" ]; then [ -f "$1" ] || fail "regular file required: $1"; fi
}
check_json() {
    jq -s -e 'length == 1' "$1" >/dev/null 2>&1 || fail "invalid JSON: $1"
}
# Only direct files in a review and immediate history SQL copies qualify.
is_snapshot() {
    case "$1" in .sqlreview/reviews/*) ;; *) return 1 ;; esac
    local tail slug rest history_name
    tail=${1#.sqlreview/reviews/}
    slug=${tail%%/*}
    [ -n "$slug" ] && [ "$slug" != . ] && [ "$slug" != .. ] && [ "$tail" != "$slug" ] || return 1
    rest=${tail#*/}
    case "$rest" in
        source.sql|scope.source.sql) return 0 ;;
        history/*.sql)
            history_name=${rest#history/}
            case "$history_name" in */*) return 1 ;; *) return 0 ;; esac ;;
        *) return 1 ;;
    esac
}
sha256() {
    local result
    if command -v sha256sum >/dev/null 2>&1; then
        result=$(sha256sum < "$1")
    elif command -v shasum >/dev/null 2>&1; then
        result=$(shasum -a 256 < "$1")
    else
        fail 'sha256sum or shasum is required'
    fi
    result=${result%% *}
    [ "${#result}" -eq 64 ] || fail "invalid SHA-256 result: $1"
    case "$result" in *[!0-9a-f]*) fail "invalid SHA-256 result: $1" ;; esac
    printf '%s\n' "$result"
}

store=$root/.sqlreview
ignore=$store/.gitignore
audit=$root/docs/maintenance/sqlreview-snapshot-hashes.json
check_directory "$store"
check_directory "$root/docs"
check_directory "$root/docs/maintenance"
check_file "$audit"
check_file "$ignore"
paths=()
hashes=()
path_count=0
if [ -d "$store" ]; then
    find "$store" -print0 > "$scratch/paths" || fail 'cannot inventory review store'
    while IFS= read -r -d '' path; do
        relative=${path#"$root/"}
        case "$relative" in *[[:cntrl:]]*) fail "path contains a control character: $relative" ;; esac
        [ ! -L "$path" ] || fail "symlink refused: $relative"
        if [ -d "$path" ]; then
            is_snapshot "$relative" && fail "regular snapshot file required: $relative"
        elif [ -f "$path" ]; then
            case "$path" in *.json) check_json "$path" ;; esac
            if is_snapshot "$relative"; then
                paths[$path_count]=$relative
                path_count=$((path_count + 1))
            fi
        else
            fail "nonregular file refused: $relative"
        fi
    done < "$scratch/paths"
fi
if [ -f "$audit" ]; then
    check_json "$audit"
    jq -e '
        type == "object" and (keys == ["schemaVersion", "snapshots"]) and
        .schemaVersion == 1 and (.snapshots | type == "object") and
        (.snapshots | to_entries | all(.[];
            (.key | test("[[:cntrl:]]") | not) and
            (.key | test("^\\.sqlreview/reviews/[^/\\r\\n]+/(source\\.sql|scope\\.source\\.sql|history/[^/\\r\\n]*\\.sql)$")) and
            (.key | split("/")[2] != "." and split("/")[2] != "..") and
            (.value | type == "object" and keys == ["sql_sha256"]) and
            (.value.sql_sha256 | type == "string" and test("^[0-9a-f]{64}$"))))
    ' "$audit" >/dev/null 2>&1 || fail 'invalid passive audit index schema or paths'
    cp "$audit" "$scratch/index.json"
else
    printf '{"schemaVersion":1,"snapshots":{}}\n' > "$scratch/index.json"
fi
# No project writes until every candidate and record has passed preflight.
i=0
while [ "$i" -lt "$path_count" ]; do
    relative=${paths[$i]}
    hash=$(sha256 "$root/$relative")
    hashes[$i]=$hash
    jq -e --arg path "$relative" --arg hash "$hash" '
        .snapshots[$path] == null or .snapshots[$path].sql_sha256 == $hash
    ' "$scratch/index.json" >/dev/null || fail "audit SHA conflict: $relative"
    jq --arg path "$relative" --arg hash "$hash" '
        .snapshots[$path] = {sql_sha256: $hash}
    ' "$scratch/index.json" > "$scratch/index.next"
    mv "$scratch/index.next" "$scratch/index.json"
    printf '%s %s\n' "$hash" "$relative"
    i=$((i + 1))
done
if "$check"; then
    printf 'check only: %s SQL copies planned for removal; no files changed\n' "$path_count"
    exit 0
fi
# Persist every SHA in a single same-directory atomic replacement BEFORE deletion.
if [ "$path_count" -gt 0 ]; then
    if [ ! -f "$audit" ] || ! jq -e --slurpfile expected "$scratch/index.json" '. == $expected[0]' "$audit" >/dev/null; then
        mkdir -p "$root/docs/maintenance"
        atomic_temp=$(mktemp "$root/docs/maintenance/.sqlreview-hashes.XXXXXX")
        cat "$scratch/index.json" > "$atomic_temp"
        mv -f -- "$atomic_temp" "$audit"
        atomic_temp=
    fi
fi
# Preserve custom ignore bytes as a prefix; append only missing exclusions.
if [ -d "$store" ]; then
    if [ -f "$ignore" ]; then cat "$ignore" > "$scratch/ignore"; else : > "$scratch/ignore"; fi
    for rule in '/reviews/**/source.sql' '/reviews/**/scope.source.sql' '/reviews/**/history/*.sql'; do
        if ! grep -F -x -q -- "$rule" "$scratch/ignore"; then
            if [ -s "$scratch/ignore" ] && [ -n "$(tail -c 1 "$scratch/ignore")" ]; then printf '\n' >> "$scratch/ignore"; fi
            printf '%s\n' "$rule" >> "$scratch/ignore"
        fi
    done
    if [ ! -f "$ignore" ] || ! cmp -s "$ignore" "$scratch/ignore"; then
        atomic_temp=$(mktemp "$store/.sqlreview-ignore.XXXXXX")
        cat "$scratch/ignore" > "$atomic_temp"
        mv -f -- "$atomic_temp" "$ignore"
        atomic_temp=
    fi
fi
i=0
while [ "$i" -lt "$path_count" ]; do
    relative=${paths[$i]}
    check_file "$root/$relative"
    [ -f "$root/$relative" ] || fail "snapshot disappeared after preflight: $relative"
    [ "$(sha256 "$root/$relative")" = "${hashes[$i]}" ] || fail "snapshot changed after preflight: $relative"
    rm -- "$root/$relative"
    i=$((i + 1))
done
printf 'removed %s SQL copies; review records unchanged\n' "$path_count"
