Subagent outline: data-request-triage
=====================================

Read this outline only when delegation is useful or the user requests a subagent.
It is a prompt reference, not an automatically registered agent. The main agent
may execute the skill directly without loading this outline.

Handoff
-------

Give each worker the request (ticket, enquiry and approval repository), its
ledger entry, the exact files and revisions to read, the stage skill to follow,
the permitted changes (repository, branch and worktree) and the return contract.
Pass this outline and the stage SKILL.md by resolved path, or include their text
if the worker cannot read them. Use the host's available subagent mechanism; do
not assume a named agent type exists. The worker follows the same authorisation
boundary as the parent; these instructions grant no additional permissions.

Required capabilities: Read, Grep, Glob and Bash for read-only work; Edit and
Write only for agreed co-development tasks. Map these names to the tools the host
provides; this list is guidance, not a runtime permission configuration.

Select models by capability
---------------------------

Choose from the models the host offers at run time, by the reasoning a task
needs:

* Use the strongest reasoning tier for gap planning, ambiguous requirements,
  library design, cross-repository review and the final review.
* Use a faster tier for bounded tasks with named inputs: scoping from listed
  files, copyedits and re-running a known check.

Name the tier in the plan, not a model family. Record the model that actually ran
each task in the ledger. If the host offers one model, run every task on it and
say so.

Disclose runtime limits
-----------------------

Before you plan, state which of these the session lacks: a subagent tool,
``add_repo`` or another way to bring a child repository into scope, native
Workflow execution, network access to GitHub, and write access to the child.
When a needed capability is unavailable, run the task directly, park it with the
reason, or hand the human a prompt to run elsewhere. Never report an unavailable
step as done.

Scope rules
-----------

* One writer per worktree and per branch. Run workers in parallel only on
  different repositories or on read-only tasks.
* Preserve branches that others own.
* In triage-only mode, workers are read-only and return text.
* Workers never merge, release, run extracts, run ``copier update``, bypass
  hooks or write to service-desk.
* Workers open PRs as drafts and attribute commits to the model that actually
  authored them.
* Keep hand-backs to about 800 words: paths, revisions and decisions, not file
  dumps.

Return and verification
-----------------------

Return the result, evidence as file, line and revision, changed paths, commands
run with their results, unresolved items and the model that did the work. The
parent rechecks every gap claim and every "missing" finding against current code
before accepting it: in September 2026 a worker reported a column missing from a
resolver that already had it. Do not delegate recursively unless the task says
so.
