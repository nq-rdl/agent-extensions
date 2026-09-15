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

CI runs the same test with pinned Codex CLI versions `0.152.0` and `0.154.0`. The
test installs every generated marketplace entry into an isolated `CODEX_HOME`,
then verifies that all pilot skills contribute their qualified names to a
clean session's structured skill input. It compares every installed skill tree,
including references, scripts, and assets, against the package, then verifies
that removal clears the cache and discovery and reinstallation restores discovery.

The same required CI job also builds `.devcontainer/codex/Dockerfile` with Codex
`0.154.0` and runs the smoke test inside that image, without networking and with
a read-only checkout. For local commands, see the
[Codex smoke devcontainer](https://github.com/nq-rdl/agent-extensions/tree/main/.devcontainer/codex).

These checks run without an API key and do not execute model requests. For a
manual execution check, install from the branch, start a new authenticated Codex
session, and ask `$go:naming` to review a small Go naming example. Confirm Codex
reads the installed skill and applies its guidance. For a skill with references,
also confirm Codex can read the relevant reference from the installed cache.

Use Codex CLI or the desktop app for plugins. The IDE extension does not currently
support plugin installation; see the [supported surfaces](https://learn.chatgpt.com/docs/plugins).

## Scope

The Codex manifests point at the same self-contained `plugins/<subject>/skills/`
copies used by Claude Code. Current Codex derives a missing skill `name` from
the containing leaf directory and exposes the qualified `<plugin>:<leaf>` name.
This compatibility behavior is covered by the smoke test but is less strict
than the documented Agent Skills and public Plugins Directory requirements.

Claude hooks, MCP configurations, and apps are not advertised
by the phase-one Codex manifests. Each capability must gain target-specific
validation before its `targets.codex.components` flag can be enabled. Public
OpenAI Plugins Directory submission is also a separate review and publication
process from this repository marketplace.

Codex-enabled skills must also remain host-neutral. CI rejects pilot skills that
depend on `${CLAUDE_PLUGIN_ROOT}`, `AskUserQuestion`, or Claude-style
`/plugin:skill` invocations.

## Delegation

Skills may link to `references/subagent.rst` for optional worker execution. Read
that outline when delegation is useful or requested; ordinary skill execution
can stay on the main agent. These references are included in plugin installation
and do not register named custom agents. See [Delegation](delegation.md).

The migration preserves the existing five-bundle pilot. It adds the converted Go
workflows to that already-enabled bundle; other bundles still require a separate
portability check before enabling their Codex target.
