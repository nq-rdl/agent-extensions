# Hash-only SQL Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Direct implementation in this session is recommended; execution choice awaits plan review.

**Goal:** Resolve #505 by retaining reproducible hashes and source commits while preserving SQL diffs, confirmation evidence and release checks.

**Architecture:** One shared Bash helper reconstructs committed sources into private temporary storage. Existing consumers authenticate those renders instead of snapshot files; JSON history retains revision identities. A separate unbundled maintainer utility preserves legacy hashes and cleans existing child repos.

**Tech Stack:** Bash 3.2-compatible shell, jq >= 1.6, git; pixi-managed Python for tests and packaging. SQL generation remains in the child's runtime.

**Spec:** [Approved design](2026-10-08-hash-only-sql-review-design.md).

## Global Constraints

- Bash 3.2 + jq; no new Python runtime in shipped review helpers, no `eval`.
- New workflows write no SQL text files under `.sqlreview/`, including temporary render/diff inputs; existing copies are removed separately.
- Authenticate full recorded SHA before body/line binding; unavailable evidence never means unchanged or SQL absent.
- New SQL-bound records reference committed sources; scope-before-SQL retains null-hash behavior.
- No git history rewrite, automatic child push, extract execution or database connection.
- Edit canonical `skills/` and `hooks/`; regenerate both published skill trees.
- Production scaffold adapter belongs to scaffold#290; use a real committed fixture adapter here and report that integration boundary.
- Migration utility/runbook stay outside `skills/`, `plugins/` and `dist/codex/`; no migration subcommand or migration instructions in the packaged skill.

## Review Focus

1. Project root below git root: historical renders must use the correct committed prefix (Task 1).
2. Paths/argv with spaces, quotes, Unicode or newlines: preserve argv and exact SQL bytes (Task 1).
3. Legacy scaffold manifest hashes normalize BOM/CRLF/trailing blank lines: do not confuse manifest hashes with the review's exact-byte SHA (Task 1).
4. Interruption or concurrent edits: keep published JSON/hash evidence intact; remove temporary SQL (Task 2 and separate Rollout A).
5. Missing or corrupt historical source: no automatic `sql-absent`, header-only match or line carry (Tasks 3, 4).

## Task 1: Shared render and provenance interface

**Files:** Create `skills/data-request-setup/scripts/sqlreview-source.sh`, `skills/data-request-setup/references/sql-provenance.rst`, `tests/test_sql_review_sources.py`; modify `sqlreview-lib.sh`, `sqlreview.sh`, `sqlreview-check.jq` in that scripts directory and `tests/test_sql_review_scripts.py` for reusable fixtures.

**Interfaces:** `sr_source_render REF SQL_PATH OUTPUT` resolves REF to a commit, renders into caller-owned OUTPUT, and sets `SR_SOURCE_COMMIT`, `SR_SOURCE_MODE`, `SR_SOURCE_PREFIX`. `sr_source_auth DOC OUTPUT` reconstructs the document's source and authenticates full/body hashes. `sr_source_clean` refuses uncommitted source changes. Callers own a trapped private workspace outside the git tree. New `sql_provenance` fields are `{mode, project_root, commit}`; mode is `rendered` or `tracked`, project_root is a normalized relative prefix (empty at git root), commit is immutable and equals `git_commit`.

- [ ] Write `Sources.test_generated_sql_absent_from_git` using a committed shell adapter and ignored `sql/request.sql`: fingerprint must return SHA256 of exact `SELECT 1;\n`, HEAD commit, `git_dirty: false`, mode `rendered`, and no SQL file under `.sqlreview/`.
- [ ] Add `test_historical_adapter_and_nested_root`, `test_argv_and_exact_bytes`, `test_manifest_hash_semantics`, `test_dirty_source_refused`, `test_generated_path_without_adapter_refused`, `test_failure_output_not_leaked`, `test_missing_or_symlink_output_refused`. Pin manifest classification to `.requests[path].source` (`builder`, `cohort`, `spec`, `hand-written`); validate malformed/undeclared entries. Preserve exact-byte review hashes while honoring a declared manifest hash's algorithm. A canonical legacy hash is not a raw-byte provenance hash.
- [ ] Run `pixi run python3 -m unittest discover -s tests -p 'test_sql_review_sources.py' -v`; verify failures are the missing reconstruction behavior.
- [ ] Implement the interfaces and wire fingerprint. Read adapter argv from the selected commit's `.sqlreview/config.json`; invoke it with `--sql-path` and `--output`. Use disposable git checkout with hooks disabled. Refuse replacement refs/grafts, unsafe prefixes/paths, missing commits and source symlinks. Capture adapter logs privately and emit classified errors rather than SQL. Ignore only review-record changes under `reviews/`, `templates/`, `ledger.json` and the store ignore file; config/adapter/manifest/pin changes remain source changes. Ignored outputs are not source changes.
- [ ] Document the adapter, clean-source prerequisite, provenance fields and manifest hash distinction in the reference. Run the new suite and existing fingerprint/path tests; update fixtures to commit maintained sources where required. Commit this task.

