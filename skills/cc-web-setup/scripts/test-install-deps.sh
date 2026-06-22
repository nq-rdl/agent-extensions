#!/usr/bin/env bash
# scripts/test-install-deps.sh
# Unit + integration tests for assets/install-deps.sh (the portable SessionStart
# hook shipped by the cc-web-setup skill).
#
# install-deps.sh is sourceable (its imperative body is guarded by
# `[ "${BASH_SOURCE[0]}" = "${0}" ]`), so this harness sources it to get the REAL
# ensure_gh / codex functions / persist_path and exercises them against a fake
# PATH of stub executables — the only things stubbed are the external I/O boundary
# (gh/codex/curl/tar/sha256sum/uname). No network. The CLAUDE_CODE_REMOTE gate and
# the *.local.sh seam are covered by running the script as a subprocess.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${HERE}/../assets/install-deps.sh"
PASS=0; FAIL=0; SKIP=0
ok()   { PASS=$((PASS+1)); echo "  PASS  $*"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL  $*"; }
skip() { SKIP=$((SKIP+1)); echo "  SKIP  $*"; }

# Source the script under test. With the main-guard in place, sourcing only
# defines the functions and never runs the hook body (side-effect free).
# shellcheck source=../assets/install-deps.sh
source "$SCRIPT"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/install-deps-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# Coreutils the functions legitimately use (not the stubbed I/O boundary).
COREUTILS="bash mkdir mktemp find head rm install env cat dirname grep ln tail touch mv chmod printf awk sed id"

new_stub_dir() {
  local d tool real
  d="$(mktemp -d "$WORK/path.XXXXXX")"
  for tool in $COREUTILS; do
    real="$(command -v "$tool" 2>/dev/null || true)"
    [ -n "$real" ] && ln -s "$real" "$d/$tool"
  done
  echo "$d"
}

write_stub() {
  local dir="$1" name="$2" body="$3"
  # new_stub_dir() pre-populates the dir with symlinks to the real coreutils
  # (e.g. `id`). Without removing it first, the `>` redirect would FOLLOW such a
  # symlink and try to overwrite the real system binary (clobbering it, or
  # failing with EACCES) instead of replacing the link with our stub. Drop any
  # existing entry so the stub always lands in the temp dir.
  rm -f "$dir/$name"
  printf '#!/usr/bin/env bash\n%s\n' "$body" >"$dir/$name"
  chmod +x "$dir/$name"
}

run_in_subshell() { # <stub_dir> <out_file> <home> <fn>
  local stub_dir="$1" out_file="$2" home="$3" fn="$4"
  # shellcheck disable=SC2030,SC2031
  (
    export HOME="$home" PATH="$stub_dir" TMPDIR="$WORK"
    LOG="$out_file"
    "$fn"
  ) >>"$out_file" 2>&1
}

# ---------------------------------------------------------------------------
# ensure_gh()
# ---------------------------------------------------------------------------
run_ensure_gh() {
  local stub_dir="$1" out_file="$2" home="${3:-}"
  [ -n "$home" ] || home="$(mktemp -d "$WORK/home.XXXXXX")"
  run_in_subshell "$stub_dir" "$out_file" "$home" ensure_gh
}

test_gh_pin_match() {
  local d log; d="$(new_stub_dir)"; log="$WORK/g1.log"
  write_stub "$d" gh "echo 'gh version ${GH_PIN} (2026-01-01)'"
  write_stub "$d" curl "touch '$WORK/g1-download'; exit 1"
  rm -f "$WORK/g1-download"
  run_ensure_gh "$d" "$log" && ok "gh pin match: returns 0 (idempotent)" \
    || fail "gh pin match: returned non-zero for a pinned gh"
  [ -e "$WORK/g1-download" ] && fail "gh pin match: attempted a download" \
    || ok "gh pin match: did NOT attempt a download"
}

test_gh_pin_mismatch() {
  local d log; d="$(new_stub_dir)"; log="$WORK/g2.log"
  write_stub "$d" gh "echo 'gh version 2.40.0 (2024-01-01)'"
  write_stub "$d" curl "exit 1"
  write_stub "$d" uname "echo x86_64"
  run_ensure_gh "$d" "$log" && fail "gh pin mismatch: accepted a wrong-version gh" \
    || ok "gh pin mismatch: rejected wrong-version gh and failed the install"
}

test_gh_missing_sha256sum() {
  local d log; d="$(new_stub_dir)"; log="$WORK/g3.log"
  # shellcheck disable=SC2016
  write_stub "$d" curl 'while [ $# -gt 0 ]; do [ "$1" = "-o" ] && { out="$2"; shift; }; shift; done; printf dummy >"$out"'
  write_stub "$d" uname "echo x86_64"
  write_stub "$d" tar "exit 0"
  # No sha256sum stub on this PATH; remove the symlinked real one too.
  rm -f "$d/sha256sum"
  run_ensure_gh "$d" "$log" && fail "gh missing-sha: returned 0 with no sha256sum" \
    || ok "gh missing-sha: returned non-zero"
  grep -q 'sha256sum not found' "$log" 2>/dev/null \
    && ok "gh missing-sha: attributed to the missing tool" \
    || fail "gh missing-sha: cause not named. Log: $(cat "$log" 2>/dev/null)"
}

# ---------------------------------------------------------------------------
# codex auth + sandbox
# ---------------------------------------------------------------------------
run_ensure_codex_auth() {
  local stub_dir="$1" out_file="$2" token="${3-}"
  # shellcheck disable=SC2030,SC2031
  (
    export PATH="$stub_dir" TMPDIR="$WORK"
    if [ "$#" -ge 3 ]; then export CODEX_ACCESS_TOKEN="$token"; else unset CODEX_ACCESS_TOKEN; fi
    LOG="$out_file"
    ensure_codex_auth
  ) >>"$out_file" 2>&1
}

test_codex_no_token() {
  local d log; d="$(new_stub_dir)"; log="$WORK/c1.log"
  write_stub "$d" codex "> '$WORK/c1-called'; exit 0"
  rm -f "$WORK/c1-called"
  run_ensure_codex_auth "$d" "$log" && ok "codex no-token: returns 0 (quiet no-op)" \
    || fail "codex no-token: returned non-zero"
  [ -e "$WORK/c1-called" ] && fail "codex no-token: codex was invoked" \
    || ok "codex no-token: codex NOT invoked"
}

test_codex_missing_cli() {
  local d log; d="$(new_stub_dir)"; log="$WORK/c2.log"
  run_ensure_codex_auth "$d" "$log" "tok.tok.tok" \
    && fail "codex missing-cli: returned 0 with no codex" \
    || ok "codex missing-cli: returned non-zero"
  grep -q 'not on PATH' "$log" 2>/dev/null && ok "codex missing-cli: names the missing CLI" \
    || fail "codex missing-cli: cause not named"
}

test_codex_fresh_login() {
  local d log; d="$(new_stub_dir)"; log="$WORK/c3.log"
  # shellcheck disable=SC2016
  write_stub "$d" codex \
    '[ "$1 $2" = "login status" ] && exit 1
     if [ "$2" = "--with-access-token" ]; then printf "%s" "$*" > "'"$WORK"'/c3-argv"; cat > "'"$WORK"'/c3-stdin"; exit 0; fi
     exit 1'
  rm -f "$WORK/c3-argv" "$WORK/c3-stdin"
  run_ensure_codex_auth "$d" "$log" "SECRET.JWT.VALUE" && ok "codex fresh-login: returns 0" \
    || fail "codex fresh-login: returned non-zero"
  [ "$(cat "$WORK/c3-stdin" 2>/dev/null)" = "SECRET.JWT.VALUE" ] \
    && ok "codex fresh-login: token delivered on stdin" \
    || fail "codex fresh-login: token not on stdin"
  grep -q 'SECRET.JWT.VALUE' "$WORK/c3-argv" 2>/dev/null \
    && fail "codex fresh-login: token LEAKED into argv" \
    || ok "codex fresh-login: token never in argv"
}

test_codex_blank_token() {
  local d log envf; d="$(new_stub_dir)"; log="$WORK/c4.log"; envf="$WORK/c4-envfile"; : > "$envf"
  # codex stub drops a sentinel if it is ever invoked.
  write_stub "$d" codex "> '$WORK/c4-called'; exit 0"
  rm -f "$WORK/c4-called"
  # A whitespace-only token is non-empty (passes the -z guard) but unusable: it
  # must be diagnosed as blank, NOT piped to `codex login --with-access-token`.
  ( export CLAUDE_ENV_FILE="$envf"; run_ensure_codex_auth "$d" "$log" "   " ) \
    && fail "codex blank-token: returned 0 for a whitespace-only token" \
    || ok "codex blank-token: returned non-zero"
  grep -q 'only whitespace' "$log" 2>/dev/null \
    && ok "codex blank-token: diagnosed as blank" \
    || fail "codex blank-token: not diagnosed as blank. Log: $(cat "$log" 2>/dev/null)"
  [ -e "$WORK/c4-called" ] && fail "codex blank-token: codex was invoked" \
    || ok "codex blank-token: codex NOT invoked"
  # "treating as unset" must be honored: the blank token has to be dropped from the
  # session env (codex reads CODEX_ACCESS_TOKEN at runtime), so the unset is persisted.
  grep -qF 'unset CODEX_ACCESS_TOKEN' "$envf" 2>/dev/null \
    && ok "codex blank-token: persisted unset to CLAUDE_ENV_FILE" \
    || fail "codex blank-token: did not persist unset. File: $(cat "$envf" 2>/dev/null)"
}

test_codex_trims_token() {
  local d log envf; d="$(new_stub_dir)"; log="$WORK/c5.log"; envf="$WORK/c5-envfile"; : > "$envf"
  # codex stub: report "unauthenticated" so login runs, then capture the stdin the
  # token is piped on.
  # shellcheck disable=SC2016
  write_stub "$d" codex \
    '[ "$1 $2" = "login status" ] && exit 1
     if [ "$2" = "--with-access-token" ]; then cat > "'"$WORK"'/c5-stdin"; exit 0; fi
     exit 1'
  rm -f "$WORK/c5-stdin"
  # A valid JWT wrapped in surrounding whitespace (e.g. a secret read from a file
  # with a trailing newline). It must be trimmed before being piped to codex,
  # otherwise codex rejects the otherwise-valid JWT as malformed.
  ( export CLAUDE_ENV_FILE="$envf"; run_ensure_codex_auth "$d" "$log" "
  SECRET.JWT.VALUE
  " ) && ok "codex trim-token: returns 0" \
    || fail "codex trim-token: returned non-zero"
  [ "$(cat "$WORK/c5-stdin" 2>/dev/null)" = "SECRET.JWT.VALUE" ] \
    && ok "codex trim-token: surrounding whitespace stripped before stdin" \
    || fail "codex trim-token: token not trimmed. Got: [$(cat "$WORK/c5-stdin" 2>/dev/null)]"
  # The RAW (whitespace-wrapped) value still in the live env is a malformed JWT for
  # later `codex exec`, so after the trimmed login it must be dropped + persisted.
  grep -qF 'unset CODEX_ACCESS_TOKEN' "$envf" 2>/dev/null \
    && ok "codex trim-token: dropped the raw whitespace token from the session env" \
    || fail "codex trim-token: did not persist unset of the raw token. File: [$(cat "$envf" 2>/dev/null)]"
}

test_codex_clean_token_kept() {
  local d log envf; d="$(new_stub_dir)"; log="$WORK/c6.log"; envf="$WORK/c6-envfile"; : > "$envf"
  # shellcheck disable=SC2016
  write_stub "$d" codex \
    '[ "$1 $2" = "login status" ] && exit 1
     if [ "$2" = "--with-access-token" ]; then exit 0; fi
     exit 1'
  # A pristine JWT (no surrounding whitespace) must be LEFT in the env so the normal
  # direct-token path keeps working for later codex calls — do NOT drop it.
  ( export CLAUDE_ENV_FILE="$envf"; run_ensure_codex_auth "$d" "$log" "SECRET.JWT.VALUE" ) \
    && ok "codex clean-token: returns 0" \
    || fail "codex clean-token: returned non-zero"
  grep -qF 'unset CODEX_ACCESS_TOKEN' "$envf" 2>/dev/null \
    && fail "codex clean-token: wrongly dropped a pristine token. File: [$(cat "$envf" 2>/dev/null)]" \
    || ok "codex clean-token: pristine token left in place"
}

# Fix A regression: when seed_codex_auth_json wins (auth.json is the credential of
# record), a stale CODEX_ACCESS_TOKEN must be dropped — codex reads the raw token
# BEFORE ~/.codex/auth.json, so a leftover would shadow the valid auth.json and break
# later `codex exec`. This exercises main()'s auth arm as a subprocess: codex installs
# at the pinned version, seed_codex_auth_json succeeds, and a non-JWT raw token is set.
test_codex_authjson_drops_stale_token() {
  local proj d out envf home; proj="$(mktemp -d "$WORK/aj-proj.XXXXXX")"; d="$(new_stub_dir)"
  out="$WORK/aj.out"; envf="$WORK/aj-envfile"; : > "$envf"; home="$WORK/aj-home"; mkdir -p "$home"
  mkdir -p "$proj/scripts"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$proj/scripts/cc-web-setup.sh"; chmod +x "$proj/scripts/cc-web-setup.sh"
  # gh pinned so ensure_gh short-circuits with no download.
  write_stub "$d" gh "echo 'gh version ${GH_PIN} (2026-01-01)'"
  write_stub "$d" id "echo 0"
  # codex stub: report the pinned version so ensure_codex_cli short-circuits (no
  # download), and report "authenticated" for `login status` so seed_codex_auth_json's
  # post-write probe succeeds.
  # shellcheck disable=SC2016
  write_stub "$d" codex \
    'case "$1 $2" in
       "--version "*|"--version") echo "codex-cli '"${CODEX_PIN}"'"; exit 0 ;;
       "login status") exit 0 ;;
     esac
     exit 0'
  # CODEX_AUTH_JSON present => seed_codex_auth_json wins. A stale, NON-JWT raw token is
  # live; it must be dropped + persisted as `unset CODEX_ACCESS_TOKEN`.
  # shellcheck disable=SC2030,SC2031
  if ( export PATH="$d:/usr/bin:/bin" HOME="$home" CLAUDE_CODE_REMOTE=true \
         CLAUDE_PROJECT_DIR="$proj" CLAUDE_ENV_FILE="$envf" TMPDIR="$WORK" \
         CODEX_HOME="$home/.codex" CODEX_AUTH_JSON='{"tokens":{"access_token":"x"}}' \
         CODEX_ACCESS_TOKEN='stale-not-a-jwt'; bash "$SCRIPT" ) >"$out" 2>&1; then
    ok "codex authjson-drop: main() exits 0 in remote mode"
  else
    fail "codex authjson-drop: main() exited non-zero. Out: $(cat "$out" 2>/dev/null)"
  fi
  grep -qF 'unset CODEX_ACCESS_TOKEN' "$envf" 2>/dev/null \
    && ok "codex authjson-drop: stale token unset persisted to CLAUDE_ENV_FILE" \
    || fail "codex authjson-drop: stale token NOT dropped after auth.json seeded. File: [$(cat "$envf" 2>/dev/null)] Out: $(cat "$out" 2>/dev/null)"
}

