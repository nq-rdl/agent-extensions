# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Does

Packages agent skills from `nq-rdl/agent-skills` for four runtimes: **Claude Code**, **Gemini CLI**, **pi.dev**, and **OpenCode**. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

## Commands

```bash
# Validate Claude Code plugin manifests and hooks
scripts/validate-plugin-hooks.sh

# MCP servers (TypeScript/Bun) — run from mcp/pi-rpc or mcp/gemini-cli
bun test
bun run typecheck
bun run start

# pi-server Go binary
cd skills/pi-rpc/scripts && make build        # local
make cross-compile DESTDIR=../../../plugins/dev-tools/bin  # CI target
make test && make generate                    # test / regen protobuf (requires buf)

# Changelog
changie new            # new entry → .changes/unreleased/
changie batch 0.4.0    # batch unreleased → .changes/0.4.0.md
changie merge          # regenerate CHANGELOG.md

# Docs site
pixi run zensical serve
```

## Key Non-Obvious Facts

- **Skills are vendored, not a live submodule.** `skills/` is synced from `nq-rdl/agent-skills` via `sync-skills.yml`; never edit it by hand.
- **Symlinks, not copies.** `plugins/<bundle>/skills/<skill>` symlinks into `../../../skills/<skill>`. Claude Code follows symlinks at install time — do not break them.
- **Go binaries are committed.** `plugins/dev-tools/bin/pi-server-<os>-<arch>` are pre-built artifacts checked in. They rebuild automatically when `skills/pi-rpc/scripts/**` changes (CI: `build-pi-server.yml`).
- **Release = push a `v*` tag.** CI batches the changelog, bumps version in all JSON/TOML manifests, commits back to `main`, then creates the GitHub release.
- **`registry/bundles/*.yaml` is the source of truth** for which skills belong to which bundle and which platforms are enabled. The CI `validate.yml` cross-checks every skill name against `skills/`.
- **Local install for testing.** Inside the devcontainer: `claude plugin marketplace add /workspace` then `claude plugin install <bundle>@rdl`. For single-session in-place testing use `claude --plugin-dir ./plugins/<bundle>`. See [`docs/local-testing.md`](docs/local-testing.md).

## Docs

| File | Contents |
|------|----------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full platform model, bundle registry schema, CI/release design, exact install flows |
| [`docs/bundles.md`](docs/bundles.md) | Bundle definitions and skill groupings |
| [`docs/claude.md`](docs/claude.md) | Claude Code-specific plugin wiring |
| [`docs/gemini-cli.md`](docs/gemini-cli.md) | Gemini CLI extension packaging |
| [`docs/pidev.md`](docs/pidev.md) | pi.dev package structure |
| [`docs/local-testing.md`](docs/local-testing.md) | Install the marketplace locally / in a devcontainer to verify skills are visible before release |
