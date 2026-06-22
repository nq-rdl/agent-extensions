#!/usr/bin/env bash
#
# web-bootstrap.local.sh — project-specific PER-SESSION provisioning for
# agent-extensions. Sourced by .claude/hooks/web-bootstrap.sh near the end of its
# run (inside the CLAUDE_CODE_REMOTE=true gate), AFTER the portable engine has
# installed gh/codex and persisted PATH.
#
# PLUGINS are provisioned DECLARATIVELY: Claude Code on the web installs the
# plugins declared in .claude/settings.json (extraKnownMarketplaces +
# enabledPlugins) at session start, so this repo ships NO pre-snapshot setup
# script. All project-specific provisioning therefore lives HERE, in the
# per-session hook:
#   * lefthook + changie — installed from CHECKSUM-PINNED GitHub releases into
#     ~/.local/bin (github.com is the reliably-allowlisted source on the cloud
#     sandbox), mirroring web-bootstrap.sh's ensure_gh. They back the local git
#     hooks and the changelog gate, so commits made in a cloud session run the
#     same checks as CI.
#   * python3 / jq / pyyaml — the registry pipeline scripts (generate_manifests.py
#     etc., invoked by the lefthook hooks) need them; verify + best-effort install.
#   * PATH persistence, `lefthook install`, and an origin/main fetch for changie's
#     merge-base diffs.
#
# It shares web-bootstrap.sh's helpers + globals: log(), $LOG, $PROJECT_DIR,
# $SUDO, $CLAUDE_ENV_FILE, persist_path(). Every step is non-fatal — the parent
# hook must always exit 0.

# Defensive fallbacks so the file is lint-clean / inspectable standalone; when
# sourced by web-bootstrap.sh these are already provided and act as no-ops.
if ! command -v log >/dev/null 2>&1; then
  log() { printf '[web-bootstrap.local] %s\n' "$*"; }
fi
: "${LOG:=/dev/null}"
: "${PROJECT_DIR:=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# Pinned tool releases. Update the pin and BOTH per-arch checksums together — the
# SHA-256 values are the upstream-published release checksums (lefthook's
# lefthook_checksums.txt; changie's checksums.txt).
LEFTHOOK_PIN="2.1.9"
LEFTHOOK_SHA256_x86_64="0d60b0d350c923963729574f6431171f0277788884ad0c6284fa0160c36e3877"
LEFTHOOK_SHA256_aarch64="304321997336c450af6b5c0cc641c59141168866fca0b1fc3767e067812600a9"

CHANGIE_PIN="1.24.2"
CHANGIE_SHA256_x86_64="31535a9d8dc548d6d8f315762bfd5b1fba34e707b7600748c8bb8a609649007d"
CHANGIE_SHA256_aarch64="c21bf5509c3cd6e86e0f290b497a12bed52849c40566d171c5d1cbdef19b156c"

# True iff the lefthook on PATH reports EXACTLY the pinned version. `lefthook
# version` prints a bare `X.Y.Z`, so a plain substring grep for the pin would also
# match a longer release (2.1.9 ⊂ 2.1.90), wrongly short-circuiting the install
# onto an unpinned binary. Anchor the pin between line-start (or a non-version
# char) and a trailing whitespace/EOL boundary, dots escaped to match literally —
# mirrors web-bootstrap.sh's codex_is_pinned.
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

# --- run -------------------------------------------------------------------
# Make ~/.local/bin resolvable in THIS process (for the installs + the lefthook
# call below) and persist it for later Bash tool shells.
export PATH="${HOME}/.local/bin:${PATH}"

ensure_lefthook || true
ensure_changie  || true
ensure_python_jq
ensure_pyyaml

# Persist ~/.local/bin (lefthook, changie, gh, codex) for subsequent Bash tool
# commands. persist_path is provided by web-bootstrap.sh; guard for standalone runs.
if command -v persist_path >/dev/null 2>&1; then
  persist_path "${HOME}/.local/bin"
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