run_configure_codex_sandbox() {
  local home="$1" out_file="$2"
  # shellcheck disable=SC2030,SC2031,SC2034  # LOG is read by configure_codex_sandbox (sourced)
  ( export CODEX_HOME="$home" TMPDIR="$WORK"; LOG="$out_file"; configure_codex_sandbox ) >>"$out_file" 2>&1
}

test_sandbox_creates() {
  local home log; home="$(mktemp -d "$WORK/s1.XXXXXX")"; log="$WORK/s1.log"
  run_configure_codex_sandbox "$home" "$log" && ok "sandbox create: returns 0" \
    || fail "sandbox create: returned non-zero"
  [ "$(cat "$home/config.toml" 2>/dev/null)" = 'sandbox_mode = "danger-full-access"' ] \
    && ok "sandbox create: config.toml written with danger-full-access" \
    || fail "sandbox create: config.toml not as expected"
}

test_sandbox_respects_existing() {
  local home log before; home="$(mktemp -d "$WORK/s2.XXXXXX")"; log="$WORK/s2.log"
  mkdir -p "$home"; printf 'sandbox_mode = "workspace-write"\nmodel = "x"\n' > "$home/config.toml"
  before="$(cat "$home/config.toml")"
  run_configure_codex_sandbox "$home" "$log" >/dev/null
  [ "$(cat "$home/config.toml")" = "$before" ] \
    && ok "sandbox respect: user-set sandbox_mode left untouched" \
    || fail "sandbox respect: clobbered a user-set sandbox_mode"
}

