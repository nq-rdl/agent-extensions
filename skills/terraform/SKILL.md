---
name: terraform
description: Terraform infrastructure specialist that generates compliant HCL using latest provider/module versions, manages HCP Terraform workspaces, orchestrates plan/apply workflows, and enforces security and formatting best practices.
license: MIT
metadata:
  upstream: https://github.com/github/awesome-copilot/blob/main/agents/terraform.agent.md
  repo: https://github.com/nq-rdl/agent-extensions
---

# Provision

Inspect provider and module versions, backend configuration, and the target workspace before generating HCL. Format and validate changes, inspect the plan for replacements or deletions, and keep apply within explicit user authorization. Verify provider APIs against the pinned versions’ official documentation.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the subagent outline,
handoff inputs, execution boundaries, and expected result. Read it when delegating
would help or the user asks to “create a subagent to execute this.” Otherwise,
work directly from this skill; the reference does not need to be loaded.
