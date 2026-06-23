======================================
Claude Code on the web — setup reference
======================================

Authoritative facts, the layered architecture, and the anti-patterns behind the
``cc-web-setup`` skill. Read this before bootstrapping an unfamiliar repo or when
debugging a plugin that is *declared* but never *installs*.

The two source-of-truth notes this distills from live in the repo and should be
read for the full story:

- ``docs/notes/claude-code-web-issues.md`` — the investigation log (why declarative
  won, why the self-heal stays, the ``reloadSkills`` finding, the Docker note).
- ``CONTRIBUTING.md`` § "Claude Code on the web" — why a catalog-dev session enables
  *external* dev-helper plugins, never the catalog itself.

Official docs: https://code.claude.com/docs/en/claude-code-on-the-web


What carries over (the platform contract)
=========================================

Per the web docs' "what carries over" table, **plugins declared in**
``.claude/settings.json`` (``extraKnownMarketplaces`` + ``enabledPlugins``) are
*"installed at session start from the marketplace you declared. Requires network
access to reach the marketplace source."*

Consequences that drive every design choice here:

- Declaring the marketplace + plugin **is the whole mechanism**. There is **no
  Setup-script field, no** ``make``\ **, no** ``.claude/skills/`` **bake** needed for
  plugins. ``github.com`` is on the default *Trusted* allowlist, so a github-sourced
  marketplace is reachable by default.
- The only failure mode is the marketplace source being unreachable, or its local
  index being stale on a cold VM. Both are handled by the self-heal (below).
- A cloud session is a **fresh VM with only a clone of the repo** — anything not in
  git (or not installed by the SessionStart hook) is absent.


The three layers
================

1. **Declarative settings (plugins).** ``.claude/settings.json`` carries
   ``extraKnownMarketplaces`` (sources, ``autoUpdate``) and ``enabledPlugins``. The
   platform installs them at session start. This skill ships two bases —
   ``assets/settings.json.tmpl`` (rdl) and ``assets/settings.externals.json.tmpl``
   (team externals, no rdl) — and ``assets/marketplaces.json`` as the single source
   of truth for marketplace sources + the curated team-externals set.

2. **The portable engine** — ``.claude/scripts/install-deps.sh``, a SessionStart
   hook **gated on** ``CLAUDE_CODE_REMOTE=true`` (a no-op on a contributor's laptop).
   It provisions only what the declarative path does not: per-session CLIs (``gh``,
   and Codex when ``CODEX_AUTH_JSON`` is set), the project dev toolchain via the
   ``install-deps.local.sh`` seam, and a cheap idempotent **plugin self-heal**
   (``ensure_plugins``). Every step is non-fatal; the hook always exits 0.

3. **The project seam** — ``.claude/scripts/install-deps.local.sh`` (optional,
   per-repo). Language toolchains, git-hook wiring, and **starting** ``dockerd``
   (the web runner ships the docker CLI + daemon binary but **no running daemon and
   no systemd**, so a repo that needs containers must start it here).

The chain to keep in mind: **declared ≠ installed ≠ surfaced.**
``announce-capabilities.sh`` (the second SessionStart hook) cross-checks
``claude plugin list`` and reports **"Enabled plugins (installed)"** vs **"⚠️
Declared but NOT installed"**, so a reachability failure is surfaced, never masked.


The self-heal (``ensure_plugins``)
==================================

Declarative install is primary; the self-heal is the backstop kept **deliberately**
(it has empirically rescued installs). It reads ``enabledPlugins`` from
``settings.json`` via ``jq``, skips ids already in ``claude plugin list``, and
installs the rest idempotently. On a failed install it derives the marketplace from
the ``@`` suffix, runs ``claude plugin marketplace update <mkt>`` (the refresh
``claude plugin install`` does **not** do itself — the stale-index failure mode),
and retries once, refreshing each marketplace at most once per run.

A plugin the self-heal installs **surfaces from the *next* session**: Claude
enumerates skills at startup, *before* SessionStart hooks run, and ``reloadSkills``
empirically *appears* to re-scan only loose ``~/.claude/skills/``, not the plugin
install cache (unconfirmed upstream — see ``docs/notes/claude-code-web-issues.md``).


The two guards this skill enforces
==================================

Run from the skill's ``scripts/web-settings.sh`` (a setup-time tool, never copied
into the target repo):

- **Self-marketplace (Phase 0)** — ``strip-self <repo-root> <settings>`` removes any
  ``enabledPlugins``/marketplace that resolves to this repo's own
  ``.claude-plugin/marketplace.json``. Prevents shadowing working-tree edits with the
  published copy.
- **Marketplace coverage (Phase 2/5, issue #157)** — ``ensure <settings>`` auto-adds
  every missing-but-known marketplace from ``marketplaces.json`` and **stops and
  asks** on an unknown one (it writes nothing and exits non-zero). ``cover
  <settings>`` is the read-only assertion that every enabled plugin's ``@marketplace``
  is declared.


Anti-patterns — do not repeat these
===================================

These each cost a PR (or several) to learn:

- **Self-referential / meta marketplace in its own dev env.** Enabling ``rdl@rdl``
  inside ``nq-rdl/agent-extensions`` re-clones the repo and fans out to dozens of
  dependency plugins; that oversized self-cloning batch broke the whole session-start
  install so **nothing** surfaced. A catalog-dev env enables *external* dev-helper
  plugins, not the catalog.
- **A pre-snapshot Setup-script field for plugins** (``make install-deps`` / ``make
  cc-web-setup``). Plugins already auto-install declaratively; worse, a ``make``
  Setup-script field hard-failed *environment startup* on a CWD hiccup. The
  Setup-script field is only worth it for heavy **non-plugin** caching.
- **Believing "the platform registers marketplaces but does not install
  enabledPlugins."** It does install them. An empty ``claude plugin list`` is the
  stale-index / unreachable-source failure, not a missing platform feature.
- **Reporting *declared* plugins as installed.** Build the banner from ``claude plugin
  list``, not from ``settings.json``, or a missing marketplace looks healthy while the
  slash menu is empty.
- **A naive ``claude plugin install`` retry without ``marketplace update``.** On a
  cold VM the index is empty; the retry re-hits the same stale index forever.
- **Leaving ``CODEX_ACCESS_TOKEN`` set.** Codex parses it as a JWT at runtime; a
  blob/blank value breaks every later ``codex exec`` even with a valid ``auth.json``.
  Unset it in-process and via ``CLAUDE_ENV_FILE``.
- **Predictable ``/tmp`` log paths.** A symlink-truncation/race vector — use ``mktemp``
  with ``umask 077``.
