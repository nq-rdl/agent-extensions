#!/usr/bin/env bash
#
# Run NVIDIA SkillSpector (https://github.com/NVIDIA/SkillSpector) against the
# repo's skills via Docker. Static analysis only (--no-llm): no API keys,
# deterministic, fast. Used by the lefthook pre-push hook and the GitHub Actions
# backstop, so this script is the single source of truth for the pinned ref,
# image build, and invocation.
#
# SkillSpector treats its directory argument as ONE skill: it reads the SKILL.md
# at that directory's root and emits finding paths relative to it. Scanning
# skills/ as a single directory would therefore give every nested skill an empty
# manifest (no SKILL.md at skills/ root) and emit paths like "bitwarden/SKILL.md"
# instead of "skills/bitwarden/SKILL.md". So we scan each skill directory
# individually and, for SARIF output, prepend the "skills/<name>/" prefix to
# every finding location and merge the findings into a SINGLE SARIF run (the
# CodeQL upload-sarif action rejects multiple runs that share one category).
#
# Env vars:
#   SKILLSPECTOR_REF     SkillSpector git ref to build/pin (default: pinned SHA below).
#   SKILLSPECTOR_FORMAT  Output format: terminal|json|markdown|sarif (default: terminal).
#   SKILLSPECTOR_OUTPUT  Report filename (relative to repo root). When set, the
#                        per-skill reports are combined and written there (SARIF
#                        runs are merged with repository-relative paths).
#   SKILLSPECTOR_SKIP    Set to 1 to skip the scan entirely (escape hatch).
#
# Exit codes: 0 = clean, 1 = a finding (risk_score > 50 for some skill), 2 =
# execution error (missing/failed Docker, or a SkillSpector internal error on
# some skill). Both callers (the CI workflow and the pre-push hook) report
# findings for visibility but do not fail on them — findings surface as
# code-scanning alerts via the CI SARIF upload.
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
FORMAT="${SKILLSPECTOR_FORMAT:-terminal}"

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
SKILLS_DIR="$REPO_ROOT/skills"

# Enumerate the immediate skill directories (those with a SKILL.md), portably
# (no GNU-only `find -printf`, so this also works on macOS).
skills=()
for d in "$SKILLS_DIR"/*/; do
  [ -f "${d}SKILL.md" ] || continue
  skills+=("$(basename "$d")")
done

if [ "${#skills[@]}" -eq 0 ]; then
  echo "skillspector: no skills found under skills/; nothing to scan." >&2
  exit 0
fi

# merge_sarif <outdir> <dest>: combine the per-skill SARIF reports in <outdir>
# into a SARIF document with a SINGLE run at <dest>, prepending each finding's
# location with its "skills/<name>/" prefix (SkillSpector emits paths relative to
# the scanned skill dir, e.g. "SKILL.md"). One run is required: the CodeQL
# upload-sarif action rejects multiple runs that share one category. SkillSpector
# emits no tool.driver.rules and references rules only by ruleId string (no
# ruleIndex), so the results concatenate directly with no rule/index remapping.
# Per-skill files that are not valid SARIF (e.g. an empty report from a failed
# scan) are skipped.
merge_sarif() {
  local outdir="$1" dest="$2"
  local results_acc schema="" version="" tool="" f name
  results_acc="$(mktemp)"
  echo '[]' >"$results_acc"
  for f in "$outdir"/*.report; do
    [ -f "$f" ] || continue
    jq -e '.runs[0]' "$f" >/dev/null 2>&1 || continue # skip non-SARIF/empty reports
    name="$(basename "$f" .report)"
    if [ -z "$schema" ]; then # capture the SARIF envelope + tool from the first run
      schema="$(jq -r '."$schema" // empty' "$f")"
      version="$(jq -r '.version // empty' "$f")"
      tool="$(jq -c '.runs[0].tool' "$f")"
    fi
    # Collect this skill's results, prefixing each relative finding location uri.
    jq --arg p "skills/$name/" '
      [ .runs[].results[]?
        | .locations = ( (.locations // [])
            | map( if (.physicalLocation.artifactLocation.uri | type) == "string"
                   then .physicalLocation.artifactLocation.uri = ($p + .physicalLocation.artifactLocation.uri)
                   else . end ) ) ]' "$f" >"$f.res"
    jq -s '.[0] + .[1]' "$results_acc" "$f.res" >"$results_acc.next"
    mv "$results_acc.next" "$results_acc"
  done
  [ -n "$schema" ] || schema="https://json.schemastore.org/sarif-2.1.0.json"
  [ -n "$version" ] || version="2.1.0"
  [ -n "$tool" ] || tool='{"driver":{"name":"skillspector"}}'
  jq -n --arg schema "$schema" --arg version "$version" \
    --argjson tool "$tool" --slurpfile results "$results_acc" \
    '{ "$schema": $schema, version: $version, runs: [ { tool: $tool, results: $results[0] } ] }' >"$dest"
  rm -f "$results_acc"
}

# Per-skill reports land here (a host temp dir, mounted read-write into the
# container). The repo itself is mounted read-only — we never write into it.
OUTDIR="$(mktemp -d)"
trap 'rm -rf "$OUTDIR"' EXIT

want_output=""
[ -n "${SKILLSPECTOR_OUTPUT:-}" ] && want_output=1

# The SARIF merge runs on the host with jq; fail clearly if it is missing rather
# than aborting mid-merge under `set -e`. (Terminal mode needs no jq.)
if [ -n "$want_output" ] && [ "$FORMAT" = "sarif" ] && ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required to merge the per-skill SARIF reports but was not found." >&2
  exit 2
fi

echo "skillspector: scanning ${#skills[@]} skill(s) individually (static analysis)..." >&2

# Run every per-skill scan inside a single container (avoids one container start
# per skill). The container loops over the skill names passed as positional
# args, scanning each as its own skill root and writing one report per skill to
# /out when an output file is requested. Its exit code is the aggregate: 2 if any
# skill errored, else 1 if any skill had a finding, else 0.
set +e
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -e SS_FMT="$FORMAT" -e SS_WANT_OUTPUT="$want_output" \
  -v "${REPO_ROOT}:/scan:ro" -v "${OUTDIR}:/out" \
  --entrypoint sh "$IMAGE" -c '
    rc=0
    for name in "$@"; do
      if [ -n "$SS_WANT_OUTPUT" ]; then
        skillspector scan "/scan/skills/$name" --no-llm --format "$SS_FMT" --output "/out/$name.report"
      else
        printf "\n===== skills/%s =====\n" "$name"
        skillspector scan "/scan/skills/$name" --no-llm --format "$SS_FMT"
      fi
      s=$?
      if [ "$s" -eq 2 ]; then rc=2; elif [ "$s" -eq 1 ] && [ "$rc" -ne 2 ]; then rc=1; fi
    done
    exit $rc
  ' sh "${skills[@]}"
scan_rc=$?
set -e

# Combine the per-skill reports into the requested output file.
if [ -n "$want_output" ]; then
  out_path="${REPO_ROOT}/${SKILLSPECTOR_OUTPUT}"
  if [ "$FORMAT" = "sarif" ]; then
    merge_sarif "$OUTDIR" "$out_path"
  else
    # Non-SARIF output: concatenate the per-skill reports verbatim.
    : >"$out_path"
    for name in "${skills[@]}"; do
      [ -f "$OUTDIR/$name.report" ] && cat "$OUTDIR/$name.report" >>"$out_path"
    done
  fi
  echo "skillspector: wrote merged report -> ${SKILLSPECTOR_OUTPUT}" >&2
fi

exit "$scan_rc"