# ---------------------------------------------------------------------------
# persist_path()
# ---------------------------------------------------------------------------
test_persist_path() {
  local envf; envf="$WORK/p1-envfile"; : > "$envf"
  ( export CLAUDE_ENV_FILE="$envf"; persist_path "/opt/x/bin"; persist_path "/opt/x/bin" ) >/dev/null 2>&1
  grep -qF 'export PATH="/opt/x/bin:$PATH"' "$envf" \
    && ok "persist_path: wrote the export line" \
    || fail "persist_path: did not write the export line. File: $(cat "$envf")"
  [ "$(grep -cF '/opt/x/bin' "$envf")" -eq 1 ] \
    && ok "persist_path: idempotent (no duplicate on re-run)" \
    || fail "persist_path: duplicated the line on re-run"
}

# Fix B regression: a read-only CLAUDE_ENV_FILE makes the append fail. persist_path
# must WARN (not falsely log "Persisted"), so later shells are not silently left
# without the dir on PATH. Run it twice — with $LOG set and with $LOG UNSET — to lock
# in the ${LOG:-/dev/null} discipline (a bare $LOG would crash under `set -u`).
test_persist_path_readonly_warns() {
  # This test relies on a read-only file (chmod 0444) making the append FAIL. root
  # bypasses DAC permission bits, so the premise cannot hold when running as root
  # (e.g. a root devcontainer) — persist_path would succeed and the assertions
  # would spuriously fail. Skip there; CI runs as non-root and exercises it fully.
  if [ "$(id -u)" -eq 0 ]; then
    skip "persist_path readonly: requires non-root (root bypasses 0444 perms)"
    return 0
  fi
  local envf out; envf="$WORK/p2-envfile"; : > "$envf"; chmod 0444 "$envf"

  # (1) with $LOG set.
  out="$WORK/p2-log-set.out"
  ( export CLAUDE_ENV_FILE="$envf"; LOG="$WORK/p2-LOG"; persist_path "/opt/ro/bin" ) >"$out" 2>&1
  grep -q 'WARNING: could not append PATH export for /opt/ro/bin' "$out" \
    && ok "persist_path readonly (LOG set): warned on append failure" \
    || fail "persist_path readonly (LOG set): no WARNING. Out: $(cat "$out" 2>/dev/null)"
  grep -q 'Persisted /opt/ro/bin' "$out" \
    && fail "persist_path readonly (LOG set): falsely claimed success" \
    || ok "persist_path readonly (LOG set): did NOT falsely claim success"

  # (2) with $LOG UNSET — must not crash under `set -u` (guarded ${LOG:-/dev/null}).
  out="$WORK/p2-log-unset.out"
  if ( export CLAUDE_ENV_FILE="$envf"; unset LOG; persist_path "/opt/ro/bin" ) >"$out" 2>&1; then
    ok "persist_path readonly (LOG unset): ran without crashing under set -u"
  else
    fail "persist_path readonly (LOG unset): crashed (likely a bare \$LOG). Out: $(cat "$out" 2>/dev/null)"
  fi
  grep -q 'WARNING: could not append PATH export for /opt/ro/bin' "$out" \
    && ok "persist_path readonly (LOG unset): warned on append failure" \
    || fail "persist_path readonly (LOG unset): no WARNING. Out: $(cat "$out" 2>/dev/null)"

  chmod 0644 "$envf" 2>/dev/null || true
  # The unwritable file must remain empty — nothing was appended on either run.
  [ ! -s "$envf" ] \
    && ok "persist_path readonly: nothing written to the unwritable file" \
    || fail "persist_path readonly: unexpectedly wrote to the file. File: [$(cat "$envf" 2>/dev/null)]"
}

