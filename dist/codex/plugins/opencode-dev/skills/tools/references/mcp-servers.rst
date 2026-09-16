<!-- Source: https://opencode.ai/docs/mcp-servers/ — fetched 2026-06-29. Canonical truth; verify here (and re-check the live page for drift) before authoring OpenCode tools code. -->

# MCP Servers Technical Documentation

## Overview
OpenCode supports integrating external tools via the Model Context Protocol (MCP), offering both local and remote server configurations. "MCP tools are automatically available to the LLM alongside built-in tools" once added.

## Enable Configuration

Basic MCP configuration structure in `opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "name-of-mcp-server": {
      "enabled": true
    }
  }
}
```

### Remote Defaults Override
Organizations can provide default MCP servers via `.well-known/opencode` endpoints. Local config values override remote defaults through config precedence.

## Local MCP Servers

Configuration type: `"local"`

```jsonc
{
  "mcp": {
    "my-local-mcp-server": {
      "type": "local",
      "command": ["npx", "-y", "my-mcp-command"],
      "enabled": true,
      "environment": {
        "MY_ENV_VAR": "value"
      }
    }
  }
}
```

### Local Server Options

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `type` | String | Y | Must be `"local"` |
| `command` | Array | Y | Command and arguments to run |
| `cwd` | String | N | Working directory for process |
| `environment` | Object | N | Environment variables |
| `enabled` | Boolean | N | Enable/disable on startup |
| `timeout` | Number | N | Tool fetch timeout in ms (default: 5000) |

## Remote MCP Servers

Configuration type: `"remote"`

```json
{
  "mcp": {
    "my-remote-mcp": {
      "type": "remote",
      "url": "https://my-mcp-server.com",
      "enabled": true,
      "headers": {
        "Authorization": "Bearer MY_API_KEY"
      }
    }
  }
}
```

### Remote Server Options

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `type` | String | Y | Must be `"remote"` |
| `url` | String | Y | Remote server URL |
| `enabled` | Boolean | N | Enable/disable on startup |
| `headers` | Object | N | Request headers |
| `oauth` | Object | N | OAuth configuration |
| `timeout` | Number | N | Tool fetch timeout in ms (default: 5000) |

## OAuth Authentication

### Automatic OAuth
No special configuration needed for most OAuth-enabled servers. OpenCode detects 401 responses and initiates Dynamic Client Registration (RFC 7591).

### Pre-registered Credentials

```json
{
  "mcp": {
    "my-oauth-server": {
      "type": "remote",
      "url": "https://mcp.example.com/mcp",
      "oauth": {
        "clientId": "{env:MY_MCP_CLIENT_ID}",
        "clientSecret": "{env:MY_MCP_CLIENT_SECRET}",
        "scope": "tools:read tools:execute"
      }
    }
  }
}
```

### OAuth CLI Commands

```bash
# Authenticate with server
opencode mcp auth my-oauth-server

# List all servers and auth status
opencode mcp list

# Remove stored credentials
opencode mcp logout my-oauth-server

# Debug OAuth flow
opencode mcp debug my-oauth-server
```

### Disable OAuth

```json
{
  "mcp": {
    "my-api-key-server": {
      "type": "remote",
      "url": "https://mcp.example.com/mcp",
      "oauth": false,
      "headers": {
        "Authorization": "Bearer {env:MY_API_KEY}"
      }
    }
  }
}
```

### OAuth Options

| Option | Type | Description |
|--------|------|-------------|
| `oauth` | Object \| false | OAuth config or `false` to disable |
| `clientId` | String | OAuth client ID |
| `clientSecret` | String | OAuth client secret |
| `scope` | String | OAuth scopes to request |

## Tool Management

### Global Disable

```json
{
  "mcp": {
    "my-mcp-foo": { "type": "local", "command": [...] },
    "my-mcp-bar": { "type": "local", "command": [...] }
  },
  "tools": {
    "my-mcp-foo": false
  }
}
```

### Glob Pattern Disable

```json
{
  "tools": {
    "my-mcp*": false
  }
}
```

### Per-Agent Configuration

```json
{
  "mcp": {
    "my-mcp": {
      "type": "local",
      "command": ["bun", "x", "my-mcp-command"],
      "enabled": true
    }
  },
  "tools": {
    "my-mcp*": false
  },
  "agent": {
    "my-agent": {
      "tools": {
        "my-mcp*": true
      }
    }
  }
}
```

### Glob Pattern Syntax
- `*` matches zero or more characters
- `?` matches exactly one character
- All other characters match literally

## Common MCP Server Examples

### Sentry
```json
{
  "mcp": {
    "sentry": {
      "type": "remote",
      "url": "https://mcp.sentry.dev/mcp",
      "oauth": {}
    }
  }
}
```

Authenticate: `opencode mcp auth sentry`

### Context7
```json
{
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "{env:CONTEXT7_API_KEY}"
      }
    }
  }
}
```

### Grep by Vercel
```json
{
  "mcp": {
    "gh_grep": {
      "type": "remote",
      "url": "https://mcp.grep.app"
    }
  }
}
```

## Important Caveat

"MCP servers add to your context, so you want to be careful with which ones you enable." Certain servers like GitHub MCP can rapidly exceed context limits through token accumulation.
