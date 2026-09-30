# Development

This page is the reference for day-to-day work in the repository: the build
and validation commands, the local git hooks, the CI checks, local install
tests, the changelog, and the release process. For tool setup, see
[`CONTRIBUTING.md`](https://github.com/nq-rdl/agent-extensions/blob/main/CONTRIBUTING.md).
For how to write and package a skill, see [Authoring skills](authoring-skills.md).

## Commands

All Python (including the `python3` heredocs inside the shell scripts) runs through
the pixi environment — hence the `pixi run` prefix on every command below.

```bash
# Validate all Claude/Codex plugin manifests, hooks, skills
pixi run bash scripts/validate-plugins.sh

# Validate only plugins touched by changed files
pixi run bash scripts/validate-plugins.sh plugins/claude-code/hooks/hooks.json

# Refresh plugin trees from canonical skills/. Run after
# editing a skill.
pixi run bash scripts/sync-plugins.sh           # all bundles
pixi run bash scripts/sync-plugins.sh go        # one bundle

# Regenerate Claude + Codex plugin.json and marketplace.json files. These manifests
# are GENERATED — never hand-edit them. Run after changing a bundle's
# description/keywords, marketplace.yaml, or VERSION.
pixi run python3 scripts/generate_manifests.py .          # write manifests
pixi run python3 scripts/generate_manifests.py . --check  # CI gate: fail on drift

# Regenerate docs/bundles.md from the registry (also a --check CI gate).
pixi run python3 scripts/generate_bundles_doc.py .          # write
pixi run python3 scripts/generate_bundles_doc.py . --check  # CI gate: fail on drift

# Regenerate evals/claude/**/graders/*.md from each case's graders.spec.yaml (also a --check gate).
pixi run python3 scripts/generate_eval_graders.py .          # write
pixi run python3 scripts/generate_eval_graders.py . --check  # fail on drift

# Bundle reference + grouping + three-way consistency checks (also run by validate.yml)
pixi run python3 scripts/check_bundle_refs.py .   # registry refs resolve to skills/
pixi run python3 scripts/check_exposure.py .      # every canonical skill/hook/mcp is exposed by >=1 bundle (strict); add --warn for a non-blocking reminder
pixi run python3 scripts/check_grouping.py .      # grouping contract: valid member shape, unique leaf + pluginName
pixi run python3 scripts/check_consistency.py .   # each target's bundle <-> marketplace <-> plugin tree agrees

# Weekly link-rot scan + tracker plan (network; needs lychee 0.24.2). --dry-run
# snapshots the live tracker read-only; see docs/link-monitoring.md.
pixi run python3 scripts/link_rot.py scan --out-dir /tmp/link-rot
pixi run python3 scripts/link_rot.py track --dry-run --observations /tmp/link-rot/observations.json

# Unit tests for the pipeline scripts (deps come from the pixi env)
pixi run python3 -m unittest discover -s tests -p 'test_*.py'

# Build + run the skills spec validator (Go), and its unit tests
go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/ && /tmp/asctl repo-check
go -C tools/asctl test ./...

# Review body lines, approximate tokens, and reference counts before content pilots
/tmp/asctl repo-check --size-report
```

## Local git hooks

`lefthook.yml` mirrors the CI checks, so most failures appear before you push.
Each job runs only when its staged or pushed files match the job's glob.

| Hook | Job | Blocks |
|---|---|---|
| pre-commit | `gofmt`, `go vet`, and `go build` for `tools/asctl` | Yes |
| pre-commit | `asctl repo-check`, including local references | Yes |
| pre-commit | Plugin validation and generated-artefact drift | Yes |
| pre-commit | Changie fragment length and YAML parse | Yes |
| pre-commit | lychee external links on staged skill `.md` and `.rst` files | Yes, when lychee is installed |
| pre-commit | Bundle exposure reminder | No |
| pre-push | `asctl` Go tests | Yes |
| pre-push | Pipeline Python unit tests | Yes |
| pre-push | Codex runtime tests (`node --test`) | Yes |
| pre-push | SkillSpector scan (needs Docker) | No |
| pre-push | `claude plugin eval` for changed plugins | No |
| pre-push | Changie fragment present on the branch | Yes |

The `claude plugin eval` job runs only when you set `CLAUDE_EVAL_ENABLE=1`.
It makes paid model calls with your local `claude` login, and it has no CI
equivalent. See `evals/claude/README.md`.

To bypass all hooks for one command, set `LEFTHOOK=0` or use
`git commit --no-verify`. To bypass only the changie gate, set `CHANGIE_SKIP=1`.

## CI checks

CI runs `validate.yml` on every PR/push to main. It checks:
- Bundle YAML skill references resolve to `skills/<name>/` (`scripts/check_bundle_refs.py`)
- The skill-grouping contract holds (`scripts/check_grouping.py`)
- Generated Claude and Codex `plugin.json` + `marketplace.json` files match the registry (`scripts/generate_manifests.py --check`)
- Generated `docs/bundles.md` matches the registry (`scripts/generate_bundles_doc.py --check`)
- Registry bundles, `marketplace.json`, and `plugins/` dirs stay in lockstep (`scripts/check_consistency.py`)
- Every canonical skill/hook/mcp is exposed by >=1 bundle (`scripts/check_exposure.py`); intentional exclusions live in `registry/unbundled.yaml`
- Plugin manifests, hooks, skills, and `.mcp.json` wiring are valid (`scripts/validate-plugins.sh`)
- Codex `0.152.0` and `0.154.0` install every native marketplace entry and discover the enabled native skill copies with explicit leaf names (`scripts/smoke-codex-marketplace.sh`)
- Any symlink under `plugins/` resolves (`validate-symlinks` — plugin trees are real-file copies, so this guards against accidental links)
- The pipeline scripts' unit tests pass (`tests/`)
- Skills validate against the agentskills.io spec, **the directory-structure standard, the repository's 500-body-line limit, and offline local Markdown/RST references** (`asctl repo-check`, built from `tools/asctl/`; every relative link target must exist inside its skill — see [Local references](authoring-skills.md#local-references))

Three more workflows run on PRs alongside `validate.yml`:
- `changelog-check.yml` — fails if no changie fragment was added (bypass with the `skip-changelog` label), and lints each *added* fragment's body against the 200-char per-fragment cap (`scripts/check_changie_length.py`, which also fails on fragments whose YAML does not parse)
- `link-check.yml` — external (HTTP) link check with lychee, advisory for merging: a PR that changes `skills/**/*.md`, `skills/**/*.rst`, the workflow, `skills/lychee/scripts/check-links.sh`, or either `lychee.toml` triggers an uncached scan of all skill Markdown and RST using the root `lychee.toml` (narrow, commented exclusions; see [Example URLs and placeholders](authoring-skills.md#example-urls-and-placeholders)). It can also be run by `workflow_dispatch`. Generated `plugins/**` and `dist/**` copies are not scanned
- `skillspector.yml` — NVIDIA SkillSpector scan over `skills/`; informational, uploads SARIF to code scanning (non-gating)


### Merge enforcement

**Configured checks and merge enforcement are separate.** Observed on
**2026-09-23** via `GET /repos/nq-rdl/agent-extensions/branches/main/protection`
and `GET /repos/nq-rdl/agent-extensions/rules/branches/main`: the protection
response returned `required_status_checks: null`, and the branch rules response
was `[]`. No required status checks were configured. Protection required one PR
approval and conversation resolution; `enforce_admins.enabled` was `false`.
Failed validation therefore did not itself block merging through required-check
enforcement. This observation describes those settings on that date, not their
history. Contributors should still resolve applicable validation failures before
merging.

The intended always-run check inventory comes from these exact `validate.yml`
job names (legacy wording is retained for stable check contexts):

| Job ID | Check name |
|---|---|
| `validate-bundles` | Validate bundle references + registry consistency |
| `validate-symlinks` | Validate skill + agent symlinks |
| `validate-plugins` | Validate Claude plugin structure, hooks, and agents |
| `unit-tests` | Unit tests (pipeline scripts) |
| `validate-skills` | Validate skills against the agentskills.io spec (asctl) |

Enabling required checks and deciding administrator bypass policy are separate
maintainer settings decisions. If required checks are enabled, keep their
configured contexts aligned with the exact job names whenever jobs change;
renaming a job can leave a required context waiting for a result. Record settings
changes here. See [GitHub's protected-branch documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

Keep external `check-links` advisory and outside that intended set: its path
filter skips unrelated PRs, so requiring it could leave them waiting. The
`check-changie-fragment`, SkillSpector `scan`, and release-specific
`version-monotonic` checks are also outside the always-run set. It is not
currently a configured required status check, and base-branch moves do not
retrigger it, so a green result can be stale. Before merging a release PR,
reviewers must rerun `version-monotonic` against current `main` (or confirm the
PR's `VERSION` is strictly newer than `main`'s current `VERSION`).

### Link checks

Local and external link checks are separate. The deterministic, offline local
Markdown/RST reference check runs inside `asctl repo-check`, so it is part of the
always-run `validate-skills` job and the `asctl-repo-check` pre-commit hook; network
failures cannot affect it. External HTTP health stays in the advisory `check-links`
job ([issue #300](https://github.com/nq-rdl/agent-extensions/issues/300)).

Weekly link-rot monitoring (`link-rot-check.yml`,
[issue #301](https://github.com/nq-rdl/agent-extensions/issues/301)) runs on
Mondays at 04:23 UTC and by `workflow_dispatch` (with a `dry_run` input). It is
not a PR check and not a merge gate. It scans canonical `skills/**/*.{md,rst}`,
`agents/**/*.md`, `docs/**/*.md`, `README.md`, `CONTRIBUTING.md` and `AGENTS.md`.
URLs in `hooks/*.sh` and skill shell/YAML/JSON/Python assets are report-only;
`plugins/**` and `dist/**` are never scanned. It uses the root `lychee.toml` as the
single config, with `--cache=false`. It maintains one `link-rot` tracker issue.
Only 404/410 confirmed in two passes, or confirmed NXDOMAIN, counts as rot;
timeouts, 403/429 and 5xx are *unknown* and never open or close the tracker. An
operational failure fails the run and leaves the tracker untouched. The logic is
`scripts/link_rot.py` (tests: `tests/test_link_rot.py`). Classification,
suppression commands, closure and state storage are in [Link monitoring](link-monitoring.md).

## Testing installs locally

To verify skills are visible before release, install the repo as a local Claude Code marketplace:

```bash
# Single-session in-place (preferred in devcontainer — no cache copy, reads files directly from the working tree)
claude --plugin-dir ./plugins/go

# Persistent install (workspace must stay mounted at /workspace)
claude plugin marketplace add /workspace
claude plugin install go@rdl-agent-extensions

# Onboarding onto the team's Claude Code setup goes through the rdl-team plugin:
claude plugin install rdl-team@rdl-agent-extensions
```

For the isolated native Codex install/discovery smoke test (requires `codex` and `jq`):

```bash
scripts/smoke-codex-marketplace.sh
```

The existing plugin-validation job also runs this test in the dedicated
`.devcontainer/codex` image (CLI 0.154.0, no network or credentials, read-only
checkout). See `.devcontainer/codex/README.md` for local Docker/devcontainer commands.

## MCP servers

MCP servers are Go binaries under `mcp/<name>-go/`, cross-compiled into `plugins/<subject>/bin/mcp/` (the subject plugin that wires the server) and referenced via that plugin's `.mcp.json` — no separate install step required. The catalog currently ships no Go MCP servers; the hosted Lucid (`lucid`) and Playwright (`playwright`) servers are wired by URL/command, not as committed binaries.

To build locally:

```bash
cd mcp/<name>-go
make build            # builds for the current platform
make cross-compile DESTDIR=../../plugins/<subject>/bin/mcp
```

## Documentation site

The docs site uses Zensical (configured in `zensical.toml`), provided by the pixi `docs` environment (linux-64 only). Source is `docs/`. Architecture decisions live in [Architecture](ARCHITECTURE.md).

Review the docs locally with the `zensical` pixi task — it runs Zensical from the `docs` environment and provisions it on first run, so no `-e docs` flag is needed:

```bash
pixi run zensical serve   # live-reload preview at http://localhost:8000
pixi run zensical build   # build the static site into ./site
```

The task forwards any subcommand and flags to Zensical (`pixi run zensical <cmd> …`). The `docs` environment is linux-64 only; on macOS either use the dedicated **Zensical Docs** dev container (`.devcontainer/docs/` — pinned to `linux/amd64`, forwards port 8000; see its `README.md`) or install Zensical separately (`uv tool install zensical` or `pip install zensical`) and run `zensical` directly.

## Changelog

Use `changie` for all changelog entries:

```bash
changie new               # create an unreleased change entry
changie batch auto        # batch unreleased into a version (uses semver from kind)
changie merge             # merge versions into CHANGELOG.md
```

**One idea per fragment; keep it short.** Each fragment `body` has a hard
**200-character cap** (`.changie.yaml` `body.maxLength`). Changie has no `lint`
command, so this is enforced two ways: `changie new` rejects an over-long body
at creation, and `scripts/check_changie_length.py` re-lints *added* fragments in
the pre-commit hook and in `changelog-check.yml` (catching fragments written
directly, bypassing the prompt). The same check also rejects a fragment whose
YAML does not parse (e.g. an unquoted `body:` containing `: `), so a malformed
hand-written fragment fails at commit/PR time instead of at release `changie
batch`. The cap is **per fragment, not per change** —
there is no limit on how many fragments a branch adds, so split a large change
into several: run `changie new` once per idea (`Added: thing 1`, `Added: thing
2`, …) rather than packing everything into one run-on body. The cap governs
**current unreleased and future** fragments only; already-released versions
(`.changes/<version>.md` + the GitHub release body) are immutable and out of
scope. Override the limit for a run with `CHANGIE_MAX_BODY_LENGTH` (keep it in
sync with `.changie.yaml`).

## Release

Releases are cut from the GitHub UI, not a local tag push. Run the **"Release — Prepare PR"**
workflow (Actions tab, `workflow_dispatch`) with an explicit `version` input (`X.Y.Z`, no leading
`v`, no zero-padded components — `1.0.00` is rejected). It batches the changie changelog, stamps
`VERSION` (and `pyproject.toml`), regenerates all manifests from the registry, and opens a
`release/v<version>` PR labelled `skip-changelog` — all via the GitHub App token (`RELEASE_APP_ID`
/ `RELEASE_APP_PRIVATE_KEY`) so the PR's own CI runs on it. Reviewing and squash-merging that PR
**is** the release gate (branch protection controls who can merge). A pre-merge **"Release — PR
guard"** check runs on every `release/v*` PR and fails closed if the PR's version doesn't match its
branch name or isn't strictly newer than `main`'s current `VERSION`, catching a stale release PR
before it can merge. On merge, **"Release — Finalize on merge"** tags `v<version>` on the
squash-merge commit and publishes the GitHub release from `.changes/<version>.md` — it never pushes
to `main`, and it is idempotent (safe to re-run; recovers a tag-pushed-but-release-missing partial
failure).

Prepare runs a pinned Changie (`version:` on the `changie-action` step in `release-prepare.yml`),
so an unchanged workflow batches the same changelog; bump the pin deliberately on a normal PR. A
weekly **Changie pin check** workflow (`changie-pin-check.yml`) opens a `changie-pin` tracking issue
when that pin falls behind upstream's latest release — it only notifies; the bump stays a reviewed PR.

**Recovery.** Finalize fails closed rather than guessing: in every state an existing `v<version>`
tag must point at the PR's merge commit, and a remote lookup error is an error, not "absent".

To deliberately exercise both idempotency paths, dispatch **"Release — Verify Finalize recovery"**
from `main` for the current Latest release and enter the exact confirmation string shown by the
workflow. The drill first proves the tag-plus-release no-op, then queues another Finalize attempt
before temporarily deleting only the GitHub release. Its mutation jobs share Finalize's FIFO
concurrency group, preventing a newer release from publishing in that window. A baseline artifact
is stored before deletion; an independent **"Release — Recovery watchdog"** run verifies or restores
the supported metadata after success, failure, timeout, or cancellation. The drill refuses older,
immutable, draft, prerelease, asset-bearing, discussion-linked, or body-drifted releases.

Deletion/recreation necessarily changes the release database ID, creation/publication timestamps,
and release-event/webhook history; those cannot be restored. The title, body, tag target,
`target_commitish`, author identity, and safe Latest state are verified. If the watchdog itself
fails (for example during a GitHub outage), restore `.changes/<version>.md` manually before any
new release. This is a verification drill, not the routine recovery path.

- *Prepare failed after pushing the branch* (e.g. an API error while opening the PR): the run
  deletes `release/v<version>` itself — lease-protected, so only while the branch still points at
  the commit it pushed — and you simply re-dispatch. If the log says the branch was not deleted,
  inspect it and delete it by hand first; Prepare refuses to start while the branch exists.
- *Finalize failed part-way*: re-run it from the Actions tab; it is idempotent.
- *Finalize refuses to run*: a foreign `v<version>` tag, a release without its tag (a draft, or one
  cut by hand), or a remote lookup error — all hard failures. Resolve the cause, then re-run.
- *Two release PRs merged close together*: finalize runs share one FIFO queue, so whichever runs
  second sees the first's tag — newer-after-older publishes both in order; older-after-newer fails
  closed (no tag, no release). Recover by cutting a corrective release with a higher version, or,
  if the out-of-order merge was intentional, tag and release by hand as the run's error says.

`marketplace.json` sources are relative paths (`./plugins/<bundle>`) — installs read directly from `main` (or whatever ref the user pinned), no separate release branch involved.
