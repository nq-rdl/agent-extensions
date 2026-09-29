# Skill review: plugins added after epic #312 was written

This record applies the epic #312 criteria to the plugins added after the epic
was written on 2026-09-15: `data-request`, `pandera`, `testcontainers`,
`tech-writing` and `lucid`. The `prompting`, `git`, `gh` and `rdl-team` plugins
are reviewed elsewhere. Hooks (`data-request-preflight`, `data-request-guard`,
`stylepedia-reminder`) are owned by another review; this record only reports
hook findings.

The tasks, invariants and planned changes below were recorded **before** any
skill edit, at source revision `4817a19` (`epic/skill-review`).

## Scope

| Plugin | Skills (canonical → leaf) | Other components |
|---|---|---|
| data-request | 13: `data-request-{setup,bootstrap,analyse,explain,release,guardrails,map,draft,validate,fix,amend,lift,triage}` → same leaf without the prefix | hooks `data-request-preflight`, `data-request-guard` |
| pandera | `pandera-validate` → `validate` | – |
| testcontainers | `testcontainers` → `integration-test` | – |
| tech-writing | `tech-writing-copyedit` → `copyedit`, `se-technical-writer` → `author` | hook `stylepedia-reminder` (Claude Stop/SubagentStop agent review) |
| lucid | none | hosted MCP server `https://mcp.lucid.app/mcp` |

## Planned changes and invariants (pre-edit)

### data-request: triage co-development routing (#306)

The triage co-development table routes agreed tasks to eight stages. It has no
row for `/data-request:amend` (a change to a released extract) or
`/data-request:release` (the researcher-facing release body), although both
stages exist and a service-desk queue carries both kinds of request.

| ID | Invariant | Where |
|---|---|---|
| DR-1 | Triage-only mode stays read-only in every repository | triage SKILL.md |
| DR-2 | Triage routes to stages and does not restate their procedures | triage SKILL.md |
| DR-3 | Triage SKILL.md stays at 140 lines or fewer | triage SKILL.md |
| DR-4 | "Never infer permission" list is unchanged | triage SKILL.md |
| DR-5 | #413 (clinician and resource names are not personal information) and #419 (handles, never email addresses) wording is unchanged | guardrails, map, lifts.rst, amend, analyse, explain, release, lift |
| DR-6 | Co-development routes a released-extract change to amend, a release body to release and an export defect to fix | triage SKILL.md |

Test first: extend `tests/test_data_request_triage.py` (stages `amend` and
`release`) and add the eval case `triage-codev-routes-stages` with grader
fixtures in `tests/test_eval_data_request_graders.py`. Run the case on the
original skill (baseline), then on the revised skill, and re-run
`triage-only-read-only` on the revised skill for DR-1.

#### Added after the first revised run (pre-edit for the descriptions)

