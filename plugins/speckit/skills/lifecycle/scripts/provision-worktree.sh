#!/usr/bin/env bash
# provision-worktree.sh <slug> [--base <branch>]
#
# Derive NNN (max across git branches, specs/, and .claude/worktrees/, +1,
# zero-padded), guard against conflicts, create the spec branch + worktree off
# the trunk (or --base), and seed the spec via .specify/scripts/bash/create-new-feature.sh
# when present (bare git otherwise). Prints the created worktree path on stdout.
set -euo pipefail

die() { echo "Error: $*" >&2; exit 1; }

SLUG=""; BASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="${2:-}"; shift 2 ;;
    -h|--help) echo "Usage: $0 <slug> [--base <branch>]"; exit 0 ;;
    --) shift ;;
    -*) die "unknown flag: $1" ;;
    *) if [ -z "$SLUG" ]; then SLUG="$1"; shift; else die "unexpected argument: $1"; fi ;;
  esac
done
[ -n "$SLUG" ] || die "slug required (usage: $0 <slug> [--base <branch>])"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git repository"
cd "$REPO_ROOT"

# --- Trunk detection (runtime discovery, never hardcoded) ------------------
detect_trunk() {
  local t
  t="$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null | sed 's|^refs/remotes/origin/||')"
  if [ -n "$t" ]; then printf '%s\n' "$t"; return; fi
  local c
  for c in main master trunk; do
    if git show-ref --verify --quiet "refs/heads/$c"; then printf '%s\n' "$c"; return; fi
  done
  git rev-parse --abbrev-ref HEAD
}
BASE="${BASE:-$(detect_trunk)}"
git rev-parse --verify --quiet "$BASE^{commit}" >/dev/null || die "base branch '$BASE' not found"

# --- NNN derivation: max(branches, specs/, worktrees/) + 1 -----------------
highest_num() {
  {
    printf '000\n'   # floor, so grep always matches (empty repo -> NNN 001)
    git branch -a --format='%(refname:short)' 2>/dev/null | sed 's|.*/||'
    ls -1 specs 2>/dev/null
    ls -1 .claude/worktrees 2>/dev/null
  } | grep -oE '^[0-9]{3}' | sort -n | tail -1
}
HIGH="$(highest_num)"; HIGH="${HIGH:-000}"
NNN="$(printf '%03d' "$((10#$HIGH + 1))")"

BRANCH="${NNN}-${SLUG}"
WT_DIR=".claude/worktrees/${NNN}"

# --- Conflict guard (fails safe under concurrent creation) -----------------
git show-ref --verify --quiet "refs/heads/${BRANCH}" && die "branch '${BRANCH}' already exists"
[ -e "$WT_DIR" ] && die "worktree slot '${WT_DIR}' already exists"

# --- Create branch + worktree off BASE -------------------------------------
git worktree add -b "$BRANCH" "$WT_DIR" "$BASE" >&2

# --- Seed the spec: prefer speckit's own script, else leave bare ------------
CNF=".specify/scripts/bash/create-new-feature.sh"
if [ -x "$CNF" ]; then
  ( cd "$WT_DIR" && "${REPO_ROOT}/${CNF}" --json --allow-existing-branch \
      --number "$NNN" --short-name "$SLUG" "$SLUG" ) >&2 || \
    echo "warning: create-new-feature.sh failed; worktree created without seeded spec" >&2
fi

printf '%s\n' "$WT_DIR"
