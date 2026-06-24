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

- Declaring the marketplace + plugin is the **whole mechanism** for the platform's
  session-start install. But ``github.com`` being on the *Trusted* allowlist does **not**
  make a github-sourced marketplace reachable by **git**: the in-sandbox GitHub proxy
  authorizes git only against the session's **own repo** (see "Failure mode #4" below), so
  ``claude plugin marketplace add owner/repo`` 403s for every external marketplace. The
  allowlist governs ordinary HTTPS (API, ``raw``, ``codeload``), not the git protocol.
- The failure modes are: the marketplace registry still **empty** because this hook
  outran the platform's registration of ``extraKnownMarketplaces`` on a cold VM (a
  **race**, not a network error — issue #181); the local index being **stale**; the
  source genuinely **unreachable**; or the git clone **403'd by the GitHub proxy** because
  the marketplace repo is not the session repo (failure mode #4). All four are handled by
  the self-heal (below).
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
installs the rest idempotently. When any plugin is still pending it **first registers
every declared marketplace** with ``claude plugin marketplace add`` (idempotent — a
no-op once on disk), so it never depends on the platform having registered
``extraKnownMarketplaces`` first (the cold-start race, issue #181). A GitHub source
pins its ref as ``owner/repo@ref`` (a git URL as ``<git-url>#ref``); a source carrying
a custom ``path`` (a non-default ``marketplace.json``) has no ``marketplace add``
equivalent and is **skipped**, left to declarative registration. When a GitHub
``marketplace add`` **fails** — overwhelmingly the proxy 403 of failure mode #4 — it
falls back to ``register_marketplace_via_tarball``: fetch the marketplace over HTTPS
(``api.github.com/repos/<owner>/<repo>/tarball`` → ``codeload``, both allowlisted),
extract to a stable cache dir, and ``claude plugin marketplace add <local-dir>`` — a
**local-path** registration that never invokes git. The name-reserved
``claude-plugins-official`` is the one exception (the CLI rejects a local-path source
for it); it short-circuits with a vendoring pointer. On a failed install it then
derives the marketplace from the ``@`` suffix, runs ``claude plugin marketplace
update <mkt>`` (the refresh ``claude plugin install`` does **not** do itself — the
stale-index failure mode), and retries once, refreshing each marketplace at most once
per run. The hook owns the whole **add → update → install** chain so it assumes no
platform-side state; gated on a pending count, a warm resume is a silent no-op.

A plugin the self-heal installs **surfaces from the *next* session**: Claude
enumerates skills at startup, *before* SessionStart hooks run, and ``reloadSkills``
empirically *appears* to re-scan only loose ``~/.claude/skills/``, not the plugin
install cache (unconfirmed upstream — see ``docs/notes/claude-code-web-issues.md``).


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
source repo *is* the session repo. Every external marketplace 403s. Two escape routes:

1. **Vendor into ``.claude/skills/``** (below) — the robust, first-session path.
2. **The self-heal's HTTPS-tarball fallback** (above) — works for every marketplace
   except the name-reserved ``claude-plugins-official``.


Failure mode #5 — the non-existent plugin id (dataops#169)
==========================================================

Distinct from #4: here the marketplace *is* reachable and declared, but the **plugin
name does not exist in it**. A hallucinated id — ``pyright-lsp@claude-plugins-official``,
a guessed ``ty-lsp@astral-sh``, ``<lang>-lsp``, or a subject id reconstructed from memory
— is declared in ``enabledPlugins``, installs **nothing**, and shows up as "Declared but
NOT installed" every session. Unlike #4 (which clears on the next session via the
self-heal or by vendoring), a non-existent id **never** resolves: there is nothing to
install.

Why the existing guards miss it: ``web-settings.sh cover`` and ``ensure`` only check that
each id's ``@marketplace`` **suffix** is declared/known — never that the plugin **name**
exists in that marketplace's catalog. So a real-marketplace + fake-name id passes both.

Root cause: the ``marketplace-scout`` agent (or the model) recommending/writing an id it
did **not** read from a fetched ``marketplace.json`` or the curated ``marketplaces.json``
— typically after a catalog fetch failed and it filled the gap from memory.

The defences (all shipped here):

- **``web-settings.sh verify <settings.json>``** — fetches each marketplace's catalog and
  prints any enabled id absent from it (exit 1, stdout). Ids whose marketplace is
  *unreachable* are reported on stderr as *unverifiable* (it never fails on those — that is
  #4, not #5). Run in SKILL Phase 2 (step 5) and Phase 4.
- **The ``web-setup-plugin-check`` PostToolUse hook** (shipped in the ``claude-code``
  plugin) — runs ``verify`` automatically whenever ``.claude/settings.json`` is written
  during a setup session and injects an advisory telling the model to fix the bad ids.
- **The scout's no-guessing rule** — never recommend an id not traceable to a catalog it
  actually read; if a fetch failed, recommend only the curated ids and say so.


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
  token). It is the GitHub proxy scoping git to the session repo. Fix by **vendoring** or
  the HTTPS-tarball fallback — never by retrying the clone or widening the network level.
- **Believing "the platform registers marketplaces but does not install
  enabledPlugins."** It does install them. An empty ``claude plugin list`` is a
  stale-index / unreachable-source failure **or the cold-start race below** — not a
  missing platform feature.
- **Reporting *declared* plugins as installed.** Build the banner from ``claude plugin
  list``, not from ``settings.json``, or a missing marketplace looks healthy while the
  slash menu is empty.
- **A naive ``claude plugin install`` retry without ``marketplace update``.** On a
  cold VM the index can be stale; the retry re-hits the same stale index forever unless
  it refreshes.
- **Assuming ``extraKnownMarketplaces`` is already registered when the SessionStart
  hook runs (issue #181).** On a cold VM this hook can outrun that registration, so the
  registry is **empty** and ``claude plugin install`` *and* ``claude plugin marketplace
  update`` both fail with ``Marketplace not found. Available marketplaces:`` (an empty
  list) — **not** a network failure, and it must not be reported as one. The self-heal
  must ``claude plugin marketplace add`` every declared marketplace itself and own the
  whole add → update → install chain, assuming no platform-side state.
- **Leaving ``CODEX_ACCESS_TOKEN`` set.** Codex parses it as a JWT at runtime; a
  blob/blank value breaks every later ``codex exec`` even with a valid ``auth.json``.
  Unset it in-process and via ``CLAUDE_ENV_FILE``.
- **Predictable ``/tmp`` log paths.** A symlink-truncation/race vector — use ``mktemp``
  with ``umask 077``.
