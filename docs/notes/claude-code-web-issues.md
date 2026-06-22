# Notes — issues to raise for the `claude-code` plugin / Claude Code on the web

Working notes captured while debugging "plugin skill commands are not visible in
Claude Code on the web" (branch `claude/skill-commands-visibility-pfjssk`). These
are candidates to file as issues — against the **`claude-code`** plugin in this
repo (the `cc-web-setup` / `web-setup` skill) where we own the fix, and against
**upstream Claude Code** where the root cause is the harness.

## 1. Does `reloadSkills` re-scan plugin-cache skills? (upstream Claude Code)

**Symptom.** On a fresh web environment, `/<plugin>:<skill>` commands declared via
`.claude/settings.json` (`extraKnownMarketplaces` + `enabledPlugins`) do **not**
appear in the first session's slash menu. They show only from the *second* session.

**Root cause.** Claude Code enumerates plugin skills at process startup, **before**
`SessionStart` hooks finish (confirmed: hooks docs say *"Skill discovery normally
runs before SessionStart hooks finish"*). A plugin installed by a SessionStart hook
therefore lands after enumeration.

**Our fix (this repo, committed, no manual step).** The `CLAUDE_CODE_REMOTE`-gated
SessionStart hook installs the plugins (`.claude/hooks/cc-web-setup.sh`), and
`announce-capabilities.sh` returns `reloadSkills: true`, which per the docs makes
Claude *"re-scan the skill and command directories after the SessionStart hooks
complete, so skills the hook installed are available in the same session."*

**The open question to raise.** The docs only document/exemplify the `reloadSkills`
re-scan for **loose** skills under `~/.claude/skills/` (e.g. a `git clone` into that
dir). They do **not** state whether the re-scan also covers **plugin-cache** skills
installed via `claude plugin install` (which live under the plugin install cache,
not `~/.claude/skills/`). If it does not, hook-installed *plugin* skills still only
surface next session, and the pre-snapshot Setup-script (`make cc-web-setup`) is the
only guaranteed first-session path.

**Ask upstream.** (a) Confirm/document whether `reloadSkills` re-scans plugin-cache
skills, not just loose `~/.claude/skills/`; and (b) ideally install `enabledPlugins`
from known marketplaces *before* skill enumeration on web so no hook dance is needed.

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
