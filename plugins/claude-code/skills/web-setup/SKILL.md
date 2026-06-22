---
license: CC-BY-4.0
description: >-
  Bootstrap a repository for Claude Code on the web — provision its `.claude/`
  setup so cloud sessions are correctly configured. Use when the user wants to
  "set up Claude Code on the web", "bootstrap web sessions", "add the web setup
  scripts", "configure the SessionStart hook for cloud", "provision a cloud
  environment", "install web-bootstrap", or "make this repo work with Claude
  Code on the web". Provisions a declarative `.claude/settings.json`
  (`extraKnownMarketplaces` + `enabledPlugins` install plugins at session start in
  the cloud) plus portable `scripts/web-bootstrap.sh` (SessionStart hook),
  `scripts/announce-capabilities.sh`, and an optional `scripts/cc-web-setup.sh`
  setup script for baking heavy non-plugin deps into the snapshot. Guards that
  every enabled plugin's `@marketplace` is declared, warns when the repo is itself
  a marketplace, and covers the `CLAUDE_CODE_REMOTE` gate, GH/Codex CLI
  provisioning, and the `*.local.sh` extension seams.
argument-hint: "Bootstrap this repo for Claude Code on the web? (run from the repo root; say if you have an existing .claude/settings.json to merge)"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Bootstrap a repo for Claude Code on the web

Your job is to provision the current repository so **Claude Code on the web** (cloud)
sessions start correctly configured: plugins declared so their skills are available on
the first session, the GitHub and Codex CLIs available, and a SessionStart hook that
persists tooling. The portable pieces ship as files in this skill's `assets/`
directory; you copy them into the target repo and merge the settings idempotently.

## Background you must understand before acting

**Plugins are provisioned declaratively — no setup script needed.** Plugins declared in
`.claude/settings.json` (`extraKnownMarketplaces` + `enabledPlugins`) are installed by
Claude Code **at session start in the cloud**, over the default-Trusted github.com, so
their skills are available on the **first** session. This is the primary mechanism and
the default path of this skill (Phase 2). Do **not** reach for an imperative
`claude plugin install` step to get session-1 skills — the declarative settings already
deliver that.

Two provisioning mechanisms remain, both for **non-plugin** concerns:

1. **SessionStart hook** — `scripts/web-bootstrap.sh`, runs **every session** (cloud
   *and* local), gated on `CLAUDE_CODE_REMOTE=true` so it is a no-op on a contributor's
   laptop. It provisions per-session tooling a snapshot cannot carry (the GitHub CLI and
   the Codex CLI) and sources an optional project hook.
2. **Setup script (OPTIONAL)** — `scripts/cc-web-setup.sh`, bash that runs **once, before
   Claude starts**, whose filesystem is captured in the environment snapshot. It is **not**
   for plugins. Its only job is to bake **heavy, non-plugin dependencies** (language
   toolchains, container runtimes, large caches) into the snapshot once — a latency
   optimization over fetching them every session. A repo with no such deps does not need
   to wire it at all. When a repo does want it, the user sets the environment's **Setup
   script** field (in the web settings UI, not the repo) to `make cc-web-setup`.

You cannot set the environment Setup-script field for the user (it is not in the repo).
Mention it only if the repo actually has heavy pre-snapshot deps.

### Caveat: `announce-capabilities.sh` reports *configured*, not *installed*

`scripts/announce-capabilities.sh` lists the `enabledPlugins` from `settings.json` as
*configured* plugins — it cannot confirm they actually installed. A plugin whose
`@marketplace` is missing from `extraKnownMarketplaces` installs **nothing, silently**
(no error), yet would still be announced. The Phase 2 marketplace-consistency guard
below exists to prevent exactly that.

## Phase 0 — Confirm context

- Confirm you are at the **repo root** of the repo to bootstrap (a `.git` dir is present).
- Check whether `.claude/settings.json`, `scripts/`, and `Makefile` already exist — this
  decides create-fresh vs. merge for each.
