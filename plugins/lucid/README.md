# Lucid

Wires the hosted **Lucid** MCP server into Claude Code, exposing Lucid's
visual-collaboration tools (Lucidchart / Lucidspark) as MCP tools. This plugin
ships only the server declaration — no skills or agents — so it can be enabled
on its own.

## Install

```bash
/plugin marketplace add nq-rdl/agent-extensions   # once per machine
/plugin                                            # enable "lucid"
```

## Authenticate

Lucid is a hosted service that uses OAuth — there is no API key to configure.
After enabling the plugin, open `/mcp`, select **lucid**, and choose
**Authenticate**. A browser window completes the Lucid sign-in; tokens are then
managed by Claude Code. Until that is done, `/mcp` reports the server as
`Needs authentication` (expected — it means the endpoint is reachable).

Tools surface under the `plugin:lucid:lucid` server, i.e.
`mcp__plugin_lucid_lucid__<tool-name>`.

## Transport

Streamable HTTP (`type: http`) at `https://mcp.lucid.app/mcp`.
