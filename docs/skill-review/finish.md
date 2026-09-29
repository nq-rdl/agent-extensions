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

Attempted the approved `installer-oracle.rst` isolation on 2026-09-29: fresh
temporary HOME, XDG and uv directories; `env -i`; `/usr/bin:/bin` PATH;
`UV_NO_CONFIG=1`; `UV_PYTHON_DOWNLOADS=never`; `GIT_TERMINAL_PROMPT=0`;
the existing pixi Python; and the exact upstream tag `v1.0.12`.

`uv tool run --python <pixi-python> --from
git+https://github.com/github/spec-kit@v1.0.12 specify version` exited 1.
The nested git fetch exited 128: “Could not resolve host: github.com”.
Initialization and all 15 extension fixtures were **not run**. The EXIT trap
removed the temporary directory and confirmed `cleaned up`. No user project
was touched. Predictions remain source-derived, not installer observations.

## Last two delegation contracts (#310)

Added the existing Handoff contract to `data-request-triage` and
`se-technical-writer`, preserving scope, caller questions, existing
authorisation, destructive-step ownership and verification loops. Removed both
from `CONTRACT_PENDING`; no outlines remain exempt. After regeneration, all
21 delegation tests pass, including both target copies.