# ---------------------------------------------------------------------------
# ensure_plugins()
# ---------------------------------------------------------------------------
# A stateful `claude` stub driven by files under $STATE (exported into the
# subshell), so one stub models every case the self-heal must handle:
#   * installed        — `> <id>` lines returned by `plugin list` (seed = already present)
#   * refreshed.<mkt>  — sentinel; `plugin install` succeeds IFF present (absent = stale index)
#   * unreachable      — marketplaces whose `marketplace update` fails (network down)
#   * refreshes        — one line appended per successful `marketplace update` (call counter)
write_claude_stub() { # <stub_dir> ; reads $STATE at runtime
  write_stub "$1" claude '
case "$1 $2" in
  "plugin list")
    cat "$STATE/installed" 2>/dev/null; exit 0 ;;
  "plugin install")
    p="$3"; mkt="${p##*@}"
    if [ -f "$STATE/refreshed.$mkt" ]; then
      printf "> %s\n" "$p" >> "$STATE/installed"; echo "installed $p"; exit 0
    fi
    echo "Plugin \"$p\" not found in marketplace \"$mkt\"; your local copy may be out of date." >&2
    exit 1 ;;
  "plugin marketplace")
    [ "$3" = "update" ] || exit 0
    if grep -qxF "$4" "$STATE/unreachable" 2>/dev/null; then
      echo "marketplace update failed: $4" >&2; exit 1
    fi
    printf "%s\n" "$4" >> "$STATE/refreshes"; touch "$STATE/refreshed.$4"; echo "updated $4"; exit 0 ;;
