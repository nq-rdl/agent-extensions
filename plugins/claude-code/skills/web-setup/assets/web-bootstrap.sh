#!/usr/bin/env bash
#
# web-bootstrap.sh — per-session bootstrap for a Claude Code on the web session.
#
# Invoked from the repo's .claude/settings.json SessionStart hook. It is a no-op
# unless running inside an Anthropic-managed cloud VM (CLAUDE_CODE_REMOTE=true),
# so it never touches a local contributor's machine.
#
# The heavy provisioning (Claude plugin pre-seed) lives in
# scripts/cc-web-setup.sh, which the web environment's *setup script* should run
# ONCE before the snapshot (`make cc-web-setup`) so plugin skills are available
# on the FIRST session — Claude enumerates skills at startup, so a plugin
# installed by this hook only surfaces next session. This per-session hook then:
#   * self-heals by running cc-web-setup.sh when the environment was not
#     pre-provisioned (on that path, plugin skills only arrive next session);
#   * provisions the portable per-session tooling a snapshot cannot carry: the
#     GitHub CLI (PR/CI automation) and the Codex CLI (a second opinion via
#     `codex exec`), persisting both on PATH for later Bash commands;
#   * sources an optional project hook (web-bootstrap.local.sh) for repo-specific
#     glue (language toolchains, container runtimes, git-hook wiring, …).
#
# This script is PORTABLE: it carries no project-specific dependencies. Anything
# specific to one repo belongs in scripts/web-bootstrap.local.sh (sourced below).
#
# Output discipline: SessionStart stdout is injected into Claude's context, so
# verbose tool output goes to $LOG and only concise status lines reach stdout.
#
# Every step is non-fatal: a SessionStart hook that exits non-zero can disrupt
# session start, so problems are logged and the script always exits 0.
set -uo pipefail

# Only colorize on a TTY — cloud SessionStart stdout is non-TTY and injected into
# the model context, where ANSI escapes are just noise.
if [ -t 1 ]; then _BLU=$'\033[34m'; _RST=$'\033[0m'; else _BLU=''; _RST=''; fi
log() { printf '%s[web-bootstrap]%s %s\n' "$_BLU" "$_RST" "$*"; }

# Pinned GitHub CLI (gh) release. GitHub releases are on the cloud "Trusted"
# network allowlist. Update the pin and BOTH per-arch checksums together — the
# SHA-256 values are gh's published gh_<ver>_checksums.txt entries.
GH_PIN="2.95.0"
GH_SHA256_x86_64="25d1e4729e8808c9ed3d613e96ebd3f3e44446f2d368c89d878a71a36ddb3d8c"
GH_SHA256_aarch64="d41e0b3b6218e5741c8bb4db39b16e53a59e0e06299a8489bd38f623ef7ebaae"

