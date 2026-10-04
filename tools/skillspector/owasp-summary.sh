#!/usr/bin/env bash
#
# Summarise a SARIF report written by scan.sh (SKILLSPECTOR_FORMAT=sarif) as a
# Markdown table of findings per OWASP Agentic Skills Top 10 risk. The CI
# workflow appends the table to the job summary; run it locally on any merged
# report:
#
#   SKILLSPECTOR_FORMAT=sarif SKILLSPECTOR_OUTPUT=skillspector.sarif tools/skillspector/scan.sh
#   tools/skillspector/owasp-summary.sh skillspector.sarif
#
# Counts exclude suppressed results. A risk with no mapped SkillSpector rule
# family is marked "no SkillSpector rule": static scanning cannot evidence it, and
# docs/security-scanning.md records how the repo addresses it instead.
#
# Exit codes: 0 = summary written, 2 = missing jq or unreadable SARIF.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <merged.sarif>" >&2
  exit 2
fi
sarif="$1"
map="$(cd "$(dirname "$0")" && pwd)/owasp-ast10.json"

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required but was not found." >&2
  exit 2
fi
if ! jq -e '.runs[0]' "$sarif" >/dev/null 2>&1; then
  echo "error: $sarif is not a readable SARIF report." >&2
  exit 2
fi

jq -r --slurpfile map "$map" '
  $map[0] as $m
  | [ .runs[].results[]? | select((.suppressions // []) | length == 0)
      | .properties["owasp-ast10"] // "unmapped" ] as $ids
  | ([ $m.families[], $m.rules[] | .risk ] | unique) as $covered
  | def count($id): [ $ids[] | select(. == $id) ] | length;
    "| OWASP risk | Findings |",
    "|---|---|",
    ( $m.risks | to_entries[] | .key as $id
      | "| [\($id) \(.value.name)](\($m.source.pages)/\($id | ascii_downcase)) | "
        + (if any($covered[]; . == $id) then (count($id) | tostring) else "no SkillSpector rule" end)
        + " |" ),
    ( count("unmapped") as $n
      | if $n > 0 then "| Unmapped SkillSpector rules (extend `tools/skillspector/owasp-ast10.json`) | \($n) |" else empty end )
' "$sarif"
