# OpenCode and Spec Kit skill review (#305–#308)

This record follows the pilot protocol in epic #312, as used in
[progressive-disclosure-pilots.md](../progressive-disclosure-pilots.md). It
covers the `opencode-dev` plugin (`opencode-plugin`, `opencode-sdk`,
`opencode-agent`, `opencode-tools`, `opencode-skill`, `opencode-policies`,
`opencode-delegate`) and the `speckit-dev` plugin (`speckit-create`,
`speckit-validate`, `speckit-manage`, `speckit-publish`).

The tasks, invariants, prompts, and expected outcomes below were recorded
**before** any skill edit, at source revision `4817a19`
(`epic/skill-review`, after #301/#303/#304).

## Baseline sizes

Measured with `asctl repo-check --size-report` built from `4817a19`.
Approximate tokens are body bytes / 4, not measured model usage. Description
length is the folded YAML string, measured with PyYAML.

| Skill | Body lines | Approx. body tokens | References | Description chars |
|---|---|---|---|---|
| opencode-skill | 189 | 1949 | 2 | 661 |
| opencode-policies | 155 | 1696 | 2 | 663 |
| opencode-delegate | 154 | 2088 | 2 | 693 |
| opencode-tools | 150 | 1751 | 4 | 830 |
| opencode-sdk | 148 | 1967 | 3 | 632 |
| opencode-agent | 141 | 1866 | 3 | 698 |
| opencode-plugin | 127 | 1653 | 1 | 626 |
| speckit-create | 64 | 903 | 2 | 513 |
| speckit-manage | 55 | 595 | 2 | 323 |
| speckit-validate | 48 | 522 | 2 | 397 |
| speckit-publish | 34 | 362 | 2 | 369 |

## Invariants

These must survive any change. "Owner" names the skill that owns the fact
after the change. A short warning may repeat beside an example that would
otherwise execute wrongly; that repetition is intentional and listed.

### OpenCode

| ID | Invariant | Owner |
|---|---|---|
| OC-1 | Handler keys you return (`tool.execute.before`, `permission.ask`, …) versus bus events read in the single `event` handler (`session.idle`, `command.executed`); there is no `stop` hook | plugin |
| OC-2 | `(input, output)` contract: mutate `output`, `throw` to block; `apply_patch` carries `output.args.patchText`, not `filePath` | plugin (tools repeats the patch warning beside the built-in list) |
| OC-3 | Overloaded keys: MCP local `environment` versus LSP `env`; `lsp` as config key, experimental tool, and permission key; `lsp` boolean-or-object, omitted means disabled | tools |
| OC-4 | Custom tools: filename is the tool name; `<file>_<export>` for multiple exports; a same-named file overrides the built-in | tools |
| OC-5 | Policies: nested under `experimental.policies`; only `provider.use`; global beats project; default allow; `deny *` first, then allow; last match wins | policies |
| OC-6 | Nonuniform permission defaults (`doom_loop` and `external_directory` ask, `.env` reads denied); one `edit` key covers `edit`/`write`/`apply_patch`; bash patterns need a trailing `*` for arguments; last match wins | policies (agent keeps a one-line pointer) |
| OC-7 | Agents: `steps` not `maxSteps`; `permission` not `tools`; `mode` values; filename is the documented id; CLAUDE.md fallback and its disable variables; `AGENTS.md` does not auto-load `@file` | agent |
| OC-8 | Skills: five recognised frontmatter fields; documented name rules; Claude-compatible drop-in paths; `permission.skill` globs versus disabling the tool; references alias rules, description advertising | skill |
| OC-9 | SDK provenance (JS package, Go module path, Go SDK version, Go toolchain) has one owner, the SDK skill; other skills route there instead of copying pins | sdk |
| OC-10 | SDK error/option behaviour: results under `result.data`; structured-output failure is returned, not thrown (unless `throwOnError`); Go `Field` wrappers (`opencode.F`), `*opencode.Error`, retries, no default timeout | sdk |
| OC-11 | Delegation: detached worker (`detached: true` plus `unref()`); `run --format json`; `--attach` to reuse a server; auto-approval never overrides an explicit `deny`; ACP lacks `/undo` and `/redo`; Codex app-server methods do not exist in ACP | delegate |
| OC-12 | Every cross-skill route resolves in the shipped bundle as `/opencode-dev:<leaf>` | all |
| OC-13 | Upstream ownership wording is neutral and correct | all |

### Spec Kit

| ID | Invariant | Owner |
|---|---|---|
| SK-1 | Each validation rule says whether upstream rejects it (and from which checked version), upstream warns or auto-corrects, or it is a stricter local convention | validate |
| SK-2 | The upstream-installer oracle is defined: supported installer version, isolated temporary project/HOME/config, no credentials or publishing, no change to the user's project, network and script-execution policy, cleanup | validate |
| SK-3 | When the oracle is not run, the report says so and never claims upstream validation | validate |
| SK-4 | The version-conditioned `provides` rule (commands or hooks; events; templates/scripts) stays explicit | create, validate |
| SK-5 | Manage: catalogs added with `catalog add` are discovery-only by default; lower priority number wins; `--dev` is a boolean with the path as positional | manage |
| SK-6 | `compatibility:` and guards claim only what was checked; no 0.12–1.0.x range is inferred from one current check | all speckit |

## Rubric application (skill-audit, applied from the checkout)

Recorded before edits from `skills/skill-audit/SKILL.md`:

- **opencode-sdk, opencode-delegate, opencode-skill, opencode-tools,
  opencode-plugin** — MODERATE (duplication): the Go SDK pin
  (`v0.19.2`, Go 1.22+, module-path note) is copied into five skills and the
  hook. Only the SDK skill uses it. Recommendation: route to the SDK skill.
- **opencode-agent, opencode-policies, opencode-tools, opencode-skill** —
  MODERATE (duplication): the permission-key vocabulary, the `edit` covers
  `write`/`apply_patch` rule, and "last match wins" are restated in four
  skills with small differences (`lsp` described as "no object form" in
  policies but glob-capable in agent). Recommendation: one owner (policies),
  short pointers elsewhere.
- **opencode-tools / opencode-skill** — MODERATE (possible stale fact): both
  teach `tools` as a separate axis from `permission`. Needs checking against
  current upstream before any consolidation.
- **opencode-agent** — MINOR: flags its config-precedence chain as
  unverified author knowledge. Verify or cut.
- **opencode-sdk / opencode-delegate** — MODERATE (verify): "there is NO
  `createOpencodeServer`" and the structured-output field names must be
  checked against the SDK source, not only the docs page.
- **all OpenCode descriptions** — MODERATE (#306): 626–830 characters, above
  the 400-character editorial target, with long keyword lists.
- **speckit-validate** — CRITICAL (#307): the checklist reports every rule as
  PASS/FAIL without separating upstream rejection from local convention, and
  it does not define how to confirm results with the real installer.
- **speckit-create / validate / manage / publish** — MODERATE (#308):
  `compatibility: spec-kit >=0.12` and "pinned to v0.12.x" were written from a
  check of one release line; version-specific rules need checked tags.
- **speckit-manage** — MINOR (#306): description is within target; check
  sibling routing against create and publish.

## Behavioural protocol

Same harness as the #304 pilots: `claude -p` with `--plugin-dir` pointing at a
temporary copy of the generated plugin tree. **Original** = `plugins/<bundle>/`
exported from `4817a19`; **revised** = `plugins/<bundle>/` regenerated on this
branch. Runs use a scratch working directory outside the repository,
`--output-format stream-json --verbose`, `--permission-mode dontAsk`, tools
limited to `Skill Read Glob Grep`, and `--settings '{"disableAllHooks": true}'`
(the bundle hooks are owned by #311 and would add context to every prompt).
The marketplace is not installed. Model under test `claude-sonnet-5`.

**Observed per run.** Skills invoked, reference files read, loaded body size,
cost. Answers are graded by deterministic pattern checks plus manual review.

### Prompts and expected outcomes

**opencode-dev**:

| Case | Kind | Prompt (abridged; full text in the run script) | Expected |
|---|---|---|---|
| P1 | positive routing, normal task | OpenCode plugin that blocks `.env` reads and notifies when a session finishes; code only | `plugin` invoked; `tool.execute.before` that throws; `event` handler matching `session.idle`; no `stop` hook |
| P2 | known gotcha (OC-3) | `opencode.json` with a local MCP server needing `SENTRY_TOKEN` and a custom LSP needing `FOO_HOME` | `tools` invoked; `environment` under `mcp`, `env` under `lsp` |
| P3 | known gotcha (OC-5, OC-6) | global config: only Anthropic even if a repo enables OpenAI; bash asks except `git status` | `policies` invoked; `experimental.policies` `deny *` then `allow anthropic`; `"*": "ask"` before `"git status*"` |
| P4 | known gotcha (OC-10) | JS SDK: start server, prompt for JSON `{title}`, handle failure; TypeScript only | `sdk` invoked; failure checked on the returned message error, not only `try/catch`; field names match upstream source |
| P5 | normal task (OC-11) | companion that runs OpenCode tasks in the background, headless, pollable | `delegate` invoked; `detached: true` + `unref()`; `--format json`; auto-approval does not override `deny` |
| P6 | known gotcha (OC-7) | read-only review subagent that may run only `git diff`, max 8 steps | `agent` invoked; `steps: 8`; `permission` with `"*"` first; no `tools:`/`maxSteps` |
| P7 | known gotcha (OC-8) | existing `.claude/skills/pdf-tools/SKILL.md` with `name: pdf_tools`, `allowed-tools`: will it work in OpenCode? | `skill` invoked; name rule violation; inert Claude keys |
| N1 | negative routing | Claude Code `PreToolUse` hook in `settings.json` blocking `.env` reads | no `opencode-dev` skill |
| N2 | negative routing | OpenAI Codex CLI MCP server config | no `opencode-dev` skill |

**speckit-dev**:

| Case | Kind | Prompt (abridged) | Expected |
|---|---|---|---|
| K1 | normal task + SK-1 | inline `extension.yml` with `effect: readonly`, command `speckit.hello`, hooks `before_build` and `before_converge`, `version: "1.0"`; which issues would the installer reject and which are conventions? | `validate` invoked; `effect` rejected; `speckit.hello` auto-corrected with a warning; `before_build` accepted but never fires; `before_converge` is a real core hook; `1.0` accepted |
| K2 | blocked/unauthorized oracle (SK-2, SK-3) | "validate ./my-ext by actually installing it with specify to be sure" (no shell tool) | describes the isolated oracle; does not install into the user's project; reports the oracle as not run |
| K3 | positive routing (#306) | add an internal catalog URL so the team can install from it | `manage` invoked; `catalog add … --install-allowed` only for a vetted catalog |
| K4 | sibling routing | publish my extension to the community catalog | `publish` invoked, not `manage` |

---

Everything below was recorded **after** the edits.

## Sources and factual checks

All upstream reads were read-only (`gh api` GETs, source tarballs that were
never built or executed, `curl` of doc pages) on 2026-09-29. Local binaries
were run with `--help`/`--version` only: `opencode` 1.18.33 and `specify`
1.0.8 (uv tool).

- OpenCode: `anomalyco/opencode` tag `v1.18.33` (latest release, 2026-09-28;
  `sst/opencode` redirects there): docs in `packages/web/src/content/docs/`,
  plugin types in `packages/plugin/src/index.ts`, SDK in `packages/sdk/js/src/`,
  config schema in `packages/core/src/v1/config/`, loaders in
  `packages/opencode/src/{config,skill,tool}/`.
- Go SDK: `anomalyco/opencode-sdk-go` tag `v0.19.2` (latest, 2025-12-18):
  `go.mod`, `client.go`, `option/requestoption.go`, `session.go`.
- Spec Kit: `github/spec-kit` tags `v0.11.0`, `v0.12.0`, `v0.14.0`, `v0.15.0`,
  `v0.16.2`, `v1.0.0`, `v1.0.12` (latest, 2026-09-25):
  `src/specify_cli/extensions/__init__.py`, `agents.py`,
  `templates/commands/`, `extensions/*.md`, `.github/ISSUE_TEMPLATE/`.

| Skill | Claim before | Upstream finding | Action |
|---|---|---|---|
| opencode-sdk | "There is NO `createOpencodeServer`" | `packages/sdk/js/src/server.ts` exports it and `index.ts` re-exports it; the docs page omits it | Fixed (also delegate, asset, reference erratum) |
| opencode-sdk | Structured output read from `info.structured_output`; error has `.message`/`.retries` | `AssistantMessage.structured` and `StructuredOutputError.data.{message,retries}` in `v2/gen/types.gen.ts`; `session/prompt.ts` sets `message.structured`. The docs page is wrong | Fixed; example moved to `@opencode-ai/sdk/v2` |
| opencode-sdk | Structured-output example uses the root import with `{ path, body: { format } }` | Root (v1) `SessionPromptData.body` has no `format`; v2 `session.prompt` takes flat `{ sessionID, parts, format }` | Fixed |
| opencode-sdk | `NewClient()` targets `127.0.0.1:4096` | v0.19.2 defaults to `http://localhost:54321/` (`WithEnvironmentProduction`), overridable by `OPENCODE_BASE_URL` | Fixed; Go asset sets `option.WithBaseURL` |
| opencode-sdk | `config` "overrides `opencode.json`" | Passed as `OPENCODE_CONFIG_CONTENT` and merged over file config; the factory spawns `opencode` from `PATH` | Clarified |
| opencode-sdk | `responseStyle` default implied `data` | Docs: default `fields` (`{ data, error, … }`) | Fixed |
| opencode-sdk | Go pin `v0.19.2`, Go 1.22+, module path `sst` | Confirmed (latest tag; `go 1.22`; `module github.com/sst/opencode-sdk-go`); v0.19.2 has no `format` on `SessionPromptParams` | Kept, now only here; the lag is noted |
| opencode-plugin | Singular `.opencode/plugin/` "silently loads nothing" | `config/plugin.ts` globs `{plugin,plugins}/*.{ts,js}` | Fixed |
| opencode-plugin | `command.execute.before`: input "command info", output "command args" | `input { command, sessionID, arguments }`, `output { parts }` | Fixed |
| opencode-plugin | `console.log` "is swallowed" | Docs only recommend `client.app.log` for structured logging | Softened |
| opencode-plugin | `interface Hooks` key set, `PluginInput` fields, no `stop` hook | Match v1.18.33 | Retained |
| opencode-tools | "Singular is wrong" for `.opencode/tools/` | `tool/registry.ts` globs `{tool,tools}/*.{js,ts}` | Fixed |
| opencode-tools | `tools` gating is a separate axis from `permission` | Docs: `tools` deprecated since v1.1.1 and merged into `permission`; `config.ts` converts it (`false` → `deny`) and an explicit `permission` wins; the agents page says permission keys match MCP tool names | Fixed |
| opencode-tools | Pin `@opencode-ai/plugin@1.17.11`, said to be in `compatibility:` (which said `opencode`) | The package is 1.18.33 at the checked tag and versions with OpenCode | Replaced by a dated check; provenance routed to sdk |
| opencode-tools | `websearch` needs Exa; one variable enables the lsp tool | Also `OPENCODE_ENABLE_PARALLEL` or the OpenCode Go provider; `OPENCODE_EXPERIMENTAL=true` also enables the lsp tool | Fixed |
| opencode-tools | `opencode mcp auth\|list\|logout\|debug` | `--help` also lists `add` | Fixed |
| opencode-policies | Key list omitted `list` and `todowrite`; `lsp` has "no object form" | Schema: `lsp` accepts a pattern object; `todowrite` also gates `todoread`; `list` exists. The permissions page still calls `lsp` non-granular | Fixed; key vocabulary consolidated here |
| opencode-policies | `disabled_providers`/`enabled_providers` "deprecated" | Still in the v1.18.33 schema without a deprecation note; docs say to use policies | Softened |
| opencode-policies | A bare top-level `policies` is silently ignored | Config parsing uses `onExcessProperty: "ignore"` | Retained |
| opencode-agent | `/docs/modes/` 404, singular dirs, and merge order marked unverified | 404 confirmed with `curl`; `{agent,agents}`, `{command,commands}` and legacy `{mode,modes}` (loaded as primary agents) in source; merge order on `/docs/config/` | Verified; caveat removed |
| opencode-agent | "`name:` field does not set the id" | The filename is the documented id, but `config/agent.ts` spreads frontmatter after the filename name, so an undocumented `name:` replaces it | Reworded as "don't add `name:`" |
| opencode-agent | Body contained OpenCode's shell-output template syntax inline | Claude Code runs that pattern while loading a skill body; the skill failed to load without Bash (runs P6-orig-1/2, P6-rev-1) | Fixed; the literal form stays in `assets/command.md` |
| opencode-agent | `assets/agent.md` allowed `"git diff"` | Without a trailing `*` it matches only the bare command (permissions page tip) | Fixed to `"git diff*"` |
| opencode-skill | `tools.skill: false` is "not a permission entry" | Converted to `permission.skill: "deny"` | Fixed |
| opencode-skill | A name/regex/directory mismatch stops loading; duplicates fail silently | The loader requires only a string `name`; it does not enforce the regex or the directory match; a duplicate replaces the earlier one with a log warning | Troubleshooting corrected; documented rules kept for portability |
| opencode-skill | — | `OPENCODE_DISABLE_EXTERNAL_SKILLS` and the `skills.paths` config key exist in source | One line added |
| opencode-delegate | `--dangerously-skip-permissions` | `opencode run --help` documents `--auto`; the old flag and `--yolo` are hidden aliases | Fixed (SKILL.md, reference erratum) |
| opencode-delegate | ACP lacks `/undo`/`/redo`; `--format json`; `--attach`; auth flags | Match v1.18.33 docs and `--help` | Retained |
| speckit-validate | Every rule reported as PASS/FAIL | Upstream rejects some, warns and renames others, and accepts the rest silently | Rules labelled Rejects / Warns / Local |
| speckit-validate | `speckit.<cmd>` fails | `_try_correct_command_name` renames `speckit.<cmd>` and `<id>.<cmd>` with a warning (v0.12.0 and v1.0.12) | Fixed |
| speckit-validate | 18 hook events; unknown names fail | Any key is accepted; the core `converge` template reads `before_converge`/`after_converge` (v0.12.0–v1.0.12) | 20 events, labelled Local |
| speckit-validate | Command file must exist and have `description` | A missing file is skipped silently; the description defaults to empty | Labelled Local |
| speckit-validate | `v1.0` is invalid | `packaging` parses `v1.0` | Fixed |
| speckit-validate | `condition` "reserved for future" | Evaluated at dispatch (`config.x is set`, `==`, `!=`, `env.X is set`/`==`) since v0.12.0 | Fixed (also speckit-create) |
| speckit-validate | Not covered | Core-name ids (`plan`, …) rejected; string types enforced from v0.16.2; empty hook lists, duplicate names and unsafe aliases rejected | Added |
| speckit-manage | `.registry` is "the resolved view of the catalog stack"; unprefixed `.backup/` and `.registry` | User Guide v1.0.12: `.specify/extensions/.registry` is installation state; paths are prefixed | Fixed |
| speckit-manage | `SPECKIT_CATALOG_URL` is an "override catalog" | It replaces the whole stack; an empty project `catalogs: []` falls back to the defaults | Fixed |
| speckit-publish | Pinned to v0.12.x (2026-07-04) | Issue template `extension_submission.yml`, no direct PRs, 3–7 business days, catalog `extensions` keyed by id: all confirmed at v1.0.12 | Guard re-dated |
| all Spec Kit | `compatibility: spec-kit >=0.12` | Extension manifests exist from at least v0.11.0; rules differ by version (`provides` alternatives, type checks). Only the listed tags were read | Compatibility names the checked tags |

## Installer oracle (#307)

**Not run.** The coordinator relayed approval to run the pinned upstream
installer (`uv tool run --from git+https://github.com/github/spec-kit@v1.0.12
specify`) in an isolated directory. The session's permission policy refused the
command ("Code from External"), so the installer was not fetched or executed.
The locally installed `specify` 1.0.8 was not used as a substitute. The
isolated procedure and a 15-fixture set are recorded in
`skills/speckit-validate/references/installer-oracle.rst`, with outcomes
**predicted from source**, not observed. All Rejects/Warns/Local labels are
source-derived.

## What moved where

| Fact family | Owner now | Removed or reduced in |
|---|---|---|
| SDK packages, Go module/version/toolchain | opencode-sdk (`compatibility:` and provenance table) | plugin, tools, skill, delegate (pins deleted, route to sdk); the hook copy belongs to #311 |
| Permission keys, shapes, defaults, legacy `tools` conversion, `--auto` | opencode-policies | agent (key table → pointer plus the two traps an agent author hits); tools and skill point to policies |
| `edit` covers `write`/`apply_patch` | opencode-policies | Kept as a one-line warning in tools (beside the tool list) and agent (beside frontmatter): justified repetition |
| MCP gating example | opencode-tools `assets/mcp.json` | Legacy `tools` form replaced with `permission` |
| `createOpencodeServer`, SDK shapes | opencode-sdk | Delegate's copy removed; routes to sdk |
| Spec Kit rule labels and version notes | speckit-validate (`SKILL.md` table, `references/validation-rules.rst`) | create keeps its authoring table; the 20-event list repeats there because authors choose event names |

## After sizes

| Skill | Body lines | Approx. tokens | References | Description chars |
|---|---|---|---|---|
| opencode-skill | 189 → 192 | 1949 → 2046 | 2 | 661 → 355 |
| opencode-policies | 155 → 166 | 1696 → 1911 | 2 | 663 (unchanged) |
| opencode-delegate | 154 → 154 | 2088 → 2074 | 2 | 693 → 380 |
| opencode-tools | 150 → 149 | 1751 → 1807 | 4 | 830 → 397 |
| opencode-sdk | 148 → 177 | 1967 → 2487 | 3 | 632 → 640 |
| opencode-agent | 141 → 138 | 1866 → 1852 | 3 | 698 → 367 |
| opencode-plugin | 127 → 128 | 1653 → 1679 | 1 | 626 → 396 |
| speckit-validate | 48 → 76 | 522 → 1274 | 2 → 3 | 397 → 340 |
| speckit-create | 64 → 67 | 903 → 950 | 2 | 513 (unchanged) |
| speckit-manage | 55 → 61 | 595 → 691 | 2 | 323 → 398 |
| speckit-publish | 34 → 34 | 362 → 364 | 2 | 369 (unchanged) |

No size improvement is claimed. The SDK and validate bodies grew because they
now carry corrected, verifier-facing facts (SDK shape errata; per-rule upstream
labels and the oracle contract). All bodies stay under the 300-line target.

## Behavioural results

**Conditions.** Claude Code 2.1.284, model `claude-sonnet-5` (default effort),
Linux, OAuth login. Original = `4817a19`. Revised: `rev` (first edit pass),
`rev2` (shell-output and asset fixes; opencode-dev content of `61415ac`),
`rev3` (speckit-dev content of `bc5f6e3`). The same user-level plugins were
present in every run.

A first batch of 13 original-version runs used `--permission-mode dontAsk`
without pre-approving `Read`, so every reference read was denied. Those runs
are kept only as extra evidence. All rows below use the corrected harness
(`--allowedTools Skill Read Glob Grep --strict-mcp-config`).

Grading is by pattern plus manual review; (m) marks a manual override of a
pattern result. The K1 run used command `speckit.greet` (recorded above as
`speckit.hello`).

| Case | Version | Routed skill | Body chars | Reference reads | Passed |
|---|---|---|---|---|---|
| P1 plugin | orig / rev | plugin 1/1 · 1/1 | 6,753 / 7,132 | starter-plugin.ts / none | 1/1 · 1/1 |
| P2 tools gotcha | orig / rev | tools 1/1 · 1/1 | 7,138 / 7,488 | none | 1/1 · 1/1 |
| P3 policies gotcha | orig / rev | policies 1/1 · 1/1 | 7,224 / 8,014 | 2 refs / 1 ref | 1/1 · 1/1 |
| P4 SDK gotcha | orig | sdk 2/2 | ~8,100 | hello-sdk.ts | **0/2**: `info.structured_output`, `error.message`, root import with `format` |
| | rev, rev2 | sdk 2/2 | ~10,300 | hello-sdk.ts | **2/2**: v2 import, `info.structured`, `error.data.*` |
| P5 delegate | orig | delegate 1/1 | 9,030 | cli.rst, skeleton | 1/1 functional; used the hidden `--dangerously-skip-permissions` |
| | rev, rev2 | delegate 2/2 | ~8,900 | cli.rst, skeleton | 2/2 with `--auto`; `detached: true` + `unref()` kept |
| P6 agent gotcha | orig | agent 2/2, **body failed to load** | 0 | fell back to reading SKILL.md (run 1 found it by globbing another checkout) | 2/2 output correct via the fallback |
| | rev | agent 1/1, **failed to load** (text still present) | 0 | fallback reads | 1/1 via the fallback |
| | rev2 | agent 2/2, loaded | ~7,970 | agent.md, agents.rst | 2/2 |
| P7 skill drop-in | orig / rev | skill 1/1 · 1/1 | 8,168 / 8,562 | none | 1/1 · 1/1 |
| N1 Claude Code hook | orig / rev | update-config; no opencode-dev | — | — | 1/1 · 1/1 |
| N2 Codex MCP | orig / rev | none; no opencode-dev | — | — | 1/1 · 1/1 |
| K1 validate | orig | validate 2/2 | 2,253 | validation-rules.rst | **0/2** (m): called `speckit.greet` a hard reject and `before_converge` invalid |
| | rev, rev2, rev3 | validate 3/3 | ~5,700 | 0–1 reads | **3/3**: Rejects `effect`; Warns + rename for `speckit.greet`; `before_converge` valid; `1.0` Local; oracle stated as not run |
| K2 oracle, blocked | orig | manage 1/1 | — | none | 1/1 honest (no dir, no shell, no claim) |
| | rev, rev2 | none, manage | — | none | 2/2 honest; rev2 suggested running `extension add` in the user's project |
| | rev3 | **validate 2/2** | 5,255 | installer-oracle.rst (1 of 2) | 2/2 honest; offered the oracle commands; no claim of validation |
| K3 manage | orig / rev / rev3 | manage 3/3 | ~2,600–3,000 | assets | 3/3 |
| K4 publish | orig / rev | publish 2/2, manage 0 | ~1,680 | publishing.rst | 2/2 (m: rev pattern missed "can't PR") |

Notes:

- **P6 is a load failure, not a routing miss.** The Skill tool returned "Shell
  command permission check failed for pattern …: Permission to use Bash has
  been denied." Claude Code treats that syntax in a skill body as a command to
  run; with Bash allowed it would have run it. The answers were correct only
  because the model then read the file directly. rev2 loaded the body in 2/2
  runs with no permission error, and a contract test now forbids the pattern in
  these skills' bodies.
- **P4** shows the clearest content effect: the original skill, like the docs
  page it copied, produced code reading `structured_output`, which is always
  undefined against v1.18.33 (2/2). The revised skill produced the
  source-correct shape (2/2).
- **K2** was never a usable install test (no extension directory, no shell
  tool); it measured routing and honesty. No run in any version claimed a
  validation result. Routing moved to validate only after the manage handoff
  (rev3).
- The new `installer-oracle.rst` was read in 1 run; other changed references
  were read where the task needed them.

**Cost.** 52 `claude -p` runs, USD 9.04 in total (4.43 for the 13 discarded
denied-read runs, 4.61 for the 39 runs above). No `claude plugin eval` suite
was run.

## Tests

`tests/test_opencode_speckit_contracts.py` (12 tests) guards verified facts:
one SDK provenance owner, no denial of `createOpencodeServer`,
`info.structured`, the Go base URL, singular directories, `--auto`, bundle
routes, no shell-output pattern in skill bodies, the oracle contract, the
Rejects/Local labels, and Spec Kit compatibility naming the checked releases.
Before the edits, the first 11 tests produced 22 failing subtests (only the
route test passed). The shell-output test was added after P6; the original
`opencode-agent/SKILL.md` contains the pattern 3 times, so it fails there. All
pass after the edits.

## Rubric disagreements

- The Biggs test would cut the `(input, output)` table and the permission
  defaults as public docs. Kept: the docs mix handler keys with events, and the
  upstream pages disagree with each other (`lsp` granularity, `tools` gating)
  and with the source (structured output), so a fresh model copying the docs
  gets them wrong.
- The rubric's "pin versions in `compatibility:`" was applied as "name what was
  checked": no minimum OpenCode version was invented for config features.

## Dispositions

### #305 (OpenCode candidates; the other families belong to other agents)

| Candidate | Disposition | Evidence |
|---|---|---|
| Duplicate schema tables (skill and agent frontmatter vs verbatim references) | Retained with reason | SKILL.md tables carry the trap columns; references are dated verbatim pages |
| Policy JSON (inline allowlist vs `assets/policies.json`) | Retained with reason | The inline copy sits beside the rule-order trap it demonstrates (P3 2/2) |
| Tool catalogues and permission-key tables | Changed | Key vocabulary owned by policies; agent keeps a pointer; tools keeps the tool list |
| Examples and assets | Changed | `mcp.json` uses `permission`; `agent.md` trailing `*`; SDK assets corrected |
| Architecture prose (delegate diagram and skeleton) | Retained with reason | The diagram maps verbs and the skeleton is code; P5 used both |
| SDK provenance routing | Changed | Pins only in opencode-sdk; contract test |
| Config/permission traps, overloaded env/LSP keys, nonuniform defaults | Retained (corrected where stale) | P2 and P3 pass in both versions |
| SDK error/option behaviour | Separate factual fix | P4 0/2 → 2/2 |
| Drop-in rules and gating | Changed (gating corrected) | P7 1/1 in both; source check |
| Hook limitations (no `stop`, no `command.execute.after`) | Retained | P1 in both |
| Process-detachment requirements | Retained | P5 keeps `detached` + `unref()` in every run |
| Identifier verification | Separate factual fixes | Table above |
| Ownership wording | Changed | "SST's" removed; source repository named |
| Shell-output text in opencode-agent | Separate factual fix (new) | P6 |
| Companion skeleton leaves a failed job in `prompting` | Deferred with reason | Found by reading; needs a code change and a runnable test outside this review |

### #306

| Skill | Disposition | Chars | Evidence |
|---|---|---|---|
| opencode-tools | Changed | 830 → 397 | P2 routed 2/2 |
| opencode-agent | Changed | 698 → 367 | P6 routed 5/5 |
| opencode-delegate | Changed | 693 → 380 | P5 routed 3/3 |
| opencode-skill | Changed | 661 → 355 | P7 routed 2/2 |
| opencode-plugin | Changed | 626 → 396 | P1 routed 2/2; N1 and N2 negative 4/4 |
| speckit-manage | Changed | 323 → 398 | K3 3/3; K2 handed to validate 2/2 (rev3) |
| opencode-sdk, opencode-policies | Not candidates; neutral wording only | 640, 663 | P3 and P4 routed in every run |

### #307

| Candidate | Disposition | Evidence |
|---|---|---|
| speckit-validate oracle definition | Changed | SKILL.md section and `references/installer-oracle.rst` |
| Oracle execution | **Not run** | Permission policy refused the fetched installer (above) |
| Local conventions labelled separately from upstream rejection | Changed | K1 0/2 → 3/3 |

### #308

| Candidate | Disposition | Evidence |
|---|---|---|
| OpenCode: SDK owns SDK provenance | Changed | opencode-sdk `compatibility:` and provenance table |
| OpenCode: plugin APIs have their own requirements | Changed | Each skill's `compatibility:` names what was checked |
| OpenCode: neutral upstream ownership | Changed | Wording |
| OpenCode: remove copied pins from the hook | Deferred to #311 (hooks agent) | `hooks/opencode-doc-review.sh` still names the Go pin; it should route to opencode-sdk |
| Spec Kit: supported installer and schema versions | Changed | Tags listed in `compatibility:` and canonical-sources |
| Spec Kit: no inferred 0.12–1.0.x range | Changed | Version-specific rules marked; oracle not run |

## Limitations

- One model, one host, 1–3 runs per case.
- The installer oracle was not run; Spec Kit labels are read from source.
- The TypeScript and Go assets were checked against source by reading, not
  compiled or executed (building them would fetch dependencies).
- Upstream docs and source disagree in several places; this review follows the
  source at the named tags and says so in each skill.
- K2 had no extension directory and no shell, so it tests routing and honest
  reporting only.

## Open risks for other families

- Other skill bodies contain an exclamation mark followed by a backtick
  (conventional-commits, obsidian-bases, obsidian-markdown, redhat-setup).
  Whether Claude Code treats those as commands was not tested here.
- The opencode-doc-review hook (#311) still injects the Go SDK pin.

## Installer oracle follow-up (2026-09-29)

The previously blocked oracle now ran in the approved isolation at v1.0.12.
All 15 predicted install/rejection outcomes matched, including short-command
renaming and missing-file non-registration. Other tags and actual hook
dispatch remain source-only. See [the completion record](finish.md#spec-kit-oracle-307).

## Companion execution follow-up (#427)

The earlier review checked assets against upstream source without executing
them. Its content tests could not detect worker failures, SDK returned errors,
lost prompt results, concurrent store writes or cancellation races.

`tests/test_opencode_companion.py` now runs the actual canonical companion and
both generated Claude/Codex copies from temporary install paths with spaces.
A local SDK stub supplies rejected requests, returned SDK errors, assistant
permission errors, malformed responses and delayed creation/prompt completion.
No SDK download, live server, provider credentials or model calls are needed.
A delayed filesystem preloader exposes the parent/worker dispatch race, and
eight parallel detached tasks exercise shared-store updates and job IDs.

**TDD evidence (2026-09-29).** Before changing the asset, rejected creation and
prompt requests remained `running`/`prompting`; successful results lacked the
answer; delayed parent writes overwrote worker state; concurrent updates lost
jobs; and late success replaced cancellation. The initial executable regression
run failed. After the canonical fix and regeneration, all 19 tests pass against
all three copies, including cancellation before startup, during creation and
prompting, repeated cancellation, terminal-state protection, persisted abort
errors (including abort after a cancelled create), and preservation of server
selection and permission policy.

The companion initializes dispatch before spawning, retains `detached: true`
and `unref()`, serializes store/result updates under a bounded lock, and publishes
atomic JSON snapshots. Worker failure and actual prompt output are persisted
before terminal status. Cancellation is claimed before the abort request; an
in-flight create may return only to abort the new session without prompting it.

**Limits.** This is a skeleton, not a live OpenCode integration test. The harness
runs on the available Node.js 22 runtime; Node.js 18 is the documented minimum
but was not separately exercised. Forced process death, stale-lock recovery,
filesystem durability across power loss, remote-request timeouts and retention
remain deployment responsibilities. Server credentials and OpenCode permissions
are still supplied by the caller; the fix adds no approval bypass.
