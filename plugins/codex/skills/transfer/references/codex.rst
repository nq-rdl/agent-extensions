Codex host execution
====================

This entrypoint runs in Codex. The bundled Node companion is an independent CLI
client, not a named agent. Verify Node.js >=18.18.0 before calling it. Resolve
``PLUGIN_ROOT`` from the installed skill path, not the working directory. Pass
user arguments literally; ``ARGUMENTS`` below is notation, not an injected shell
variable. Use the host shell tool and its background-session support. Never call
Claude's Bash, BashOutput, Agent, or AskUserQuestion tools from Codex.

Import a Claude Code transcript into an independent Codex session only when the
user requests that transfer. Require an explicit --source path to the user's
Claude JSONL transcript. Never pass the current Codex transcript as a Claude
transcript or guess from the current session. The runtime accepts Claude sources
under the user's ~/.claude/projects tree.

Run ``node "${PLUGIN_ROOT}/scripts/codex-companion.mjs" transfer ARGUMENTS`` with
the explicit source and requested flags. Return stdout verbatim. A native Codex
continuation uses its own resume flow, not this import workflow.
