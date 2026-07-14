# Zensical docs dev container

A dedicated dev container for previewing and editing the [Zensical](https://zensical.org)
documentation site — built for contributors on **macOS**, where
`pixi run zensical` can't run natively.

## Why this exists

The repo's `docs` pixi environment is pinned to `linux-64` because Zensical
ships **no macOS (or aarch64) conda build** — only `conda-forge/linux-64`. So
`pixi run zensical serve` / `build` work only on Linux. This container gives
macOS (and any) contributors a Linux environment where those commands work,
without touching the shared pixi config or the marketplace sandbox next door.

It is deliberately separate from the sibling **RDL Plugin Sandbox**
(`../devcontainer.json`): that one is a locked-down box (outbound firewall,
`claude-code`, full toolchain) for developing the marketplace itself. This one
is a lightweight docs-preview box — `pixi` + `claude-code`, open outbound, port
8000 forwarded, no firewall.

## Requirements

- Docker (Docker Desktop on macOS) and the VS Code **Dev Containers** extension.
- On **Apple Silicon**: the container is pinned to `linux/amd64` (to match the
  `linux-64`-only `docs` env) and runs under Docker's emulation. The first build
  is slower as a result; the preview server itself is plenty fast.

## Usage

1. In VS Code: **Dev Containers: Reopen in Container** → pick **Zensical Docs**
   (the picker appears because the repo now has more than one `.devcontainer`
   config).
2. On first create, the container runs `pixi install -e docs` to provision the
   docs environment. Then, in the integrated terminal:

   ```bash
   pixi run zensical serve
   ```

   VS Code auto-forwards port **8000** and opens your browser to the
   live-reloading preview. Edit files under `docs/` and the site refreshes.
3. To produce a static build instead:

   ```bash
   pixi run zensical build   # outputs ./site
   ```

### Accessing the server outside VS Code

VS Code forwards the loopback-bound dev server automatically. If you run the
container with plain `docker` (no VS Code port forwarding), bind to all
interfaces so the published port is reachable from the host:

```bash
pixi run zensical serve -a 0.0.0.0:8000
```

## See also

- `docs/ARCHITECTURE.md` — the pixi environment layout and the docs feature.
- `zensical.toml` — the Zensical site configuration.
- `../devcontainer.json` — the marketplace-dev sandbox container.
