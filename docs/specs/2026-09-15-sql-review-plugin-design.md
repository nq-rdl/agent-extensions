# SQL Review plugin — implementation plan

> Historical review/schema design. The plugin is now `data-request`; see the
> [Data Request extension and migration](2026-09-15-data-request-plugin-design.md) for current
> invocation names, canonical paths, hook packaging and development actions.

Epic #131; sub-issues #126 (setup), #127 (bootstrap), #130 (analyse), #128 (explain).
Target branch for the PR: `release/0.30.0`. Revised after a Codex adversarial review (§10).

## 1. What ships

One subject plugin, `sql-review` (CONTRIBUTING rule 4: a no-tool subject is named for the
workflow), with four stage facets. Ordering lives in skill content (each stage points to the next),
never in the namespace.

| Canonical skill               | Leaf        | Invocation            | Actor          | Issue |
|-------------------------------|-------------|-----------------------|----------------|-------|
| `skills/sql-review-setup/`    | `setup`     | `/sql-review:setup`   | anyone, once   | #126  |
| `skills/sql-review-bootstrap/`| `bootstrap` | `/sql-review:bootstrap` | Data Engineer | #127  |
| `skills/sql-review-analyse/`  | `analyse`   | `/sql-review:analyse` | Data Engineer  | #130  |
| `skills/sql-review-explain/`  | `explain`   | `/sql-review:explain` | Data Analyst   | #128  |

Registry: `registry/bundles/sql-review.yaml` with `{source, leaf}` members, two hooks, no agents,
no MCP. `sql-review` is appended to `order:` in `registry/marketplace.yaml`. Manifests, the plugin
tree and `docs/bundles.md` are generated (sync + generate scripts); nothing under `plugins/` is
hand-written except `plugins/sql-review/hooks/hooks.json` and the hook-script copies (the existing
`redhat` precedent, pinned by a byte-identical test).

Language: bash 3.2-compatible shell + `jq` (with a `python3` fallback for JSON in the hooks, as the
redhat hooks do). The Language Policy table names Go for "new first-party CLI helper"; this change
**amends that table** with an explicit row for skill helper scripts (small, portable shell + `jq`
under `skills/<name>/scripts/`, the class the shipped `rh-*.sh` scripts already belong to) so the
policy and the catalog agree. Rationale: a Go helper would need cross-compiled binaries committed
per platform, a CI build/drift step, and a platform-dispatch wrapper — none of which exists today.

## 2. The `.sqlreview/` contract (v1)

`/sql-review:setup` creates this; the other three consume it. The layout is the contract in #126.
**The root is fixed**: `.sqlreview/` at the project root. Every consumer resolves it the same way
(`sqlreview-lib.sh: sr_root`): `$SQLREVIEW_ROOT` if set, else walk up from the cwd to the first
directory containing `.sqlreview/`, else the git top-level. Hooks resolve from the event's `cwd`.
Nothing about the location is customisable.

```
.sqlreview/
  config.json                 # schemaVersion: 1 — settings + the shared definitions
  templates/
    scope.md                  # bootstrap output layout ({{placeholders}})
    review.md                 # analyse output layout
  reviews/<slug>/
    scope.json  scope.md      # bootstrap: authoritative JSON + rendered doc
    review.json review.md     # analyse:   authoritative JSON + rendered doc
    history/<revision>.sql    # immutable SQL bytes for resumed explanations
    scope.source.sql          # bootstrap SQL baseline
    source.sql                # analyse:   exact bytes of the SQL as last reviewed (diff baseline)
    review.draft.json         # analyse work-in-progress before human confirmation (guard-exempt)
    explain.json              # explain: state marker only (last walked-through fingerprint)
```

- **Slug = project-relative path identity**: encoded stem components joined with `__`, `.sql` extension dropped
  (`reports/monthly.sql` → `reports__monthly`, `audits/monthly.sql` → `audits__monthly`). Every
  JSON also records `sql_path`; `sqlreview.sh slug` refuses a directory whose stored `sql_path`
  differs from the one requested. A renamed SQL file is a new slug; `status` lists the old one as
  `missing` and the skill offers `sqlreview.sh move OLD NEW` (renames the directory, rewrites
  `sql_path`, marks the review stale so it is reassessed). Bootstrap takes the *intended* path and
  produces the same slug analyse will later use.
