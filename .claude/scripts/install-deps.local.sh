#!/usr/bin/env bash
#
# install-deps.local.sh — THIS repo's dev toolchain (project-specific). Sourced
# by .claude/scripts/install-deps.sh in EVERY mode (it is the "dev toolchain"
# step, before the remote-only web runtime), so it provisions both `make
# install-deps` for a local contributor and every web session. It is the project
# seam: the portable engine carries no project deps, they all live here.
#
# PLUGINS are NOT installed here — install-deps.sh's ensure_plugins does that
# (Claude Code on the web registers the marketplaces but does not install the
# enabledPlugins). This seam provisions the tooling needed to WORK ON this repo:
#   * lefthook + changie — installed from CHECKSUM-PINNED GitHub releases into
#     ~/.local/bin (github.com is the reliably-allowlisted source on the cloud
#     sandbox), mirroring install-deps.sh's ensure_gh. They back the local git
#     hooks and the changelog gate, so commits made anywhere run the same checks
#     as CI.
#   * python3 / jq / pyyaml — the registry pipeline scripts (generate_manifests.py
#     etc., invoked by the lefthook hooks) need them; verify + best-effort install.
#   * the Docker daemon — the web runner ships the docker CLI + dockerd binary but
#     NO running daemon (no systemd), so a cloud session that needs containers
#     (devcontainer smoke tests, testcontainers, image builds) must start dockerd
#     itself. ensure_docker is idempotent: a no-op when `docker info` already
#     answers (a local dev's Docker Desktop, or a resume), so it is safe in every
#     mode. See the "Docker on Claude Code web" note in the cc-web-setup skill.
#   * PATH persistence, `lefthook install`, and an origin/main fetch for changie's
#     merge-base diffs.
#
# It shares install-deps.sh's helpers + globals: log(), $LOG, $PROJECT_DIR,
# $SUDO, $CLAUDE_ENV_FILE, persist_path(). Every step is non-fatal — the parent
# must always exit 0.

# Defensive fallbacks so the file is lint-clean / inspectable standalone; when
# sourced by install-deps.sh these are already provided and act as no-ops.
if ! command -v log >/dev/null 2>&1; then
  log() { printf '[install-deps.local] %s\n' "$*"; }
fi
: "${LOG:=/dev/null}"
: "${PROJECT_DIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
# $SUDO is provided by install-deps.sh (empty when root, `sudo -n` otherwise).
# Default it so a standalone run of this file is safe under `set -u`.
: "${SUDO:=}"

# Pinned tool releases. Update the pin and BOTH per-arch checksums together — the
# SHA-256 values are the upstream-published release checksums (lefthook's
# lefthook_checksums.txt; changie's checksums.txt).
LEFTHOOK_PIN="2.1.9"
LEFTHOOK_SHA256_x86_64="0d60b0d350c923963729574f6431171f0277788884ad0c6284fa0160c36e3877"
LEFTHOOK_SHA256_aarch64="304321997336c450af6b5c0cc641c59141168866fca0b1fc3767e067812600a9"

CHANGIE_PIN="1.24.2"
CHANGIE_SHA256_x86_64="31535a9d8dc548d6d8f315762bfd5b1fba34e707b7600748c8bb8a609649007d"
CHANGIE_SHA256_aarch64="c21bf5509c3cd6e86e0f290b497a12bed52849c40566d171c5d1cbdef19b156c"

# gopls — the Go language server, wired by the gopls-lsp@claude-plugins-official
# plugin (it runs the bare `gopls` command). Installed from source with `go
# install` (gopls ships no prebuilt GitHub release asset), so the pin is a module
# version rather than a checksummed binary; Go's module proxy + go.sum verify it.
GOPLS_PIN="0.22.0"

