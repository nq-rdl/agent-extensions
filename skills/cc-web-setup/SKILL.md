---
name: cc-web-setup
license: CC-BY-4.0
description: >-
  Bootstrap a repository for Claude Code on the web — provision its `.claude/`
  setup so cloud sessions start with the team's plugins and tooling. Use when the
  user wants to "set up Claude Code on the web", "bootstrap web sessions", "add
  the web setup scripts", "configure the SessionStart hook for cloud", "provision
  a cloud environment", or "make this repo work with Claude Code on the web".
  Installs a parameterized `.claude/settings.json` that DECLARES the marketplaces
  and plugins (the platform installs them at session start), plus a portable
  `.claude/scripts/install-deps.sh` SessionStart hook (GH/Codex CLIs, the project
  dev toolchain, a plugin self-heal) and `.claude/scripts/announce-capabilities.sh`.
  Covers the declarative plugin path, the `CLAUDE_CODE_REMOTE` gate, and the
  `install-deps.local.sh` seam for project dependencies (Docker, toolchains).
argument-hint: "Bootstrap this repo for Claude Code on the web? (run from the repo root; say if you have an existing .claude/settings.json to merge)"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Bootstrap a repo for Claude Code on the web

Your job is to provision the current repository so **Claude Code on the web** (cloud)
sessions start correctly configured: the team's marketplace and plugins **declared** so
the platform installs them at session start, the GitHub (and optionally Codex) CLI
available, and a SessionStart hook that provisions project tooling and self-heals. The
portable pieces ship as files in this skill's `assets/` directory; you copy them into the
target repo's `.claude/scripts/` and merge the settings idempotently.

## Background you must understand before acting

