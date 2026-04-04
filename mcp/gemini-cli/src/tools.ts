/**
 * MCP tool definitions for the Gemini CLI server.
 *
 * Five tools:
 * 1. gemini_run           — Core one-shot dispatch
 * 2. gemini_web_search    — Dedicated web search (flash default)
 * 3. gemini_run_with_context — Run with piped stdin context
 * 4. gemini_resume        — Continue a previous session
 * 5. gemini_list_models   — List available models
 */

import { z } from "zod";
import { runGemini, runGeminiWithContext, resumeGemini } from "./gemini.js";
import { acpAsk } from "./acpClient.js";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { writeFileSync, mkdirSync } from "fs";
import { dirname } from "path";

/**
 * Available Gemini model IDs plus named presets.
 * Presets are resolved to real IDs in buildArgs — use them to avoid
 * memorising full model strings.
 */
const GEMINI_MODELS = [
  // ── Named presets (recommended) ──────────────────────────────────────────
  "fast",               // → gemini-3-flash-preview   (default for most tasks)
  "quality",            // → gemini-3.1-pro-preview   (complex reasoning / architecture)
  // ── Full model IDs ───────────────────────────────────────────────────────
  "gemini-3-flash-preview",
  "gemini-3.1-pro-preview",
  "gemini-3-pro-preview",
  "gemini-2.5-pro",
  "gemini-2.5-flash",
  "gemini-2.5-flash-lite",
  "auto",               // routes to cheapest available — avoid unless intentional
] as const;

/** Shared option schemas reused across tools */
const modelSchema = z
  .enum(GEMINI_MODELS)
  .optional()
  .describe(
    "Model to use. " +
    "PREFER 'fast' (→ gemini-3-flash-preview) for most tasks — web search, code review, analysis, generation. " +
    "Use 'quality' (→ gemini-3.1-pro-preview) for complex reasoning, architecture design, nuanced tasks. " +
    "Avoid 'auto' — it routes to the cheapest model (gemini-2.5-flash-lite) regardless of task complexity. " +
    "Default when omitted: GEMINI_DEFAULT_MODEL env var (gemini-3-flash-preview)."
  );

const approvalModeSchema = z
  .enum(["yolo", "auto_edit", "default"])
  .default("yolo")
  .describe("yolo=auto-approve all (required for headless); auto_edit=approve edits only; default=blocks in headless");

const sandboxSchema = z
  .boolean()
  .default(false)
  .describe(
    "Sandbox tool execution. Default false — Gemini CLI sandbox sets HOME=/home/node " +
    "which requires a specific system setup. Enable only if your system supports it."
  );

const systemContextSchema = z
  .string()
  .optional()
  .describe(
    "System-level instructions injected as GEMINI.md. Sets Gemini's persona/output format. " +
    "E.g. 'Return JSON with fields: title, summary, url' or 'You are a security auditor.'"
  );

const timeoutSchema = z
  .number()
  .positive()
  .default(300_000)
  .describe("Timeout in milliseconds. Default: 300000 (5 minutes).");

const cwdSchema = z
  .string()
  .optional()
  .describe("Working directory for the Gemini subprocess. Defaults to current directory.");

const allowedToolsSchema = z
  .array(z.string())
  .optional()
  .describe("Limit which tools Gemini can use. E.g. ['web_search', 'read_file']");

const outputFileSchema = z
  .string()
  .optional()
  .describe(
    "Absolute path to write the full response JSON. When set, only stats + metadata are returned to the caller " +
    "(response_bytes, output_file, session_id, stats). Use for outputs >10KB to avoid context window bloat."
  );