# True iff the lefthook on PATH reports EXACTLY the pinned version. `lefthook
# version` prints a bare `X.Y.Z`, so a plain substring grep for the pin would also
# match a longer release (2.1.9 ⊂ 2.1.90), wrongly short-circuiting the install
# onto an unpinned binary. Anchor the pin between line-start (or a non-version
# char) and a trailing whitespace/EOL boundary, dots escaped to match literally —
# mirrors install-deps.sh's codex_is_pinned.
lefthook_is_pinned() {
  command -v lefthook >/dev/null 2>&1 || return 1
  lefthook version 2>/dev/null | grep -Eq "(^|[^0-9.])${LEFTHOOK_PIN//./\\.}([[:space:]]|\$)"
}

# Install lefthook from a checksum-pinned GitHub release (a RAW binary asset, not
# a tarball) into ~/.local/bin. Idempotent + pin-aware: short-circuit ONLY when
# the lefthook on PATH already reports the pinned version, so a base image
# shipping a different lefthook is replaced rather than silently used.
ensure_lefthook() {
  export PATH="${HOME}/.local/bin:${PATH}"
  if lefthook_is_pinned; then
    return 0
  fi
  local tool
  for tool in curl sha256sum; do
    command -v "$tool" >/dev/null 2>&1 || { log "WARNING: $tool not found — cannot install lefthook."; return 1; }
  done
  local arch asset sha url tmp
  arch="$(uname -m)"
  case "$arch" in
    x86_64)  asset="lefthook_${LEFTHOOK_PIN}_Linux_x86_64";  sha="$LEFTHOOK_SHA256_x86_64" ;;
    aarch64) asset="lefthook_${LEFTHOOK_PIN}_Linux_aarch64"; sha="$LEFTHOOK_SHA256_aarch64" ;;
    *) log "WARNING: unsupported arch '$arch' for the lefthook install."; return 1 ;;
  esac
  url="https://github.com/evilmartians/lefthook/releases/download/v${LEFTHOOK_PIN}/${asset}"
  log "Installing lefthook ${LEFTHOOK_PIN} from GitHub (${asset})…"
  mkdir -p "${HOME}/.local/bin"
  if ! tmp="$(mktemp -d "${TMPDIR:-/tmp}/lefthook-install.XXXXXX")" || [ -z "$tmp" ]; then
    log "WARNING: failed to create a temp dir for the lefthook install."; return 1
  fi
  if ! curl -fsSL "$url" -o "$tmp/lefthook" 2>>"$LOG"; then
    log "WARNING: lefthook download failed (see ${LOG})."; rm -rf "$tmp"; return 1
  fi
  if ! printf '%s  %s\n' "$sha" "$tmp/lefthook" | sha256sum -c - >>"$LOG" 2>&1; then
    log "WARNING: lefthook checksum mismatch for ${asset} — refusing to install."; rm -rf "$tmp"; return 1
  fi
  if ! install -m 0755 "$tmp/lefthook" "${HOME}/.local/bin/lefthook" 2>>"$LOG"; then
    log "WARNING: failed to install lefthook into ${HOME}/.local/bin (see ${LOG})."; rm -rf "$tmp"; return 1
  fi
  rm -rf "$tmp"
  # Honest final signal: confirm the pinned lefthook is what now resolves
  # (boundary-aware — the same check as the short-circuit above).
  lefthook_is_pinned
}

# True iff the changie on PATH reports EXACTLY the pinned version. `changie
# --version` prints `changie version vX.Y.Z`, so a plain substring grep for the
# pin would also match a longer release (1.24.2 ⊂ 1.24.20). Anchored as in
# lefthook_is_pinned: the leading `v` (a non-version char) and a whitespace/EOL
# boundary fence the pin in.
changie_is_pinned() {
  command -v changie >/dev/null 2>&1 || return 1
  changie --version 2>/dev/null | grep -Eq "(^|[^0-9.])${CHANGIE_PIN//./\\.}([[:space:]]|\$)"
}