# Install the GitHub CLI from a checksum-pinned GitHub release into ~/.local/bin
# so PR/CI automation can run from the cloud session (gh authenticates from the
# GH_TOKEN the environment injects). Idempotent, but PIN-AWARE: it short-circuits
# ONLY when the gh already on PATH reports the pinned version, so a base image
# shipping a different gh is replaced by GH_PIN rather than silently used.
# (GitHub releases, not a vendor install script, because only github.com is on
# the default Trusted allowlist.)
ensure_gh() {
  export PATH="${HOME}/.local/bin:${PATH}"
  # Fixed-string grep (-F) so the version literal is matched verbatim, no regex.
  # The trailing space pins the match to the exact version: `gh --version` prints
  # `gh version X.Y.Z (DATE)`, so the space after ${GH_PIN} stops 2.95.0 from
  # matching a hypothetical 2.95.01.
  if command -v gh >/dev/null 2>&1 && gh --version 2>/dev/null | grep -qF "gh version ${GH_PIN} "; then
    return 0
  fi
  # Preflight every external tool the install path needs, failing fast with a
  # per-tool message so a missing sha256sum does not surface as a misleading
  # "checksum mismatch".
  local tool
  for tool in curl sha256sum tar; do
    command -v "$tool" >/dev/null 2>&1 || { log "WARNING: $tool not found — cannot install gh."; return 1; }
  done
  local arch asset sha url tmp bin
  arch="$(uname -m)"
  case "$arch" in
    x86_64)  asset="gh_${GH_PIN}_linux_amd64.tar.gz"; sha="$GH_SHA256_x86_64" ;;
    aarch64) asset="gh_${GH_PIN}_linux_arm64.tar.gz"; sha="$GH_SHA256_aarch64" ;;
    *) log "WARNING: unsupported arch '$arch' for the gh install."; return 1 ;;
  esac
  url="https://github.com/cli/cli/releases/download/v${GH_PIN}/${asset}"
  log "Installing gh ${GH_PIN} from GitHub (${asset})…"
  mkdir -p "${HOME}/.local/bin"
  # Template-based mktemp: portable across GNU/BSD (a bare `mktemp -d` needs a
  # template on BSD/macOS).
  if ! tmp="$(mktemp -d "${TMPDIR:-/tmp}/gh-install.XXXXXX")" || [ -z "$tmp" ]; then
    log "WARNING: failed to create a temp dir for the gh install."; return 1
  fi
  if ! curl -fsSL "$url" -o "$tmp/gh.tar.gz" 2>>"$LOG"; then
    log "WARNING: gh download failed (see ${LOG})."; rm -rf "$tmp"; return 1
  fi
  # Verify the pinned checksum before touching the binary.
  if ! printf '%s  %s\n' "$sha" "$tmp/gh.tar.gz" | sha256sum -c - >>"$LOG" 2>&1; then
    log "WARNING: gh checksum mismatch for ${asset} — refusing to install."; rm -rf "$tmp"; return 1
  fi
  # Extract/find/install with an explicit, logged failure arm at every step: a
  # silent no-op here would let the function fall through to a stale wrong-version
  # gh already on PATH (via the ${HOME}/.local/bin prepend) and falsely report OK.
  if tar -xzf "$tmp/gh.tar.gz" -C "$tmp" 2>>"$LOG"; then
    bin="$(find "$tmp" -type f -name gh -path '*/bin/gh' 2>/dev/null | head -1 || true)"
    if [ -z "$bin" ]; then
      log "WARNING: gh tarball had no bin/gh after extract — refusing to install."; rm -rf "$tmp"; return 1
    fi
    if ! install -m 0755 "$bin" "${HOME}/.local/bin/gh" 2>>"$LOG"; then
      log "WARNING: failed to install gh into ${HOME}/.local/bin (see ${LOG})."; rm -rf "$tmp"; return 1
    fi
  else
    log "WARNING: failed to extract the gh tarball (see ${LOG})."; rm -rf "$tmp"; return 1
  fi
  rm -rf "$tmp"
  # Honest final signal: confirm the PINNED version is what now resolves (trailing
  # space => exact match), rather than trusting whatever gh PATH happens to find.
  gh --version 2>/dev/null | grep -qF "gh version ${GH_PIN} "
}

# Pinned Codex CLI release (openai/codex). GitHub releases are on the cloud
# "Trusted" network allowlist, so — like ensure_gh — we install from a release
# asset rather than npm (not on the default allowlist). We deliberately install
# the "package" tarball (codex-package-<arch>-unknown-linux-musl.tar.gz), NOT the
# bare codex-<arch>.tar.gz, for two reasons: (1) OpenAI publishes its SHA-256 in
# the release's codex-package_SHA256SUMS, so the checksum below is an
# upstream-published digest (the bare binary has none); (2) it bundles the runtime
# resources codex uses (the bwrap sandbox + a vendored ripgrep) under
# codex-resources/ + codex-path/, which the binary resolves relative to its real
# path. Update the pin and BOTH per-arch checksums together — the values are the
# codex-package-<arch>-unknown-linux-musl.tar.gz entries from that tag's
# codex-package_SHA256SUMS.
CODEX_PIN="0.141.0"
CODEX_TAG="rust-v${CODEX_PIN}"
CODEX_SHA256_x86_64="091c8a2e27370c41407fa1cb647fe905bd4fd70e4689c13effee0a2dce1b2b07"
CODEX_SHA256_aarch64="b70030338592de3e361f3cde83d624f88061df300abe31b62075a5c5a058a6fc"

# True iff the codex on PATH reports EXACTLY the pinned version. `codex --version`
# prints `codex-cli X.Y.Z`; codex has no trailing space to anchor on (unlike `gh
# version X.Y.Z `), so we match with an ERE boundary ([[:space:]]|$). That keeps a
# suffixed build like `codex-cli 0.141.0-alpha.7` from satisfying the pin as a
# prefix, and the dots in the pin are escaped so they match literally.
codex_is_pinned() {
  command -v codex >/dev/null 2>&1 || return 1
  codex --version 2>/dev/null | grep -Eq "codex-cli ${CODEX_PIN//./\\.}([[:space:]]|\$)"
}