/** Register all Gemini CLI tools on an MCP server instance */
export function registerTools(server: McpServer): void {
  // ─── gemini_run ───────────────────────────────────────────────────────────
  server.tool(
    "gemini_run",
    "Run a prompt headlessly with Gemini CLI. Returns the response, session ID (for follow-up with gemini_resume), and token stats. " +
    "Defaults to yolo+sandbox for safe headless operation. Use for coding tasks, analysis, generation, or any job you want to offload.",
    {
      prompt: z.string().describe("The prompt or task for Gemini"),
      model: modelSchema,
      approval_mode: approvalModeSchema,
      sandbox: sandboxSchema,
      system_context: systemContextSchema,
      timeout_ms: timeoutSchema,
      cwd: cwdSchema,
      allowed_tools: allowedToolsSchema,
      output_file: outputFileSchema,
    },
    async ({ prompt, model, approval_mode, sandbox, system_context, timeout_ms, cwd, allowed_tools, output_file }) => {
      const result = await runGemini(prompt, {
        model,
        approval_mode,
        sandbox,
        system_context,
        timeout_ms,
        cwd,
        allowed_tools,
      });
      if (output_file) {
        mkdirSync(dirname(output_file), { recursive: true });
        const json = JSON.stringify(result, null, 2);
        writeFileSync(output_file, json, "utf-8");
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              session_id: result.session_id,
              stats: result.stats,
              output_file,
              response_bytes: Buffer.byteLength(json, "utf-8"),
            }, null, 2),
          }],
        };
      }
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    }
  );

  // ─── gemini_web_search ────────────────────────────────────────────────────
  server.tool(
    "gemini_web_search",
    "Search the web using Gemini CLI's built-in search tool. " +
    "Defaults to 'gemini-3-flash-preview' for speed — retrieval tasks don't need pro quality. " +
    "Use system_context to control output format (e.g. JSON citations, structured summaries).",
    {
      query: z.string().describe("Natural language search query"),
      model: z
        .enum(GEMINI_MODELS)
        .optional()
        .describe("Model for web search. Defaults to 'fast' (gemini-3-flash-preview) — retrieval tasks don't need pro quality. Use 'quality' only for deep research synthesis."),
      system_context: systemContextSchema,
      timeout_ms: timeoutSchema,
    },
    async ({ query, model, system_context, timeout_ms }) => {
      // Frame the query to ensure Gemini uses its web search tool
      const prompt = `Search the web for: ${query}\n\nProvide a thorough, accurate answer based on current web results.`;
      const result = await runGemini(prompt, {
        model,
        approval_mode: "yolo",
        sandbox: true,
        system_context,
        timeout_ms,
        allowed_tools: ["web_search"],
      });
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    }
  );

  // ─── gemini_run_with_context ──────────────────────────────────────────────
  server.tool(
    "gemini_run_with_context",
    "Run Gemini with piped context — file contents, git diffs, logs, command output, etc. " +
    "The context is passed via stdin so it doesn't need to be escaped in the prompt. " +
    "Perfect for code review, log analysis, diff summarization, or any task where you have a large blob of text to process.",
    {
      prompt: z.string().describe("Instructions for how to process the context"),
      context: z.string().describe("The content to process (file contents, git diff, logs, etc.)"),
      model: modelSchema,
      approval_mode: approvalModeSchema,
      sandbox: sandboxSchema,
      system_context: systemContextSchema,
      timeout_ms: timeoutSchema,
      cwd: cwdSchema,
      output_file: outputFileSchema,
    },
    async ({ prompt, context, model, approval_mode, sandbox, system_context, timeout_ms, cwd, output_file }) => {
      const result = await runGeminiWithContext(prompt, context, {
        model,
        approval_mode,
        sandbox,
        system_context,
        timeout_ms,
        cwd,
      });
      if (output_file) {
        mkdirSync(dirname(output_file), { recursive: true });
        const json = JSON.stringify(result, null, 2);
        writeFileSync(output_file, json, "utf-8");
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              session_id: result.session_id,
              stats: result.stats,
              output_file,
              response_bytes: Buffer.byteLength(json, "utf-8"),
            }, null, 2),
          }],
        };
      }
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    }
  );

  // ─── gemini_resume ────────────────────────────────────────────────────────
  server.tool(
    "gemini_resume",
    "Continue a previous Gemini session for multi-turn conversations. " +
    "Each gemini_run/gemini_web_search call returns a session_id — use it here to follow up. " +
    "The resumed session has full context of the prior exchange without re-sending it.",
    {
      session_id: z.string().describe("session_id from a previous gemini_run or gemini_web_search call"),
      prompt: z.string().describe("Follow-up prompt continuing the previous session"),
      model: modelSchema,
      approval_mode: approvalModeSchema,
      sandbox: sandboxSchema,
      system_context: systemContextSchema,
      timeout_ms: timeoutSchema,
    },
    async ({ session_id, prompt, model, approval_mode, sandbox, system_context, timeout_ms }) => {
      const result = await resumeGemini(session_id, prompt, {
        model,
        approval_mode,
        sandbox,
        system_context,
        timeout_ms,
      });
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    }
  );

  // ─── gemini_acp_ask ───────────────────────────────────────────────────────
  server.tool(
    "gemini_acp_ask",
    "Ask a question to a persistent, stateful Gemini session. Unlike gemini_run (one-shot), this maintains full conversation context " +
    "across calls — Gemini remembers everything said previously. Perfect for interactive supervisors, iterative reviewers, or any workflow " +
    "where you need back-and-forth collaboration. The session is created lazily on first call and persists until the MCP server exits. " +
    "Use session_name to run multiple concurrent sessions (e.g. 'supervisor' on quality, 'checker' on fast).",
    {
      question: z.string().describe("The question or prompt to send to the persistent session"),
      context: z.string().optional().describe("Optional extra context prepended to the question (file contents, data, etc.)"),
      session_name: z
        .string()
        .default("default")
        .describe("Named session slot. Each name gets its own persistent subprocess. Default: 'default'"),
      model: z
        .enum(GEMINI_MODELS)
        .optional()
        .describe("Model for this session (set on first call, ignored on subsequent calls to the same session_name)"),
      system_context: z
        .string()
        .optional()
        .describe("Persona/instructions for the session (set on first call via GEMINI.md, ignored on subsequent calls)"),
    },
    async ({ question, context, session_name, model, system_context }) => {
      const result = await acpAsk(question, {
        context,
        session_name,
        model,
        system_context,
      });
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    }
  );

  // ─── gemini_list_models ───────────────────────────────────────────────────
  server.tool(
    "gemini_list_models",
    "List available Gemini models with guidance on when to use each.",
    {},
    async () => {
      const models = [
        {
          id: "auto",
          description: "Routes to the best model automatically (default). Use when unsure.",
        },
        {
          id: "gemini-3.1-pro-preview",
          description: "Gemini 3.1 Pro Preview. Highest quality. Best for: complex reasoning, architecture design, nuanced tasks.",
        },
        {
          id: "gemini-3-pro-preview",
          description: "Gemini 3 Pro Preview. High quality. Best for: complex tasks requiring strong reasoning.",
        },
        {
          id: "gemini-3-flash-preview",
          description: "Gemini 3 Flash Preview. Fast and balanced. Best for: web search, code review, most tasks. Recommended default.",
        },
        {
          id: "gemini-2.5-pro",
          description: "Gemini 2.5 Pro. Stable high quality. Best for: long documents, extended context tasks.",
        },
        {
          id: "gemini-2.5-flash",
          description: "Gemini 2.5 Flash. Balanced speed/quality. Best for: general tasks.",
        },
        {
          id: "gemini-2.5-flash-lite",
          description: "Gemini 2.5 Flash-Lite. Fastest, lowest cost. Best for: simple lookups, classification.",
        },
      ];
      const defaultModel = process.env.GEMINI_DEFAULT_MODEL ?? "auto";
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({ models, default_model: defaultModel }, null, 2),
          },
        ],
      };
    }
  );
}
