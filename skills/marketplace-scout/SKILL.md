---
name: marketplace-scout
description: Discover plugins for a repository during Claude Code setup. Compare live team marketplace catalogs with the project stack and return ranked suggestions. Research only; do not install plugins or edit settings.
license: MIT
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Discover Plugins

Read the team’s tracked marketplace catalog and inspect the repository’s languages and tooling. Verify available plugins against live upstream catalogs and return ranked suggestions with marketplace IDs and reasons. Research only: do not install plugins or edit settings.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the subagent outline,
handoff inputs, execution boundaries, and expected result. Read it when delegating
would help or the user asks to “create a subagent to execute this.” Otherwise,
work directly from this skill; the reference does not need to be loaded.