## Task 2: Atomic publication and JSON revision history

**Files:** Modify `skills/data-request-setup/scripts/sqlreview.sh`, `sqlreview-check.jq`, `sqlreview-lib.sh`; tests `test_sql_review_publish.py`, `test_sql_body_binding.py`, `test_sql_review_bootstrap_header.py`, `test_sql_review_regressions.py`.

**Interfaces:** Publish authenticates draft source and current HEAD through Task 1. Prior scope/review JSON is retained at `history/<kind>/<revision>.json`. Snapshot verifies the published review and creates no SQL. Historical reconstruction absence has exit 6; malformed input/operational errors retain exit 2, invalid documents exit 4. Binding remains 0 full / 10 header-only / 1 changed internally.

- [ ] Write `Publish.test_rendered_publication_without_snapshots`, `test_revision_history_retains_hash_and_commit`, `test_history_conflict_preserves_final`, `test_failed_publication_preserves_history`, `test_snapshot_is_idempotent_verification`: assert zero `.sql` files and zero `.sql` additions in staged `.sqlreview/` diffs after scope and review publication/snapshot.
- [ ] Add header-only tests that preserve the original full SHA/confirmation and record current header hash plus source commit; corrupt recorded full hashes must refuse publication even with matching body hashes. Test source changes between fingerprint and publish and publication interrupted before replacement.
- [ ] Add legacy-record tests with no `sql_provenance`: authenticate only a recorded clean commit reproducing the full hash; null/dirty/mismatched evidence refuses historical proof without consulting any cleanup index.
- [ ] Run the named test files and observe the expected snapshot-dependent failures before implementation.
- [ ] Replace snapshot writes with authenticated render binding; validate helper-owned provenance consistency. Preflight history conflicts, preserve prior JSON atomically, then replace final JSON. Re-check source/document identity before replacement. Keep lifts publication and question semantics intact.
- [ ] Run the publication/body/header/regression suites; update assertions that explicitly require SQL copies to assert provenance/history instead. Commit this task.

## Task 3: Diffs, carry checks and line remapping

**Files:** Modify `skills/data-request-setup/scripts/sqlreview.sh`, `sqlreview-lib.sh`, `sqlreview-carry.jq`; tests `test_sql_review_sources.py`, `test_sql_review_carryforward.py`, `test_sql_review_carryover.py`, `test_sql_review_scope_carry.py`, `test_sql_review_remap.py`, `test_data_request_grain.py`.

**Interfaces:** `_delta_prepare` and `_carry_context` supply temporary authenticated `SR_BASE`/`SR_CUR` and `CF_BASE`/`CF_CUR` paths from Task 1; preserve existing carry result fields/bases. Callers trap cleanup across success, failure and signals. Remap freezes both reconstructed SQL and JSON outside the repository and checks commit/input identity before replacing only draft JSON.

- [ ] Write a two-commit builder fixture: delta must display `-SELECT 1;` and `+SELECT 2;`, return 10, and leave no SQL in `.sqlreview/`; impact uses the same renders. Add shifted-range remap and unchanged-range carry tests retaining prior `confirmed_by`, `confirmed_at`, `confirmed_revision` and `carried_from_revision`.
- [ ] Add `test_corrupt_previous_hash_cannot_carry`, `test_missing_commit_is_not_sql_absent`, `test_no_sql_scope_keeps_intent_carry`, `test_changed_governed_lines_refused_at_publish`, `test_remap_concurrent_input_change_refused`.
- [ ] Run these tests, confirm expected failures, then replace baseline-file lookups in delta/impact/carryforward/carryover/remap with the shared source interface. Keep authenticated absence distinct from unknown evidence in the jq context. Provide scope delta support for bootstrap's former direct file diff.
- [ ] Run all carry/remap/grain tests and two-commit acceptance tests; verify cleanup on nonzero exits. Commit this task.

## Task 4: Status, explanation, header decisions and release evidence

**Files:** Modify `skills/data-request-setup/scripts/sqlreview-lib.sh`, `sqlreview.sh`, `release.sh`; `hooks/data-request-preflight.sh`, `hooks/data-request-guard.sh`; tests `test_sql_review_sources.py`, `test_sql_review_completion.py`, `test_sql_review_hooks.py`, `test_sql_review_header_carry.py`, `test_sql_review_notes.py`, `test_data_request_release.py`.

**Interfaces:** Add `sqlreview.sh materialize SLUG scope|review REVISION OUTPUT`, selecting current/published historical JSON, authenticating it, and refusing outputs inside the repository. The caller deletes OUTPUT. Status uses committed-render binding; `no-baseline` means unavailable provenance, not a missing snapshot file. Release evidence calls `sr_source_render` at its resolved release commit and retains ancestor/question checks.

