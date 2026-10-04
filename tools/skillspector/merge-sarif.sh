#!/usr/bin/env bash
#
# Usage: merge-sarif.sh <outdir> <dest>
#
# Combine the per-skill SARIF reports (<outdir>/<skill>.report) written by
# scan.sh into a SARIF document with a SINGLE run at <dest>, prepending each finding's
# location with its "skills/<name>/" prefix (SkillSpector emits paths relative to
# the scanned skill dir, e.g. "SKILL.md"). One run is required: the CodeQL
# upload-sarif action rejects multiple runs that share one category.
# SkillSpector references rules only by ruleId string (no ruleIndex), so results
# concatenate directly; the per-skill tool.driver.rules are unioned by id.
# Every result is also downgraded to SARIF level "note" so the code-scanning PR
# check GitHub auto-creates from the upload never gates the PR (see the inline
# comment at the result-collection step below). Per-skill files that are not
# valid SARIF (e.g. an empty report from a failed scan) are skipped.
#
# Each rule and result is also classified against the OWASP Agentic Skills Top
# 10 using owasp-ast10.json (exact rule id first, then the id's family prefix):
# results gain properties["owasp-ast10"] (e.g. "AST03", or "unmapped") and an
# "owasp-ast10/<id>" tag; rules gain the same tag and a helpUri to the OWASP
# risk page, so code scanning can filter alerts by OWASP risk.
#
# The merged run keeps the scanner's columnKind (SkillSpector reports columns in
# Unicode code points; SARIF otherwise assumes UTF-16 code units) and every
# skill's invocations, tagged with properties.skill and with notification
# locations prefixed like findings. Invocations carry executionSuccessful,
# analysisCompleteness and the warnings for files that were only partially
# inspected, which owasp-summary.sh reports.
#
# Called by scan.sh; standalone so the merge and OWASP classification are
# unit-tested without Docker (tests/test_skillspector_owasp.py). Needs jq.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <outdir> <dest>" >&2
  exit 2
fi
OWASP_MAP="$(cd "$(dirname "$0")" && pwd)/owasp-ast10.json"
outdir="$1" dest="$2"
schema="" version="" tool=""
parts="$(mktemp)"
trap 'rm -f "$parts"' EXIT
for f in "$outdir"/*.report; do
  [ -f "$f" ] || continue
  jq -e '.runs[0]' "$f" >/dev/null 2>&1 || continue # skip non-SARIF/empty reports
  name="$(basename "$f" .report)"
  if [ -z "$schema" ]; then # capture the SARIF envelope + tool from the first run
    schema="$(jq -r '."$schema" // empty' "$f")"
    version="$(jq -r '.version // empty' "$f")"
    tool="$(jq -c '.runs[0].tool' "$f")"
  fi
  # Collect this skill's rules and results, prefixing each relative finding
  # location uri and downgrading every result to SARIF level "note". The
  # downgrade is what actually keeps SkillSpector non-gating: uploading the
  # SARIF makes GitHub code scanning auto-create a separate PR check (named
  # "skillspector", owned by the GitHub Advanced Security app) that fails on any
  # *new* "error"-level alert — independent of this workflow's own
  # continue-on-error / informational summary. Emitting every finding at "note"
  # keeps them visible in the Security tab (category "skillspector") as
  # informational alerts without failing the PR check. Real per-skill severity
  # is still surfaced by the terminal scan (the lefthook pre-push hook) and
  # reflected in this script's aggregate exit code.
  jq -c --arg p "skills/$name/" --arg skill "$name" '
    def prefixed: (. // [])
      | map( if (.physicalLocation.artifactLocation.uri | type) == "string"
             then .physicalLocation.artifactLocation.uri = ($p + .physicalLocation.artifactLocation.uri)
             else . end );
    {
    columnKind: ([ .runs[].columnKind // empty ] | first),
    rules: [ .runs[].tool.driver.rules[]? ],
    results: [ .runs[].results[]?
      | .level = "note"
      | .locations |= prefixed ],
    invocations: [ .runs[].invocations[]?
      | .properties = ((.properties // {}) + { skill: $skill })
      | if .toolExecutionNotifications
        then .toolExecutionNotifications |= map(if .locations then .locations |= prefixed else . end)
        else . end ] }' "$f" >>"$parts"
done
[ -n "$schema" ] || schema="https://json.schemastore.org/sarif-2.1.0.json"
[ -n "$version" ] || version="2.1.0"
[ -n "$tool" ] || tool='{"driver":{"name":"skillspector"}}'
jq -n --arg schema "$schema" --arg version "$version" \
  --argjson tool "$tool" --slurpfile parts "$parts" --slurpfile map "$OWASP_MAP" '
  $map[0] as $m
  | def owasp($id):
      ($m.rules[$id] // $m.families[$id | sub("[0-9]+$"; "")]) as $hit
      | if $hit then $hit.risk else "unmapped" end;
    def tagged($risk): ((.properties.tags // []) + ["owasp-ast10/" + $risk]) | unique;
  ([ $parts[].results[] ] | map(owasp(.ruleId) as $r
      | .properties = ((.properties // {}) + { "owasp-ast10": $r })
      | .properties.tags = tagged($r))) as $results
  # Union declared rule descriptors with a stub for every ruleId a result
  # uses, so each referenced rule carries its OWASP tag.
  | ([ $parts[].rules[] ] + [ $results[] | { id: .ruleId } ]
      | group_by(.id) | map(add)
      | map(owasp(.id) as $r
          | .properties.tags = tagged($r)
          | if $r == "unmapped" then .
            else .helpUri = ($m.source.pages + "/" + ($r | ascii_downcase)) end)) as $rules
  | ([ $parts[].columnKind // empty ] | first) as $columnKind
  | { "$schema": $schema, version: $version,
      runs: [ { tool: ($tool | .driver.rules = $rules), results: $results }
              + (if $columnKind then { columnKind: $columnKind } else {} end)
              + { invocations: [ $parts[].invocations[] ] } ] }' >"$dest"
