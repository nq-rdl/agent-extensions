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
``waves PLAN.json`` emits the same units with wave numbers, or null for skipped
units. Every overlapping predecessor precedes the current unit; a wave holds
at most the configured cap. This is conservative and deterministic, not an
optimising scheduler. The user approves the plan before worktree/launch calls.

Execution
---------

``worktree BRANCH`` invokes exactly
``wt switch --create BRANCH --base origin/main --no-cd --no-hooks``. The created
path is resolved through Git porcelain, respecting Worktrunk's path template.
Existing branches/collisions fail; do not clobber. Fetch main in the orchestrator
before each wave. No project hook approval is implied by skipping create hooks.

``render UNIT.json WORKTREE`` reads the RST worker template, replaces fixed
markers literally, and appends the brief. Only dispatchable units render.
Issue units get a Closes directive; free text forbids it. The template directs
workers to read repo rules instead of duplicating a particular repo's pipeline.

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
