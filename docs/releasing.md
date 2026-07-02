# Releasing

This is the runbook for cutting a release of this repo's marketplace/plugins. It complements the
design rationale in [`docs/ARCHITECTURE.md`](ARCHITECTURE.md#release) and the summary in
[`AGENTS.md`](../AGENTS.md#release).

Releases are cut through a reviewable pull request — never by pushing a `v*` tag locally. Two
workflows drive the flow:

- **Release — Prepare PR** (`.github/workflows/release-prepare.yml`, `workflow_dispatch`) — opens
  a `release/v<version>` PR.
- **Release — Finalize on merge** (`.github/workflows/release-finalize.yml`, `pull_request:
  closed` on `main`) — tags and publishes once that PR is merged.

## Cutting a release

1. Go to the repo's **Actions** tab → **"Release — Prepare PR"** → **Run workflow**.
2. Enter the `version` input as `X.Y.Z` with no leading `v` (e.g. `0.20.0`) and run it.
3. The workflow batches the changie changelog, stamps `VERSION` (and `pyproject.toml`),
   regenerates every manifest from the registry, and opens a `release/v<version>` PR labelled
   `skip-changelog`, authored via the GitHub App token so the PR's own CI runs on it.
4. Review the PR diff. Expect: `CHANGELOG.md` and a new `.changes/<version>.md` added, the
   `.changes/unreleased/` fragments consumed (removed), and `VERSION` + `pyproject.toml` +
   the regenerated manifests (every `plugins/*/.claude-plugin/plugin.json` plus the root
   `.claude-plugin/marketplace.json`) bumped to the new version. `docs/bundles.md` is
   version-independent and does not change.
5. Squash-merge the PR once it's green and approved. Merging **is** the release gate — branch
   protection controls who is allowed to do this.
6. On merge, **"Release — Finalize on merge"** tags `v<version>` on the squash-merge commit and
   publishes the GitHub release from `.changes/<version>.md`.

Preconditions enforced by the prepare workflow: the version must be monotonically greater than the
current `VERSION`; no existing `v<version>` tag, `release/v<version>` branch, or already-batched
`.changes/<version>.md` may be present; and there must be unreleased changie fragments to batch.
The finalize workflow re-asserts monotonicity at the publish point: it refuses to tag a version at
or below the newest existing `v*` tag, so merging two open release PRs out of order fails closed
instead of publishing a downgrade. A pre-merge companion, **"Release — PR guard"**
(`.github/workflows/release-pr-guard.yml`), runs on every `release/v*` PR and fails when the PR's
version is not strictly greater than `main`'s current `VERSION` — catching a stale release PR
*before* its downgraded `VERSION` and manifests can land on `main` at all (see the required-check
prerequisite below for what makes this binding).

A brief red `changelog-check` run on the PR right when it opens is expected and harmless — the
`skip-changelog` label is applied moments after PR creation, and the label's own event re-runs the
check as skipped.

## Partial-failure recovery

**Tag pushed but release missing.** If "Release — Finalize on merge" tagged `v<version>` but
failed before (or during) publishing the GitHub release, just re-run the failed workflow run from
the Actions tab. The workflow is idempotent and branches on what already exists:

- Neither tag nor release exist → creates both (the normal path).
- Tag exists, release does not → skips tagging, creates only the release.
- Both already exist → full no-op.

**Need a late changie fragment after the PR is already open.** The prepare run already batched
`.changes/unreleased/` into `.changes/<version>.md` — a fragment simply committed to the release
branch stays in `unreleased/`, is **omitted from the release notes**, and merges back to `main`
(where it would ship in the *next* release instead). To include it in *this* release, either:

- close the PR, delete the `release/v*` branch, land the fragment on `main`, and re-dispatch
  "Release — Prepare PR" with the same version (cleanest — the whole batch re-runs), or
- on the release branch, fold the entry into `.changes/<version>.md` by hand (add the bullet under
  the right kind heading) and rebuild `CHANGELOG.md` with `changie merge` — never leave the new
  fragment in `.changes/unreleased/`.

## Rollback

**Yanking a bad GitHub release.** Delete the GitHub release from the Releases page. Tag deletion
is more restricted: under the planned `v*` tag ruleset (#175), only the release GitHub App can
delete a `v*` tag — a human with normal write access cannot.

**This does not unpublish content.** Installs read manifests straight from `main`
(`marketplace.json` plugin sources are relative `./plugins/<bundle>` paths, not pinned to a
release tag), so deleting a tag or release does **not** roll back what a `claude plugin install`
picks up. To truly roll back a bad version, revert the release PR's commit on `main` and cut a new
*higher* version — there is no way to make `main` serve an older manifest state under the same or
a lower version number.

## Repo-settings prerequisites (one-time)

Tracked in #175 / #176, required before the flow above works end-to-end:

- The release GitHub App is installed on the repo with `contents: write`, `pull requests: write`,
  and `issues: write` (the last is needed to apply the `skip-changelog` label) permissions.
- The old branch-protection bypass that let the release bot push directly to `main` is removed —
  the new flow never pushes to `main`, so the bypass is no longer needed and should not be kept
  around as a standing exception.
- A `v*` tag ruleset is added restricting tag create/delete/non-fast-forward-update to the release
  App, so only the finalize workflow (or a maintainer acting through it) can move release tags.
- The **"Release — PR guard" / `version-monotonic`** check is marked as a required status check on
  `main`, and **"require branches to be up to date before merging"** is enabled. Base-branch moves
  alone do not re-run PR checks, so without the up-to-date requirement a stale release PR keeps the
  green guard run it earned before a newer version merged. (The guard job is skipped on
  non-release PRs; GitHub treats a skipped required check as passing.)
- The always-run `validate.yml` gates are marked as required status checks on `main` so red CI
  blocks the merge button — see [`docs/branch-protection.md`](branch-protection.md) for the exact
  list, which checks are deliberately left optional, and the job-name coupling caveat (#221).

**Bootstrap note (#172).** `workflow_dispatch` and `pull_request: closed` both execute the
workflow file as it exists on the **default branch**, not as it exists on a feature branch. That
means this release flow only works once the PR introducing it has been merged to `main` — the
first release cut with the new flow is the *next* version after that merge (at the time of
writing, that is `0.20.0`).
