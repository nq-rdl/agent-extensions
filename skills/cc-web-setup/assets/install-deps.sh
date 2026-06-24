#!/usr/bin/env bash
#
# install-deps.sh — SessionStart hook for Claude Code on the web.
#
# Invoked from .claude/settings.json (SessionStart). A no-op unless running inside
# an Anthropic-managed cloud VM (CLAUDE_CODE_REMOTE=true), so the same committed
# hook is safe for every local contributor.
#
# PLUGINS ARE NOT INSTALLED HERE (primarily). Claude Code on the web installs the
# plugins declared in .claude/settings.json (enabledPlugins + extraKnownMarketplaces)
# at session start from their marketplaces — see the web docs' "what carries over"
# table — so their /<plugin>:<skill> commands surface without any Setup script or
# `make`. This hook only provisions what that declarative path does NOT cover:
#   * the per-session tooling a base image may lack — the GitHub CLI (PR/CI
#     automation) and the Codex CLI (a second opinion via `codex exec`);
#   * the project dev toolchain + services (lefthook, changie, gopls, python/jq,
#     the Docker daemon) via the optional project seam (install-deps.local.sh);
#   * a cheap idempotent PLUGIN SELF-HEAL (ensure_plugins) that retries the
#     declarative install if it did not complete at session start — first
#     REGISTERING the declared marketplaces (`claude plugin marketplace add`, for
#     the cold-start case where this hook outran Claude Code's own registration of
#     extraKnownMarketplaces and the registry is still empty), then refreshing a
#     stale index (`claude plugin marketplace update`) on a failed install.
#
# This engine is PORTABLE: it carries no project-specific dependencies. Anything
# specific to one repo belongs in .claude/scripts/install-deps.local.sh (sourced
# below) — the dev toolchain for THIS repo lives there.
#
# Output discipline: SessionStart stdout is injected into Claude's context, so
# verbose tool output goes to $LOG and only concise status lines reach stdout.
#
# Every step is non-fatal: a SessionStart hook that exits non-zero can disrupt
# session start, so problems are logged and the script always exits 0.
#
# Apply strict mode ONLY when executed as the hook, not when the test harness
# sources this file: `set` mutates global shell options, so an unguarded `set`
# here would leak -u/pipefail into the caller's shell and break the
# sourceable-for-tests guarantee noted at the bottom. Same BASH_SOURCE[0] == $0
# test as the main() guard.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  set -uo pipefail
fi

# Only colorize on a TTY — cloud SessionStart stdout is non-TTY and injected into
# the model context, where ANSI escapes are just noise.
if [ -t 1 ]; then _BLU=$'\033[34m'; _RST=$'\033[0m'; else _BLU=''; _RST=''; fi
log() { printf '%s[install-deps]%s %s\n' "$_BLU" "$_RST" "$*"; }

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
        || grep -Eq '^[[:space:]]*\[permissions([.][^]]+)?\][[:space:]]*$' "$config"; then
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
    # Check the append: an unwritable CLAUDE_ENV_FILE would otherwise leave later
    # Bash shells without ${dir} on PATH while we falsely log success. LOG may be
    # unset here (persist_path runs outside main() in tests), so guard the stderr
    # redirect with ${LOG:-/dev/null} to stay safe under `set -u`.
    if printf '%s\n' "$line" >> "$CLAUDE_ENV_FILE" 2>>"${LOG:-/dev/null}"; then
      log "Persisted ${dir} on PATH via CLAUDE_ENV_FILE."
    else
      log "WARNING: could not append PATH export for ${dir} to CLAUDE_ENV_FILE — later Bash shells will not see ${dir} on PATH."
    fi
  fi
}

