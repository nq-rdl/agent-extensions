# Hook packaging and portability review (#311)

This record covers both work packages of issue #311 (part of epic #312):
**A** — canonical hook packaging and installed behaviour, and **B** —
portability and scoped cleanup. The inventory, tasks, and invariants below
were recorded **before** any hook, sync, or test change, at source revision
`43de0df` (branch `epic/skill-review`).

Host: Linux 5.14 (RHEL 9), GNU bash 5.1.8, jq 1.6, Node.js 22.23.1,
Python 3.14.3 (pixi). The macOS-compatible run used the
`docker.io/library/bash:3.2` image (bash 3.2.57, BusyBox `grep`/`sed`, no
`jq`, no `python3`) under Podman.

## Baseline inventory (at `43de0df`)

"Claude parity" means that `scripts/sync-plugins.sh --check` fails when the
installed copy differs from the canonical source.

| Canonical hook | Bundle | Claude installed copy | Claude config source | Claude parity | Codex copy |
|---|---|---|---|---|---|
| `codex-session-lifecycle` | codex | `plugins/codex/scripts/` | hand-edited `plugins/codex/hooks/hooks.json` | **none** | not shipped (Codex uses `adapter.sh codex-context`) |
| `codex-stop-review-gate` | codex | `plugins/codex/scripts/` | hand-edited | **none** | not shipped |
| `codex-defect-report` | codex | `plugins/codex/scripts/` | hand-edited | **none** | not shipped |
| `skill-audit-nudge` | claude-code | `plugins/claude-code/scripts/` | hand-edited | **none** | `dist/.../hooks/` (checked) |
| `opencode-doc-review` | opencode-dev | `plugins/opencode-dev/scripts/` | hand-edited | **none** | checked |
| `redhat-docs-preflight` | redhat | `plugins/redhat/scripts/` | hand-edited | test-only byte check (`test_redhat_hooks.py`) | checked |
| `redhat-docs-guard` | redhat | `plugins/redhat/scripts/` | hand-edited | test-only byte check | checked |
| `speckit-publish-target` | speckit-dev | `plugins/speckit-dev/scripts/` | hand-edited | **none** | checked |
| `data-request-preflight` | data-request | `plugins/data-request/hooks/` | canonical `hooks/data-request/hooks.json` | sync `--check` (bytes only) | checked |
| `data-request-guard` | data-request | `plugins/data-request/hooks/` | canonical | sync `--check` (bytes only) | checked |
| `stylepedia-reminder` | tech-writing | `plugins/tech-writing/hooks/` | canonical `hooks/tech-writing/hooks.json` | sync `--check` (bytes only) | checked (inline adapter mode) |
| `changie-fragment-lint` | — (`registry/unbundled.yaml`) | none | `hooks/changie-fragment-lint.json` (repo-relative) | n/a | n/a |
| `hooks/codex/adapter.sh` | every Codex hook bundle | n/a | n/a | n/a | copied by `codex_package.py`, checked incl. mode |

All eleven shipped copies were byte-identical to `hooks/` at the baseline;
the gap is that nothing prevents drift for eight of them. The Codex side
(`codex_package.py --check`) already compared whole trees, including the
executable bit.

Runtime dependencies that live outside `hooks/`:

| Hook | Dependency | Resolved via |
|---|---|---|
| `codex-*` wrappers | `scripts/{session-lifecycle,stop-review-gate,defect-report}-hook.mjs` (vendored runtime) | `${CLAUDE_PLUGIN_ROOT}/scripts/` |
| `redhat-docs-preflight`, `redhat-docs-guard` | `skills/fetch-docs/scripts/rh-preflight.sh` → sources `rh-lib.sh` | `${CLAUDE_PLUGIN_ROOT}`, then `$(dirname "$0")/..` |
| `data-request-preflight`, `data-request-guard` | `skills/setup/scripts/sqlreview.sh` (+ `release.sh`, `sqlreview-identity.jq`) | `${CLAUDE_PLUGIN_ROOT}`, then `$(dirname "$0")/..` |
| every Codex hook | `hooks/adapter.sh` | `${PLUGIN_ROOT}` |

