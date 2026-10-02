Helper contracts
================

Resolve paths relative to this installed skill directory, not the checkout.
Set S to its scripts directory. All commands are ``bash "$S/pi-dispatch.sh"``
followed by the subcommand below. Invoke from the repository being dispatched.
No shell evaluation of issue text, config, model IDs or rendered prompts occurs.

State and defaults
------------------

Read optional user JSON config at
``${XDG_CONFIG_HOME:-$HOME/.config}/pi-dispatch/config.json`` with jq. Export its
approved model as MODEL, concurrency as PI_DISPATCH_CAP (default 2, range 1..32),
and optional stateDirectory as PI_DISPATCH_STATE_DIR. These helpers do not read
config themselves; the orchestrator must explicitly pass approved values.
The optional fast boolean defaults to false. Pass --fast only for an approved
Fast request; --no-fast on the workflow overrides a saved true default.
Read `Fast mode <fast.rst>`_ before checking catalog support or changing usage.

Absent an override, state is
``${XDG_STATE_HOME:-$HOME/.local/state}/pi-dispatch/<owner>--<repo>/`` derived from
``gh repo view``. Use the SAME state directory for all launchers of this repo,
including user-started workers. Do not override it per worktree or per wave:
that defeats the cap. Multiple clones need to share it if they share resources.
The cap is per repo, not a machine-wide limit; account for other repos manually.

Launch creates private directories/files with umask 077. Logs can contain
source and secrets from tools; do not upload them without reviewing/redacting.
Existing directory permissions are not silently changed: choose a private state
parent in setup. Do not place state inside the checkout.

Planning
--------

``resolve TARGET`` emits a JSON array. Whitespace-separated numbers/ranges may
be mixed; ``>=N`` and ``label:<name>`` are standalone filters of OPEN issues.
Explicit numbers also fetch closed issues for triage, never silently reopen.
Results are deduplicated. Filters stop with an error at 1000 results rather than
silently truncate; narrow the filter. Ranges are bounded to 1000 numbers.
``resolve --text TEXT`` forces one task, including text beginning with numbers.
Slugs are ASCII kebab-case, at most 48 characters; empty/colliding slugs need
user correction. Confirm the branch before creating anything.

The orchestrator fills classification, reason and paths in each unit. Valid
classifications are dispatchable, human-only, umbrella, blocked; untriaged is
not launchable. Inspect repository files/grep to supply path predictions; the
helper does not infer semantic triage. Empty paths mean unknown and overlap
with everything. Directory prefix overlap is supported; glob patterns are not.
Predict hand-written paths, including shared generators and config; exclude
outputs the repository's pipeline regenerates. Regenerate those after rebasing.
``waves PLAN.json`` emits the same units with wave numbers (null for skipped
units) and ``dependsOn`` lists of all earlier dispatchable branches whose paths
overlap. Skipped units have an empty list and never become predecessors. This
is direct path overlap, not inferred code dependencies or a transitive closure.
For example, five independent units at cap 2 have waves 1/1/2/2/3 but all have
``dependsOn: []``: later waves are cap-only and launchable when a slot opens,
without waiting for review/merge or every worker in an earlier wave to finish.
Every overlapping predecessor precedes the current unit in the advisory wave
packing; each wave holds at most the cap. This conservative, deterministic
packing is not a runtime scheduler. The orchestrator records a user-confirmed
strategy for each dependent unit: parallel-then-rebase (default for small,
understood overlap), stacked for actual code dependencies, or wait-for-merge
(default for heavy/unknown overlap or competing design decisions). Only the
last strategy requires merged predecessors before launch. User approval covers
selected units, strategies and bases before worktree/launch calls; the launch
helper does not enforce dependency eligibility.

Execution
---------

``worktree BRANCH [BASE]`` defaults to origin/main and invokes exactly
``wt switch --create BRANCH --base BASE --no-cd --no-hooks``. The created path
is resolved through Git porcelain, respecting Worktrunk's path template.
Existing branches/collisions or missing bases fail; do not clobber. Fetch origin
before creating launchable worktrees. No project hook approval is implied by
skipping create hooks; workers still run the repository's commit/push hooks.

For a confirmed stack, once the parent worker commits its implementation, use
``worktree issue-SECOND issue-FIRST`` (or a verified fetched parent ref), record
that parent commit, and set ``prBase: "issue-FIRST"`` on the child unit so its
PR targets the parent branch. Review changes to the parent may require a bounded
child follow-up; reconfirm material changes. Do not invent a multi-parent base.
After the parent merges, retarget the child PR to main and rebase only its own
commits onto updated origin/main using the recorded parent boundary (important
for squash merges). Workers still never merge.

