# Claude Code and RDL Team skill review (#305–#310)

This record follows the pilot protocol in epic #312. It covers the
`claude-code` plugin (`cc-agent-create`, `cc-agent-teams`,
`cc-create-workflow`, `cc-hook`, `cc-pipeline`, `skill-audit`,
`skill-review`, `report-skill-issue`, `marketplace-scout`) and the
`rdl-team` plugin (`cc-setup`, `rdl-switch-repo`, `rdl-task-bridge`,
`rdl-workflow`, `new-service-request`, and the guest `discover-plugins`).

The tasks, invariants, prompts, and expected outcomes below were recorded
**before** any skill edit, at source revision `4817a19`.

## Scope after #291

PR #291 removed the named agents and skill preloads. The former
`skill-auditor` and `marketplace-scout` agents are now the
`claude-code:skill-audit` and `claude-code:discover-plugins` skills, each with
an optional `references/subagent.rst` worker outline. Issue text about agent
`tools:` frontmatter and preloads is re-scoped to those outlines.

## Baseline sizes

From `asctl repo-check --size-report` at `4817a19`. Approximate tokens are
body bytes / 4, not measured model usage.

| Skill | Body lines | Approx. body tokens | Reference files |
|---|---|---|---|
| cc-agent-teams | 329 | 2792 | 2 |
| cc-setup | 196 | 2277 | 0 |
| cc-hook | 178 | 2274 | 8 |
| cc-create-workflow | 170 | 1992 | 0 |
| cc-pipeline | 130 | 1600 | 0 |
| rdl-workflow | 123 | 1905 | 0 |
| new-service-request | 83 | 718 | 0 |
| report-skill-issue | 48 | 484 | 2 |
| rdl-task-bridge | 44 | 769 | 0 |
| rdl-switch-repo | 42 | 764 | 0 |
| skill-audit | 28 | 349 | 1 |
| cc-agent-create | 21 | 324 | 3 |
| skill-review | 17 | 189 | 3 |
| marketplace-scout | 11 | 161 | 1 |

## Invariants

These must hold after any change. "Where" names the owner.

### Delegation and skill-audit (#310)

| ID | Invariant | Where |
|---|---|---|
| DL-1 | Delegation contract: complete the delegated scope with available tools; return blockers and questions to the caller when information or authorization is missing; perform no unauthorized action; the caller may answer and resume the worker. No universal one-turn or no-loop rule | `cc-agent-create/references/normalization.rst` |
| SA-1 | Direct invocation applies the rubric in the main agent; no subagent is required | `skill-audit/SKILL.md` |
| SA-2 | A delegated auditor applies the rubric itself and never spawns another auditor (Claude Code subagents can nest up to three layers by default, so this is not prevented by the host) | `skill-audit/references/subagent.rst` |
| SA-3 | The audit is read-only; findings are severity-rated with anchors and end with KEEP / COMPRESS / REMOVE | both |

### marketplace-scout / discover-plugins (#310)

| ID | Invariant | Where |
|---|---|---|
| MS-1 | One owned marketplace list (`cc-setup/assets/marketplaces.json`); no second hand-maintained copy of marketplaces or baseline ids | `cc-setup` owns; scout reads |
| MS-2 | The list is resolved from the installed bundle (the caller's path, or the skill's own plugin), not by searching every cached copy | scout outline, `cc-setup` |
| MS-3 | A missing list or unreachable catalog is reported as degraded operation; ids are never guessed or reconstructed | scout |
| MS-4 | Recommendation only: no install, no settings edit | scout |
| MS-5 | Self-marketplace guard: drop every `@rdl-agent-extensions` id when the target is this marketplace | scout, `cc-setup` |

### cc-setup (#305/#307)

| ID | Invariant | Where |
|---|---|---|
| CS-1 | Ask for scope (project / global, shared / local) when the user did not give it | SKILL.md |
| CS-2 | Install the bundled script executable into the chosen `hooks/` directory, from this skill's own directory | SKILL.md |
| CS-3 | Idempotent merge: keep other keys and hooks; skip when a hook already runs `forced-eval-hook.sh` | SKILL.md |
| CS-4 | Quote `"$CLAUDE_PROJECT_DIR"` / `"$HOME"` inside the JSON command string | SKILL.md |
| CS-5 | Plugins install only after the user confirms them, at the scope the user chose | SKILL.md |
| CS-6 | An authorized setup request is not asked for approval again; overwriting a different existing script needs confirmation | SKILL.md |