No canonical `hooks/*.sh` file is sourced by another hook; the
`*-preflight.sh` hooks are independent `SessionStart` hooks. The former
`sql-review-*` hooks were renamed to `data-request-*` in `c00f4e3`.

Baseline suites: `python3 -m unittest discover -s tests` — 1037 tests, OK;
`node --test tests/codex/*.test.mjs` — 223 tests, 223 pass.

## Tasks and invariants (recorded before changes)

### Work package A

| ID | Invariant |
|---|---|
| A-1 | Every hook-bearing bundle has one canonical Claude config under `hooks/<plugin>/hooks.json`; the packaged `plugins/<plugin>/hooks/` directory is generated from it. |
| A-2 | The destination of each hook script is read from the canonical config (`${CLAUDE_PLUGIN_ROOT}/<dir>/<name>.sh`). Every registry hook is wired at least once; every wired script is a registry hook. Install paths do not move. |
| A-3 | `sync-plugins.sh --check` fails on a stale, missing, content-drifted, or mode-drifted hook copy, and on a hook copy left in a legacy location. Vendored files next to hook copies (for example `plugins/codex/scripts/*.mjs`) are never pruned. |
| A-4 | Every `${CLAUDE_PLUGIN_ROOT}/…` path a packaged hook names resolves inside its own plugin tree (Claude and Codex). |
| A-5 | Hook commands survive a plugin root that contains spaces. |
| A-6 | A copy of only the plugin directory, run from an unrelated working directory whose path contains spaces, works with no access to this checkout: stdin is forwarded, the child exit status is preserved, executable bits are kept, and missing, old, or unparseable Node produces the exact preflight message. |
| A-7 | The Red Hat guard still denies a gated Portal fetch when `rh-preflight.sh` (or its sourced `rh-lib.sh`) is missing and no credential exists, and still allows it when an environment or file credential exists. No source error, no bypass. |
| A-8 | Existing skill packaging, Codex suites, and Red Hat suites stay green. |

### Work package B

| ID | Invariant |
|---|---|
| B-1 | The OpenCode route list names exactly the `opencode-dev` bundle leaves. |
| B-2 | The OpenCode hook carries no copied SDK version pin; it routes to `/opencode-dev:sdk` as the owner. |
| B-3 | Without `jq` and `python3`, the OpenCode and Spec Kit fallbacks still fire on bash 3.2 with non-GNU `grep`/`sed` and stay silent otherwise. |
| B-4 | The dormant changie hook is either removed with its allowlist entry or retained under the current event contract and changie policy (200-character body cap). The obsolete 20-word rule does not survive. |
| B-5 | A shared Node preflight is extracted only if it lowers risk; otherwise the single owned minimum is enforced by a test. |
| B-6 | Advisory hooks (OpenCode, Spec Kit, skill-audit nudge, Stylepedia) have fire, no-fire, malformed-input, and event-specific output tests. `hookSpecificOutput` is required only where the event uses it. |

## Sources

Retrieved 2026-09-29:

- Claude Code hooks reference, https://code.claude.com/docs/en/hooks
  (`hooks.md`). Shell form: "The equivalent shell form needs quoting to
  handle paths with spaces or special characters". Both forms export
  `CLAUDE_PLUGIN_ROOT` to the spawned process. `UserPromptSubmit` input carries
  `prompt`; plain stdout and `hookSpecificOutput.additionalContext` both add
  context. For `PreToolUse`, top-level `decision`/`reason` "are deprecated
  for this event"; use `hookSpecificOutput.permissionDecision`. For
  `PreToolUse`/`PostToolUse`, plain stdout goes only to the debug log.
- Changie v1.26.0 (local CLI) and `.changie.yaml` (`body.maxLength: 200`).
- Issue #187 (closed; read-only `gh issue view`). It asked for fragment YAML
  validation. `scripts/check_changie_length.py` and its test
  `test_malformed_yaml_flagged` do this. This review does not claim more
  than that for #187.

