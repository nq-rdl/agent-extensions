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

---

Everything below was recorded **after** the edits.

## Sources

Fetched on 2026-09-29 with Claude Code **2.1.284** installed
(`claude --version`):

- Hooks reference and guide: https://code.claude.com/docs/en/hooks and
  https://code.claude.com/docs/en/hooks-guide
- Agent teams, subagents, workflows, skills, settings, and plugin discovery:
  https://code.claude.com/docs/en/agent-teams, https://code.claude.com/docs/en/sub-agents,
  https://code.claude.com/docs/en/workflows, https://code.claude.com/docs/en/skills,
  https://code.claude.com/docs/en/settings, https://code.claude.com/docs/en/discover-plugins
- Version minimums: the Claude Code changelog,
  https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md
- Service-desk templates: `rdl-service-desk/service-desk`
  `.github/ISSUE_TEMPLATE/*.md` at `a3f4f4a` (read-only `gh api`). Recent
  issue titles confirm the `THHSRDLENQ-<n>` convention.
- `claude plugin install --help` and `claude plugin marketplace add --help`.
  Both take `--scope user|project|local`; the default is `user`.

## Factual checks

| Skill | Finding | Source | Action |
|---|---|---|---|
| cc-hook | "Claude Code ignores JSON when you exit 2" (SKILL.md, output.rst) | hooks: exit 2 blocks, valid JSON is still read, and a JSON `reason` wins over stderr | Fixed in both copies |
| cc-hook | Plain stdout becomes context for UPS/UPE/SessionStart; SKILL.md omitted UPE, and all copies omitted PostModelSwitch | hooks: four events | Fixed |
| cc-hook | lifecycle.rst: `PermissionRequest` exit 2 "Denies permission" | hooks: exit 2 is not honored; deny through `decision.behavior` | Fixed |
| cc-hook | lifecycle.rst: Setup/Notification "show stderr to the user" | hooks: exit code and stderr are ignored | Fixed; added the missing PreModelSwitch, WorktreeRemove, StopFailure, and DirectoryAdded rows |
| cc-hook | output.rst: TaskCompleted uses top-level `decision` | hooks decision table: TeammateIdle/TaskCompleted use the exit code or `continue: false` | Fixed; added PostToolUseFailure/PostToolBatch to the top-level list |
| cc-hook | `suppressOutput: true` hides stdout (3 files) | hooks: has no effect | Fixed |
| cc-hook | `stopReason` "not shown to Claude" | hooks: stays in the conversation | Fixed |
| cc-hook | HTTP 2xx plain text "added as context" | hooks: non-blocking error, not added | Fixed |
| cc-hook | A prompt hook's `ok:false` on PreToolUse returns the reason to Claude | hooks: ends the turn by default; `continueOnBlock: true` (v2.1.210) and agent hooks continue | Fixed; completed the per-event list |
| cc-hook | `$ARGUMENTS` "interpolates provided arguments"; default model "Haiku" | hooks: placeholder for the input JSON (appended if absent); the background model | Fixed |
| cc-hook | Skill/agent frontmatter hooks run "while active" | hooks: skill hooks persist for the session (`once: true` removes one after its first successful run); subagent hooks run while the subagent runs | Fixed |
| cc-hook | SessionEnd matcher `bypass_permissions_disabled`; SessionStart without `fork`; precedence without `defer`; imprecise matcher rule | hooks matcher and precedence tables | Fixed |
| cc-hook | The ConfigChange recipe reads `.config_source` and `.changed_keys` | hooks: the input fields are `source` and `file_path` | Fixed (the recipe logged nulls) |
| cc-hook | `PermissionRequest` "does not fire in -p mode" | hooks-guide: fires only when an SDK `canUseTool` callback supplies the prompt | Fixed (3 places) |
| cc-hook | The auto-format recipe exits 1 on an empty path; the stop-checklist asset claims to "continue until checks pass" | executed; asset read | Fixed; the description now matches the one-shot reminder |
| cc-hook | Two grid tables were malformed RST (pre-existing) | docutils | Fixed |
| cc-hook | The block-rm-rf pattern misses `rm -fr`, `rm -r -f`, and `git push -f` | executed by the fact-check worker | Limitation stated beside the recipe |
| cc-agent-teams | Size "2-5" versus "3-5"; a `~/.claude.json` teammateMode fallback; a teammate "inherits prompt, tools, model"; "lead's permission settings"; `/resume` only; no note that named subagents become teammates | agent-teams docs | Fixed |
| cc-agent-teams | Subagents "cannot talk", are "ephemeral", and have "no user interaction"; overhead is "quadratic" | sub-agents docs (SendMessage resume, agent panel) | Fixed in subagent-vs-team.rst |
| cc-create-workflow | Only permission prompts pause a run; `/effort high` turns ultracode off | changelog 2.1.271 (usage-limit pause); 2.1.284 (`/effort ultracode off` toggle) | Fixed with version conditions |
| cc-create-workflow | "2.1.274 supports plugin workflows" reads as a minimum | no changelog entry | Relabelled as the verified version |
| cc-setup | Plugin installs have no `--scope` (default user) after a project-scope setup | CLI help; discover-plugins docs | Fixed; see C4 |
| cc-setup | On this host, `find ~/.claude/plugins … \| head -1` returns the marketplace clone's canonical `skills/cc-setup` copy before any installed plugin | executed | Replaced with `${CLAUDE_SKILL_DIR}` (changelog 2.1.69; skills docs) |
| marketplace-scout | An embedded fallback table duplicated `marketplaces.json`; it used the same `find \| head -1` lookup; the whole procedure lived in the delegation outline, so direct use had none | reading; see M1/M2 | Procedure moved to SKILL.md; list resolved from the installed bundle; fallback table removed |
| report-skill-issue | SKILL.md told the agent to look for `skills/<name>/SKILL.md`; codex.rst already resolved the installed skill | reading | SKILL.md aligned with codex.rst |
| new-service-request | Templates, labels, and headings | service-desk templates at `a3f4f4a` | Retained; provenance recorded |

