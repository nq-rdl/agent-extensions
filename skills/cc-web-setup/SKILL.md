---
name: cc-web-setup
license: CC-BY-4.0
description: >-
  Bootstrap a repository for Claude Code on the web so cloud sessions start with the
  team's skills and slash-commands available on the FIRST session. Use when the user
  wants to "set up Claude Code on the web", "bootstrap web sessions", "add the web
  setup scripts", fix "skills/commands not available in Claude Code web", "configure
  the SessionStart hook for cloud", or "make this repo work with Claude Code on the
  web". The first-session mechanism is VENDORING — committing the chosen skills/agents
  into `.claude/`, which carry over as part of the clone (first-session, no network).
  Declarative `enabledPlugins` is kept as best-effort config for plugins that ship real
  behavior (hooks/MCP/LSP), but its web activation is unverified — not the first-session
  path. Covers the `CLAUDE_CODE_REMOTE` gate, the GitHub
  git-proxy 403, and the `install-deps.local.sh` seam (Docker, toolchains).
argument-hint: "Bootstrap this repo for Claude Code on the web? (run from the repo root; say if you have an existing .claude/settings.json to merge)"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Bootstrap a repo for Claude Code on the web

Provision the current repository so **Claude Code on the web** (cloud) sessions start with
the team's skills and slash-commands available **on the first session**, plus the GitHub
(and optionally Codex) CLI and project tooling. The portable pieces ship in this skill's
`assets/`; you copy them into the target repo's `.claude/`, **vendor** the chosen skills,
and merge the settings idempotently.

## Why the first session comes up empty (the invariant)

Skills are enumerated at process startup, and the docs are explicit that this happens
**before SessionStart hooks finish**:

> *"Skill discovery normally runs before SessionStart hooks finish, so files the hook writes
> into `~/.claude/skills/` or `.claude/skills/` would otherwise only appear in the next
> session."* ([hooks reference](https://code.claude.com/docs/en/hooks))

So a plugin installed at session start — by the platform's declarative install **or** any
SessionStart install hook (this skill ships none) — lands in the **plugin cache**, which
the same-session re-scan
(`reloadSkills`) does **not** cover. A **slow** install (cold-start race) lands in the
cache late, so its `/plugin:skill` commands appear the **next** session; a **failed**
install (unreachable marketplace, the git-proxy 403 below, or a wrong plugin id) writes no
cache at all, so it does **not** self-resolve — it re-fails until the cause is fixed. An empty first-session menu most often means the
declarative install did not land in time — though an unreachable marketplace or a wrong
plugin id can look the same. (Full evidence and the documented race — upstream issue #63028 —
live in [`references/web-setup.rst`](references/web-setup.rst).)

The reliable fix is to put skills where they are visible **before** any network step. This
skill uses **one first-session route plus a best-effort plugin layer**:

1. **Vendoring (the first-session route).** Commit the chosen skills into `.claude/skills/`
   and agents into `.claude/agents/`. Per the "what carries over" table these are *"part of
   the clone"* — present at startup, before enumeration, with zero network/git/marketplace.
   The robust path, and the **only** route for the name-reserved `claude-plugins-official`
   plugins. See Phase 3A.