- [ ] Write `test_release_ref_uses_historical_builder`, `test_materialize_exact_revision`, `test_materialize_refuses_in_repo_output`, `test_status_without_working_sql`, `test_unknown_render_cannot_complete`, `test_generated_header_decision_unproved`: generated SQL must be absent from every git tree; checks still distinguish current/header-only/changed/unavailable.
- [ ] Run the new tests to show snapshot/blob assumptions fail. Wire state, release and materialize through Tasks 1–3. Ensure full baseline authentication precedes release body binding. Operational failure is visible and cannot satisfy completion.
- [ ] Keep tracked-source header-history proof. For generated-source histories that cannot prove all intermediate committed rendered headers, emit no fresh header-decision eligibility and require ordinary confirmation. Preserve other valid carry bases and existing malformed-header rules.
- [ ] Change the guard to refuse direct writes of legacy snapshot paths and update preflight hints. Run completion, hook, notes, header and release tests; commit this task.

## Task 5: Workflow instructions, packaging and full verification

**Files:** Modify `skills/data-request-{setup,bootstrap,analyse,explain}/SKILL.md` and relevant `.rst` references, including `references/codex.rst` when present; update `docs/data-request-permissions.md` if runtime guidance needs the adapter; add a Changie fragment. Regenerate `plugins/data-request/` and `dist/codex/plugins/data-request/`. Extend `scripts/run_bash32_portability.py`, `tests/bash32_fixture.py` as needed and add `tests/test_sql_review_sources_bash32.py`.

- [ ] Add content tests that fail on workflow instructions copying snapshots or assuming generated SQL is tracked, and Bash 3.2 fixture cases exercising adapter argv, historical render, publish and carry. Assert no migration command, utility or runbook appears in either generated plugin tree.
- [ ] Run them to observe expected failures. Update workflows to commit maintained source, fingerprint/render for review, publish/hash verification and temporary historical materialization. Include historical-evidence reassessment and the scaffold adapter prerequisite; exclude rollout instructions. Add fresh-store ignore rules `/reviews/**/source.sql`, `/reviews/**/scope.source.sql`, `/reviews/**/history/*.sql`. Keep new skill bodies within 500 lines and references within each installed skill.
- [ ] Refresh copies with `pixi run bash scripts/sync-plugins.sh data-request`. Create a Changie entry under 200 body characters; remove `skip-changelog` from PR #506 when runtime work is present.
- [ ] Run `pixi run python3 -m unittest discover -s tests -p 'test_*.py'`, `pixi run bash scripts/validate-plugins.sh`, `pixi run bash scripts/sync-plugins.sh data-request --check`, `go -C tools/asctl test ./...`, build asctl and run `repo-check`, and `git diff --check`. Run strict Bash 3.2 preparation/execution from `docs/bash32-portability.md`; skips do not prove portability. Confirm the sync script's option ordering before its check invocation.
- [ ] Review the complete diff against all acceptance items; independently review using the selected execution workflow. Update PR title/body to final implemented behavior, validation results and scaffold integration status. Push the branch and resolve applicable CI failures; leave the PR unmerged. Do not claim production scaffold integration or close #505 until its required adapter is verified.

## Separate Rollout A: Maintainer cleanup utility and child PRs

This is a rollout deliverable, separate from the five packaged-runtime tasks.
The utility can be reviewed in this branch; execution in child repositories
requires the affected-repo inventory and corresponding operator handoff.

**Files:** Create `scripts/migrate_sqlreview_snapshots.sh`, `docs/sqlreview-snapshot-cleanup.md`, `tests/test_sql_review_snapshot_migration.py`. No changes to `sqlreview.sh` dispatch or installed skill instructions.

**Interfaces:** `bash scripts/migrate_sqlreview_snapshots.sh --root CHILD [--check]`. The child's passive audit file `docs/maintenance/sqlreview-snapshot-hashes.json` has schemaVersion 1 and `snapshots` keyed by project-relative legacy path, each containing `sql_sha256`. The runtime does not consume this file; existing scope/review JSON stays byte-for-byte unchanged.

- [ ] Write tests for check-only byte preservation, successful/idempotent removal, null/dirty commit record preservation, orphan `history/7.sql` SHA preservation, malformed JSON/symlink/nonregular refusal, audit-index conflict, custom ignore preservation and interruption after hash persistence. Assert confirmation/question/lift/report bytes remain unchanged.
- [ ] Run migration tests to confirm missing-utility failures. Preflight all candidates before changing files; compute and atomically persist all hash evidence before deleting the first SQL copy. A rerun verifies index entries rather than overwriting conflicts. Remove only named legacy files; never stage/commit/push a child or rewrite history.
- [ ] Add snapshot ignore rules to existing stores without replacing custom content. Document inventory, check/apply, hash-preservation inspection and normal child-PR review in the maintainer runbook. Do not infer commits, add provenance or refresh human confirmations.
- [ ] Run utility tests and verify it/runbook are absent from regenerated plugin trees. Record cleanup delivery separately from runtime completion; existing children remain pending until their individual PRs are verified.

## Review and execution handoff

The spec and separate migration delivery are approved. This revised plan
awaits review before runtime implementation. No affected child repos have
been changed or marked migrated.
Recommended method: implement directly in this session using executing-plans,
then review the whole branch independently. The tasks share one rendering and
provenance interface, so implementing them in sequence avoids interface drift.
