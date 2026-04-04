/**
 * MCP tool registrations for pi-rpc.
 *
 * Each tool maps to one pirpc.v1.SessionService endpoint.
 * The pi-server must be running (make serve in the pi-rpc skill scripts/).
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  piCreate,
  piPrompt,
  piPromptAsync,
  piGetMessages,
  piGetState,
  piAbort,
  piDelete,
  piList,
} from "./client.js";

const sessionIdSchema = z.string().describe("Session ID returned by pi_create");

export function registerTools(server: McpServer): void {
  server.tool(
    "pi_create",
    "Create a new pi.dev coding agent session. Spawns a pi --mode rpc subprocess. Returns a session_id for subsequent calls.",
    {
      provider: z.string().describe('AI provider, e.g. "openai-codex" or "anthropic"'),
      model: z.string().describe('Model ID, e.g. "gpt-5.4" or "claude-sonnet-4-20250514"'),
      cwd: z.string().optional().describe("Working directory for the pi.dev subprocess"),
      thinking_level: z
        .enum(["off", "minimal", "low", "medium", "high", "xhigh"])
        .optional()
        .describe("Thinking level for reasoning models"),
    },
    async ({ provider, model, cwd, thinking_level }) => {
      const result = await piCreate(provider, model, cwd, thinking_level);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }
  );

  server.tool(
    "pi_prompt",
    "Send a prompt to a pi.dev session and wait for completion (synchronous, up to 5 minutes). Returns session state and messages.",
    {
      session_id: sessionIdSchema,
      message: z.string().describe("Prompt to send to the coding agent"),
    },
    async ({ session_id, message }) => {
      const result = await piPrompt(session_id, message);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }
  );

  server.tool(
    "pi_prompt_async",
    "Send a prompt to a pi.dev session without waiting. Returns immediately. Use pi_get_state to monitor progress.",
    {
      session_id: sessionIdSchema,
      message: z.string().describe("Prompt to send to the coding agent"),
    },
    async ({ session_id, message }) => {
      const result = await piPromptAsync(session_id, message);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }
  );

  server.tool(
    "pi_get_messages",
    "Retrieve all conversation messages buffered in a pi.dev session.",
    {
      session_id: sessionIdSchema,
    },
    async ({ session_id }) => {
      const result = await piGetMessages(session_id);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }
  );

  server.tool(
    "pi_get_state",
    "Get current state of a pi.dev session (IDLE, RUNNING, ERROR, TERMINATED) and metadata.",
    {
      session_id: sessionIdSchema,
    },
    async ({ session_id }) => {
      const result = await piGetState(session_id);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }
  );

  server.tool(
    "pi_abort",
    "Abort the current operation in a pi.dev session. The session remains open for further prompts.",
    {
      session_id: sessionIdSchema,
    },
    async ({ session_id }) => {
      const result = await piAbort(session_id);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }
  );

  server.tool(
    "pi_delete",
    "Delete a pi.dev session. Kills the subprocess and frees all resources.",
    {
      session_id: sessionIdSchema,
    },
    async ({ session_id }) => {
      const result = await piDelete(session_id);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }
  );

  server.tool(
    "pi_list",
    "List all active pi.dev sessions managed by the pi-server. Use as a health check (empty array = server ready).",
    {},
    async () => {
      const result = await piList();
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }
  );
}
