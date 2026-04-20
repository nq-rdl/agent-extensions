---
icon: lucide/package-check
---

# Local Marketplace Testing

How to install this repo as a local Claude Code marketplace to verify skills are visible before release.

## TL;DR

Single-session in-place test (no persistence, no cache copy):

```bash
claude --plugin-dir ./plugins/swe
```

Skills from that bundle are immediately available in the session. Nothing is written to `~/.claude`.

## Devcontainer Quickstart

Inside the devcontainer the repo is mounted at `/workspace` and `CLAUDE_CONFIG_DIR=/home/node/.claude`. Run:

```bash
# Validate manifests first — catch schema errors before install
claude plugin validate /workspace

# Register the local repo as a marketplace named "rdl"
claude plugin marketplace add /workspace

# Confirm it registered
claude plugin marketplace list

# Install a bundle from the local marketplace
claude plugin install swe@rdl
claude plugin install dev-tools@rdl
```

Then launch `claude` and type `/` — confirm the expected skills appear (e.g. `/swe:tdd`, `/swe:changie`, `/dev-tools:cc-hooks`).

You can also verify from the CLI without entering the REPL:

```bash
claude plugin list
```

## Verifying a New Skill Is Visible

After adding a new skill (e.g. `sops`) to the bundle:

1. Ensure `registry/bundles/swe.yaml` lists `- sops` under `skills:`.
2. Ensure `plugins/swe/skills/sops` symlink exists and resolves: `test -e plugins/swe/skills/sops && echo ok`.
3. Re-run install: `claude plugin install swe@rdl`.
4. In the Claude REPL, type `/swe:sops` — it should autocomplete.

## Symlink Caveat

`plugins/<bundle>/skills/<skill>` entries are **relative symlinks** pointing three levels up:

```
plugins/swe/skills/tdd -> ../../../skills/tdd
```

`claude plugin marketplace add` preserves symlinks but resolves them against the **absolute path at install time**. If the workspace moves (or is mounted at a different path), the resolved paths break.

**Prefer `--plugin-dir` for short-lived devcontainer tests** — it loads in-place without caching, so symlinks always resolve relative to the current mount point:

```bash
claude --plugin-dir ./plugins/swe
```

## Cleanup

Remove the marketplace registration and all installed plugins from it:

```bash
claude plugin marketplace remove rdl
```

## Why Not Copy Into `.claude/`?

Copying plugin directories directly into `~/.claude/plugins/` bypasses the marketplace metadata and breaks the relative symlinks (they'd point into the cache path, not back to `skills/`). Always use `claude plugin marketplace add` or `--plugin-dir` as the entry point.

## References

- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) — upstream walkthrough including "Walkthrough: create local marketplace"
- [Plugins Reference](https://code.claude.com/docs/en/plugins-reference) — full CLI reference for `claude plugin *` commands