``render UNIT.json WORKTREE`` reads the RST worker template, replaces fixed
markers literally, and appends the brief. Only dispatchable units render.
Issue units get a Closes directive; free text forbids it. Optional ``prBase``
defaults to main; stacked plans must explicitly select the parent PR branch.
The template directs workers to read repo rules instead of duplicating a
particular repo's pipeline.

``launch UNIT.json WORKTREE PROMPT MODEL --confirmed [--fast]`` validates the unit and
worktree branch, then acquires a directory lock and checks active recorded PIDs
against their process start time (Linux /proc boot ID + start ticks, otherwise
POSIX-host ps lstart; avoids PID reuse). It refuses if the cap is full, this
branch already runs, or any previous worker has no exit marker and an uncertain
process identity. Confirmation is a caller attestation, not a
runtime policy engine; do not call it before the user approves the plan.

A detached nohup Bash runner runs from WORKTREE with stdin /dev/null:
``pi -p --mode json --session-id SESSION --model MODEL --no-approve -- PROMPT``.
SESSION is issue-N or pi-slug (slash is invalid in pi 0.99.1). No --approve is
added implicitly. Trust-gated project resources are skipped; AGENTS.md still
loads. If required project extensions are missing, return the blocker rather
than granting trust. Global extensions remain active; review them in setup.

State files per session: .json metadata (PID/start time, branch, worktree, model,
repo, Fast flag/catalog and service_tier labelled priority (requested) or off),
.prompt, .jsonl stdout, .err stderr, .exit numeric runner result. Resuming
an exited unit archives these files with a timestamp suffix and reuses the pi
session in its original worktree. Do not move/delete pi's session storage while
follow-ups are pending. The lock is held only during launch, not the worker's
lifetime. A launch interrupted while holding the lock fails closed: inspect
processes and metadata before manually removing .launch-lock. Never clear it
while a launcher is active. If a runner is killed abruptly, status reports an
unknown exit code; new launches fail closed. Inspect children and logs before
manually archiving that unit's metadata to clear the unresolved state. Never
clear metadata while its worker or test descendants are still running.

Bounded rebase follow-up
------------------------

After overlapping predecessors merge with user authorisation, wait for the
child worker to exit and resume it in the SAME worktree via the same launch
command/unit/branch. The stable session ID reopens its history; archived logs
preserve the previous invocation. The ordinary cap and memory rules still apply.
Fast must be re-selected explicitly: omit --fast for normal usage, or pass it
only after renewed explicit selection of approved Fast usage/cost. Previous
metadata or session history does not enable Fast on a follow-up.

Write a short follow-up prompt rather than rerunning the full implementation.
Name the predecessor PRs/commits and existing child PR, constrain conflict
resolution to the confirmed scope, specify the repository's regeneration and
relevant validation commands, and stop on unexpected design conflicts. Example::

  Stay in <original worktree> on <child branch>, using existing PR <number>.
  Predecessor PRs <numbers> are merged. Read repo rules, require a clean tree,
  fetch origin and rebase onto origin/main. Resolve only confirmed overlap in
  <hand-written paths>; stop and report any new design decision. Regenerate
  derived outputs with <repo pipeline>, run <relevant validation> serially,
  and report exact results. Update only this PR and watch CI. Never merge,
  bypass hooks, change permissions, remove worktrees or run unapproved live checks.

For stacks, replace the plain rebase instruction with
``git rebase --onto origin/main <recorded-parent-commit>`` after verifying that
boundary, and retarget the PR to main. The prompt must explicitly include user
approval for any history-rewriting push: verify the expected remote head and
use a lease-protected push only to the child branch; never force unconditionally.
If approval, a clean tree or a safe boundary is missing, report the blocker
instead of guessing. Rebuild generated conflicts, do not hand-edit the outputs.

Observation
-----------

``status`` emits one JSON object with memory and workers, regardless of whether
the harness or user launched the helper. Running means a recorded PID still has
the same start time and no exit marker; exited does not mean successful. The
last five tool_execution_start events and model error/aborted messages are read
from the last 200 log lines. Partial/non-JSON lines are tolerated during writes.
Inspect the full private log for older activity/errors. The JSON agent_settled
event alone is not a process exit signal.

Each branch's most recent PR is queried with gh pr list; URL, state and CI checks
are reported via gh pr checks. Pending exit 8 and failed-check exit 1 retain
JSON results. No PR, no checks or gh/network failure is unknown, never green.
This helper does not merge or change GitHub state.

Linux memory uses MemAvailable and, when available, the cgroup v2 root limit;
under 10 percent remaining is HIGH. Nested cgroup layouts/platforms without
these files may be unknown or miss a narrower limit: inspect the OS/container
memory monitor as well. Memory status is advisory, not an OOM guarantee. Heavy
worker test descendants can use much more RAM than pi itself.
