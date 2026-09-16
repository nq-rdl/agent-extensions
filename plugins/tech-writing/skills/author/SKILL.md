---
description: Use when asked to technical writing tasks — developer docs, blog posts, tutorials, ADRs, and user guides — it adapts voice, structure, and depth to audience and content type.
license: MIT
metadata:
  upstream: https://github.com/github/awesome-copilot/blob/main/agents/se-technical-writer.agent.md
  repo: https://github.com/nq-rdl/agent-extensions
---

# Author

Identify the audience and requested document type, then draft from verified source material. Apply the tech-writing:copyedit skill to documentation, tutorials, guides, and ADRs, including its mandatory STE review. Keep the blog-specific style separate and report unresolved factual gaps.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the subagent outline,
handoff inputs, execution boundaries, and expected result. Read it when delegating
would help or the user asks to “create a subagent to execute this.” Otherwise,
work directly from this skill; the reference does not need to be loaded.