The first revised run (table rows "Targeted defects, and logic changes before
the first release → fix" and "Changes to a released extract → amend") routed
the released `Encounter_id` defect to amend in one of three runs. That run
read only guardrails; its reply quoted the **fix description**, "A change to a
released extract goes to amend", as the reason. The first `claude plugin eval`
baseline (natural-language prompt, triage not loaded, original skills) failed
the same grader in one of three runs. The amend body already says that output
contradicting what was agreed is a defect for fix, and the fix body sends only
a change request on a released extract to amend. The descriptions and the new
table rows do not carry that distinction.

| ID | Invariant | Where |
|---|---|---|
| DR-7 | fix and amend descriptions separate a defect (output that contradicts what was agreed, released or not → fix) from different output requested for a released extract (→ amend); before the first release a logic change still goes to fix | fix, amend frontmatter; triage table |
| DR-8 | fix and amend bodies are unchanged; the existing `amend-*` and `prerelease-*` cases still pass | fix, amend SKILL.md |

### tech-writing (#306, #298-style factual fix)

| ID | Invariant | Where |
|---|---|---|
| TW-1 | `author` description is grammatical, names its content types and points copyedits of existing prose to `tech-writing:copyedit` | se-technical-writer SKILL.md |
| TW-2 | The simplified STE review stays mandatory on every host; the completion-hook claim is limited to Claude Code, where the agent Stop hook runs (Codex runs only the reminder, `docs/codex.md`) | tech-writing-copyedit SKILL.md |
| TW-3 | Explicit invocation of either skill still works; the author skill still applies copyedit | both |

Behavioural check: `claude -p` with `--plugin-dir` on temporary copies of the
original and revised `plugins/tech-writing/`, hooks disabled, prompts: new
tutorial (expect `author`), copyedit a pasted paragraph (expect `copyedit`),
unrelated Python bug (expect neither).

### pandera (#308)

| ID | Invariant | Where |
|---|---|---|
| PA-1 | Every behavioural claim in the body holds on the baseline release and on the latest release | pandera-validate SKILL.md |
| PA-2 | `compatibility:` distinguishes the API baseline from the verification date | frontmatter |

## Results

### Harness

- Host: Claude Code 2.1.284, model under test `claude-sonnet-5`, judge
  `claude-haiku-4-5`, 2026-09-29.
- `claude -p` runs: `--plugin-dir` on temporary copies of `plugins/data-request/`
  (original = `593351e`, revised = working tree after the change), scratch cwd,
  `--permission-mode dontAsk`, `--allowedTools "Skill Read Glob Grep"`,
  `--settings '{"disableAllHooks": true}'`, `--max-turns 8`.
- `claude plugin eval` runs: `scripts/eval-claude-plugin.sh data-request --case <c>
  --ablation none`, original via `EVAL_REV=593351e`.

### data-request routing (DR-6, DR-7)

Prompt: `evals/claude/data-request/triage-codev-routes-stages/prompt.md`. Answers
are `rename_stage, identifier_stage, release_body_stage`; the expected answer is
`amend, fix, release`.

| Variant | Skills | Runs | Correct | Wrong answers |
|---|---|---|---|---|
| Natural prompt, triage not loaded | original | 4 | 1 | 3 × `identifier_stage: amend` |
| Natural prompt, triage not loaded | revised (DR-7) | 4 | 4 | – |
| `/data-request:triage … --co-develop` | original | 3 | 3 | – (5, 1 and 7 tool calls: it listed and read sibling SKILL.md files) |
| `/data-request:triage … --co-develop` | first table wording only | 3 | 2 | 1 × `identifier_stage: amend` (quoted the fix description) |
| `/data-request:triage … --co-develop` | revised (DR-7) | 6 | 6 | – |
| `claude plugin eval`, natural prompt | original | 3 | 2 | 1 × identifier-to-fix failed |
| `claude plugin eval`, natural prompt | revised | 3 | 3 | – |

The `skill-fired` indicator failed in every `claude plugin eval` run: the model
answered from the skill list without loading triage. It is a with-only
indicator under the default `with-without` ablation.

Regression checks (`claude plugin eval`, revised skills):

- `amend-rename-safe`: 3/3 runs score 1.0.
- `prerelease-change-routes-to-fix`: `workflow-fix`, `no-amd-entry`,
  `runbook-uat-same-change`, `review-stale`, `renamed-column` pass in 9/9
  revised and 9/9 original runs. `analyse-full-rewalk` passes 4/9 revised and
  5/9 original. Most runs answer in one turn without loading fix, so the
  `analyse` value is a guess from the prompt's option list. The difference is
  within run-to-run noise; not a regression claim either way.

Paid spend recorded in the run outputs: about USD 5.4 (claude -p about
USD 3.1; `claude plugin eval` about USD 2.3).

### Verified facts (no edit made)

- **pandera (PA-1):** a probe script (`import pandera.pandas`, `required` vs
  `nullable`, `int64` nulls vs `pd.Int64Dtype()`, schema-level `coerce`,
  `strict="filter"`, Series vs DataFrame null masking and `ignore_na=False`,
  non-lazy coercion raising `SchemaErrors`, Polars `LazyFrame` schema-only
  default, `DataFrameModel` annotation alone vs `@pa.check_types`) gave the
  documented result on pandera 0.33.0 and 0.33.1 (pandas 3.0.6, polars 1.44.2),
  2026-09-29. PyPI latest: 0.33.1 (2026-09-01).
- **testcontainers:** GitHub latest releases on 2026-09-29: java 2.0.5, go
  v0.44.0, dotnet 4.15.0, node **v12.2.0 (2026-09-28, after the skill's
  2026-09-26 check)**, python 4.15.0, rs 0.28.0, rs modules v0.15.0. Node
  12.1.0 and 12.2.0 both declare `engines.node >= 22.22`. Python 4.15.0:
  `testcontainers.postgres` emits `DeprecationWarning` pointing to
  `testcontainers.community.postgres`; `wait_container_is_ready` warns;
  `testcontainers.core.wait_strategies` exists. Maven Central:
  `testcontainers-postgresql` 2.0.5 exists; the old `postgresql` artifact ends
  at 1.21.4.
- **Local references (#300):** `asctl repo-check` passes; every
  `${CLAUDE_PLUGIN_ROOT}/…` path used by data-request exists in the Claude and
  Codex packages; every `/data-request:*`, `/rdl-team:workflow` and
  `/tech-writing:copyedit` route resolves to a registered leaf.

## Per-issue disposition

| Plugin / skill | #303 size | #304/#305 disclosure, duplication | #306 description, routing | #307 outcomes, authorization | #308 versions, guards | #310 delegation | #300/#301 refs, links |
|---|---|---|---|---|---|---|---|
| data-request (13 skills) | Retained: largest body guardrails 277 lines, all ≤300 | Retained with reason: repeated text (released-extract test in fix/amend, runbook+UAT same change, stale-review full re-walk, exempt probes in guardrails/map/lifts.rst, ethnicity convention, handle-not-email beside each record-writing step) sits in independently loaded entry points beside the action it governs; map defers to guardrails as owner; wording is consistent, #413/#419 intact | **Changed** fix/amend descriptions and triage table (DR-6, DR-7). Other siblings retained: analyse/explain/validate/release/draft/map separate by stage and role. Over the 400-char target, retained as justified: setup 515, analyse 477, amend 464, explain 453, release 448, bootstrap 442 | Retained: every workflow ends with a report and done-check; governance, PII and approval gates unchanged | Retained: query-builder 0.6.0 / scaffold 0.5.0 baselines carry "verify at use time" guards; not re-verified against the private repos in this review | Changed: Handoff contract added; no pending exceptions; 21 delegation tests pass | Retained: passes; covered by link-rot scan of `skills/**` |
| pandera-validate | Retained: 80 lines | Retained: no duplication | Retained: 234 chars, single skill | Retained: fixture-based done-check present | Changed (PA-2): compatibility distinguishes 0.33.0 baseline from verification on 0.33.0/0.33.1, dated 2026-09-29 | n/a | Retained |
| testcontainers | Retained: 118 lines | Retained: languages/guides in references | Retained with reason: 666 chars over target, but single-skill plugin with no sibling; product identifiers are routing cues | Retained | Retained: dated check (2026-09-26) is accurate; node moved to v12.2.0 after it (follow-up) | n/a | Retained |
| tech-writing-copyedit | Retained: 176 lines | Retained | Retained: 422 chars | Retained | Changed (TW-2): blocking completion-hook claim now names Claude Code; mandatory direct STE review remains on every host | n/a | Retained |
| se-technical-writer | Retained: 11 lines; 505-line outline is upstream-derived and loaded only for delegation | Retained: outline already reconciled with house style | Changed (TW-1): grammatical new-writing trigger and explicit copyedit route; original/final positive and negative routing pass | Retained | Retained: upstream link present | Changed: Handoff contract added; canonical and both installed copies pass | Retained |
| lucid (MCP only) | n/a | n/a | n/a (no skills) | n/a | Retained: hosted URL, no pinned binary | n/a | n/a |

Hook findings (report only): the tech-writing Stop/SubagentStop agent review
does not run in Codex; the skill text should say so (TW-2). No data-request hook
finding.

## Status at hand-off

Done and committed on `epic312/new-plugins`:

- Pre-edit record (`5477e7d`, `593351e`).
- DR-6/DR-7: fix and amend descriptions, triage co-development table, unit tests
  (`tests/test_data_request_prerelease_change.py::DefectVersusReleasedChange`,
  `tests/test_data_request_triage.py` stages), eval case
  `triage-codev-routes-stages` with fixtures in
  `tests/test_eval_data_request_graders.py`, two changie fragments. The tests
  failed before the edit and pass after it.

Not started (next steps):

1. TW-1: rewrite the `se-technical-writer` description (grammar, content types,
   pointer to `tech-writing:copyedit` for existing prose); routing check with
   `claude -p` on temporary copies of `plugins/tech-writing/`, hooks disabled.
2. TW-2: limit the completion-hook sentence in `tech-writing-copyedit` to Claude
   Code; keep the STE review mandatory everywhere.
3. PA-2: add the 2026-09-29 verification (0.33.0 and 0.33.1) to
   `pandera-validate` `compatibility:`.
4. Optional: note testcontainers-node v12.2.0 in the skill's dated check.
5. Each needs a changie fragment and `sync-plugins.sh <bundle>`.

Scratch harness and raw results (not committed):
`/tmp/claude-1001/-home-rudolfjs-dev-rdl-nq-rdl-agent-extensions/15b2cf65-4e02-4635-9f01-fd1df4014e8d/scratchpad/dr/`
(`run.sh`, `batch.sh`, `evalcases.sh`, `*.jsonl` traces, `natural.md`) and
`…/scratchpad/eval-*` (`result.json` per `claude plugin eval` run),
`…/scratchpad/pandera/probe.py`, `tc_probe.py`.

## Recommended follow-up issues (not filed)

- Trim data-request descriptions over 400 characters (setup, analyse, explain,
  release, bootstrap) with a routing suite, not by line count.
- Add the #310 delegation contract sentence to every `references/subagent.rst`
  in one catalog-wide change with `tests/test_delegation_handoff.py`.
- `prerelease-change-routes-to-fix` rarely loads fix, so `analyse-full-rewalk`
  is a guess; make the case require the skill (or score it only under
  `with-without`).
- The `claude plugin eval` harness does not expand a leading slash command in
  `prompt.md`; explicit-invocation cases need `claude -p` or harness support.

## Follow-up results (2026-09-29)

TW-1 baseline was recorded in [finish.md](finish.md) before editing. The final
description now names new technical writing and directs existing-prose edits
to `tech-writing:copyedit`. Claude Code 2.1.284 / claude-sonnet-5, temporary
original and final plugins, hooks disabled, tools Skill/Read/Glob/Grep:

| Prompt | Original | Final |
|---|---|---|
| Tutorial for Python developers: a context manager that closes files, with a runnable example | author then copyedit | author, then reads copyedit plus house-style and STE references |
| Copyedit “You can utilize the command in order to obtain the data. It is recommended that users should ensure that the config is valid.” | copyedit | copyedit |
| Why does Python raise TypeError for `1 + "2"`? | neither | neither |

These are one run per variant; they show preserved routing for these prompts,
not a measured routing gain. Original = the pre-edit snapshot at a2364aa;
final = the canonical description change in this follow-up.

TW-2: the completion-hook sentence is now scoped to Claude Code. Codex is
explicitly directed to perform the same mandatory STE review before delivery.
No hook registration or STE rule changed. The author routing run read the
copyedit and STE references; the final copyedit body remains mandatory on both
hosts. Native Codex hook execution was not claimed.

PA-2: compatibility now records the 2026-09-29 verification on 0.33.0 and
0.33.1 separately from the 0.33.0 API baseline. This records the existing
executed probes above; it does not claim a new probe or broader version range.
