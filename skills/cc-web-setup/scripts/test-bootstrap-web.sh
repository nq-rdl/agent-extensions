#!/usr/bin/env bash
# scripts/test-bootstrap-web.sh
# Unit + integration tests for assets/bootstrap-web.sh (the SessionStart hook that
# fetches team skills into ~/.claude/skills/ and asks Claude Code to reloadSkills).
#
# bootstrap-web.sh is sourceable (its imperative body is guarded by
# `[ "${BASH_SOURCE[0]}" = "${0}" ]`), so this harness sources it to get the REAL
# fetch_repo_tarball / install_skill / bootstrap_web_skills and exercises them
# against a fake PATH of stub executables. The only stubs are the external I/O
# boundary (curl/tar; jq is real when available). No network. The CLAUDE_CODE_REMOTE
# gate and the reloadSkills emit are covered by running the script as a subprocess.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${HERE}/../assets/bootstrap-web.sh"
PASS=0; FAIL=0; SKIP=0
ok()   { PASS=$((PASS+1)); echo "  PASS  $*"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL  $*"; }
skip() { SKIP=$((SKIP+1)); echo "  SKIP  $*"; }

# Source the script under test. With the main-guard in place, sourcing only defines
# the functions and never runs the hook body (side-effect free).
# shellcheck source=../assets/bootstrap-web.sh
source "$SCRIPT"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/bootstrap-web-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# Coreutils the functions legitimately use (not the stubbed I/O boundary).
COREUTILS="bash mkdir mktemp rm cp mv printf cat dirname tr id find head ln chmod awk grep cksum"

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
  rm -f "$dir/$name"
  printf '#!/usr/bin/env bash\n%s\n' "$body" >"$dir/$name"
  chmod +x "$dir/$name"
}

# A curl stub that records each call and writes a dummy tarball to the -o target.
stub_curl_ok() { # <dir>
  write_stub "$1" curl '
    printf "%s\n" "$*" >> "$STATE/curl_calls"
    out=""; while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out="$2"; shift; done
    [ -n "$out" ] && printf dummytar > "$out"; exit 0'
}