# Install the Codex CLI from a checksum-pinned GitHub release. Mirrors ensure_gh:
# idempotent and PIN-AWARE (short-circuits ONLY when the codex on PATH reports the
# pinned version, so a base image shipping a different codex is replaced rather
# than silently used), with an explicit logged failure arm at every step so a
# silent no-op can never make the function falsely report OK.
#
# The package tarball is not a lone binary: it extracts to bin/codex plus sibling
# codex-resources/ + codex-path/ trees. So we stage it into a per-version dir under
# ${HOME}/.local/share/codex and symlink bin/codex onto ${HOME}/.local/bin. codex
# locates its resources via its real executable path (/proc/self/exe follows the
# symlink to the staged dir), so a PATH symlink keeps the bundled sandbox + ripgrep
# resolvable — verified before adopting this layout.
ensure_codex_cli() {
  export PATH="${HOME}/.local/bin:${PATH}"
  # Pin-aware short-circuit: skip the install ONLY when the codex on PATH already
  # reports exactly the pinned version (boundary-aware — see codex_is_pinned).
  if codex_is_pinned; then
    return 0
  fi
  # Preflight every external tool the install path needs, failing fast with a
  # per-tool message (mirrors ensure_gh — a missing sha256sum must not surface as
  # a misleading checksum mismatch).
  local tool
  for tool in curl sha256sum tar; do
    command -v "$tool" >/dev/null 2>&1 || { log "WARNING: $tool not found — cannot install codex."; return 1; }
  done
  local arch asset sha url tmp staging dest
  arch="$(uname -m)"
  case "$arch" in
    x86_64)  asset="codex-package-x86_64-unknown-linux-musl.tar.gz";  sha="$CODEX_SHA256_x86_64" ;;
    aarch64) asset="codex-package-aarch64-unknown-linux-musl.tar.gz"; sha="$CODEX_SHA256_aarch64" ;;
    *) log "WARNING: unsupported arch '$arch' for the codex install."; return 1 ;;
  esac
  url="https://github.com/openai/codex/releases/download/${CODEX_TAG}/${asset}"
  log "Installing codex ${CODEX_PIN} from GitHub (${asset})…"
  mkdir -p "${HOME}/.local/bin" "${HOME}/.local/share/codex"
  if ! tmp="$(mktemp -d "${TMPDIR:-/tmp}/codex-install.XXXXXX")" || [ -z "$tmp" ]; then
    log "WARNING: failed to create a temp dir for the codex install."; return 1
  fi
  if ! curl -fsSL "$url" -o "$tmp/codex.tar.gz" 2>>"$LOG"; then
    log "WARNING: codex download failed (see ${LOG})."; rm -rf "$tmp"; return 1
  fi
  # Verify the pinned (upstream-published) checksum before touching the archive.
  if ! printf '%s  %s\n' "$sha" "$tmp/codex.tar.gz" | sha256sum -c - >>"$LOG" 2>&1; then
    log "WARNING: codex checksum mismatch for ${asset} — refusing to install."; rm -rf "$tmp"; return 1
  fi
  # Stage into a sibling of the final dir so the swap-in is an atomic same-FS
  # rename (mktemp -d under ${HOME}/.local/share/codex), then verify the entrypoint
  # exists before adopting it — a silent extract no-op must not fall through to the
  # final version check off a stale codex already on PATH.
  if ! staging="$(mktemp -d "${HOME}/.local/share/codex/.stage.XXXXXX")" || [ -z "$staging" ]; then
    log "WARNING: failed to create a staging dir for the codex install."; rm -rf "$tmp"; return 1
  fi
  if ! tar -xzf "$tmp/codex.tar.gz" -C "$staging" 2>>"$LOG"; then
    log "WARNING: failed to extract the codex tarball (see ${LOG})."; rm -rf "$tmp" "$staging"; return 1
  fi
  if [ ! -x "$staging/bin/codex" ]; then
    log "WARNING: codex tarball had no bin/codex after extract — refusing to install."; rm -rf "$tmp" "$staging"; return 1
  fi
  dest="${HOME}/.local/share/codex/${CODEX_PIN}"
  rm -rf "$dest"
  if ! mv "$staging" "$dest" 2>>"$LOG"; then
    log "WARNING: failed to move codex into ${dest} (see ${LOG})."; rm -rf "$tmp" "$staging"; return 1
  fi
  rm -rf "$tmp"
  if ! ln -sf "$dest/bin/codex" "${HOME}/.local/bin/codex" 2>>"$LOG"; then
    log "WARNING: failed to symlink codex onto ${HOME}/.local/bin (see ${LOG})."; return 1
  fi
  # Honest final signal: confirm the PINNED version is what now resolves on PATH,
  # rather than trusting whatever codex PATH happens to find.
  codex_is_pinned
}