# Install changie from a checksum-pinned GitHub release tarball into ~/.local/bin.
# Mirrors ensure_lefthook; the goreleaser tarball extracts to a bare `changie`
# binary at its root. Idempotent + pin-aware.
ensure_changie() {
  export PATH="${HOME}/.local/bin:${PATH}"
  if changie_is_pinned; then
    return 0
  fi
  local tool
  for tool in curl sha256sum tar; do
    command -v "$tool" >/dev/null 2>&1 || { log "WARNING: $tool not found — cannot install changie."; return 1; }
  done
  local arch asset sha url tmp bin
  arch="$(uname -m)"
  case "$arch" in
    x86_64)  asset="changie_${CHANGIE_PIN}_linux_amd64.tar.gz"; sha="$CHANGIE_SHA256_x86_64" ;;
    aarch64) asset="changie_${CHANGIE_PIN}_linux_arm64.tar.gz"; sha="$CHANGIE_SHA256_aarch64" ;;
    *) log "WARNING: unsupported arch '$arch' for the changie install."; return 1 ;;
  esac
  url="https://github.com/miniscruff/changie/releases/download/v${CHANGIE_PIN}/${asset}"
  log "Installing changie ${CHANGIE_PIN} from GitHub (${asset})…"
  mkdir -p "${HOME}/.local/bin"
  if ! tmp="$(mktemp -d "${TMPDIR:-/tmp}/changie-install.XXXXXX")" || [ -z "$tmp" ]; then
    log "WARNING: failed to create a temp dir for the changie install."; return 1
  fi
  if ! curl -fsSL "$url" -o "$tmp/changie.tar.gz" 2>>"$LOG"; then
    log "WARNING: changie download failed (see ${LOG})."; rm -rf "$tmp"; return 1
  fi
  if ! printf '%s  %s\n' "$sha" "$tmp/changie.tar.gz" | sha256sum -c - >>"$LOG" 2>&1; then
    log "WARNING: changie checksum mismatch for ${asset} — refusing to install."; rm -rf "$tmp"; return 1
  fi
  if tar -xzf "$tmp/changie.tar.gz" -C "$tmp" 2>>"$LOG"; then
    bin="$(find "$tmp" -type f -name changie 2>/dev/null | head -1 || true)"
    if [ -z "$bin" ]; then
      log "WARNING: changie tarball had no changie binary after extract — refusing to install."; rm -rf "$tmp"; return 1
    fi
    if ! install -m 0755 "$bin" "${HOME}/.local/bin/changie" 2>>"$LOG"; then
      log "WARNING: failed to install changie into ${HOME}/.local/bin (see ${LOG})."; rm -rf "$tmp"; return 1
    fi
  else
    log "WARNING: failed to extract the changie tarball (see ${LOG})."; rm -rf "$tmp"; return 1
  fi
  rm -rf "$tmp"
  # Honest final signal: confirm the pinned changie is what now resolves
  # (boundary-aware — the same check as the short-circuit above).
  changie_is_pinned
}

# True iff the gopls on PATH reports EXACTLY the pinned version. `gopls version`
# prints `golang.org/x/tools/gopls vX.Y.Z`, so the leading `v` (a non-version
# char) and a trailing whitespace/EOL boundary fence the pin in — same anchoring
# as changie_is_pinned, guarding against 0.22.0 ⊂ 0.22.00.
gopls_is_pinned() {
  command -v gopls >/dev/null 2>&1 || return 1
  gopls version 2>/dev/null | grep -Eq "(^|[^0-9.])${GOPLS_PIN//./\\.}([[:space:]]|\$)"
}

