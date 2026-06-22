#!/usr/bin/env bash
# scripts/test-cc-web-setup.sh
# Tests for assets/cc-web-setup.sh (the portable pre-snapshot setup script shipped
# by the cc-web-setup skill).
#
# The plugin pre-seed runs against a stubbed `claude` CLI that records every
# subcommand it sees, so the tests assert WHICH marketplaces/plugins are seeded
# (defaults + CC_WEB_* overrides), the no-claude path, and that the optional
# project hook (cc-web-setup.local.sh) is sourced. Run via the harness or by hand.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${HERE}/../assets/cc-web-setup.sh"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  PASS  $*"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL  $*"; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/cc-web-setup-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# A `claude` stub that appends every invocation's args to $CLAUDE_LOG. The path is
# passed via env so the same stub works across scenarios.
make_claude_stub() { # <dir>
  local dir="$1"
  cat >"$dir/claude" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CLAUDE_LOG"
exit 0
EOF
  chmod +x "$dir/claude"
}

# Like make_claude_stub, but the plugin install AND update both fail (marketplace
# registration still succeeds), so the pre-seed cannot recover — exercises the
# documented non-zero exit on a real provisioning failure.
make_claude_stub_failing() { # <dir>
  local dir="$1"
  cat >"$dir/claude" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CLAUDE_LOG"
case "$*" in
  *"plugin install"*|*"plugin update"*) exit 1 ;;
  *) exit 0 ;;
esac
EOF
  chmod +x "$dir/claude"
}

