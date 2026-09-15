# Marketplace smoke E2E

`marketplace-smoke.sh` asserts the post-audit marketplace end-state.

- Static: `bash tests/e2e/marketplace-smoke.sh`
- Live (inside the devcontainer): `bash tests/e2e/marketplace-smoke.sh --live`

Devcontainer run from the host:

    devcontainer up --workspace-folder .
    devcontainer exec --workspace-folder . bash -lc 'bash tests/e2e/marketplace-smoke.sh --live'

Not wired into CI (no docker-in-docker there); it is the local acceptance gate.

# SQL Code plugin smoke E2E

`sql-code-smoke.sh` asserts the `sql-code` plugin end-state (#131) and drives its helper and
hooks; `--live` additionally installs the plugin with the `claude` CLI, exercises the **installed**
copies, and runs the first-run acceptance test (`claude -p '/sql-code:setup --default --yes'`
must create `.sqlreview/config.json`). Without credentials that last step is reported `SKIP` and
the run is RED — it is required, not optional.

- Static: `bash tests/e2e/sql-code-smoke.sh`
- Live (inside the sandbox container): `bash tests/e2e/sql-code-smoke.sh --live`

Without the `devcontainer` CLI, build and run the sandbox with Docker directly. Mount the repo at
its host path (a git worktree's `.git` file points at the main checkout, so mount that too), run
as the host uid, and give Claude a throwaway home seeded with your own OAuth credentials:

    docker build -t rdl-plugin-sandbox -f .devcontainer/Dockerfile .devcontainer
    H="$(mktemp -d)"; mkdir -p "$H/.claude"; cp ~/.claude/.credentials.json "$H/.claude/"
    printf '{"hasCompletedOnboarding":true}\n' | tee "$H/.claude.json" > "$H/.claude/.claude.json"
    W="$PWD"; G="$(git rev-parse --git-common-dir | xargs realpath)"
    docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp/home -e CLAUDE_CONFIG_DIR=/tmp/home/.claude \
      -e WORKSPACE_DIR="$W" -e PATH=/usr/local/share/npm-global/bin:/home/node/.pixi/bin:/usr/local/bin:/usr/bin:/bin \
      -v "$H":/tmp/home -v "$W":"$W" -v "$G":"$G" -w "$W" rdl-plugin-sandbox \
      bash -c 'git config --global --add safe.directory "*"; pixi run python3 -m unittest discover -s tests -p "test_sql_review_*.py"; bash tests/e2e/sql-code-smoke.sh --live'
