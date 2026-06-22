# Notes — issues to raise for the `claude-code` plugin / Claude Code on the web

Working notes captured while debugging "plugin skill commands are not visible in
Claude Code on the web" (branch `claude/skill-commands-visibility-pfjssk`). These
are candidates to file as issues — against the **`claude-code`** plugin in this
repo (the `cc-web-setup` / `web-setup` skill) where we own the fix, and against
**upstream Claude Code** where the root cause is the harness.

## Resolution — CORRECTED (2026-06-22, issue #161)

> **Earlier "resolution" (below this block) was WRONG and is kept only for the
> record.** It claimed the platform installs `enabledPlugins` at session start, so
> no setup script / `make` was needed. **It does not.** Verified live on Claude
> Code 2.1.185: a fresh web VM had every `extraKnownMarketplaces` entry registered
> yet `claude plugin list` **empty** and no `/<plugin>:<skill>` in the menu;
> `claude plugin install` then worked instantly (network fine). So
> `extraKnownMarketplaces` makes plugins *known* and `enabledPlugins` only
> *enables* an already-installed plugin — **neither installs one.** When the
> "declarative is enough" belief led us to delete the install machinery, nothing
> installed the plugins at all.

**The actual mechanism (now shipped):**

- A repo script must run `claude plugin install` for the declared set.
  `.claude/scripts/install-deps.sh` (`ensure_plugins`, reading `enabledPlugins`
  from `settings.json`) does this, exposed as `make install-deps`.
- Claude enumerates skills at **startup, before** any SessionStart hook, so a
  hook-installed plugin surfaces only from the **next** session. The plugin cache
  **does** persist across sessions in an environment (confirmed: a resume reported
  "already present" and the skills loaded), so the hook is enough from session 2 —
  but the **first** session of a new environment needs a **pre-snapshot** install.
- That pre-snapshot install is the environment's **Setup-script field** set to
  `CLAUDE_CODE_REMOTE=true make install-deps`. The `install-deps.sh --session`
  SessionStart hook self-heals resumes; `announce-capabilities.sh` cross-checks
  `claude plugin list` and flags "Declared but NOT installed".

The self-referential `rdl@rdl` point still stands: do not enable a repo's own meta
marketplace inside that repo's dev env (it re-clones + fans out and breaks the
batch). The `make cc-web-setup` name is retired in favour of `make install-deps`.

### Superseded resolution (kept for the record)

The practical fix was **not** the `cc-web-setup` pre-seed. Claude Code on the web
installs the plugins declared in `.claude/settings.json` (`enabledPlugins` +
`extraKnownMarketplaces`) **at session start from their marketplaces** (web docs,
"what carries over" table), so their `/<plugin>:<skill>` commands surface on the
first session with no setup script and no `make`. This repo's earlier failure was
self-inflicted: it declared 44 plugins headed by the **self-referential `rdl@rdl`
meta-plugin** (which re-clones this repo and fans out to 35 deps), breaking the
session-start install as a whole — so *nothing*, not even `superpowers`, surfaced.
Scoping `.claude/settings.json` to a small set of **external** dev-helper plugins
(the same path that gives `nq-rdl/dataops` its `/superpowers:*`) resolved it, and
the `.claude/hooks/cc-web-setup.sh` + `make cc-web-setup` self-heal machinery was
removed as unnecessary. The notes below are kept as the historical investigation
and the upstream asks (which still stand).

## 1. Does `reloadSkills` re-scan plugin-cache skills? (upstream Claude Code)

**Symptom.** On a fresh web environment, `/<plugin>:<skill>` commands declared via
`.claude/settings.json` (`extraKnownMarketplaces` + `enabledPlugins`) do **not**
appear in the first session's slash menu. They show only from the *second* session.

**Root cause.** Claude Code enumerates plugin skills at process startup, **before**
`SessionStart` hooks finish (confirmed: hooks docs say *"Skill discovery normally
runs before SessionStart hooks finish"*). A plugin installed by a SessionStart hook
therefore lands after enumeration.

**Our fix (two layers).** The guaranteed path is the **pre-snapshot Setup-script
field** (`make cc-web-setup`), which installs the plugins before Claude enumerates —
see `CONTRIBUTING.md` § "Claude Code on the web". As a fallback, the
`CLAUDE_CODE_REMOTE`-gated SessionStart hook also installs the plugins
(`.claude/hooks/cc-web-setup.sh`) and `announce-capabilities.sh` returns
`reloadSkills: true` — but, as confirmed below, that re-scan does not pick up
plugin-cache skills, so the hook only self-heals for the *next* session.

**Confirmed empirically (2026-06-22).** `reloadSkills` does **not** re-scan
**plugin-cache** skills. In a fresh web session the SessionStart hook installed all
declared plugins (`claude plugin list` → all `√ enabled`, their `SKILL.md` files
present under `~/.claude/plugins/cache/rdl/...`) and `announce-capabilities.sh`
returned `reloadSkills: true` — yet the only skills in the slash menu were Claude
Code's built-ins; **no** `/<plugin>:<skill>` command surfaced, and a manual
`/reload-skills` reported "no changes". So the docs' `reloadSkills` re-scan covers
only loose `~/.claude/skills/`, not the plugin install cache. **The pre-snapshot
Setup-script field (`make cc-web-setup`) is therefore the only guaranteed
first-session path** — the SessionStart hook is a self-heal, not a substitute.

**Ask upstream.** (a) Confirm/document whether `reloadSkills` re-scans plugin-cache
skills, not just loose `~/.claude/skills/`; and (b) ideally install `enabledPlugins`
from known marketplaces *before* skill enumeration on web so no hook dance is needed.

## 2. `announce-capabilities.sh` reports enabled, not installed (this repo) — FIXED

`announce-capabilities.sh` listed `enabledPlugins` from `settings.json` as
"Enabled plugins" without verifying they actually installed/loaded. This produced
a false-positive that masked issue #1 (the announcement looked healthy while the
slash menu was empty).

**Fixed.** The hook now cross-checks the declared set against `claude plugin list`:
it reports only verified-installed plugins under **"Enabled plugins (installed)"**
and surfaces any declared-but-not-installed plugins under a **"⚠️ Declared but NOT
installed"** line with the `make cc-web-setup` remedy. It falls back to the declared
set when the `claude` CLI is unavailable (some Action runners).

## 3. `cc-web-setup` skill assumed a `scripts/` layout only (this repo)

The shipped skill template wires hooks under `scripts/`, but this repo keeps them
under `.claude/hooks/`. The skill should document/support both layouts (or the
discrepancy will keep biting repos that follow the `.claude/hooks/` convention).

## 4. Docker daemon is not running on web runners (documented; verify upstream)

Web runners ship the `docker` CLI + `dockerd` binary but **no running daemon** and
no systemd. Anything needing containers (devcontainer smoke tests, testcontainers,
k3d) must start `dockerd` itself in the `web-bootstrap.local.sh` seam (now wired
here via `ensure_docker`, and documented in the `cc-web-setup` skill). Worth a docs
issue upstream so this is discoverable rather than tribal knowledge.

## 5. Pre-seed should read `settings.json` (consider upstreaming to the skill asset)

This repo's `cc-web-setup.sh` reads the marketplaces + enabled plugins straight
from `.claude/settings.json` (single source of truth) instead of the skill asset's
hardcoded-with-env-override list. Consider folding the settings-driven approach
back into `skills/cc-web-setup/assets/cc-web-setup.sh` so the two cannot drift.
