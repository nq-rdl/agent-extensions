# Epic #312 completion record

## Baseline before follow-up edits (2026-09-29)

Starting revision: `a2364aa`, clean `epic/skill-review`. This record supplements
the family reports; historical hand-off sections describe their original state.

- TW-1: `se-technical-writer` says “Use when asked to technical writing tasks”
  and does not distinguish existing-prose copyediting in its description.
- TW-2: `tech-writing-copyedit` claims a blocking completion hook on every
  host. Its mandatory STE review must remain; only Claude Code has that hook.
- PA-2: Pandera compatibility names the 0.33.0 API baseline without the
  2026-09-29 verification on 0.33.0/0.33.1 already recorded in
  [new-plugins.md](new-plugins.md).
- Pixi: no compatibility, provenance or canonical-source guard. Installed
  `pixi --version` is 0.78.0. The 24 converted references remain in place.
- Delegation: removing the two names from `CONTRACT_PENDING` exposes missing
  Handoff contracts in both canonical outlines and four generated copies.
- Shell expansion: replacing the OpenCode-only guard with a test of every
  canonical entrypoint initially flagged five more skills. Combined red run:
  `pixi run python -m unittest tests.test_delegation_handoff.DelegationContract
  tests.test_skill_shell_expansion`: 6 tests, 11 failures (before edits).

That first guard was too broad: subsequent live probes distinguished command
openers from harmless inline code. The refined guard and results are recorded
below; the five harmless examples remain unchanged.

## Initial sandbox baseline

Before the session was restarted with full permissions, the shell could not resolve `api.github.com` or `github.com`. The GitHub connector
could read PR #320 and issues #304–#311. A bounded `claude -p` readiness probe
with the previous model (`claude-sonnet-5`), no tools, hooks disabled and no
session persistence timed out after 45 seconds with no result or stderr.
This was not a behavioural result and establishes no model cost. The initial
full unit run had 1,166 tests: a loopback-socket permission error, one failure
from an unnecessary Red Hat wording edit (since reverted), and two skips.
These results are superseded by validation after the restart.

## Spec Kit oracle (#307)

The first attempt failed DNS resolution in the restricted sandbox (uv exit 1,
git fetch exit 128) and cleaned up. After permissions were restored, the exact
isolated v1.0.12 oracle ran successfully, twice (the second run also inspected
registered skill paths): tag commit `e77daa9021d20db26b878f7dfa5640fe5a42d04e`,
Python 3.14.3, `version` and `init` exit 0. All 15 fixtures matched the predicted
installation/rejection outcome. Seven installed (exit 0), eight rejected
(exit 1); short-command printed its rename warning. The missing-file fixture
printed a provided-command entry but did not register the Claude skill. The
no-description fixture registered it. Unknown hook dispatch is still verified
only from source; the oracle never executed hooks or extension scripts.

Used a fresh temporary HOME, all three XDG directories, uv cache/tool dirs,
`env -i`, `/usr/bin:/bin` PATH, `UV_NO_CONFIG=1`,
`UV_PYTHON_DOWNLOADS=never`, `GIT_TERMINAL_PROMPT=0`, and fresh project and
extension copies per fixture. Cleanup confirmed after both runs. No user
project or configuration changed. Commands and outcomes are recorded in
`skills/speckit-validate/references/installer-oracle.rst`.

## Last two delegation contracts (#310)

Added the existing Handoff contract to `data-request-triage` and
`se-technical-writer`, preserving scope, caller questions, existing
authorisation, destructive-step ownership and verification loops. Removed both
from `CONTRACT_PENDING`; no outlines remain exempt. After regeneration, all
21 delegation tests pass, including both target copies.

## Shell-expansion regression guard (#307)

A temporary plugin tested Claude Code 2.1.284 with `Skill,Read` available and
Bash absent, hooks disabled, `--permission-mode dontAsk`, and model
`claude-sonnet-5`. A load-time denial is a local result (zero API turns and
zero model cost), not a model refusal. A successful load proceeds to the model.

| Form | Observed preprocessing |
|---|---|
| Raw command at body start | Bash permission denial |
| Command after a space, including indentation | Bash permission denial |
| Command inside a fenced block | Bash permission denial |
| Command inside a double-backtick span with an interior space | Bash permission denial |
| Command containing a newline | Bash permission denial |
| Escaped bang | Loaded |
| Bang preceded by a word character or opening parenthesis | Loaded |
| Inline bang code span followed by another code span | Loaded |
| Original bodies of obsidian-bases, obsidian-markdown, redhat-setup, rust-explain and conventional-commits | Loaded; no shell preprocessing denial |

The original five bodies therefore remain unchanged. Red Hat subsequently
reported unavailable fixture helpers, as expected: this was a load test, not
an authenticated Red Hat workflow. An early rerun accidentally changed the
plugin name without changing its invocation; those runs were discarded and
all forms and original bodies were rerun with matching names.

The test now recognises a whitespace/start-of-body command opener and allows
literal inline syntax. Its negative fixtures failed with the naive matcher
(3 tests, 10 failures), then passed with the corrected boundary. It scans every
canonical SKILL.md, replacing the OpenCode-only guard. Combined shell, OpenCode,
Spec Kit and delegation checks: 35 tests pass. The earlier opencode-agent fix
remains necessary; no additional triggering body was found.

## Remaining-work dispositions

All five required handover items are complete. The family reports retain the
original baselines, intermediate failures and final comparisons:

