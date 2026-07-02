<!-- Source: https://opencode.ai/docs/tools/ — fetched 2026-06-29. Canonical truth; verify here (and re-check the live page for drift) before authoring OpenCode tools code. -->

# Tools Documentation - OpenCode

## Overview

"Tools allow the LLM to perform actions in your codebase." OpenCode includes built-in tools and supports extensions through custom tools or MCP servers. By default, all tools are enabled without requiring permission.

## Permission Configuration

Control tool behavior using the `permission` field in `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "edit": "deny",
    "bash": "ask",
    "webfetch": "allow"
  }
}
```

Wildcards support multiple tools: `"mymcp_*": "ask"`

## Built-in Tools

| Tool | Function |
|------|----------|
| **bash** | Execute shell commands in project environment |
| **edit** | Modify existing files using exact string replacements |
| **write** | Create new files or overwrite existing ones (controlled by `edit` permission) |
| **read** | Read file contents from codebase |
| **grep** | Search file contents using regular expressions |
| **glob** | Find files by pattern matching |
| **lsp** | Code intelligence features (experimental; requires `OPENCODE_EXPERIMENTAL_LSP_TOOL=true`) |
| **apply_patch** | Apply patch files to codebase (controlled by `edit` permission) |
| **skill** | Load SKILL.md file content into conversation |
| **todowrite** | Manage todo lists during coding sessions |
| **webfetch** | Fetch and read web pages |
| **websearch** | Search web using Exa AI (requires `OPENCODE_ENABLE_EXA=1` or OpenCode provider) |
| **question** | Ask users questions during execution |

## Key Technical Details

- **apply_patch** uses `output.args.patchText` with relative paths embedded in marker lines
- **ripgrep** powers `grep` and `glob`, respecting `.gitignore` by default
- Create `.ignore` file to explicitly allow ignored paths: `!node_modules/`
- "todowrite is disabled for subagents by default"
