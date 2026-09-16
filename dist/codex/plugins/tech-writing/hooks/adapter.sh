#!/usr/bin/env bash
# Native Codex event adapter for canonical command hooks. No network/model calls.
set -euo pipefail
mode="${1:?hook mode required}"
root="${PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd -P)}"
# Only the adapter translates the legacy implementation's private environment.
export CLAUDE_PLUGIN_ROOT="$root"
if ! command -v jq >/dev/null 2>&1; then
  case "$mode" in
    redhat-docs-guard|data-request-guard)
      printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"This guard requires jq >=1.6. Install jq before retrying."}}' ;;
  esac
  exit 0
fi
input="$(cat)"
printf '%s' "$input" | jq -e 'type == "object"' >/dev/null 2>&1 || exit 0
event="$(jq -r '.hook_event_name // empty' <<<"$input")"
tool="$(jq -r '.tool_name // empty' <<<"$input")"
context() {
  jq -nc --arg e "$event" --arg c "$1" '{hookSpecificOutput:{hookEventName:$e,additionalContext:$c}}'
}
deny() {
  jq -nc --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
}
case "$tool" in
  exec_command|shell_command|shell)
    input="$(jq '.tool_name="Bash" | .tool_input.command=(.tool_input.command // .tool_input.cmd // "")' <<<"$input")" ;;
esac
case "$mode" in
  codex-context)
    [ "$event" = SessionStart ] || exit 0
    context 'Codex companion workflows run independent CLI jobs. Use $codex:review or $codex:rescue only when requested. Claude transcript import requires an explicit Claude JSONL source; Codex sessions are not Claude transcripts. The Claude lifecycle/automatic stop-review hooks are not installed in this native package.'
    exit 0 ;;
  stylepedia-reminder)
    [ "$event" = UserPromptSubmit ] || exit 0
    prompt="$(jq -r '.prompt // ""' <<<"$input")"
    [[ "$prompt" =~ (tech-writing:copyedit|tech-writing:author|tech-writing-copyedit) ]] || exit 0
    context 'For technical writing, consult https://stylepedia.net/style/#part-Writing_Style_Guide and the installed house-style references. Review the actual changed prose against the simplified STE profile before completion. This is an advisory reminder; Codex does not execute Claude agent review hooks.'
    exit 0 ;;
  skill-audit-nudge)
    if [ "$tool" = apply_patch ]; then
      patch="$(jq -r '.tool_input.command // .tool_input.patch // ""' <<<"$input")"
      if printf '%s\n' "$patch" | grep -Eq '^\*\*\* (Add|Update|Delete) File: (.*\/)?skills/[^/]+/SKILL\.md$'; then
        context 'A skill entrypoint changed. Consider $claude-code:skill-audit; preserve canonical skills and optional references/subagent.rst. No standalone agents are published.'
      fi
      exit 0
    fi ;;
  data-request-guard)
    if [ "$tool" = apply_patch ]; then
      patch="$(jq -r '.tool_input.command // .tool_input.patch // ""' <<<"$input")"
      # Only paths in patch headers count: prose/content mentioning .sqlreview is inert.
      paths="$(printf '%s\n' "$patch" | sed -nE 's/^\*\*\* (Add File|Update File|Delete File|Move to): //p')"
      while IFS= read -r path; do
        [ -n "$path" ] || continue
        path="$(printf '%s\n' "$path" | awk -F/ '{n=0; for(i=1;i<=NF;i++){if($i==""||$i==".")continue;if($i==".."){if(n>0)n--;continue}p[++n]=$i}for(i=1;i<=n;i++)printf "%s%s",(i>1?"/":""),p[i];print ""}')"
        case "/$path" in
          */.sqlreview/config.json|*/.sqlreview/reviews/*/review.json|*/.sqlreview/reviews/*/scope.json|*/.sqlreview/reviews/*/review.md|*/.sqlreview/reviews/*/scope.md)
            deny 'Authoritative SQL review files require whole-document validation. Write a confirmed draft, then run bash "${PLUGIN_ROOT}/skills/setup/scripts/sqlreview.sh" publish <slug> <scope|review> <draft-path>; this validates a staged copy before atomic replacement. Run the same helper with render <slug> <scope|review> for Markdown. Config changes use $data-request:setup. This patch guard does not intercept shell writes.'
            exit 0 ;;
        esac
      done <<<"$paths"
      exit 0
    fi ;;
esac
case "$mode" in
  redhat-docs-preflight|redhat-docs-guard|data-request-preflight|data-request-guard|skill-audit-nudge|opencode-doc-review|speckit-publish-target) ;;
  *) printf 'Unknown Codex hook mode: %s\n' "$mode" >&2; exit 1 ;;
esac
output="$(printf '%s' "$input" | bash "$root/hooks/$mode.sh")"
[ -n "$output" ] || exit 0
# Codex parses `ask` but continues the call on failure. Convert it to a denial
# with an actionable sanctioned path, never silently to allow.
if printf '%s' "$output" | jq -e 'type=="object"' >/dev/null 2>&1; then
  printf '%s' "$output" | jq '
    if .hookSpecificOutput.permissionDecision == "ask" then .hookSpecificOutput.permissionDecision="deny" else . end
    | walk(if type=="string" then
        gsub("/(?<plugin>redhat|data-request|claude-code|opencode-dev|speckit-dev):"; "$" + .plugin + ":")
        | gsub("AskUserQuestion"; "the host user-question tool")
      else . end)' 
else
  context "$output"
fi
