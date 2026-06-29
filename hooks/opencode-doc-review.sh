#!/usr/bin/env bash
# UserPromptSubmit hook (opencode-dev plugin) — nudges canonical-doc verification
# when the user is developing an OpenCode solution.
#
# OpenCode (opencode.ai, SST's open-source coding agent — NOT OpenAI Codex) has a
# young, fast-moving API that predates the model's training cutoff. This hook fires
# only when the prompt mentions OpenCode and injects advisory context steering the
# agent to the opencode-dev skills' verbatim references/ and the live docs before
# writing plugin / agent / config / SDK code. Silent no-op otherwise.
#
# Framing is DECLARATIVE and fenced (<opencode-dev-guidance>) so it reads as
# hook-provided context, not an injected instruction (see AGENTS.md / cc-hook's
# safe-context-injection pattern). Emitted via the UserPromptSubmit
# additionalContext channel (jq); falls back to plain stdout when jq is absent.

set -euo pipefail

input=$(cat)

# Extract the prompt text (jq → python3 → grep), mirroring forced-eval-hook.sh.
if command -v jq >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | jq -r '.prompt // empty')
elif command -v python3 >/dev/null 2>&1; then
  prompt=$(printf '%s' "$input" | python3 -c 'import sys, json; print(json.load(sys.stdin).get("prompt") or "")' 2>/dev/null || true)
else
  prompt=$(printf '%s' "$input" | grep -oP '"prompt"\s*:\s*"\K[^"]+' || true)
fi

# Gate: fire only on OpenCode markers. `\bopencode\b` matches "OpenCode"/"opencode"
# as a token (not "open code"); the path and package markers catch config/SDK work.
# "OpenAI Codex" matches none of these, so the two stay disambiguated.
if ! printf '%s' "$prompt" | grep -qiE '\bopencode\b|\.opencode/|@opencode-ai'; then
  exit 0
fi

read -r -d '' payload <<'CTX' || true
<opencode-dev-guidance>
This prompt looks like OpenCode development work. OpenCode (opencode.ai — SST's
open-source coding agent, NOT OpenAI Codex) has a young API that moves fast and
predates the model's training cutoff, so memory is an unreliable source here.

The opencode-dev plugin ships skills for each surface — invoke the matching one:
  /opencode-dev:plugin    plugins & hooks (the Hooks interface)
  /opencode-dev:sdk       @opencode-ai/sdk, opencode-sdk-go, `opencode serve`
  /opencode-dev:agent     agents, commands, AGENTS.md rules
  /opencode-dev:tools     custom tools, MCP servers, LSP servers
  /opencode-dev:skill     OpenCode Agent Skills + references
  /opencode-dev:policies  experimental.policies + permissions
  /opencode-dev:delegate  drive OpenCode from a Claude Code plugin (ACP/serve/run)

Before writing any plugin / agent / config / SDK code, the reliable path is:
  - load the matching skill and read its references/ (verbatim canonical docs),
  - re-check the cited opencode.ai/docs/<page> for drift,
  - prefer primary sources over recall; record version pins (Go SDK v0.19.2, Go 1.22+).
Advisory only.
</opencode-dev-guidance>
CTX

if command -v jq >/dev/null 2>&1; then
  jq -n --arg ctx "$payload" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $ctx
    }
  }'
else
  printf '%s\n' "$payload"
fi
