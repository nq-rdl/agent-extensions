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
