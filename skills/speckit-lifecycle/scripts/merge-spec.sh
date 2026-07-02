#!/usr/bin/env bash
# merge-spec.sh <NNN>
#
# Merge a completed spec branch into its topological parent (the trunk, or the
# integration branch it was cut from — resolved via git merge-base), then clean
# up: remove the worktree slot BEFORE deleting the branch (git refuses `branch -d`
# while a branch is checked out in a worktree), delete the local + remote branch.
# Idempotent worktree removal; loud refusal if the slot has uncommitted changes.
set -euo pipefail

die() { echo "Error: $*" >&2; exit 1; }

NNN="${1:-}"
[ -n "$NNN" ] || die "usage: $0 <NNN>"
[[ "$NNN" =~ ^[0-9]{3}$ ]] || die "NNN must be three digits (got '$NNN')"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git repository"
cd "$REPO_ROOT"

BRANCH="$(git branch --format='%(refname:short)' | grep -E "^${NNN}-" | head -1 || true)"
[ -n "$BRANCH" ] || die "no spec branch matching '${NNN}-*'"

WT_DIR=".claude/worktrees/${NNN}"

# Refuse if the worktree slot has uncommitted changes.
if [ -d "$WT_DIR" ] && [ -n "$(git -C "$WT_DIR" status --porcelain 2>/dev/null)" ]; then
  die "worktree ${WT_DIR} has uncommitted changes — commit or discard them before merging"
fi

detect_trunk() {
  local t c
  t="$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null | sed 's|^refs/remotes/origin/||')"
  [ -n "$t" ] && { printf '%s\n' "$t"; return; }
  for c in main master trunk; do
    git show-ref --verify --quiet "refs/heads/$c" && { printf '%s\n' "$c"; return; }
  done
  git rev-parse --abbrev-ref HEAD
}
TRUNK="$(detect_trunk)"

# Merge target = the closest ancestor branch whose tip lies on BRANCH's history
# (i.e. BRANCH was cut from it and it has not advanced since). Prefer the nearest
# such branch (fewest commits to BRANCH), so an integration branch wins over trunk.
TARGET=""; best=-1
while IFS= read -r cand; do
  [ "$cand" = "$BRANCH" ] && continue
  [ "$(git rev-parse "$cand")" = "$(git merge-base "$cand" "$BRANCH" 2>/dev/null || echo x)" ] || continue
  dist="$(git rev-list --count "${cand}..${BRANCH}" 2>/dev/null || echo 999999)"
  if [ "$best" -lt 0 ] || [ "$dist" -lt "$best" ]; then best="$dist"; TARGET="$cand"; fi
done < <(git branch --format='%(refname:short)')
TARGET="${TARGET:-$TRUNK}"

# Merge --no-ff into the resolved target.
git checkout -q "$TARGET"
git merge --no-ff -m "Merge ${BRANCH} into ${TARGET}" "$BRANCH" >&2

# Remove the worktree slot BEFORE deleting the branch (idempotent).
if [ -d "$WT_DIR" ]; then
  git worktree remove "$WT_DIR" 2>/dev/null || git worktree remove --force "$WT_DIR" 2>/dev/null || true
fi
git worktree prune

git branch -d "$BRANCH" >&2
git push origin --delete "$BRANCH" >/dev/null 2>&1 || true   # best-effort; ok if no remote

# On a TRUNK merge the spec is ephemeral — its decision points belong in a durable ADR
# (archive first via the architecture-decision-records skill). Strip specs/NNN-slug/ so
# trunk stays clean. On an integration-branch merge the spec is retained (work continues).
if [ "$TARGET" = "$TRUNK" ]; then
  SPEC_DIR="$(ls -d "specs/${NNN}-"* 2>/dev/null | head -1 || true)"
  if [ -n "$SPEC_DIR" ] && [ -d "$SPEC_DIR" ]; then
    git rm -rq "$SPEC_DIR"
    git commit -q -m "chore(${NNN}): archive ephemeral spec — decision record lives in docs/adr/"
    echo "stripped ephemeral ${SPEC_DIR} (archive its decisions as an ADR)" >&2
  fi
fi

echo "merged ${BRANCH} -> ${TARGET}"
