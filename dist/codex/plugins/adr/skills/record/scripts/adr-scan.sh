#!/usr/bin/env bash
# adr-scan.sh — locate a repository's ADR directory and inspect its records.
#
# Usage: adr-scan.sh [--root DIR] [--dir ADR_DIR] next|list|check
#
#   next   key=value lines: dir, exists, index, style, highest, next, others.
#          The next number is one above the highest number ever used: files in
#          the directory, links and ADR-NNNN mentions in the index, and ADR
#          files in git history on every local and fetched ref. Deleted or
#          unmerged records therefore keep their numbers.
#   list   tab-separated rows: number, status, date, title, path.
#   check  reports duplicate numbers and records missing from the index;
#          exits 1 when it finds either.
#
# Bash 3.2 compatible; needs only POSIX find/sed/awk/sort and optional git.
set -eu

ROOT=""
DIR=""
MODE=""

die() { printf 'adr-scan: %s\n' "$1" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --root) [ $# -ge 2 ] || die "--root needs a value"; ROOT="$2"; shift 2 ;;
    --dir) [ $# -ge 2 ] || die "--dir needs a value"; DIR="$2"; shift 2 ;;
    next|list|check) MODE="$1"; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done
[ -n "$MODE" ] || die "missing mode (next, list or check)"

if [ -z "$ROOT" ]; then
  ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
fi
[ -d "$ROOT" ] || die "root is not a directory: $ROOT"
cd "$ROOT"

# An ADR file is NNNN-slug.md (MADR, adr-tools) or adr-NNNN-slug.md (legacy).
ADR_RE='^(adr-)?[0-9][0-9][0-9][0-9]+-.*\.md$'

adr_files() {
  # $1 = directory; prints matching basenames, one per line.
  [ -d "$1" ] || return 0
  find "$1" -maxdepth 1 -type f -name '*.md' 2>/dev/null |
    sed 's|.*/||' | grep -E "$ADR_RE" | sort || true
}

CANDIDATES="docs/adr docs/decisions doc/adr docs/architecture/decisions docs/architecture-decisions adr decisions"

if [ -z "$DIR" ] && [ -f .adr-dir ]; then
  # adr-tools records a non-default location here.
  DIR=$(sed -n '1p' .adr-dir | sed 's/[[:space:]]*$//')
fi
OTHERS=""
if [ -z "$DIR" ]; then
  for c in $CANDIDATES; do
    if [ -n "$(adr_files "$c")" ]; then
      if [ -z "$DIR" ]; then DIR="$c"; else OTHERS="${OTHERS:+$OTHERS,}$c"; fi
    fi
  done
fi
if [ -z "$DIR" ]; then
  for c in $CANDIDATES; do
    if [ -d "$c" ]; then DIR="$c"; break; fi
  done
fi
DIR="${DIR:-docs/adr}"
DIR="${DIR%/}"

INDEX=""
for name in README.md index.md; do
  if [ -f "$DIR/$name" ]; then INDEX="$DIR/$name"; break; fi
done

number_of() {
  # Leading digits of an ADR basename, ignoring an adr- prefix.
  printf '%s\n' "$1" | sed -E 's/^adr-//; s/^([0-9]+).*/\1/'
}

used_numbers() {
  adr_files "$DIR" | while IFS= read -r f; do number_of "$f"; done
  if [ -n "$INDEX" ]; then
    grep -oE '(adr-)?[0-9]{4,}-[A-Za-z0-9._-]*\.md|ADR-[0-9]{4,}' "$INDEX" 2>/dev/null |
      sed -E 's/^ADR-//; s/^adr-//; s/^([0-9]+).*/\1/' || true
  fi
  if git rev-parse --git-dir >/dev/null 2>&1; then
    git log --all --format= --name-only -- "$DIR" 2>/dev/null |
      sed 's|.*/||' | grep -E "$ADR_RE" |
      while IFS= read -r f; do number_of "$f"; done || true
  fi
}

case "$MODE" in
  next)
    files=$(adr_files "$DIR")
    prefixed=$(printf '%s\n' "$files" | grep -c '^adr-' || true)
    plain=$(printf '%s\n' "$files" | grep -cE '^[0-9]' || true)
    style="NNNN-"
    if [ "$prefixed" -gt "$plain" ]; then style="adr-NNNN-"; fi
    exists=no
    if [ -d "$DIR" ]; then exists=yes; fi
    used_numbers | awk -v dir="$DIR" -v exists="$exists" -v idx="$INDEX" \
      -v style="$style" -v others="$OTHERS" '
      /^[0-9]+$/ { n = $0 + 0; if (!seen || n > max) { max = n; seen = 1 } }
      END {
        print "dir=" dir
        print "exists=" exists
        print "index=" idx
        print "style=" style
        if (seen) { printf "highest=%04d\n", max; printf "next=%04d\n", max + 1 }
        else { print "highest=none"; print "next=0001" }
        print "others=" others
      }'
    ;;
  list)
    adr_files "$DIR" | while IFS= read -r f; do
      awk -v num="$(number_of "$f")" -v path="$DIR/$f" '
        NR == 1 && /^---[[:space:]]*$/ { fm = 1; next }
        fm && /^---[[:space:]]*$/ { fm = 0; next }
        fm && /^status:/ { s = $0; sub(/^status:[[:space:]]*/, "", s); gsub(/"/, "", s); status = s }
        fm && /^date:/ { d = $0; sub(/^date:[[:space:]]*/, "", d); gsub(/"/, "", d); date = d }
        !fm && title == "" && /^# / { title = substr($0, 3) }
        !fm && /^## Status[[:space:]]*$/ { want = 1; next }
        want && NF { if (status == "") status = $0; want = 0 }
        END {
          if (status == "") status = "unknown"
          if (date == "") date = "unknown"
          printf "%s\t%s\t%s\t%s\t%s\n", num, status, date, title, path
        }' "$DIR/$f"
    done
    ;;
  check)
    problems=0
    dups=$(adr_files "$DIR" | while IFS= read -r f; do number_of "$f"; done | sort | uniq -d)
    for n in $dups; do
      same=$(adr_files "$DIR" | grep -E "^(adr-)?$n-" | tr '\n' ' ')
      printf 'duplicate %s: %s\n' "$n" "${same% }"
      problems=1
    done
    if [ -n "$INDEX" ]; then
      unindexed=$(adr_files "$DIR" | while IFS= read -r f; do
        grep -qF "($f)" "$INDEX" || printf 'unindexed %s\n' "$f"
      done)
      if [ -n "$unindexed" ]; then
        printf '%s\n' "$unindexed"
        problems=1
      fi
      for f in $(grep -oE '\((adr-)?[0-9]{4,}-[A-Za-z0-9._-]*\.md\)' "$INDEX" | tr -d '()' || true); do
        [ -f "$DIR/$f" ] || printf 'reserved %s (indexed, file absent; number stays used)\n' "$f"
      done
    fi
    exit "$problems"
    ;;
esac
