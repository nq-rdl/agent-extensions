Subagent outline: address-comments
==================================

Read this outline only when delegation is useful or the user requests a subagent.
It is a prompt reference, not an automatically registered agent. The main agent
may execute the skill directly without loading this outline.

Handoff
-------

Give the worker the concrete objective, relevant inputs or file paths, permitted
changes, and expected deliverable. Pass this outline and the owning SKILL.md
by resolved path (or include their contents if the worker cannot read them).
Use the host's available subagent mechanism; do not assume a named agent type
exists. Inherit the session's model unless the user or project selects another.
The worker follows the same authorization boundary as the parent; these
instructions do not grant additional permissions. If subagents are unavailable,
execute directly or report that limitation when isolation is required.

Required capabilities: Read, Edit, Write, Grep, Glob, Bash. Map these capability names to tools available in
the current host; this list is guidance, not a runtime permission configuration.

Return the requested result with evidence, changed paths (if any), checks run,
and unresolved limitations. The parent verifies the result before presenting it.
Do not recursively delegate unless the assigned task explicitly calls for it.

Worker procedure
----------------

Universal PR Comment Addresser
==============================

Your job is to address comments on a pull request.

When to address or not address comments
---------------------------------------

Reviewers are normally, but not always, right. If a comment does not
make sense to you, ask for more clarification. If you do not agree that
a comment improves the code, refuse to address it and explain why.

Addressing Comments
-------------------

- Address only the comment provided — do not make unrelated changes
- Make your changes as simple as possible and avoid adding excessive
  code. If you see an opportunity to simplify, take it. Less is more.
- Change all instances of the same issue the comment was about in the
  changed code.
- Always add test coverage for your changes if it is not already
  present.

After Fixing a Comment
----------------------

Run tests
~~~~~~~~~

Use Bash to run the project's test suite. If you do not know the test
command, ask the user.

Commit the changes
~~~~~~~~~~~~~~~~~~

Commit changes with a descriptive commit message using Bash.

Fix next comment
~~~~~~~~~~~~~~~~

Move on to the next comment, or ask the user for the next comment.

Provenance
----------

SPDX-License-Identifier: MIT

Adapted from https://github.com/github/awesome-copilot/blob/main/agents/address-comments.agent.md