- **JSON is authoritative; markdown is rendered.** `scope.md` / `review.md` are produced by
  `sqlreview.sh render` from the JSON plus the template. This is what makes the reports
  "standardised" (#131) and gives `explain` a machine-readable cross-reference (#128 names "the
  JSON").
- **Baseline is a snapshot, not a commit.** `source.sql` holds the exact reviewed bytes; `delta`
  diffs those bytes against the current file, so dirty, untracked, reverted and rebased histories
  all behave identically. `git_commit` / `git_dirty` are recorded as provenance only. A review
  directory without `source.sql` has no baseline: a full analyse rebuild retains the previous revision history, increments the revision and reconfirms all items.
- **Revisions**: `review.json.revision` (int) increments on every update; `changes[]` records
  `{revision, at, by, summary}`. `scope.json` carries its own `revision`.
- **Shared definitions live once**: authored in `skills/sql-review-setup/assets/sqlreview/config.json`
  (the default template) and `skills/sql-review-setup/references/definitions.rst` (prose), copied into
  the project's `config.json` by setup. Bootstrap/analyse/explain read `definitions` from the project
  config and never restate them.
  - `assumption` — "Decision points made by the RDL" (from the epic).
  - `limitation` — **TBD in the epic.** Draft used here until ratified: "A constraint on what the
    output can be relied on for that arises from the data, the source system, or the request — not
    from an RDL decision. Recorded so the analyst knows where the result must not be over-read."
- Item shape (assumptions and limitations alike):
  `{id: "A1", text, rationale, location: {lines: [a,b]} | null, status: "confirmed", confirmed_by, confirmed_at, confirmed_revision}`.
  Only `confirmed` items may reach the final JSON; rejected candidates stay in the draft.
  `confirmed_revision` is the review revision at which the human last confirmed the item. On an
  update, changed items are re-put to the human and get the new revision; an unchanged item may be
  carried (§12), keeping its earlier `confirmed_revision` and recording `carried_from_revision`.
  Any other `confirmed_revision < revision` is a stale confirmation and `check` rejects it.

Note on #126's wording "reference template in the skill's `references/`": `asctl repo-check` allows
only `.rst` under `references/`, so the template files live under `assets/` and the prose that
explains them under `references/`. Same outcome, spec-compliant layout.

## 3. Hooks (`hooks/sql-review-*.sh`, wired in `plugins/sql-review/hooks/hooks.json`)

Both are exec-form `command` hooks following the redhat pattern: JSON via `jq` with a `python3`
fallback, malformed stdin is a no-op, advisory paths never fail the session.

**`sql-review-preflight.sh` — `SessionStart`.** One declarative context line from
`sqlreview.sh status --json` resolved from the event `cwd`: initialised or not (→
`/sql-review:setup`), config schema version, review count, and which reviews are `stale` (current
SQL bytes differ from `source.sql`) or `missing`. Injection-safe phrasing (factual, not imperative).
Silent no-op when there is nothing to say.

**`sql-review-guard.sh` — `PreToolUse`, matcher `Write|Edit`.** This is the "hook/trigger on
assumptions and limitations" required by #130 §1.1. **What it is:** an invariant check that no
review or scope document can be written unless every assumption and limitation carries an explicit,
complete confirmation record for the current revision — it turns "forgot to ask the human" from a
silent slip into a denied tool call with the offending ids named. **What it is not:** proof that a
human answered; a model could fabricate `confirmed_by` (the skills forbid it, and the record makes
such fabrication auditable in the diff). Bash heredocs into `.sqlreview/` are also out of reach.
It fires only for paths under `.sqlreview/`:

| Path                                        | Tool       | Decision | Why |
|---------------------------------------------|------------|----------|-----|
| `reviews/*/review.json`, `reviews/*/scope.json` | Write   | run `sqlreview.sh check` on the content → `allow`, else `deny` naming the violations and the AskUserQuestion step | forces confirmation to be a deliberate, recorded act |
| same files                                  | Edit       | `deny`   | an Edit shows only a fragment; the check needs the whole document |
| `reviews/*/*.draft.json`, `reviews/*/explain.json`, `reviews/*/source.sql` | any | pass | work-in-progress, state marker, snapshot |
| `reviews/*/scope.md`, `reviews/*/review.md` | Write/Edit | `deny`   | rendered artefacts — edit the JSON and re-render |
| `config.json`                               | Write/Edit | `ask`    | config changes go through the setup update path with human confirmation |
| `templates/*`                               | any        | pass     | user-customisable |

The validation logic lives in one place, `sqlreview.sh check`, resolved by the guard via
`${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/`, then relative to the hook's own plugin copy, then the
canonical `skills/sql-review-setup/scripts/` (for in-repo tests). If the checker cannot be found the
guard **denies** with an install-broken message: a missing guardrail must not silently pass.

## 4. Shared helper: `skills/sql-review-setup/scripts/sqlreview.sh` (+ `sqlreview-lib.sh`)

One entry point with subcommands, so every skill does `S="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts"`
and calls `bash "$S/sqlreview.sh" <cmd>` (the redhat-setup → fetch-docs precedent for sharing
scripts across a plugin's skills).

| Subcommand | Does | Exit |
|---|---|---|
| `init [--diff] [--apply PATH...]` | Create `.sqlreview/` from the bundled default at the resolved root (cwd's git top-level when nothing exists yet). Never overwrites: `--diff` reports each template file as `new` / `same` / `differs` (with a unified diff); `--apply` replaces only the named files after the human confirmed. | 0 ok · 10 differences · 2 error |
| `status [--json]` | Lists reviews with `slug, sql_path, revision, state ∈ {current, stale, missing, no-baseline, scoped, draft, invalid}`. Exit 3 when not initialised — **setup is the one caller that treats 3 as "proceed to init"**; every other skill stops and points at `/sql-review:setup`. Bundled templates the project lacks are reported as `missing_templates` plus `missing_templates_fix` (`--json`) or one stderr line (text rows unchanged). | 0 · 3 |
| `slug PATH` | Prints the slug for a project-relative path; exit 5 if `reviews/<slug>/` exists bound to a different `sql_path`. | 0 · 5 |
| `check FILE [--stdin]` | Validates a scope/review JSON: required keys, item shape, every item `confirmed` with `confirmed_by`/`confirmed_at` and `confirmed_revision == revision`, or a carried item's fields (§12). One line per violation. | 0 valid · 4 invalid |
| `carryforward SLUG scope\|review DRAFT` | Read-only JSON: which draft items may carry the previous published revision's confirmation (with the exact fields to set) and which must be walked, and why (§12). | 0 · 2 · 4 |
| `fingerprint SQL` | `{sql_path, sql_sha256, git_commit, git_dirty}` for the skill to embed. | 0 · 2 |
| `snapshot SLUG SQL` | Copies the current SQL bytes to `reviews/<slug>/source.sql` (called by analyse after the guarded final JSON Write succeeds, verifying its SHA256 and preserving history/<revision>.sql). | 0 · 2 |
| `delta SLUG` | Unified diff of `source.sql` vs the current file; header lines report both sha256s. | 0 unchanged · 10 changed · 6 no baseline · 2 |
| `impact SLUG` | **Hints only.** Identifiers introduced/altered inside the diff hunks (CTE names, aliases, columns) and the non-diff lines referencing them. Printed under a "heuristic — does not prove anything unaffected" banner. | 0 · 6 · 2 |
| `move OLD NEW` | Rename a review directory when the SQL moved; rewrites `sql_path`, invalidates the baseline state to `stale`. | 0 · 2 |
| `render SLUG scope\|review\|lifts` | JSON + `templates/<kind>.md` → `<kind>.md`. A missing template is first installed from the bundled default (never overwriting, symlinks refused, one stderr line). Fixed placeholder set; unknown placeholders are left in place and reported. Deterministic. | 0 · 2 |

Portability: no associative arrays, no `mapfile`, `shasum -a 256` / `sha256sum` probe — the same
rules `rh-lib.sh` follows.

## 5. Skill behaviour (SKILL.md content — concise, the non-inferable delta only)

Frontmatter on all four: `user-invocable: true`, `argument-hint`, `allowed-tools: Bash, Read, Glob,
Grep, Write, AskUserQuestion`, `compatibility` pinned to `.sqlreview` schema `1` and `jq >= 1.6`,
`metadata.repo`. Bootstrap/analyse/explain open with `sqlreview.sh status` and stop on exit 3 with a
pointer to `/sql-review:setup`. **Cancellation rule (all skills):** if the human stops or a question
cannot be asked, leave the draft on disk and write nothing final; say so.

**setup** (`[--default|--custom] [--check] [--yes]`) — exempt from the init gate.
1. `init --diff` → nothing exists / exists with per-file delta.
2. Not initialised: AskUserQuestion once — **Default (Recommended)** / **Custom** (unless a flag
   was given). Custom asks only about things that do not move files: team names for the two roles
   (report sections are edited in the project templates); then shows the resulting `config.json`
   for confirmation.
3. Confirm the target location and the file list before writing (AskUserQuestion; `--yes` skips
   only this confirmation and exists for scripted/e2e runs).
4. Already initialised: show the delta per file; for each file that differs ask keep / replace;
   never clobber (§2.1 of #126). `--check` stops after step 1.
5. Point at the next stage: `/sql-review:bootstrap`.

**bootstrap** (`<intended sql path> [--update]`)
1. Existing `scope.json` → update path: if the SQL now exists, show it against the scope's intent /
   inputs / outputs; `git log -p` on `scope.json` when tracked shows how the scope itself moved.
   Re-put every assumption `carryforward` does not carry (§12) to the human (confirm / reword /
   drop) and ask for new ones.
2. Else interview: intent, inputs, outputs, candidate assumptions (using the config's definition —
   decision points the RDL is taking), open questions. Pause for confirmation on each scoping
   decision; confirm each assumption individually via AskUserQuestion.
3. Write `scope.json` (guard validates), `render`, show the doc, point at `/sql-review:analyse`.

**analyse** (`<sql path> [--update]`)
1. `slug`, `fingerprint`; find the scope by slug (offer to run bootstrap retroactively if none).
2. Existing `review.json` with a baseline → update path: `delta` → walk the human through each
   hunk → `impact` hints → then **reassess every existing assumption and limitation** `carryforward`
   does not carry (§12) (confirm / reword / drop, hints flag the likely-affected ones first) and add
   new ones → `revision + 1`,
   `changes[]` entry. No baseline → full analyse.
3. Else full read of the SQL against the scope: purpose, inputs (sources/tables), outputs
   (grain, columns), logic walkthrough (numbered steps with line ranges), candidate assumptions,
   candidate limitations, open questions → `review.draft.json`.
4. Human-in-the-loop trigger: each candidate assumption and limitation is put to the human via
   AskUserQuestion (confirm / reword / reject). Only confirmed items are written to `review.json`,
   `confirmed_by` = the user, `confirmed_revision` = the new revision; the guard enforces the
   record. The skill never fills these fields from anything but an answered question.
5. Write `review.json`, `snapshot` (verify SHA256 and retain revision history), `render`, delete the draft; point at `/sql-review:explain`.

**explain** (`<sql path | slug>`) — interactive, no report artefact.
1. Load `review.json`, `review.md`, `scope.*`, the SQL. **Always** compare the review baseline
   (`source.sql`) with the current SQL first. Stale → AskUserQuestion: run `/sql-review:analyse
   --update` first (Recommended) or explain the stored snapshot, clearly labelled as such.
2. If `explain.json` exists and either its `sql_sha256` or its `review_revision` differs from now,
   walk the delta first (`delta`, `impact` hints, then the revised items), then continue.
3. Walkthrough in review order: purpose → inputs → each logic step with its lines → the
   assumptions and limitations that apply to that step (cross-referenced by id) → outputs → open
   questions. At each step AskUserQuestion: **Continue** / **I have a question** / **Stop here**.
4. Write `explain.json` `{sql_sha256, review_revision, at, by, completed: bool}` only for material
   actually walked through (a stop writes `completed: false` with the last step). State marker,
   not a report — flagged because #128 says "no new artifact generated".

## 6. Tests (TDD — written first, red, then made green)

- `tests/test_sql_review_scripts.py` — every subcommand against temp fixtures: init creates the
  tree and is idempotent; `--diff` reports new/same/differs and `--apply` replaces only what was
  named; `slug` gives distinct slugs for `reports/monthly.sql` vs `audits/monthly.sql` and exit 5
  on a conflicting binding; `check` accepts a confirmed document and rejects each missing key,
  unconfirmed item, and stale `confirmed_revision` with the id in the message; `fingerprint` matches
  `sha256sum`; `snapshot` + `delta` exit 0 unchanged, 10 after a change **including** dirty,
  untracked, reverted-to-HEAD and no-git cases, 6 with no baseline; `impact` lists a downstream
  reference of a renamed CTE, nothing for an untouched one, and carries the heuristic banner;
  `move` rebinds and marks stale; `render` is byte-stable from a golden JSON and reports unknown
  placeholders; root resolution from a nested cwd.
- `tests/test_sql_review_hooks.py` — the guard's decision table (allow / deny with ids / ask /
  pass-through / draft-exempt / Edit-denied / md-denied / config-ask / stale-revision-denied /
  missing-checker-denies / malformed-stdin no-op / jq-less python3 fallback / nested cwd), the
  preflight's context line (not initialised → setup hint; initialised → counts, stale and missing
  slugs; nothing to say → no-op), and a byte-identical check between `hooks/` and
  `plugins/sql-review/scripts/`.
- `tests/test_sql_review_plugin.py` — bundle has the four leaves and both hooks; each SKILL.md is
  `user-invocable`, lists `AskUserQuestion`; the three consumer skills name `/sql-review:setup`;
  setup's SKILL.md does not gate on status exit 3; default template files present under
  `assets/`; `hooks.json` scripts exist; the language-policy row is present in both AGENTS.md and
  ARCHITECTURE.md.
- Existing gates unchanged: `check_bundle_refs`, `check_exposure`, `check_grouping`,
  `generate_manifests --check`, `generate_bundles_doc --check`, `check_consistency`,
  `validate-plugins.sh`, `sync-plugins.sh --check`, `asctl repo-check` (via `pixi exec --spec go`
  on this host).
- `tests/e2e/sql-review-smoke.sh` — static: bundle/plugin/marketplace end-state. `--live` (in the
  sandbox container): `claude plugin validate`, marketplace add, `install sql-review@…`, plugin
  list; then in a scratch project drive `init/slug/fingerprint/snapshot/check/render/delta` and
  pipe hook events through the **installed** copies. **First-run acceptance** (required, not
  optional): with credentials mounted, `claude -p '/sql-review:setup --default --yes'` in an empty
  git repo must leave `.sqlreview/config.json` behind; the run is reported as skipped-red if
  credentials are unavailable, never as green.

## 7. Container verification

The `devcontainer` CLI is not installed on this host; Docker is. Build `.devcontainer/Dockerfile`
directly, run it with the worktree bind-mounted at `/workspace` and a throwaway `~/.claude` seeded
with the host's OAuth credentials, and execute: `pixi install`, the unit tests,
`tests/e2e/sql-review-smoke.sh --live`. Findings feed back into the skills before the PR.

## 8. Delivery

1. Plan → `/codex:adversarial-review --wait` → fold in the findings (done, §10).
2. Registry + skeleton (bundle YAML, marketplace order, four skill dirs, hooks.json, policy row).
3. Tests (red) → `sqlreview.sh`, lib, hooks (green) → SKILL.md content → templates + definitions.
4. `sync-plugins.sh sql-review`, `generate_manifests.py`, `generate_bundles_doc.py`, full validation.
5. Changie fragments (one idea each, ≤200 chars).
6. Container run (§7). Commit, push, PR against `release/0.30.0` closing #126 #127 #128 #130 and
   referencing #131.

## 9. Decisions to ratify (not blocking)

- **Limitation definition** — draft in §2; the epic marks it TBD.
- **`config.json` rather than YAML** — hooks and helpers are `jq`-only.
- **Markdown is rendered, not hand-written** — standardisation over free-form prose.
- **`explain.json` state marker** — the only way to resume from a previous explanation (#128 §2).
- **Language-policy amendment** — a documented row for shell skill helpers instead of a Go CLI.
- **Template under `assets/`** — `references/` is `.rst`-only by the directory-structure standard.

## 10. Adversarial review findings and how the plan changed

| Finding (Codex) | Resolution |
|---|---|
| Basename slugs collide | Slug is the project-relative path (`dir__name`); `sql_path` binding checked by `slug`; `move` for renames; collision test. |
| Fingerprint cannot reconstruct reviewed SQL | `source.sql` snapshot is the baseline; `delta` diffs bytes, git is provenance only; no baseline → full analyse; dirty/untracked/reverted tests. |
| Identifier heuristic insufficient | `impact` demoted to hints with a banner; update paths reassess **every** item; `confirmed_revision` makes a stale confirmation machine-detectable. |
| Guard validates self-asserted confirmation | Scoped honestly as an invariant check; skills forbid filling confirmation fields from anything but an answered question; cancellation leaves the draft. |
| Explain can present an obsolete review | Explain always compares baseline vs current SQL first; `explain.json` tracks both SQL sha and review revision; completion recorded only for material walked through. |
| Init gate blocks first-run setup | Setup exempt; exit 3 semantics defined; first-run acceptance test required in the container. |
| Custom output dir escapes discovery/guard | Removed; root is fixed and resolved by one shared function; nested-cwd tests. |
| Bash CLI conflicts with Language Policy | Explicit policy amendment (AGENTS.md + ARCHITECTURE.md) shipped in the same change; flagged for the reviewer. |


## 11. PR #297 review corrections

- Slugs encode each path stem component, including underscores, percent signs and dots, before
  joining with `__`. SQL paths end in `.sql`; empty stems encode as `%00`. This distinguishes
  `a/b.sql`, `a__b.sql`, whitespace/punctuation variants and dot-only filenames. Relative command
  paths resolve from the project root. Helpers reject unsafe slugs, traversal and symlink paths.
- The final guarded review Write precedes snapshot. Snapshot checks its bytes against the final
  SHA256, retains `history/<revision>.sql`, then replaces `source.sql`. Status/delta also compare
  the baseline hash with final JSON, so an interrupted update cannot appear current.
- Explain compares retained revision snapshots when resuming; missing history requires an explicit
  full walkthrough. Missing current SQL stops explanation. Missing baseline requires analyse.
- Move marks a review stale even when bytes are unchanged and removes obsolete rendered reports.
  Failed file mutations return errors. Draft-only directories are reported as resumable drafts.
- Bootstrap inspects staged and unstaged scope diffs, keeps its own `scope.source.sql` baseline,
  and reconfirms limitations alongside assumptions.
- Validation checks one JSON object, normalized binding, integer revisions, collection/item shapes,
  rationale and line ranges. Markdown table cells escape pipes and line breaks. Guard denial
  messages name the correct authoritative/draft file; absence of both parsers denies writes.
- Custom setup supports roles and editable templates. Unimplemented `sql_globs` and `sections`
  settings were removed before release; no filtering or section-flag behavior is promised.
- SkillSpector notes 519–522 provide only generic category labels, without exploit details.
  Setup already requires confirmation (or explicit `--yes`), draft cleanup follows successful
  finalization, and temporary validation input is local. These are reviewed as informational;
  path containment and persistence checks above cover the concrete tool-parameter concerns.


## 12. Carrying unchanged confirmations across revisions (#348)

A revision bump no longer invalidates every confirmation. The lift ledger already keeps an entry's
revision when its confirmed content is unchanged; scope and review items now do the same.

- **Fields.** A fresh item has `confirmed_revision == revision` and no (or null)
  `carried_from_revision`. A carried item keeps the `confirmed_by`, `confirmed_at` and
  `confirmed_revision` of the revision where a human confirmed it, and records
  `carried_from_revision` = the previous published revision. Chains keep the original confirmation.
- **`check` (stateless).** `confirmed_revision` is an integer in 1..revision; equal to revision
  → no `carried_from_revision`; lower → `carried_from_revision == revision - 1` and
  `>= confirmed_revision`. The guard denies a direct Write carrying items: only publish can prove them.
- **`publish` (stateful).** Each carried item needs, in the previous published document of the same
  kind, an item with the same id in the same list and identical `text`, `rationale`,
  `confirmed_by`, `confirmed_at` and `confirmed_revision`, and unchanged governed SQL. The baseline
  is `source.sql` (review; written by `snapshot` after each publish) or `scope.source.sql` (scope;
  copied by bootstrap after each publish). It is evidence only when its SHA256 equals the previous
  document's `sql_sha256` (when one was recorded), as for `carryover`. With a `location`, the previous
  lines in the baseline must equal the new lines in the current SQL (remaps allowed, same length).
  With `location: null`, the whole SQL must be unchanged (SHA equality) or absent at both revisions.
  `publish --reconfirm-all` refuses every carried item.
- **`carryforward`** prints the same verdict for a draft, from the same jq definition
  (`sqlreview-carry.jq`) publish enforces, so the two cannot drift. Bootstrap and analyse walk only
  what it lists under `walk`, plus any carryable item the diff implicates indirectly.
- **Render** marks a carried item's revision cell `N (carried)`; `N` is where it was confirmed.
