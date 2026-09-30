# Contributing

Thank you for contributing to the RDL agent extension catalog. This guide
describes the tools you need, how to set up a working copy, and the usual
change loop. The detailed rules are in the documentation:

- [Authoring skills](docs/authoring-skills.md) – grouping rules, skill layout,
  content conventions, and packaging
- [Development](docs/development.md) – commands, git hooks, CI checks,
  changelog, and releases
- [Architecture](docs/ARCHITECTURE.md) – design and packaging decisions

## Tools

The build scripts need macOS or Linux. On Windows, use WSL2 or a dev container.

| Tool | Use | Required |
|---|---|---|
| [Dev Containers](https://containers.dev/) | Isolated development environments (`.devcontainer/`) | Recommended |
| [pixi](https://pixi.sh/) | Python environment for the registry scripts and the docs site | Yes |
| [lefthook](https://lefthook.dev/) 1.10 or later | pre-commit and pre-push hooks that mirror CI | Yes |
| [Go](https://go.dev/) | Builds and tests the `asctl` skill validator | Yes |
| [changie](https://changie.dev/) | Changelog fragments | Yes |
| [Bun](https://bun.sh/) | TypeScript dependencies and type checks for the Codex runtime | For Codex work |
| Node.js 18.18 or later | Codex runtime tests | For Codex work |
| [lychee](https://lychee.cli.rs/) | External link checks | Optional |
| Docker | SkillSpector scan, dev containers | Optional |

Run all repository Python through pixi (`pixi run …`). Do not use a system
`python3`.

## Dev containers

The repository has three dev containers:

| Container | Path | Use |
|---|---|---|
| RDL Plugin Sandbox | `.devcontainer/` | General catalog development, with an outbound firewall |
| Zensical Docs | `.devcontainer/docs/` | Docs preview on macOS, because the `docs` pixi environment is linux-64 only |
| Codex smoke test | `.devcontainer/codex/` | Offline Codex marketplace install test |

Each container directory has a `README.md` with its own instructions.

## Set up a working copy

1. Clone the repository and open it in a dev container or a local shell.
2. Create the Python environment:

    ```bash
    pixi install
    ```

3. Activate the git hooks:

    ```bash
    lefthook install
    ```

4. For Codex runtime work, install the TypeScript dependencies:

    ```bash
    bun install
    ```

## Make a change

1. Create a branch from `main`.
2. Edit canonical content only. Skills are in `skills/`, hooks are in `hooks/`,
   and bundle definitions are in `registry/`.
3. Regenerate the plugin trees:

    ```bash
    pixi run bash scripts/sync-plugins.sh
    ```

4. If you changed a bundle, `registry/marketplace.yaml`, or `VERSION`,
   regenerate the manifests and the bundle list:

    ```bash
    pixi run python3 scripts/generate_manifests.py .
    pixi run python3 scripts/generate_bundles_doc.py .
    ```

5. Add a changelog fragment. Write one idea in each fragment, in 200
   characters or fewer:

    ```bash
    changie new
    ```

6. Commit, push, and open a pull request. The git hooks run the same checks
   as CI.

Do not edit generated files by hand. These are the `plugins/` and
`dist/codex/` trees, all `plugin.json` and `marketplace.json` files, and
`docs/bundles.md`.

## Preview the docs

On Linux, run:

```bash
pixi run zensical serve
```

The preview is at <http://localhost:8000>. On macOS, use the Zensical Docs dev
container.

## Claude Code plugins for catalog work

Install development plugins, such as Go language servers or PR review tools, in
your user settings. See [External marketplaces](docs/external-marketplaces.md).
Do not enable the `rdl-agent-extensions` marketplace or its plugins in a session
that develops the catalog. To test a plugin from your working copy, see
[Testing installs locally](docs/development.md#testing-installs-locally).
