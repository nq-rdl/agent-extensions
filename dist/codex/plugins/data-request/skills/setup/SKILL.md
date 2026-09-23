---
name: setup
license: CC-BY-4.0
description: 'Initialise project scope and review records for the Data Request workflow:
  create the .sqlreview/ directory with config.json (settings + the shared assumption/limitation
  definitions) and the scope/review report templates, from the bundled default or
  from answers to a few questions. Safe to re-run — an existing setup is diffed file
  by file and nothing is overwritten without confirmation. Use once per project before
  $data-request:bootstrap, :analyse or :explain, or whenever one of them reports "not
  initialised".'
compatibility: .sqlreview schema 2 (schema 1 remains readable) (docs/specs/2026-09-15-sql-review-plugin-design.md);
  bash 3.2+, jq >= 1.6, git optional. macOS and Linux.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Use the host’s available file, search, shell, and user-question tools for this workflow. Legacy tool names and slash-qualified skill references in supporting references describe capabilities; they do not install those tools. Keep code/configuration examples for another host unchanged when authoring that host’s artifacts.

When supporting references invoke a catalog skill as /subject:facet, use $subject:facet in Codex. Preserve slash syntax inside examples that configure or document another host.

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate a shell variable for them. Pass arguments with shell quoting that preserves literal text; never evaluate user text as shell code.

# Data Request — setup

Creates the `.sqlreview/` contract used by bootstrap, analyse, explain and lift.
Ordinary composition can run without setup; recording a hand-SQL candidate silently
initialises the default store when absent. **Among the record stages, setup alone accepts an
uninitialised project**: `sqlreview.sh status` exiting 3 means "proceed to init".
Arguments: `$ARGUMENTS`.

```bash
S="${PLUGIN_ROOT}/skills/setup/scripts"
bash "$S/sqlreview.sh" init --diff        # exit 0: all files match the bundled default
                                          # exit 10: lists new / same / differs per file (with a diff)
```

The root is the git top-level (or the cwd outside git); it is not configurable — hooks, helpers
and the other stages all resolve the same `.sqlreview/` by walking up from the cwd.

## 1. Fresh project (every file reported `new`)

`--check`: report and stop. Otherwise, unless `--default`/`--custom` was given, ask **once**
(the host user-question tool), options in this order:

- **Default (Recommended)** — the bundled template as-is: the shared definitions
  (`references/definitions.rst`), roles "Data Engineer (RDL)" / "Data Analyst", all
  report sections.
- **Custom** — ask, in one the host user-question tool call: the two role names as the team calls them. **The definitions are not customised here** — they are the workflow's shared vocabulary;
  point at `references/definitions.rst` if asked, and say a change belongs in that file.

Then confirm before writing (the host user-question tool, skipped only with `--yes`): the target path and
the file list — `config.json`, `templates/scope.md`, `templates/review.md`, `templates/lifts.md`, `reviews/`.

```bash
bash "$S/sqlreview.sh" init                # copies the bundled default; never touches existing files
```

Custom answers: after `init`, show the two role names and confirm them with the host user-question tool
(skipped only with `--yes`). Then run the helper with those answers as shell-quoted arguments:

```bash
bash "$S/sqlreview.sh" roles "<confirmed engineer role>" "<confirmed analyst role>"
```

The helper atomically updates only the two role names. It preserves `schemaVersion`, `definitions`
and all other settings. Stop on failure; do not patch or overwrite `config.json` directly.

## 2. Already initialised (re-run — #126 §2)

Never clobber. For each file `init --diff` reports as `differs`, show the diff and ask
(the host user-question tool): **Keep mine** / **Replace with the bundled default**. Apply only the replaced
ones:

```bash
bash "$S/sqlreview.sh" init --apply templates/review.md     # only the files the human chose
```

A `new` file (added by a newer plugin version) is applied after a single confirmation. `same`
files need nothing. Report what changed and what was kept.

### Migrating from SQL Review or SQL Code

Before removing the old plugin, inspect both project templates for `/sql-review:` or `/sql-code:`
invocations. For unchanged defaults, confirm and apply each replacement with
`init --apply templates/scope.md templates/review.md`. For customised templates,
show a targeted diff changing only `/sql-review:` or `/sql-code:` to `/data-request:` and apply the
confirmed edits, preserving custom sections and placeholders. `--check` reports
these pending changes without writing. Keeping an old invocation leaves migration
incomplete; report that explicitly.

For each existing `reviews/<slug>/scope.md` or `review.md` containing an old
invocation, rerender from its corresponding JSON after updating the template:

```bash
bash "$S/sqlreview.sh" render "<slug>" scope    # or review, for each affected report
```

Inspect any report customisations before rerendering and preserve them with the
user's chosen template edits. Verify no `/sql-review:` or `/sql-code:` invocations remain in the
active templates and reports. Do not rewrite JSON, snapshots or history; report
missing source JSON or any retained old invocations as incomplete migration.

## 3. Verify and hand over

```bash
bash "$S/sqlreview.sh" status          # exit 0 now; lists reviews (none yet on a fresh project)
```

For any `invalid` review, run `status --verbose` to name the reason. A legacy review whose slug is
not derived from any current path (a schema-1 hand-chosen slug) reports a binding mismatch; after
confirming the SQL it now describes, rebind it with `sqlreview.sh move --slug <old slug> <sql path>`.
`status --verbose` also prints `migrate=sqlreview.sh move '<path>' '<path>'` for a review under a
legacy-encoded slug (`sql__cohort%5Fpipeline__x`). It keeps working as is; the command renames it to
the readable slug (`sql__cohort_pipeline__x`) without marking it stale, then re-render its reports.

Tell the user the next stage: `$data-request:bootstrap <intended sql path>` before the SQL is
written, or `$data-request:analyse <sql path>` for SQL that already exists. Suggest committing
`.sqlreview/` — the reviews inside it are the handoff record.

SQL paths are supplied explicitly to bootstrap/analyse. To customise report sections, edit the
project templates; SQL glob filtering and section flags are not configuration options.
