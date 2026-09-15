Codex host execution
====================

This entrypoint runs in Codex. The bundled Node companion is an independent CLI
client, not a named agent. Verify Node.js >=18.18.0 before calling it. Resolve
``PLUGIN_ROOT`` from the installed skill path, not the working directory. Pass
user arguments literally; ``ARGUMENTS`` below is notation, not an injected shell
variable. Use the host shell tool and its background-session support. Never call
Claude's Bash, BashOutput, Agent, or AskUserQuestion tools from Codex.

Inspect ``node "${PLUGIN_ROOT}/scripts/codex-defects.mjs" show --latest`` or
``list`` to find the runtime failure. Read the canonical reporting procedure in
this skill's source references only if needed. Prepare a minimal sanitized report
with expected/actual behavior and reproduction. Never include tokens, credentials,
private prompts, or full transcripts. Check existing issues before filing.

File through gh only when the user explicitly requested reporting or approved the
concrete report. After successful publication, mark the defect using
``node "${PLUGIN_ROOT}/scripts/codex-defects.mjs" mark-reported DEFECT_ID --url ISSUE_URL``.
Do not mark a failed or unpublished report as sent.
