---
name: build-mcp
description: Use when asked to authoring or reviewing Go MCP servers; it applies official
  github.com/modelcontextprotocol/go-sdk patterns, type-safe structs, context handling,
  and idiomatic Go conventions throughout.
license: MIT
metadata:
  upstream: https://github.com/github/awesome-copilot/blob/main/agents/go-mcp-expert.agent.md
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Delegation is optional. Read references/subagent.rst only when delegation is useful or requested. It does not install a named agent or grant permissions.

# Build Mcp

Inspect the project’s Go SDK version and transport before changing an MCP server. Use typed tool inputs and outputs, propagate context cancellation, and test handlers and failure paths. Verify API details against the official github.com/modelcontextprotocol/go-sdk source for that version.

## Optional delegation

[references/subagent.rst](references/subagent.rst) contains the subagent outline,
handoff inputs, execution boundaries, and expected result. Read it when delegating
would help or the user asks to “create a subagent to execute this.” Otherwise,
work directly from this skill; the reference does not need to be loaded.
