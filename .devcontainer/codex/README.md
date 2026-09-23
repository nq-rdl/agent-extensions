# Codex marketplace smoke container

This container runs the native Codex plugin acceptance test using CLI `0.154.0`.
It installs the local marketplace, verifies every enabled plugin and skill,
compares cached references/scripts/assets, and checks removal and reinstallation.

The build downloads the pinned CLI and installs Python from the repository's
Pixi lockfile under `/opt/codex-python`. The test runs as a non-root user with no
network, no credentials, and a read-only repository mount. Its temporary Codex
configuration and cache live inside the container and are cleaned after the test.
This verifies packaging and discovery; it does not execute model requests or
prove that a model follows the skill or its delegation outline.

## Dev Containers CLI

From the repository root:

```bash
devcontainer up --workspace-folder . --config .devcontainer/codex/devcontainer.json
devcontainer exec --workspace-folder . --config .devcontainer/codex/devcontainer.json \
  bash scripts/smoke-codex-marketplace.sh
```

`postCreateCommand` runs the test on initial creation. The explicit exec command
reruns it after changes. In VS Code, choose **Codex Marketplace Smoke** when
reopening the repository in a container.

## Docker and CI

The `validate-plugins` CI job runs these same image and test commands:

```bash
docker build --build-arg CODEX_VERSION=0.154.0 \
  -t rdl-codex-smoke -f .devcontainer/codex/Dockerfile .
docker run --rm --network none \
  --mount "type=bind,source=$PWD,target=/workspace,readonly" \
  rdl-codex-smoke bash scripts/smoke-codex-marketplace.sh
```

The repository is mounted at test time, so uncommitted plugin changes are tested.
The image contains tools and the locked environment, not a copy of the catalog. The existing
host-run CI checks still cover Codex `0.152.0` and `0.154.0`.

The same container also validates native hook discovery and version replacement:

```bash
pixi run --locked --manifest-path /opt/codex-python/pyproject.toml \
  python3 /workspace/scripts/check_codex_runtime.py /workspace
```

The package root uses `.codex-plugin/plugin.json`; a portable root manifest would
suppress hooks on the pinned runtime. Hook trust is never bypassed by these tests.
