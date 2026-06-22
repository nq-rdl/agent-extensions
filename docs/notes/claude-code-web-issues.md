# Notes — Claude Code on the web plugin visibility

Working notes from debugging "plugin skill commands are not visible in Claude Code
on the web." Kept as the record of what was tried, what was wrong, and the upstream
asks that still stand.

## Resolution (2026-06-22, post-#162) — plugins install declaratively

**The official docs settle it.** Per the
[Use Claude Code on the web "what carries over" table](https://code.claude.com/docs/en/claude-code-on-the-web):

> **Plugins declared in `.claude/settings.json`** — carries over: **Yes** —
> *"Installed at session start from the marketplace you declared. **Requires
> network access to reach the marketplace source.**"*

So the platform installs the declared plugins at session start. The original empty
slash menu was the documented failure mode — the marketplace source could not be
reached *as a whole* because the web set was headed by the **self-referential
`rdl@rdl` meta-plugin** that re-clones this repo and fans out to dozens of deps
(#160). Scoping `.claude/settings.json` to a small set of **external** dev-helper
plugins fixed the original problem.

**Where we went wrong (and corrected on the simplify branch).** A single live
observation of an empty `claude plugin list` (one session, on `main`) led us to
conclude the platform does *not* install declared plugins, and to build machinery
to install them ourselves: a root `Makefile` / `make install-deps`, a
`CLAUDE_CODE_REMOTE=true make install-deps` **Setup-script-field** entrypoint, and a
three-mode `install-deps.sh` (#161/#162). That was overbuilt — and the Setup-script
field also hard-failed environment startup (`make: No rule to make target
'install-deps'`, a CWD/branch issue). The corrected design:

- **Plugins: declarative only** (`enabledPlugins` + `extraKnownMarketplaces`). No
  setup script, no `make`, no manual Setup-script field.
- **`install-deps.sh`**: a `CLAUDE_CODE_REMOTE`-gated **SessionStart hook** that
  provisions only non-plugin tooling (gh/codex CLIs, the project dev toolchain +
  Docker via the `install-deps.local.sh` seam) **plus** an idempotent
  `ensure_plugins` **self-heal** (see the open question below).
- **`announce-capabilities.sh`**: keeps the "Declared but NOT installed" canary so a
  marketplace-reachability failure is surfaced, not masked.
- **Removed**: the `Makefile`, the `make install-deps` Setup-script guidance, and the
  three-mode engine. The Setup-script field is for caching heavy *packages*, not
  plugins.

**Process lesson:** read the one authoritative doc table before building around a
single live observation. The docs were reachable the whole time.

## Open question — is `ensure_plugins` (the self-heal) actually needed?

The docs say the platform installs declared plugins at session start. Yet we *did*
observe a session where `claude plugin list` was empty despite reachable
marketplaces, and where our hook's `claude plugin install` was what populated them.
Two readings:

- **Docs are right; it was transient.** Then `ensure_plugins` is redundant — the
  platform retries each session, and a hook-installed plugin can't surface until the
  next session anyway (skills enumerate before SessionStart hooks).
- **The platform's auto-install is unreliable in practice here.** Then
  `ensure_plugins` is the belt-and-suspenders that makes plugins appear at all.

We kept it as a cheap, idempotent self-heal because the empirical evidence (we
watched the platform not install, and the hook install + persist) outweighs a
docs-only argument. If repeated observation shows the platform installs reliably,
delete `ensure_plugins` and rely purely on the declarative path. **Ask upstream:**
document the retry/idempotency behavior of the session-start plugin install, and
whether it re-attempts after a transient marketplace failure.

## Open question — does `reloadSkills` re-scan the plugin cache? (upstream)

Claude enumerates plugin skills at **process startup, before** `SessionStart` hooks
finish (hooks docs: *"Skill discovery normally runs before SessionStart hooks
finish"*). Empirically, `announce-capabilities.sh` returning `reloadSkills: true` did
**not** surface plugin-cache skills mid-session — `/reload-skills` reported "no
changes." So that re-scan appears to cover loose `~/.claude/skills/` only, not the
plugin install cache. **Ask upstream:** confirm/document the `reloadSkills` scope,
and ideally have the platform install `enabledPlugins` *before* skill enumeration so
no hook involvement is ever needed.

## Note — Docker daemon is not running on web runners

Web runners ship the `docker` CLI + `dockerd` binary but **no running daemon** and no
systemd. Anything needing containers (devcontainer smoke tests, testcontainers, k3d)
must start `dockerd` itself in the `install-deps.local.sh` seam (wired here via
`ensure_docker`, documented in the `cc-web-setup` skill). Worth a docs issue upstream
so it is discoverable rather than tribal knowledge.
