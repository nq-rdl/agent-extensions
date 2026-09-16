---
name: rescue
license: Apache-2.0
description: Forward investigation, an explicit fix request, or follow-up rescue work
  to the Codex companion runtime
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Use the host’s available file, search, shell, and user-question tools for this workflow. Legacy tool names and slash-qualified skill references in supporting references describe capabilities; they do not install those tools. Keep code/configuration examples for another host unchanged when authoring that host’s artifacts.

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Delegation is optional. Read references/subagent.rst only when delegation is useful or requested. It does not install a named agent or grant permissions.

Codex host execution
====================

This entrypoint runs in Codex. The bundled Node companion is an independent CLI
client, not a named agent. Verify Node.js >=18.18.0 before calling it. Resolve
``PLUGIN_ROOT`` from the installed skill path, not the working directory. Pass
user arguments literally; ``ARGUMENTS`` below is notation, not an injected shell
variable. Use the host shell tool and its background-session support. Never call
Claude's Bash, BashOutput, Agent, or AskUserQuestion tools from Codex.

Forward the user's task to an independent Codex CLI session. Preserve explicitly
requested model and effort; leave both unset otherwise. Default to foreground.
Honor --background with the host shell's background support; strip --wait and
--background before calling ``task``. Keep --resume or --fresh if supplied.

Select the task's write scope from the user's request. Add ``--write`` for an
authorized fix, implementation, or other edit request: the runtime defaults to a
read-only sandbox without it. Omit ``--write`` for review, diagnosis, research,
or an explicit read-only request. Continuing a prior thread does not authorize
edits by itself; apply the current request's scope to resumed work too.

Without an explicit choice, run
``node "${PLUGIN_ROOT}/scripts/codex-companion.mjs" task-resume-candidate --json``.
Forward a supplied ``--cwd`` to this candidate lookup as well as the task call.
If a candidate exists, ask whether to continue it or start fresh, then add
``--resume`` or ``--fresh`` for the selected answer. Never silently attach an
unrelated job. Then run
``node "${PLUGIN_ROOT}/scripts/codex-companion.mjs" task ARGUMENTS`` and return its
stdout verbatim. Do not monitor, edit, or add follow-up work to the forwarding step.

Optional delegation: read [references/subagent.rst](references/subagent.rst) only
when the user requests a worker or delegation helps. Use the host's mechanism,
translate tool requirements to available Codex tools, and retain the thin-forwarder
scope. The reference does not register an agent or grant tool permissions.
