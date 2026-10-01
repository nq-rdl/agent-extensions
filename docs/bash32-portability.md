# Bash 3.2 portability checks

The `Unit tests (pipeline scripts)` check in `validate.yml` prepares a pinned
fixture with Docker on the Ubuntu runner, then runs
`scripts/run_bash32_portability.py`. The existing check name stays unchanged.
The dedicated runner lists every required case and fails on an empty or
incomplete selection, a missing test, a failure, an expected failure, or any
skip (including a skipped subtest). Its verbose output names the cases and
reports the executed and skipped counts. Red Hat credential cases additionally
exercise Bitwarden text/hidden custom fields, Notes precedence, and empty/missing
fields with the pinned jq; the same cases run under the host Bash in general discovery.
Sops shims cover source detection/missing CLI/file, empty/decrypt failure, hidden
storage before a file exists in the running session, atomic writes, optional
Bitwarden Notes/custom-field seeding, path overrides/source filtering, preflight
tool reporting, and narrowly scoped direct-decryption guard decisions. These run
under both host Bash and the pinned Bash 3.2 fixture (not real sops/hardware).
Red Hat fetch cases use curl/wget shims to exercise direct HTML validation/article
extraction, source/index fallback order, fresh-token retries and entitlement versus
credential diagnostics. No live Red Hat requests or real credentials are used.
Red Hat setup shims additionally cover pinned raw-binary installs on Linux/macOS
amd64/arm64, package-manager selection, preview-only behavior, checksum/download/
version failures, private identity paths and reuse, symlink/concurrent-key refusal,
recipient inference, and accessible/inaccessible TPM detection. These tests never
run real package installs or upstream downloads; TPM generation uses a shim.
Pi dispatch cases run all target parsing, conservative overlap/cap waves,
prompt rendering, worktree and launch argv (including opt-in Fast env/extension,
offline catalog checks and requested-tier status), resume, status/CI, lock safety and
read-only setup checks with local pi/wt/gh/git shims under both host Bash and the
pinned Bash 3.2 fixture. No real workers, credentials or model calls are used.
General unit-test discovery can still
skip these fixtures on contributors' machines without container prerequisites.

The cases exercise both installed prompt hooks' fire/no-fire paths, JSON-escaped
quotes, newlines and backslashes, and configuration enable/disable/check while
preserving unrelated settings. Hook fixtures assert that jq and Python are
absent. Every fixture asserts Bash 3.2 and BusyBox sed, uses a disposable copy,
and runs with `--network=none --pull=never`. Only host-side preparation uses
the network. No credentials or checkout mounts enter the fixture containers.

This is Linux Bash 3.2.57 with BusyBox userland, a non-GNU portability stand-in.
It is **not evidence of native macOS/BSD execution**.

## Pinned sources

Pins are maintained together in `tests/bash32_fixture.py`:

- Official [Docker Bash image](https://hub.docker.com/_/bash), `3.2.57`, index
  digest `sha256:0fd7cb8499c63a3c9345e7088a9cd83bb69f6e895e83833859aff838a0312091`.
  Verified against the Docker Hub `library/bash:3.2` registry manifest on
  2026-09-29, including its content hash. Its amd64 manifest digest is
  `sha256:ae50c35ff361cd17a9c6cc4ee045b44a7778c4e2bf66def577752403c446c810`;
  image annotations identify source revision
  `099d6114cbdb9b016fb8c4beb653187df002f66f` in
  [docker-bash](https://github.com/tianon/docker-bash/tree/099d6114cbdb9b016fb8c4beb653187df002f66f/3.2).
- [jq 1.7.1](https://github.com/jqlang/jq/releases/tag/jq-1.7.1), upstream static
  `jq-linux-amd64` release asset. SHA-256:
  `5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5`, verified
  against upstream's
  [sha256sum.txt](https://github.com/jqlang/jq/releases/download/jq-1.7.1/sha256sum.txt).
  Preparation and fixture discovery both verify the checksum before using it.

The fixture explicitly selects `linux/amd64` to match jq. Local execution needs
a working Docker or Podman runtime and amd64 support (native or emulated).
To reproduce with Podman, from the repository root:

```bash
pixi run --locked python3 scripts/run_bash32_portability.py --prepare /tmp/rdl-bash32 --runtime podman
BASH32_CONTAINER_RUNTIME=podman BASH32_STATIC_JQ=/tmp/rdl-bash32/jq \
  pixi run --locked python3 scripts/run_bash32_portability.py
```

Replace `podman` with `docker` for Docker. No image tag fallback or in-fixture
package install is allowed. To refresh pins, verify the official image manifest
and upstream jq checksum, update the fixture constants and provenance here,
then rerun the strict gate and its runner regression tests.