# Seed $CODEX_HOME/auth.json from a pre-obtained ChatGPT-OAuth credential blob.
#
# This is the headless path for a *personal* ChatGPT plan (Plus/Pro/Team), which
# CANNOT mint the enterprise agent-identity JWT that `--with-access-token` requires
# (see ensure_codex_auth). Instead the user runs `codex login` once on a trusted
# machine with a browser — configuring `cli_auth_credentials_store = "file"` in
# ~/.codex/config.toml so codex writes the credential to disk rather than the OS
# keychain — and injects the ENTIRE resulting ~/.codex/auth.json as the secret
# CODEX_AUTH_JSON. We write it back verbatim, so the on-disk shape always matches
# the codex version that produced it. The long-lived refresh_token then lets codex
# refresh the short-lived access_token in place during the session.
#
# Idempotent and non-destructive: writes only when no auth.json exists yet, so a
# token codex already refreshed THIS session is never clobbered. printf + umask 077
# keep the secret off argv and off a group/other-readable file. Quiet no-op when
# CODEX_AUTH_JSON is unset (returns 1 so the caller can fall back to the token path).
seed_codex_auth_json() {
  [ -n "${CODEX_AUTH_JSON:-}" ] || return 1
  if ! command -v codex >/dev/null 2>&1; then
    log "WARNING: CODEX_AUTH_JSON is set but the codex CLI is not on PATH — skipping."
    return 1
  fi
  local codex_home auth
  codex_home="${CODEX_HOME:-${HOME}/.codex}"
  auth="${codex_home}/auth.json"
  # Already present (a resume, or codex refreshed it this session) => trust it and
  # do not overwrite a possibly-refreshed file with the original secret.
  if [ -f "$auth" ]; then
    log "Codex auth.json already present — leaving it untouched."
    return 0
  fi
  if ! mkdir -p "$codex_home" 2>>"$LOG"; then
    log "WARNING: could not create ${codex_home} for the codex auth.json (see ${LOG})."; return 1
  fi
  # Subshell umask so the secret file is created 0600 from the outset (never a
  # group/other-readable window); printf keeps the blob off argv.
  if ! ( umask 077; printf '%s' "$CODEX_AUTH_JSON" > "$auth" ) 2>>"$LOG"; then
    log "WARNING: failed to write ${auth} from CODEX_AUTH_JSON (see ${LOG})."; return 1
  fi
  chmod 600 "$auth" 2>>"$LOG" || true
  # Honest signal: confirm codex actually accepts the seeded credentials, rather
  # than trusting that a written file means a working login. Probe with
  # CODEX_ACCESS_TOKEN unset so it reflects ONLY auth.json (mirrors ensure_codex_auth).
  if ( unset CODEX_ACCESS_TOKEN; codex login status ) >>"$LOG" 2>&1; then
    log "Seeded codex auth.json from CODEX_AUTH_JSON (authenticated)."
    return 0
  fi
  log "WARNING: seeded auth.json but 'codex login status' still reports unauthenticated — re-capture CODEX_AUTH_JSON from a fresh local 'codex login' (see ${LOG})."
  return 1
}

# Drop CODEX_ACCESS_TOKEN on BOTH fronts so a value codex can't use as a JWT never
# reaches it: (1) `unset` it in THIS process, and (2) persist `unset CODEX_ACCESS_TOKEN`
# to CLAUDE_ENV_FILE so later Bash tool shells inherit the unset too. Codex reads
# CODEX_ACCESS_TOKEN from the live env at runtime and parses it AS a JWT, so leaving a
# blank/whitespace or auth.json-blob value in place makes every later `codex exec` fail
# even when a valid auth.json is on disk. $1 is a short reason for the log line.
drop_codex_access_token() {
  local reason="$1"
  if [ -n "${CLAUDE_ENV_FILE:-}" ] && ! grep -qF 'unset CODEX_ACCESS_TOKEN' "$CLAUDE_ENV_FILE" 2>/dev/null; then
    if echo 'unset CODEX_ACCESS_TOKEN' >> "$CLAUDE_ENV_FILE" 2>>"$LOG"; then
      log "Unset CODEX_ACCESS_TOKEN for the session (${reason})."
    else
      log "WARNING: could not append 'unset CODEX_ACCESS_TOKEN' to CLAUDE_ENV_FILE — later codex calls may still see it (see ${LOG})."
    fi
  fi
  unset CODEX_ACCESS_TOKEN
}

