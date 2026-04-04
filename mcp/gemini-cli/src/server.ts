/**
 * MCP stdio server entry point for Gemini CLI.
 *
 * Wraps Gemini CLI headless mode as MCP tools:
 * - gemini_run              One-shot prompt dispatch
 * - gemini_web_search       Dedicated web search (flash default)
 * - gemini_run_with_context Run with piped stdin context
 * - gemini_resume           Continue a previous session (--resume)
 * - gemini_acp_ask          Persistent interactive session (--acp, JSON-RPC 2.0)
 * - gemini_list_models      List available models
 *
 * Transport: stdio (Claude Code discovers via .mcp.json in the plugin)
 * Binary:    configurable via GEMINI_BINARY env var (default: "gemini")
 * Context:   GEMINI_SYSTEM_MD env var for persistent default system context
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerTools } from "./tools.js";
import { acpShutdownAll } from "./acpClient.js";

const server = new McpServer({
  name: "gemini-cli",
  version: "0.1.0",
});

registerTools(server);

// Clean up ACP subprocesses on exit
process.on("SIGTERM", async () => {
  await acpShutdownAll();
  process.exit(0);
});
process.on("SIGINT", async () => {
  await acpShutdownAll();
  process.exit(0);
});

const transport = new StdioServerTransport();
await server.connect(transport);
