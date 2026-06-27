#!/usr/bin/env bash
#
# bootstrap-web.sh — SessionStart hook for Claude Code on the web.
#
# FIRST-SESSION SKILL AVAILABILITY (the reloadSkills path).
#
# Claude Code enumerates skills at process startup, BEFORE SessionStart hooks
# finish — the hooks docs say so outright: "Skill discovery normally runs before
# SessionStart hooks finish, so files the hook writes into ~/.claude/skills/ or
# .claude/skills/ would otherwise only appear in the next session." The supported
# fix is the SessionStart output field `reloadSkills: true`, which "re-scans the
# skill and command directories after the SessionStart hooks complete, so skills
# the hook installed are available in the same session, starting with the first
# prompt" (hooks reference). The official example is a SessionStart hook that drops
# a team-skills repo into ~/.claude/skills/ and returns reloadSkills:true.
#
# This hook is that pattern, adapted for the cloud's GitHub git block: it fetches
# the skills listed in .claude/web-skills.json into ~/.claude/skills/<leaf>/ over
# HTTPS — api.github.com/repos/<owner>/<repo>/tarball -> codeload, both on the
# default Trusted allowlist — and then emits reloadSkills:true. It NEVER uses git:
# the in-sandbox GitHub proxy authorizes git only against the session's own repo,
# so `git clone` of any other repo 403s regardless of the network level or a
# GH_TOKEN (the token only helps the non-git HTTPS paths).
#
# It is the DYNAMIC alternative to VENDORING skills into the repo's own
# .claude/skills/ (which carry over as part of the clone and need no hook, no
# network, and no reloadSkills — available the very first session). Use this hook
# when you want the skills pulled FRESH each session instead of committed, or for
# skills you cannot commit. Both routes put loose skills where reloadSkills can see
# them — unlike a plugin install, whose cache reloadSkills does NOT re-scan.
#
# SKILLS ONLY. reloadSkills re-scans the skill + command dirs, NOT agents — so an
# AGENT fetched here would not surface this session. Agents (and slash-commands you
# want guaranteed) must be VENDORED (committed into .claude/agents/ and
# .claude/commands/), which carry over in the clone. This hook deliberately handles
# only ~/.claude/skills/, the dynamic-fetch escape hatch; vendoring is the default.
#
# Gated on CLAUDE_CODE_REMOTE=true: a no-op on a contributor's laptop, where it
# would otherwise write into the user's global ~/.claude/skills/. A quiet no-op
# when .claude/web-skills.json is absent (vendor-only repos never need it). Every
# step is non-fatal — a SessionStart hook that exits non-zero can disrupt session
# start — so problems are logged to $LOG and the script always exits 0.
#
# Apply strict mode ONLY when executed as the hook, not when the test harness
# sources this file (same BASH_SOURCE[0]==$0 guard as the main() runner at the
# bottom): an unguarded `set` would leak -u/pipefail into the caller's shell.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  set -uo pipefail
fi

# Only colorize on a TTY — cloud SessionStart stdout is non-TTY and (for the JSON
# we emit) machine-read, so ANSI escapes would be noise.
if [ -t 1 ]; then _BLU=$'\033[34m'; _RST=$'\033[0m'; else _BLU=''; _RST=''; fi
log() { printf '%s[bootstrap-web]%s %s\n' "$_BLU" "$_RST" "$*" >&2; }

