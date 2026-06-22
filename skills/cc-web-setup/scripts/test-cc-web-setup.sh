#!/usr/bin/env bash
# scripts/test-cc-web-setup.sh
# Tests for assets/cc-web-setup.sh — the OPTIONAL, plugin-free pre-snapshot setup
# script shipped by the cc-web-setup skill.
#
# cc-web-setup.sh no longer does any plugin/marketplace work (plugins install
# declaratively from .claude/settings.json). Its only job is to source an
# optional project hook (cc-web-setup.local.sh) so a repo can bake heavy
# non-plugin deps into the snapshot. These tests assert: the no-hook no-op path,
# that the project hook IS sourced, that a hook's stray `exit` is contained by
# the subshell, and that the script is sourceable without running main().
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${HERE}/../assets/cc-web-setup.sh"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  PASS  $*"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL  $*"; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/cc-web-setup-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

new_bin() { # build a PATH dir with just coreutils
  local d tool real; d="$(mktemp -d "$WORK/bin.XXXXXX")"
  for tool in bash printf cat rm mkdir dirname grep head touch; do
    real="$(command -v "$tool" 2>/dev/null || true)"; [ -n "$real" ] && ln -s "$real" "$d/$tool"
  done
  echo "$d"
}

# run_setup <bin_dir> <project_dir> <out> [env assignments...] — execute the REAL
# script as a subprocess (so main() runs) with an isolated PATH/PROJECT_DIR.
run_setup() {
  local bin="$1" proj="$2" out="$3"; shift 3
  # shellcheck disable=SC2163  # "$@" holds KEY=val assignments to export, intentional
  ( export PATH="$bin" CLAUDE_PROJECT_DIR="$proj" TMPDIR="$WORK" "$@"; bash "$SCRIPT" ) >"$out" 2>&1
}

# --- Test 1: no project hook -> no-op, exit 0 --------------------------------
test_no_hook() {
  local bin proj out; bin="$(new_bin)"; proj="$(mktemp -d "$WORK/p1.XXXXXX")"; out="$WORK/t1.out"
  run_setup "$bin" "$proj" "$out" && ok "no-hook: exit 0" || fail "no-hook: non-zero exit. Out: $(cat "$out")"
  grep -q 'nothing to pre-snapshot' "$out" \
    && ok "no-hook: logged the no-op (nothing to pre-snapshot)" \
    || fail "no-hook: did not log the no-op. Out: $(cat "$out")"
}

# --- Test 2: project hook sourced -------------------------------------------
test_local_hook() {
  local bin proj out; bin="$(new_bin)"; proj="$(mktemp -d "$WORK/p2.XXXXXX")"; out="$WORK/t2.out"
  mkdir -p "$proj/scripts"
  printf 'touch "%s/t2-sentinel"\n' "$WORK" > "$proj/scripts/cc-web-setup.local.sh"
  rm -f "$WORK/t2-sentinel"
  run_setup "$bin" "$proj" "$out" \
    && ok "local-hook: exit 0 when project hook succeeds" \
    || fail "local-hook: non-zero exit. Out: $(cat "$out")"
  [ -e "$WORK/t2-sentinel" ] \
    && ok "local-hook: cc-web-setup.local.sh was sourced" \
    || fail "local-hook: project hook not sourced. Out: $(cat "$out")"
}

# --- Test 3: a project hook that exits is contained by the subshell ----------
test_local_hook_exit_contained() {
  # `( source "$local_hook" )` must isolate a stray `exit` so it cannot abort
  # main() at the source line: rc becomes 1 and the epilogue still runs.
  local bin proj out; bin="$(new_bin)"; proj="$(mktemp -d "$WORK/p3.XXXXXX")"; out="$WORK/t3.out"
  mkdir -p "$proj/scripts"
  printf 'touch "%s/t3-before"\nexit 1\n' "$WORK" > "$proj/scripts/cc-web-setup.local.sh"
  rm -f "$WORK/t3-before"
  if run_setup "$bin" "$proj" "$out"; then
    fail "exit-contained: expected non-zero exit (hook failed). Out: $(cat "$out")"
  else
    ok "exit-contained: hook's non-zero exit propagates to rc"
  fi
  [ -e "$WORK/t3-before" ] \
    && ok "exit-contained: the hook actually ran" \
    || fail "exit-contained: hook did not run at all. Out: $(cat "$out")"
  grep -q 'Provisioning finished with errors' "$out" \
    && ok "exit-contained: main() ran its epilogue (the exit did not escape the subshell)" \
    || fail "exit-contained: epilogue missing — exit escaped the subshell. Out: $(cat "$out")"
}

# --- Test 4: sourceable (main-guard) -----------------------------------------
test_sourceable() {
  # Sourcing must NOT run main(): it should only define the log() helper and not
  # exit the shell or emit provisioning output.
  # shellcheck disable=SC1090
  ( set +e; source "$SCRIPT"; declare -F log >/dev/null && [ "$(type -t main)" = "function" ] ) \
    && ok "sourceable: source defines helpers without running main()" \
    || fail "sourceable: sourcing did not behave (main ran or helpers missing)"
}

test_no_hook
test_local_hook
test_local_hook_exit_contained
test_sourceable

echo ""
echo "cc-web-setup: ${PASS} passed, ${FAIL} failed"
[ "$FAIL" -eq 0 ]
