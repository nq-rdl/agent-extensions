# Maintainer SQL review snapshot cleanup

This is a separate rollout deliverable for existing child repositories. The
utility is not installed in either plugin, exposed by `sqlreview.sh`, or called
by the skill runtime. Installing the hash-only runtime does not migrate a child.
No affected child has been migrated by this repository change. The affected-repo
inventory and individual operator handoffs remain pending.

## Inventory and handoff

Before applying cleanup, inventory each affected repository and its review
stores. Assign an operator and a normal reviewable PR branch per child. Record
the repository, branch/base commit, store paths, snapshot count, check output,
operator, and eventual PR/verification status in the rollout tracking record.
Run only against the intended git working-tree root. Use an exclusive working
tree without a concurrent review publication, cleanup, or filesystem edit.
Review unrelated changes before starting; retain any pre-existing dirty state
in the handoff. The utility does not require a clean working tree and does not
infer that a dirty or null commit is valid evidence.

Prerequisites are Bash 3.2 or later, `jq`, git, standard file utilities, and either
`sha256sum` or `shasum`. There is no new Python dependency. Supply a checkout of
this maintainer repository separately from the child's installed skills.

## Check and apply

Set `CHILD` to the absolute child working-tree root and `MAINTAINER` to this
repository checkout. Create the child's PR branch using the repository's normal
process, then inspect its starting status and planned removals:

```bash
git -C "$CHILD" status --short
bash "$MAINTAINER/scripts/migrate_sqlreview_snapshots.sh" --root "$CHILD" --check
```

Check-only prints each full SHA-256 and project-relative legacy filename,
followed by a removal count, and changes no child files. Capture this output in
the operator's handoff before applying. Both check and apply validate every JSON
file in `.sqlreview/`, the audit index if present, and review-store paths.
Malformed/multiple JSON documents, symlinks, nonregular files, unsafe audit paths
and conflicting saved hashes stop cleanup before any child-file mutation.
Resolve these inputs explicitly and rerun check; do not bypass the checks.

```bash
bash "$MAINTAINER/scripts/migrate_sqlreview_snapshots.sh" --root "$CHILD"
git -C "$CHILD" status --short
```

Only `.sqlreview/reviews/<slug>/source.sql`, `scope.source.sql` and immediate
`history/*.sql` are removed. Orphan history SQL copies are included even when
no JSON revision refers to them. Unrelated SQL, nested history files, reports,
questions, lift history, scope/review JSON and human confirmation fields remain
byte-for-byte unchanged. The utility appends missing snapshot exclusions to
`.sqlreview/.gitignore`, retaining existing content as a byte-identical prefix.
It creates no SQL files.

## Inspect hash preservation and recovery

All candidate hashes are persisted together by an atomic replacement of
`docs/maintenance/sqlreview-snapshot-hashes.json` before the first SQL deletion.
The passive index has this shape:

```json
{
  "schemaVersion": 1,
  "snapshots": {
    ".sqlreview/reviews/example/history/7.sql": {
      "sql_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  }
}
```

The key is the project-relative legacy filename, and the value contains only
`sql_sha256`. Inspect all entries and compare each against the captured check
output, including orphan history files:

```bash
jq -r '.snapshots | to_entries[] | [.value.sql_sha256, .key] | @tsv' \
  "$CHILD/docs/maintenance/sqlreview-snapshot-hashes.json"
git -C "$CHILD" diff -- .sqlreview docs/maintenance/sqlreview-snapshot-hashes.json
```

A new untracked index does not appear in `git diff` until the maintainer stages
it; inspect the file directly first. If there were no SQL candidates and no
existing index, no index is created. Review JSON should have no diff. Compare
unstaged changes against the recorded starting state as well as the PR base.
The JSON records' original commit/hash/confirmation values are deliberately
unchanged, even when commits are null or marked dirty. Do not add provenance,
guess commits, or refresh confirmations as part of cleanup.

If cleanup is interrupted after hash persistence, all hashes remain available
although some SQL copies may remain. Rerun check and apply in the same exclusive
working tree. Existing entries are verified against remaining SQL bytes;
a conflicting hash refuses cleanup rather than overwriting evidence. Already
removed snapshots keep their audit entries. Successful reruns produce no further
changes. A failure during deletion can therefore leave a partial cleanup with a
complete index; inspect the error and rerun after resolving its cause. Atomic
replacement protects against process interruption, not a promise of durability
through storage hardware failure.

The runtime never reads the index. These hashes cannot supply absent SQL,
authorize a carry, or repair unavailable/dirty historical evidence. Such records
still require reassessment when their historical SQL is needed.

## Child PR verification and completion

The utility never stages, commits, pushes, rewrites history, or executes SQL.
The maintainer stages the named deletions, ignore additions and passive audit
index through the child's usual PR process after inspection. Include the
inventory/check evidence and confirm the preserved JSON/report/question/lift
bytes in the PR. Verify that no unrelated files changed and rerun check/apply to
confirm idempotence. Retain deleted SQL in existing git history; do not rewrite
history as part of this rollout.

Mark an individual child migrated only when its reviewed PR and hash-preservation
checks are verified. Runtime completion, delivery of this utility and completion
of each child's cleanup are separate tracking items. A future scaffold
`copier update` may call this cleanup contract; that wiring is outside this
utility's delivery. Production committed-source adapter integration remains
tracked separately in scaffold#290.
