Importing an agent procedure
===========================

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

Record adapted provenance in the reference. For a mixed-license owning skill,
keep the imported reference's own SPDX license and attribution instead of
relicensing it to match the entrypoint.
