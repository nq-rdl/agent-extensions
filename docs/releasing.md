---
icon: lucide/rocket
---

# Releasing

This runbook covers how to cut a release, how to recover when a release run fails
part-way, and how to roll back a bad release. The design rationale is in
[Architecture → Release](ARCHITECTURE.md#release). The workflow details are in
`AGENTS.md` under **Release**.

A release publishes nothing to a package registry. Claude Code and Codex read
`marketplace.json` from the ref that the user added (normally `main`) and copy
each plugin into a local cache keyed by its version. The version comes from
`VERSION`. A release does three things: it bumps that version on `main`, it tags
the merge commit `v<version>`, and it publishes a GitHub release with the
changelog.

## Cut a release

1. Make sure that every change you want in the release is merged to `main` with
   its changie fragment in `.changes/unreleased/`.
2. In the Actions tab, run **Release — Prepare PR** (`release-prepare.yml`) from
   `main`. Enter an explicit `version` in the form `X.Y.Z`: no leading `v` and no
   zero-padded components. The version must be greater than the current `VERSION`.
3. The workflow opens a `release/v<version>` PR labelled `skip-changelog`. The PR
   batches the fragments into `.changes/<version>.md` and `CHANGELOG.md`, stamps
   `VERSION` and `pyproject.toml`, and regenerates the manifests. Review the
   changelog and the version bump. The **Release — PR guard** check
   (`version-monotonic`) must pass.
4. Squash-merge the PR. Merging is the release gate.
5. **Release — Finalize on merge** (`release-finalize.yml`) tags `v<version>` on
   the squash-merge commit and publishes the GitHub release from
   `.changes/<version>.md`. Confirm that the run is green and that the release is
   marked **Latest**.

## Recover from a partial failure

| Symptom | Action |
|---|---|
| Prepare failed after it pushed `release/v<version>` (for example, the PR could not be opened) | The run deletes the branch itself if the branch still points at the commit that it pushed. Re-dispatch Prepare. If the log says that the branch was not deleted, inspect it, delete it by hand, then re-dispatch. Prepare refuses to start while the branch exists. |
| Finalize pushed the tag but did not publish the release | Re-run Finalize from the Actions tab. It is idempotent: it sees the matching tag and creates only the release. |
| Finalize refuses to run | The cause is a `v<version>` tag that does not point at the merge commit, a release without its tag (a draft, or one cut by hand), or a failed remote lookup. Fix the cause, then re-run. |
| Two release PRs merged close together | Finalize runs in one FIFO queue. Newer-after-older publishes both. Older-after-newer fails closed with no tag and no release: cut a corrective release with a higher version. |
| A changie fragment merged to `main` after Prepare ran | See [Late changie fragment](#late-changie-fragment). |

For a verification drill of Finalize's idempotency paths, see
**Release — Verify Finalize recovery** in `AGENTS.md`. The drill is not the
routine recovery path.

### Late changie fragment

Prepare batches only the fragments that are on `main` when it runs. A fragment
merged afterwards is not in the open release PR. It is not lost: it stays in
`.changes/unreleased/` on `main` after the release PR merges, and it ships in the
next release. If it must be in this release, use one of these options:

- **Re-dispatch (preferred).** Close the release PR and delete its
  `release/v<version>` branch. Then run Prepare again with the same version. The
  new PR batches every fragment that is on `main` now. This is safe because
  nothing was tagged or published, and `.changes/<version>.md` exists only on the
  unmerged branch.
- **Rebase the release PR.** Rebase `release/v<version>` onto `main`. Then move
  the new fragment's body into `.changes/<version>.md` under its kind heading,
  delete the fragment, and run `changie merge` to rebuild `CHANGELOG.md`. Push the
  result and have the extra commit reviewed with the PR. Use this option only
  when a re-dispatch is not possible, because the release commit is no longer
  purely generated.

Do not merge the release PR and then add the fragment to `.changes/<version>.md`
on `main`. Finalize publishes the release body from the file as it was at the
merge commit.

## Roll back a bad release

### Unpublish means revert on `main`

Installs read manifests and plugin files from `main` (or from the ref that the
user pinned). Deleting a GitHub release or a tag does not remove anything that
users install. To withdraw a bad change:

1. Open a PR that reverts the change on `main`, with a changie fragment (`Fixed`,
   or `Removed` if you withdraw a feature). Merge it.
2. Cut a new patch release immediately (see [Cut a release](#cut-a-release)).
   Installed plugins are cached by version, so existing installs pick up the
   revert only when the version changes.
3. Tell users who pinned the marketplace to the bad tag to move to the new tag.

Never re-release the same version number. Prepare refuses a version whose tag
exists, and a reused version would not replace the copies that are already
cached.

### Yank a bad GitHub release

The GitHub release is only a changelog announcement. Use one of these options:

- **Mark it (preferred).** Add a warning to the release notes that points to the
  fixed version, and mark the release as a prerelease so that it loses the
  **Latest** badge:

  ```bash
  gh release edit v<version> --prerelease --notes-file notes.md
  ```

- **Delete it.** `gh release delete v<version> --yes` removes the release and
  keeps the tag. Do not add `--cleanup-tag`.

After either option, check which release GitHub shows as **Latest**. If
necessary, set it with `gh release edit v<previous> --latest`. Do not re-run
Finalize for the yanked version, because it would publish the release again.

### `v*` tag deletion policy

Do not delete or move a published `v*` tag. Tags are the release record:

- Finalize compares each new version with the newest existing tag. Deleting a
  tag weakens that downgrade check.
- A deleted tag lets Prepare accept the same version again.
- Users who pinned the tag lose their ref.

On 2026-09-23, no tag ruleset protected `v*`, so deletion was prevented only by
this policy. [#175](https://github.com/nq-rdl/agent-extensions/issues/175) plans
a tag ruleset that restricts creation and deletion of `v*` tags to the release
GitHub App. After it is active, deleting a tag needs a ruleset bypass. The only
acceptable reason is a tag that points at the wrong commit and has no published
release. In that case, record the reason in the release PR or in an issue.
