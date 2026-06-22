---
license: CC-BY-4.0
description: >-
  Bootstrap a repository for Claude Code on the web — provision its `.claude/`
  setup so cloud sessions start with the team's plugins and tooling. Use when the
  user wants to "set up Claude Code on the web", "bootstrap web sessions", "add
  the web setup scripts", "configure the SessionStart hook for cloud", "provision
  a cloud environment", "install web-bootstrap / install-deps", or "make this repo
  work with Claude Code on the web". Installs a parameterized `.claude/settings.json`
  (declaring the marketplaces + plugins), a portable `.claude/scripts/install-deps.sh`
  engine exposed as `make install-deps`, and `.claude/scripts/announce-capabilities.sh`.
  Covers the pre-snapshot Setup-script field that makes plugins appear on the FIRST
  session, the `--session` SessionStart self-heal, the `CLAUDE_CODE_REMOTE` gate,
  GH/Codex CLI provisioning, and the `*.local.sh` seam for project dependencies.
argument-hint: "Bootstrap this repo for Claude Code on the web? (run from the repo root; say if you have an existing .claude/settings.json to merge)"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Bootstrap a repo for Claude Code on the web

Your job is to provision the current repository so **Claude Code on the web** (cloud)
sessions start correctly configured: the team's marketplace registered and its plugins
installed, the GitHub (and optionally Codex) CLI available, and a SessionStart hook that
self-heals and persists tooling. The portable pieces ship as files in this skill's
`assets/` directory; you copy them into the target repo's `.claude/scripts/` and merge
the settings idempotently.

## Background you must understand before acting

There are **two** facts about Claude Code on the web that this setup is built around.
Get them right and the rest follows.

**1. The platform registers marketplaces, but does NOT install the plugins.**
On a cloud session the platform reads `.claude/settings.json` and registers every
`extraKnownMarketplaces` entry — but it does **not** install the `enabledPlugins` from
them. `enabledPlugins` only *enables* an already-installed plugin; it does not *install*
one. (Verified live on Claude Code 2.1.185: a fresh VM had all marketplaces registered
yet `claude plugin list` empty and no `/<plugin>:<skill>` command in the menu.) So
**something in the repo must run `claude plugin install`** — that is `install-deps.sh`'s
`ensure_plugins`, which reads the declared set straight from `settings.json`.

**2. Claude enumerates skills at startup, BEFORE any SessionStart hook runs.**
So a plugin a hook installs only surfaces its commands on the **next** session. The
plugin cache **does** persist across sessions in an environment, so the hook is enough
from session 2 onward — but to get plugins on the **first** session of a brand-new
environment you must install them **before the snapshot**, via the environment's
**Setup-script field**.

`install-deps.sh` is one engine with **three invocation modes** that cover all of this:

| Invocation | Runs | Purpose |
|---|---|---|
| `make install-deps` (local) | dev toolchain only | a human contributor's machine |
| `CLAUDE_CODE_REMOTE=true make install-deps` | dev toolchain **+ plugin pre-seed + gh/codex** | the **Setup-script field** → **first-session** plugins |
| `install-deps.sh --session` (SessionStart hook) | no-op locally; full on web | **self-heal** + resumes |

`announce-capabilities.sh` (the second SessionStart hook) then cross-checks the declared
set against `claude plugin list` and reports **"Enabled plugins (installed)"** vs a
**"⚠️ Declared but NOT installed"** line — so a failed install is surfaced, never masked.
Remember the chain: **declared ≠ installed ≠ surfaced.**

