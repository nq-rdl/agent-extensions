# Agent extensions

A plugin marketplace for Claude Code and Codex. Each plugin covers one subject,
such as Go or Git, and installs as a self-contained package. A plugin brings
skills and, where the subject needs them, hooks and MCP servers.

Install only the subjects you work with. Each skill in a plugin is one facet of
its subject. For example, `/go:naming` is the naming facet of the `go` plugin.
[`docs/bundles.md`](docs/bundles.md) lists the plugins.

## Install in Claude Code

1. Add the marketplace once:

    ```bash
    /plugin marketplace add nq-rdl/agent-extensions
    ```

2. Install a plugin:

    ```bash
    /plugin install go@rdl-agent-extensions
    ```

To set up the RDL team configuration, install the `rdl-team` plugin:

```bash
/plugin install rdl-team@rdl-agent-extensions
```

### Use a skill in Claude Code

Type `/<plugin>:<skill>`, then your request:

```text
/go:naming review the identifiers in internal/store/
```

Type `/<plugin>` to list the skills of a plugin in autocomplete. Claude can also
load an installed skill when your request matches the description of the skill.

### Update or remove a plugin

Run these commands from a shell. Inside a session, `/plugin` opens the same
manager.

```bash
# Refresh the marketplace catalog, then update an installed plugin
claude plugin marketplace update rdl-agent-extensions
claude plugin update go@rdl-agent-extensions   # restart Claude Code to apply

# Remove a plugin
claude plugin uninstall go@rdl-agent-extensions
```

## Install in Codex

1. Add the marketplace once:

    ```bash
    codex plugin marketplace add nq-rdl/agent-extensions
    ```

2. List the available plugins, then install one:

    ```bash
    codex plugin list --marketplace rdl-agent-extensions --available --json
    codex plugin add go@rdl-agent-extensions --json
    ```

Codex installs the same plugins as Claude Code, with native skills, MCP
integrations, and command hooks. See [Codex](docs/codex.md) for verification
commands and current limitations.

### Use a skill in Codex

Type `$` in the composer to select an installed skill, then add your request:

```text
$git:pr-comments <PR URL>
```

The CLI also provides `/skills`. See [Invoking skills](docs/codex.md#invoking-skills)
for the desktop menu and the differences from Claude Code slash commands.

## Delegation

Some skills can run their workflow in a subagent. See
[Delegation](docs/delegation.md) for when this applies and for the names of the
former agents.

## Contributing

Plugins are generated from canonical skills in `skills/` and bundle definitions
in `registry/`. Do not edit `plugins/` or `dist/codex/` by hand.

- [`CONTRIBUTING.md`](CONTRIBUTING.md) – required tools and setup
- [Authoring skills](docs/authoring-skills.md) – grouping rules, skill layout,
  and packaging
- [Development](docs/development.md) – commands, CI checks, the changelog, and
  releases
- [Architecture](docs/ARCHITECTURE.md) – design decisions

`AGENTS.md` is the entry point for coding agents. The repository has no
`CLAUDE.md`.

## Roadmap

Epics and the [RDL Planning project board](https://github.com/orgs/nq-rdl/projects/1)
track planned work. Only members of the `nq-rdl` organisation can see the board.

- [#180](https://github.com/nq-rdl/agent-extensions/issues/180) – a reviewable,
  merge-triggered release process that follows Actions best practice
- [#261](https://github.com/nq-rdl/agent-extensions/issues/261) – follow-up for
  the `redhat` plugin: settle the credential path and docs-to-source map
  ([#262](https://github.com/nq-rdl/agent-extensions/issues/262)), and verify it
  end to end on Linux and macOS with real credentials
  ([#267](https://github.com/nq-rdl/agent-extensions/issues/267))
- [#312](https://github.com/nq-rdl/agent-extensions/issues/312) – reliable,
  discoverable skills: verified fixes, behavioural pilots, and link integrity

See [open issues](https://github.com/nq-rdl/agent-extensions/issues) for smaller
items.

## Licence

The licence of a file depends on its type. You do not choose between them.

- **Software** – `SPDX-License-Identifier: MIT`. Full text: [LICENSE](LICENSE).
- **Media** – `SPDX-License-Identifier: CC-BY-4.0`. Full text:
  [LICENSE-CC-BY-4.0](LICENSE-CC-BY-4.0).