esac
exit 0'
}

run_ensure_plugins() { # <stub_dir> <out_file> <project_dir> <state_dir>
  local stub_dir="$1" out_file="$2" proj="$3" state="$4"
  # shellcheck disable=SC2030,SC2031,SC2034  # PROJECT_DIR/LOG are read by ensure_plugins (sourced)
  ( export PATH="$stub_dir" TMPDIR="$WORK" STATE="$state"
    PROJECT_DIR="$proj"; LOG="$out_file"
    ensure_plugins
  ) >>"$out_file" 2>&1
}

# Stage a project dir with a (jq-stubbed) settings.json and a fresh state dir.
setup_plugins_case() { # <tag> -> echoes "<stub_dir> <out_file> <project_dir> <state_dir>"
  local tag="$1" d proj state
  d="$(new_stub_dir)"
  proj="$(mktemp -d "$WORK/${tag}-proj.XXXXXX")"; mkdir -p "$proj/.claude"; : > "$proj/.claude/settings.json"
  state="$(mktemp -d "$WORK/${tag}-state.XXXXXX")"; : > "$state/installed"
  # jq is stubbed to emit the declared set straight from $STATE/declared, so the
  # tests do not depend on real jq or on parsing a real settings.json.
  write_stub "$d" jq 'cat "$STATE/declared" 2>/dev/null'
  write_claude_stub "$d"
  printf '%s %s %s %s' "$d" "$WORK/${tag}.log" "$proj" "$state"
}

