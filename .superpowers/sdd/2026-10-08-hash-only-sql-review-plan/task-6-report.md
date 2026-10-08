# Task 6 implementation report

Status: DONE. Deliverable is the separate maintainer cleanup utility and runbook;
no actual child repository was applied or marked migrated. Affected-repo inventory
and operator handoffs remain pending.

## Implemented

- `scripts/migrate_sqlreview_snapshots.sh`: Bash 3.2-compatible shell/file/git/jq
  plumbing, `--root CHILD [--check]`, no Python runtime or eval. Requires the
  intended real git working-tree root. Inventories `.sqlreview/`, preflights all
  descendant paths and JSON, and checks ignore/audit parents and passive index
  schema before child mutations. Refuses symlinks, nonregular files, malformed,
  empty/multiple JSON, control-character paths, and audit hash conflicts.
- Hashes only direct review `source.sql`, `scope.source.sql`, and immediate
  `history/*.sql`, including orphan history. Atomically persists the complete
  passive `schemaVersion: 1` index with filename keys and `sql_sha256`-only values
  before deleting the first SQL file. Existing index evidence is preserved and
  conflicts are verified rather than overwritten; matching existing index bytes
  are not rewritten. Rechecks candidate bytes before deletion.
- Preserves scope/review JSON, confirmation fields, questions, lifts, reports,
  unrelated SQL and existing custom ignore bytes. Adds missing exclusions as
  append-only content. Does not stage, commit, push, execute SQL, rewrite history,
  infer commits/provenance, or refresh confirmations. Runtime never reads index.
- `docs/sqlreview-snapshot-cleanup.md`: inventory/operator handoff, check/apply,
  passive hash inspection, interruption recovery, reviewable child PR process,
  and separate runtime/utility/child completion records.
- `tests/test_sql_review_snapshot_migration.py`: 11 real temporary git-child tests,
  using full existing review/scope fixture schemas with null `git_commit` and
  dirty commit records, byte preservation and unstaged/index/HEAD assertions.
  A PATH-only `rm` shim refuses the first SQL deletion, verifying that all hashes
  were already persisted and a normal rerun recovers; no production test hook.

## TDD evidence

RED command (before utility existed):

```text
PATH=/workspace/scratch/a49ed4839082/toolchain:/workspace/scratch/a49ed4839082/toolchain/go/bin:$PATH pixi run python3 -m unittest discover -s tests -p test_sql_review_snapshot_migration.py
Ran 6 tests in 0.293s
FAILED (failures=2, errors=1)
check/apply: 127 != 0; bash: scripts/migrate_sqlreview_snapshots.sh: No such file or directory
interruption: FileNotFoundError reading the not-yet-created passive audit index
```

Failures were expected because the specified utility and its hash-persistence
behavior had not been implemented. Negative refusal cases initially passed
because a missing utility also refuses execution; successful application and
interruption assertions supplied the positive behavior gate.

First GREEN after implementing utility: same command, `Ran 6 tests in 1.150s`,
`OK`. Expanded focused GREEN: same command, `Ran 11 tests in 1.833s`, `OK`.
Final focused run covers check byte preservation, successful/idempotent cleanup,
null/dirty commit and confirmation preservation, orphan hashes, unsafe JSON and
paths, malformed/symlink/FIFO/directory audit paths, index conflicts (including
NUL keys), custom ignores with/without a final newline, matching audit byte
preservation, missing-store noop/missing-ignore creation, interruption recovery,
and refusal of changed SQL against previously saved evidence.

## Static and packaging checks

```text
bash -n scripts/migrate_sqlreview_snapshots.sh
exit 0; no output
pixi run bash scripts/sync-plugins.sh --check data-request
Checking data-request -> plugins/data-request
plugin trees are in sync with canonical skills/.
exit 0 (includes Codex package --check)
find skills plugins dist/codex -name migrate_sqlreview_snapshots.sh -o -name sqlreview-snapshot-cleanup.md
no output
rg -n 'migrate_sqlreview_snapshots|sqlreview-snapshot-cleanup' skills plugins dist/codex
no matches (exit 1, expected)
git diff --check
exit 0; no output
```

Self-review checked the full utility/tests/runbook and task requirements. Empty
array counts use an explicit counter to avoid old Bash nounset pitfalls. Audit
path controls are refused consistently with filesystem paths. No generated tree,
installed instruction, dispatch, runtime helper, ledger or plan was edited.

## Limitations and rollout boundaries

- Local Bash 3.2 runtime is unavailable and the earlier preparation was rejected
  by automatic approval review. No download/preparation retry was made. Host
  Bash syntax and behavior plus a manual Bash 3.2 construct review are verified;
  actual Bash 3.2 execution remains a reported verification limitation.
- Per controller authorization, only focused isolated-component tests/static and
  generated-boundary checks were run; the already-reviewed tasks 1–5 full suite
  was not repeated for this separate utility.
- Atomic replacement protects process interruption; there is no hardware-durable
  fsync guarantee or concurrent-editor support. The runbook requires an exclusive
  child working tree. Actual child inventory/application/PR verification remains
  pending. Production scaffold adapter integration belongs to scaffold#290.
