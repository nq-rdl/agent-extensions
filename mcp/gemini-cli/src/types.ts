/**
 * Types for the Gemini CLI MCP server.
 * Modelled on the stream-json output format from `gemini --output-format stream-json`.
 */

/**
 * Gemini model IDs and named presets.
 * Prefer "fast" or "quality" — they resolve to the right model without
 * requiring callers to remember full ID strings.
 */
export type GeminiModel =
  | "fast"               // preset → gemini-3-flash-preview (recommended default)
  | "quality"            // preset → gemini-3.1-pro-preview (complex reasoning)
  | "gemini-3-flash-preview"
  | "gemini-3.1-pro-preview"
  | "gemini-3-pro-preview"
  | "gemini-2.5-pro"
  | "gemini-2.5-flash"
  | "gemini-2.5-flash-lite"
  | "auto"               // routes to cheapest available — avoid
  | (string & {});       // forward-compatibility

/** Approval modes for headless operation */
export type ApprovalMode = "yolo" | "auto_edit" | "default";

/** Options passed to every gemini invocation */
export interface GeminiOptions {
  /** Gemini model to use. Defaults to "auto". */
  model?: GeminiModel;
  /**
   * Approval mode for tool use.
   * Defaults to "yolo" — required for headless operation (no TTY for confirmations).
   */
  approval_mode?: ApprovalMode;
  /**
   * Sandbox tool execution. Defaults to false.
   *
   * NOTE: Gemini CLI's sandbox sets HOME=/home/node internally, which requires
   * a node user home directory to exist. Disable sandbox (default) unless your
   * system is configured for Gemini CLI sandboxing.
   * When enabled with yolo, sandboxing limits blast radius.
   */
  sandbox?: boolean;
  /**
   * System-level instructions injected as a temporary GEMINI.md via --include-directories.
   * Overrides the GEMINI_SYSTEM_MD environment variable.
   */
  system_context?: string;
  /** Working directory for the subprocess. Defaults to process.cwd(). */
  cwd?: string;
  /** Timeout in milliseconds. Defaults to 300000 (5 minutes). */
  timeout_ms?: number;
  /** Limit which tools Gemini can use (comma-separated tool names). */
  allowed_tools?: string[];
  /** Session ID from a previous run for multi-turn continuation. */
  session_id?: string;
  /** When set, write the full response JSON to this absolute path and return only stats/metadata to the caller. */
  output_file?: string;
}

/** Result returned by all gemini_run variants */
export interface GeminiResult {
  /** The model's final response text */
  response: string;
  /** Session ID from the init event — use with gemini_resume for multi-turn */
  session_id: string;
  /** Token usage and latency statistics */
  stats: GeminiStats;
}

/**
 * Token usage and latency stats from Gemini CLI JSON output.
 * Actual fields from --output-format json:
 *   { models: { "gemini-3-flash-preview": { api: {...}, tokens: {...} } }, tools: {...}, files: {...} }
 * Actual fields from stream-json result event:
 *   { total_tokens, input_tokens, output_tokens, cached, duration_ms, tool_calls, models: {...} }
 */
export interface GeminiStats {
  // stream-json result event fields
  total_tokens?: number;
  input_tokens?: number;
  output_tokens?: number;
  cached?: number;
  duration_ms?: number;
  tool_calls?: number;
  // json format nested models breakdown
  models?: Record<string, unknown>;
  // json format top-level tool/file stats
  tools?: unknown;
  files?: unknown;
}

/** A single JSONL event from `--output-format stream-json` */
export type StreamEvent =
  | InitEvent
  | MessageEvent
  | ToolUseEvent
  | ToolResultEvent
  | ErrorEvent
  | ResultEvent;

export interface InitEvent {
  type: "init";
  sessionId: string;
  model: string;
}

export interface MessageEvent {
  type: "message";
  role: "user" | "assistant";
  content: string;
}

export interface ToolUseEvent {
  type: "tool_use";
  tool: string;
  args: Record<string, unknown>;
}

export interface ToolResultEvent {
  type: "tool_result";
  tool: string;
  result: unknown;
}

export interface ErrorEvent {
  type: "error";
  message: string;
  code?: string;
}

export interface ResultEvent {
  type: "result";
  response: string;
  stats: GeminiStats;
}

// ── ACP (Agent Communication Protocol) types ──────────────────────────────

/** JSON-RPC 2.0 request (outgoing) */
export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params?: Record<string, unknown>;
}

/** JSON-RPC 2.0 success response (incoming) */
export interface JsonRpcResult {
  jsonrpc: "2.0";
  id: number;
  result: Record<string, unknown>;
}

/** JSON-RPC 2.0 error response (incoming) */
export interface JsonRpcError {
  jsonrpc: "2.0";
  id: number;
  error: { code: number; message: string; data?: unknown };
}

/** JSON-RPC 2.0 notification (incoming, no id) */
export interface JsonRpcNotification {
  jsonrpc: "2.0";
  method: string;
  params?: Record<string, unknown>;
}

/** Any incoming JSON-RPC message */
export type JsonRpcMessage = JsonRpcResult | JsonRpcError | JsonRpcNotification;

/** ACP session/update notification payload */
export interface AcpSessionUpdate {
  sessionId: string;
  update: {
    sessionUpdate: string;
    text?: string;
  };
}

/** ACP session/prompt result */
export interface AcpPromptResult {
  stopReason: string;
  usage: {
    inputTokens?: number;
    outputTokens?: number;
    totalTokens?: number;
  };
}

/** Options for creating an ACP session */
export interface AcpSessionOptions {
  model?: string;
  system_context?: string;
  cwd?: string;
}

/** Return value from acpAsk */
export interface AcpAskResult {
  answer: string;
  session_id: string;
  turn: number;
  usage: AcpPromptResult["usage"];
}
