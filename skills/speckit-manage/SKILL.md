---
name: speckit-manage
license: CC-BY-4.0
compatibility: "spec-kit >=0.12; `specify extension` CLI; re-verify at github.github.io/spec-kit"
description: >-
  Install, list, enable/disable, update, and configure GitHub spec-kit extensions,
  and manage the catalog stack. Use when running `specify extension` commands,
  wiring a team/internal catalog, resolving the PyPI specify-cli install footgun,
  configuring .specify/extension-catalogs.yml or extensions.yml, or when the user
  runs /speckit-dev:manage.
argument-hint: "What to manage? (e.g. 'install jira from our team catalog', 'add an internal catalog')"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Manage spec-kit extensions

> **Verify-canonical guard.** CLI flags/behavior are pinned to v0.12.x
> (2026-07-04). Confirm against `references/cli-and-catalogs.rst` and the live
> [extensions reference](https://github.github.io/spec-kit/reference/extensions.html)
> and [user guide](https://raw.githubusercontent.com/github/spec-kit/main/extensions/EXTENSION-USER-GUIDE.md).

## Install spec-kit correctly (footgun)

`uv tool install specify-cli --from git+https://github.com/github/spec-kit.git`
Plain `pip install specify-cli` from PyPI is an **unrelated stub** without the
`extension`/`preset` commands.

## CLI surface

| Command | Purpose | Key flags |
|---|---|---|
| `specify extension search [q]` | search catalogs | `--tag --author --verified` |
| `specify extension add <name>` | install | `--dev <path>`, `--from <url>`, `--force`, `--priority N` |
| `specify extension remove <name>` | uninstall | `--keep-config`, `--force` |
| `specify extension list` | installed | `--available`, `--all` |
| `specify extension info <name>` | details | |
| `specify extension update [name]` | update one/all | |
| `specify extension enable/disable <name>` | toggle | |
| `specify extension set-priority <name> <N>` | resolution order | |
| `specify extension catalog list/add/remove` | manage catalogs | add: `--name --priority --install-allowed` |

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
