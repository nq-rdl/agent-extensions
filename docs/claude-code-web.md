# Claude Code on the web — how this repo's setup works

[Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web) runs each
session on a fresh, Anthropic-managed VM with **only a clone of your repository**. The goal of
this repo's `cc-web-setup` skill (`/claude-code:web-setup`) is that a cloud session starts with
the team's **skills and slash-commands available on the first session** — not the second.

## The invariant that makes "first session" hard

Skill discovery runs at process startup, **before SessionStart hooks finish**. The hooks
reference states it outright:

> *"Skill discovery normally runs before SessionStart hooks finish, so files the hook writes
> into `~/.claude/skills/` or `.claude/skills/` would otherwise only appear in the next
> session."*

The same-session re-scan, `reloadSkills: true`, re-scans the loose **skill and command
directories** — but **not** the plugin install cache. So a *plugin* installed at session start
(by the platform's declarative install, or by any hook) lands in a cache that won't be
re-scanned, so it can't surface that session — and because the web sandbox is ephemeral (the
next session re-clones fresh), even a later session isn't guaranteed. An empty first-session
slash menu usually means the declarative plugin install didn't land; vendored skills sidestep
the race entirely.

## The approach: vendoring + a best-effort plugin layer

1. **Vendoring (the first-session route).** Commit the chosen skills into `.claude/skills/` and
   agents into `.claude/agents/`. These are *part of the clone* — present before enumeration,
   with no network, git, or marketplace. This is the robust, first-session-reliable path, and
   the only route for the name-reserved `claude-plugins-official` skills.
2. **Declarative `enabledPlugins` (best-effort config).** Declaring a marketplace + plugin is
   how you ask for a plugin that ships real *behavior* (bundled hooks, an MCP server, an LSP) —
   which a loose vendored skill can't provide. But its web activation is **unverified**:
   external marketplaces 403 over the git proxy, the install races skill enumeration on session
   1 (issue #63028), and the sandbox is ephemeral — so even "session 2+" inheritance is
   unproven. Treat it as necessary config for plugin-behavior picks, not a delivery guarantee;
   vendoring is the guarantee. `announce-capabilities.sh` flags any **"Declared but NOT
   installed"** plugin so a reachability failure is surfaced, never masked.

For the rare skill a team can't commit, an advanced HTTPS-fetch **escape hatch** (documented in
the skill's `references/web-setup.rst`) drops it into `~/.claude/skills/` via the same-session
re-scan — trading the first-session guarantee for not committing copies.

## Why there is no plugin self-heal

`install-deps.sh` (the `CLAUDE_CODE_REMOTE`-gated SessionStart hook) provisions per-session
CLIs (`gh`, Codex) and the project dev toolchain — but it **does not install or retry
plugins**. An earlier `ensure_plugins` self-heal was removed because it could not help:

- A hook-installed plugin lands in the plugin cache that `reloadSkills` does not re-scan, and a
  hook cannot call `/reload-plugins` (disabled in cloud), so it can't surface the same session.
- `claude plugin install` inside a SessionStart hook has been reported to **hang** web sessions
  ([anthropics/claude-code#18088](https://github.com/anthropics/claude-code/issues/18088)).

First-session availability comes from vendoring, not a retry hook.

## Two constraints worth knowing

- **The GitHub git proxy is repo-scoped.** In a cloud session, `git clone` of any repo *other
  than the session's own* returns 403 — independent of the network-access level and unaffected
  by `GH_TOKEN`. So vendoring (and the escape-hatch fetch) use **HTTPS** (`api.github.com`
  tarball → `codeload`, both Trusted-allowlisted), never git.
- **No running Docker daemon.** The web runner ships the `docker` CLI and `dockerd` binary but
  no running daemon and no systemd. A repo that needs containers must start `dockerd` itself in
  the `install-deps.local.sh` project seam (an idempotent pattern ships commented in the skill's
  `assets/install-deps.local.sh.example`).

## Setting it up

Run **`/claude-code:web-setup`** from the repo root. It discovers the repo's stack (via the
`marketplace-scout` agent), lets you confirm a plugin/skill set, then vendors the chosen skills
into `.claude/` and writes a `.claude/settings.json` that declares the best-effort plugin layer
plus the SessionStart hooks.
The skill's full reference (the platform contract and the hard-won anti-patterns) lives in
`skills/cc-web-setup/references/web-setup.rst`.
