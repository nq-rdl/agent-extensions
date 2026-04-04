/**
 * MCP stdio server entry point for pi-rpc.
 *
 * Exposes pi.dev session management as MCP tools:
 *   pi_create, pi_prompt, pi_prompt_async,
 *   pi_get_messages, pi_get_state, pi_abort, pi_delete, pi_list
 *
 * Transport: stdio (registered via .mcp.json in the platform adapter)
 * Server:    pi-rpc ConnectRPC service (default: http://localhost:4097)
 *            Override with PI_SERVER_URL env var.
 *
 * Prerequisites:
 *   - pi-server must be running before MCP tools are called
 *   - Start it: cd skills/pi-rpc/scripts && make serve
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerTools } from "./tools.js";

const server = new McpServer({
  name: "pi-rpc",
  version: "0.1.0",
});

registerTools(server);

process.on("SIGTERM", () => process.exit(0));
process.on("SIGINT", () => process.exit(0));

const transport = new StdioServerTransport();
await server.connect(transport);