## Changes and results

### A — canonical mapping (`ad6f94a`)

The mapping is **explicit and config-driven**, so no registry schema change
was needed:

- **Canonical config:** `hooks/<plugin>/hooks.json` for all seven hook bundles.
  Five are new: `claude-code`, `codex`, `opencode-dev`, `redhat`, and
  `speckit-dev`. The `codex` plugin's file is `hooks/codex/hooks.json`, beside
  the Codex adapter directories. Its name is the plugin name. It is not a
  Codex adapter config. The generated file is `plugins/<plugin>/hooks/hooks.json`.
- **Hook list:** the bundle's `hooks:` array.
- **Destination:** the quoted `${CLAUDE_PLUGIN_ROOT}/<dir>/<name>.sh` path in
  the config command. `plugins/<plugin>/hooks/` is owned as a whole tree.
  `plugins/codex/scripts/` and the other `scripts/` directories are owned file
  by file. Vendored `.mjs` runtime files there are never touched.
- **Runtime dependencies:** each `${CLAUDE_PLUGIN_ROOT}/…` path in a hook
  must resolve to one of three targets. The first is a mapped hook. The second
  is `skills/<leaf>/…`, checked through the registry leaf-to-source map. The
  third is a vendored file already in the plugin tree.
- **Codex target:** unchanged. `codex_package.py --check` already compared
  whole trees, including the executable bit. `hooks/codex/adapter.sh` stays a
  target helper, and `check_exposure.py` now documents why it is not a hook
  identity (`test_nested_target_helpers_are_not_hooks`).

Install paths do not move. The only content change to generated files was
the quoted commands. `sync-plugins.sh --check` already runs in CI (the
`validate-bundles` job, step "Check plugin trees match canonical skills/")
and in the lefthook `generated-in-sync` job, so no job or check name changed.

Drill on the real tree after the change:

```text
$ chmod -x plugins/codex/scripts/codex-defect-report.sh; sync-plugins.sh --check
  - plugins/codex/scripts/codex-defect-report.sh: content or executable mode differs from hooks/codex-defect-report.sh
$ echo '# drift' >> hooks/skill-audit-nudge.sh; sync-plugins.sh --check
  - plugins/claude-code/scripts/skill-audit-nudge.sh: content or executable mode differs from hooks/skill-audit-nudge.sh
```

The pre-change Claude side had no such check. `codex_package.py --check`
passed (exit 0) with two edits applied together. One was a canonical-only edit
to `hooks/codex-defect-report.sh`: the Codex runtime copy is compared with
`plugins/codex/scripts/`, not with `hooks/`. The other was an edit to the
Claude copy `plugins/claude-code/scripts/skill-audit-nudge.sh`: the Codex copy
is built from `hooks/`. A canonical edit to a hook shipped to both targets was
caught only indirectly, through its Codex copy. The Red Hat byte test covered
only its own two hooks.

### A — installed runtime (`910c24e`)

A real gap was found: every non-`tech-writing` config used an unquoted
`${CLAUDE_PLUGIN_ROOT}/…` command. With the installed plugin under a path that
contains spaces, the shell splits it:

- the new wrapper tests failed 5/22 against the pre-change `plugins/codex/hooks/hooks.json`,
  for both shell expansion and textual substitution;
- `test_unquoted_plugin_root_breaks_under_spaces` keeps a live demonstration.

After quoting, the following suites pass. None reads this checkout at hook
run time.

- `tests/codex/hook-wrappers.test.mjs` (+7 tests). It copies only
  `plugins/codex` to `…/plugin cache/codex` and runs from an unrelated cwd
  with `PATH` holding only a fake `node`. Each installed command is run with
  `/bin/sh -c`. The tests prove that each wrapper keeps its executable bit
  and execs the `.mjs` inside the installed copy. They also prove that stdin
  arrives, that exit status 7 passes through, and that missing, 18.17, and
  unparseable Node each print the exact preflight message with exit 1.