# Authenticate the Codex CLI non-interactively from an env-injected OAuth token.
#
# The web container is fresh each session and ~/.codex is not persisted, so the
# interactive browser login cannot be used. Codex stores credentials in
# $CODEX_HOME/auth.json (default ~/.codex/auth.json); the supported headless path
# is `codex login --with-access-token`, which reads the token from STDIN. We pipe
# it in via printf so the secret never appears on a command line (argv is visible
# to other processes via `ps`/\proc) and never lands in CLAUDE_ENV_FILE.
#
# CODEX_ACCESS_TOKEN must be a Codex **agent identity JWT** — the only thing
# `--with-access-token` accepts. A ChatGPT *user* OAuth access token or an
# OPENAI_API_KEY is rejected on this path.
#
# Tolerated convenience case: if CODEX_ACCESS_TOKEN actually holds a full auth.json
# blob (leading '{') rather than a JWT, we route it to seed_codex_auth_json and
# unset the env var for the session, so a ChatGPT-OAuth blob works regardless of
# which secret slot it landed in (CODEX_AUTH_JSON is still the canonical name).
#
# Non-fatal and idempotent: absent token => quiet no-op; already-authenticated
# (e.g. a resume) => skip the re-login.
ensure_codex_auth() {
  # No token => nothing to do. Stay TRULY silent here: SessionStart stdout is
  # injected into the model context and this is the common case.
  if [ -z "${CODEX_ACCESS_TOKEN:-}" ]; then
    return 0
  fi
  # A CODEX_ACCESS_TOKEN with surrounding whitespace passes the -z guard above but
  # is unusable as-is: a JWT never contains leading/trailing whitespace, yet a
  # secret injected from a file commonly carries a stray trailing newline (and a
  # slot may hold only spaces). Trim BOTH ends once — reused by the blank check,
  # the auth.json-blob detection, AND the login below — so an otherwise-valid
  # token isn't piped verbatim to `codex login --with-access-token` and rejected
  # as a malformed JWT (which emits a misleading "must be an agent identity JWT"
  # warning). If nothing remains, surface a clear "blank" diagnostic instead.
  local _codex_tok_trimmed="${CODEX_ACCESS_TOKEN#"${CODEX_ACCESS_TOKEN%%[![:space:]]*}"}"
  _codex_tok_trimmed="${_codex_tok_trimmed%"${_codex_tok_trimmed##*[![:space:]]}"}"
  if [ -z "$_codex_tok_trimmed" ]; then
    log "WARNING: CODEX_ACCESS_TOKEN is set but contains only whitespace — treating as unset (no codex login)."
    # "treating as unset" must be literal: codex reads CODEX_ACCESS_TOKEN at runtime
    # and would still parse the whitespace as a (malformed) JWT, so drop it for real.
    drop_codex_access_token "it contains only whitespace"
    return 1
  fi
  if ! command -v codex >/dev/null 2>&1; then
    log "WARNING: CODEX_ACCESS_TOKEN is set but the codex CLI is not on PATH — skipping."
    return 1
  fi
  # A full auth.json blob — not a JWT — is sometimes injected into CODEX_ACCESS_TOKEN
  # (e.g. to reuse a single GH_TOKEN-style secret slot for a personal ChatGPT-OAuth
  # credential). `--with-access-token` would reject it as a malformed JWT, so detect
  # the JSON shape (a leading '{' after optional whitespace) and route it to the
  # auth.json seeding path instead. Drop CODEX_ACCESS_TOKEN first (see
  # drop_codex_access_token) so codex doesn't parse the blob as a JWT at runtime; it
  # then falls back to ~/.codex/auth.json.
  # (_codex_tok_trimmed is the leading-trimmed token computed above.)
  if [ "${_codex_tok_trimmed:0:1}" = '{' ]; then
    local _codex_blob="$CODEX_ACCESS_TOKEN"
    drop_codex_access_token "it holds an auth.json blob, not a JWT"
    CODEX_AUTH_JSON="$_codex_blob" seed_codex_auth_json
    return $?
  fi
  # Idempotent: skip the re-login when a prior run THIS session already persisted
  # auth.json. The probe runs with CODEX_ACCESS_TOKEN unset so it reflects ONLY
  # saved credentials.
  if ( unset CODEX_ACCESS_TOKEN; codex login status ) >>"$LOG" 2>&1; then
    log "Codex already authenticated — skipping login."
    return 0
  fi
  # printf (no trailing newline) keeps the token off argv; codex reads it on stdin.
  # Pipe the whitespace-trimmed token: a stray leading/trailing newline would make
  # codex reject an otherwise-valid JWT (see _codex_tok_trimmed above).
  if printf '%s' "$_codex_tok_trimmed" | codex login --with-access-token >>"$LOG" 2>&1; then
    log "Codex authenticated via access token."
    # The trimmed value only fixed THIS login. If the raw env var carried
    # surrounding whitespace, the value still visible to later Bash tool shells is
    # a MALFORMED JWT — codex reads live CODEX_ACCESS_TOKEN before ~/.codex/auth.json,
    # so every later `codex exec` would fail despite the auth.json this login just
    # wrote. Drop the raw value (codex then falls back to auth.json). A clean token
    # (raw == trimmed) is left in place so the normal direct-token path keeps working.
    if [ "$CODEX_ACCESS_TOKEN" != "$_codex_tok_trimmed" ]; then
      drop_codex_access_token "it carried surrounding whitespace (a malformed JWT for later codex calls)"
    fi
    return 0
  fi
  log "WARNING: 'codex login --with-access-token' failed — CODEX_ACCESS_TOKEN must be a Codex agent identity JWT, not a ChatGPT access token or API key (see ${LOG})."
  return 1
}

# Turn OFF codex's own inner sandbox in $CODEX_HOME/config.toml. This whole hook
# only runs when CLAUDE_CODE_REMOTE=true (main() is gated on it), i.e. inside the
# isolated, ephemeral cloud container — which is ALREADY an external sandbox. So
# codex re-sandboxing every model-run command is redundant; worse, the container
# ships no bubblewrap on PATH, so each `codex exec` prints a "could not find
# bubblewrap" warning. Setting sandbox_mode = "danger-full-access" (the value
# codex documents for "environments that are externally sandboxed") disables the
# inner sandbox and silences that warning.
#
# Non-destructive + idempotent: leave config.toml untouched if the user has
# already made a deliberate sandbox/permissions choice (a top-level sandbox_mode
# key, a top-level default_permissions key, or any [permissions.*] table).
# "Top-level" matters: a key buried inside a [table] is an unrelated setting, so
# the guard inspects ONLY the region before the first [table] header. Otherwise
# inject the key — PREPEND it when a config already exists (a bare top-level key
# must precede any [table] header), or create it fresh. Failure is non-fatal.
configure_codex_sandbox() {
  local codex_home config
  codex_home="${CODEX_HOME:-${HOME}/.codex}"
  config="${codex_home}/config.toml"

  if [ -f "$config" ]; then
    local toplevel
    toplevel="$(awk '/^[[:space:]]*\[/{exit} {print}' "$config" 2>>"$LOG")"

    if printf '%s\n' "$toplevel" | grep -Eq '^[[:space:]]*sandbox_mode[[:space:]]*='; then
      log "Codex sandbox_mode already set in config.toml — leaving it untouched."
      return 0
    fi

    # `[].]` is a valid two-member bracket class {']', '.'} — a `]` immediately
    # after `[` is literal in POSIX ERE — so this matches a `[permissions]` table
    # header or any `[permissions.<sub>]` subtable, and nothing else.
    if printf '%s\n' "$toplevel" | grep -Eq '^[[:space:]]*default_permissions[[:space:]]*=' \
        || grep -Eq '^[[:space:]]*\[permissions[].]' "$config"; then
      log "Codex permission profile already configured — leaving config.toml untouched."
      return 0
    fi
  fi

  if ! mkdir -p "$codex_home" 2>>"$LOG"; then
    log "WARNING: could not create ${codex_home} for the codex config (see ${LOG})."
    return 1
  fi

  if [ -f "$config" ]; then
    local tmp
    if ! tmp="$(mktemp "${config}.XXXXXX")" || [ -z "$tmp" ]; then
      log "WARNING: could not stage a temp file to update the codex config (see ${LOG})."
      return 1
    fi
    if { printf 'sandbox_mode = "danger-full-access"\n'; cat "$config"; } >"$tmp" 2>>"$LOG" \
        && mv "$tmp" "$config" 2>>"$LOG"; then
      log "Disabled codex inner sandbox (sandbox_mode=danger-full-access) — the runner is already sandboxed."
      return 0
    fi
    rm -f "$tmp" 2>/dev/null
    log "WARNING: failed to update ${config} with sandbox_mode (see ${LOG})."
    return 1
  fi

  if ( umask 022; printf 'sandbox_mode = "danger-full-access"\n' >"$config" ) 2>>"$LOG"; then
    log "Disabled codex inner sandbox (sandbox_mode=danger-full-access) — the runner is already sandboxed."
    return 0
  fi
  log "WARNING: failed to write ${config} with sandbox_mode (see ${LOG})."
  return 1
}

# Persist a directory on PATH for subsequent Claude Bash tool commands. SessionStart
# hooks persist env for later commands by appending `export` lines to the file at
# $CLAUDE_ENV_FILE (which subsequent Bash commands source). Idempotent via a grep
# guard so re-runs do not duplicate the line. No-op when CLAUDE_ENV_FILE is unset.
persist_path() {
  local dir="$1" line
  [ -n "${CLAUDE_ENV_FILE:-}" ] || return 0
  # shellcheck disable=SC2016  # literal $PATH intended — expanded when sourced later
  line="export PATH=\"${dir}:\$PATH\""
  # Idempotent on the EXACT line (grep -qxF), not a substring: an unusual dir
  # cannot false-match another entry and skip a needed export. printf avoids
  # echo's backslash/-flag surprises.
  if ! grep -qxF "$line" "$CLAUDE_ENV_FILE" 2>/dev/null; then
    printf '%s\n' "$line" >> "$CLAUDE_ENV_FILE"
    log "Persisted ${dir} on PATH via CLAUDE_ENV_FILE."
  fi
}

# Imperative body. Wrapped in main() so the script is *sourceable* for unit
# tests: executing it (the SessionStart hook runs it by direct exec) runs main;
# sourcing it (the test harness) only defines the functions/globals above so they
# can be exercised against stubbed external tools. SUDO/LOG/PROJECT_DIR and the
# CLAUDE_CODE_REMOTE gate live in here so sourcing never touches the environment.
main() {
  # Only run inside Claude Code on the web. Locally this is a fast no-op so the
  # same committed hook is safe for every contributor.
  if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
    exit 0
  fi

  # SUDO is intentionally exposed as a global for the sourced project hook
  # (web-bootstrap.local.sh) to use when starting daemons (e.g. dockerd).
  SUDO=''
  # -n (non-interactive): a SessionStart hook has no TTY, so a sudo that needs a
  # password must fail fast rather than block the session waiting on input.
  # shellcheck disable=SC2034  # consumed by the sourced project hook, not this file
  [ "$(id -u)" -eq 0 ] || SUDO='sudo -n'

  # Verbose output sink (keeps the model's context clean — see header). Created
  # 0600 via a subshell umask so the log (which may capture command output) is
  # not world-readable from the outset.
  LOG="${TMPDIR:-/tmp}/rdl-web-bootstrap.log"
  ( umask 077; : > "$LOG" ) 2>/dev/null || LOG=/dev/null

  # Resolve the repo root. The hook exports CLAUDE_PROJECT_DIR; fall back to the
  # script's own location so it also works when run by hand.
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

  # --- 1. provisioning self-heal (plugin pre-seed) ----------------------------
  # Normally already done ONCE by the environment setup script (`make
  # cc-web-setup`) before the snapshot, which is what makes plugin skills available
  # this session. Re-running is idempotent, so this self-heals environments whose
  # setup script does not run it — though on that path plugin skills only surface
  # next session.
  if [ -f "${PROJECT_DIR}/scripts/cc-web-setup.sh" ]; then
    bash "${PROJECT_DIR}/scripts/cc-web-setup.sh" \
      || log "WARNING: cc-web-setup reported errors (see ${TMPDIR:-/tmp}/rdl-cc-web-setup.log)."
  fi

  # --- 2. GitHub CLI + token (every session) ----------------------------------
  # Provision gh so PR/CI automation can run from the cloud session, and report
  # whether the environment injected a GitHub token. gh reads GH_TOKEN (or
  # GITHUB_TOKEN) straight from the env — no `gh auth login` — so we just verify it
  # resolves. The install is idempotent, so after the first session this is cheap.
  if ensure_gh; then
    log "gh CLI ready ($(gh --version 2>/dev/null | head -1))."
    persist_path "${HOME}/.local/bin"
    if [ -n "${GH_TOKEN:-}" ] || [ -n "${GITHUB_TOKEN:-}" ]; then
      if gh auth status >>"$LOG" 2>&1; then
        log "GitHub token present — gh is authenticated."
      else
        log "GitHub token present but 'gh auth status' did not confirm auth (see ${LOG})."
      fi
    else
      log "WARNING: no GH_TOKEN/GITHUB_TOKEN in env — gh API calls will be unauthenticated/rate-limited."
    fi
  else
    log "WARNING: gh CLI not available (install failed — see ${LOG})."
  fi

  # --- 3. Codex CLI install + auth (every session; quiet no-op without creds) --
  # Install the Codex CLI and authenticate it so `codex exec` works headlessly.
  # Two supported credential inputs, in priority order:
  #   * CODEX_AUTH_JSON   — the full contents of a ~/.codex/auth.json captured from
  #                         a local `codex login` (ChatGPT OAuth). See seed_codex_auth_json.
  #   * CODEX_ACCESS_TOKEN — a Codex *agent identity JWT* for `--with-access-token`.
  #                         As a convenience this slot also accepts a full auth.json
  #                         blob (leading '{'), which is then seeded and unset.
  # Either one is the signal that codex is wanted here; with neither we skip the
  # (non-trivial) download too, keeping the committed hook a quiet no-op for
  # contributors who do not use Codex.
  if [ -n "${CODEX_AUTH_JSON:-}" ] || [ -n "${CODEX_ACCESS_TOKEN:-}" ]; then
    if ensure_codex_cli; then
      log "Codex CLI ready ($(codex --version 2>/dev/null | head -1))."
      persist_path "${HOME}/.local/bin"
      # Disable codex's inner sandbox: the runner is already an external sandbox.
      configure_codex_sandbox || true
      # Auth: prefer a pre-obtained auth.json blob (ChatGPT OAuth, personal plans);
      # fall back to the agent-identity token login (enterprise). Both idempotent.
      seed_codex_auth_json || ensure_codex_auth || true
    else
      log "WARNING: codex CLI install failed — 'codex exec' will be unavailable (see ${LOG})."
    fi
  fi

  # --- 4. SOURCE PROJECT HOOK (optional, project-specific) --------------------
  # The portable engine above carries no project dependencies. Repo-specific glue
  # — language toolchains on PATH, container runtimes, git-hook wiring (.husky /
  # .githooks / lefthook), fetching the default branch for merge-base checks, etc.
  # — belongs in scripts/web-bootstrap.local.sh, sourced here if present. A subshell
  # inherits main()'s helpers and globals (log, $LOG, $PROJECT_DIR, $SUDO,
  # $CLAUDE_ENV_FILE, persist_path), so its file/system side effects persist.
  #
  # SECURITY/ISOLATION: web-bootstrap.local.sh is trusted, repo-owned code — the
  # same trust level as this committed hook. Running it in a SUBSHELL keeps a stray
  # `exit` (or `exit 1`) from breaking this hook's "always exit 0" discipline and
  # stops its variable edits from leaking back; it does NOT sandbox the code (a
  # project hook legitimately needs the session's git/gh credentials). Signal a
  # soft failure with a non-zero exit/return — it is logged, never fatal.
  local local_hook="${PROJECT_DIR}/scripts/web-bootstrap.local.sh"
  if [ -f "$local_hook" ]; then
    log "Running project bootstrap hook (web-bootstrap.local.sh)…"
    # shellcheck source=/dev/null
    ( source "$local_hook" ) || log "WARNING: project bootstrap hook reported errors (see ${LOG})."
  fi

  log "Session bootstrap complete."
  exit 0
}

# Run the imperative body only when executed, not when sourced. The hook is
# invoked by direct exec ("$CLAUDE_PROJECT_DIR"/scripts/web-bootstrap.sh from the
# SessionStart hook), so BASH_SOURCE[0] == $0 holds for the real run and the test
# harness (which sources this file) skips main and just exercises the functions.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