# A tar stub that lays down a fixed skill tree under the -C dest (post --strip-components):
#   plugins/p/skills/s/SKILL.md   (matches the manifest paths the tests use)
stub_tar_skill() { # <dir>
  write_stub "$1" tar '
    dir=""; while [ $# -gt 0 ]; do [ "$1" = "-C" ] && dir="$2"; shift; done
    if [ -n "$dir" ]; then
      mkdir -p "$dir/plugins/p/skills/s"
      printf -- "---\nname: s\n---\n# s\n" > "$dir/plugins/p/skills/s/SKILL.md"
    fi
    exit 0'
}

# ---------------------------------------------------------------------------
# install_skill()
# ---------------------------------------------------------------------------
run_install_skill() { # <src_root> <path> <leaf> <skills_dir> <log>
  # shellcheck disable=SC2030,SC2031,SC2034  # SKILLS_DIR/LOG read by install_skill (sourced)
  ( SKILLS_DIR="$4"; LOG="$5"; install_skill "$1" "$2" "$3" ) >>"$5" 2>&1
}

test_install_skill_happy() {
  local src skills log; src="$(mktemp -d "$WORK/is1-src.XXXXXX")"; skills="$WORK/is1-skills"; log="$WORK/is1.log"
  # leaf must equal the upstream frontmatter name.
  mkdir -p "$src/plugins/p/skills/s"; printf -- '---\nname: myleaf\n---\n' > "$src/plugins/p/skills/s/SKILL.md"
  run_install_skill "$src" "plugins/p/skills/s" "myleaf" "$skills" "$log" \
    && ok "install_skill happy: returns 0" || fail "install_skill happy: returned non-zero. Log: $(cat "$log" 2>/dev/null)"
  [ -f "$skills/myleaf/SKILL.md" ] \
    && ok "install_skill happy: copied skill to ~/.claude/skills/<leaf>/SKILL.md" \
    || fail "install_skill happy: SKILL.md not at destination"
}

test_install_skill_unsafe_leaf() {
  local src skills log; src="$(mktemp -d "$WORK/is2-src.XXXXXX")"; skills="$WORK/is2-skills"; log="$WORK/is2.log"
  mkdir -p "$src/plugins/p/skills/s"; printf 'x' > "$src/plugins/p/skills/s/SKILL.md"
  run_install_skill "$src" "plugins/p/skills/s" "../escape" "$skills" "$log" \
    && fail "install_skill unsafe-leaf: accepted a path-traversal leaf" \
    || ok "install_skill unsafe-leaf: rejected '../escape'"
  [ -e "$skills/../escape" ] && fail "install_skill unsafe-leaf: wrote outside the skills dir" \
    || ok "install_skill unsafe-leaf: nothing written outside the skills dir"
}

test_install_skill_missing_skillmd() {
  local src skills log; src="$(mktemp -d "$WORK/is3-src.XXXXXX")"; skills="$WORK/is3-skills"; log="$WORK/is3.log"
  mkdir -p "$src/plugins/p/skills/s"   # NO SKILL.md
  run_install_skill "$src" "plugins/p/skills/s" "myleaf" "$skills" "$log" \
    && fail "install_skill no-skillmd: accepted a path with no SKILL.md" \
    || ok "install_skill no-skillmd: rejected a path with no SKILL.md"
  grep -q 'no SKILL.md' "$log" 2>/dev/null && ok "install_skill no-skillmd: names the reason" \
    || fail "install_skill no-skillmd: reason not named. Log: $(cat "$log" 2>/dev/null)"
}

test_install_skill_resume_noop() {
  local src skills log; src="$(mktemp -d "$WORK/is4-src.XXXXXX")"; skills="$WORK/is4-skills"; log="$WORK/is4.log"
  mkdir -p "$src/plugins/p/skills/s"; printf 'NEW' > "$src/plugins/p/skills/s/SKILL.md"
  mkdir -p "$skills/myleaf"; printf 'OLD' > "$skills/myleaf/SKILL.md"   # already present
  run_install_skill "$src" "plugins/p/skills/s" "myleaf" "$skills" "$log" \
    && ok "install_skill resume: returns 0 when already present" \
    || fail "install_skill resume: returned non-zero"
  [ "$(cat "$skills/myleaf/SKILL.md")" = "OLD" ] \
    && ok "install_skill resume: left the existing copy untouched (no clobber)" \
    || fail "install_skill resume: overwrote an existing skill"
}

test_install_skill_path_traversal() {
  local src skills log; src="$(mktemp -d "$WORK/is5-src.XXXXXX")"; skills="$WORK/is5-skills"; log="$WORK/is5.log"
  mkdir -p "$src/p/skills/s"; printf 'x' > "$src/p/skills/s/SKILL.md"
  run_install_skill "$src" "../../../etc/evil" "myleaf" "$skills" "$log" \
    && fail "install_skill traversal: accepted a '..' path" \
    || ok "install_skill traversal: rejected a path containing '..'"
  grep -q "escapes the repo" "$log" 2>/dev/null && ok "install_skill traversal: names the reason" \
    || fail "install_skill traversal: reason not named. Log: $(cat "$log" 2>/dev/null)"
}

# The leaf MUST equal the fetched skill's own frontmatter name (fail-closed; no
# frontmatter rewriting). Mismatch => refuse with a clear reason; match => install.
test_install_skill_requires_leaf_eq_name() {
  local src skills log; src="$(mktemp -d "$WORK/is6-src.XXXXXX")"; skills="$WORK/is6-skills"; log="$WORK/is6.log"
  mkdir -p "$src/p/skills/s"
  printf -- '---\nname: upstreamname\ndescription: d\n---\n# body\n' > "$src/p/skills/s/SKILL.md"
  # Mismatch: leaf 'different' != name 'upstreamname' -> refuse.
  run_install_skill "$src" "p/skills/s" "different" "$skills" "$log" \
    && fail "install_skill name-contract: accepted a leaf != upstream name" \
    || ok "install_skill name-contract: refused leaf != upstream name"
  [ ! -e "$skills/different" ] && ok "install_skill name-contract: wrote nothing on mismatch" \
    || fail "install_skill name-contract: wrote a dir despite the mismatch"
  # Match: leaf == name -> install.
  run_install_skill "$src" "p/skills/s" "upstreamname" "$skills" "$log" \
    && ok "install_skill name-contract: installs when leaf == upstream name" \
    || fail "install_skill name-contract: refused a matching leaf. Log: $(cat "$log" 2>/dev/null)"
  [ -f "$skills/upstreamname/SKILL.md" ] \
    && ok "install_skill name-contract: matched skill landed under its name" \
    || fail "install_skill name-contract: matched skill not installed"
}

# A symlinked source dir is the reproduced escape vector: cp -R would preserve/deref
# it and a later read/write could reach outside the extracted repo. Refuse it.
test_install_skill_rejects_symlink() {
  local src skills log; src="$(mktemp -d "$WORK/is8-src.XXXXXX")"; skills="$WORK/is8-skills"; log="$WORK/is8.log"
  local outside; outside="$(mktemp -d "$WORK/is8-out.XXXXXX")"
  printf -- '---\nname: evil\n---\n' > "$outside/SKILL.md"
  mkdir -p "$src/p/skills"; ln -s "$outside" "$src/p/skills/link"
  run_install_skill "$src" "p/skills/link" "evil" "$skills" "$log" \
    && fail "install_skill symlink: accepted a symlinked source dir" \
    || ok "install_skill symlink: refused a symlinked source dir"
  grep -q 'symlink' "$log" 2>/dev/null && ok "install_skill symlink: names the reason" \
    || fail "install_skill symlink: reason not named. Log: $(cat "$log" 2>/dev/null)"
  [ ! -e "$skills/evil" ] && ok "install_skill symlink: installed nothing" \
    || fail "install_skill symlink: installed despite the symlink"
}

test_install_skill_no_stage_leftover() {
  local src skills log; src="$(mktemp -d "$WORK/is7-src.XXXXXX")"; skills="$WORK/is7-skills"; log="$WORK/is7.log"
  mkdir -p "$src/p/skills/s"; printf -- '---\nname: myleaf\n---\n' > "$src/p/skills/s/SKILL.md"
  run_install_skill "$src" "p/skills/s" "myleaf" "$skills" "$log" >/dev/null
  local leftovers; leftovers="$(find "$skills" -maxdepth 1 -name '.stage.*' 2>/dev/null)"
  [ -z "$leftovers" ] && ok "install_skill atomic: no .stage leftover after a successful install" \
    || fail "install_skill atomic: staging dir left behind ([$leftovers])"
}

# ---------------------------------------------------------------------------
# fetch_repo_tarball()
# ---------------------------------------------------------------------------
test_fetch_tarball_https_and_memoizes() {
  local d cache log; d="$(new_stub_dir)"; cache="$WORK/ft1-cache"; mkdir -p "$cache"; log="$WORK/ft1.log"
  local state="$WORK/ft1-state"; mkdir -p "$state"; : > "$state/curl_calls"
  stub_curl_ok "$d"; stub_tar_skill "$d"
  local first second
  # shellcheck disable=SC2030,SC2031,SC2034  # globals read by fetch_repo_tarball (sourced)
  first="$( ( export PATH="$d" STATE="$state" TMPDIR="$WORK"; TARBALL_CACHE="$cache"; LOG="$log"; fetch_repo_tarball "acme/repo" "" ) )"
  [ -n "$first" ] && [ -d "$first" ] \
    && ok "fetch_tarball: returned an extracted dir" \
    || fail "fetch_tarball: no dir returned. Log: $(cat "$log" 2>/dev/null)"
  grep -q 'api.github.com/repos/acme/repo/tarball' "$state/curl_calls" 2>/dev/null \
    && ok "fetch_tarball: fetched over HTTPS api.github.com (no git)" \
    || fail "fetch_tarball: did not hit the HTTPS tarball URL. Calls: $(cat "$state/curl_calls" 2>/dev/null)"
  [ -f "$first/plugins/p/skills/s/SKILL.md" ] \
    && ok "fetch_tarball: extracted the repo tree" || fail "fetch_tarball: tree not extracted"
  # Second call for the SAME repo@ref must reuse the cache — no second download.
  # shellcheck disable=SC2030,SC2031,SC2034
  second="$( ( export PATH="$d" STATE="$state" TMPDIR="$WORK"; TARBALL_CACHE="$cache"; LOG="$log"; fetch_repo_tarball "acme/repo" "" ) )"
  [ "$second" = "$first" ] && ok "fetch_tarball: memoized (same dir on re-fetch)" \
    || fail "fetch_tarball: re-fetch returned a different dir"
  [ "$(grep -c 'tarball' "$state/curl_calls" 2>/dev/null)" = "1" ] \
    && ok "fetch_tarball: did NOT re-download a cached repo@ref" \
    || fail "fetch_tarball: downloaded twice ([$(cat "$state/curl_calls" 2>/dev/null)])"
}

test_fetch_tarball_anon_then_token() {
  local d cache log state; d="$(new_stub_dir)"; cache="$WORK/ft2-cache"; mkdir -p "$cache"; log="$WORK/ft2.log"
  state="$WORK/ft2-state"; mkdir -p "$state"; : > "$state/curl_calls"
  # curl: fail the ANON call (no Authorization arg), succeed only WITH a Bearer token.
  write_stub "$d" curl '
    printf "%s\n" "$*" >> "$STATE/curl_calls"
    auth=0; out=""; while [ $# -gt 0 ]; do [ "$1" = "-H" ] && case "$2" in Authorization:*) auth=1;; esac; [ "$1" = "-o" ] && out="$2"; shift; done
    [ "$auth" = "1" ] || exit 22
    [ -n "$out" ] && printf dummytar > "$out"; exit 0'
  stub_tar_skill "$d"
  local got
  # shellcheck disable=SC2030,SC2031,SC2034
  got="$( ( export PATH="$d" STATE="$state" TMPDIR="$WORK" GH_TOKEN="tok123"; TARBALL_CACHE="$cache"; LOG="$log"; fetch_repo_tarball "acme/private" "" ) )"
  [ -n "$got" ] && [ -d "$got" ] \
    && ok "fetch_tarball private: succeeded on the token retry" \
    || fail "fetch_tarball private: did not recover with GH_TOKEN. Log: $(cat "$log" 2>/dev/null)"
  grep -q 'Authorization: Bearer tok123' "$state/curl_calls" 2>/dev/null \
    && ok "fetch_tarball private: retried with the Bearer token" \
    || fail "fetch_tarball private: token retry not attempted"
}

# ---------------------------------------------------------------------------
# bootstrap_web_skills() — end to end with REAL jq
# ---------------------------------------------------------------------------
test_bootstrap_end_to_end() {
  command -v jq >/dev/null 2>&1 || { skip "bootstrap e2e: jq not available"; return; }
  local d proj skills log state; d="$(new_stub_dir)"; ln -sf "$(command -v jq)" "$d/jq"
  proj="$(mktemp -d "$WORK/be-proj.XXXXXX")"; mkdir -p "$proj/.claude"
  skills="$WORK/be-skills"; log="$WORK/be.log"; state="$WORK/be-state"; mkdir -p "$state"; : > "$state/curl_calls"
  stub_curl_ok "$d"; stub_tar_skill "$d"
  # leaf 's' matches the stub skill's frontmatter name (stub_tar_skill).
  cat > "$proj/.claude/web-skills.json" <<'JSON'
{ "skills": [ { "repo": "acme/repo", "ref": "", "path": "plugins/p/skills/s", "leaf": "s" } ] }
JSON
  # shellcheck disable=SC2030,SC2031,SC2034
  ( export PATH="$d" STATE="$state" TMPDIR="$WORK"; PROJECT_DIR="$proj"; SKILLS_DIR="$skills"; LOG="$log"; bootstrap_web_skills ) >>"$log" 2>&1
  [ -f "$skills/s/SKILL.md" ] \
    && ok "bootstrap e2e: installed the manifest skill into ~/.claude/skills/" \
    || fail "bootstrap e2e: skill not installed. Log: $(cat "$log" 2>/dev/null)"
  grep -q 'Web skills: 1 installed' "$log" 2>/dev/null \
    && ok "bootstrap e2e: summary counts the install" \
    || fail "bootstrap e2e: wrong summary. Log: $(cat "$log" 2>/dev/null)"
}

# A non-string field makes jq's @tsv fail; the hook must NOT report a fake success.
test_bootstrap_malformed_manifest() {
  command -v jq >/dev/null 2>&1 || { skip "bootstrap malformed: jq not available"; return; }
  local d proj skills log; d="$(new_stub_dir)"; ln -sf "$(command -v jq)" "$d/jq"
  proj="$(mktemp -d "$WORK/mf-proj.XXXXXX")"; mkdir -p "$proj/.claude"
  skills="$WORK/mf-skills"; log="$WORK/mf.log"
  # .repo is a number, not a string.
  cat > "$proj/.claude/web-skills.json" <<'JSON'
{ "skills": [ { "repo": 123, "ref": "", "path": "plugins/p/skills/s", "leaf": "s" } ] }
JSON
  # shellcheck disable=SC2030,SC2031,SC2034
  ( export PATH="$d" TMPDIR="$WORK"; PROJECT_DIR="$proj"; SKILLS_DIR="$skills"; LOG="$log"; bootstrap_web_skills ) >>"$log" 2>&1 \
    && ok "bootstrap malformed: returns 0 (non-fatal)" || fail "bootstrap malformed: returned non-zero"
  grep -q 'is malformed' "$log" 2>/dev/null \
    && ok "bootstrap malformed: rejected the bad-typed manifest with a clear reason" \
    || fail "bootstrap malformed: did not flag the malformed manifest. Log: $(cat "$log" 2>/dev/null)"
  [ ! -d "$skills" ] && ok "bootstrap malformed: installed nothing" \
    || fail "bootstrap malformed: wrote skills despite a malformed manifest"
}

test_bootstrap_dup_leaf_skipped() {
  command -v jq >/dev/null 2>&1 || { skip "bootstrap dup-leaf: jq not available"; return; }
  local d proj skills log state; d="$(new_stub_dir)"; ln -sf "$(command -v jq)" "$d/jq"
  proj="$(mktemp -d "$WORK/dl-proj.XXXXXX")"; mkdir -p "$proj/.claude"
  skills="$WORK/dl-skills"; log="$WORK/dl.log"; state="$WORK/dl-state"; mkdir -p "$state"; : > "$state/curl_calls"
  stub_curl_ok "$d"; stub_tar_skill "$d"
  cat > "$proj/.claude/web-skills.json" <<'JSON'
{ "skills": [
  { "repo": "acme/repo",  "ref": "", "path": "plugins/p/skills/s", "leaf": "s" },
  { "repo": "acme/other", "ref": "", "path": "plugins/p/skills/s", "leaf": "s" }
] }
JSON
  # shellcheck disable=SC2030,SC2031,SC2034
  ( export PATH="$d" STATE="$state" TMPDIR="$WORK"; PROJECT_DIR="$proj"; SKILLS_DIR="$skills"; LOG="$log"; bootstrap_web_skills ) >>"$log" 2>&1
  grep -q "duplicate leaf 's'" "$log" 2>/dev/null \
    && ok "bootstrap dup-leaf: warned and skipped the repeat" \
    || fail "bootstrap dup-leaf: no duplicate warning. Log: $(cat "$log" 2>/dev/null)"
  grep -q 'Web skills: 1 installed' "$log" 2>/dev/null \
    && ok "bootstrap dup-leaf: only the first of the duplicate leaves installed" \
    || fail "bootstrap dup-leaf: wrong install count. Log: $(cat "$log" 2>/dev/null)"
}

test_bootstrap_absent_manifest_noop() {
  command -v jq >/dev/null 2>&1 || { skip "bootstrap absent-manifest: jq not available"; return; }
  local d proj skills log; d="$(new_stub_dir)"; ln -sf "$(command -v jq)" "$d/jq"
  proj="$(mktemp -d "$WORK/bn-proj.XXXXXX")"; mkdir -p "$proj/.claude"   # NO web-skills.json
  skills="$WORK/bn-skills"; log="$WORK/bn.log"
  # shellcheck disable=SC2030,SC2031,SC2034
  ( export PATH="$d" TMPDIR="$WORK"; PROJECT_DIR="$proj"; SKILLS_DIR="$skills"; LOG="$log"; bootstrap_web_skills ) >>"$log" 2>&1 \
    && ok "bootstrap absent-manifest: returns 0 (quiet no-op)" \
    || fail "bootstrap absent-manifest: returned non-zero"
  [ ! -d "$skills" ] && ok "bootstrap absent-manifest: wrote no skills dir" \
    || fail "bootstrap absent-manifest: created a skills dir for an absent manifest"
}

# ---------------------------------------------------------------------------
# main() gate + reloadSkills emit (subprocess)
# ---------------------------------------------------------------------------
test_gate_local_noop() {
  local out; out="$WORK/gate.out"
  if CLAUDE_CODE_REMOTE='' bash "$SCRIPT" >"$out" 2>&1; then
    ok "gate: no-op exit 0 when CLAUDE_CODE_REMOTE unset"
  else
    fail "gate: non-zero exit when CLAUDE_CODE_REMOTE unset"
  fi
  [ -s "$out" ] && fail "gate: produced output when it should be silent" \
    || ok "gate: produced no output (true no-op)"
}

test_main_emits_reloadskills_with_manifest() {
  command -v jq >/dev/null 2>&1 || { skip "main reloadSkills: jq not available"; return; }
  local d proj home out state; d="$(new_stub_dir)"; ln -sf "$(command -v jq)" "$d/jq"
  proj="$(mktemp -d "$WORK/mr-proj.XXXXXX")"; mkdir -p "$proj/.claude"
  home="$WORK/mr-home"; mkdir -p "$home"; out="$WORK/mr.out"; state="$WORK/mr-state"; mkdir -p "$state"; : > "$state/curl_calls"
  stub_curl_ok "$d"; stub_tar_skill "$d"
  cat > "$proj/.claude/web-skills.json" <<'JSON'
{ "skills": [ { "repo": "acme/repo", "ref": "", "path": "plugins/p/skills/s", "leaf": "s" } ] }
JSON
  ( export PATH="$d:/usr/bin:/bin" HOME="$home" STATE="$state" TMPDIR="$WORK" \
      CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$proj"; bash "$SCRIPT" ) >"$out" 2>/dev/null || true
  grep -q '"reloadSkills":true' "$out" 2>/dev/null \
    && ok "main reloadSkills: emitted reloadSkills:true after installing a skill" \
    || fail "main reloadSkills: did not emit reloadSkills. Out: $(cat "$out" 2>/dev/null)"
  [ -f "$home/.claude/skills/s/SKILL.md" ] \
    && ok "main reloadSkills: fetched the skill into ~/.claude/skills/" \
    || fail "main reloadSkills: skill not fetched"
}

test_main_no_emit_without_manifest() {
  local d proj home out; d="$(new_stub_dir)"
  command -v jq >/dev/null 2>&1 && ln -sf "$(command -v jq)" "$d/jq"
  proj="$(mktemp -d "$WORK/mn-proj.XXXXXX")"; mkdir -p "$proj/.claude"   # no manifest
  home="$WORK/mn-home"; mkdir -p "$home"; out="$WORK/mn.out"
  ( export PATH="$d:/usr/bin:/bin" HOME="$home" TMPDIR="$WORK" \
      CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$proj"; bash "$SCRIPT" ) >"$out" 2>/dev/null || true
  grep -q 'reloadSkills' "$out" 2>/dev/null \
    && fail "main no-manifest: emitted reloadSkills with nothing to reload. Out: $(cat "$out" 2>/dev/null)" \
    || ok "main no-manifest: emitted no reloadSkills (nothing installed)"
}

test_install_skill_happy
test_install_skill_unsafe_leaf
test_install_skill_missing_skillmd
test_install_skill_resume_noop
test_install_skill_path_traversal
test_install_skill_requires_leaf_eq_name
test_install_skill_rejects_symlink
test_install_skill_no_stage_leftover
test_fetch_tarball_https_and_memoizes
test_fetch_tarball_anon_then_token
test_bootstrap_end_to_end
test_bootstrap_malformed_manifest
test_bootstrap_dup_leaf_skipped
test_bootstrap_absent_manifest_noop
test_gate_local_noop
test_main_emits_reloadskills_with_manifest
test_main_no_emit_without_manifest

echo ""
echo "bootstrap-web: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
[ "$FAIL" -eq 0 ]