# A missing plugin against a FRESH index installs on the first try — and the
# self-heal must NOT refresh when it does not need to (stays a quiet, minimal op).
test_plugins_healthy_index_no_refresh() {
  read -r d log proj state <<<"$(setup_plugins_case pp1)"
  printf 'a@m1\n' > "$state/declared"
  touch "$state/refreshed.m1"            # index already fresh
  run_ensure_plugins "$d" "$log" "$proj" "$state"
  grep -q 'Plugin install: 1 installed, 0 failed, 0 already present' "$log" \
    && ok "plugins healthy-index: installed on first try" \
    || fail "plugins healthy-index: wrong summary. Log: $(cat "$log" 2>/dev/null)"
  [ ! -s "$state/refreshes" ] \
    && ok "plugins healthy-index: no marketplace refresh when index is fresh" \
    || fail "plugins healthy-index: refreshed unnecessarily ([$(cat "$state/refreshes" 2>/dev/null)])"
}

# THE FIX: a stale index makes the first install fail; the self-heal refreshes the
# marketplace and retries. Three plugins across two marketplaces also lock in that
# each marketplace is refreshed at most once (b@m1 rides a@m1's refresh).
test_plugins_stale_index_recovers() {
  read -r d log proj state <<<"$(setup_plugins_case pp2)"
  printf 'a@m1\nb@m1\nc@m2\n' > "$state/declared"   # cold VM, no sentinels => stale
  run_ensure_plugins "$d" "$log" "$proj" "$state"
  grep -q 'Plugin install: 3 installed, 0 failed, 0 already present' "$log" \
    && ok "plugins stale-index: all recovered after marketplace refresh" \
    || fail "plugins stale-index: wrong summary. Log: $(cat "$log" 2>/dev/null)"
  [ "$(wc -l < "$state/refreshes" 2>/dev/null | tr -d ' ')" = "2" ] \
    && [ "$(sort -u "$state/refreshes" 2>/dev/null | wc -l | tr -d ' ')" = "2" ] \
    && ok "plugins stale-index: each marketplace refreshed exactly once" \
    || fail "plugins stale-index: refresh count wrong ([$(cat "$state/refreshes" 2>/dev/null)])"
}

