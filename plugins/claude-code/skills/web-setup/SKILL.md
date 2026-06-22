---
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
  declared set **only if** the platform's session-start install didn't complete (the docs'
  *"requires network access to reach the marketplace source"* failure mode). Normally a
  no-op.

`announce-capabilities.sh` (the second SessionStart hook) cross-checks the declared set
against `claude plugin list` and reports **"Enabled plugins (installed)"** vs a
**"⚠️ Declared but NOT installed"** line — so a marketplace-reachability failure is
surfaced, never masked. Keep the chain in mind: **declared ≠ installed ≠ surfaced.**

> **Do NOT add a Setup-script field for plugins.** Earlier revisions of this repo told
> users to set the environment's Setup-script field to `make install-deps`; that was wrong
> (and it hard-blocked session startup on any CWD/branch hiccup). Plugins are declarative —
> the Setup-script field is for caching heavy *packages*, not plugins, and this skill does
> not use it.

## Phase 0 — Confirm context

- Confirm you are at the **repo root** of the repo to bootstrap (a `.git` dir is present).
- Check whether `.claude/settings.json` and `.claude/scripts/` already exist — this decides
  create-fresh vs. merge for each.
- Confirm the **target is not `agent-extensions` itself** (see the anti-pattern note in
  Phase 2).
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

## Phase 2 — Merge `.claude/settings.json`

The template is `assets/settings.json.tmpl`. It registers the **`rdl`** marketplace
(`nq-rdl/agent-extensions`), enables **`rdl@rdl`** (the meta-plugin that installs every RDL
subject plugin), wires the two SessionStart hooks
(`.claude/scripts/install-deps.sh` and `.claude/scripts/announce-capabilities.sh`), and sets
opinionated defaults (`model: opus`, `alwaysThinkingEnabled`, `effortLevel: xhigh`,
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`).

- **If `.claude/settings.json` is absent:** create `.claude/` and write the template verbatim.
- **If it exists:** perform an **idempotent JSON-aware deep-merge** (use `jq` or a careful
  read-modify-write), and **show the diff before writing**:
  - `env`: add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` without clobbering other keys.
  - `hooks.SessionStart`: find (or create) the `startup|resume` matcher group; append the
    two hook commands **only if not already present** (dedupe by exact command string).
  - `enabledPlugins`: add `"rdl@rdl": true` (or specific RDL subjects the repo wants).
  - `extraKnownMarketplaces`: add the `rdl` entry; leave any existing marketplaces intact.
  - `model` / `alwaysThinkingEnabled` / `effortLevel`: set **only if absent** — never
    override a deliberate user choice. Mention they are opinionated defaults.

> **Anti-pattern — never enable a self-referential marketplace in its own dev env.**
> `rdl@rdl` is fine for a *consumer* repo (the platform installs the catalog from a remote
> marketplace). It is **not** fine inside `agent-extensions` itself: there it re-clones the
> repo and fans out to dozens of dependency plugins — and since the docs require the install
> to *reach its marketplace source*, that self-cloning batch breaks the session-start
> install so **nothing** surfaces. If you ever bootstrap the catalog repo itself, declare a
> small set of **external** dev-helper plugins instead.

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
