======================================
Claude Code on the web — setup reference
======================================

Authoritative facts, the layered architecture, and the anti-patterns behind the
``cc-web-setup`` skill. Read this before bootstrapping an unfamiliar repo or when
debugging a plugin that is *declared* but never *installs*.

Companion docs in the repo:

- ``docs/claude-code-web.md`` — the reader-facing "how this repo's setup works" overview
  (the invariant, the first-session route, why there is no self-heal, the constraints).
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
Vendoring puts skills where they are visible first; the declarative plugin path is a
best-effort layer on top.

1. **Vendoring (the first-session route).** Commit the chosen skills into
   ``.claude/skills/`` and agents into ``.claude/agents/`` (commands into
   ``.claude/commands/``). Per the "what carries over" table these are *part of the clone*
   — present at startup, before enumeration, with no proxy/git/marketplace. The robust
   path and the **only** route for the name-reserved ``claude-plugins-official`` skills.
   Self-contained real files (no symlinks, no ``${CLAUDE_PLUGIN_ROOT}``/sibling/bundled-
   component dependencies), pinned to a commit SHA, provenance recorded.

2. **Declarative ``enabledPlugins`` (best-effort config).** ``.claude/settings.json`` carries
   ``extraKnownMarketplaces`` + ``enabledPlugins``. This is the only way to ask for a plugin
   that ships real **behavior** — bundled hooks, an MCP server, an LSP — which a loose
   vendored skill cannot provide. But its **web activation is unverified**, for three
   compounding reasons: external marketplaces 403 over the git proxy (failure mode #4); the
   session-start install races skill enumeration (issue #63028, where the engine logs
   ``getSkills returning: 0 plugin skills`` and finds the plugins ~1.5 s too late); and the
   sandbox is ephemeral, so the cache an install would populate is discarded before the next
   session — even "session 2+" inheritance is unproven. Treat it as necessary config for
   plugin-behavior picks, **not** a delivery route, until a clean-cloud lifecycle test
   (install → restart → reuse) proves activation. This skill ships two bases —
   ``assets/settings.json.tmpl`` (rdl-agent-extensions) and ``assets/settings.externals.json.tmpl`` — and
   ``assets/marketplaces.json`` as the source of truth for sources + the team-externals set.

For the rare skill a team cannot commit, see "Escape hatch — fetch without committing" below;
it is the only non-vendoring way to get a *skill* (not plugin behavior) onto a session, and it
trades the first-session guarantee for not committing copies.

Supporting hooks (not first-session mechanisms):

- **The portable engine** — ``.claude/scripts/install-deps.sh`` (SessionStart, gated on
  ``CLAUDE_CODE_REMOTE``). Provisions per-session CLIs (``gh``, Codex when
  ``CODEX_AUTH_JSON`` is set) and the project dev toolchain via the ``install-deps.local.sh``
  seam. **It does not touch plugins** (see below).
- **The project seam** — ``.claude/scripts/install-deps.local.sh`` (optional). Language
  toolchains, git-hook wiring, and **starting** ``dockerd`` (the web runner ships the docker
  CLI + daemon binary but **no running daemon and no systemd**).

The chain to keep in mind: **declared ≠ installed ≠ surfaced.**
``announce-capabilities.sh`` cross-checks ``claude plugin list --json`` and reports **"Enabled
plugins (installed/enabled)"** vs **"⚠️ Declared but NOT installed"** (and **"install
unverified"** when the CLI cannot be queried), so a reachability failure is surfaced, never
masked. "Installed" confirms install, not in-process activation.


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

So plugins are left to the platform's declarative install (best-effort config, web-activation
unverified), and first-session availability comes from **vendoring** — committed skills need no
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
source repo *is* the session repo. Every external marketplace 403s over git. The escape
fetches over **HTTPS** (api.github.com tarball → codeload), never git:

- **Vendor into ``.claude/skills/``** (below) — the robust, first-session path (commit the
  fetched skills; works for every repo including name-reserved ``claude-plugins-official``).
  The same HTTPS fetch, run at session start into ``~/.claude/skills/`` instead of committed,
  is the "Escape hatch" below — for the rare skill a team cannot commit.


Failure mode #5 — the non-existent plugin id (dataops#169)
==========================================================

Distinct from #4: here the marketplace *is* reachable and declared, but the **plugin
name does not exist in it**. A hallucinated id — ``pyright-lsp@claude-plugins-official``,
a guessed ``ty-lsp@astral-sh``, ``<lang>-lsp``, or a subject id reconstructed from memory
— is declared in ``enabledPlugins``, installs **nothing**, and shows up as "Declared but
NOT installed" every session. Unlike #4 (which **vendoring** resolves first-session — no
install needed), a non-existent id **never** resolves: there is nothing to install, so the
id itself must be corrected.

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
   # Fail CLOSED if the path is wrong, then refuse a tree with symlinks (they can point
   # outside it). For an UNTRUSTED source use the hardened fetch_skill below.
   src="$ext/plugins/<plugin>/skills/<skill>"
   [ -f "$src/SKILL.md" ] || { echo "no SKILL.md at <skill>; refusing"; exit 1; }
   find "$src" -type l -print -quit | grep -q . && { echo "skill has symlinks; refusing"; exit 1; }
   cp -R "$src" .claude/skills/<skill>
   git add .claude/skills/<skill>