# Echo the directory `go install` drops binaries into: GOBIN when set, otherwise
# the FIRST entry of GOPATH with /bin appended. GOPATH may be a colon-separated
# list and go installs into the first entry's bin, so split on ':' BEFORE
# appending /bin — a naive "$(go env GOPATH)/bin" would yield an invalid
# `path1:path2/bin`. Returns non-zero (and echoes nothing) when the go toolchain
# is absent or GOPATH is empty, so callers must guard `go env` behind this.
go_bin_dir() {
  command -v go >/dev/null 2>&1 || return 1
  local gobin gopath
  gobin="$(go env GOBIN 2>/dev/null)"
  if [ -n "$gobin" ]; then
    printf '%s\n' "$gobin"
    return 0
  fi
  gopath="$(go env GOPATH 2>/dev/null)"
  [ -n "$gopath" ] || return 1
  printf '%s\n' "${gopath%%:*}/bin"
}

# Install gopls from source with `go install` into GOPATH/bin (or GOBIN), pinned
# to GOPLS_PIN. Needs the Go toolchain (present on the base image) and module-
# proxy network access; both the download and go.sum verification are handled by
# `go install`. Idempotent + pin-aware: short-circuit only when the gopls on PATH
# already reports the pin, so a base image shipping a different gopls is replaced
# rather than silently used. Non-fatal — a missing toolchain or offline proxy
# logs a warning and the gopls-lsp plugin simply stays inert this session.
ensure_gopls() {
  local gobin
  # Only consult `go env` when the toolchain exists (go_bin_dir guards that),
  # and prepend the resolved bin dir so an already-installed gopls resolves for
  # the pin check below. A missing toolchain leaves PATH untouched.
  if gobin="$(go_bin_dir)"; then
    export PATH="${gobin}:${PATH}"
  fi
  if gopls_is_pinned; then
    return 0
  fi
  if ! command -v go >/dev/null 2>&1; then
    log "WARNING: go toolchain not found — cannot install gopls (gopls-lsp plugin will be inert)."
    return 1
  fi
  log "Installing gopls ${GOPLS_PIN} via 'go install' (golang.org/x/tools/gopls@v${GOPLS_PIN})…"
  if ! go install "golang.org/x/tools/gopls@v${GOPLS_PIN}" >>"$LOG" 2>&1; then
    log "WARNING: 'go install gopls' failed — the module proxy may be off the network allowlist (see ${LOG})."
    return 1
  fi
  # Honest final signal: confirm the pinned gopls is what now resolves
  # (boundary-aware — the same check as the short-circuit above).
  gopls_is_pinned
}

# python3 + jq are expected on the base image (the registry pipeline scripts and
# the JSON/settings tooling need them). Verify-present; warn but never fail.
ensure_python_jq() {
  command -v python3 >/dev/null 2>&1 \
    || log "WARNING: python3 not found — registry scripts (generate_manifests.py, etc.) will not run."
  command -v jq >/dev/null 2>&1 \
    || log "WARNING: jq not found — JSON/settings tooling and announce-capabilities.sh degrade without it."
}

# pyyaml backs every registry pipeline script. Import-guard first (it is commonly
# already vendored in the base python), then best-effort `pip install --user`.
# PyPI may be off the cloud network allowlist, so a failure here is logged, not
# fatal.
ensure_pyyaml() {
  command -v python3 >/dev/null 2>&1 || return 0
  if python3 -c 'import yaml' >/dev/null 2>&1; then
    return 0
  fi
  log "Installing pyyaml (python3 -c 'import yaml' failed)…"
  if python3 -m pip install --user --quiet pyyaml >>"$LOG" 2>&1; then
    if python3 -c 'import yaml' >/dev/null 2>&1; then
      log "pyyaml installed."
    else
      log "WARNING: pyyaml still not importable after pip install (see ${LOG})."
    fi
  else
    log "WARNING: could not pip install pyyaml — PyPI may be off the network allowlist (see ${LOG})."
  fi
}

