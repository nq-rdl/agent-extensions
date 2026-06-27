======================================
Claude Code on the web — setup reference
======================================

Authoritative facts, the layered architecture, and the anti-patterns behind the
``cc-web-setup`` skill. Read this before bootstrapping an unfamiliar repo or when
debugging a plugin that is *declared* but never *installs*.

Companion docs in the repo:

- ``docs/claude-code-web.md`` — the reader-facing "how this repo's setup works" overview
  (the invariant, the two first-session routes, why there is no self-heal, the constraints).
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

- Declaring the marketplace + plugin is the **whole mechanism** for the platform's
  session-start install. But ``github.com`` being on the *Trusted* allowlist does **not**
  make a github-sourced marketplace reachable by **git**: the in-sandbox GitHub proxy
  authorizes git only against the session's **own repo** (see "Failure mode #4" below), so
  ``claude plugin marketplace add owner/repo`` 403s for every external marketplace. The
  allowlist governs ordinary HTTPS (API, ``raw``, ``codeload``), not the git protocol.
- The declarative install's failure modes are: the source genuinely **unreachable**; the
  local index being **stale**; or the git clone **403'd by the GitHub proxy** because the
  marketplace repo is not the session repo (failure mode #4). All of them only delay or block
  the *best-effort* plugin layer; ``announce-capabilities.sh`` surfaces the gap, and the
  first-session fix is to **vendor** the skill (route 1) rather than depend on that install.
- A cloud session is a **fresh VM with only a clone of the repo** — anything not in
  git (or not installed by the SessionStart hook) is absent.


First-session routes vs the best-effort plugin layer
====================================================

The governing fact: **skill discovery runs before SessionStart hooks finish** (hooks
reference), and the same-session re-scan ``reloadSkills`` covers the loose **skill and
command directories** (``.claude/skills/``, ``~/.claude/skills/``, ``.claude/commands/``)
— **not** the plugin install cache. So a plugin installed at session start (declaratively
or by a hook) cannot surface that session unless it was already cached before enumeration.
Two routes put skills where they are visible first; the declarative plugin path is a
best-effort layer on top.

1. **Vendoring (default, first-session).** Commit the chosen skills into
   ``.claude/skills/`` and agents into ``.claude/agents/`` (commands into
   ``.claude/commands/``). Per the "what carries over" table these are *part of the clone*
   — present at startup, before enumeration, with no proxy/git/marketplace. The robust
   path and the **only** route for the name-reserved ``claude-plugins-official`` skills.
   Self-contained real files (no symlinks, no ``${CLAUDE_PLUGIN_ROOT}``/sibling/bundled-
   component dependencies), pinned to a commit SHA, provenance recorded.

2. **``bootstrap-web.sh`` (opt-in, same-session).** A SessionStart hook (gated on
   ``CLAUDE_CODE_REMOTE``) that HTTPS-tarball-fetches the skills listed in
   ``.claude/web-skills.json`` into ``~/.claude/skills/`` and returns
   ``reloadSkills: true`` — the documented pattern for "skills the hook installed are
   available in the same session, starting with the first prompt." Skills only (not
   agents); the leaf must equal each skill's upstream ``name:``. Use it when a team prefers
   fetch-fresh over committing copies. Wired only when chosen.

3. **Declarative ``enabledPlugins`` (best-effort).** ``.claude/settings.json`` carries
   ``extraKnownMarketplaces`` + ``enabledPlugins``; the platform installs them at session
   start *when the marketplace is reachable*, giving ``/plugin:skill`` namespacing and
   ``autoUpdate`` from **session 2+**. It is **not** a first-session guarantee (the install
   races skill enumeration — issue #63028, where the engine logs ``getSkills returning: 0
   plugin skills`` and finds the plugins ~1.5 s too late). This skill ships two bases —
   ``assets/settings.json.tmpl`` (rdl) and ``assets/settings.externals.json.tmpl`` — and
   ``assets/marketplaces.json`` as the source of truth for sources + the team-externals set.