| Item | Final disposition | Evidence |
|---|---|---|
| 1: Rust and Pixi | Retain both reference trees; Pixi gains verified provenance and consumer command repairs | [Tools and docs](tools-docs.md) |
| 2: GitHub workflows | Four saved runs graded; changed cases repeated; corrected H1 fixture routes to Husky in 2/2 revised runs | [GitHub workflows](gh-workflows.md) |
| 3: New plugins | Author description, host-specific completion claim, Pandera verification date and last two handoff contracts corrected | [New plugins](new-plugins.md) |
| 4: Shell preprocessing | Live boundary probes and catalog-wide regression test; harmless inline examples retained | Above |
| 5: Installer oracle | Pinned isolated installer observed on all 15 fixtures, including registration inspection and cleanup | Above; [OpenCode and Spec Kit](opencode-speckit.md) |

The optional R/Shiny cases were not ported into `evals/claude/r/`; their
behavioural and executable evidence remains in the R/Shiny report.

Applied the checkout's `skills/skill-audit/SKILL.md` rubric directly. The final
Rust and Pixi decisions are **KEEP**. No critical finding remains in these
follow-up edits. The Pixi offline recipe corrects observed consumer failures,
its checked versions and canonical guard are explicit, and routing/packaging
checks pass. Rust deletion would not reduce observed loading. The rubric's
generic “could a fresh model write this → cut” rule is insufficient evidence
for deleting these references: selective loading and consumer outcomes govern
the decision. Pixi's unknown original snapshot and untested pages remain
documented maintenance limitations, not claims of current API coverage.

## Deferred work

Each handover deferral has a separate issue and acceptance criteria. No broad
rewrite or unverified runtime repair is folded into this completion:

| Follow-up | Decision and boundary |
|---|---|
| [#426: prompt-builder pilot](https://github.com/nq-rdl/agent-extensions/issues/426) | Retain the untested optional outline pending worker tasks. The handover's 594-line figure referred to this reference, not the 11-line SKILL.md body; the outline is now 606 lines. |
| [#427: OpenCode failure state](https://github.com/nq-rdl/agent-extensions/issues/427) | Fix rejected companion requests with an executable SDK stub and race coverage in a separate change. Current failed requests can leave persisted `running` / `prompting` state. |
| [#428: Obsidian duration arithmetic](https://github.com/nq-rdl/agent-extensions/issues/428) | Keep the existing formula until tested in a real application. Source and skill disagree; no application was available. #304 stays open because this is an explicitly required critical invariant. |
| [#429: Bash 3.2 CI coverage](https://github.com/nq-rdl/agent-extensions/issues/429) | Add pinned image/static-jq provisioning and assert no skips in CI. Both container test classes ran locally; that does not establish native macOS execution. |
| [#430: live Codex interaction](https://github.com/nq-rdl/agent-extensions/issues/430) | Verify interactive questions and review-model precedence separately. Existing stub/installed-runtime tests do not establish these live paths. |

#305–#311 have their candidate dispositions and scoped acceptance evidence in
the family reports; PR #320 proposes closure on merge. #304 and epic #312
remain open. No public skill was retired and no model-tier policy changed.

## Validation after the permissions restart

Run on the completed implementation on 2026-09-29; later edits only tidy this
evidence and the docs navigation. Push-hook and remote CI outcomes belong in
PR #320's current validation section.

| Check | Result |
|---|---|
| Full Python suite | 1,168 tests, OK, no skips; Podman Bash 3.2 fixtures and `BASH32_STATIC_JQ` supplied |
| Codex Node suite | 230 passed, no skips |
| Go validator | Build, vet and `go test ./...` pass; `asctl repo-check --size-report` validates 117 skills |
| Generated outputs | Plugin sync, manifests, bundles doc, eval graders and Codex directory checks pass; strict Codex package validation passes |
| Registry and packages | Bundle refs, exposure, grouping, consistency and plugin validation pass |
| Native Codex smoke | Local CLI 0.158.0: 38 plugins, 109 skills; installation, cache, removal and reinstallation pass. This is not a local run of CI's 0.152.0/0.154.0 matrix. |
| External skill links | 1,328 total: 1,191 OK, zero errors, 127 excluded, 10 unsupported; 107 redirects |
| Weekly monitor scan | 391 canonical inputs: 553 healthy, zero broken/unknown, 61 excluded. Report-only asset URLs include eight broken template URLs and one unknown (403); these are not canonical-link failures. |
| Tracker dry run | `GH_REPO=nq-rdl/agent-extensions` supplied; no changes planned, no tracker mutation |
| Docs build and whitespace | Zensical build and `git diff --check` pass |

The earlier sandbox run and the first tracker dry run without repository
context failed; their successful replacements are recorded above. Tests and
isolated workflows used disposable projects. Generated trees came from the
repository scripts; VERSION is unchanged and hooks were not bypassed.

## Cost and limits

The nine earlier family streams reported approximately USD 63. Recorded
follow-up result events total USD 6.21 (including discarded probe attempts),
approximately USD 69–70 overall. The follow-up includes 50 behavioural runs
plus load-time probes; zero-turn preprocessing denials cost zero. An early
timeout without a result has no recorded charge and is not scored as a pass.

Behavioural comparisons use Claude Code 2.1.284 and claude-sonnet-5 with small
samples, isolated plugins and disabled hooks. They establish the listed case
outcomes, not universal model reliability. The Spec Kit oracle did not execute
extension hooks/scripts; only v1.0.12 was executed. GDAL installation, all Pixi
reference examples, real Obsidian, live credentials and interactive Codex paths
were not tested in this follow-up. Historical family reports list their own
additional limitations.