new_bin() { # build a PATH dir with coreutils + optional claude
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

# --- Test 1: defaults -> seeds rdl marketplace + rdl@rdl ---------------------
test_defaults() {
  local bin proj out clog; bin="$(new_bin)"; proj="$(mktemp -d "$WORK/p1.XXXXXX")"; out="$WORK/t1.out"
  make_claude_stub "$bin"; clog="$WORK/t1-claude.log"; : > "$clog"
  run_setup "$bin" "$proj" "$out" "CLAUDE_LOG=$clog" && ok "defaults: exit 0" || fail "defaults: non-zero exit"
  grep -q 'plugin marketplace add nq-rdl/agent-extensions' "$clog" \
    && ok "defaults: registered the rdl marketplace (nq-rdl/agent-extensions)" \
    || fail "defaults: did not register rdl marketplace. Log: $(cat "$clog")"
  grep -q 'plugin install rdl@rdl --scope project' "$clog" \
    && ok "defaults: pre-seeded rdl@rdl" \
    || fail "defaults: did not pre-seed rdl@rdl. Log: $(cat "$clog")"
}

# --- Test 2: CC_WEB_* overrides honored --------------------------------------
test_overrides() {
  local bin proj out clog; bin="$(new_bin)"; proj="$(mktemp -d "$WORK/p2.XXXXXX")"; out="$WORK/t2.out"
  make_claude_stub "$bin"; clog="$WORK/t2-claude.log"; : > "$clog"
  run_setup "$bin" "$proj" "$out" "CLAUDE_LOG=$clog" \
    "CC_WEB_MARKETPLACES=acme/plugins|acme" "CC_WEB_PLUGINS=foo@acme bar@acme" \
    && ok "overrides: exit 0" || fail "overrides: non-zero exit"
  grep -q 'plugin marketplace add acme/plugins' "$clog" \
    && ok "overrides: registered the overridden marketplace" \
    || fail "overrides: override marketplace not used. Log: $(cat "$clog")"
  grep -q 'plugin install foo@acme --scope project' "$clog" && grep -q 'plugin install bar@acme --scope project' "$clog" \
    && ok "overrides: pre-seeded both overridden plugins" \
    || fail "overrides: override plugins not used. Log: $(cat "$clog")"
  grep -q 'rdl@rdl' "$clog" \
    && fail "overrides: still seeded the default rdl@rdl (override ignored)" \
    || ok "overrides: defaults were replaced, not appended"
}

# --- Test 3: no claude on PATH -> skip pre-seed, still exit 0 -----------------
test_no_claude() {
  local bin proj out; bin="$(new_bin)"; proj="$(mktemp -d "$WORK/p3.XXXXXX")"; out="$WORK/t3.out"
  # No claude stub on this PATH.
  run_setup "$bin" "$proj" "$out" && ok "no-claude: exit 0" || fail "no-claude: non-zero exit"
  grep -q 'claude CLI not on PATH' "$out" \
    && ok "no-claude: logged the skip" \
    || fail "no-claude: did not log the skip. Out: $(cat "$out")"
}

# --- Test 4: project hook sourced --------------------------------------------
test_local_hook() {
  local bin proj out clog; bin="$(new_bin)"; proj="$(mktemp -d "$WORK/p4.XXXXXX")"; out="$WORK/t4.out"
  make_claude_stub "$bin"; clog="$WORK/t4-claude.log"; : > "$clog"
  mkdir -p "$proj/scripts"
  printf 'touch "%s/t4-sentinel"\n' "$WORK" > "$proj/scripts/cc-web-setup.local.sh"
  rm -f "$WORK/t4-sentinel"
  run_setup "$bin" "$proj" "$out" "CLAUDE_LOG=$clog" >/dev/null \
    && ok "local-hook: exit 0 when project hook succeeds" \
    || fail "local-hook: non-zero exit. Out: $(cat "$out")"
  [ -e "$WORK/t4-sentinel" ] \
    && ok "local-hook: cc-web-setup.local.sh was sourced" \
    || fail "local-hook: project hook not sourced. Out: $(cat "$out")"
}

# --- Test 6: plugin pre-seed failure -> non-zero exit ------------------------
test_plugin_failure_rc() {
  # The exit-status contract: a plugin that can neither install nor update is a
  # provisioning failure and must produce a non-zero exit (not a silent rc=0).
  local bin proj out clog; bin="$(new_bin)"; proj="$(mktemp -d "$WORK/p6.XXXXXX")"; out="$WORK/t6.out"
  make_claude_stub_failing "$bin"; clog="$WORK/t6-claude.log"; : > "$clog"
  if run_setup "$bin" "$proj" "$out" "CLAUDE_LOG=$clog"; then
    fail "plugin-fail: expected non-zero exit when pre-seed fails. Out: $(cat "$out")"
  else
    ok "plugin-fail: non-zero exit when a plugin can neither install nor update"
  fi
  grep -q 'Provisioning finished with errors' "$out" \
    && ok "plugin-fail: surfaced the provisioning failure in the epilogue" \
    || fail "plugin-fail: did not log the failure. Out: $(cat "$out")"
}

# --- Test 7: a project hook that exits is contained by the subshell ----------
test_local_hook_exit_contained() {
  # `( source "$local_hook" )` must isolate a stray `exit` so it cannot abort
  # main() at the source line: rc becomes 1 and the epilogue still runs.
  local bin proj out clog; bin="$(new_bin)"; proj="$(mktemp -d "$WORK/p7.XXXXXX")"; out="$WORK/t7.out"
  make_claude_stub "$bin"; clog="$WORK/t7-claude.log"; : > "$clog"
  mkdir -p "$proj/scripts"
  printf 'touch "%s/t7-before"\nexit 1\n' "$WORK" > "$proj/scripts/cc-web-setup.local.sh"
  rm -f "$WORK/t7-before"
  if run_setup "$bin" "$proj" "$out" "CLAUDE_LOG=$clog"; then
    fail "exit-contained: expected non-zero exit (hook failed). Out: $(cat "$out")"
  else
    ok "exit-contained: hook's non-zero exit propagates to rc"
  fi
  [ -e "$WORK/t7-before" ] \
    && ok "exit-contained: the hook actually ran" \
    || fail "exit-contained: hook did not run at all. Out: $(cat "$out")"
  grep -q 'Provisioning finished with errors' "$out" \
    && ok "exit-contained: main() ran its epilogue (the exit did not escape the subshell)" \
    || fail "exit-contained: epilogue missing — exit escaped the subshell. Out: $(cat "$out")"
}

# --- Test 5: sourceable (main-guard) -----------------------------------------
test_sourceable() {
  # Sourcing must NOT run main(): define globals only. Assert MARKETPLACES exists
  # and main() did not exit the shell.
  # shellcheck disable=SC1090
  ( set +e; source "$SCRIPT"; [ "${MARKETPLACES[0]}" = "nq-rdl/agent-extensions|rdl" ] ) \
    && ok "sourceable: source defines globals without running main()" \
    || fail "sourceable: sourcing did not behave (main ran or globals missing)"
}

test_defaults
test_overrides
test_no_claude
test_local_hook
test_plugin_failure_rc
test_local_hook_exit_contained
test_sourceable

echo ""
echo "cc-web-setup: ${PASS} passed, ${FAIL} failed"
[ "$FAIL" -eq 0 ]
