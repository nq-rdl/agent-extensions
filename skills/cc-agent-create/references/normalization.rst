Importing an agent procedure
============================

Fetch the exact upstream source requested by the user. Preserve the source URL,
license, and copyright attribution. If the source cannot be retrieved, report
that limitation rather than inventing its contents.

Separate the reusable task from the host's agent registration:

* Put purpose, discovery metadata, essential constraints, and the direct workflow
  in SKILL.md. Merge with an existing owning skill when the task already exists.
* Put optional worker instructions in ``references/subagent.rst``. Convert Markdown
  headings, links, tables, and fenced examples to actual reStructuredText.
* Preserve operational invariants, output contracts, and authorization boundaries.
  Remove redundant persona boilerplate where it adds no task-specific value.
* Translate tool names into capability requirements; use the current host's tools.
  Do not carry VS Code tool namespaces or assume Claude-only calls work in Codex.
* Replace named-agent calls with links to the owning skill's delegation outline.
  Resolve companion skill paths explicitly; remove frontmatter preloads.
* Remove agent registration metadata such as ``model``, ``effort``, ``color``, and
  ``tools``. Retain necessary execution constraints in prose and have the host
  enforce permissions. Inherit the session model unless explicitly selected.

Delegation contract
-------------------

State this contract in the outline's return section, adapted to the task:

   Complete the delegated scope using available tools. If blocked by missing
   information or authorization, return the blocker and questions to the
   caller. Do not perform unauthorized actions. The caller may provide
   answers and resume the work.

Convert upstream dialogue with the user into questions returned to the caller;
a worker cannot reach the user directly. Keep verification loops that the task
needs, such as re-running a failing check after a fix. Do not add a one-turn or
no-loop rule: the host may resume a worker (Claude Code resumes a completed
subagent by ID or name with ``SendMessage``). Do not make the worker ask again
for authorization the user already gave for the delegated scope. A step that
needs the user's explicit approval, such as a destructive step, still runs in
the parent, as the outline's destructive-step rule states. Tool permissions are
a host setting and do not authorize an action.

Record adapted provenance in the reference. For a mixed-license owning skill,
keep the imported reference's own SPDX license and attribution instead of
relicensing it to match the entrypoint.
