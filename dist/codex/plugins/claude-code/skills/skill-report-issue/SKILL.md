---
name: skill-report-issue
license: CC-BY-4.0
description: Report a defect in an installed skill to the skill's upstream GitHub
  repository. Use when a skill gives wrong instructions, errors, or fails silently,
  or when the user says "this skill is broken", "file a bug for this skill", or "report
  this to the skill author". Searches for duplicates, drafts one issue per problem,
  and files it when the user asks.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---
# Report Skill Issue

Report a failing installed skill to its upstream repository using the host's
available GitHub integration or authenticated `gh` CLI.

## Identify the installed skill

1. Identify the failing skill from the conversation, including its plugin and
   leaf name when available. If ambiguous, ask which skill the user means.
2. Use the resolved `SKILL.md` path from the loaded skill or the host's discovered
   skill catalog. Read that exact file. For plugin skills this is normally inside
   the installed plugin's `skills/<leaf>/` directory; it is independent of the
   user's working directory. Resolve relative catalog paths against their stated
   plugin/cache root. Do not assume `skills/<name>/SKILL.md` exists in the project
   or use the reporting skill's own metadata as the failing skill's repository.
3. If the path is not already known, inspect available skill-discovery results or
   plugin cache metadata to locate the installed skill. Only after discovery
   fails, ask for the installed skill path or upstream repository URL.
4. Parse the failing skill's YAML frontmatter and read `metadata.repo`. If it is
   absent, ask for the upstream repository rather than guessing. Preserve the
   qualified skill identity and installed version/commit when available for the
   report's environment section.

## Review and publish

Read and follow [references/reporting.rst](references/reporting.rst), the required
shared procedure for duplicate search, diagnosis, authorization, publication,
and failure handling. Discover the GitHub tools actually available in this host;
do not assume Claude-specific MCP tool names exist. Use `gh` with a body file
when no suitable integration is available. If neither route works, prepare the
manual report and state that it was not filed.

A user's request to file the report authorizes filing it; otherwise present
the complete draft and wait for explicit confirmation, as the shared procedure
states. An observed defect alone does not authorize filing an issue.
