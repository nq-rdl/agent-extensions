#!/usr/bin/env bash
#
# Run NVIDIA SkillSpector (https://github.com/NVIDIA/SkillSpector) against the
# repo's skills via Docker. Static analysis only (--no-llm): no API keys,
# deterministic, fast. Used by the lefthook pre-push hook and the GitHub Actions
# backstop, so this script is the single source of truth for the pinned ref,
# image build, and invocation.
#
# Env vars:
#   SKILLSPECTOR_REF     SkillSpector git ref to build/pin (default: pinned SHA below).
#   SKILLSPECTOR_FORMAT  Output format: terminal|json|markdown|sarif (default: terminal).
#   SKILLSPECTOR_OUTPUT  Report filename (relative to repo root). When set, the
#                        workspace is mounted read-write so the report can be written.
#   SKILLSPECTOR_SKIP    Set to 1 to skip the scan entirely (escape hatch).
#
# Exit codes: 0 = clean, 1 = risk_score > 50 (a finding), 2 = execution error
# (missing/failed Docker, or a SkillSpector internal error). Both callers (the CI
# workflow and the pre-push hook) report findings for visibility but do not fail
# on them — findings surface as code-scanning alerts via the CI SARIF upload.
set -euo pipefail

# Pinned for reproducible, supply-chain-safe scans. No upstream release tags
# exist, so we pin to a commit SHA. Bump this (or override via SKILLSPECTOR_REF)
# to upgrade.
SKILLSPECTOR_REF="${SKILLSPECTOR_REF:-a5092dd9b9521ff57a9b53612bb129ce78019002}"
# Docker tags allow only [A-Za-z0-9_.-] and must not start with '.' or '-'; a
# branch ref like "feature/foo" would otherwise produce an invalid tag. Derive a
# sanitized tag from the ref (the unmodified ref is still used for the git build
# URL below).
SKILLSPECTOR_TAG="$(printf '%s' "$SKILLSPECTOR_REF" | tr -c 'A-Za-z0-9_.-' '-' | sed 's/^[.-]*//')"
IMAGE="skillspector:${SKILLSPECTOR_TAG:-pinned}"

if [ "${SKILLSPECTOR_SKIP:-0}" = "1" ]; then
  echo "skillspector: SKILLSPECTOR_SKIP=1 set; skipping scan."
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required for the SkillSpector check but was not found." >&2
  echo "  install Docker, or set SKILLSPECTOR_SKIP=1 to bypass (not recommended)." >&2
  exit 2
fi

# Build the pinned image once; reuse the cache on subsequent runs. A build
# failure is an execution error (exit 2), not a finding, so don't let
# `set -e` propagate docker's exit 1 and trip the CI gate's finding branch.
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "skillspector: building image $IMAGE (one-time)..." >&2
  if ! docker build -t "$IMAGE" \
    "https://github.com/NVIDIA/SkillSpector.git#${SKILLSPECTOR_REF}" >&2; then
    echo "error: failed to build the SkillSpector image." >&2
    exit 2
  fi
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"

args=(scan /scan/skills --no-llm --format "${SKILLSPECTOR_FORMAT:-terminal}")

if [ -n "${SKILLSPECTOR_OUTPUT:-}" ]; then
  # Need to write the report into the workspace: mount read-write. Run as the host
  # user (with a writable HOME) so the report isn't left root-owned on the host.
  echo "skillspector: scanning skills/ (-> ${SKILLSPECTOR_OUTPUT})..." >&2
  args+=(--output "/scan/${SKILLSPECTOR_OUTPUT}")
  exec docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
    -v "${REPO_ROOT}:/scan" "$IMAGE" "${args[@]}"
else
  echo "skillspector: scanning skills/ (static analysis)..." >&2
  exec docker run --rm -v "${REPO_ROOT}:/scan:ro" "$IMAGE" "${args[@]}"
fi