# Fetch a GitHub repo as a tarball over HTTPS and extract it to a per-repo cache
# dir, echoing that dir on success. NO git (the proxy 403s a non-session clone);
# api.github.com + codeload are Trusted-allowlisted. Tries ANONYMOUS first (public
# repos need no token, and a stale token would 401 an otherwise-fine request), then
# retries with the env GitHub token for a PRIVATE marketplace. Memoizes per repo@ref
# in $TARBALL_CACHE so several skills from one repo download it once. Returns 0 and
# echoes the extracted dir on success; non-zero (nothing echoed) on failure.
#
# $1 owner/repo, $2 ref (empty => default branch).
fetch_repo_tarball() {
  local repo="$1" ref="$2" key slug sum dir tmp url tok
  # Cache key: a filesystem-safe slug of repo@ref, made COLLISION-FREE with a cksum
  # suffix of the exact input. A bare slug (tr non-[A-Za-z0-9._-] -> '-') would map
  # distinct refs like `feature/foo` and `feature-foo` to one dir and risk serving the
  # wrong revision; the digest of the raw `repo@ref` disambiguates them.
  slug="$(printf '%s@%s' "$repo" "$ref" | tr -c 'A-Za-z0-9._-' '-')"
  # cksum is POSIX (present on the runner); if somehow absent the suffix is empty and
  # the key degrades to the bare slug — no worse than before, never an error to stderr.
  sum="$(printf '%s@%s' "$repo" "$ref" | cksum 2>/dev/null | tr -cd '0-9')"
  key="${slug}.${sum}"
  dir="${TARBALL_CACHE}/${key}"
  # Already fetched this repo@ref this run (another skill shares it) => reuse.
  if [ -f "${dir}/.cc-web-fetched" ]; then
    printf '%s\n' "$dir"
    return 0
  fi
  local tool
  for tool in curl tar; do
    command -v "$tool" >/dev/null 2>&1 || { log "  WARNING: $tool not found — cannot fetch ${repo}."; return 1; }
  done
  if ! tmp="$(mktemp "${TMPDIR:-/tmp}/cc-web-skill.XXXXXX")" || [ -z "$tmp" ]; then
    log "  WARNING: could not stage a temp tarball for ${repo}."; return 1
  fi
  # api.github.com/repos/<owner>/<repo>/tarball[/<ref>] 302-redirects to a signed
  # codeload URL; -L follows it. Omit the ref segment for the default branch.
  url="https://api.github.com/repos/${repo}/tarball${ref:+/${ref}}"
  if ! curl -fsSL "$url" -o "$tmp" 2>>"$LOG"; then
    tok="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
    if [ -z "$tok" ] || ! curl -fsSL -H "Authorization: Bearer ${tok}" "$url" -o "$tmp" 2>>"$LOG"; then
      log "  WARNING: could not download ${repo} tarball from ${url} (see ${LOG})."; rm -f "$tmp"; return 1
    fi
  fi
  # Clean re-extract: remove the whole dir (a glob would leave dotfiles behind),
  # then recreate. The scoped [ -n ] keeps any failure inside this function (a bare
  # ${dir:?} would abort the whole hook shell). GitHub nests the tree under a
  # top-level <repo>-<sha>/ dir, so strip one component.
  [ -n "$dir" ] || { log "  WARNING: empty cache path for ${repo} — skipping."; rm -f "$tmp"; return 1; }
  rm -rf "$dir" 2>>"$LOG" || true
  if ! mkdir -p "$dir" 2>>"$LOG"; then
    log "  WARNING: could not create cache dir ${dir} for ${repo} (see ${LOG})."; rm -f "$tmp"; return 1
  fi
  if ! tar -xzf "$tmp" -C "$dir" --strip-components=1 2>>"$LOG"; then
    log "  WARNING: could not extract ${repo} tarball (see ${LOG})."; rm -f "$tmp" "$dir"; return 1
  fi
  rm -f "$tmp"
  : > "${dir}/.cc-web-fetched" 2>/dev/null || true
  printf '%s\n' "$dir"
}

