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

Pending.