2. **Declarative `enabledPlugins` (best-effort config).** The settings declaration is how you
   ask the platform for a plugin that ships real **behavior** — bundled hooks, an MCP server,
   an LSP — which a loose vendored skill **cannot** provide. But its web activation is
   **unverified**: external marketplaces 403 over the git proxy (below), the install races
   skill enumeration on session 1 (issue #63028), and the sandbox is ephemeral, so even
   "session 2+" inheritance is unproven. Treat it as necessary config for plugin-behavior
   picks, **not** a delivery guarantee — vendoring (route 1) is the guarantee.

> For the rare skill a team is contractually barred from committing (consume-but-not-
> redistribute) or too large to vendor, an **advanced escape hatch** — a manual HTTPS-fetch
> into `~/.claude/skills/` followed by `/reload-skills` — is documented in
> [`references/web-setup.rst`](references/web-setup.rst). It is not a shipped script; it
> trades the first-session guarantee for not committing copies.

## Background you must understand before acting

**The declarative plugin path is real, but fragile — treat it as best-effort, not the
guarantee.** Per the [web docs' "what carries over" table](https://code.claude.com/docs/en/claude-code-on-the-web):

> **Plugins declared in `.claude/settings.json`** carry over — *"Installed at session
> start from the marketplace you declared. Requires network access to reach the
> marketplace source."*

Declaring the marketplace under `extraKnownMarketplaces` and the plugin under
`enabledPlugins` is the mechanism for the platform's session-start install — there is **no
`make`, no manual step**. But the docs' one-line *"requires network access to reach the
marketplace source"* undersells a hard constraint that is why layers 1–2 exist:

> **The in-sandbox GitHub proxy authorizes git only against the session's own repo.**
> `claude plugin marketplace add owner/repo` is a `git clone`; verified empirically, it
> returns **403** for *every* repo that is not the session's working repo — a different
> repo in the **same org** and unrelated **public** repos alike. That proxy is
> **independent of the environment's network-access level**, so "Full network access" does
> **not** change it (per the web docs, *"GitHub operations use a separate proxy that is
> independent of this setting"*). `github.com` on the *Trusted* allowlist only governs
> ordinary HTTPS — the API, `raw.githubusercontent.com`, and `codeload` tarballs all
> work — **not** the git protocol.

Practical consequence: a marketplace whose source repo **is** the session repo (e.g.
`rdl@rdl` inside `nq-rdl/agent-extensions`) git-clones fine; **every external marketplace**
(`claude-plugins-official`, `worktrunk`, `astral-sh`, …) 403s over git. The route that
survives this (see [`references/web-setup.rst`](references/web-setup.rst) → "Failure mode #4 —
git-proxy repo-scoping" and Phase 3 below):

- **Vendor the skills into the repo's `.claude/skills/`** (Phase 3A) — they carry over as
  part of the clone (zero proxy, zero git, available the **first** session). The robust path,
  and what this repo does for its own plugins. Works for every source including the
  name-reserved `claude-plugins-official`. For the rare can't-commit case, the documented
  HTTPS-fetch escape hatch fetches the same way (over HTTPS, never git).

The fetch path is **HTTPS** (the git path is what 403s). The `install-deps.sh` **SessionStart
hook** this skill installs does **not** drive any plugin install. It is gated on
`CLAUDE_CODE_REMOTE` (a no-op on a contributor's laptop) and provisions only what the
declarative path does not:

- **Per-session CLIs** the base image may lack — `gh` (PR/CI automation) and, when
  `CODEX_AUTH_JSON`/`CODEX_ACCESS_TOKEN` is set, the Codex CLI.
- **The project dev toolchain + services** (language toolchains, the Docker daemon,
  git-hook wiring) via the optional `install-deps.local.sh` seam.

`install-deps.sh` does **not** touch plugins. An earlier `ensure_plugins` self-heal was
removed: a SessionStart plugin install lands in the plugin cache that `reloadSkills` does not
re-scan (so it can't surface a plugin the same session), and `claude plugin install` in a hook
has been reported to **hang** web sessions ([#18088](https://github.com/anthropics/claude-code/issues/18088)).
First-session availability comes from **vendoring** (route 1), not a retry hook.

`announce-capabilities.sh` (the second SessionStart hook) cross-checks the declared set
against `claude plugin list --json` and reports **"Enabled plugins (installed/enabled)"** vs
a **"⚠️ Declared but NOT installed"** line — so a marketplace-reachability failure is
surfaced, never masked. (It flags **"install unverified"** when the CLI can't be queried;
"installed" confirms install, not in-process activation.) Keep the chain in mind:
**declared ≠ installed ≠ surfaced.**

> **Do NOT drive the plugin install from a Setup-script field via `make`/git.** Earlier
> revisions set the environment's Setup-script field to `make install-deps`; that was wrong
> twice over — it drove the install through **git** (which 403s, failure mode #4) and it
> hard-blocked session startup on any CWD/branch hiccup. Plugins install declaratively; when
> the git path is blocked, the fix is **vendoring** (or the documented HTTPS-fetch escape
> hatch) — never `git`/`make`. A Setup-script field earns its keep only for caching heavy
> *packages*, or to pre-bake vendored/tarball-fetched content into the snapshot for
> first-session availability (it must fetch over HTTPS, never git, and be `|| true`-guarded
> so a hiccup never fails startup). This skill ships the portable hook, not a Setup-script.

> Authoritative platform facts (the web docs' "what carries over" table), the first-session
> route (vendoring) vs the best-effort declarative layer, the `install-deps.sh` engine +
> `install-deps.local.sh` seam, and the
> hard-won anti-patterns live in [`references/web-setup.rst`](references/web-setup.rst). Read
> it before bootstrapping an unfamiliar repo, and to debug a "declared but not installed" plugin.

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
project. Project specifics go in the optional `install-deps.local.sh` seam (Phase 3C).

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
2. **Discover and tailor the plugin set.** Delegate the "what does this repo need?" work to
   the **`marketplace-scout`** agent (Task tool): it locates `assets/marketplaces.json`,
   enumerates the *live* catalog of every tracked marketplace (the RDL marketplace **and**
   the team's extra marketplaces — official, worktrunk, codex, goland, astral), inspects the
   repo's languages/tooling, and returns a ranked suggestion list with provenance. It only
   recommends — **you** present its menu and let the user confirm; never silently decide.
   The scout's report is organized as:
   - **Baseline (always-useful)** — from `marketplaces.json` → `baseline`: `pr-review-toolkit@claude-plugins-official`,
     `gh@rdl`, `worktrunk@worktrunk`, plus the applicable LSP (`gopls-lsp@claude-plugins-official`
     for Go; the official marketplace ships more `*-lsp` plugins the scout enumerates per language).
   - **Language/LSP + stack-matched** — RDL subject plugins and `teamExternals` whose subject
     matches a detected language/tool (e.g. `go@rdl` + `modern-go-guidelines` + `gopls-lsp` for Go,
     `terraform@rdl` for `*.tf`, `astral@astral-sh` for Python).

   If you cannot or do not delegate, tailor by hand from `assets/marketplaces.json`: always
   offer the `baseline.always` set and the `agnostic`-tagged `teamExternals`; add the
   `go`/`python`/`workflow`-tagged entries and the matching `baseline.lsp` entry by language.
   Remember `gh@rdl` (and any other `@rdl` baseline pick) is stripped automatically inside this
   repo by `strip-self` (Phase 0) — it is a suggestion for *consumer* repos.

   **Then classify each confirmed pick** — this single selection drives all three layers, and
   nothing is hardcoded:
   - **A skill the user wants on the first session → VENDOR it** (Phase 3A). Default for the
     baseline picks and the name-reserved `claude-plugins-official` skills. (For the rare skill
     a team can't commit, the HTTPS-fetch escape hatch in the reference is the fallback.)
   - **A pick that needs real plugin behavior** (bundled hooks/MCP/LSP, `/plugin:` namespace) →
     **DECLARE** it in `enabledPlugins` (best-effort config, web-activation unverified); do not
     loose-vendor it (a partial plugin breaks — see Phase 3A self-containment).
   - The `enabledPlugins`/`extraKnownMarketplaces` you compose below is the **declare** set;
     the vendor/fetch sets are handled in Phase 3.
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
5. **Verify every enabled plugin actually exists (#169):**
   ```bash
   bash "$WS" verify .claude/settings.json
   ```
   `cover`/`ensure` only check the `@marketplace` *suffix* is declared — they do **not**
   check the plugin **name** exists in that marketplace's catalog. A hallucinated id (real
   marketplace, non-existent plugin — e.g. `pyright-lsp@claude-plugins-official`, a guessed
   `<lang>-lsp` or subject id) passes them and then sits as "Declared but NOT installed"
   **forever**. `verify` fetches each marketplace's `marketplace.json` and prints any enabled
   id **absent** from its catalog (exit 1) — **remove or correct those ids**. Ids it can't
   check because the marketplace was unreachable are reported on **stderr** as *unverifiable*
   (it never fails on those — that's the git-403 case, not a non-existent plugin). Only ever
   enable ids the `marketplace-scout` confirmed from a fetched catalog or the curated
   `marketplaces.json`; never hand-write an id from memory.

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

## Phase 3 — Make the chosen skills first-session-available

This is where the user's confirmed picks (Phase 2) become available. Classify each: a
**skill** is **vendored** (3A) — the first-session route; a **plugin** that ships real
behavior stays declared (Phase 2, best-effort config). **Agents and slash-commands are always
vendored** — `reloadSkills` does not reload agents, so only committed files are guaranteed at
startup.

### Phase 3A — Vendor the chosen skills/agents (the first-session route)

`.claude/skills/`, `.claude/agents/`, `.claude/commands/` carry over *as part of the clone* —
present before enumeration, no proxy/git/marketplace. Vendor self-contained real-file copies
(the model this repo uses under `plugins/`). It is also the **only** route for the
name-reserved `claude-plugins-official` plugins (`superpowers`, `pr-review-toolkit`,
`gopls-lsp`, `skill-creator`, `plugin-dev`). Fetch over **HTTPS**, pinned to an **immutable
commit SHA**, and copy only what you want:

```bash
# api.github.com/repos/<owner>/<repo>/tarball/<SHA> → codeload (both Trusted-allowlisted).
# No git. Add `-H "Authorization: Bearer $GH_TOKEN"` only for a PRIVATE marketplace.
SHA=<immutable-commit-sha>
ext="$(mktemp -d)"; tgz="$(mktemp)"
curl -fsSL "https://api.github.com/repos/OWNER/REPO/tarball/${SHA}" -o "$tgz"
tar -xzf "$tgz" -C "$ext" --strip-components=1
src="$ext/<path-to-skill>"
# Fail CLOSED if <path-to-skill> is wrong, THEN refuse a tree containing symlinks (they can
# point outside it). For an UNTRUSTED source use the hardened fetch_skill in
# references/web-setup.rst, which also rejects symlinked / `..` path components.
[ -f "$src/SKILL.md" ] || { echo "no SKILL.md at <path-to-skill>; refusing"; exit 1; }
find "$src" -type l -print -quit | grep -q . && { echo "skill has symlinks; refusing"; exit 1; }
mkdir -p .claude/skills
cp -R "$src" .claude/skills/<name>   # dir <name> MUST equal the skill's frontmatter name
git add .claude/skills/<name>
```

Before committing each vendored skill:
- **Record provenance** in `.claude/skills/VENDORED.md`: upstream `repo`, the **commit SHA**,
  source path, install name, and license — this is what makes a later refresh reviewable.
- **Preserve license/NOTICE** the upstream requires, alongside the skill.
- **Name agreement:** the install dir name must equal the skill's `name:` frontmatter (a loose
  skill's `/id` follows its name; a renamed dir alone would not rename the command).
- **Self-containment:** reject symlinks, and watch for skills that depend on
  `${CLAUDE_PLUGIN_ROOT}`, sibling plugin files, or bundled hooks/MCP/LSP — loose vendoring of
  those yields a **broken partial plugin**. If a pick needs real plugin behavior, leave it on
  the declarative layer (Phase 2) and accept its best-effort, unverified web activation (not a
  first-session guarantee).
- **Refresh deliberately:** on update, re-fetch the successor SHA, diff against the committed
  copy, and never silently overwrite local edits.

Vendor **agents** into `.claude/agents/<name>.md` and slash-**commands** into
`.claude/commands/` the same way.

### Phase 3B — (Advanced) the no-commit escape hatch

Skip this for almost every repo — vendoring (3A) is the route. Reach for it **only** when a
team is contractually barred from committing a skill's contents (consume-but-not-redistribute)
or the skill is too large to vendor. There is **no shipped script**: follow the manual pattern
in [`references/web-setup.rst`](references/web-setup.rst) → "Escape hatch — fetch without
committing" — an HTTPS-tarball fetch into `~/.claude/skills/<leaf>/` (`<leaf>` == the skill's
upstream `name:`), followed by `/reload-skills`. Trade-offs: it fetches over the network each
session (latency), covers **skills only** (agents/commands must be vendored), surfaces only
after the re-scan (not committed, so it can drift), and **forfeits the first-session
guarantee** that vendoring gives.

### Phase 3C — Offer the project extension seam (+ Docker)

`install-deps.sh` sources an optional, project-owned `.claude/scripts/install-deps.local.sh`
as its dev-toolchain step (every web session) — the sanctioned place for language toolchains,
container runtimes, git-hook wiring, and **starting `dockerd`** (the web runner ships the
docker CLI + daemon binary but **no running daemon and no systemd**, so a repo needing
containers must start it here; the idempotent pattern ships commented in
`assets/install-deps.local.sh.example`). Offer to scaffold it from the example; do **not**
create it unless the repo needs project-specific steps.

## Phase 4 — Verify

- **Vendored skills/agents (route 1, the first-session guarantee):** every vendored skill is
  at `.claude/skills/<name>/SKILL.md` with `<name>` == its frontmatter `name:`, contains no
  symlinks (`find .claude/skills -type l` is empty), and its provenance is recorded. Agents at
  `.claude/agents/<name>.md`. These are what make the slash menu populate on session 1.
- `CLAUDE_CODE_REMOTE=true bash .claude/scripts/install-deps.sh` → runs the hook (dev toolchain
  + gh/codex) and exits 0; `bash .claude/scripts/install-deps.sh` (no env var) → an immediate
  no-op. (Cloud installs may warn if offline — fine; it must still exit 0.)
- Validate `.claude/settings.json` parses (`jq . .claude/settings.json`).
- **Marketplace coverage (#157), only for the best-effort declarative layer:** `bash "$WS"
  cover .claude/settings.json` exits 0. Any line is an enabled plugin whose marketplace is
  undeclared (it would install nothing) — fix Phase 2. Configuration only; it cannot prove a
  cloud install succeeded, and the declarative layer is not the first-session guarantee.
- **Plugin existence (#169):** `bash "$WS" verify .claude/settings.json` exits 0. Any line on
  **stdout** is an enabled plugin id that does **not exist** in its (reachable) marketplace
  catalog — a hallucinated id that would be "Declared but NOT installed" forever; remove or
  correct it (Phase 2 step 5). Ids it could not check (marketplace unreachable) are noted on
  **stderr** and do not fail the check.

## Phase 5 — Summarize for the user

Tell the user, concisely:
- What was created/merged (the vendored skills/agents, the settings keys touched) and to
  **commit** it all so cloud sessions (which clone the repo) pick it up.
- **Why skills appear on the first session:** they are **vendored** into `.claude/` (part of
  the clone) — present before enumeration, with no network. No Setup-script field, no `make`.
- That declarative `enabledPlugins` is **best-effort config** for plugin behavior (hooks/MCP/
  LSP) — its web activation is **unverified**, not the first-session mechanism — and that
  `announce-capabilities.sh` flags any **"Declared but NOT installed"** plugin.
- That `install-deps.sh` is safe locally (no-op unless `CLAUDE_CODE_REMOTE=true`) and on the
  web provisions the gh/Codex CLIs and the project dev toolchain; Codex provisioning activates
  only when `CODEX_AUTH_JSON`/`CODEX_ACCESS_TOKEN` is set.
- How to add project-specific deps via `.claude/scripts/install-deps.local.sh`.
