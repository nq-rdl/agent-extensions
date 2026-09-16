---
name: skill-report-issue
license: CC-BY-4.0
description: Report issues with skills to their upstream repository. Use when a skill
  produces errors, unexpected behavior, incorrect output, or fails silently. Also
  trigger when the user says things like "this skill is broken", "file a bug for this
  skill", "report this to the skill author", or when you notice a skill behaving incorrectly
  during normal use. Even if the user doesn't explicitly ask, offer to report the
  issue if you observe a clear skill defect.
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
shared procedure for duplicate search, diagnosis, draft approval, publication,
and failure handling. Discover the GitHub tools actually available in this host;
do not assume Claude-specific MCP tool names exist. Use `gh` with a body file
when no suitable integration is available. If neither route works, prepare the
manual report and state that it was not filed.

Present the complete destination, title, and body for the user's review before
publishing. Do not publish without the explicit confirmation required by the
shared procedure. An observed defect alone does not authorize filing an issue.
