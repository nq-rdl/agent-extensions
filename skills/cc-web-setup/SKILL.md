---
name: cc-web-setup
license: CC-BY-4.0
description: >-
  Bootstrap a repository for Claude Code on the web so cloud sessions start with the
  team's skills and slash-commands available on the FIRST session. Use when the user
  wants to "set up Claude Code on the web", "bootstrap web sessions", "add the web
  setup scripts", fix "skills/commands not available in Claude Code web", "configure
  the SessionStart hook for cloud", or "make this repo work with Claude Code on the
  web". DEFAULT is VENDORING — committing the chosen skills/agents into `.claude/`,
  which carry over as part of the clone (first-session, no network). Optionally adds a
  `.claude/scripts/bootstrap-web.sh` hook that HTTPS-fetches `.claude/web-skills.json`
  skills into `~/.claude/skills/` + `reloadSkills`, for teams that prefer fetch-fresh.
  Declarative `enabledPlugins` is kept best-effort (namespacing/autoUpdate from session
  2+, not the first-session path). Covers the `CLAUDE_CODE_REMOTE` gate, the GitHub
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
SessionStart self-heal — lands in the **plugin cache**, which the same-session re-scan
(`reloadSkills`) does **not** cover. If that install is slow or fails (unreachable
marketplace, the git-proxy 403 below, or a cold-start race), its `/plugin:skill` commands
appear only the **next** session. An empty first-session menu most often means the
declarative install did not land in time — though an unreachable marketplace or a wrong
plugin id can look the same. (Full evidence and the documented race — upstream issue #63028 —
live in [`references/web-setup.rst`](references/web-setup.rst).)

The reliable fix is to put skills where they are visible **before** any network step. This
skill uses **two first-session routes plus a best-effort plugin layer**:

1. **Vendoring (the default).** Commit the chosen skills into `.claude/skills/` and agents
   into `.claude/agents/`. Per the "what carries over" table these are *"part of the clone"* —
   present at startup, before enumeration, with zero network/git/marketplace. The robust path,
   and the **only** route for the name-reserved `claude-plugins-official` plugins. See Phase 3A.
2. **`bootstrap-web.sh` (optional, opt-in).** For skills a team would rather pull **fresh**
   than commit: a SessionStart hook HTTPS-tarball-fetches the skills listed in
   `.claude/web-skills.json` into `~/.claude/skills/` and returns `reloadSkills: true` — the
   documented same-session re-scan. Added **only when chosen** (Phase 3B); on a resume it
   leaves already-present skills untouched.
