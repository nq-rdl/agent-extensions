<!-- Source: https://opencode.ai/docs/policies/ — fetched 2026-06-29. Canonical truth; verify here (and re-check the live page for drift) before authoring OpenCode policies code. -->

# Policies (OpenCode)

## Overview

Policies control which configured resources OpenCode may use. They are configured via the `experimental.policies` array in `opencode.json` and function separately from permissions — permissions govern tool capabilities during sessions, while policies regulate resource access like LLM providers.

## Configuration Structure

Each policy statement requires three fields:

- **`effect`** — `"allow"` or `"deny"`
- **`action`** — The operation being controlled
- **`resource`** — Resource ID or wildcard pattern

### Example: Deny OpenAI Provider

```json
{
  "$schema": "https://opencode.ai/config.json",
  "experimental": {
    "policies": [
      {
        "effect": "deny",
        "action": "provider.use",
        "resource": "openai"
      }
    ]
  }
}
```

A denied provider becomes unavailable for model selection or use, regardless of configuration status.

## Supported Policy Actions

| Action | Resource | Description |
|--------|----------|-------------|
| `provider.use` | Provider ID (e.g., `openai`) | Allow/deny LLM provider usage |

## Wildcard Matching

The `resource` field supports wildcards: `*` matches zero or more characters; `?` matches one character.

```json
{
  "experimental": {
    "policies": [
      {
        "effect": "deny",
        "action": "provider.use",
        "resource": "company-*"
      }
    ]
  }
}
```

## Rule Precedence

**Last matching rule wins.** Place broad rules first, then specific exceptions after them.

### Allow Only Anthropic

```json
{
  "experimental": {
    "policies": [
      {
        "effect": "deny",
        "action": "provider.use",
        "resource": "*"
      },
      {
        "effect": "allow",
        "action": "provider.use",
        "resource": "anthropic"
      }
    ]
  }
}
```

Default behavior: provider use is allowed if no policy matches.

**Priority hierarchy:** Global policies override project policies, preventing repository-level re-enablement of globally denied providers.

## Provider Lists Migration

Replace legacy `disabled_providers` and `enabled_providers` settings with policies.

### Replace `disabled_providers`

```json
{
  "experimental": {
    "policies": [
      { "effect": "deny", "action": "provider.use", "resource": "openai" },
      { "effect": "deny", "action": "provider.use", "resource": "google" }
    ]
  }
}
```

### Replace `enabled_providers`

```json
{
  "experimental": {
    "policies": [
      { "effect": "deny", "action": "provider.use", "resource": "*" },
      { "effect": "allow", "action": "provider.use", "resource": "anthropic" },
      { "effect": "allow", "action": "provider.use", "resource": "openai" }
    ]
  }
}
```