**Plugins install declaratively — there is no setup script, no `make`, no manual step.**
Per the [web docs' "what carries over" table](https://code.claude.com/docs/en/claude-code-on-the-web):

> **Plugins declared in `.claude/settings.json`** carry over — *"Installed at session
> start from the marketplace you declared. Requires network access to reach the
> marketplace source."*

So declaring the marketplace under `extraKnownMarketplaces` and the plugin under
`enabledPlugins` is the **whole mechanism** — the platform installs them at session start
and their `/<plugin>:<skill>` commands surface on the first session. The only requirement
is that the marketplace source is reachable (`github.com` is on the default *Trusted*
allowlist).

The `install-deps.sh` **SessionStart hook** this skill installs does **not** drive that
plugin install. It is gated on `CLAUDE_CODE_REMOTE` (a no-op on a contributor's laptop)
and provisions only what the declarative path does not:

- **Per-session CLIs** the base image may lack — `gh` (PR/CI automation) and, when
  `CODEX_AUTH_JSON`/`CODEX_ACCESS_TOKEN` is set, the Codex CLI.
- **The project dev toolchain + services** (language toolchains, the Docker daemon,
  git-hook wiring) via the optional `install-deps.local.sh` seam.
- **A plugin self-heal** (`ensure_plugins`): a cheap, idempotent retry that reinstalls the
  declared set **only if** the platform's session-start install didn't complete. It first
  **registers** the declared marketplaces (`claude plugin marketplace add`) — on a cold VM
  this hook can outrun Claude Code's own registration of `extraKnownMarketplaces`, leaving
  the registry empty, which is a **race**, not the docs' *"requires network access to reach
  the marketplace source"* failure — then refreshes a stale index on a failed install,
  owning the whole add → update → install chain. Gated on a pending count, so a warm resume
  stays a no-op.

`announce-capabilities.sh` (the second SessionStart hook) cross-checks the declared set
against `claude plugin list` and reports **"Enabled plugins (installed)"** vs a
**"⚠️ Declared but NOT installed"** line — so a marketplace-reachability failure is
surfaced, never masked. Keep the chain in mind: **declared ≠ installed ≠ surfaced.**

> **Do NOT add a Setup-script field for plugins.** Earlier revisions of this repo told
> users to set the environment's Setup-script field to `make install-deps`; that was wrong
> (and it hard-blocked session startup on any CWD/branch hiccup). Plugins are declarative —
> the Setup-script field is for caching heavy *packages*, not plugins, and this skill does
> not use it.

> Authoritative platform facts (the web docs' "what carries over" table), the three-layer
> architecture (declarative settings ↔ `install-deps.sh` engine ↔ `install-deps.local.sh`
> project seam), and the hard-won anti-patterns live in
> [`references/web-setup.rst`](references/web-setup.rst). Read it before bootstrapping an
> unfamiliar repo, and to debug a "declared but not installed" plugin.

## Phase 0 — Confirm context

- Confirm you are at the **repo root** of the repo to bootstrap (a `.git` dir is present).
- Check whether `.claude/settings.json` and `.claude/scripts/` already exist — this decides
  create-fresh vs. merge for each.
- **Self-marketplace check.** If the target repo has a `.claude-plugin/marketplace.json`, it
  **is itself a Claude Code marketplace** — enabling a plugin it publishes (e.g. `rdl@rdl`
  inside `nq-rdl/agent-extensions`) installs `main`'s *published* copy into the plugin cache,
  silently **shadowing the working-tree edits** under development. Pick the **externals** base
  (not rdl) in Phase 2; the bundled `web-settings.sh strip-self` enforces this
  deterministically for any marketplace repo, not just this one.
- Ask the user only if something is ambiguous (e.g. a pre-existing `settings.json` with a
  conflicting `model`/`hooks` block). Otherwise proceed with the defaults below.

## Phase 1 — Copy the portable scripts

Copy these two files from this skill's `assets/` into the target repo's `.claude/scripts/`,
creating the directory if absent, and `chmod +x` each:

| From (skill asset) | To (target repo) |
|---|---|
| `assets/install-deps.sh` | `.claude/scripts/install-deps.sh` |
| `assets/announce-capabilities.sh` | `.claude/scripts/announce-capabilities.sh` |

These are **portable and carry no project-specific dependencies** — do not edit them per
project. Project specifics go in the optional `install-deps.local.sh` seam (Phase 3).

If a target file already exists and differs, show the diff and ask before overwriting.

## Phase 2 — Choose a base template and merge `.claude/settings.json`

Two complete templates ship in `assets/`. The skill **composes** the right `enabledPlugins`
on a chosen base and lets the bundled helper `scripts/web-settings.sh` make the marketplace
wiring deterministic — it never concatenates two templates. `web-settings.sh` is a
**setup-time** tool; it is **not** copied into the target repo. It lives in **this skill's
own `scripts/` directory** (the directory this `SKILL.md` is in) — not in the target repo and
not on `PATH` — so the model's cwd (the target repo root) cannot find it by name. Resolve its
absolute path once and reuse it:

```bash
# Resolve this skill's own scripts/ dir. On an installed plugin the skill lives in
# the plugin cache — locate the helper rather than guessing the path:
WS="$(find "$HOME/.claude/plugins" -path '*/web-setup/scripts/web-settings.sh' 2>/dev/null | head -1)"
# Fallback: the absolute path of the scripts/ directory beside this SKILL.md.
WS="${WS:-<absolute path to this skill>/scripts/web-settings.sh}"
```

`strip-self` and `ensure` are **stdout filters** — they print the corrected document and
do **not** edit `.claude/settings.json` in place (so you can review the diff first). Capture
the output to a temp file and move it into place; the `&&` leaves the original untouched if
the guard exits non-zero (e.g. `ensure`'s stop-and-ask on an unknown marketplace), which is
exactly what you want. `cover` is a read-only assertion (no redirect needed).

| Base | File | Use for |
|---|---|---|
| **rdl** | `assets/settings.json.tmpl` | a *consumer* repo that wants the RDL catalog (`rdl@rdl`) |
| **externals** | `assets/settings.externals.json.tmpl` | the team's external dev-helper plugins, **no rdl** — and the **only** correct base when Phase 0 found a `.claude-plugin/marketplace.json` |

Both wire the two SessionStart hooks and the opinionated defaults (`model: opus`,
`alwaysThinkingEnabled`, `effortLevel: xhigh`, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`).

1. **Pick the base** per the table. For *rdl + externals* (a consumer wanting both), start
   from the externals base and add `"rdl@rdl": true` to `enabledPlugins`.
2. **Tailor the external set** from `assets/marketplaces.json` (`teamExternals`) by the
   repo's language: always offer the `agnostic`-tagged (superpowers, pr-review-toolkit,
   codex); add `go`-tagged for a Go repo, `python`-tagged (astral) for Python, `workflow`
   (worktrunk) as desired. Present the menu and let the user confirm — do not silently decide.
3. **Strip self-references (Phase 0 enforcement):**
   ```bash
   tmp="$(mktemp)"
   bash "$WS" strip-self "$PWD" .claude/settings.json > "$tmp" && mv "$tmp" .claude/settings.json
   ```
   Removes any `enabledPlugins`/marketplace that resolves to *this* repo's own
   `.claude-plugin/marketplace.json`; a no-op passthrough when there is none.
4. **Guarantee marketplace coverage (#157):**
   ```bash
   tmp="$(mktemp)"
   bash "$WS" ensure .claude/settings.json > "$tmp" && mv "$tmp" .claude/settings.json
   ```
   Auto-adds every missing-but-known marketplace from `marketplaces.json`. If it exits
   non-zero it printed an **unknown** marketplace to stderr and wrote **nothing** — **stop and
   ask** the user for that marketplace's source, declare it, and re-run. Always keep
   `claude-plugins-official` declared explicitly (auto-known on the local CLI, unreliable on
   the web).

**Merging into an existing `.claude/settings.json`** (idempotent; **show the diff before
writing**):
- `env`: add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` without clobbering other keys.
- `hooks.SessionStart`: find (or create) the `startup|resume` matcher group; append the two
  hook commands **only if not already present** (dedupe by exact command string).
- `enabledPlugins` / `extraKnownMarketplaces`: union the chosen set in, leave existing entries
  intact, then run `strip-self` + `ensure` (steps 3–4) over the merged result.
- `model` / `alwaysThinkingEnabled` / `effortLevel`: set **only if absent** — never override a
  deliberate user choice.

> **Why externals-not-rdl for a marketplace repo.** Enabling `rdl@rdl` inside
> `nq-rdl/agent-extensions` installs `main`'s published catalog into the plugin cache,
> shadowing your working-tree edits, and the self-cloning batch can break the whole
> session-start install so **nothing** surfaces. `strip-self` removes it deterministically;
> the externals base avoids it by construction.

## Phase 3 — Offer the project extension seam

`install-deps.sh` sources an optional, project-owned `.claude/scripts/install-deps.local.sh`
as its **dev-toolchain** step (every web session). This is the **only** sanctioned place for
project-specific provisioning — language toolchains on PATH, container runtimes, git-hook
wiring (`.husky`/`.githooks`/lefthook), fetching the default branch. Keep it out of the
portable engine so it stays re-syncable.

Offer to scaffold a commented `.claude/scripts/install-deps.local.sh` from
`assets/install-deps.local.sh.example`. Do **not** create it unless the repo actually needs
project-specific steps.

### Docker on Claude Code on the web

A web runner is **not** a laptop: it ships the `docker` CLI and the `dockerd` binary but
**no running daemon**, and there is **no systemd / service manager** to start one. So any
repo that needs containers in a web session — devcontainer smoke tests, `testcontainers`,
k3d/k8s-in-docker, building images — **must start `dockerd` itself**, in the
`install-deps.local.sh` seam (the portable engine deliberately does not — not every repo
wants Docker). The pattern is shipped commented in `assets/install-deps.local.sh.example`;
it is idempotent (a no-op when `docker info` already answers). This — heavy deps and
services — is the kind of provisioning the SessionStart hook / project seam is for; plugins
are handled declaratively by the platform.

## Phase 4 — Verify

- `CLAUDE_CODE_REMOTE=true bash .claude/scripts/install-deps.sh` → runs the full hook (dev
  toolchain + gh/codex + the plugin self-heal) and exits 0. (Cloud tooling installs may warn
  if offline — that is fine; it must still exit 0.)
- `bash .claude/scripts/install-deps.sh` (no env var) → an immediate no-op (exit 0, no
  output): the committed hook never disturbs a local session.
- Validate `.claude/settings.json` parses (`jq . .claude/settings.json`).
- **Marketplace coverage (#157):** `bash "$WS" cover .claude/settings.json` (this skill's
  bundled helper — `$WS` from Phase 2, an absolute path) exits 0. Any line it prints is an
  enabled plugin whose marketplace is undeclared — it would install **nothing, silently** —
  so fix Phase 2. This checks *configuration* only; it cannot prove a cloud install succeeded.

## Phase 5 — Summarize for the user

Tell the user, concisely:
- What was created/merged (list the files + the settings keys touched).
- **No manual step is required.** Plugins install declaratively at session start from the
  marketplace declared in `.claude/settings.json` — there is **no Setup-script field to set
  and no `make`**. The marketplace just has to be reachable.
- That `announce-capabilities.sh` reports **installed** plugins and flags any
  **"Declared but NOT installed"** — the canary if a marketplace was unreachable.
- That `install-deps.sh` is safe locally (a no-op unless `CLAUDE_CODE_REMOTE=true`) and on
  the web provisions the gh/Codex CLIs, the project dev toolchain, and a plugin self-heal.
- How to add project-specific deps via `.claude/scripts/install-deps.local.sh`.
- That Codex CLI provisioning activates only when `CODEX_AUTH_JSON` or `CODEX_ACCESS_TOKEN`
  is set in the environment.
- To commit the new files so cloud sessions (which clone the repo) pick them up.
