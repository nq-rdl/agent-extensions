Codex host execution
====================

This entrypoint runs in Codex. The bundled Node companion is an independent CLI
client, not a named agent. Verify Node.js >=18.18.0 before calling it. Resolve
``PLUGIN_ROOT`` from the installed skill path, not the working directory. Pass
user arguments literally; ``ARGUMENTS`` below is notation, not an injected shell
variable. Use the host shell tool and its background-session support. Never call
Claude's Bash, BashOutput, Agent, or AskUserQuestion tools from Codex.

Run an independent adversarial review; do not fix the findings. Inspect git
status including untracked files, preserve the user's target and focus. Honor
--wait or --background. Without either flag, ask once whether to wait or use the
host's background shell session. The companion parses flags; the host detaches.

Run ``node "${PLUGIN_ROOT}/scripts/codex-companion.mjs" adversarial-review ARGUMENTS``.
Pass the argument string literally. Return completed stdout verbatim. On a
background launch, report its identity without claiming the review completed.