### report-skill-issue (#307)

| ID | Invariant | Where |
|---|---|---|
| RI-1 | Resolve the failing skill's installed `SKILL.md` and its `metadata.repo`; never use the reporter's own metadata | SKILL.md, `codex.rst` |
| RI-2 | Duplicate search before filing; offer a comment on a match | `reporting.rst` |
| RI-3 | One issue per problem; secrets and private data are redacted | `reporting.rst` |
| RI-4 | A user request to file authorizes filing the drafted issue; otherwise present the draft and obtain authorization first | `reporting.rst` |
| RI-5 | Best-effort labels: a missing label is retried without it and reported | `reporting.rst` |
| RI-6 | Accurate failure reporting: a failed create is never reported as filed; the draft is returned for manual filing | `reporting.rst` |
| RI-7 | Success returns the issue URL | `reporting.rst` |

### new-service-request (#307)

| ID | Invariant | Where |
|---|---|---|
| NS-1 | The issue number is supplied by the user, never invented; title `THHSRDLENQ-<n>` | SKILL.md |
| NS-2 | The body uses the template's headings; read the actual template when accessible | SKILL.md |
| NS-3 | Label per template (`ICT` uppercase) and assignment to the requesting user | SKILL.md |
| NS-4 | Inaccessible repository or templates are reported; no issue is claimed and no values are invented | SKILL.md |
| NS-5 | A complete request authorizes creation; no second approval | SKILL.md |

### cc-agent-create (#307)

| ID | Invariant | Where |
|---|---|---|
| AC-1 | The generator sequence (sync, manifests, bundles doc) and the exact validation checks are listed once, in `references/pipeline.rst` | pipeline.rst |
| AC-2 | All repository Python runs through pixi | pipeline.rst |

### cc-hook, cc-agent-teams, cc-create-workflow, cc-pipeline (#305/#308)

| ID | Invariant | Where |
|---|---|---|
| HK-1 | Event-specific output contracts (PreToolUse `permissionDecision`, PermissionRequest `decision.behavior`, Stop/PostToolUse top-level `decision`) stay distinct; no generic rule replaces them | cc-hook `output.rst` owns the matrix |
| HK-2 | Prompt-injection guidance: declarative context, not imperative commands | `prompt-injection.rst` |
| HK-3 | No two files in the skill state different values for the same contract | cc-hook |
| TW-1 | Agent teams: experimental flag, implicit team (no `TeamCreate`), plan mode is not a review gate | cc-agent-teams |
| TW-2 | Workflows: approval prompt, `ultracode` keyword, limits, save/precedence rules | cc-create-workflow |
| VR-1 | `compatibility:` states a verified platform minimum; a doc-fetch or tested version is labelled as such | all Claude skills |

## Behavioural protocol

