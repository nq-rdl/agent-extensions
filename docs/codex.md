---
icon: lucide/bot
---

# Codex

This repository publishes a native Codex marketplace at
`.agents/plugins/marketplace.json`. Codex support is currently a skill-only
pilot for these subject plugins:

- `go`
- `rust`
- `shiny`
- `quarto`
- `obsidian`

The manifest layout follows OpenAI's [plugin packaging guide](https://developers.openai.com/plugins/build/plugins).

## Install

Add the GitHub repository as a marketplace, list its available plugins, and
install a subject:

```bash
codex plugin marketplace add nq-rdl/agent-extensions
codex plugin list --marketplace rdl-agent-extensions --available --json
codex plugin add go@rdl-agent-extensions --json
```

Start a new Codex session after installation. Bundled skills are qualified by
their plugin and leaf names, such as `$go:naming` and `$go:secure`.

To test a branch that has been pushed to GitHub:

```bash
codex plugin marketplace add nq-rdl/agent-extensions --ref <branch-or-sha> --json
```

For a local checkout, use the repository root:

```bash
codex plugin marketplace add "$PWD" --json
```

Contributors can run the isolated local smoke test with:

```bash
scripts/smoke-codex-marketplace.sh
```

CI installs the pinned `@openai/codex@0.152.0` CLI and runs the same test. The
test installs every generated marketplace entry into an isolated `CODEX_HOME`,
then verifies that all 10 pilot skills contribute their qualified names to a
clean session's structured skill input and that a discovered installed copy has
its packaged body.

## Scope

The Codex manifests point at the same self-contained `plugins/<subject>/skills/`
copies used by Claude Code. Current Codex derives a missing skill `name` from
the containing leaf directory and exposes the qualified `<plugin>:<leaf>` name.
This compatibility behavior is covered by the smoke test but is less strict
than the documented Agent Skills and public Plugins Directory requirements.

Claude subagents, Claude hooks, MCP configurations, and apps are not advertised
by the phase-one Codex manifests. Each capability must gain target-specific
validation before its `targets.codex.components` flag can be enabled. Public
OpenAI Plugins Directory submission is also a separate review and publication
process from this repository marketplace.

Codex-enabled skills must also remain host-neutral. CI rejects pilot skills that
depend on `${CLAUDE_PLUGIN_ROOT}`, `AskUserQuestion`, or Claude-style
`/plugin:skill` invocations.
