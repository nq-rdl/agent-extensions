---
name: cc-web-setup
license: CC-BY-4.0
description: >-
  Bootstrap a repository for Claude Code on the web — provision its `.claude/`
  setup so cloud sessions are correctly configured. Use when the user wants to
  "set up Claude Code on the web", "bootstrap web sessions", "add the web setup
  scripts", "configure the SessionStart hook for cloud", "provision a cloud
  environment", "install web-bootstrap", or "make this repo work with Claude
  Code on the web". Installs a parameterized `.claude/settings.json` plus
  portable `scripts/web-bootstrap.sh` (SessionStart hook), `scripts/cc-web-setup.sh`
  (pre-snapshot setup script that pre-seeds the RDL marketplace), and
  `scripts/announce-capabilities.sh`. Also covers the setup-script-vs-SessionStart
  split, the `CLAUDE_CODE_REMOTE` gate, GH/Codex CLI provisioning, and the
  `*.local.sh` extension seam for project-specific dependencies.
argument-hint: "Bootstrap this repo for Claude Code on the web? (run from the repo root; say if you have an existing .claude/settings.json to merge)"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Bootstrap a repo for Claude Code on the web

Your job is to provision the current repository so **Claude Code on the web** (cloud)
sessions start correctly configured: the RDL marketplace registered and pre-seeded,
the GitHub and Codex CLIs available, and a SessionStart hook that self-heals and
persists tooling. The portable pieces ship as files in this skill's `assets/`
directory; you copy them into the target repo and merge the settings idempotently.

## Background you must understand before acting

Claude Code on the web has **two** provisioning mechanisms, and this setup uses both:

1. **Setup script** — bash that runs **once, before Claude starts**, whose filesystem
   is captured in the environment snapshot. Configured in the web environment's
   settings UI (not the repo), but the *script it runs* lives in the repo at
   `scripts/cc-web-setup.sh`. The user wires it by setting the environment's **Setup
   script** field to `make cc-web-setup` (or `bash scripts/cc-web-setup.sh`). Plugins
   installed here are available on the **first** session (Claude enumerates skills at
   startup, before any hook runs).
2. **SessionStart hook** — `scripts/web-bootstrap.sh`, runs **every session** (cloud
   *and* local), gated on `CLAUDE_CODE_REMOTE=true` so it is a no-op on a contributor's
   laptop. It self-heals the plugin pre-seed and provisions per-session tooling.

You cannot set the environment Setup-script field for the user (it is not in the repo).
**Tell them** to set it to `make cc-web-setup` after you finish.

## Phase 0 — Confirm context

- Confirm you are at the **repo root** of the repo to bootstrap (a `.git` dir is present).
- Check whether `.claude/settings.json`, `scripts/`, and `Makefile` already exist — this
  decides create-fresh vs. merge for each.
- Ask the user only if something is ambiguous (e.g. a pre-existing `settings.json` with a
  conflicting `model`/`hooks` block). Otherwise proceed with the defaults below.

## Phase 1 — Copy the portable scripts

Copy these three files from this skill's `assets/` into the target repo's `scripts/`,
creating `scripts/` if absent, and `chmod +x` each:

| From (skill asset) | To (target repo) |
|---|---|
| `assets/web-bootstrap.sh` | `scripts/web-bootstrap.sh` |
| `assets/cc-web-setup.sh` | `scripts/cc-web-setup.sh` |
| `assets/announce-capabilities.sh` | `scripts/announce-capabilities.sh` |

These are **portable and carry no project-specific dependencies** — do not edit them per
project. Project specifics go in the optional `*.local.sh` seam (Phase 4).

If a target file already exists and differs, show the diff and ask before overwriting.

## Phase 2 — Merge `.claude/settings.json`

The template is `assets/settings.json.tmpl`. It registers the **`rdl`** marketplace
(`nq-rdl/agent-extensions`), enables **`rdl@rdl`** (the meta-plugin that installs every
RDL subject plugin), wires the two SessionStart hooks, and sets opinionated defaults
(`model: opus`, `alwaysThinkingEnabled`, `effortLevel: xhigh`,
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`).

- **If `.claude/settings.json` is absent:** create `.claude/` and write the template verbatim.
- **If it exists:** perform an **idempotent JSON-aware deep-merge** (use `jq` or a careful
  read-modify-write), and **show the diff before writing**:
  - `env`: add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` without clobbering other keys.
  - `hooks.SessionStart`: find (or create) the `startup|resume` matcher group; append the
    two hook commands **only if not already present** (dedupe by exact command string), so
    re-running is a no-op.
  - `enabledPlugins`: add `"rdl@rdl": true`.
  - `extraKnownMarketplaces`: add the `rdl` entry; leave any existing marketplaces intact.
  - `model` / `alwaysThinkingEnabled` / `effortLevel`: set **only if absent** — never
    override a deliberate user choice. Mention they are opinionated defaults the user can
    decline.
  - If a stale `"superpowers@claude-plugins-official"` (or other migrated-away entry) is
    present, point it out and offer to remove it.

## Phase 3 — Merge the Makefile target

Append `assets/Makefile.snippet` to the repo's `Makefile` **only if** a `cc-web-setup:`
target is not already present. If there is no `Makefile`, create one containing just the
snippet. This gives the user the `make cc-web-setup` entrypoint to set as the environment
Setup script.

## Phase 4 — Offer the project extension seam

The portable scripts source two optional, project-owned hooks if present:
`scripts/cc-web-setup.local.sh` (heavy pre-snapshot deps) and `scripts/web-bootstrap.local.sh`
(per-session glue: language toolchains on PATH, container runtimes, git-hook wiring like
`.husky`/`.githooks`/lefthook, fetching the default branch). This is the **only** sanctioned
place for project-specific provisioning — keep it out of the portable scripts so they stay
re-syncable.

Offer to scaffold a commented `scripts/web-bootstrap.local.sh` from
`assets/web-bootstrap.local.sh.example`. Do **not** create it unless the repo actually needs
project-specific steps.

## Phase 5 — Verify

- Run `CLAUDE_CODE_REMOTE=true bash scripts/web-bootstrap.sh` and confirm it exits 0. (Cloud
  tooling installs may warn if offline — that is fine; the hook must still exit 0.)
- Run `bash scripts/web-bootstrap.sh` (no env var) and confirm it is an immediate no-op.
- Confirm `bash scripts/cc-web-setup.sh` is sentinel-/idempotent — a second run changes nothing.
- Validate `.claude/settings.json` parses (`jq . .claude/settings.json`).

## Phase 6 — Summarize for the user

Tell the user, concisely:
- What was created/merged (list the files + the settings keys touched).
- **The one manual step:** set the web environment's **Setup script** field to
  `make cc-web-setup` so plugin skills are baked into the snapshot and available on the
  first session (otherwise they only appear from the second session onward).
- That `web-bootstrap.sh` is safe locally (no-op unless `CLAUDE_CODE_REMOTE=true`).
- How to add project-specific deps via `scripts/*.local.sh`.
- That Codex CLI provisioning activates only when `CODEX_AUTH_JSON` or `CODEX_ACCESS_TOKEN`
  is set in the environment.
- To commit the new files so cloud sessions (which clone the repo) pick them up.
