---
name: report-defect
license: Apache-2.0
description: Review a recorded Codex plugin defect marker and decide whether to file
  it against nq-rdl/agent-extensions
disable-model-invocation: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Use the host’s available file, search, shell, and user-question tools for this workflow. Legacy tool names and slash-qualified skill references in supporting references describe capabilities; they do not install those tools. Keep code/configuration examples for another host unchanged when authoring that host’s artifacts.

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Execute this workflow only on an explicit user request; preserve its review-only or mutation scope and existing authorization checks.

Codex host execution
====================

This entrypoint runs in Codex. The bundled Node companion is an independent CLI
client, not a named agent. Verify Node.js >=18.18.0 before calling it. Resolve
``PLUGIN_ROOT`` from the installed skill path, not the working directory. Pass
user arguments literally; ``ARGUMENTS`` below is notation, not an injected shell
variable. Use the host shell tool and its background-session support. Never call
Claude's Bash, BashOutput, Agent, or the host user-question tool tools from Codex.

Inspect ``node "${PLUGIN_ROOT}/scripts/codex-defects.mjs" show --latest`` or
``list`` to find the runtime failure. Read the canonical reporting procedure in
this skill's source references only if needed. Prepare a minimal sanitized report
with expected/actual behavior and reproduction. Never include tokens, credentials,
private prompts, or full transcripts. Check existing issues before filing.

File through gh only when the user explicitly requested reporting or approved the
concrete report. After successful publication, mark the defect using
``node "${PLUGIN_ROOT}/scripts/codex-defects.mjs" mark-reported DEFECT_ID --url ISSUE_URL``.
Do not mark a failed or unpublished report as sent.
