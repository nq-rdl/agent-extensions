#!/usr/bin/env bash
# Shared bats helpers: build a throwaway fixture git repo for exercising the
# bundled scripts. The scripts under test are referenced by absolute path from
# the skill dir; they operate on `git rev-parse --show-toplevel`, i.e. the fixture.

setup() {
  TEST_TMP="$(mktemp -d)"
  cd "$TEST_TMP" || return 1
  git init -q -b main
  git config user.email 't@example.com'
  git config user.name 'Test'
  git commit -q --allow-empty -m 'init'

  mkdir -p .specify/scripts/bash specs .claude/worktrees

  SKILL_DIR="$(cd "${BATS_TEST_DIRNAME}/.." && pwd)"   # skills/speckit-lifecycle
  PROVISION="${SKILL_DIR}/scripts/provision-worktree.sh"
  MERGE="${SKILL_DIR}/scripts/merge-spec.sh"
}

teardown() {
  cd / || true
  [ -n "${TEST_TMP:-}" ] && rm -rf "$TEST_TMP"
}
