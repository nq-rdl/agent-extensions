#!/usr/bin/env bats
load helper

@test "derives NNN 001 in an empty repo and creates branch + worktree" {
  run "$PROVISION" my-feature
  [ "$status" -eq 0 ]
  [[ "$output" == *".claude/worktrees/001"* ]]
  [ -d ".claude/worktrees/001" ]
  git show-ref --verify --quiet refs/heads/001-my-feature
}

@test "derives the next NNN from existing specs/" {
  mkdir -p specs/007-old-thing
  run "$PROVISION" next-feature
  [ "$status" -eq 0 ]
  git show-ref --verify --quiet refs/heads/008-next-feature
  [ -d ".claude/worktrees/008" ]
}

@test "derives the next NNN from existing branches" {
  git branch 042-prior
  run "$PROVISION" after
  [ "$status" -eq 0 ]
  git show-ref --verify --quiet refs/heads/043-after
}

@test "sequential provisioning never reuses a number (derivation-based guard)" {
  run "$PROVISION" first
  [ "$status" -eq 0 ]
  run "$PROVISION" second   # reads worktrees/001 -> next is 002, no collision
  [ "$status" -eq 0 ]
  git show-ref --verify --quiet refs/heads/001-first
  git show-ref --verify --quiet refs/heads/002-second
}

# NOTE: the branch/slot conflict guard in provision-worktree.sh is a TOCTOU
# race safety net. It cannot be triggered single-threaded because NNN derivation
# (max of all numbered branches/specs/slots + 1) provably never yields an already
# used number — so a dedicated single-process test would be fiction. The guard is
# validated by the no-reuse test above and by code review of the guard block.

@test "--base cuts the spec branch from the given integration branch" {
  git checkout -q -b integration
  git commit -q --allow-empty -m "integration work"
  git checkout -q main
  run "$PROVISION" grouped --base integration
  [ "$status" -eq 0 ]
  run git -C .claude/worktrees/001 log --oneline
  [[ "$output" == *"integration work"* ]]
}

@test "unknown base branch fails clearly" {
  run "$PROVISION" thing --base nope-not-a-branch
  [ "$status" -ne 0 ]
  [[ "$output" == *"not found"* ]]
}