# Echo the first top-level `name:` value from a SKILL.md's YAML frontmatter (the
# leading `---` block), or nothing if there is none. READ-ONLY — we validate that the
# leaf equals this name rather than rewriting it (frontmatter surgery is fragile:
# quoted/duplicate/block-scalar name keys all make a blind rewrite unsafe). Strips
# surrounding whitespace and quotes; a skill name never contains a quote.
skill_frontmatter_name() {
  local file="$1"
  command -v awk >/dev/null 2>&1 || return 0
  [ -f "$file" ] || return 0
  awk '
    NR==1 && /^---[[:space:]]*$/ { infm=1; next }
    infm && /^---[[:space:]]*$/  { exit }
    infm && /^name:[[:space:]]/ {
      v=$0; sub(/^name:[[:space:]]*/,"",v); sub(/[[:space:]]+$/,"",v); gsub(/["'\'']/,"",v)
      print v; exit
    }
  ' "$file" 2>/dev/null
}

# Copy one skill out of an extracted repo tarball into ~/.claude/skills/<leaf>/.
# Validates that the source path holds a SKILL.md (a skill dir must), so a wrong
# `path` fails with a clear reason instead of installing an empty/garbage dir.
# Idempotent on a resume: skips when ~/.claude/skills/<leaf>/SKILL.md already
# exists (the home dir is fresh per session but the hook can re-fire on resume).
#
# $1 extracted repo dir, $2 path within it to the skill dir, $3 leaf (target name).
# Returns 0 iff the skill is now present under ~/.claude/skills/<leaf>/.
install_skill() {
  local src_root="$1" path="$2" leaf="$3" src dest stage upstream
  # leaf is the install dir AND must equal the skill's own frontmatter name (below).
  # Enforce the skill-id contract: ASCII alnum + interior hyphens, ≤64 chars, no
  # leading/trailing hyphen. This both keeps it inside the tree (no '/', '..') and
  # guarantees it is a valid, unambiguous skill name.
  case "$leaf" in
    ''|-*|*-|*[!A-Za-z0-9-]*) log "  WARNING: skill leaf '${leaf}' is not a valid skill id (ASCII alnum + interior hyphens) — skipping."; return 1 ;;
  esac
  [ "${#leaf}" -le 64 ] || { log "  WARNING: skill leaf '${leaf}' exceeds 64 chars — skipping."; return 1; }
  # Constrain `path` to INSIDE the extracted repo: an absolute path or a `..`
  # segment could resolve outside src_root (…/../../etc). Bracket with slashes so a
  # leading/trailing or interior `..` segment is caught; a filename merely
  # CONTAINING dots (e.g. v1..2) is fine because it is not a bare `..` segment.
  case "/${path}/" in
    //*) log "  WARNING: skill '${leaf}': absolute path '${path}' — skipping."; return 1 ;;
    */../*) log "  WARNING: skill '${leaf}': path '${path}' escapes the repo (contains '..') — skipping."; return 1 ;;
  esac
  dest="${SKILLS_DIR}/${leaf}"
  if [ -f "${dest}/SKILL.md" ]; then
    log "  skill '${leaf}': already present — leaving it untouched (resume no-op)."
    return 0
  fi
  src="${src_root}/${path}"
  # Reject a SYMLINKED source dir: cp -R would preserve/deref it and a later read or
  # write could reach files OUTSIDE the extracted repo (a symlink escape).
  if [ -L "$src" ]; then
    log "  WARNING: skill '${leaf}': source path '${path}' is a symlink — refusing (not self-contained)."; return 1
  fi
  if [ ! -f "${src}/SKILL.md" ]; then
    log "  WARNING: skill '${leaf}': no SKILL.md at path '${path}' in the tarball — skipping."
    return 1
  fi
  if ! mkdir -p "$SKILLS_DIR" 2>>"$LOG"; then
    log "  WARNING: could not create ${SKILLS_DIR} (see ${LOG})."; return 1
  fi
  # ATOMIC install: stage into a sibling temp dir on the SAME filesystem, finalize
  # the copy, then rename into place. A failed cp can never leave a half-copied dest
  # that a later run mistakes for complete (its SKILL.md present but the rest missing).
  if ! stage="$(mktemp -d "${SKILLS_DIR}/.stage.XXXXXX" 2>>"$LOG")" || [ -z "$stage" ]; then
    log "  WARNING: could not stage a temp dir for skill '${leaf}' (see ${LOG})."; return 1
  fi
  # cp -R (not a symlink) so the skill survives independent of the per-run tarball cache.
  if ! cp -R "$src" "$stage/payload" 2>>"$LOG"; then
    log "  WARNING: could not copy skill '${leaf}' (see ${LOG})."; rm -rf "$stage"; return 1
  fi
  # Self-contained REAL FILES only: reject ANY symlink in the copied tree — it could
  # point outside the skill, and a vendored/fetched skill must not depend on targets
  # that vanish with the per-run tarball cache. (Catches a symlinked payload root too.)
  if [ -n "$(find "$stage/payload" -type l 2>/dev/null | head -1)" ]; then
    log "  WARNING: skill '${leaf}': contains symlink(s) — refusing (not self-contained)."; rm -rf "$stage"; return 1
  fi
  if [ ! -f "$stage/payload/SKILL.md" ]; then
    log "  WARNING: skill '${leaf}' copy left no SKILL.md — skipping."; rm -rf "$stage"; return 1
  fi
  # FAIL-CLOSED name contract: the leaf (install id) must EQUAL the skill's own
  # frontmatter name, so the /<id> is exactly what the manifest declares — no
  # frontmatter surgery, no silent mismatch (a loose skill's id follows its name).
  upstream="$(skill_frontmatter_name "$stage/payload/SKILL.md")"
  if [ -z "$upstream" ]; then
    log "  WARNING: skill '${leaf}': fetched SKILL.md has no frontmatter name — refusing."; rm -rf "$stage"; return 1
  fi
  if [ "$upstream" != "$leaf" ]; then
    log "  WARNING: skill '${leaf}': fetched skill is named '${upstream}' — set the manifest leaf to the upstream name (no renaming). Skipping."; rm -rf "$stage"; return 1
  fi
  # A stale dest must be removed FIRST, and a failed removal is FATAL: otherwise the
  # mv would nest payload INSIDE the surviving dir (…/<leaf>/payload).
  if [ -e "$dest" ] && ! rm -rf "$dest" 2>>"$LOG"; then
    log "  WARNING: could not replace existing ${dest} (see ${LOG})."; rm -rf "$stage"; return 1
  fi
  if ! mv "$stage/payload" "$dest" 2>>"$LOG"; then
    log "  WARNING: could not install skill '${leaf}' into ${dest} (see ${LOG})."; rm -rf "$stage"; return 1
  fi
  rm -rf "$stage"
  # Honest signal: confirm the destination really has a SKILL.md before counting it.
  [ -f "${dest}/SKILL.md" ] || { log "  WARNING: skill '${leaf}' install left no SKILL.md — skipping."; return 1; }
  log "  skill '${leaf}': installed into ~/.claude/skills/ from ${path}."
  return 0
}

# Read .claude/web-skills.json and install every listed skill into
# ~/.claude/skills/. Echoes nothing; sets the global N_INSTALLED to the count
# actually placed this run (0 on a pure resume or an absent/empty manifest), which
# main() uses to decide whether a reloadSkills re-scan is worth requesting.
#
# Manifest shape (objects under .skills[]):
#   { "repo": "owner/repo", "ref": "", "path": "plugins/<p>/skills/<s>", "leaf": "<name>" }
# `ref` is optional (empty => default branch). jq emits one repo<TAB>path<TAB>leaf<TAB>ref
# row per entry — with the only legitimately-empty field (ref) LAST, because TAB is an
# IFS-whitespace char so `read` collapses an EMPTY MIDDLE field and shifts the rest
# (a trailing empty field is harmless). The loop dedupes the tarball download per
# repo@ref via fetch_repo_tarball.
bootstrap_web_skills() {
  N_INSTALLED=0
  command -v jq >/dev/null 2>&1 || { log "jq not available — cannot read web-skills.json; skipping."; return 0; }
  local manifest="${PROJECT_DIR}/.claude/web-skills.json"
  [ -f "$manifest" ] || return 0
  # Validate shape AND element TYPES up front: .skills must be an array whose entries
  # each carry string repo/path/leaf (and an optional string ref). A non-string field
  # would make the @tsv below fail mid-stream — which, fed through a process
  # substitution, would be an invisible exit status and a fake "0 installed" success.
  if ! jq -e '
      (.skills // []) | type == "array"
      and all(.[]?;
        (.repo|type=="string") and (.path|type=="string") and (.leaf|type=="string")
        and ((.ref == null) or (.ref|type=="string")))
    ' "$manifest" >/dev/null 2>&1; then
    log "WARNING: ${manifest} is malformed — need .skills[] with string repo/path/leaf (optional string ref); skipping."
    return 0
  fi

  # Materialize the TSV to a file and CHECK jq's exit status before reading it: the
  # `done < <(jq …)` process-substitution form hides jq's rc, so a parse failure there
  # would silently yield zero rows and report success.
  local tsv
  tsv="$(mktemp "${TMPDIR:-/tmp}/cc-web-manifest.XXXXXX" 2>/dev/null)" \
    || { log "WARNING: could not stage the manifest TSV — skipping."; return 0; }
  if ! jq -r '.skills[]? | [(.repo // ""), (.path // ""), (.leaf // ""), (.ref // "")] | @tsv' \
        "$manifest" > "$tsv" 2>>"$LOG"; then
    log "WARNING: could not parse ${manifest} (jq error, see ${LOG}) — skipping."
    rm -f "$tsv"; return 0
  fi

  TARBALL_CACHE="$(mktemp -d "${TMPDIR:-/tmp}/cc-web-tarballs.XXXXXX" 2>/dev/null)" \
    || { log "WARNING: could not create a tarball cache dir — skipping."; rm -f "$tsv"; return 0; }

  local repo ref path leaf extracted n_seen=0 seen_leaves=" "
  while IFS=$'\t' read -r repo path leaf ref; do
    [ -n "$repo" ] && [ -n "$path" ] && [ -n "$leaf" ] || {
      log "WARNING: web-skills.json entry missing repo/path/leaf — skipping one entry."; continue; }
    # Strict leaf contract (mirrors install_skill): a valid skill id, so the resume
    # fast-path and dup tracking below operate only on safe names.
    case "$leaf" in
      ''|-*|*-|*[!A-Za-z0-9-]*) log "WARNING: web-skills.json leaf '${leaf}' is not a valid skill id (ASCII alnum + interior hyphens) — skipping."; continue ;;
    esac
    # Reject a duplicate leaf WITHIN the manifest: two entries targeting one
    # ~/.claude/skills/<leaf> would have the first silently win (the second hits the
    # resume fast-path below and is dropped without notice). Surface it instead.
    case "$seen_leaves" in
      *" ${leaf} "*) log "WARNING: duplicate leaf '${leaf}' in web-skills.json — skipping the repeat."; continue ;;
    esac
    seen_leaves="${seen_leaves}${leaf} "
    n_seen=$((n_seen + 1))
    # Reproducibility: only a full commit SHA is immutable. An empty ref tracks the
    # moving default branch; a tag or branch name can be repointed. Warn on any
    # non-SHA ref so a team can pin one.
    if [ -z "$ref" ]; then
      log "  note: skill '${leaf}' pins no ref — fetching the default branch (mutable); pin a commit SHA in web-skills.json for reproducibility."
    elif ! printf '%s' "$ref" | grep -qiE '^[0-9a-f]{7,64}$'; then
      log "  note: skill '${leaf}' ref '${ref}' is not a commit SHA — tags/branches are mutable; pin a full commit SHA for reproducibility."
    fi
    # Resume fast-path: a leaf already on disk needs neither a download nor a copy.
    if [ -f "${SKILLS_DIR}/${leaf}/SKILL.md" ]; then
      log "  skill '${leaf}': already present — leaving it untouched (resume no-op)."
      continue
    fi
    if extracted="$(fetch_repo_tarball "$repo" "$ref")" && [ -n "$extracted" ]; then
      if install_skill "$extracted" "$path" "$leaf"; then
        N_INSTALLED=$((N_INSTALLED + 1))
      fi
    fi
  done < "$tsv"
  rm -f "$tsv" 2>/dev/null || true

  rm -rf "$TARBALL_CACHE" 2>/dev/null || true
  log "Web skills: ${N_INSTALLED} installed into ~/.claude/skills/ ($((n_seen - N_INSTALLED)) already present or skipped)."
  return 0
}

# Imperative body, wrapped in main() so the script is sourceable for unit tests
# (executing it runs main; sourcing it only defines the functions above). The
# CLAUDE_CODE_REMOTE gate, LOG, PROJECT_DIR, SKILLS_DIR live here so sourcing never
# touches the environment.
main() {
  # Gate: only the cloud session writes into ~/.claude/skills/. A local contributor
  # is an immediate no-op so the committed hook never pollutes their global skills.
  [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

  # Verbose sink (keeps the model's context clean): the only thing this hook writes
  # to STDOUT is the reloadSkills JSON below — all status goes to $LOG. mktemp for a
  # unique, unpredictable name (a fixed /tmp path is a symlink-truncation/race
  # vector); umask 077 keeps it 0600. Fall back to /dev/null.
  LOG="$(umask 077; mktemp "${TMPDIR:-/tmp}/cc-bootstrap-web.XXXXXX" 2>/dev/null)" || LOG=/dev/null
  [ -n "$LOG" ] || LOG=/dev/null

  # Repo root. The hook exports CLAUDE_PROJECT_DIR; fall back to this file's location
  # (.claude/scripts/, so the repo root is two levels up) for a by-hand run.
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
  # Loose user skills dir — the directory reloadSkills re-scans. Honor CLAUDE_CONFIG_DIR
  # if the session relocates ~/.claude.
  SKILLS_DIR="${CLAUDE_CONFIG_DIR:-${HOME}/.claude}/skills"

  bootstrap_web_skills

  # Ask Claude Code to re-scan the skill + command directories once all SessionStart
  # hooks finish, so anything we just fetched into ~/.claude/skills/ is live THIS
  # session (skills enumerate before hooks finish — see the header). Emit it only
  # when we actually placed >=1 skill: a no-op manifest/resume needs no re-scan, and
  # announce-capabilities.sh already requests one on the web regardless. jq builds
  # the object; a printf fallback covers a jq-less runner.
  if [ "${N_INSTALLED:-0}" -gt 0 ]; then
    if command -v jq >/dev/null 2>&1; then
      jq -cn '{hookSpecificOutput: {hookEventName: "SessionStart", reloadSkills: true}}'
    else
      printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","reloadSkills":true}}'
    fi
  fi
  exit 0
}

# Run the imperative body only when executed, not when sourced (the SessionStart
# hook invokes this by direct exec, so BASH_SOURCE[0]==$0 holds; the test harness
# sources it and just exercises the functions).
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
