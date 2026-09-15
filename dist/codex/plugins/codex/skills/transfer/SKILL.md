---
name: transfer
license: Apache-2.0
description: Transfer the current Claude Code session into a resumable Codex thread
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

Import a Claude Code transcript into an independent Codex session only when the
user requests that transfer. Require an explicit --source path to the user's
Claude JSONL transcript. Never pass the current Codex transcript as a Claude
transcript or guess from the current session. The runtime accepts Claude sources
under the user's ~/.claude/projects tree.

Run ``node "${PLUGIN_ROOT}/scripts/codex-companion.mjs" transfer ARGUMENTS`` with
the explicit source and requested flags. Return stdout verbatim. A native Codex
continuation uses its own resume flow, not this import workflow.
