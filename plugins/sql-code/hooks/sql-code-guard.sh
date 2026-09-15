#!/usr/bin/env bash
# PreToolUse guard (sql-code plugin), matcher Write|Edit. Fires only for paths under a
# .sqlreview/ directory; everything else passes silently. Decisions via permissionDecision JSON:
#   reviews/*/review.json, scope.json   Write → content run through `sqlreview.sh check`:
#                                        every assumption/limitation must carry a complete
#                                        confirmation record for the current revision, else deny
#                                        (the violations and the AskUserQuestion step are named)
#                                       Edit  → deny (a fragment cannot be validated; Write the whole file)
#   reviews/*/review.md, scope.md       deny  (rendered from the JSON by `sqlreview.sh render`)
#   config.json                         ask   (config changes go through /sql-code:setup)
#   reviews/*/*.draft.json, explain.json, source.sql, templates/*   pass
# This is an invariant check, not proof that a human answered: it makes "forgot to ask" a denied
# tool call with the offending ids named, and leaves a fabricated confirmation auditable in the
# recorded document. Bash heredocs into .sqlreview/ are out of its reach by design (guardrail, not sandbox).
# The checker is resolved via CLAUDE_PLUGIN_ROOT, then relative to this hook's own plugin copy,
# then the canonical skills/ tree; when none is found the guard DENIES — a missing guardrail must
# not silently pass. JSON in/out via jq, falling back to python3 for the event; neither present,
# or malformed stdin → no-op when a parser is available.
set -u
command -v jq >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1 || {
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"SQL Review guard requires jq; no event parser is available. Install jq before writing."}}'
  exit 0
}
input="$(cat 2>/dev/null)" || exit 0
[ -n "$input" ] || exit 0

field() { # <.dotted.path> → string value from $input, or empty
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$input" | jq -r "$1 // empty" 2>/dev/null
  else
    printf '%s' "$input" | python3 -c 'import json,sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
for k in sys.argv[1].strip(".").split("."):
    d = d.get(k) if isinstance(d, dict) else None
sys.stdout.write(d if isinstance(d, str) else "")' "$1" 2>/dev/null
  fi
}
decide() { # <allow|deny|ask> <reason>
  if command -v jq >/dev/null 2>&1; then
    jq -nc --arg d "$1" --arg r "$2" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:$d,permissionDecisionReason:$r}}'
  else
    python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":sys.argv[1],"permissionDecisionReason":sys.argv[2]}}))' "$1" "$2"
  fi
  exit 0
}

tool="$(field .tool_name)"
case "$tool" in Write|Edit) ;; *) exit 0 ;; esac
path="$(field .tool_input.file_path)"; [ -n "$path" ] || exit 0
cwd="$(field .cwd)"; [ -n "$cwd" ] || cwd="$(pwd -P)"
case "$path" in /*) abs="$path" ;; *) abs="$cwd/$path" ;; esac
# Collapse . and .. without touching the filesystem (the target may not exist yet).
abs="$(printf '%s\n' "$abs" | awk -F/ '{ n=0; for (i=1;i<=NF;i++) { if ($i==""||$i==".") continue; if ($i=="..") { if (n>0) n--; continue }; p[++n]=$i }; o=""; for (i=1;i<=n;i++) o=o "/" p[i]; print (o==""?"/":o) }')"
case "$abs" in
  */.sqlreview/*) rel="${abs##*/.sqlreview/}" ;;
  *) exit 0 ;;
esac

case "$rel" in
  config.json)
    decide ask "Editing .sqlreview/config.json directly bypasses the setup flow. Use /sql-code:setup — on an initialised project it shows the per-file delta and applies only what the human confirms." ;;
  reviews/*/review.md|reviews/*/scope.md)
    decide deny "$rel is rendered markdown — never hand-write it. Update reviews/<slug>/$(basename "${rel%.md}").json (whole-file Write, so the guard can validate it) and re-render: S=\${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts; bash \"\$S/sqlreview.sh\" render <slug> $(basename "${rel%.md}")" ;;
  reviews/*/review.json|reviews/*/scope.json)
    ;;  # validated below
  *) exit 0 ;;
esac

if [ "$tool" = "Edit" ]; then
  decide deny "$rel is an authoritative SQL Review document: it is validated as a whole (every assumption and limitation must carry a confirmation record). Write the complete file instead of an Edit fragment."
fi

here="$(cd "$(dirname "$0")" 2>/dev/null && pwd -P)"
checker=""
for c in "${CLAUDE_PLUGIN_ROOT:-/nonexistent}/skills/setup/scripts/sqlreview.sh" \
         "$here/../skills/setup/scripts/sqlreview.sh" \
         "$here/../skills/sql-code-setup/scripts/sqlreview.sh"; do
  [ -f "$c" ] && { checker="$c"; break; }
done
[ -n "$checker" ] || decide deny "SQL Review guard cannot find sqlreview.sh (looked under \${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/ and next to this hook). The plugin install is incomplete — reinstall sql-code@rdl-agent-extensions before writing $rel."
command -v jq >/dev/null 2>&1 || decide deny "SQL Review documents are validated with jq, which is not installed. Install jq (>= 1.6) before writing $rel."

content="$(field .tool_input.content)"
out="$(printf '%s' "$content" | bash "$checker" check --stdin 2>&1)"; rc=$?
if [ "$rc" -eq 0 ]; then
  expected_slug="${rel#reviews/}"; expected_slug="${expected_slug%/*}"
  expected_kind="$(basename "${rel%.json}")"
  printf '%s' "$content" | jq -e --arg s "$expected_slug" --arg k "$expected_kind" '.slug == $s and .kind == $k' >/dev/null || decide deny "Document slug/kind must match its destination."
  exit 0
fi
decide deny "$rel rejected by sqlreview.sh check: $(printf '%s' "$out" | tr '\n' ';' | sed 's/;$//'). Every assumption and limitation must be put to the human via AskUserQuestion and written with status=confirmed, confirmed_by, confirmed_at and confirmed_revision equal to the document revision. Keep unconfirmed candidates in reviews/<slug>/$(basename "${rel%.json}").draft.json instead."
