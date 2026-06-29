<!-- Source: https://opencode.ai/docs/permissions/ — fetched 2026-06-29. Canonical truth; verify here (and re-check the live page for drift) before authoring OpenCode permissions code. -->

# Permissions (OpenCode)

## Overview

OpenCode uses permission configuration to control whether actions run automatically, require approval, or are blocked. The system resolves each permission rule to one of three states:

- `"allow"` — execute without approval
- `"ask"` — prompt user for approval
- `"deny"` — block the action

## Configuration Structure

### Global and Tool-Specific Permissions

Permissions can be set globally using `"*"` and overridden for specific tools:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "*": "ask",
    "bash": "allow",
    "edit": "deny"
  }
}
```

Alternatively, set all permissions uniformly:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": "allow"
}
```

## Granular Rules (Object Syntax)

Most permissions support object-based rules that apply different actions based on tool input:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "bash": {
      "*": "ask",
      "git *": "allow",
      "npm *": "allow",
      "rm *": "deny",
      "grep *": "allow"
    },
    "edit": {
      "*": "deny",
      "packages/web/src/content/docs/*.mdx": "allow"
    }
  }
}
```

**Evaluation Rule:** Last matching pattern wins. Place catch-all `"*"` first, then more specific rules.

### Wildcard Matching

- `*` — zero or more characters
- `?` — exactly one character
- All other characters match literally

### Home Directory Expansion

Patterns support `~` or `$HOME` at the start:

- `~/projects/*` → `/Users/username/projects/*`
- `$HOME/projects/*` → `/Users/username/projects/*`
- `~` → `/Users/username`

### External Directories

The `external_directory` permission allows tool calls affecting paths outside the project working directory. This applies to tools accepting path inputs (read, edit, glob, grep, bash commands):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "external_directory": {
      "~/projects/personal/**": "allow"
    }
  }
}
```

Allowed directories inherit workspace defaults. Add explicit denial rules when restricting specific tools:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "external_directory": {
      "~/projects/personal/**": "allow"
    },
    "edit": {
      "~/projects/personal/**": "deny"
    }
  }
}
```

## Available Permissions

- `read` — reading files (matches file path)
- `edit` — file modifications (covers edit, write, patch)
- `glob` — file globbing (matches glob pattern)
- `grep` — content search (matches regex pattern)
- `bash` — shell command execution (matches parsed commands)
- `task` — launching subagents (matches subagent type)
- `skill` — loading skills (matches skill name)
- `lsp` — running LSP queries (non-granular)
- `question` — asking users during execution
- `webfetch` — URL fetching (matches URL)
- `websearch` — web search (matches query)
- `external_directory` — triggered when tools access paths outside project
- `doom_loop` — triggered when same tool repeats 3 times with identical input

## Default Permissions

```json
{
  "permission": {
    "read": {
      "*": "allow",
      "*.env": "deny",
      "*.env.*": "deny",
      "*.env.example": "allow"
    }
  }
}
```

- Most permissions default to `"allow"`
- `doom_loop` and `external_directory` default to `"ask"`
- `.env` files are denied by default

## "Ask" Behavior

When OpenCode prompts for approval, three outcomes are available:

- `once` — approve only this request
- `always` — approve future matching requests (current session only)
- `reject` — deny the request

Tools provide suggested patterns for `always` approval (e.g., bash suggests command prefixes like `git status*`).

## Agent-Level Overrides

Agent permissions override global configuration. Agent rules take precedence:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "bash": {
      "*": "ask",
      "git *": "allow",
      "git commit *": "deny",
      "git push *": "deny",
      "grep *": "allow"
    }
  },
  "agent": {
    "build": {
      "permission": {
        "bash": {
          "*": "ask",
          "git *": "allow",
          "git commit *": "ask",
          "git push *": "deny",
          "grep *": "allow"
        }
      }
    }
  }
}
```

Markdown-based agent permissions:

```yaml
---
description: Code review without edits
mode: subagent
permission:
  edit: deny
  bash: ask
  webfetch: deny
---
Only analyze code and suggest changes.
```

**Note on pattern matching:** Commands with arguments require explicit patterns. `"grep *"` permits `grep pattern file.txt`, while `"grep"` alone blocks it.