- **Self-marketplace detection.** Check for `.claude-plugin/marketplace.json` at the repo
  root. If present, the repo **is itself a Claude Code marketplace** — parse its
  marketplace `name` and the `name` of each plugin it publishes. Any plugin the template
  would enable that resolves to **this** repo (e.g. `rdl@rdl` inside
  `nq-rdl/agent-extensions`) is a **self-reference**: enabling it installs `main`'s
  *published* copy of those skills into the plugin cache, which **shadows the working-tree
  edits under development** (a session would run the released skill, not your branch).
  When self-references exist:
  - **Warn** the user explicitly about the working-tree-shadowing risk.
  - **Auto-omit** every self-referencing `name@marketplace` from `enabledPlugins`, and
    drop that marketplace from `extraKnownMarketplaces` if nothing else needs it. Inside
    `nq-rdl/agent-extensions` the correct result is **no `rdl@rdl` and no `rdl` entry**.
  - Then ask **only** whether to enable any remaining **known external** plugins (do not
    pose an open-ended "which plugins?"). Carry this filtered set into Phase 2.
- Ask the user only if something else is ambiguous (e.g. a pre-existing `settings.json`
  with a conflicting `model`/`hooks` block). Otherwise proceed with the defaults below.

## Phase 1 — Copy the portable scripts

Copy these files from this skill's `assets/` into the target repo's `scripts/`,
creating `scripts/` if absent, and `chmod +x` each:

| From (skill asset) | To (target repo) | Purpose |
|---|---|---|
| `assets/web-bootstrap.sh` | `scripts/web-bootstrap.sh` | SessionStart hook (gh/Codex CLI, every session) |
| `assets/announce-capabilities.sh` | `scripts/announce-capabilities.sh` | SessionStart hook (capability banner) |
| `assets/cc-web-setup.sh` | `scripts/cc-web-setup.sh` | **Optional** one-time setup script (heavy non-plugin deps only) |

`cc-web-setup.sh` does **no** plugin work — it only sources the optional
`scripts/cc-web-setup.local.sh`. Copy it so the snapshot-baking seam is available, but it
is wired (via `make cc-web-setup`) only if the repo has heavy pre-snapshot deps (Phase 3).

These are **portable and carry no project-specific dependencies** — do not edit them per
project. Project specifics go in the optional `*.local.sh` seams (Phase 4).

If a target file already exists and differs, show the diff and ask before overwriting.

## Phase 2 — Merge `.claude/settings.json`

