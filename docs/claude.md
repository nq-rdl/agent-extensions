---
icon: lucide/terminal
---

# Claude Code

How agent-extensions packages skills for Claude Code via the plugin marketplace.

## Architecture

Claude Code uses a **marketplace → plugin → skills** model:

```text
.claude-plugin/
  marketplace.json           ← marketplace manifest (repo root)

plugins/
  swe/                       ← one plugin per bundle
    .claude-plugin/
      plugin.json            ← plugin manifest
    skills/
      tdd -> ../../../skills/skills/tdd
      go-secure -> ../../../skills/skills/go-secure
  infra/
    ...
  dataops/
    ...
  informatics/
    ...
  dev-tools/
    ...
  meta/
    ...
```

Claude Code requires `.claude-plugin/marketplace.json` at the **repository root** — there is no subdirectory marketplace source. The marketplace lists 6 plugins, one per bundle.

## How it works

1. **Marketplace manifest** (`.claude-plugin/marketplace.json`) declares the marketplace name (`rdl`), owner, and an array of plugin entries. Each entry has a `source` pointing to a relative path under `plugins/`.

2. **Plugin manifests** (`plugins/<bundle>/.claude-plugin/plugin.json`) declare the plugin name, version, and a `skills` path pointing to `./skills/`.

3. **Skill symlinks** (`plugins/<bundle>/skills/<name>`) are relative symlinks into the `skills/` submodule at the repo root. The symlink path is `../../../skills/skills/<name>` (three levels up from the skill directory to the repo root, then into the submodule).

4. **On install**, Claude Code copies the plugin directory into `~/.claude/plugins/cache`. Symlinks are **followed during copying**, so the installed plugin is self-contained — no submodule dependency at runtime.

## Install

```bash
# Add the marketplace (once)
/plugin marketplace add nq-rdl/agent-extensions

# Install individual bundles
/plugin install swe@rdl
/plugin install infra@rdl
/plugin install informatics@rdl

# Use a skill (namespaced by plugin)
/swe:tdd
/infra:ansible
```

## Bundles

Skills are split into 6 bundles so users install only what they need:

| Bundle | Skills | Focus |
|--------|--------|-------|
| swe | 7 | TDD, Go, CI/CD, changelogs |
| infra | 4 | Ansible, git hooks, StarRocks |
| dataops | 5 | CSV, Excel, PDF, Word, design |
| informatics | 12 | R, Shiny, Quarto, CRAN |
| dev-tools | 11 | Agent dispatch, Jules, link checking |
| meta | 2 | Skill review, issue reporting |

See [Bundles](bundles.md) for the full skill list per bundle.

## Update workflow

When skills are updated in the `nq-rdl/agent-skills` submodule:

1. Dependabot opens a PR to bump the submodule pointer.
2. CI validates that all skill symlinks still resolve.
3. After merge, bump the `version` in `marketplace.json` and each affected `plugin.json`.
4. Users receive update prompts via `/plugin marketplace update`.

## Why bundles instead of one plugin

Claude Code's marketplace supports fine-grained install and uninstall. Splitting into bundles means:

- Users keep their environment lean — install only the bundles relevant to their work
- Skills are namespaced by bundle (`/swe:tdd`, `/infra:ansible`) which helps discoverability
- Bundles can be versioned independently in the future

## Validation

```bash
# Validate marketplace and plugin structure
claude plugin validate .

# Test locally without installing
claude --plugin-dir ./plugins/swe
```