Trade-off: vendored copies carry the upstream license and **drift** from upstream —
refresh them deliberately. This is the model this repo already uses for its own plugins
(self-contained real-file copies under ``plugins/``).


Escape hatch — fetch without committing (advanced)
==================================================

For almost every repo, **vendoring is the answer** — stop here. Reach for this only when a
team is contractually barred from committing a skill's contents (consume-but-not-redistribute)
or the skill is too large to vendor. It is the *only* non-vendoring way to get a **skill**
(not plugin behavior) onto a session, and it **forfeits the first-session guarantee**: skills
land via the same-session re-scan, not the clone.

There is **no shipped script** — wire the manual pattern into the project's existing
``CLAUDE_CODE_REMOTE``-gated SessionStart hook (or run it once by hand and ``/reload-skills``):

.. code-block:: bash

   # Fetch ONE skill over HTTPS (never git — failure mode #4) into ~/.claude/skills/<leaf>/.
   # Runs inside ( ) so a failure returns non-zero WITHOUT killing the host SessionStart hook
   # (do not put `set -e` in the caller). Validates <leaf> BEFORE any rm — an empty or
   # traversal value would otherwise let `rm -rf` delete the wrong directory.
   fetch_skill() (
     leaf="$1"; repo="$2"; ref="$3"; src="$4"   # src = path to the skill within the repo tarball
     case "$leaf" in ''|*[!A-Za-z0-9-]*|-*|*-)
       echo "refusing invalid leaf '$leaf' (ASCII alnum + interior hyphens only)" >&2; return 2 ;;
     esac
     ext="$(mktemp -d)" && tgz="$(mktemp)" || return 1
     trap 'rm -rf "$ext" "$tgz"' EXIT   # fires when this ( ) subshell-function returns
     curl -fsSL "https://api.github.com/repos/${repo}/tarball/${ref}" -o "$tgz" || return 1
     tar -xzf "$tgz" -C "$ext" --strip-components=1 || return 1
     # Refuse a symlink at ANY component of $src under $ext, not just the final dir: an
     # intermediate symlink (src "link/skill") would let cp -R follow it OUTSIDE the tarball,
     # and the post-copy `find -type l` can't catch it (the copied files are real). Split with
     # parameter expansion so a */?/[ component can't word-split or glob-evade the walk, and
     # reject `.`/`..` components, which would otherwise let `$src` escape `$ext`.
     walk="$ext"; rest="$src"
     while [ -n "$rest" ]; do
       seg="${rest%%/*}"; case "$rest" in */*) rest="${rest#*/}" ;; *) rest="" ;; esac
       [ -n "$seg" ] || continue
       case "$seg" in .|..) echo "path component '$seg' in '$src' not allowed; refusing" >&2; return 1 ;; esac
       walk="${walk}/${seg}"
       [ -L "$walk" ] && { echo "path component '$seg' under '$src' is a symlink; refusing" >&2; return 1; }
     done
     [ -f "$ext/$src/SKILL.md" ] || { echo "no SKILL.md under '$src'" >&2; return 1; }
     find "$ext/$src" -type l -print -quit | grep -q . && { echo "skill has symlinks; refusing" >&2; return 1; }
     # Read name: from the YAML frontmatter block only (first ---…--- fence), not the body.
     name="$(awk 'NR==1 && $0=="---"{f=1; next} f && $0=="---"{exit} f' "$ext/$src/SKILL.md" \
               | sed -n 's/^name:[[:space:]]*//p' | head -1)"
     [ "$name" = "$leaf" ] || { echo "frontmatter name '$name' != leaf '$leaf'; refusing" >&2; return 1; }
     mkdir -p "$HOME/.claude/skills" || return 1
     # Stage to a temp dir first, so a failed COPY never deletes the existing skill. Then move
     # any existing version ASIDE before swapping the new one in, so a failed mv rolls back to
     # it instead of leaving the skill missing. The swap is not atomic (replacing a directory
     # can't be one rename) and uses fixed .tmp/.old paths, so do not run two fetches for the
     # same <leaf> concurrently — fine for a SessionStart fetch before the first turn.
     dest="$HOME/.claude/skills/$leaf"
     staged="$HOME/.claude/skills/.$leaf.tmp"; old="$HOME/.claude/skills/.$leaf.old"
     rm -rf "$staged" "$old"
     cp -R "$ext/$src" "$staged" || return 1
     [ -e "$dest" ] && { mv "$dest" "$old" || return 1; }
     mv "$staged" "$dest" || { [ -e "$old" ] && mv "$old" "$dest"; return 1; }
     rm -rf "$old"
   )
   # <leaf> MUST equal the skill's upstream frontmatter name: (enforced above).
   fetch_skill "superpowers" "OWNER/REPO" "<immutable-commit-sha>" "plugins/<plugin>/skills/<skill>" || \
     echo "escape-hatch fetch failed; continuing" >&2

A SessionStart hook that fetches before the first turn must return ``reloadSkills: true`` so
the skills register the same session (the documented same-session re-scan). Caveats: it
fetches over the network each session (latency); covers **skills only** (agents/commands must
be vendored); a pinned SHA is reproducible but not "fresh", a moving ref is fresh but adds
supply-chain drift; and fetching does not resolve any upstream licensing the team must honor.


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

- **Self-referential / meta marketplace in its own dev env.** Enabling ``rdl@rdl-agent-extensions``
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
  the HTTPS-fetch escape hatch) — never by retrying the clone or widening the network.
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
