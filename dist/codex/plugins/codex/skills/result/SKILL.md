---
name: result
license: Apache-2.0
description: Show the stored final output for a finished Codex job in this repository
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

Run ``node "${PLUGIN_ROOT}/scripts/codex-companion.mjs" result ARGUMENTS`` for
the requested job. Return stdout verbatim. Do not infer success from a running job
or apply findings unless the user separately requests implementation.