Supporting hooks (not first-session mechanisms):

- **The portable engine** — ``.claude/scripts/install-deps.sh`` (SessionStart, gated on
  ``CLAUDE_CODE_REMOTE``). Provisions per-session CLIs (``gh``, Codex when
  ``CODEX_AUTH_JSON`` is set) and the project dev toolchain via the ``install-deps.local.sh``
  seam. **It does not touch plugins** (see below).
- **The project seam** — ``.claude/scripts/install-deps.local.sh`` (optional). Language
  toolchains, git-hook wiring, and **starting** ``dockerd`` (the web runner ships the docker
  CLI + daemon binary but **no running daemon and no systemd**).

The chain to keep in mind: **declared ≠ installed ≠ surfaced.**
``announce-capabilities.sh`` cross-checks ``claude plugin list`` and reports **"Enabled
plugins (installed)"** vs **"⚠️ Declared but NOT installed"**, so a reachability failure is
surfaced, never masked.


Why there is no plugin self-heal (``ensure_plugins`` was removed)
================================================================

``install-deps.sh`` used to carry an ``ensure_plugins`` self-heal — it registered declared
marketplaces (with an HTTPS-tarball local-path fallback for the git-403), refreshed a stale
index, and retried ``claude plugin install``. **It was removed**, because it could not do the
one thing that would justify it:

- **It cannot surface a plugin the session it installs.** The install lands in the plugin
  cache, which ``reloadSkills`` does not re-scan, and a SessionStart hook cannot call
  ``/reload-plugins`` (disabled in cloud anyway). At best it helped a later resume on the
  *same* VM; the next fresh session discarded that cache.