> **The one manual, non-committable step.** The Setup-script field lives in the web
> environment's settings UI, not the repo, so you cannot set it for the user. After you
> finish, **tell them** to set the environment's **Setup script** field to
> `CLAUDE_CODE_REMOTE=true make install-deps`. Without it, plugins appear only from the
> *second* session (the hook self-heals but can't beat first-session enumeration).

## Phase 0 — Confirm context

- Confirm you are at the **repo root** of the repo to bootstrap (a `.git` dir is present).
- Check whether `.claude/settings.json`, `.claude/scripts/`, and `Makefile` already exist —
  this decides create-fresh vs. merge for each.
- Confirm the **target is not `agent-extensions` itself.** This skill bootstraps *other*
  team repos to consume the catalog; see the anti-pattern note in Phase 2.
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
project. Project specifics go in the optional `install-deps.local.sh` seam (Phase 4).

If a target file already exists and differs, show the diff and ask before overwriting.

## Phase 2 — Merge `.claude/settings.json`

The template is `assets/settings.json.tmpl`. It registers the **`rdl`** marketplace
(`nq-rdl/agent-extensions`), enables **`rdl@rdl`** (the meta-plugin that installs every
RDL subject plugin), wires the two SessionStart hooks
(`.claude/scripts/install-deps.sh --session` and `.claude/scripts/announce-capabilities.sh`),
and sets opinionated defaults (`model: opus`, `alwaysThinkingEnabled`, `effortLevel: xhigh`,
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`).

- **If `.claude/settings.json` is absent:** create `.claude/` and write the template verbatim.
- **If it exists:** perform an **idempotent JSON-aware deep-merge** (use `jq` or a careful
  read-modify-write), and **show the diff before writing**:
  - `env`: add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` without clobbering other keys.
  - `hooks.SessionStart`: find (or create) the `startup|resume` matcher group; append the
    two hook commands **only if not already present** (dedupe by exact command string), so
    re-running is a no-op.
  - `enabledPlugins`: add `"rdl@rdl": true` (or specific RDL subjects the repo wants).
  - `extraKnownMarketplaces`: add the `rdl` entry; leave any existing marketplaces intact.
  - `model` / `alwaysThinkingEnabled` / `effortLevel`: set **only if absent** — never
    override a deliberate user choice. Mention they are opinionated defaults the user can
    decline.

> **Anti-pattern — never enable a self-referential marketplace in its own dev env.**
> `rdl@rdl` is fine for a *consumer* repo (it installs the catalog from a remote
> marketplace). It is **not** fine inside `agent-extensions` itself: there it re-clones
> the repo and fans out to dozens of dependency plugins, which can break the session-start
> install as a whole so that **nothing** surfaces. If you are ever bootstrapping the
> catalog repo itself, declare a small set of **external** dev-helper plugins instead.

## Phase 3 — Merge the Makefile target

Append `assets/Makefile.snippet` to the repo's `Makefile` **only if** an `install-deps:`
target is not already present. If there is no `Makefile`, create one containing just the
snippet. This gives both the human-dev command (`make install-deps`) and the web
Setup-script entrypoint (`CLAUDE_CODE_REMOTE=true make install-deps`).

## Phase 4 — Offer the project extension seam

`install-deps.sh` sources an optional, project-owned `.claude/scripts/install-deps.local.sh`
as its **dev-toolchain** step (run in every mode, before the remote-only web runtime). This
is the **only** sanctioned place for project-specific provisioning — language toolchains on
PATH, container runtimes, git-hook wiring (`.husky`/`.githooks`/lefthook), fetching the
default branch. Keep it out of the portable engine so it stays re-syncable.

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
it is idempotent (a no-op when `docker info` already answers), so it is safe locally too.

This is exactly the kind of **non-plugin, snapshot-relevant** provisioning the Setup-script
path is for. Plugins install declaratively-plus-`ensure_plugins`; heavy deps and daemons
belong here in the project seam.

## Phase 5 — Verify

- `make install-deps` (no env var) → provisions the dev toolchain and prints
  "web runtime skipped". Safe on a contributor's laptop.
- `CLAUDE_CODE_REMOTE=true bash .claude/scripts/install-deps.sh` → runs the full path
  (dev toolchain + gh/codex + `ensure_plugins`) and exits 0. (Cloud tooling installs may
  warn if offline — that is fine; it must still exit 0.)
- `bash .claude/scripts/install-deps.sh --session` (no env var) → an immediate no-op
  (exit 0, no output): the committed hook never disturbs a local session.
- Validate `.claude/settings.json` parses (`jq . .claude/settings.json`).

## Phase 6 — Summarize for the user

Tell the user, concisely:
- What was created/merged (list the files + the settings keys touched).
- **The one manual step:** set the web environment's **Setup script** field to
  `CLAUDE_CODE_REMOTE=true make install-deps`, so the declared plugins are pre-seeded into
  the snapshot *before* Claude enumerates skills — the only way their `/<plugin>:<skill>`
  commands appear on the **first** session of a new environment. Without it they appear
  only from the second session (the SessionStart hook self-heals but can't beat
  first-session enumeration).
- That `make install-deps` is the local-dev command (dev toolchain only; the web runtime
  is gated on `CLAUDE_CODE_REMOTE`).
- That `announce-capabilities.sh` reports **installed** plugins and flags any
  **"Declared but NOT installed"** — the canary if a marketplace was unreachable or an
  install failed.
- That `install-deps.sh --session` is safe locally (no-op unless `CLAUDE_CODE_REMOTE=true`).
- How to add project-specific deps via `.claude/scripts/install-deps.local.sh`.
- That Codex CLI provisioning activates only when `CODEX_AUTH_JSON` or `CODEX_ACCESS_TOKEN`
  is set in the environment.
- To commit the new files so cloud sessions (which clone the repo) pick them up.
