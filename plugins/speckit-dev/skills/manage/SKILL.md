---
license: CC-BY-4.0
compatibility: "spec-kit >=0.12; `specify extension` CLI; re-verify at github.github.io/spec-kit"
description: >-
  Install, list, enable/disable, update, and configure GitHub spec-kit extensions,
  and manage the catalog stack. Use when running `specify extension` commands,
  wiring a team/internal catalog, installing spec-kit itself,
  configuring .specify/extension-catalogs.yml or extensions.yml, or when the user
  runs /speckit-dev:manage.
argument-hint: "What to manage? (e.g. 'install jira from our team catalog', 'add an internal catalog')"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Manage spec-kit extensions

> **Verify-canonical guard.** CLI semantics below were re-verified against
> v1.0.12 source (2026-09-28); flags drift, so `--help` is authoritative. Confirm
> against `references/cli-and-catalogs.rst` and the live
> [extensions reference](https://github.github.io/spec-kit/reference/extensions.html)
> and [user guide](https://raw.githubusercontent.com/github/spec-kit/main/extensions/EXTENSION-USER-GUIDE.md).

## Install spec-kit

PyPI `specify-cli` and a pinned GitHub tag are both official install routes
(uv, pipx, or pip). Follow the
[installation guide](https://github.github.io/spec-kit/installation.html);
`specify version` confirms the CLI is on `PATH`.

## CLI surface

Run `specify extension --help`, `specify extension <cmd> --help`, and
`specify extension catalog --help` for the current commands and flags.
Non-obvious semantics:

- `add <path> --dev` — `--dev` is a boolean; the positional is the local
  directory. `--from <url>` installs from a URL, bypassing catalog lookup.
- Priority (`add --priority`, `set-priority <name> <N>`, `catalog add --priority`)
  — lower number wins; default 10.
- `list` shows installed extensions, enabled or disabled; browse catalogs with
  `search`. `list --json` emits installed extensions for scripting.
- `update` with no name updates every installed extension.
- `catalog add <https-url> --name <n>` writes the project
  `.specify/extension-catalogs.yml`. It is **discovery-only by default**; pass
  `--install-allowed` only for a catalog you own and vet. The built-in community
  catalog is discovery-only: vet an entry, then `add <name> --from <url>`.

## Catalog stack (precedence)

`SPECKIT_CATALOG_URL` env → project `.specify/extension-catalogs.yml` → user
`~/.specify/extension-catalogs.yml` → built-in defaults (official +
community). Lower `priority` number wins on id conflicts. See
`assets/extension-catalogs.yml` for wiring a team catalog with
`install_allowed: true`.

## Config precedence (per extension)

extension defaults → `<ext>-config.yml` → `<ext>-config.local.yml` →
`SPECKIT_<EXT>_*` env.

## Commit vs gitignore

Commit `.specify/extensions.yml` + `<ext>-config.yml`. Gitignore
`.specify/extensions/.cache/`, `.backup/`, `*.local.yml`, `.registry`.

## Canonical sources

See `references/cli-and-catalogs.rst` and `references/canonical-sources.rst`.