- `tests/test_installed_hooks.py` (21 tests). The same isolation applies for
  `claude-code`, `opencode-dev`, `redhat`, `speckit-dev`, `data-request`, and
  `tech-writing`. `RH_*`/`BW_*` are stripped, HOME is temporary, credential
  sources are `env,file`, and no network is used.
- Red Hat fallback (A-7) passed **before and after** without code changes, so
  the behaviour is retained with evidence. The installed copy was tested in
  four states. With `rh-preflight.sh` present, the gated Portal fetch is
  denied without a credential. With it deleted, the fetch is denied without
  a credential and allowed with an env or 0600-file credential. With the
  sourced `rh-lib.sh` deleted, the fetch is still denied (fail closed; no
  stderr source error). Without `CLAUDE_PLUGIN_ROOT`, the guard resolves the
  companion relative to itself. The SessionStart preflight is a silent no-op
  without the companion.

### B — portability and cleanup (`910c24e`, `65c9295`)

| Test (fail before → pass after) | Before |
|---|---|
| `OpenCodeRoutes.test_no_copied_version_pin` | copied `Go SDK v0.19.2, Go 1.22+` and stale `forced-eval-hook.sh` comment |
| `PromptAdvisoryHooks.test_malformed_input_is_a_silent_noop` | OpenCode exited 5 (jq parse error under `set -e`) on `not json` and `[]` |
| `…test_without_jq_the_fallbacks_still_gate` (escaped quote in prompt) | both sed/grep scrapes stopped at the first `\"`, so a later marker was missed |
| `Bash32BusyBoxFallback` (OpenCode) | `grep -oP` is absent in BusyBox (exit 2), so the no-jq fallback **never fired** |
| `RedHatGuardFallback.test_sso_ask_makes_no_fixed_token_lifetime_claim` | "caches the 15-minute access token" |

The OpenCode `grep -oP` fallback passed on the Linux host, because GNU grep
has `-P`. It failed only in the BusyBox container. Host-only testing would
have missed it.

**macOS-compatible run, stated exactly:** Podman image
`docker.io/library/bash:3.2` (digest
`sha256:ae50c35ff361cd17a9c6cc4ee045b44a7778c4e2bf66def577752403c446c810`),
bash 3.2.57 (the version macOS ships as `/bin/bash`), BusyBox v1.37.0
`grep`/`sed`/`tr` (no `grep -P`), no `jq`, no `python3`, `--network=none`.
Both prompt hooks fired on a matching prompt, including one with escaped
quotes, and stayed silent otherwise. The run is in
`tests/test_installed_hooks.py::Bash32BusyBoxFallback`, which is skipped
unless Podman and that image are present locally, so CI does not run it.
BSD `sed` and BSD `grep` themselves were **not** run: BusyBox is a non-GNU
POSIX stand-in, not macOS. The expressions use only POSIX ERE (`sed -E`,
bracket expressions, `[[:space:]]`), which BSD `sed` documents. On the host,
the same fallbacks are also run with `python3` present and with neither
`jq` nor `python3` on a restricted `PATH`.

## Per-issue disposition (#311)

