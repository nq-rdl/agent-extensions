# Hash-only SQL review records — issue #505

Status: proposed; implementation awaits design review.

## Intent and acceptance

Resolve [agent-extensions#505](https://github.com/nq-rdl/agent-extensions/issues/505):
retain hashes and reproducible source commits instead of generated SQL under
`.sqlreview/`. Engineers and analysts must still see line diffs and re-prove
carried confirmations against the earlier revision. No existing git history is
rewritten. Hand-written SQL remains in its maintained location in git.

After bootstrap, analyse, publish and snapshot, `.sqlreview/` contains no SQL
text files, including intermediate files. Historical and current SQL used for
comparison exist only in private temporary directories outside the repository.
An unavailable historical render is reported as unavailable, never unchanged.

## Existing behavior and affected consumers

Repository inspected at `cba1a3f9cffbf1613029bfe045027a8841e554a3`.

| Consumer | Existing dependency | Required replacement |
| --- | --- | --- |
| `sqlreview.sh fingerprint` | Hashes the current SQL file | Fresh render, or maintained hand-written source |
| `publish` | Current SQL and `source.sql` / `scope.source.sql` | Fresh current render and authenticated historical render |
| `snapshot` | Writes baseline and `history/<revision>.sql` | Verify committed-source evidence; write no SQL |
| `delta`, `impact` | Baseline and current SQL files | Two temporary authenticated renders |
| `carryforward`, `carryover` | Baseline bytes for item ranges | Earlier render authenticated against recorded full SHA |
| `remap` | Baseline, current file, temporary SQL under `.sqlreview/` | Temporary render pair outside the repository |
| `status`, hook completion checks | Snapshot existence and binding | Reproducible reference and render binding |
| `release.sh evidence` | SQL blob at release ref and baseline | Render at release ref and authenticate reviewed source |
| Bootstrap skill | Directly copies `scope.source.sql` | Publish records provenance atomically |
| Explain skill | Reads baseline/history SQL paths | Materialize recorded revisions temporarily |
| Header-decision proof | Git history of rendered SQL | Source history plus authenticated renders |

Change canonical `skills/` content only; regenerate Claude and Codex copies
with `pixi run bash scripts/sync-plugins.sh data-request`.

## Rendering contract

Use a shared Bash 3.2 + jq helper in the setup skill. Keep SQL generation in the
child's existing runtime, rather than introducing a second query-builder
implementation in this marketplace. Expose a project adapter as an argv array
in `.sqlreview/config.json` under `sql_render.command`; execute arguments
directly, never through `eval` or a shell command string. The adapter receives
`--sql-path <project-relative path> --output <absolute temporary file>` and
runs from the project root. A zero exit code requires a regular output file.
Stdout is not the SQL channel; failed adapter output is not printed as SQL
review evidence. The adapter must render only, with no database connection or
extract execution.

The scaffold adapter resolves each path through `sql/provenance.json`, uses
the declared builder/cohort/spec and its locked dependencies, and reproduces
the exact UTF-8 bytes, including final newline. The scaffold's current
`run_extract.py` includes connection and execution capabilities; do not invoke
its extract CLI to obtain SQL. Extract a render-only interface as part of
[scaffold#290](https://github.com/nq-rdl/data-analysis-scaffold/issues/290).
Until an adapter is present, generated paths fail with an actionable missing
adapter message. Do not silently hash an old generated file.

Provenance manifests select generated versus hand-written paths. For an
explicitly hand-written path, read the maintained SQL at the selected commit;
for legacy projects without a manifest or adapter, a tracked SQL source is
the compatibility route. An untracked SQL file without a generator declaration
cannot supply durable review evidence.

Historical rendering uses a disposable checkout of the exact source commit,
outside the repository, with no checkout hooks. Use the adapter/configuration
and dependency pins from that commit. Do not inject current builders, current
configuration, credentials, or uncommitted changes into historical renders.
Resolve refs to immutable commit IDs before rendering. Support project roots
below the git top level by recording their relative prefix.

Historical dependency availability is a prerequisite: missing commits, missing
pins, unavailable dependencies, render failures and hash mismatches are distinct
failures. Never replace them with a committed SQL snapshot or an assumed match.
Temporary directories are private and removed on normal exit and trapped
signals. No SQL is put in argv or written under `.sqlreview/`.

## Record and publication contract

Preserve existing `sql_sha256`, `sql_body_sha256`, `git_commit`, revision and
human confirmation fields. Add helper-owned `sql_provenance` containing the
mode (`rendered` or `tracked`), project-root prefix and immutable source commit.
For new SQL-bound records, `git_commit` equals that source commit and
`git_dirty` is false. A scope framed before SQL exists can retain a null hash
and no SQL provenance, preserving `scope-before-sql` carry behavior.

Fingerprint renders from HEAD in a disposable checkout. It refuses uncommitted
source changes; review-record-only edits and ignored runtime outputs do not
change source identity. Commit builder/configuration/pins before fingerprinting.
It returns the existing hash/body-hash/commit fields plus `sql_provenance`.
A manifest hash alone is not fresh render evidence; compare it with the render
when the manifest declares one.

Publish re-renders the draft's recorded commit and current HEAD. Authenticate
the recorded render against the full recorded SHA before any body or line
comparison, including when the current hash happens to match. Publication
refuses a changed body or nonreproducible commit. Keep the existing conservative
header-only behavior: authenticate the original full render first, record the
new full header hash and source commit in helper-owned `header_revisions`, and
preserve the original confirmation provenance. Changed item text, rationale
or decisions still require confirmation.

Publish stores the previous JSON at `history/<kind>/<revision>.json` for scope
and review, just as lifts already retain JSON history. Check history conflicts
before replacing the final document. Each JSON contains its own hash and
source commit; history never contains rendered SQL. Snapshot becomes an
idempotent verification command for the published review, not a second write
of its baseline. A failed publication cannot advance provenance/history.

Carry checks use the previous published document of the same kind and the
authenticated earlier render, preserving all existing confirmation and
line-range rules. Missing evidence must not become `sql-absent`; only a scope
that explicitly had no SQL qualifies for the existing absence/intent rules.
Release evidence renders the release ref, preserving ancestor, question and
header/body checks. Explain materializes the exact recorded revision; it must
not substitute current SQL when offering to explain an earlier review.

Header-decision eligibility must inspect the committed maintained source and
its rendered header history. Until that history can be proved, refuse fresh
header-decision carry eligibility and require ordinary item confirmation;
other valid carry bases continue to work.

## Migration

Add `sqlreview.sh migrate-snapshots [--check]`. Dry-run lists planned removals
and evidence availability without changing files. The apply command preflights
all candidate files and JSON, rejects symlinks/nonregular files, computes each
legacy snapshot's SHA, and preserves it in JSON before deleting any SQL.

Retain each existing document's recorded full SHA verbatim. Preserve hashes
for otherwise orphaned `history/*.sql` in a helper-owned legacy hash index.
Never guess which commit produced a dirty or null-commit snapshot. Mark such
revisions as unavailable for reconstruction and require reassessment when a
historical proof is needed. A matching render at a recorded commit may promote
that revision to reproducible provenance; a mismatch preserves the original
hash and reports unavailable evidence.

Remove `source.sql`, `scope.source.sql` and `history/*.sql` from the working
tree. The deletions are included in the child's normal reviewed commit; no
git history rewrite or automatic child push occurs. Install a per-store
`.gitignore` for legacy snapshot paths so an interrupted older workflow does
not accidentally add a new SQL copy. Re-runs are idempotent. Preserve reports,
human confirmation records, questions, lift history and unrelated files.

## Validation for implementation

- Real temporary git child with an ignored generated SQL path: fingerprint,
  scope/review publish and snapshot leave no SQL under `.sqlreview/` or in its
  staged diff, even when the generated file never exists in the working tree.
- Commit a builder change: delta shows the actual old/new line diff; impact
  and remap use those same authenticated bytes.
- Carry an unchanged range across a changed builder and shifted lines; retain
  confirmation provenance. Changed governed lines and corrupt historical
  hashes refuse carry at publication.
- Refuse missing commit/adapter/dependency, dirty source, nondeterministic
  render, manifest mismatch and missing output. No failure reports unchanged.
- Verify header-only binding and fresh header-decision refusal when historical
  decision provenance is unavailable; preserve scope-before-SQL behavior.
- Release and explain work when generated SQL is absent from all git trees.
- Migration preserves every recorded/hash-only revision, removes SQL copies,
  handles orphan history, refuses unsafe paths, and is repeatable.
- Interrupted publication/migration preserves published JSON and hash evidence;
  temporary SQL remains outside the project and is cleaned up.
- Run existing review, carry, header, remap, release, hook and pipeline tests;
  update snapshot-specific assertions to the new public contract. Run the
  repository's strict Bash 3.2 portability gate and generated-copy checks.

## Implementation boundary

This PR currently proposes the design only. It does not close #505 and does
not change shipped behavior. After approval, write the implementation plan,
then implement on this branch. Scaffold#290 supplies the production render
adapter; test this repository against a deterministic fixture adapter and
report production integration as pending until the scaffold contract is met.
