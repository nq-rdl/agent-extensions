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
re-scanned, and only surfaces the **next** session. An empty first-session slash menu almost
always means the declarative plugin install didn't land in time.

## The approach: two first-session routes + a best-effort plugin layer

1. **Vendoring (the default).** Commit the chosen skills into `.claude/skills/` and agents into
   `.claude/agents/`. These are *part of the clone* — present before enumeration, with no
   network, git, or marketplace. This is the robust, first-session-reliable path, and the only
   route for the name-reserved `claude-plugins-official` skills.
2. **`bootstrap-web.sh` (opt-in).** For skills a team prefers to pull *fresh* rather than
   commit: a `CLAUDE_CODE_REMOTE`-gated SessionStart hook HTTPS-tarball-fetches the skills
   listed in `.claude/web-skills.json` into `~/.claude/skills/` and returns `reloadSkills: true`
   — the documented same-session pattern. SHA-pinned; skills only (agents must be vendored).
3. **Declarative `enabledPlugins` (best-effort).** When the marketplace is reachable, the
   platform installs declared plugins at session start, giving `/plugin:skill` namespacing and
   `autoUpdate` from **session 2+**. It is *not* the first-session guarantee — routes 1–2 are.
   `announce-capabilities.sh` flags any **"Declared but NOT installed"** plugin so a
   reachability failure is surfaced, never masked.

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
  by `GH_TOKEN`. So vendoring and `bootstrap-web.sh` fetch over **HTTPS** (`api.github.com`
  tarball → `codeload`, both Trusted-allowlisted), never git.
- **No running Docker daemon.** The web runner ships the `docker` CLI and `dockerd` binary but
  no running daemon and no systemd. A repo that needs containers must start `dockerd` itself in
  the `install-deps.local.sh` project seam (an idempotent pattern ships commented in the skill's
  `assets/install-deps.local.sh.example`).

## Setting it up

Run **`/claude-code:web-setup`** from the repo root. It discovers the repo's stack (via the
`marketplace-scout` agent), lets you confirm a plugin/skill set, then vendors the chosen skills
(default) — optionally wiring `bootstrap-web.sh` for fetch-fresh skills — and writes a
`.claude/settings.json` that declares the best-effort plugin layer plus the SessionStart hooks.
The skill's full reference (the platform contract and the hard-won anti-patterns) lives in
`skills/cc-web-setup/references/web-setup.rst`.
