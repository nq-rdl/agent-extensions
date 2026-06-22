# Notes — issues to raise for the `claude-code` plugin / Claude Code on the web

Working notes captured while debugging "plugin skill commands are not visible in
Claude Code on the web" (branch `claude/skill-commands-visibility-pfjssk`). These
are candidates to file as issues — against the **`claude-code`** plugin in this
repo (the `cc-web-setup` / `web-setup` skill) where we own the fix, and against
**upstream Claude Code** where the root cause is the harness.

## 1. First-session skill enumeration vs. SessionStart (upstream Claude Code)

**Symptom.** On a fresh web environment, `/<plugin>:<skill>` commands declared via
`.claude/settings.json` (`extraKnownMarketplaces` + `enabledPlugins`) do **not**
appear in the first session's slash menu. They show only from the *second* session.

**Root cause.** Claude Code enumerates plugin skills at process startup, **before**
any `SessionStart` hook runs. A plugin installed by a SessionStart hook therefore
lands after enumeration → not in the menu until next session.

**Our mitigation (this repo).** A pre-snapshot setup script (`make cc-web-setup`
→ `.claude/hooks/cc-web-setup.sh`) installs the plugins *before* Claude starts, so
they are baked into the environment snapshot. Requires the env's **Setup script**
field to be set — a per-environment UI setting, not committable.

**Ask upstream.** Either (a) install `enabledPlugins` from known marketplaces
*before* skill enumeration on web, or (b) re-enumerate skills after `SessionStart`
hooks complete, so a hook-driven install surfaces same-session. Today the
declarative `enabledPlugins` path is effectively second-session-only on web.

## 2. `announce-capabilities.sh` reports enabled, not installed (this repo)

`announce-capabilities.sh` lists `enabledPlugins` from `settings.json` as
"Enabled plugins" without verifying they actually installed/loaded. This produced
a false-positive that masked issue #1 (the announcement looked healthy while the
slash menu was empty). Consider verifying against `claude plugin list` and marking
declared-but-not-installed plugins.

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
