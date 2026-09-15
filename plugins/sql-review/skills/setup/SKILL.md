---
license: CC-BY-4.0
description: >-
  Initialise a project for the SQL Review workflow: create the .sqlreview/ directory with
  config.json (settings + the shared assumption/limitation definitions) and the scope/review
  report templates, from the bundled default or from answers to a few questions. Safe to re-run —
  an existing setup is diffed file by file and nothing is overwritten without confirmation. Use
  once per project before /sql-review:bootstrap, :analyse or :explain, or whenever one of them
  reports "not initialised".
argument-hint: '[--default|--custom] [--check] [--yes]'
user-invocable: true
compatibility: >-
  .sqlreview schema 1 (docs/specs/2026-09-15-sql-review-plugin-design.md); bash 3.2+, jq >= 1.6,
  git optional. macOS and Linux.
allowed-tools: Bash, Read, Glob, Grep, Write, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# SQL Review — setup

Creates the `.sqlreview/` contract every other stage consumes. **This is the one stage that does
not require an initialised project**: `sqlreview.sh status` exiting 3 means "proceed to init".
Arguments: `$ARGUMENTS`.

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts"
bash "$S/sqlreview.sh" init --diff        # exit 0: all files match the bundled default
                                          # exit 10: lists new / same / differs per file (with a diff)
```

The root is the git top-level (or the cwd outside git); it is not configurable — hooks, helpers
and the other stages all resolve the same `.sqlreview/` by walking up from the cwd.

## 1. Fresh project (every file reported `new`)

`--check`: report and stop. Otherwise, unless `--default`/`--custom` was given, ask **once**
(AskUserQuestion), options in this order:

- **Default (Recommended)** — the bundled template as-is: the shared definitions
  (`references/definitions.rst`), roles "Data Engineer (RDL)" / "Data Analyst", all
  report sections.
- **Custom** — ask, in one AskUserQuestion call: the two role names as the team calls them. **The definitions are not customised here** — they are the workflow's shared vocabulary;
  point at `references/definitions.rst` if asked, and say a change belongs in that file.

Then confirm before writing (AskUserQuestion, skipped only with `--yes`): the target path and
the file list — `config.json`, `templates/scope.md`, `templates/review.md`, `reviews/`.

```bash
bash "$S/sqlreview.sh" init                # copies the bundled default; never touches existing files
```

Custom answers: after `init`, Write `.sqlreview/config.json` with the edited `roles` (keep `schemaVersion` and `definitions` untouched). The guard asks for permission
on that Write — that prompt *is* the confirmation for this path.

## 2. Already initialised (re-run — #126 §2)

Never clobber. For each file `init --diff` reports as `differs`, show the diff and ask
(AskUserQuestion): **Keep mine** / **Replace with the bundled default**. Apply only the replaced
ones:

```bash
bash "$S/sqlreview.sh" init --apply templates/review.md     # only the files the human chose
```

A `new` file (added by a newer plugin version) is applied after a single confirmation. `same`
files need nothing. Report what changed and what was kept.

## 3. Verify and hand over

```bash
bash "$S/sqlreview.sh" status          # exit 0 now; lists reviews (none yet on a fresh project)
```

Tell the user the next stage: `/sql-review:bootstrap <intended sql path>` before the SQL is
written, or `/sql-review:analyse <sql path>` for SQL that already exists. Suggest committing
`.sqlreview/` — the reviews inside it are the handoff record.

SQL paths are supplied explicitly to bootstrap/analyse. To customise report sections, edit the
project templates; SQL glob filtering and section flags are not configuration options.
