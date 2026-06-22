---
name: cc-web-setup
license: CC-BY-4.0
description: >-
  Bootstrap a repository for Claude Code on the web — provision its `.claude/`
  setup so cloud sessions are correctly configured. Use when the user wants to
  "set up Claude Code on the web", "bootstrap web sessions", "add the web setup
  scripts", "configure the SessionStart hook for cloud", "provision a cloud
  environment", "install web-bootstrap", or "make this repo work with Claude
  Code on the web". Installs a parameterized `.claude/settings.json` plus
  portable `scripts/web-bootstrap.sh` (SessionStart hook), `scripts/cc-web-setup.sh`
  (pre-snapshot setup script that pre-seeds the RDL marketplace), and
  `scripts/announce-capabilities.sh`. Also covers the setup-script-vs-SessionStart
  split, the `CLAUDE_CODE_REMOTE` gate, GH/Codex CLI provisioning, and the
  `*.local.sh` extension seam for project-specific dependencies.
argument-hint: "Bootstrap this repo for Claude Code on the web? (run from the repo root; say if you have an existing .claude/settings.json to merge)"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Bootstrap a repo for Claude Code on the web

Your job is to provision the current repository so **Claude Code on the web** (cloud)
sessions start correctly configured: the RDL marketplace registered and pre-seeded,
the GitHub and Codex CLIs available, and a SessionStart hook that self-heals and
persists tooling. The portable pieces ship as files in this skill's `assets/`
directory; you copy them into the target repo and merge the settings idempotently.

## Background you must understand before acting

