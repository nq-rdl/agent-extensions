Codex host execution
====================

This entrypoint runs in Codex. The bundled Node companion is an independent CLI
client, not a named agent. Verify Node.js >=18.18.0 before calling it. Resolve
``PLUGIN_ROOT`` from the installed skill path, not the working directory. Pass
user arguments literally; ``ARGUMENTS`` below is notation, not an injected shell
variable. Use the host shell tool and its background-session support. Never call
Claude's Bash, BashOutput, Agent, or AskUserQuestion tools from Codex.

This native skill checks CLI readiness. The stop-time review gate belongs to the
Claude Code integration; its hook is not installed in Codex. If the user supplies
``--enable-review-gate`` or ``--disable-review-gate``, explain that limitation and
stop before running the companion. Do not silently discard those flags or change
the shared Claude gate configuration.

Otherwise run ``node "${PLUGIN_ROOT}/scripts/codex-companion.mjs" setup --json ARGUMENTS``.
Forward supplied readiness options such as ``--cwd`` with literal shell quoting.
If setup reports missing installation or authentication, explain the result and
use the requested setup flow. Do not inspect auth files or print credentials.
A working Codex host does not prove the independent CLI client has the same
authentication. Present the readiness result; explain that ``reviewGateEnabled``
and gate-related ``nextSteps`` describe Claude Code only. For login guidance, use
``codex login`` in a terminal; the ``!`` prefix in companion output is Claude's
shell shortcut. Run setup again with the same readiness options to verify completion.
