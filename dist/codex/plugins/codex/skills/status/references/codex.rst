Codex host execution
====================

This entrypoint runs in Codex. The bundled Node companion is an independent CLI
client, not a named agent. Verify Node.js >=18.18.0 before calling it. Resolve
``PLUGIN_ROOT`` from the installed skill path, not the working directory. Pass
user arguments literally; ``ARGUMENTS`` below is notation, not an injected shell
variable. Use the host shell tool and its background-session support. Never call
Claude's Bash, BashOutput, Agent, or AskUserQuestion tools from Codex.

Run ``node "${PLUGIN_ROOT}/scripts/codex-companion.mjs" status ARGUMENTS``.
Return the actual job status. Do not continuously poll or claim completion when
the job is still running. Use $codex:result for requested completed output.