- **It was a hang risk.** ``claude plugin install`` inside a SessionStart hook has been
  reported to hang web sessions (upstream issue #18088).

So plugins are left to the platform's declarative install (best-effort, session 2+), and
first-session availability comes from **vendoring** (route 1) — committed skills need no
install at all. ``announce-capabilities.sh`` still flags a declared-but-not-installed plugin
so the gap is visible.


Failure mode #4 — git-proxy repo-scoping (the 403)
==================================================

The one most likely to be misread as a network-policy problem. In a cloud session
**all GitHub git traffic is rewritten through an in-sandbox proxy** that injects a
scoped credential (``url.http://local_proxy@127.0.0.1:<port>/git/.insteadof =
https://github.com/``). That proxy authorizes git operations **only against the
session's own working repo**. Reproduced directly with ``git ls-remote``:

==========================================  ======
target                                      result
==========================================  ======
the session's own repo                      200
a **different repo in the same org**        **403**
an unrelated **public** repo                **403**
``anthropics/claude-plugins-official``      **403**
==========================================  ======

…while ordinary HTTPS to those *same* repos succeeds — ``raw.githubusercontent.com``,
``codeload.github.com`` (tarball), and ``api.github.com`` all return **200** (all on
the default Trusted allowlist). So the block is specific to the **git smart-HTTP
protocol on a non-session repo**, not the host.

Two facts make this its own failure mode, distinct from "unreachable source":

- **It is independent of the network-access level.** The web docs state *"GitHub
  operations use a separate proxy that is independent of this setting."* Switching the
  environment to **Full** network access does **not** change it — confirmed.
- **A GitHub token does not fix it.** ``claude plugin marketplace add owner/repo`` is a
  ``git clone``; the in-sandbox git client authenticates via the proxy's scoped
  credential, not ``GH_TOKEN`` (*"your token never enters the container"*). Embedding a
  token in a relay-bypassing git URL still 403s. ``GH_TOKEN`` only helps the **non-git**
  HTTPS paths (the tarball fetch, ``gh api``) — useful for the workaround, not the clone.

The consequence: ``claude plugin marketplace add owner/repo`` works **only** when the
source repo *is* the session repo. Every external marketplace 403s over git. Both escape
routes fetch over **HTTPS** (api.github.com tarball → codeload), never git:

1. **Vendor into ``.claude/skills/``** (below) — the robust, first-session path (commit the
   fetched skills; works for every repo including name-reserved ``claude-plugins-official``).
2. **``bootstrap-web.sh``** — the opt-in hook fetches the same way into ``~/.claude/skills/``
   and triggers ``reloadSkills`` (same session, not committed).


Vendoring third-party plugin content
====================================

The only route the proxy cannot block, and the **only** route for the name-reserved
``claude-plugins-official`` plugins (``superpowers``, ``pr-review-toolkit``,
``gopls-lsp``, ``skill-creator``, ``plugin-dev``). Per the "what carries over" table,
``.claude/skills/`` / ``.claude/agents/`` / ``.claude/commands/`` carry over because they
are *part of the clone* — no proxy, no git, no marketplace, available the **first**
session. Fetch upstream over HTTPS (not git), copy in only the skills you want, commit:

.. code-block:: bash

   # api.github.com/repos/<owner>/<repo>/tarball[/<ref>] → codeload (both allowlisted).
   # Add `-H "Authorization: Bearer $GH_TOKEN"` only for a PRIVATE marketplace.
   ext="$(mktemp -d)"; tgz="$(mktemp)"
   # Download to a file first rather than piping curl into tar (inspectable; no
   # half-extracted partial download).
   curl -fsSL "https://api.github.com/repos/OWNER/REPO/tarball" -o "$tgz"
   tar -xzf "$tgz" -C "$ext" --strip-components=1
   cp -R "$ext/plugins/<plugin>/skills/<skill>" .claude/skills/<skill>
   git add .claude/skills/<skill>

Trade-off: vendored copies carry the upstream license and **drift** from upstream —
refresh them deliberately. This is the model this repo already uses for its own plugins
(self-contained real-file copies under ``plugins/``).


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
  Setup-script field is only worth it for heavy **non-plugin** caching — and if it ever
  fetches plugin content it must use **HTTPS, not git** (failure mode #4), guarded with
  ``|| true``.
- **Reading the marketplace 403 as a network-policy / token problem (failure mode #4).**
  ``claude plugin marketplace add owner/repo`` 403'ing is **not** fixed by switching to
  **Full** network access (the GitHub proxy is independent of that level) nor by adding
  ``GH_TOKEN`` + ``gh auth`` (the git clone uses the proxy's scoped credential, not your
  token). It is the GitHub proxy scoping git to the session repo. Fix by **vendoring** (or
  the ``bootstrap-web.sh`` HTTPS fetch) — never by retrying the clone or widening the network.
- **Believing "the platform registers marketplaces but does not install
  enabledPlugins."** It does install them. An empty ``claude plugin list`` is a
  stale-index / unreachable-source failure **or the cold-start race below** — not a
  missing platform feature.
- **Reporting *declared* plugins as installed.** Build the banner from ``claude plugin
  list``, not from ``settings.json``, or a missing marketplace looks healthy while the
  slash menu is empty.
- **Doing plugin installs in a SessionStart hook at all.** A hook-installed plugin lands in
  the plugin cache that ``reloadSkills`` does not re-scan, so it cannot surface that session
  (and a hook cannot call ``/reload-plugins``); worse, ``claude plugin install`` in a hook has
  been reported to **hang** web sessions (issue #18088). This is why the old ``ensure_plugins``
  self-heal was removed. Make skills first-session-available by **vendoring**, not by retrying
  the declarative install from a hook.
- **Leaving ``CODEX_ACCESS_TOKEN`` set.** Codex parses it as a JWT at runtime; a
  blob/blank value breaks every later ``codex exec`` even with a valid ``auth.json``.
  Unset it in-process and via ``CLAUDE_ENV_FILE``.
- **Predictable ``/tmp`` log paths.** A symlink-truncation/race vector — use ``mktemp``
  with ``umask 077``.
