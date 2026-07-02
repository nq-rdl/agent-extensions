#!/usr/bin/env bats
load helper

@test "merges a spec branch into trunk and cleans up" {
  run "$PROVISION" feat
  [ "$status" -eq 0 ]
  ( cd .claude/worktrees/001 && git commit -q --allow-empty -m "spec work" )
  run "$MERGE" 001
  [ "$status" -eq 0 ]
  ! git show-ref --verify --quiet refs/heads/001-feat
  [ ! -d ".claude/worktrees/001" ]
  run git log --oneline main
  [[ "$output" == *"Merge 001-feat into main"* ]]
}

@test "resolves the integration branch it was cut from (not trunk)" {
  git checkout -q -b epic-x
  git commit -q --allow-empty -m "epic base"
  git checkout -q main
  run "$PROVISION" grouped --base epic-x
  [ "$status" -eq 0 ]
  ( cd .claude/worktrees/001 && git commit -q --allow-empty -m "spec work" )
  run "$MERGE" 001
  [ "$status" -eq 0 ]
  run git log --oneline epic-x
  [[ "$output" == *"Merge 001-grouped into epic-x"* ]]
  run git log --oneline main
  [[ "$output" != *"Merge 001-grouped"* ]]
}

@test "refuses to merge when the worktree has uncommitted changes" {
  run "$PROVISION" dirty
  [ "$status" -eq 0 ]
  echo "scratch" > .claude/worktrees/001/uncommitted.txt
  run "$MERGE" 001
  [ "$status" -ne 0 ]
  [[ "$output" == *"uncommitted"* ]]
  git show-ref --verify --quiet refs/heads/001-dirty   # branch untouched
}

@test "worktree removal is idempotent (slot already gone)" {
  run "$PROVISION" gone
  [ "$status" -eq 0 ]
  ( cd .claude/worktrees/001 && git commit -q --allow-empty -m "w" )
  git worktree remove --force .claude/worktrees/001
  run "$MERGE" 001
  [ "$status" -eq 0 ]
  ! git show-ref --verify --quiet refs/heads/001-gone
}

@test "fails clearly for a missing NNN" {
  run "$MERGE" 999
  [ "$status" -ne 0 ]
  [[ "$output" == *"no spec branch"* ]]
}