# Register a declared GitHub marketplace WITHOUT git, by fetching it as a tarball
# over HTTPS and adding it from a local path.
#
# WHY THIS EXISTS: in a cloud session the in-sandbox GitHub proxy authorizes git
# operations ONLY against the session's own working repo. Verified empirically —
# `git ls-remote` of the session repo returns 200, but EVERY other repo (a
# different repo in the SAME org, and unrelated public repos alike) returns 403,
# and that proxy is independent of the environment's network-access level (so
# "Full" access does not change it). `claude plugin marketplace add owner/repo`
# is a `git clone`, so it 403s for every marketplace whose source repo is not the
# session repo — which is essentially all of them. This is a distinct failure
# mode from an empty registry, a stale index, or an unreachable host: the host is
# reachable and the policy allows it; only the git protocol to a non-session repo
# is denied.
#
# The non-git GitHub hosts (api.github.com, codeload.github.com) ARE on the
# default Trusted allowlist, so we fetch the marketplace as a tarball over HTTPS
# and register it from the extracted LOCAL PATH — which never invokes git.
# Verified end to end: `claude plugin marketplace add <local-dir>` + `claude
# plugin install <plugin>@<name>` both succeed this way.
#
# $1 declared marketplace name, $2 owner/repo, $3 ref (empty => default branch).
# Returns 0 iff the local-path registration succeeded. Non-fatal: every failure
# logs a specific reason and returns non-zero so the caller does not double-warn.
register_marketplace_via_tarball() {
  local name="$1" repo="$2" ref="$3"
  # A marketplace name is a settings.json key; reject path-unsafe values up front so
  # they cannot break the temp-file template or let $dest escape the cache dir.
  case "$name" in
    ''|.|..|*/*) log "  WARNING: marketplace name '${name}' is not a path-safe identifier — skipping tarball registration."; return 1 ;;
  esac
  # The official marketplace's NAME is reserved by the CLI to GitHub sources from
  # the 'anthropics' org ("The name 'claude-plugins-official' is reserved … and can
  # only be used with GitHub sources from the 'anthropics' organization"), so a
  # local-path registration is rejected outright — confirmed. Don't waste a
  # multi-MB download on it: its plugins must be VENDORED into the repo's
  # .claude/skills/ instead (the only path the proxy can't block — see the skill's
  # references/web-setup.rst). Catch it by the declared name or the anthropics owner.
  if [ "$name" = "claude-plugins-official" ] || [ "${repo%%/*}" = "anthropics" ]; then
    log "  WARNING: marketplace '${name}' (${repo}) is an official/reserved marketplace — it cannot be registered from a tarball; vendor its plugins' skills into .claude/skills/ instead (see the cc-web-setup skill's web-setup.rst)."
    return 1
  fi
  local tool
  for tool in curl tar; do
    command -v "$tool" >/dev/null 2>&1 || { log "  WARNING: $tool not found — cannot tarball-register marketplace '${name}'."; return 1; }
  done
  local base dest tmp url
  base="${XDG_CACHE_HOME:-${HOME}/.cache}/rdl-web-setup/marketplaces"
  dest="${base}/${name}"
  if ! mkdir -p "$base" 2>>"$LOG"; then
    log "  WARNING: could not create the marketplace cache dir ${base} (see ${LOG})."; return 1
  fi
  # Generic temp name — NOT mkt-${name}: a name with a '/' would make this a
  # nonexistent-subdir template and mktemp would fail for an otherwise-valid repo.
  if ! tmp="$(mktemp "${TMPDIR:-/tmp}/rdl-mkt.XXXXXX")" || [ -z "$tmp" ]; then
    log "  WARNING: could not stage a temp tarball for marketplace '${name}'."; return 1
  fi
  # api.github.com/repos/<owner>/<repo>/tarball[/<ref>] 302-redirects to a signed
  # codeload URL; -L follows it. Both hosts are Trusted-allowlisted. Omit the ref
  # segment to get the default branch (no need to discover it). Try ANONYMOUS first
  # — public repos need no token, and a stale/placeholder token would 401 a request
  # that would otherwise succeed — then retry WITH the env GitHub token for a
  # PRIVATE marketplace. This HTTPS fetch is the one place GH_TOKEN actually helps
  # the marketplace path; the git proxy ignores it entirely.
  url="https://api.github.com/repos/${repo}/tarball${ref:+/${ref}}"
  if ! curl -fsSL "$url" -o "$tmp" 2>>"$LOG"; then
    local tok="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
    if [ -z "$tok" ] || ! curl -fsSL -H "Authorization: Bearer ${tok}" "$url" -o "$tmp" 2>>"$LOG"; then
      log "  WARNING: could not download marketplace '${name}' tarball from ${url} (see ${LOG})."; rm -f "$tmp"; return 1
    fi
  fi
  # Re-extract cleanly: remove the WHOLE dir (a `${dest}/*` glob leaves dotfiles —
  # notably a prior run's .claude-plugin/ — behind, defeating the clean extract and
  # risking a register off stale content), then recreate it. The scoped `[ -n ]`
  # keeps any failure inside this function (a bare `${dest:?}` would abort the whole
  # hook shell, which the caller's `|| true` can't rescue). GitHub nests the tree
  # under a top-level <repo>-<sha>/ dir, so strip one component.
  [ -n "$dest" ] || { log "  WARNING: empty cache path for marketplace '${name}' — skipping."; rm -f "$tmp"; return 1; }
  rm -rf "$dest" 2>>"$LOG" || true
  if ! mkdir -p "$dest" 2>>"$LOG"; then
    log "  WARNING: could not recreate ${dest} for marketplace '${name}' (see ${LOG})."; rm -f "$tmp"; return 1
  fi
  if ! tar -xzf "$tmp" -C "$dest" --strip-components=1 2>>"$LOG"; then
    log "  WARNING: could not extract marketplace '${name}' tarball (see ${LOG})."; rm -f "$tmp"; return 1
  fi
  rm -f "$tmp"
  # Honest signal: a marketplace dir must carry .claude-plugin/marketplace.json, or
  # `marketplace add` would reject it — fail with a clear reason rather than letting
  # a malformed extract fall through.
  if [ ! -f "${dest}/.claude-plugin/marketplace.json" ]; then
    log "  WARNING: marketplace '${name}' tarball had no .claude-plugin/marketplace.json — refusing to register."; return 1
  fi
  # Register from the LOCAL PATH (no git → no 403). A reserved-name rejection can
  # still surface here for an official marketplace not caught by the guard above;
  # translate it into the vendoring pointer rather than a generic failure.
  local out
  if out="$(claude plugin marketplace add "$dest" </dev/null 2>&1)"; then
    printf 'marketplace %s registered from local tarball %s (%s)\n%s\n' "$name" "$dest" "$repo" "$out" >>"$LOG"
    log "  marketplace '${name}': registered from a downloaded tarball (git clone is blocked for non-session repos)."
    return 0
  fi
  printf '%s\n' "$out" >>"$LOG"
  if printf '%s' "$out" | grep -qi 'reserved'; then
    log "  WARNING: marketplace '${name}' uses a reserved name and cannot be registered from a tarball — vendor its plugins' skills into .claude/skills/ instead (see the cc-web-setup skill's web-setup.rst)."
  else
    log "  WARNING: could not register marketplace '${name}' from its tarball (see ${LOG})."
  fi
  return 1
}

# Self-heal the plugins declared in .claude/settings.json (enabledPlugins == true).
#
# WHY THIS EXISTS: Claude Code on the web installs the plugins declared in
# .claude/settings.json (enabledPlugins + extraKnownMarketplaces) at session start
# from their marketplaces — see the web docs' "what carries over" table — so this
# is NOT the primary install path. It is a belt-and-suspenders RETRY for when that
# did not complete. Four failure modes are covered: (1) an EMPTY marketplace
# registry — on a cold cloud VM this SessionStart hook can outrun Claude Code's own
# registration of extraKnownMarketplaces, so `claude plugin install` (and even
# `marketplace update`) fail with "Marketplace not found. Available marketplaces:"
# (an empty list) — NOT a network error; (2) a STALE local marketplace index — the
# marketplace is registered but its index was never refreshed, so the install fails
# with "Plugin not found in marketplace … your local copy may be out of date";
# (3) the docs' "requires network access to reach the marketplace source"; and
# (4) GITHUB-PROXY REPO-SCOPING — the in-sandbox GitHub proxy authorizes git only
# against the session's OWN repo, so `claude plugin marketplace add owner/repo` (a
# git clone) 403s for every other marketplace repo, independent of the network
# level. To cover (1) we first `claude plugin marketplace add` every declared
# marketplace (idempotent — a no-op once on disk) so the hook owns the whole add →
# update → install chain; `claude plugin install` does not refresh the index
# itself, so a failed install then runs `claude plugin marketplace update
# <marketplace>` and retries once (which fixes (2)). To cover (4), a failed git
# `marketplace add` of a GitHub source falls back to register_marketplace_via_tarball
# — an HTTPS tarball fetch + local-path add that never touches git (the official
# anthropics marketplace is name-reserved and the one exception, which must be
# vendored). Normally every plugin is already present and this is a quiet no-op.
#
# CAVEAT (timing): Claude enumerates skills at process startup, BEFORE SessionStart
# hooks finish, so anything this retry installs surfaces from the NEXT session, not
# the one that installs it — acceptable for a self-heal, since the platform's own
# session-start install is the first-session path.
#
# Idempotent: skips any plugin already in `claude plugin list`. Non-fatal: a failed
# install logs a warning and the session continues. Reads the enabled set straight
# from settings.json (single source of truth) so it cannot drift from what
# announce-capabilities.sh verifies.
ensure_plugins() {
  command -v claude >/dev/null 2>&1 || { log "claude CLI not on PATH — skipping plugin install."; return 0; }
  command -v jq >/dev/null 2>&1 || { log "jq not available — cannot read enabledPlugins; skipping plugin install."; return 0; }
  local settings="${PROJECT_DIR}/.claude/settings.json"
  [ -f "$settings" ] || return 0

  local plugins=() p
  while IFS= read -r p; do
    [ -n "$p" ] && plugins+=("$p")
  done < <(jq -r '(.enabledPlugins // {}) | to_entries[] | select(.value == true) | .key' "$settings" 2>/dev/null)
  [ "${#plugins[@]}" -gt 0 ] || return 0

  # Already-installed plugin ids (the `> <id>` lines from `claude plugin list`), so
  # we skip re-installing on a resume. Empty on a cold VM — every plugin installs.
  local installed_blob
  installed_blob="$(claude plugin list 2>/dev/null | awk '/^[[:space:]]*>[[:space:]]/ { print $2 }')"

  # Count plugins still needing install (those NOT already in `claude plugin list`).
  # On a cold VM this is the full set; on a warm resume it is 0 and the marketplace
  # registration + install below are skipped, keeping the resume a quiet no-op.
  local pending=0
  for p in "${plugins[@]}"; do
    printf '%s\n' "$installed_blob" | grep -qxF -- "$p" || pending=$((pending + 1))
  done

  # COLD-START RACE FIX: register the declared marketplaces BEFORE installing. On a
  # fresh cloud VM this hook can run before Claude Code has registered
  # extraKnownMarketplaces, leaving the registry empty — then `claude plugin install`
  # and `claude plugin marketplace update` both fail with "Marketplace not found.
  # Available marketplaces:" (an empty list), which is NOT a network failure.
  # `claude plugin marketplace add` is idempotent (a no-op once the marketplace is on
  # disk), so registering here lets the hook own the whole add → update → install
  # chain instead of depending on a registration that may not have happened yet.
  #
  # Source encoding (the `marketplace add <source>` grammar): a GitHub source pins a
  # ref as `owner/repo@ref`, a git URL as `<git-url>#ref`. A `path` on a GitHub
  # source (a non-default marketplace.json location) has NO `marketplace add`
  # equivalent — only the declarative extraKnownMarketplaces entry expresses it — so
  # such a marketplace is SKIPPED here rather than registered as the wrong catalog,
  # and Claude Code's own declarative registration handles it. jq emits one
  # `name<TAB>add|skip<TAB>source-or-reason<TAB>owner/repo<TAB>ref` row per declared
  # marketplace; the trailing owner/repo + ref (empty for non-github sources) feed
  # the git-403 tarball fallback below.
  if [ "$pending" -gt 0 ]; then
    # jq emits two extra fields beyond name/kind/src: the bare GitHub `owner/repo`
    # and `ref` (both empty for non-github sources), so a git-add failure can fall
    # back to a non-git tarball registration without re-parsing `owner/repo@ref`.
    local mkt_name mkt_kind mkt_src mkt_repo mkt_ref mkt_out
    while IFS=$'\t' read -r mkt_name mkt_kind mkt_src mkt_repo mkt_ref; do
      [ -n "$mkt_name" ] || continue
      if [ "$mkt_kind" = "skip" ]; then
        printf 'marketplace %s: not self-healed (%s)\n' "$mkt_name" "$mkt_src" >>"$LOG"
        continue
      fi
      [ -n "$mkt_src" ] || continue
      # `marketplace add` is idempotent but can still exit non-zero when the
      # marketplace is already registered (see tests/e2e/marketplace-smoke.sh) — that
      # case is benign, so an "already" message counts as success. Capture output to
      # $LOG either way; only a genuine failure earns a WARNING.
      if mkt_out="$(claude plugin marketplace add "$mkt_src" </dev/null 2>&1)"; then
        printf 'marketplace %s registered via %s\n%s\n' "$mkt_name" "$mkt_src" "$mkt_out" >>"$LOG"
      elif printf '%s' "$mkt_out" | grep -qi 'already'; then
        printf 'marketplace %s already registered (%s)\n%s\n' "$mkt_name" "$mkt_src" "$mkt_out" >>"$LOG"
      else
        # The git `marketplace add` failed. In the cloud the dominant cause is the
        # GitHub proxy 403'ing git for any non-session repo (see
        # register_marketplace_via_tarball). For a GitHub source, fall back to a
        # non-git tarball registration; the helper logs its own outcome (success or a
        # specific reason), so don't double-warn here. A non-github source (a git URL
        # or local path) has no tarball path, so it keeps the original WARNING.
        printf '%s\n' "$mkt_out" >>"$LOG"
        if [ -n "$mkt_repo" ]; then
          register_marketplace_via_tarball "$mkt_name" "$mkt_repo" "$mkt_ref" || true
        else
          log "  WARNING: could not register marketplace '${mkt_name}' (${mkt_src}) — see ${LOG}."
        fi
      fi
    done < <(jq -r '
      (.extraKnownMarketplaces // {}) | to_entries[]
      | .key as $name | .value.source as $s
      | if ($s.source == "github") and ($s.repo) then
          if (($s.path // "") != "") then [$name, "skip", "custom marketplace.json path not expressible via marketplace add", "", ""]
          else [$name, "add", ($s.repo + (if (($s.ref // "") != "") then "@" + $s.ref else "" end)), $s.repo, ($s.ref // "")] end
        elif (($s.url // "") != "") then [$name, "add", ($s.url + (if (($s.ref // "") != "") then "#" + $s.ref else "" end)), "", ""]
        elif (($s.path // "") != "") then [$name, "add", $s.path, "", ""]
        else [$name, "skip", "unrecognized source shape", "", ""] end
      | @tsv
    ' "$settings" 2>/dev/null)
  fi

  # $refreshed memoizes the marketplaces whose index we have already tried to
  # `marketplace update` THIS run, as a space-delimited set " <mkt> <mkt> ". Plain
  # string (not an associative array) so the hook stays bash 3.2-portable.
  local n_ok=0 n_fail=0 mkt refreshed=" "
  for p in "${plugins[@]}"; do
    if printf '%s\n' "$installed_blob" | grep -qxF -- "$p"; then
      continue
    fi
    log "Installing plugin ${p}…"
    if claude plugin install "$p" </dev/null >>"$LOG" 2>&1; then
      log "  ${p}: installed."
      n_ok=$((n_ok + 1))
      continue
    fi
    # First attempt failed. With the marketplace now registered (we ensured it just
    # above), the usual remaining cause is a STALE local index: the install reports
    # "Plugin not found in marketplace … your local copy may be out of date — try
    # `claude plugin marketplace update`", and `claude plugin install` does NOT do
    # that refresh itself. The id is `<plugin>@<marketplace>`, so the marketplace is
    # the suffix after the last '@'.
    mkt="${p##*@}"
    case "$refreshed" in
      *" ${mkt} "*)
        # A refresh was already ATTEMPTED for this marketplace earlier this run. If it
        # succeeded, this plugin's FIRST attempt above already ran against the updated
        # index; if it failed (unreachable), re-running the update would just fail
        # again. Either way a re-update + retry is pointless. Refresh each marketplace
        # AT MOST ONCE per run: multiple plugins can share one (e.g. three
        # claude-plugins-official entries), and an unreachable marketplace must not be
        # re-hit per plugin (network + SessionStart-delay). Fall straight through to
        # the failure diagnostic. Say "a refresh was already attempted" (not
        # "refreshed") so the line stays accurate even when that earlier update failed.
        log "  WARNING: could not install ${p}; a refresh was already attempted for marketplace '${mkt}' this run — the plugin id may be wrong or its source unreachable (see ${LOG})."
        n_fail=$((n_fail + 1))
        ;;
      *)
        refreshed="${refreshed}${mkt} "
        log "  ${p}: first attempt failed; refreshing marketplace '${mkt}' and retrying…"
        if claude plugin marketplace update "$mkt" </dev/null >>"$LOG" 2>&1; then
          if claude plugin install "$p" </dev/null >>"$LOG" 2>&1; then
            log "  ${p}: installed (after refreshing marketplace '${mkt}')."
            n_ok=$((n_ok + 1))
          else
            # Index is now fresh yet the install still fails => the plugin id is
            # likely wrong. Non-fatal — announce-capabilities.sh flags the gap.
            log "  WARNING: could not install ${p} even after refreshing marketplace '${mkt}' — the plugin id may be wrong (see ${LOG})."
            n_fail=$((n_fail + 1))
          fi
        else
          # The refresh itself failed, so the index may still be stale; say so rather
          # than claim we refreshed. Usually the marketplace source is unreachable.
          log "  WARNING: could not install ${p}; marketplace '${mkt}' could not be refreshed — its source may be unreachable (network) (see ${LOG})."
          n_fail=$((n_fail + 1))
        fi
        ;;
    esac
  done
  log "Plugin install: ${n_ok} installed, ${n_fail} failed, $(( ${#plugins[@]} - n_ok - n_fail )) already present."
  # When the self-heal actually had to install >=1 plugin THIS session (i.e. the
  # platform's own session-start install did not complete), leave a marker for
  # announce-capabilities.sh to surface the gap once. Best-effort: never fail on it.
  if [ "$n_ok" -gt 0 ]; then
    printf '%s\n' "$n_ok" > "${TMPDIR:-/tmp}/rdl-web-setup-installed" 2>/dev/null || true
  fi
  return 0
}

# Imperative body. Wrapped in main() so the script is *sourceable* for unit
# tests: executing it (the SessionStart hook runs it by direct exec) runs main;
# sourcing it (the test harness) only defines the functions/globals above so they
# can be exercised against stubbed external tools. SUDO/LOG/PROJECT_DIR and the
# CLAUDE_CODE_REMOTE gate live in here so sourcing never touches the environment.
main() {
  # SessionStart hook for Claude Code on the web. A no-op on a local machine so the
  # same committed hook never disturbs a contributor; everything below runs only in
  # a cloud session.
  [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0

  # SUDO is intentionally exposed as a global for the sourced project hook
  # (install-deps.local.sh) to use when starting daemons (e.g. dockerd).
  SUDO=''
  # -n (non-interactive): a SessionStart hook has no TTY, so a sudo that needs a
  # password must fail fast rather than block the session waiting on input.
  # shellcheck disable=SC2034  # consumed by the sourced project hook, not this file
  [ "$(id -u)" -eq 0 ] || SUDO='sudo -n'

  # Verbose output sink (keeps the model's context clean — see header). Use
  # mktemp for a UNIQUE, unpredictable name: a fixed /tmp/rdl-install-deps.log
  # could be pre-created as a symlink (truncating an arbitrary target via the
  # old `: > "$LOG"` redirect) or raced by a concurrent session. mktemp creates
  # the file safely (O_EXCL, no symlink follow); the subshell umask 077 keeps it
  # 0600 from the outset. Fall back to /dev/null if mktemp is unavailable/fails.
  LOG="$(umask 077; mktemp "${TMPDIR:-/tmp}/rdl-install-deps.XXXXXX" 2>/dev/null)" || LOG=/dev/null
  [ -n "$LOG" ] || LOG=/dev/null

  # Resolve the repo root. The hook exports CLAUDE_PROJECT_DIR; fall back to the
  # script's own location (this file lives at .claude/scripts/, so the repo root
  # is two levels up) so it also works when run by hand.
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

  # --- Project dev toolchain — source the project seam ------------------------
  # The portable engine carries no project deps. THIS repo's dev toolchain
  # (lefthook, changie, gopls, python/jq, the Docker daemon) + git-hook wiring
  # lives in the project seam, sourced here. A subshell inherits main()'s helpers
  # and globals (log, $LOG, $PROJECT_DIR, $SUDO, $CLAUDE_ENV_FILE, persist_path),
  # so its file/system side effects persist.
  #
  # SECURITY/ISOLATION: install-deps.local.sh is trusted, repo-owned code — the
  # same trust level as this committed script. Running it in a SUBSHELL keeps a
  # stray `exit` from breaking the "always exit 0" discipline and stops its
  # variable edits from leaking back; it does NOT sandbox the code (it legitimately
  # needs the session's git/gh credentials). Non-zero exit is logged, never fatal.
  local local_hook="${PROJECT_DIR}/.claude/scripts/install-deps.local.sh"
  if [ -f "$local_hook" ]; then
    log "Provisioning dev toolchain (install-deps.local.sh)…"
    # shellcheck source=/dev/null
    ( source "$local_hook" ) || log "WARNING: project bootstrap hook reported errors (see ${LOG})."
  fi

  # --- GitHub CLI + token -----------------------------------------------------
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

  # --- Codex CLI install + auth (quiet no-op without creds) -------------------
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
      if seed_codex_auth_json; then
        # auth.json is now the credential of record (freshly seeded OR already present
        # on a resume). codex reads CODEX_ACCESS_TOKEN BEFORE ~/.codex/auth.json, so a
        # leftover raw token would shadow the valid auth.json and break later
        # `codex exec`. ensure_codex_auth (the only caller of drop_codex_access_token)
        # never runs on this arm, so drop a stale token here ourselves.
        [ -n "${CODEX_ACCESS_TOKEN:-}" ] \
          && drop_codex_access_token "auth.json seeded; raw token would shadow it for later codex exec"
      else
        ensure_codex_auth || true
      fi
    else
      log "WARNING: codex CLI install failed — 'codex exec' will be unavailable (see ${LOG})."
    fi
  fi

  # --- Plugin self-heal (cheap no-op once installed) --------------------------
  # Claude Code on the web installs the plugins declared in .claude/settings.json
  # at session start (docs: "what carries over"). This is only a belt-and-suspenders
  # retry for the case where that did not complete (e.g. a transient marketplace
  # network failure) — idempotent, so normally a no-op. See the ensure_plugins header.
  ensure_plugins

  log "install-deps complete."
  exit 0
}

# Run the imperative body only when executed, not when sourced. The hook is
# invoked by direct exec ("$CLAUDE_PROJECT_DIR"/.claude/scripts/install-deps.sh from the
# SessionStart hook), so BASH_SOURCE[0] == $0 holds for the real run and the test
# harness (which sources this file) skips main and just exercises the functions.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