| Candidate | Disposition | Evidence |
|---|---|---|
| A1 inventory of hooks, destinations, sourced helpers, skill-relative dependencies | changed (recorded) | Baseline inventory above; no `hooks/*.sh` is sourced; `sql-review-*` renamed to `data-request-*` in `c00f4e3` |
| A1 explicit canonical mapping without copying unrelated runtime or pruning vendored content | changed | `sync_hooks` in `scripts/sync-plugins.sh`; `test_scripts_destination_keeps_vendored_files_and_checks_mode` |
| A1/A2 helper exposure classification | changed (documented + test) | `check_exposure.py` docstring; `test_nested_target_helpers_are_not_hooks`; a top-level `hooks/*.sh` must be wired (`test_listed_hook_must_be_wired`) |
| A2/A3 deterministic regeneration, `--check` fails on stale or missing copies | changed | `tests/test_hook_packaging.py` (14 tests; 17 failures and 1 error before the change); drill above |
| A3 document the supported command | changed | CONTRIBUTING.md "Bundled hooks" |
| A4 isolated installed runtime: stdin, exit status, exec bits, spaces, Node missing/old/unparseable, sourced loading | changed (tests + quoting fix) | `tests/codex/hook-wrappers.test.mjs` (5 of 22 failed on old config); `tests/test_installed_hooks.py` |
| A5 Red Hat fallback without companion library/preflight | retained with evidence | `RedHatGuardFallback` (8 tests, pass before and after) |
| B OpenCode route set vs bundle leaves | retained with evidence | 7 routes = 7 leaves; `test_route_list_matches_bundle_leaves` |
| B OpenCode copied SDK pin | changed | Pin removed; routes to `/opencode-dev:sdk`, which carries `v0.19.2` / Go 1.22+ in `skills/opencode-sdk/SKILL.md` (coordination with #308: skill not edited) |
| B OpenCode fallback parsing on macOS-compatible tooling | changed | `grep -oP` replaced by a tested POSIX `sed -E` scrape; container run above |
| B stale source-path comments | changed | `forced-eval-hook.sh` and "AGENTS.md safe-context-injection" references now point at `claude-code:hook` `references/prompt-injection.rst` |
| B changie-fragment-lint | obsolete — removed in `65c9295` | Nothing wired it (`.claude/` removed; no reference in lefthook or CI). Its 20-word rule is obsolete. Its `decision: block` output is deprecated for `PreToolUse`, and its `context` key is undocumented. `check_changie_length.py` enforces the current policy. `registry/unbundled.yaml` is now empty |
| B Codex shared Node preflight extraction | deferred with reason — not extracted | Sourcing a shared file from `#!/bin/sh` wrappers would add a path-resolution failure mode at every hook start. The three copies are byte-identical, and a new test enforces identical bodies and the single 18.18 minimum. First-use diagnostics are unchanged |
| B Red Hat shared credential-path logic | retained with reason | The inline fallback exists for when `rh-lib.sh` is unavailable, so sourcing it would defeat the fallback. A parity test pins the default token path to `rh-lib.sh` |
| B Red Hat decorative token-lifetime claim | changed | "15-minute" removed; `rh-token.sh` caches until the SSO-reported `expires_in` (fallback 900 s) |
| B advisory fire/no-fire + event schema tests | changed | OpenCode, Spec Kit (UserPromptSubmit), and skill-audit nudge (PostToolUse) in `test_installed_hooks.py`; Stylepedia already covered by `test_stylepedia_hook.py` (PreToolUse + UserPromptExpansion) and the Codex adapter tests |
| Wire parity into validators without renaming checks | changed | Extends the existing `sync-plugins.sh --check` and unit-test jobs; no workflow file edited |

## Behavioural model runs and cost

None were run, and paid model spend is **USD 0**. Every changed artefact is a
deterministic shell hook or packaging script. The behaviour under test
(stdout JSON, exit status, and files on disk) is fully observable without a
model, and the tests above observe it directly. A model run would test Claude
Code's hook loader, not this repository.

## Validation (final)

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests -p 'test_*.py'` | 1073 tests, OK (baseline 1037) |
| `node --test tests/codex/*.test.mjs` | 230 pass, 0 fail (baseline 223) |
| `validate-plugins.sh`, `sync-plugins.sh --check`, all `--check` generators, `check_*` scripts, `check_changie_length.py` | pass |
| `asctl repo-check` | pass |
| `scripts/smoke-codex-marketplace.sh` | pass (local `codex` CLI) |

## Limitations

- Real BSD `sed`/`grep` and a macOS host were not available. See the
  container description above.
- The spaces fix follows the documented shell-form quoting rule and was
  exercised with `/bin/sh -c`, both with shell expansion and with textual
  substitution. It was not observed inside a running Claude Code session.
- `tests/test_sql_review_plugin.py::test_hooks_json_wires_both_scripts` pins
  the exact data-request command strings. It was updated to the quoted form,
  which may conflict with parallel data-request work.