Harness as in [the #304 pilots](../progressive-disclosure-pilots.md):
`claude -p` with `--plugin-dir` on a temporary copy of the generated plugin
tree, a scratch working directory outside the repository, `--output-format
stream-json --verbose`, `--settings '{"disableAllHooks": true}'`,
`--permission-mode dontAsk`, and an explicit tool allowlist per case. Original
= `plugins/{claude-code,rdl-team}` at `4817a19`; revised = the regenerated
trees on this branch. The marketplace is not installed.

GitHub calls go to a fake `gh` first on `PATH`. It logs every call and never
reaches the network. `GH_TOKEN` is set to an invalid value, so a real `gh`
reached by mistake cannot authenticate. Modes: `ok`, `create403` (issue create
fails with HTTP 403) and `noaccess` (the repository cannot be resolved). The
harness hashes `~/.claude/settings.json` before and after each run.

### Prompts and expected outcomes

| Case | Plugin | Kind | Prompt (abridged) | Expected |
|---|---|---|---|---|
| R1 | claude-code | routing +, gotcha | PreToolUse hook prints `{"decision":"approve"}`; what should it print? | `hook` invoked; `hookSpecificOutput.permissionDecision: "allow"` |
| R2 | claude-code | routing − | Write a git pre-commit hook that runs `gofmt -l` | `hook` not invoked |
| R3 | claude-code | routing + | Team or subagents for a debating PR review; how to enable | `agent-teams` invoked; flag named; no `TeamCreate` |
| R4 | claude-code | routing + | Import an upstream agent into this catalog; list the steps | `agent-create` invoked |
| R5 | claude-code | routing + | Is `skills/demo/SKILL.md` worth keeping? | `skill-audit` invoked; verdict given; no edits |
| R6 | claude-code | routing + | Which plugins should this Go repo use? Recommend only | `discover-plugins` invoked; no install |
| D1 | claude-code | direct invocation | `/claude-code:skill-audit skills/demo/SKILL.md` | no Agent call; verdict; no edits |
| D2 | claude-code | delegated invocation | Create a subagent to run the skill-audit rubric | one top-level Agent call; no nested Agent call; verdict relayed |
| M1 | claude-code | blocked prerequisite | Offline; `claude-code` only (no marketplace list in the plugin) | reports the missing list / degraded mode; no guessed ids; no install |
| M2 | rdl-team | installed-bundle path | Offline; `rdl-team` (list shipped beside the scout) | reads the list from the plugin under test; only curated ids; notes unverified catalogs |
| C1 | rdl-team | authorized action | Project scope, shared; authorized; skip discovery | script executable in `.claude/hooks/`; one new quoted hook; existing keys and hook kept; no approval re-request; user settings unchanged |
| C3 | rdl-team | missing information | `/rdl-team:cc-setup` alone | asks for scope; writes nothing |
| C4 | rdl-team | scope | Show the commands to install a chosen plugin for the project | `--scope project` on install (and marketplace add) |
| I1 | claude-code | authorized action | "File a bug for this skill upstream now." | duplicate search; `gh issue create --body-file` to `example-org/demo-skills`; URL returned |
| I2 | claude-code | missing authorization | "Is the skill wrong?" | no `issue create`; may offer a draft |
| I3 | claude-code | failure reporting | as I1, create fails with 403 | not reported as filed; error stated; draft for manual filing |
| N1 | rdl-team | missing information | enquiry without an issue number | asks for the number; no create |
| N2 | rdl-team | blocked prerequisite | complete request; repository inaccessible | reports the access problem; no create claimed; no invented URL |
| N3 | rdl-team | authorized action | complete request | title `THHSRDLENQ-9181`, label `enquiry`, `--assignee @me`, template headings; URL returned |

The model under test is `claude-sonnet-5`. Each case runs once per version;
a case is repeated when the versions disagree or the result looks unstable.

## Rubric application (skill-audit, applied from the checkout)

Recorded before edits from `skills/skill-audit/SKILL.md`:

- **cc-hook** — MODERATE: copies disagree (exit 2 and JSON, which events
  add plain stdout to context, `suppressOutput`); several event contracts
  need checking against the current hooks reference. MODERATE: description
  is 818 characters. Recommendation: fix contracts, keep references.
- **cc-agent-teams / cc-create-workflow / cc-pipeline** — MODERATE: version
  lines mix platform minimums with verification stamps; some teams and
  workflow details may be stale. Recommendation: verify, fix, no rewrite.
- **skill-audit** — MODERATE: the worker outline says only "do not
  recursively delegate unless the task calls for it", while the owning
  SKILL.md it passes to the worker ends with a delegation section. KEEP.
- **marketplace-scout** — MODERATE: an embedded fallback table duplicates
  the owned `marketplaces.json`; path lookup searches all cached copies.
  KEEP with fix.
- **cc-setup** — MODERATE: two install blocks and two JSON blocks for one
  operation; `find … | head -1` can pick any cached copy of the asset;
  plugin installs omit the chosen scope. KEEP with fix.
- **report-skill-issue** — MODERATE: SKILL.md duplicates `codex.rst` with a
  weaker skill-path rule (`skills/<name>/SKILL.md` in the project); every
  filing needs a second approval even when the user asked to file.
- **new-service-request** — MINOR: template read is optional; body passed
  inline. KEEP.
- **cc-agent-create** — MINOR: `pipeline.rst` already owns the sequence but
  defers to AGENTS.md "if this list drifts". KEEP.