Claude Code subagents can spawn nested subagents by default, up to three
layers (sub-agents docs, "Let subagents spawn their own subagents"). The
skill-audit recursion risk is therefore real in principle, although no run
showed it.

## What changed where

| Skill | Change |
|---|---|
| cc-agent-create | `normalization.rst` gains the delegation contract (#310); `frontmatter-contract.rst` points outlines to it |
| skill-audit | SKILL.md and the outline say that a delegated auditor applies the rubric itself; the outline states the contract; the CONTRIBUTING lookup is limited to this repository |
| marketplace-scout | The procedure is in SKILL.md (the direct route); the outline covers only the handoff; the list path comes from the caller or the sibling `cc-setup`; a missing list is reported as degraded mode |
| cc-setup | One scope table, one install block, and one JSON example; `${CLAUDE_SKILL_DIR}` for assets; `--scope` on installs; a single idempotency rule; an authorized setup is not re-confirmed; stale asset comments fixed |
| report-skill-issue | SKILL.md holds the installed-skill lookup; `reporting.rst` step 5b always redacts, treats a filing request as authorization, and otherwise requires a draft plus explicit confirmation |
| new-service-request | A template-read step with a failure path, `--body-file`, explicit authorization and failure reporting, and template provenance |
| cc-hook, cc-agent-teams, cc-create-workflow, cc-pipeline | The factual fixes above; new descriptions for cc-hook and cc-agent-teams |
| rdl-switch-repo, rdl-workflow | `compatibility:` separates the minimum from the targeted version |

## After sizes

| Skill | Body lines | Approx. body tokens |
|---|---|---|
| cc-setup | 196 → 158 | 2277 → 1991 |
| marketplace-scout | 11 → 77 | 161 → 919 (outline 259 → 90 lines) |
| report-skill-issue | 48 → 31 | 484 → 387 |
| new-service-request | 83 → 89 | 718 → 911 |
| skill-audit | 28 → 31 | 349 → 406 |
| cc-hook | 178 → 180 | 2274 → 2346 |
| cc-agent-teams | 329 → 339 | 2792 → 2987 |
| cc-create-workflow | 170 → 181 | 1992 → 2169 |

marketplace-scout's SKILL.md grew because the procedure moved out of the
outline. The skill and outline together shrank from 270 to 167 lines.

## Behavioural results

**Conditions.** Claude Code 2.1.284, model `claude-sonnet-5` (default
effort), Linux, OAuth login. Original = the plugin trees at `4817a19`.
Revised = the trees regenerated on this branch, before the last skill-audit
wording change and two RST table fixes; neither affects these prompts. The
same user-level plugins (codex, git, pixi, worktrunk, frontend-design) were
present for both versions. Hooks were disabled. `~/.claude/settings.json`
was hashed around every run and never changed. There were 49 recorded runs
costing USD 8.40. About USD 1.1 more went on superseded runs: a `dontAsk` C1
that could not write `.claude/`, two N runs against a bug in the fake `gh`,
and an interrupted batch. The total is about USD 9.5.

Harness notes: `--allowedTools` does not stop read-only Bash (`find`, `ls`)
or `ToolSearch` → `WebFetch`, so M1 and M2 also pass `--disallowedTools
WebFetch WebSearch`. C1 and C2 need `--permission-mode bypassPermissions`
because `dontAsk` blocks writes under `.claude/`. The first N1/N3 original
runs were discarded after the fake `gh` was fixed (`repo view <repo>` and
`api repos/…`).

| Case | Expected | Original | Revised |
|---|---|---|---|
| R1 hook +, gotcha | `hook`; `permissionDecision: "allow"` | pass | pass |
| R2 Git hook − | `hook` not invoked | pass | pass |
| R3 teams + | `agent-teams` invoked | **0/2** (answered "plain subagents" from memory) | **2/2**; team plan; flag named |
| R4 agent-create + | `agent-create` | pass (read 3 references) | pass (same) |
| R5 audit + | `skill-audit`; verdict; no edits | pass | pass |
| R6 discovery + | `discover-plugins`; no install | routed 2/2; hit the 10-turn cap | routed 2/2; hit the cap once |
| D1 direct audit | no Agent call; verdict | pass; 4 tool calls (searched `/` and for CONTRIBUTING) | pass; 1 tool call |
| D2 delegated audit | 1 Agent call; no nested Agent call | pass (0 nested) | pass (0 nested) |
| M1 list missing, offline | report the missing list; no guessed ids | **fail**: 19 tool calls searching `/` and the user's marketplace clones; recommended ids from cached catalogs without saying the team list was missing | **pass**: 6 calls; states that the list is missing and why; recommends nothing unverified; says how to fix it |
| M2 installed bundle, offline | read the plugin's own list; curated ids only | pass, after a `find` over the plugin directory | pass; the first call reads `../cc-setup/assets/marketplaces.json` in the plugin under test |
| C1 authorized setup | script plus one quoted hook; keys kept; no re-ask | pass | pass (script identical to the plugin under test) |
| C2 already wired | settings unchanged | pass | pass |
| C3 no scope | ask; write nothing | pass | pass |
| C4 install scope | `--scope project` | **fail**: `claude plugin install go@rdl-agent-extensions`, labelled "scoped to this project" | **pass**: `--scope project` on both commands |
| I1 "file a bug now" | search; file with `--body-file`; URL | **asked for approval again**; not filed | filed; retried without the missing `skill` label; URL returned; no username or scratch path in the body |
| I2 "is the skill wrong?" | no filing | pass (offered) | pass (offered) |
| I3 create returns 403 | not reported as filed; draft returned | never reached create (asked for approval) | pass: quotes the 403, says "not created", gives the full draft and the manual URL |
| N1 no issue number | ask; no create | pass | pass |
| N2 repository unreachable | report the access problem; no create claimed | pass | pass |
| N3 complete request | title, label, `@me`, headings, URL | pass (inline `--body`) | pass (read the template; `--body-file`) |
| V1 skill-review | report saved; session correction used | pass | pass |
| V2 skill-audit with session context | verdict; correction used | pass | pass |

Notes:

- The revised I1 run reported the title, labels, and a one-line summary but
  not the full body that step 5b asks for. The issue URL shows the body; the
  text was not changed.
- In one revised R6 run the model read `~/.claude/settings.json` and
  `~/.claude.json` (read-only) while looking for declared marketplaces.
- Neither D2 version read the delegation outline; the parent told a
  general-purpose worker to load the skill. No run of either version spawned
  a nested auditor, so SA-2 is a preventive change, not a measured fix.

## Decision record: skill-review and skill-audit (#309)

| Field | skill-review | skill-audit |
|---|---|---|
| Published invocations | `/claude-code:skill-review`; Codex `$claude-code:skill-review` (native entrypoint `references/codex.rst`) | `/claude-code:skill-audit`; Codex `$claude-code:skill-audit` |
| Affected bundle, hooks, docs | `claude-code` bundle; no hook; delegation outline | `claude-code` bundle; the `skill-audit-nudge` PostToolUse hook suggests it after a `SKILL.md` edit; AGENTS.md, CONTRIBUTING, `docs/delegation.md` (former `skill-auditor`), and epic #312's protocol all name its rubric |
| Input | The session: touched skills, user corrections, verified API names, open questions | One target `SKILL.md` or diff |
| Output | Severity-grouped findings **saved to a report file** (host-specific default path) | Severity-grouped findings with a KEEP / COMPRESS / REMOVE verdict; read-only |
| Tasks (V1, V2, R5, D1, D2) | V1 checked the corrected fact against the file, found the correction already captured, raised an unconfirmed `git push` step, and wrote `review.md` | V2, R5, and D1 gave the verdict COMPRESS, kept the `Release-Note:` rule, and asked to pin "only for user-facing changes" |
| Network/runtime | None; writes one report file | None; read-only |
| Grouping impact of a merge | Would change one public command and its Codex override | Would change the nudge hook text and the epic protocol |
| Replacement if retired | None that keeps the saved report and the focus on session corrections | None |

**Decision: retain both.** They answer different questions. skill-review
captures what a session taught (corrections not yet in the skill) and saves a
report. skill-audit judges whether a skill's content earns its context. The
consumer tasks produced different outputs for the same fixture. A merge
would remove a public command with no replacement for the saved session
report, and it would require hook and documentation changes for no measured
gain. No migration or deprecation is needed. The auditor recursion concern
(#309 item 1) is handled under #310.

## #308 — Claude skills version lines

| Skill | Before | After | Evidence |
|---|---|---|---|
| cc-agent-teams | "first shipped v2.1.32; assumes v2.1.178+; checked … v2.1.283 on 2026-09-28" | Requires v2.1.178+ (first shipped v2.1.32), the flag, and an interactive session; checked with 2.1.284 on 2026-09-29 | changelog 2.1.32 and 2.1.178; docs: no teammates in `-p` |
| cc-create-workflow | v2.1.154+; path-walking 2.1.178+; keyword before 2.1.160 | Same, plus the Pro `/config` step and a doc-check stamp; plugin workflows labelled "verified on 2.1.274" | changelog 2.1.154, 2.1.160, 2.1.178; no entry for plugin workflows |
| cc-pipeline | "hooks I/O contract as of v2.1.x" | Minimums kept (`if` 2.1.85, workflows 2.1.154); doc-check stamp | changelog 2.1.85 and 2.1.154 |
| cc-hook | no `compatibility:` | 2.1.x; `if` v2.1.85+; checked with 2.1.284 on 2026-09-29; re-check URL | changelog 2.1.85 |
| rdl-switch-repo | "Claude Code 2.1.274; … 2.1.257+ for nested directories" | Requires 2.1.32+ (`--add-dir` skills); `/add-dir` of a subdirectory needs 2.1.257+; written for 2.1.274 | changelog 2.1.32 and 2.1.257 |
| rdl-workflow | "Claude Code 2.1.274 Workflow runtime" | Requires dynamic workflows (2.1.154+) with plugin workflow support; written for 2.1.274 | changelog 2.1.154 |
| rdl-task-bridge, cc-agent-create, skill-audit, skill-review, report-skill-issue, new-service-request, marketplace-scout | No version-dependent claims that need a pin | Retained | — |

## Disposition by issue

### #305 (duplication and stale material)

| Candidate | Disposition | Evidence |
|---|---|---|
| cc-hook contradictory copies | Changed | Factual checks table. SKILL.md, output.rst, lifecycle.rst, and prompt-injection.rst now state one exit-code, stdout, and suppressOutput rule. R1 passes in both versions |
| cc-hook event-specific contracts | Changed (verified). The per-event matrix stays in output.rst and lifecycle.rst; no generic rule replaces it | hooks reference, as cited in the table |
| cc-agent-teams stale material | Changed | Factual checks; R3 |
| cc-agent-teams `scripts/check-config.sh` | Changed (follow-up commit) | Rewritten with `jq` for Bash 3.2. It drops the nonexistent user-local scope and reports the effective value by settings precedence (managed > project local > project > user; any settings file beats a shell export). `--disable` sets `"0"` through `jq` and keeps valid JSON; invalid JSON is left untouched; no `sed -i`. `tests/test_cc_agent_teams_check_config.py` (17 tests, temporary HOME and project) had 8 failures and 2 errors on the old script and passes now, including a run under `docker.io/library/bash:3.2` (bash 3.2.57, BusyBox) with static jq 1.7.1 (sha256 `5942c9b0…c8ff5`); host jq is 1.6 |
| cc-create-workflow stale material | Changed | Factual checks |
| cc-setup one asset and one example | Changed | C1–C4; `tests/test_claude_code_family.py` |

### #306 (descriptions)

| Candidate | Disposition | Evidence |
|---|---|---|
| cc-agent-create | Retained (291 characters) | R4 routed in both versions |
| cc-hook | Changed, 818 → 382 characters; adds "Not for Git hooks" | R1 routed and R2 not routed, in both versions |
| cc-agent-teams | Changed, 507 → 351 characters; adds cues for debate and team versus subagents | R3 0/2 → 2/2 |
| skill-audit (former skill-auditor) | Retained (374 characters) | R5 routed in both versions |
| marketplace-scout (discover-plugins) | Changed, 208 → 305 characters; trigger-first | R6 routed 2/2 in both versions |
| report-skill-issue (changed with #307) | Changed, 450 → 351 characters; dropped "offer even if not asked" | I1/I3 routed; I2 offered in both versions |

### #307 (workflows and authorization)

| Candidate | Disposition | Evidence |
|---|---|---|
| report-skill-issue | Changed | I1 (authorized), I2 (not authorized), I3 (failure) |
| cc-setup | Changed | C1 (authorized), C2 (idempotent), C3 (missing information), C4 (scope) |
| cc-agent-create | Retained. `pipeline.rst` already owns the sequence and lists the exact checks, run through pixi | R4 read the three references in both versions |
| new-service-request | Changed | N1 (missing number), N2 (blocked), N3 (authorized) |

### #308

See the version table above. Every Claude-skill row was updated or retained.

### #309

skill-review and skill-audit: **retain both** (see the decision record).

### #310

| Candidate | Disposition | Evidence |
|---|---|---|
| Delegation contract in `normalization.rst` | Changed | `tests/test_claude_code_family.py` (canonical, Claude, and Codex copies) |
| skill-auditor recursion | Changed (preventive) | D1 direct and D2 delegated: no nested Agent call in either version |
| marketplace-scout: one owned asset | Changed | Test: a single `marketplaces.json` and no repository list in the scout |
| marketplace-scout: missing asset and degraded operation | Changed | M1 fail → pass |
| marketplace-scout: installed-bundle path | Changed | M2 |
| marketplace-scout: recommendation-only scope | Retained | No install or settings write in M1, M2, or R6 |

## Tests

- `tests/test_claude_code_family.py` (new) checks that every copy of
  `normalization.rst` states the delegation contract, that there is one
  `marketplaces.json`, that the discovery skill has no marketplace
  repository list, and that the cc-setup JSON example parses and quotes the
  path variable. Before the edits it had 32 failures (packaged copies
  without the contract, and the scout's embedded list); it now passes.
- `tests/test_codex_package.py`: the reporting assertion now encodes the
  #307 authorization rule; it previously asserted the old always-confirm
  sentence. The new assertions fail on the original `reporting.rst`.

## Rubric disagreements

- The rubric would call cc-setup's paragraph on hook behaviour inferable,
  but it is the only description of the script that the skill installs. It
  was kept.
- marketplace-scout's SKILL.md grew from 11 to 77 lines. The rubric's
  conciseness item favours a short entrypoint, but the short version gave
  direct invocation no no-guessing rule (M1 original).

## Limitations

- One model and one host. Each case ran once, except R3, R6, V1, and V2
  (twice). The R3 routing gain is 0/2 → 2/2, which is not a significant
  sample.
- The GitHub cases use a local `gh` shim. Real GitHub labels, permissions,
  and MCP behaviour were not exercised. In one discarded original run the
  model read the shim's source.
- R6 hit the 10-turn cap in three of four runs, so recommendation quality
  with network access was not measured.
- The delegated audit (D2) never loaded the outline, so no run exercised the
  new worker wording.
- The Bash 3.2 container test is skipped unless podman, the `bash:3.2` image, and `BASH32_STATIC_JQ` are available, so CI does not run it. BSD tools were not run; the script no longer uses `sed` and calls `mktemp` only with a template.

## Status at hand-off

`check-config.sh` follow-up: **done.** The script is rewritten with `jq`
for Bash 3.2, and `tests/test_cc_agent_teams_check_config.py` passes: 17
tests on the host (jq 1.6), plus the `bash:3.2` container run with
`BASH32_STATIC_JQ` pointing at a static jq 1.7.1. The full unit suite passes
(1112 tests, 1 skipped: the container class without `BASH32_STATIC_JQ`).
Next step (optional): make the container test runnable without a manual
jq download, for example with a pinned image that includes jq.
