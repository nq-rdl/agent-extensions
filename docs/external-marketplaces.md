# External marketplaces

This repo's `rdl-agent-extensions` marketplace ships **only the plugins the team authors here**
(under `skills/` and `agents/`). Plugins maintained by *other people* —
Anthropic, vendors, OSS projects — are **not** re-hosted in `rdl-agent-extensions`. Instead the
team consumes them straight from their **upstream marketplaces**, which Claude
Code registers via the `extraKnownMarketplaces` setting.

## Why not re-host them in `rdl-agent-extensions`?

A Claude Code marketplace catalogs *plugins*, not other marketplaces — you
cannot nest one inside another. Re-publishing someone else's plugin into `rdl-agent-extensions`
(the old `external:` passthrough, now removed) meant **we** owned its source and
version pin, and had to bump it to deliver upstream updates. Registering the
upstream marketplace instead hands versioning and auto-update back to the people
who actually maintain the plugin. We stop being a middleman.

## The curated set

Registered for the team in the project's `.claude/settings.json` (at the repo
root). Each is a real Claude Code marketplace (has
`.claude-plugin/marketplace.json`).

| Marketplace (`name`) | Source repo | Plugin | What it's for |
|---|---|---|---|
| `openai-codex` | `openai/codex-plugin-cc` | `codex` | Delegate work to the OpenAI Codex CLI (rescue / second-opinion) |
| `worktrunk` | `max-sixty/worktrunk` | `worktrunk` | Git worktree CLI for parallel agent workflows (the `wt` tooling) |
| `motherduck-skills` | `motherduckdb/agent-skills` | `motherduck-skills` | DuckDB / MotherDuck data skills |
| `astral-sh` | `astral-sh/claude-code-plugins` | `astral` | Astral Python tooling — `ruff`, `uv`, `ty` |
| `goland-claude-marketplace` | `JetBrains/go-modern-guidelines` | `modern-go-guidelines` | Modern Go syntax guidance (complements the `go` bundle) |
| `svelte` | `sveltejs/ai-tools` | `svelte` | Svelte 5 authoring + the Svelte MCP server |

**Anthropic's `pr-review-toolkit`** (six PR-review agents) is *not* in the table
because it comes from `claude-plugins-official`, the catalog bundled with Claude
Code. That marketplace is auto-available in the desktop/CLI, but on Claude Code
(web) it must be registered explicitly in `extraKnownMarketplaces` for its
enabled plugins (`pr-review-toolkit`, `superpowers`, `gopls-lsp`) to resolve and
install — so it appears in `.claude/settings.json` alongside the curated set.

## How it's wired

- **`extraKnownMarketplaces`** registers each upstream catalog. The key is the
  marketplace's own `name` (so `@<name>` references resolve), and `autoUpdate:
  true` lets Claude Code refresh the catalog and update installed plugins at
  startup.
- **`enabledPlugins`** turns specific plugins on after install, addressed as
  `<plugin>@<marketplace>`. From each third-party marketplace above we enable a
  single plugin (the one listed in the table); from the much larger
  `claude-plugins-official` catalog we enable only the handful we want —
  `pr-review-toolkit`, `superpowers`, and `gopls-lsp` — not the whole set.

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
marketplaces you trust. To stop tracking a vendor's default branch, pin that
marketplace's `source` to a specific branch or tag with `ref` and set
`autoUpdate: false` (exact-commit `sha` pins are documented for individual
plugin sources inside a `marketplace.json`, not for marketplace sources). See
the Claude Code docs on
[discovering plugins](https://code.claude.com/docs/en/discover-plugins) and
[plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces).