# Start the Docker daemon for THIS session.
#
# WHY THIS IS A CLAUDE-CODE-WEB CONCERN: the web runner ships the docker CLI and
# the dockerd binary but NOT a running daemon — and no systemd/service manager to
# start one — unlike a laptop where Docker Desktop or a systemd unit keeps dockerd
# up. So anything that needs containers in a cloud session (devcontainer smoke
# tests, testcontainers, k8s-in-docker, building images) must start dockerd
# itself. The PORTABLE engine deliberately does not (not every repo wants Docker);
# it belongs in this per-session project seam — which is exactly why install-deps.sh
# exposes $SUDO "for the sourced project hook to use when starting daemons (e.g.
# dockerd)".
#
# Idempotent: a quiet no-op when the daemon already answers (a resume, or a base
# image that started it). Non-fatal: a runner lacking the privileges/cgroups to
# run dockerd logs a warning and the session continues without containers.
ensure_docker() {
  command -v dockerd >/dev/null 2>&1 || return 0   # Docker not provisioned here.
  if docker info >/dev/null 2>&1; then
    return 0                                         # Already up.
  fi
  log "Starting Docker daemon (dockerd) for the session…"
  # nohup + background so the daemon outlives this sourced subshell (the parent
  # hook sources us in `( … )`); a reparented-to-init dockerd keeps running for
  # later Bash tool turns. $SUDO is empty when already root, `sudo -n` under an
  # unprivileged remoteUser (e.g. the devcontainer `node` user) — unquoted so
  # `sudo -n` word-splits into argv.
  # shellcheck disable=SC2086  # intentional word-split of $SUDO
  nohup $SUDO dockerd >>"$LOG" 2>&1 &
  # dockerd takes a second or two to create /var/run/docker.sock and listen.
  local i
  for i in $(seq 1 30); do
    if docker info >/dev/null 2>&1; then
      log "Docker daemon ready (Server $(docker version --format '{{.Server.Version}}' 2>/dev/null))."
      return 0
    fi
    sleep 1
  done
  log "WARNING: dockerd did not become ready within 30s — containers unavailable this session (see ${LOG})."
  return 1
}

# --- run -------------------------------------------------------------------
# Make ~/.local/bin resolvable in THIS process (for the installs + the lefthook
# call below) and persist it for later Bash tool shells.
export PATH="${HOME}/.local/bin:${PATH}"

ensure_lefthook || true
ensure_changie  || true
ensure_gopls    || true
ensure_python_jq
ensure_pyyaml
ensure_docker   || true

# Persist ~/.local/bin (lefthook, changie, gh, codex) for subsequent Bash tool
# commands. persist_path is provided by install-deps.sh; guard for standalone runs.
if command -v persist_path >/dev/null 2>&1; then
  persist_path "${HOME}/.local/bin"
  # GOPATH/bin (gopls, and any other `go install`-ed tool) so the gopls-lsp
  # plugin and Bash tool shells resolve gopls in later turns. go_bin_dir handles
  # the missing-toolchain and multi-entry-GOPATH cases.
  if _gobin="$(go_bin_dir)"; then
    persist_path "$_gobin"
    unset _gobin
  fi
fi

# Wire local git hooks so commits made in the session run the same
# pre-commit/pre-push checks as CI. Needs lefthook on PATH and a .git dir.
if command -v lefthook >/dev/null 2>&1; then
  if ( cd "$PROJECT_DIR" && lefthook install ) >>"$LOG" 2>&1; then
    log "Installed lefthook git hooks."
  else
    log "WARNING: 'lefthook install' failed (see ${LOG})."
  fi
else
  log "WARNING: lefthook not on PATH — skipping 'lefthook install'."
fi

# Best-effort fetch of the default branch so changie's merge-base diff (and the
# pre-push fragment gate) resolve on a shallow/single-branch cloud clone.
# --no-tags keeps it cheap; non-fatal when offline or origin is unset.
if command -v git >/dev/null 2>&1 && git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  if git -C "$PROJECT_DIR" fetch --no-tags --quiet origin main >>"$LOG" 2>&1; then
    log "Fetched origin/main (for changie merge-base diffs)."
  else
    log "WARNING: 'git fetch origin main' failed — changie merge-base checks may not resolve (see ${LOG})."
  fi
fi