The template is `assets/settings.json.tmpl`. For a **generic consumer** repo it registers
the **`rdl`** marketplace (`nq-rdl/agent-extensions`), enables **`rdl@rdl`** (the
meta-plugin that installs every RDL subject plugin), wires the two SessionStart hooks, and
sets opinionated defaults (`model: opus`, `alwaysThinkingEnabled`, `effortLevel: xhigh`,
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`).

**Apply the Phase 0 self-marketplace filter first.** If Phase 0 found self-references,
the template is **never written verbatim**: drop the self `enabledPlugins`/marketplace
entries before *both* the fresh-create and the merge path below.

- **If `.claude/settings.json` is absent:** create `.claude/` and write the
  (self-reference-filtered) template.
- **If it exists:** perform an **idempotent JSON-aware deep-merge** (use `jq` or a careful
  read-modify-write), and **show the diff before writing**:
  - `env`: add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` without clobbering other keys.
  - `hooks.SessionStart`: find (or create) the `startup|resume` matcher group; append the
    two hook commands **only if not already present** (dedupe by exact command string), so
    re-running is a no-op.
  - `enabledPlugins`: add the (filtered) plugin entries, e.g. `"rdl@rdl": true`.
  - `extraKnownMarketplaces`: add the corresponding entries; leave any existing
    marketplaces intact.
  - `model` / `alwaysThinkingEnabled` / `effortLevel`: set **only if absent** — never
    override a deliberate user choice. Mention they are opinionated defaults the user can
    decline.
  - If a stale `"superpowers@claude-plugins-official"` (or other migrated-away entry) is
    present, point it out and offer to remove it.

### Phase 2 (cont.) — Marketplace-consistency guard

After merging, **every plugin must have a source to install from**, or it silently never
installs (this is issue #157). So for **every** `"<name>@<marketplace>": true` entry in
the final `enabledPlugins` (only entries whose value is `true`), verify `<marketplace>` is
a key in `extraKnownMarketplaces`:

- **Missing + known** → add it automatically from this lookup table:
  | marketplace | source |
  |---|---|
  | `claude-plugins-official` | `{ "source": "github", "repo": "anthropics/claude-plugins-official" }`, `autoUpdate: true` |
  | `rdl` | `{ "source": "github", "repo": "nq-rdl/agent-extensions" }`, `autoUpdate: true` |

  Seed new entries as `{ "source": { "source": "github", "repo": "<repo>" }, "autoUpdate": true }`.
- **Missing + unknown** → **stop and ask** the user for the marketplace's source rather
  than writing a dangling reference.
- **Source conflict** → if `<marketplace>` is already a key but points at an *unexpected*
  repo (e.g. an `rdl` key not pointing to `nq-rdl/agent-extensions`), do **not** treat it
  as resolved — flag it and confirm with the user.

> Note: `claude-plugins-official` is auto-known for the local CLI/desktop, but **not** a
> reliable contract for Claude Code on the web — cloud sessions have silently failed to
> install its plugins until it was declared. So **always declare it explicitly** here.

## Phase 3 — Merge the Makefile target (optional)

This step is **only** relevant if the repo has heavy non-plugin deps to bake into the
snapshot (Phase 4's `cc-web-setup.local.sh`). It does **not** affect plugins.

If applicable, append `assets/Makefile.snippet` to the repo's `Makefile` **only if** a
`cc-web-setup:` target is not already present (create a `Makefile` with just the snippet
if none exists). This gives the user the optional `make cc-web-setup` entrypoint to set as
the environment Setup script. If the repo has no heavy pre-snapshot deps, you may skip the
Makefile target entirely.

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
- Confirm `bash scripts/cc-web-setup.sh` is idempotent — with no `cc-web-setup.local.sh`
  it is a no-op; a second run changes nothing.
- Validate `.claude/settings.json` parses (`jq . .claude/settings.json`).
- **Marketplace-coverage assertion (config consistency, not install success).** Assert
  that `extraKnownMarketplaces` covers every `@marketplace` referenced by a `true`
  `enabledPlugins` entry — flag any orphan. For example:
  ```bash
  jq -r '
    (.extraKnownMarketplaces // {} | keys) as $known
    | (.enabledPlugins // {} | to_entries
        | map(select(.value == true) | .key | split("@")[1]))
    | map(select(. as $m | ($known | index($m)) | not)) | unique[]
  ' .claude/settings.json
  ```
  Any line printed is an enabled plugin whose marketplace is undeclared (it would install
  nothing, silently) — go back and fix Phase 2. This checks *configuration* only; it
  cannot prove the plugin actually installed in a cloud session, and
  `announce-capabilities.sh` likewise reports *configured*, not *installed*.

## Phase 6 — Summarize for the user

Tell the user, concisely:
- What was created/merged (list the files + the settings keys touched).
- That **plugins install declaratively** from `.claude/settings.json` at session start in
  the cloud — their skills are available on the first session, **no manual setup-script
  step required**.
- If Phase 0 detected a **self-marketplace**, that you omitted the self-referencing
  plugin(s) to avoid shadowing the working tree, and which (if any) external plugins were
  enabled instead.
- Which marketplaces the Phase 2 guard added/confirmed so every enabled plugin resolves.
- **Only if** the repo has heavy non-plugin pre-snapshot deps: the optional step of
  setting the web environment's **Setup script** field to `make cc-web-setup` (a latency
  optimization that bakes those deps into the snapshot). Skip this otherwise.
- That `web-bootstrap.sh` is safe locally (no-op unless `CLAUDE_CODE_REMOTE=true`).
- How to add project-specific deps via `scripts/*.local.sh` (per-session
  `web-bootstrap.local.sh`; one-time pre-snapshot `cc-web-setup.local.sh`).
- That Codex CLI provisioning activates only when `CODEX_AUTH_JSON` or `CODEX_ACCESS_TOKEN`
  is set in the environment.
- That `announce-capabilities.sh` reports *configured* plugins, not *installed* ones — a
  plugin missing its marketplace would still be listed.
- To commit the new files so cloud sessions (which clone the repo) pick them up.
