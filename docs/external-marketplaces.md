# External marketplaces

This repo's `rdl-agent-extensions` marketplace ships **only the plugins the team
authors and owns here** (canonical content under `skills/` and `agents/`, packaged
into `plugins/`). Plugins maintained by *other people* — Anthropic, vendors, OSS
projects — are **not** re-hosted, nested, or version-pinned in `rdl-agent-extensions`.

## Policy: external plugins are user-level

A Claude Code marketplace catalogs *plugins*, not other marketplaces — you cannot
nest one inside another, and re-publishing someone else's plugin here would make
**us** own its source and version pin. So external plugins are installed by each
user **from their own upstream marketplaces**, via **user-level** Claude Code
configuration (`~/.claude/settings.json` → `extraKnownMarketplaces` /
`enabledPlugins`). Versioning and auto-update stay with the people who maintain
the plugin; we are not a middleman.

This repo no longer ships a project `.claude/settings.json`, and the previously
curated dev-helper set that it registered for the whole team has been removed
along with the rest of the `.claude/` contributor tooling. A future
`/rdl-team:suggested-plugins` skill is the intended replacement for team-level
recommendations; until then, enable what you want in your own user settings.

## Codex: in-house fork, not the upstream plugin

The `codex` plugin in this marketplace is an **in-house fork** of
`openai/codex-plugin-cc`, modernized for GPT-5.6 (see
[`ARCHITECTURE.md`](ARCHITECTURE.md)). It **supersedes** the upstream
`codex@openai-codex` plugin. If you previously installed that plugin from its
upstream marketplace, **uninstall it** to avoid two plugins registering
duplicate `/codex:*` actions:

```bash
claude plugin uninstall codex@openai-codex
claude plugin install codex@rdl-agent-extensions
```

## Trust

Plugins run with your privileges. Only register marketplaces you trust, and
prefer pinning a vendor `source` to a specific `ref` with `autoUpdate: false`
when you do not want to track its default branch. See the Claude Code docs on
[discovering plugins](https://code.claude.com/docs/en/discover-plugins) and
[plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces).
