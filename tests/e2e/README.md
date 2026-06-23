# Marketplace smoke E2E

`marketplace-smoke.sh` asserts the post-audit marketplace end-state.

- Static: `bash tests/e2e/marketplace-smoke.sh`
- Live (inside the devcontainer): `bash tests/e2e/marketplace-smoke.sh --live`

Devcontainer run from the host:

    devcontainer up --workspace-folder .
    devcontainer exec --workspace-folder . bash -lc 'bash tests/e2e/marketplace-smoke.sh --live'

Not wired into CI (no docker-in-docker there); it is the local acceptance gate.