# A resume where everything is already installed must be a quiet no-op: no install,
# no marketplace refresh.
test_plugins_already_present_noop() {
  read -r d log proj state <<<"$(setup_plugins_case pp3)"
  printf 'a@m1\n' > "$state/declared"
  printf '> a@m1\n' > "$state/installed"            # already installed
  run_ensure_plugins "$d" "$log" "$proj" "$state"
  grep -q 'Plugin install: 0 installed, 0 failed, 1 already present' "$log" \
    && ok "plugins already-present: quiet no-op summary" \
    || fail "plugins already-present: wrong summary. Log: $(cat "$log" 2>/dev/null)"
  grep -q 'Installing plugin' "$log" \
    && fail "plugins already-present: attempted an install" \
    || ok "plugins already-present: no install attempted"
  [ ! -s "$state/refreshes" ] \
    && ok "plugins already-present: no marketplace refresh" \
    || fail "plugins already-present: refreshed unnecessarily"
}

# When the marketplace is genuinely unreachable, a refresh does not help: the
# install is counted as failed and the warning names the refreshed marketplace.
test_plugins_unreachable_fails_after_refresh() {
  read -r d log proj state <<<"$(setup_plugins_case pp4)"
  printf 'bad@m3\n' > "$state/declared"
  printf 'm3\n' > "$state/unreachable"              # `marketplace update` fails
  run_ensure_plugins "$d" "$log" "$proj" "$state"
  grep -q 'Plugin install: 0 installed, 1 failed, 0 already present' "$log" \
    && ok "plugins unreachable: counted as failed after the refresh+retry" \
    || fail "plugins unreachable: wrong summary. Log: $(cat "$log" 2>/dev/null)"
  grep -qF "even after refreshing marketplace 'm3'" "$log" \
    && ok "plugins unreachable: warning names the refreshed marketplace" \
    || fail "plugins unreachable: warning text missing. Log: $(cat "$log" 2>/dev/null)"
}

