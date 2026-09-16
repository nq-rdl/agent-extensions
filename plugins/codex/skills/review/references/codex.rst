Codex host execution
====================

This entrypoint runs in Codex. The bundled Node companion is an independent CLI
client, not a named agent. Verify Node.js >=18.18.0 before calling it. Resolve
``PLUGIN_ROOT`` from the installed skill path, not the working directory. Pass
user arguments literally; ``ARGUMENTS`` below is notation, not an injected shell
variable. Use the host shell tool and its background-session support. Never call
Claude's Bash, BashOutput, Agent, or AskUserQuestion tools from Codex.

Run an independent review of local git state. This workflow is review-only:
return the companion's output verbatim; do not apply its fixes.

Inspect git status (including untracked files) and diff size to select working-tree
or branch scope. Preserve the user's --base and --scope arguments. --wait means
foreground; --background means use the host's background shell session. If neither
is supplied, ask once whether to wait or run in background, recommending waiting
only for a clearly tiny review. The companion parses these flags but does not
itself detach the shell process.

Run ``node "${PLUGIN_ROOT}/scripts/codex-companion.mjs" review ARGUMENTS``.
Preserve the user's arguments as one literal argument as required by the companion.
For background runs, report the job/session identity and use $codex:status only on
a requested follow-up. Do not claim completion at launch. Custom review focus,
staged-only or unstaged-only scope requires $codex:adversarial-review.
