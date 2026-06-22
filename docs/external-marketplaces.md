# External marketplaces

This repo's `rdl` marketplace ships **only the plugins the team authors here**
(under `skills/` and `agents/`). Plugins maintained by *other people* —
Anthropic, vendors, OSS projects — are **not** re-hosted in `rdl`. Instead the
team consumes them straight from their **upstream marketplaces**, which Claude
Code registers via the `extraKnownMarketplaces` setting.

## Why not re-host them in `rdl`?

A Claude Code marketplace catalogs *plugins*, not other marketplaces — you
cannot nest one inside another. Re-publishing someone else's plugin into `rdl`
(the old `external:` passthrough, now removed) meant **we** owned its source and
version pin, and had to bump it to deliver upstream updates. Registering the
upstream marketplace instead hands versioning and auto-update back to the people
who actually maintain the plugin. We stop being a middleman.

## The curated set

Registered for the team in [`.claude/settings.json`](../.claude/settings.json).
Each is a real Claude Code marketplace (has `.claude-plugin/marketplace.json`).

| Marketplace (`name`) | Source repo | Plugin | What it's for |
|---|---|---|---|
| `openai-codex` | `openai/codex-plugin-cc` | `codex` | Delegate work to the OpenAI Codex CLI (rescue / second-opinion) |
| `worktrunk` | `max-sixty/worktrunk` | `worktrunk` | Git worktree CLI for parallel agent workflows (the `wt` tooling) |
| `motherduck-skills` | `motherduckdb/agent-skills` | `motherduck-skills` | DuckDB / MotherDuck data skills |
| `astral-sh` | `astral-sh/claude-code-plugins` | `astral` | Astral Python tooling — `ruff`, `uv`, `ty` |
| `goland-claude-marketplace` | `JetBrains/go-modern-guidelines` | `modern-go-guidelines` | Modern Go syntax guidance (complements the `go` bundle) |
| `svelte` | `sveltejs/ai-tools` | `svelte` | Svelte 5 authoring + the Svelte MCP server |

**Anthropic's `pr-review-toolkit`** (six PR-review agents) is *not* in the table
because its marketplace, `claude-plugins-official`, ships with Claude Code and is
auto-available — so it needs no `extraKnownMarketplaces` entry, only an
`enabledPlugins` line.

## How it's wired

- **`extraKnownMarketplaces`** registers each upstream catalog. The key is the
  marketplace's own `name` (so `@<name>` references resolve), and `autoUpdate:
  true` lets Claude Code refresh the catalog and update installed plugins at
  startup.
- **`enabledPlugins`** turns specific plugins on after install, addressed as
  `<plugin>@<marketplace>`. Every third-party marketplace above contains exactly
  one plugin, so all of them are enabled; from the 200+-plugin
  `claude-plugins-official` we enable **only** `pr-review-toolkit`.

```jsonc
// .claude/settings.json (excerpt)
"extraKnownMarketplaces": {
  "svelte": { "source": { "source": "github", "repo": "sveltejs/ai-tools" }, "autoUpdate": true }
},
"enabledPlugins": {
  "svelte@svelte": true,
  "pr-review-toolkit@claude-plugins-official": true
}
```

## Scope: where this applies

`.claude/settings.json` is **project-scoped** — it configures Claude Code when
you are working *inside this repo*. It does not automatically propagate to your
other projects.

To get the same curated set everywhere you use Claude Code, copy the
`extraKnownMarketplaces` / `enabledPlugins` blocks into your **user** settings at
`~/.claude/settings.json`.

## Adding or removing a marketplace

1. Confirm the repo is a marketplace: it must have `.claude-plugin/marketplace.json`.
   Note its `name` and the plugin id(s) you want.
2. Add an `extraKnownMarketplaces["<name>"]` entry with a `github` source and
   `autoUpdate`.
3. Add the `enabledPlugins` line(s) you want on by default (`<plugin>@<name>`).
4. Reload with `/reload-plugins` (or restart) to pick up the change.

## Auto-update and trust

`autoUpdate: true` means Claude Code pulls the latest from each vendor's default
branch at startup. Plugins run with your privileges, so only register
marketplaces you trust. To pin a plugin to a reviewed commit instead, add a
`sha` (and optionally `ref`) to that marketplace's `source` and set
`autoUpdate: false`. See the Claude Code docs on
[discovering plugins](https://code.claude.com/docs/en/discover-plugins) and
[plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces).