# ---------------------------------------------------------------------------
# main() gate + project hook seam (subprocess)
# ---------------------------------------------------------------------------
test_gate_local_noop() {
  # On a LOCAL machine (no CLAUDE_CODE_REMOTE) the SessionStart hook must be an
  # immediate no-op (exit 0), no output — it never disturbs a contributor.
  local out; out="$WORK/gate.out"
  if CLAUDE_CODE_REMOTE='' bash "$SCRIPT" >"$out" 2>&1; then
    ok "gate: no-op exit 0 when CLAUDE_CODE_REMOTE unset"
  else
    fail "gate: non-zero exit when CLAUDE_CODE_REMOTE unset"
  fi
  [ -s "$out" ] && fail "gate: produced output when it should be silent" \
    || ok "gate: produced no output (true no-op)"
}

test_local_hook_sourced() {
  # CLAUDE_CODE_REMOTE=true with a project seam present => the dev-toolchain seam
  # (.claude/scripts/install-deps.local.sh) is sourced, exit 0.
  local proj d out; proj="$(mktemp -d "$WORK/proj.XXXXXX")"; d="$(new_stub_dir)"; out="$WORK/lh.out"
  mkdir -p "$proj/.claude/scripts"
  # A local seam that drops a sentinel when sourced.
  printf 'touch "%s/lh-sentinel"\n' "$WORK" > "$proj/.claude/scripts/install-deps.local.sh"
  rm -f "$WORK/lh-sentinel"
  # Stub gh to the pinned version so ensure_gh short-circuits; no codex creds so codex is skipped.
  write_stub "$d" gh "echo 'gh version ${GH_PIN} (2026-01-01)'"
  write_stub "$d" id "echo 0"
  # shellcheck disable=SC2030,SC2031
  if ( export PATH="$d:/usr/bin:/bin" HOME="$WORK/lh-home" CLAUDE_CODE_REMOTE=true \
         CLAUDE_PROJECT_DIR="$proj" TMPDIR="$WORK"; bash "$SCRIPT" ) >"$out" 2>&1; then
    ok "local-hook: main() exits 0 in remote mode"
  else
    fail "local-hook: main() exited non-zero. Out: $(cat "$out" 2>/dev/null)"
  fi
  [ -e "$WORK/lh-sentinel" ] \
    && ok "local-hook: install-deps.local.sh was sourced" \
    || fail "local-hook: project seam was NOT sourced. Out: $(cat "$out" 2>/dev/null)"
}

test_gh_pin_match
test_gh_pin_mismatch
test_gh_missing_sha256sum
test_codex_no_token
test_codex_missing_cli
test_codex_fresh_login
test_codex_blank_token
test_codex_trims_token
test_codex_clean_token_kept
test_codex_authjson_drops_stale_token
test_sandbox_creates
test_sandbox_respects_existing
test_persist_path
test_persist_path_readonly_warns
test_plugins_healthy_index_no_refresh
test_plugins_stale_index_recovers
test_plugins_already_present_noop
test_plugins_unreachable_fails_after_refresh
test_gate_local_noop
test_local_hook_sourced

echo ""
echo "install-deps: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
[ "$FAIL" -eq 0 ]