3. **Declarative `enabledPlugins` (best-effort).** When the marketplace is reachable it gives
   `/plugin:skill` namespacing and `autoUpdate` from session 2+ — it is **not** a first-session
   guarantee; routes 1–2 are.

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
(`claude-plugins-official`, `worktrunk`, `astral-sh`, …) 403s over git. Two routes survive
this (see [`references/web-setup.rst`](references/web-setup.rst) → "Failure mode #4 — git-proxy
repo-scoping" and Phase 3 below):

- **Vendor the skills into the repo's `.claude/skills/`** (Phase 3A) — they carry over as
  part of the clone (zero proxy, zero git, available the **first** session). The robust path,
  and what this repo does for its own plugins. Works for every source including the
  name-reserved `claude-plugins-official`.
- **`bootstrap-web.sh`** (Phase 3B, opt-in) — fetches the skills the same way (HTTPS tarball)
  into `~/.claude/skills/` + `reloadSkills`, for teams that prefer fetch-fresh over committing.

Both fetch over **HTTPS** (the git path is what 403s). The `install-deps.sh` **SessionStart
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
against `claude plugin list` and reports **"Enabled plugins (installed)"** vs a
**"⚠️ Declared but NOT installed"** line — so a marketplace-reachability failure is
surfaced, never masked. Keep the chain in mind: **declared ≠ installed ≠ surfaced.**

> **Do NOT drive the plugin install from a Setup-script field via `make`/git.** Earlier
> revisions set the environment's Setup-script field to `make install-deps`; that was wrong
> twice over — it drove the install through **git** (which 403s, failure mode #4) and it
> hard-blocked session startup on any CWD/branch hiccup. Plugins install declaratively; when
> the git path is blocked, the fix is **vendoring** (or the `bootstrap-web.sh` HTTPS fetch) —
> never `git`/`make`. A Setup-script field earns its keep only for caching heavy
> *packages*, or to pre-bake vendored/tarball-fetched content into the snapshot for
> first-session availability (it must fetch over HTTPS, never git, and be `|| true`-guarded
> so a hiccup never fails startup). This skill ships the portable hook, not a Setup-script.

> Authoritative platform facts (the web docs' "what carries over" table), the first-session
> routes (vendoring + the opt-in `bootstrap-web.sh` `reloadSkills` hook) vs the best-effort
> declarative layer, the `install-deps.sh` engine + `install-deps.local.sh` seam, and the
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

A **third** script, `assets/bootstrap-web.sh`, is **not** copied here by default — it ships
only when the user opts into the fetch-fresh route (Phase 3B), which copies it, generates
`.claude/web-skills.json`, and wires its SessionStart entry as one unit. The default path is
vendoring (Phase 3A), which needs no extra script.

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
     baseline picks and the name-reserved `claude-plugins-official` skills. Ask the user once
     whether they prefer to **commit** vendored copies (default) or **fetch fresh** (3B) for
     skills they'd rather not commit.
   - **A pick that needs real plugin behavior** (bundled hooks/MCP/LSP, `/plugin:` namespace) →
     **DECLARE** it in `enabledPlugins` (best-effort, session 2+); do not loose-vendor it (a
     partial plugin breaks — see Phase 3A self-containment).
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
**skill** is **vendored** (3A, default) or **fetched** (3B, opt-in); a **plugin** stays
declared (Phase 2, best-effort). **Agents and slash-commands are always vendored** —
`reloadSkills` does not reload agents, so only committed files are guaranteed at startup.

### Phase 3A — Vendor the chosen skills/agents (default, first-session)

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
# Real files only — refuse a skill whose tree contains symlinks (they can point outside it):
test -z "$(find "$ext/<path-to-skill>" -type l)" || { echo "skill has symlinks; refusing"; exit 1; }
mkdir -p .claude/skills
cp -R "$ext/<path-to-skill>" .claude/skills/<name>   # dir <name> MUST equal the skill's frontmatter name
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
  the declarative layer (Phase 2) and accept session-2 availability.
- **Refresh deliberately:** on update, re-fetch the successor SHA, diff against the committed
  copy, and never silently overwrite local edits.

Vendor **agents** into `.claude/agents/<name>.md` and slash-**commands** into
`.claude/commands/` the same way.

### Phase 3B — (Opt-in) fetch-fresh via `bootstrap-web.sh`

Only when the user prefers **not** to commit copies (pull fresh each session instead). Deploy
all three pieces as one unit, then verify them:

1. Copy `assets/bootstrap-web.sh` → `.claude/scripts/bootstrap-web.sh`; `chmod +x`.
2. Generate `.claude/web-skills.json` from the user's fetch picks (see
   `assets/web-skills.json.example`): one `{repo, ref, path, leaf}` per skill, `ref` a **commit
   SHA**, `leaf` == the skill's upstream `name:` (the hook refuses a mismatch).
3. Add its command to the `hooks.SessionStart` `startup|resume` group in `.claude/settings.json`
   (idempotently): `"$CLAUDE_PROJECT_DIR"/.claude/scripts/bootstrap-web.sh`.
4. **Verify all three:** the script exists + is executable, `jq . .claude/web-skills.json`
   parses, and the hook entry is present. (Omitting any one is a silent no-op or a missing-file
   reference.)

Trade-offs vs vendoring: needs network each session, adds startup latency, fetches **skills
only** (not agents), and surfaces via `reloadSkills` (same session, first prompt). On a resume
it leaves already-present skills untouched (so it is not literally "fresh" on a resume).

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
- **If Phase 3B was chosen:** `.claude/scripts/bootstrap-web.sh` is executable, `jq .
  .claude/web-skills.json` parses, and its SessionStart entry is present.
  `CLAUDE_CODE_REMOTE=true bash .claude/scripts/bootstrap-web.sh` (with the manifest) fetches
  into `~/.claude/skills/` and emits `reloadSkills`; with no env var it is a silent no-op.
- `CLAUDE_CODE_REMOTE=true bash .claude/scripts/install-deps.sh` → runs the hook (dev toolchain
  + gh/codex) and exits 0; `bash .claude/scripts/install-deps.sh` (no env var) → an immediate
  no-op. (Cloud installs may warn if offline — fine; it must still exit 0.)
- Validate `.claude/settings.json` parses (`jq . .claude/settings.json`).
- **Marketplace coverage (#157), only for the best-effort declarative layer:** `bash "$WS"
  cover .claude/settings.json` exits 0. Any line is an enabled plugin whose marketplace is
  undeclared (it would install nothing) — fix Phase 2. Configuration only; it cannot prove a
  cloud install succeeded, and the declarative layer is not the first-session guarantee.

## Phase 5 — Summarize for the user

Tell the user, concisely:
- What was created/merged (the vendored skills/agents, any `bootstrap-web.sh` + manifest, the
  settings keys touched) and to **commit** it all so cloud sessions (which clone the repo)
  pick it up.
- **Why skills appear on the first session:** they are **vendored** into `.claude/` (part of
  the clone), and/or fetched by `bootstrap-web.sh` into `~/.claude/skills/` + `reloadSkills`.
  No Setup-script field, no `make`.
- That declarative `enabledPlugins` is **best-effort** (plugin namespacing/autoUpdate from
  session 2+ when the marketplace is reachable) — not the first-session mechanism — and that
  `announce-capabilities.sh` flags any **"Declared but NOT installed"** plugin.
- That `install-deps.sh` is safe locally (no-op unless `CLAUDE_CODE_REMOTE=true`) and on the
  web provisions the gh/Codex CLIs and the project dev toolchain; Codex provisioning activates
  only when `CODEX_AUTH_JSON`/`CODEX_ACCESS_TOKEN` is set.
- How to add project-specific deps via `.claude/scripts/install-deps.local.sh`.
