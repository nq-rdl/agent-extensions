---
license: MIT
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
description: Dispatch confirmed GitHub issues or one free-text task to headless pi workers in Worktrunk worktrees. Use for Claude Code orchestration of implementation PRs, with triage, overlap waves, bounded concurrency and JSONL status; not for merging without authorisation or steering running workers.
compatibility: Verified pi 0.99.1 and wt 0.77.0; Bash 3.2+, jq >=1.6, Git and authenticated gh (CLI fields verified on 2.97.0). External pi provider credentials required.
user-invocable: true
argument-hint: "<numbers | N-M | >=N | label:name | free text>"
---

# Dispatch pi implementation workers

Verify correctness-critical flags against installed `pi --help`, `pi auth --help`
and `wt switch --help` and the [canonical Pi CLI](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli.md)
and [Worktrunk docs](https://worktrunk.dev/) before relying on them after upgrades.

## Plan first — no launches yet

1. If prerequisites or defaults are unknown, ask the user to run `/pi:setup`.
   Load approved defaults from `${XDG_CONFIG_HOME:-$HOME/.config}/pi-dispatch/config.json`
   as JSON with jq, **never source or eval it**. Missing config means ask for a
   verified model and state directory. Default cap is **2**, not the number of issues.
2. Read [helper contracts](references/helpers.rst) before using
   [pi-dispatch.sh](scripts/pi-dispatch.sh). Resolve the target from the repo:
   `bash "$S/pi-dispatch.sh" resolve "$TARGET"` (S is this skill's `scripts/`
   directory). Numbers, ranges, `>=N` and `label:<name>` resolve via gh; free text
   is **one unit**, branch `pi/<slug>`. Use `resolve --text "$TARGET"` to force text.
3. For issues, read the full issue and comments. Classify each unit:
   **dispatchable**, **human-only** (interactive UI, physical access or judgement
   unavailable to the agent), **umbrella** (tracking, not a bounded implementation),
   or **blocked** (dependencies, closed issue, missing scope or authorisation).
   Resolver output is deliberately `untriaged`; labels are clues, not authority.
   Explain the reason and questions for each skipped unit. Inspect `blockedBy`,
   linked dependencies, and acceptance criteria; do not dispatch unresolved blockers.
4. Predict touched paths from issue text **and a quick repository grep**. Set
   `paths` to repository-relative files or directory prefixes (no trailing slash).
   Include shared generators/configuration likely to change, not just the skill
   named in an issue. Unknown footprint `[]` serialises conservatively.
   Run `waves PLAN.json`; inspect the resulting overlap/cap schedule.
5. **Show every unit, classification/reason, predicted paths, branch, wave,
   model/thinking, state directory and cap. Ask the user to confirm exactly which
   units to launch.** Resolve slug collisions with the user. Issue branches are
   `issue-N`; free-text PRs have **no Closes line** and no new issue unless asked.
   Save only selected dispatchable units in the approved plan. Recompute waves
   if the selection, footprint, model or cap changes; reconfirm material changes.

## Execute one confirmed wave

Read [worker template](references/worker-prompt.rst) before rendering prompts.
Create worktrees only for the current confirmed wave, after `git fetch origin`
updates `origin/main`. Use `worktree BRANCH` (exact wt create/base/no-cd/no-hooks
contract). Later overlapping waves wait for earlier PRs to be **reviewed and
merged by the orchestrator with user authorisation**, then fetch updated main.
An exited worker or green CI is not permission to advance a dependent wave.

Extract each selected unit to UNIT.json; render it with
`render UNIT.json "$WORKTREE" > PROMPT`. Review the prompt, then call:

```bash
bash "$S/pi-dispatch.sh" launch UNIT.json "$WORKTREE" PROMPT "$MODEL" --confirmed
bash "$S/pi-dispatch.sh" status
```

The launcher enforces a per-repository cap under a lock, defaults to
`--no-approve` (no implicit project trust), and records PID, logs and exit code
independently of host harness tracking. Workers' memory-heavy test suites are why the
cap is two: do not raise it just because CPUs are idle. Inspect status memory
pressure before launching; at HIGH pressure stop launching and reduce the cap.
Do not launch parallel test suites in the orchestrator while workers test.

Claude Code auto-mode can deny `pi -p` as **Create Unsafe Agents**, even with a
permission rule. Do not disguise/retry the command to evade it. Explain the
risk and let the user launch the **same helper** with `!bash ... launch ...
--confirmed`, so PID/exit/log tracking and the cap still apply. Permission rules
and Worktrunk approvals are the user's decision; never apply them silently.

Print mode cannot steer a running worker. For an exited worker's CI follow-up,
write a bounded follow-up prompt and launch again from the **same worktree**;
the stable session ID resumes its history. `pi/<slug>` maps to `pi-<slug>` because
pi 0.99.1 rejects `/` in session IDs; issue-N is unchanged. Do not use `--name`
as a substitute for session identity. See helper contracts for resume logs.

## Review, authorised merge, cleanup

Workers open PRs, watch CI and never merge. Read the diff and acceptance criteria;
require green CI and repository reviews. An exit code 0 does not prove success
(JSON-mode model errors can still exit 0); inspect `errors`, logs and the PR.
Report judgement calls/deferred criteria under **Decisions for review**.
Only the orchestrator may merge, using repo strategy **after explicit user
authorisation**. Admin review bypass needs separate explicit session consent.
If merging is not authorised, return PR URLs and leave dependent waves pending.

After a merge, offer `wt remove` for finished worktrees; inspect `git status
--porcelain` first and never remove uncommitted work or a running worker's tree.
Retain private state/logs unless the user approves deletion. RPC steering and
Codex-hosted orchestration beyond native skill packaging are follow-ups, not MVP
capabilities. A worktree is a scope convention, **not a sandbox**.