The hard fact this whole setup works around: **Claude Code enumerates plugin skills and
slash-commands at process startup, BEFORE `SessionStart` hooks finish**
([hooks docs](https://code.claude.com/docs/en/hooks)). So a plugin a hook installs would,
by default, only surface its `/<plugin>:<skill>` commands on the *next* session. There are
two committed levers to beat that, and **the SessionStart hook is the primary one** — it
needs **no** manual, non-committable environment setting:

1. **SessionStart hook (PRIMARY — committed, zero manual setup).** `scripts/web-bootstrap.sh`
   runs **every session**, gated on `CLAUDE_CODE_REMOTE=true` (a no-op on a contributor's
   laptop). On a cloud session it installs the declared marketplaces/plugins
   (`scripts/cc-web-setup.sh`), and then `scripts/announce-capabilities.sh` (which runs
   *after* it) returns `reloadSkills: true`, which asks Claude Code to **re-scan the skill
   and command directories once all SessionStart hooks return** — so freshly-installed
   skills can surface *this* session, not next. This is the idiomatic, all-in-repo answer:
   "if `CLAUDE_CODE_REMOTE`, install + reload."
2. **Setup script (OPTIONAL fallback — guaranteed first-session).** Bash that runs **once,
   before Claude starts**, whose filesystem is captured in the environment snapshot.
   Configured in the web environment's settings UI (not the repo); it runs
   `scripts/cc-web-setup.sh` via the **Setup script** field set to `make cc-web-setup`.
   Because it installs *before* enumeration, plugin skills are guaranteed present on the
   first session.

> **Caveat to convey honestly.** The docs document the `reloadSkills` re-scan for loose
> `~/.claude/skills/` skills; whether it also re-scans **plugin-cache** skills (installed
> via `claude plugin install`) is **unconfirmed upstream**. If a team observes that plugin
> skills still only appear from the *second* session, the Setup-script fallback (lever 2)
> is the guaranteed fix. Track this as an upstream issue. Either way, lever 1 requires no
> manual step, so it is what you wire by default.

## Phase 0 — Confirm context

- Confirm you are at the **repo root** of the repo to bootstrap (a `.git` dir is present).
- Check whether `.claude/settings.json`, `scripts/`, and `Makefile` already exist — this
  decides create-fresh vs. merge for each.
- Ask the user only if something is ambiguous (e.g. a pre-existing `settings.json` with a
  conflicting `model`/`hooks` block). Otherwise proceed with the defaults below.

## Phase 1 — Copy the portable scripts

Copy these three files from this skill's `assets/` into the target repo's `scripts/`,
creating `scripts/` if absent, and `chmod +x` each:

| From (skill asset) | To (target repo) |
|---|---|
| `assets/web-bootstrap.sh` | `scripts/web-bootstrap.sh` |
| `assets/cc-web-setup.sh` | `scripts/cc-web-setup.sh` |
| `assets/announce-capabilities.sh` | `scripts/announce-capabilities.sh` |

These are **portable and carry no project-specific dependencies** — do not edit them per
project. Project specifics go in the optional `*.local.sh` seam (Phase 4).

If a target file already exists and differs, show the diff and ask before overwriting.

## Phase 2 — Merge `.claude/settings.json`

The template is `assets/settings.json.tmpl`. It registers the **`rdl`** marketplace
(`nq-rdl/agent-extensions`), enables **`rdl@rdl`** (the meta-plugin that installs every
RDL subject plugin), wires the two SessionStart hooks, and sets opinionated defaults
(`model: opus`, `alwaysThinkingEnabled`, `effortLevel: xhigh`,
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`).

- **If `.claude/settings.json` is absent:** create `.claude/` and write the template verbatim.
- **If it exists:** perform an **idempotent JSON-aware deep-merge** (use `jq` or a careful
  read-modify-write), and **show the diff before writing**:
  - `env`: add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` without clobbering other keys.
  - `hooks.SessionStart`: find (or create) the `startup|resume` matcher group; append the
    two hook commands **only if not already present** (dedupe by exact command string), so
    re-running is a no-op.
  - `enabledPlugins`: add `"rdl@rdl": true`.
  - `extraKnownMarketplaces`: add the `rdl` entry; leave any existing marketplaces intact.
  - `model` / `alwaysThinkingEnabled` / `effortLevel`: set **only if absent** — never
    override a deliberate user choice. Mention they are opinionated defaults the user can
    decline.
  - If a stale `"superpowers@claude-plugins-official"` (or other migrated-away entry) is
    present, point it out and offer to remove it.

## Phase 3 — Merge the Makefile target

Append `assets/Makefile.snippet` to the repo's `Makefile` **only if** a `cc-web-setup:`
target is not already present. If there is no `Makefile`, create one containing just the
snippet. This gives the user the `make cc-web-setup` entrypoint to set as the environment
Setup script.

## Phase 4 — Offer the project extension seam

The portable scripts source two optional, project-owned hooks if present:
`scripts/cc-web-setup.local.sh` (heavy pre-snapshot deps) and `scripts/web-bootstrap.local.sh`
(per-session glue: language toolchains on PATH, container runtimes, git-hook wiring like
`.husky`/`.githooks`/lefthook, fetching the default branch). This is the **only** sanctioned
place for project-specific provisioning — keep it out of the portable scripts so they stay
re-syncable.

Offer to scaffold a commented `scripts/web-bootstrap.local.sh` from
`assets/web-bootstrap.local.sh.example`. Do **not** create it unless the repo actually needs
project-specific steps.

### Docker on Claude Code on the web

A web runner is **not** a laptop: it ships the `docker` CLI and the `dockerd`
binary but **no running daemon**, and there is **no systemd / service manager**
to start one. On a developer machine Docker Desktop (or a systemd unit) keeps
`dockerd` up; in a cloud session nothing does. So any repo that needs containers
in a web session — devcontainer smoke tests, `testcontainers`, k3d/k8s-in-docker,
building images — **must start `dockerd` itself**.

This is per-session, project-specific work, so it belongs in the `web-bootstrap.local.sh`
seam, **not** in the portable engine (not every repo wants Docker) and **not** in the
pre-snapshot setup script (a daemon is runtime state, not snapshot filesystem state — it
does not survive into a new session). The portable `web-bootstrap.sh` exposes the `$SUDO`
global specifically so the local hook can start daemons like this. The pattern (proven in
DataOps and shipped commented in `assets/web-bootstrap.local.sh.example`):

```bash
ensure_docker() {
  command -v dockerd >/dev/null 2>&1 || return 0   # Docker not provisioned here.
  docker info >/dev/null 2>&1 && return 0           # Already up.
  # shellcheck disable=SC2086  # $SUDO word-splits into argv ('' as root, 'sudo -n' otherwise)
  nohup $SUDO dockerd >>"$LOG" 2>&1 &               # nohup+bg: outlive the sourced subshell
  local i; for i in $(seq 1 30); do docker info >/dev/null 2>&1 && return 0; sleep 1; done
  log "WARNING: dockerd did not become ready within 30s (see ${LOG})."; return 1
}
ensure_docker || true
```

Key points to convey:

- **Idempotent + non-fatal.** No-op when `docker info` already answers (a resume, or a base
  image that started it); a runner lacking the privileges/cgroups to run `dockerd` logs a
  warning and the session continues without containers — never fail the parent hook.
- **`nohup … &`** so the daemon outlives the subshell the parent hook sources the local hook
  in (a reparented-to-init `dockerd` keeps serving later Bash tool turns).
- **`$SUDO`** is empty when the session already runs as root and `sudo -n` under an
  unprivileged `remoteUser` (e.g. the devcontainer `node` user) — leave it unquoted so
  `sudo -n` splits into argv.
- **Poll the socket.** `dockerd` needs a second or two to create `/var/run/docker.sock`;
  return only once `docker info` succeeds so the next step does not race a half-up daemon.

## Phase 5 — Verify

- Run `CLAUDE_CODE_REMOTE=true bash scripts/web-bootstrap.sh` and confirm it exits 0. (Cloud
  tooling installs may warn if offline — that is fine; the hook must still exit 0.)
- Run `bash scripts/web-bootstrap.sh` (no env var) and confirm it is an immediate no-op.
- Confirm `bash scripts/cc-web-setup.sh` is sentinel-/idempotent — a second run changes nothing.
- Validate `.claude/settings.json` parses (`jq . .claude/settings.json`).

## Phase 6 — Summarize for the user

Tell the user, concisely:
- What was created/merged (list the files + the settings keys touched).
- **No manual step is required.** The committed SessionStart hook installs the plugins on
  every cloud session (gated on `CLAUDE_CODE_REMOTE`) and requests a same-session re-scan
  via `reloadSkills: true`, so skills surface without touching the web environment UI.
- **Optional fallback:** *only if* plugin skills still appear from the second session
  (i.e. the `reloadSkills` re-scan does not reach the plugin cache), set the web
  environment's **Setup script** field to `make cc-web-setup` to bake the plugins into the
  snapshot before enumeration — a guaranteed first-session fix. Frame this as a fallback,
  not a required step.
- That `web-bootstrap.sh` is safe locally (no-op unless `CLAUDE_CODE_REMOTE=true`).
- How to add project-specific deps via `scripts/*.local.sh`.
- That Codex CLI provisioning activates only when `CODEX_AUTH_JSON` or `CODEX_ACCESS_TOKEN`
  is set in the environment.
- To commit the new files so cloud sessions (which clone the repo) pick them up.
