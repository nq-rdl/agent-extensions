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

Execute this workflow only on an explicit user request; preserve its review-only or mutation scope and existing authorization checks.

Codex host execution
====================

This entrypoint runs in Codex. The bundled Node companion is an independent CLI
client, not a named agent. Verify Node.js >=18.18.0 before calling it. Resolve
``PLUGIN_ROOT`` from the installed skill path, not the working directory. Pass
user arguments literally; ``ARGUMENTS`` below is notation, not an injected shell
variable. Use the host shell tool and its background-session support. Never call
Claude's Bash, BashOutput, Agent, or AskUserQuestion tools from Codex.

Read and follow [references/reporting.rst](references/reporting.rst) before
inspecting, drafting, filing, or marking a defect. It is included in this installed
skill and owns the marker-selection, verdict, privacy, draft-approval, and outcome
gates. Use the host user-question tool for required confirmations. Pass a supplied
defect ID literally; use the latest marker only when the user supplied no ID.
