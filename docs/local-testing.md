---
icon: lucide/package-check
---

# Local Marketplace Testing

How to install this repo as a local Claude Code marketplace to verify skills are visible before release.

## TL;DR

Single-session in-place test (no persistence, no cache copy):

```bash
claude --plugin-dir ./plugins/go
```

Skills from that subject plugin are immediately available in the session. Nothing is written to `~/.claude`.

## Devcontainer Quickstart

Inside the devcontainer the repo is mounted at `/workspace` and `CLAUDE_CONFIG_DIR=/home/node/.claude`. Run:

```bash
# Validate manifests first — catch schema errors before install
claude plugin validate /workspace

# Register the local repo as a marketplace named "rdl"
claude plugin marketplace add /workspace

# Confirm it registered
claude plugin marketplace list

# Install every subject in one command via the meta-plugin…
claude plugin install rdl@rdl
# …or install a single subject
claude plugin install go@rdl
```

Then launch `claude` and type `/` — confirm the expected skills appear (e.g. `/go:secure`, `/gh:changie`, `/claude-code:hook`).

You can also verify from the CLI without entering the REPL:

```bash
claude plugin list
```

## Verifying a New Skill Is Visible

After mapping a new skill (e.g. `go-secure` → `/go:secure`) into a subject bundle:

1. Ensure `registry/bundles/go.yaml` lists it under `skills:`. A flat `- go-secure` publishes it
   as `/go:go-secure` (the leaf defaults to the source name); to invoke it as `/go:secure`, use a
   `- {source: go-secure, leaf: secure}` mapping to rename the facet.
2. Ensure the real-file copy exists: `test -d plugins/go/skills/secure && echo ok`
   (run `bash scripts/sync-plugins.sh go` if it does not).
3. Re-run install: `claude plugin install go@rdl`.
4. In the Claude REPL, type `/go:secure` — it should autocomplete.

## Self-Contained Plugin Trees

`plugins/<bundle>/skills/<name>/` and `plugins/<bundle>/agents/<name>.md` hold **real-file copies** of the canonical content under `skills/` and `agents/`. This is intentional — Claude Code's `claude plugin install` does a `cp -R` of the plugin source into a per-user cache, and any symlink whose target sits outside the copied tree would dangle.

If you edit a skill or agent, refresh the plugin tree:

```bash
bash scripts/sync-plugins.sh           # all bundles
bash scripts/sync-plugins.sh go        # one bundle
```

`--plugin-dir` still works for short-lived testing without caching:

```bash
claude --plugin-dir ./plugins/go
```

## Cleanup

Remove the marketplace registration and all installed plugins from it:

```bash
claude plugin marketplace remove rdl
```

## Why Not Copy Into `.claude/`?

Copying plugin directories directly into `~/.claude/plugins/` bypasses the marketplace metadata (installed plugins won't appear in `claude plugin list` and can't be pruned). Always use `claude plugin marketplace add` or `--plugin-dir` as the entry point.

## References

- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces) — upstream walkthrough including "Walkthrough: create local marketplace"
- [Plugins Reference](https://code.claude.com/docs/en/plugins-reference) — full CLI reference for `claude plugin *` commands
