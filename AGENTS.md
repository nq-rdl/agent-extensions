# AGENTS.md

This repository is the `rdl-agent-extensions` marketplace. It authors reusable
agent skills once, under `skills/`, and publishes them as self-contained
plugins for Claude Code and Codex. Generator scripts build the plugin trees and
manifests from the registry.

## Project structure

```text
skills/<name>/            Canonical skills: SKILL.md plus scripts/, references/ (.rst), assets/
hooks/                    Canonical Claude Code hook scripts and hooks.json configs
mcp/<name>-go/            Go MCP servers (none ship at present)
registry/bundles/*.yaml   Source of truth: which skills, hooks, and MCP servers each plugin ships
registry/marketplace.yaml Marketplace metadata, plugin defaults, and display order
VERSION                   Version stamped into every generated manifest
plugins/<subject>/        GENERATED Claude Code plugin trees (real-file copies of skills/)
dist/codex/plugins/       GENERATED Codex plugin trees
.claude-plugin/           GENERATED Claude Code marketplace manifest
.agents/plugins/          GENERATED Codex marketplace manifest
docs/bundles.md           GENERATED list of plugins and skills
scripts/                  Sync, generate, and validation scripts (run with pixi)
tools/asctl/              Go CLI that validates skills against the agentskills.io spec
tests/                    Unit tests for the pipeline scripts and the Codex runtime
evals/claude/             Claude plugin eval suites
docs/                     Project documentation (Zensical site)
.devcontainer/            Dev containers: sandbox, docs preview, Codex smoke test
```

## Rules

- Edit canonical files only (`skills/`, `hooks/`, `registry/`). Never hand-edit
  a generated path.
- After you change a skill, hook, or bundle, run
  `pixi run bash scripts/sync-plugins.sh`. After you change bundle metadata,
  `registry/marketplace.yaml`, or `VERSION`, run
  `pixi run python3 scripts/generate_manifests.py .`.
- Run all Python through `pixi run`. Never call a system `python3`.
- Add a changie fragment for each change (`changie new`). A fragment holds one
  idea in 200 characters or fewer.
- Put optional subagent instructions in `skills/<name>/references/subagent.rst`.
  Do not create an `agents/` directory.
- Language policy: new CLI helpers and MCP servers use Go. A skill helper script
  uses Bash 3.2 and `jq`. File-format skills use Python. New TypeScript is not
  permitted. See [Architecture](docs/ARCHITECTURE.md#language-policy).

## Where to look

- [`CONTRIBUTING.md`](CONTRIBUTING.md) – required tools and setup
- [Authoring skills](docs/authoring-skills.md) – grouping rules, skill layout,
  content conventions, and packaging
- [Development](docs/development.md) – commands, git hooks, CI checks, local
  install tests, changelog, and releases
- [Architecture](docs/ARCHITECTURE.md) – design decisions and the registry schema
- [Codex](docs/codex.md) and [Delegation](docs/delegation.md) – target-specific
  packaging
